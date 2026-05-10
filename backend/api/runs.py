import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db, AsyncSessionLocal
from models.run import WorkflowRun, Message
from models.workflow import Workflow
from models.agent import Agent
from runtime.engine import execute_workflow

router = APIRouter(tags=["runs"])

# in-memory event queues per run_id for WebSocket streaming
_run_queues: dict[str, asyncio.Queue] = {}


def now_iso():
    return datetime.utcnow().isoformat()


class RunCreate(BaseModel):
    workflow_id: str
    input: str


@router.post("/runs", status_code=201)
async def create_run(body: RunCreate, db: AsyncSession = Depends(get_db)):
    workflow = await db.get(Workflow, body.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    run = WorkflowRun(workflow_id=body.workflow_id, input=body.input, status="running")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    queue: asyncio.Queue = asyncio.Queue()
    _run_queues[run.id] = queue

    # load agents
    nodes = workflow.graph_definition.get("nodes", [])
    agent_ids = [n["data"]["agent_id"] for n in nodes]
    result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
    agents_list = result.scalars().all()
    agents_map = {a.id: {"id": a.id, "name": a.name, "role": a.role, "system_prompt": a.system_prompt, "model": a.model, "tools": a.tools or [], "guardrails": a.guardrails} for a in agents_list}

    async def on_event(event: dict):
        await queue.put(event)

    async def run_and_finish():
        async with AsyncSessionLocal() as session:
            try:
                final_state = await execute_workflow(workflow, agents_map, body.input, run.id, on_event, session)
                output = final_state["agent_outputs"][-1]["content"] if final_state["agent_outputs"] else ""
                tokens = final_state["token_count"]
                run_record = await session.get(WorkflowRun, run.id)
                run_record.status = "completed"
                run_record.output = output
                run_record.total_tokens = tokens
                run_record.completed_at = datetime.utcnow()
                await session.commit()
                await queue.put({"type": "run_complete", "run_id": run.id, "output": output, "tokens": tokens})
            except Exception as e:
                run_record = await session.get(WorkflowRun, run.id)
                if run_record:
                    run_record.status = "failed"
                    await session.commit()
                await queue.put({"type": "run_failed", "run_id": run.id, "error": str(e)})
            finally:
                await queue.put(None)  # sentinel to close WebSocket

    asyncio.create_task(run_and_finish())

    return {"run_id": run.id, "status": "running"}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "input": run.input,
        "output": run.output,
        "total_tokens": run.total_tokens,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.get("/runs/{run_id}/messages")
async def get_messages(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.run_id == run_id).order_by(Message.timestamp))
    msgs = result.scalars().all()
    return [
        {"id": m.id, "from_agent": m.from_agent, "to_agent": m.to_agent, "content": m.content, "tokens_used": m.tokens_used, "timestamp": m.timestamp.isoformat()}
        for m in msgs
    ]


@router.get("/runs")
async def list_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkflowRun).order_by(WorkflowRun.started_at.desc()).limit(50))
    runs = result.scalars().all()
    return [
        {"id": r.id, "workflow_id": r.workflow_id, "status": r.status, "input": r.input, "output": r.output, "total_tokens": r.total_tokens, "started_at": r.started_at.isoformat()}
        for r in runs
    ]


@router.websocket("/ws/runs/{run_id}")
async def run_websocket(websocket: WebSocket, run_id: str):
    await websocket.accept()
    queue = _run_queues.get(run_id)
    if not queue:
        await websocket.send_text(json.dumps({"type": "error", "message": "Run not found or already completed"}))
        await websocket.close()
        return
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            await websocket.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    finally:
        _run_queues.pop(run_id, None)
        await websocket.close()
