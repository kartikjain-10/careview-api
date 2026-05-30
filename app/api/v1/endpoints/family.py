from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import Settings
from app.core.dependencies import get_settings, get_current_group, require_family_write
from app.db.database import get_db
from app.db import family_repository

router = APIRouter(prefix="/family", tags=["family"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class RenameGroupBody(BaseModel):
    name: str


class CreateMemberBody(BaseModel):
    name: str
    relationship: str
    age: Optional[int] = None
    sex: Optional[str] = None
    focus: Optional[str] = None
    formal_name: Optional[str] = None
    display_name: Optional[str] = None
    color: str = "#00C9A7"


class UpdateMemberBody(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    focus: Optional[str] = None
    formal_name: Optional[str] = None
    display_name: Optional[str] = None
    color: Optional[str] = None


class UpdateMembershipBody(BaseModel):
    role: str


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def get_family(
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        members = await family_repository.list_members(db, group["id"])
    return {"group": group, "members": members}


@router.patch("")
async def rename_family(
    body: RenameGroupBody,
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        updated = await family_repository.rename_group(db, group["id"], body.name)
    return updated


@router.post("/members", status_code=201)
async def add_member(
    body: CreateMemberBody,
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        member = await family_repository.create_member(
            db,
            group_id=group["id"],
            name=body.name,
            relationship=body.relationship,
            age=body.age,
            sex=body.sex,
            focus=body.focus,
            formal_name=body.formal_name,
            display_name=body.display_name,
            color=body.color,
        )
    return member


@router.patch("/members/{member_id}")
async def update_member(
    member_id: str,
    body: UpdateMemberBody,
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        member = await family_repository.get_member(db, member_id)
        if not member or member["group_id"] != group["id"]:
            raise HTTPException(status_code=404, detail="Member not found")
        updated = await family_repository.update_member(db, member_id, body.model_dump(exclude_none=True))
    return updated


@router.delete("/members/{member_id}", status_code=204)
async def delete_member(
    member_id: str,
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        member = await family_repository.get_member(db, member_id)
        if not member or member["group_id"] != group["id"]:
            raise HTTPException(status_code=404, detail="Member not found")
        await family_repository.delete_member(db, member_id)


@router.get("/memberships")
async def list_group_memberships(
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        memberships = await family_repository.list_memberships(db, group["id"])
    return {"memberships": memberships}


@router.patch("/memberships/{user_id}")
async def update_group_membership(
    user_id: str,
    body: UpdateMembershipBody,
    group: dict = Depends(get_current_group),
    membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    if membership.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    if body.role not in {"caregiver", "viewer"}:
        raise HTTPException(status_code=422, detail="Role must be caregiver or viewer")
    async with get_db(s) as db:
        updated = await family_repository.update_membership_role(db, group["id"], user_id, body.role)
    if not updated:
        raise HTTPException(status_code=404, detail="Membership not found")
    return updated
