from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings
from app.core.dependencies import get_settings, get_current_group
from app.db.database import get_db
from app.db import habits_repository, medicine_repository

router = APIRouter(prefix="/habits", tags=["habits"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ActivityData(BaseModel):
    type: str
    duration: int


class SleepData(BaseModel):
    quality: str
    bedtime: Optional[str] = None
    wake_time: Optional[str] = None


class HabitLogBody(BaseModel):
    profile_id: str
    date: str
    water_glasses: int = 0
    mood: Optional[str] = None
    activity: Optional[ActivityData] = None
    sleep: Optional[SleepData] = None


class XPEventBody(BaseModel):
    id: Optional[str] = None
    profile_id: str
    action_type: str
    xp_amount: int
    metadata: dict = {}


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_habits(
    profile_id: Optional[str] = None,
    limit: int = 90,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        logs = await habits_repository.list_habit_logs(db, group["id"], profile_id, limit)
    return {"logs": logs}


@router.post("", status_code=201)
async def upsert_habit(
    body: HabitLogBody,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    data = body.model_dump()
    async with get_db(s) as db:
        log = await habits_repository.upsert_habit_log(db, group["id"], data)
    return log


# ── XP Events ────────────────────────────────────────────────────────────────

@router.get("/xp")
async def list_xp(
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        events = await medicine_repository.list_xp_events(db, group["id"])
    return {"xp_events": events}


@router.post("/xp", status_code=201)
async def add_xp(
    body: XPEventBody,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        event = await medicine_repository.add_xp_event(db, group["id"], body.model_dump())
    return event
