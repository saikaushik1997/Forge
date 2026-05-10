from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.agent import Agent
from config import settings
from bot.crypto import encrypt_token

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    role: str
    system_prompt: str
    model: str = "claude-sonnet-4-6"
    tools: list[str] = []
    memory_enabled: bool = False
    guardrails: dict = {}
    channel_configs: dict = {}


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    tools: Optional[list[str]] = None
    memory_enabled: Optional[bool] = None
    guardrails: Optional[dict] = None
    channel_configs: Optional[dict] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    role: str
    system_prompt: str
    model: str
    tools: list[str]
    memory_enabled: bool
    guardrails: dict
    channel_configs: dict  # tokens masked — each channel has has_token bool instead
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
            channel_configs=_mask_configs(agent.channel_configs or {}),
            created_at=agent.created_at.isoformat(),
            updated_at=agent.updated_at.isoformat(),
        )


def _maybe_encrypt(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    if not settings.forge_encryption_key:
        return token
    return encrypt_token(token)


def _encrypt_configs(configs: dict) -> dict:
    result = {}
    for channel, cfg in configs.items():
        result[channel] = {**cfg}
        if cfg.get("bot_token"):
            result[channel]["bot_token"] = _maybe_encrypt(cfg["bot_token"])
    return result


def _mask_configs(configs: dict) -> dict:
    """Replace raw tokens with has_token booleans for API responses."""
    result = {}
    for channel, cfg in configs.items():
        masked = {k: v for k, v in cfg.items() if k != "bot_token"}
        masked["has_token"] = bool(cfg.get("bot_token"))
        result[channel] = masked
    return result


@router.get("/", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    return [AgentResponse.from_orm(a) for a in result.scalars().all()]


@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    import traceback as tb
    try:
        data = body.model_dump()
        data["channel_configs"] = _encrypt_configs(data.get("channel_configs") or {})
        agent = Agent(**data)
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
    updates = body.model_dump(exclude_none=True)
    if "channel_configs" in updates:
        # Merge with existing — preserve stored tokens if new submission has no bot_token
        existing = agent.channel_configs or {}
        incoming = updates["channel_configs"]
        merged = {}
        for channel, cfg in incoming.items():
            merged[channel] = {**existing.get(channel, {}), **cfg}
            if cfg.get("bot_token"):
                merged[channel]["bot_token"] = _maybe_encrypt(cfg["bot_token"])
            elif not cfg.get("bot_token") and existing.get(channel, {}).get("bot_token"):
                merged[channel]["bot_token"] = existing[channel]["bot_token"]
        updates["channel_configs"] = merged
    for field, value in updates.items():
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
