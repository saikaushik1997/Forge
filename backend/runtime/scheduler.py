import asyncio
from datetime import datetime
from croniter import croniter
from sqlalchemy import select

from database import AsyncSessionLocal
from models.schedule import Schedule
from models.workflow import Workflow
from models.agent import Agent
from models.run import WorkflowRun
from runtime.engine import execute_workflow


async def _fire_run(schedule_id: str):
    async with AsyncSessionLocal() as db:
        schedule = await db.get(Schedule, schedule_id)
        if not schedule:
            return

        workflow = await db.get(Workflow, schedule.workflow_id)
        if not workflow:
            return

        nodes = workflow.graph_definition.get("nodes", [])
        agent_ids = [n["data"]["agent_id"] for n in nodes]
        result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        agents_map = {
            a.id: {
                "id": a.id, "name": a.name, "role": a.role,
                "system_prompt": a.system_prompt, "model": a.model,
                "tools": a.tools or [], "guardrails": a.guardrails,
                "memory_enabled": a.memory_enabled,
            }
            for a in result.scalars().all()
        }

        run = WorkflowRun(workflow_id=schedule.workflow_id, input=schedule.input, status="running")
        db.add(run)
        await db.commit()
        await db.refresh(run)

        async def on_event(_):
            pass  # no WebSocket for scheduled runs

        try:
            final_state = await execute_workflow(workflow, agents_map, schedule.input, run.id, on_event, db)
            output = final_state["agent_outputs"][-1]["content"] if final_state["agent_outputs"] else ""
            run_record = await db.get(WorkflowRun, run.id)
            run_record.status = "completed"
            run_record.output = output
            run_record.total_tokens = final_state["token_count"]
            run_record.total_cost = final_state.get("cost", 0.0)
            run_record.completed_at = datetime.utcnow()
        except Exception as e:
            run_record = await db.get(WorkflowRun, run.id)
            if run_record:
                run_record.status = "failed"
            print(f"Scheduled run failed for schedule {schedule_id}: {e}")

        await db.commit()


async def scheduler_loop():
    """Wakes every 60 s, fires any schedules whose next_run_at is due."""
    while True:
        await asyncio.sleep(60)
        try:
            async with AsyncSessionLocal() as db:
                now = datetime.utcnow()
                result = await db.execute(
                    select(Schedule).where(Schedule.enabled == True, Schedule.next_run_at <= now)
                )
                due = result.scalars().all()
                for schedule in due:
                    asyncio.create_task(_fire_run(schedule.id))
                    schedule.last_run_at = now
                    schedule.next_run_at = croniter(schedule.cron_expression, now).get_next(datetime)
                await db.commit()
        except Exception as e:
            print(f"Scheduler loop error: {e}")
