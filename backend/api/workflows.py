from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.workflow import Workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])


class GraphDefinition(BaseModel):
    nodes: list[dict] = []
    edges: list[dict] = []


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    graph_definition: GraphDefinition = GraphDefinition()
    is_template: bool = False


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    graph_definition: Optional[GraphDefinition] = None
    is_template: Optional[bool] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    graph_definition: dict
    is_template: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, w: Workflow):
        return cls(
            id=w.id,
            name=w.name,
            description=w.description or "",
            graph_definition=w.graph_definition or {"nodes": [], "edges": []},
            is_template=w.is_template,
            created_at=w.created_at.isoformat(),
            updated_at=w.updated_at.isoformat(),
        )


@router.get("/", response_model=list[WorkflowResponse])
async def list_workflows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).order_by(Workflow.created_at.desc()))
    return [WorkflowResponse.from_orm(w) for w in result.scalars().all()]


@router.post("/", response_model=WorkflowResponse, status_code=201)
async def create_workflow(body: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    workflow = Workflow(
        name=body.name,
        description=body.description,
        graph_definition=body.graph_definition.model_dump(),
        is_template=body.is_template,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return WorkflowResponse.from_orm(workflow)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    w = await db.get(Workflow, workflow_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowResponse.from_orm(w)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, body: WorkflowUpdate, db: AsyncSession = Depends(get_db)):
    w = await db.get(Workflow, workflow_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workflow not found")
    updates = body.model_dump(exclude_none=True)
    if "graph_definition" in updates:
        updates["graph_definition"] = updates["graph_definition"]
    for field, value in updates.items():
        setattr(w, field, value)
    await db.commit()
    await db.refresh(w)
    return WorkflowResponse.from_orm(w)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    w = await db.get(Workflow, workflow_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(w)
    await db.commit()
