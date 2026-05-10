from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from croniter import croniter

from database import get_db
from models.schedule import Schedule
from models.workflow import Workflow

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _next_run(cron_expr: str) -> datetime:
    return croniter(cron_expr, datetime.utcnow()).get_next(datetime)


class ScheduleCreate(BaseModel):
    workflow_id: str
    cron_expression: str
    input: str = ""
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    cron_expression: Optional[str] = None
    input: Optional[str] = None
    enabled: Optional[bool] = None


def _fmt(s: Schedule) -> dict:
    return {
        "id": s.id,
        "workflow_id": s.workflow_id,
        "cron_expression": s.cron_expression,
        "input": s.input,
        "enabled": s.enabled,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        "created_at": s.created_at.isoformat(),
    }


@router.get("/")
async def list_schedules(workflow_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(Schedule).order_by(Schedule.created_at.desc())
    if workflow_id:
        q = q.where(Schedule.workflow_id == workflow_id)
    result = await db.execute(q)
    return [_fmt(s) for s in result.scalars().all()]


@router.post("/", status_code=201)
async def create_schedule(body: ScheduleCreate, db: AsyncSession = Depends(get_db)):
    if not await db.get(Workflow, body.workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not croniter.is_valid(body.cron_expression):
        raise HTTPException(status_code=422, detail="Invalid cron expression")
    s = Schedule(
        workflow_id=body.workflow_id,
        cron_expression=body.cron_expression,
        input=body.input,
        enabled=body.enabled,
        next_run_at=_next_run(body.cron_expression),
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _fmt(s)


@router.put("/{schedule_id}")
async def update_schedule(schedule_id: str, body: ScheduleUpdate, db: AsyncSession = Depends(get_db)):
    s = await db.get(Schedule, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if body.cron_expression is not None:
        if not croniter.is_valid(body.cron_expression):
            raise HTTPException(status_code=422, detail="Invalid cron expression")
        s.cron_expression = body.cron_expression
        s.next_run_at = _next_run(body.cron_expression)
    if body.input is not None:
        s.input = body.input
    if body.enabled is not None:
        s.enabled = body.enabled
    await db.commit()
    await db.refresh(s)
    return _fmt(s)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.get(Schedule, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(s)
    await db.commit()
