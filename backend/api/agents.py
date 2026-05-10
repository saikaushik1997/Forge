from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.agent import Agent

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    role: str
    system_prompt: str
    model: str = "claude-sonnet-4-6"
    tools: list[str] = []
    memory_enabled: bool = False
    guardrails: dict = {}
    channel: Optional[str] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    tools: Optional[list[str]] = None
    memory_enabled: Optional[bool] = None
    guardrails: Optional[dict] = None
    channel: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    role: str
    system_prompt: str
    model: str
    tools: list[str]
    memory_enabled: bool
    guardrails: dict
    channel: Optional[str]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, agent: Agent):
        return cls(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            system_prompt=agent.system_prompt,
            model=agent.model,
            tools=agent.tools or [],
            memory_enabled=agent.memory_enabled,
            guardrails=agent.guardrails or {},
            channel=agent.channel,
            created_at=agent.created_at.isoformat(),
            updated_at=agent.updated_at.isoformat(),
        )


@router.get("/", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    return [AgentResponse.from_orm(a) for a in result.scalars().all()]


@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    import traceback as tb
    try:
        agent = Agent(**body.model_dump())
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return AgentResponse.from_orm(agent)
    except Exception as e:
        raise HTTPException(status_code=500, detail=tb.format_exc())


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.from_orm(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, body: AgentUpdate, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return AgentResponse.from_orm(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
