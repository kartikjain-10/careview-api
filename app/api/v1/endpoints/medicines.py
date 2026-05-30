from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import Settings
from app.core.dependencies import get_settings, get_current_group
from app.db.database import get_db
from app.db import medicine_repository

router = APIRouter(prefix="/medicines", tags=["medicines"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class MedicineBody(BaseModel):
    id: Optional[str] = None
    profile_id: str
    name: str
    dosage: str
    form: str = "tablet"
    brand_name: Optional[str] = None
    instructions: Optional[str] = None
    color: str = "#00C9A7"
    is_active: bool = True
    prescribed_by: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    schedules: list = []


class MedicineLogBody(BaseModel):
    id: Optional[str] = None
    schedule_id: str
    profile_id: str
    scheduled_for: str
    status: str
    taken_at: Optional[str] = None
    skipped_reason: Optional[str] = None
    marked_by: Optional[str] = None
    is_late: bool = False


class StreakBody(BaseModel):
    profile_id: str
    current_streak: int = 0
    longest_streak: int = 0
    freeze_tokens_remaining: int = 3
    streak_history: list = []


class BadgeBody(BaseModel):
    profile_id: str
    badge_key: str


# ── Medicine Routes ───────────────────────────────────────────────────────────

@router.get("")
async def list_medicines(
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        medicines = await medicine_repository.list_medicines(db, group["id"])
    return {"medicines": medicines}


@router.post("", status_code=201)
async def create_medicine(
    body: MedicineBody,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        med = await medicine_repository.create_medicine(db, group["id"], body.model_dump())
    return med


@router.patch("/{medicine_id}")
async def update_medicine(
    medicine_id: str,
    body: MedicineBody,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        existing = await medicine_repository.get_medicine(db, medicine_id)
        if not existing or existing["group_id"] != group["id"]:
            raise HTTPException(status_code=404, detail="Medicine not found")
        updated = await medicine_repository.update_medicine(db, medicine_id, body.model_dump())
    return updated


@router.delete("/{medicine_id}", status_code=204)
async def delete_medicine(
    medicine_id: str,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        existing = await medicine_repository.get_medicine(db, medicine_id)
        if not existing or existing["group_id"] != group["id"]:
            raise HTTPException(status_code=404, detail="Medicine not found")
        await medicine_repository.delete_medicine(db, medicine_id)


# ── Logs ──────────────────────────────────────────────────────────────────────

@router.get("/logs")
async def list_logs(
    profile_id: Optional[str] = None,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        logs = await medicine_repository.list_medicine_logs(db, group["id"], profile_id)
    return {"logs": logs}


@router.post("/logs", status_code=201)
async def upsert_log(
    body: MedicineLogBody,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        log = await medicine_repository.upsert_medicine_log(db, group["id"], body.model_dump())
    return log


# ── Streaks ───────────────────────────────────────────────────────────────────

@router.get("/streaks")
async def list_streaks(
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        streaks = await medicine_repository.list_streaks(db, group["id"])
    return {"streaks": streaks}


@router.post("/streaks", status_code=201)
async def upsert_streak(
    body: StreakBody,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        streak = await medicine_repository.upsert_streak(db, group["id"], body.model_dump())
    return streak


# ── Badges ────────────────────────────────────────────────────────────────────

@router.get("/badges")
async def list_badges(
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        badges = await medicine_repository.list_badges(db, group["id"])
    return {"badges": badges}


@router.post("/badges", status_code=201)
async def award_badge(
    body: BadgeBody,
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        badge = await medicine_repository.award_badge(db, group["id"], body.profile_id, body.badge_key)
    return badge


@router.post("/badges/{profile_id}/seen", status_code=204)
async def mark_seen(
    profile_id: str,
    _group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        await medicine_repository.mark_badges_seen(db, profile_id)
