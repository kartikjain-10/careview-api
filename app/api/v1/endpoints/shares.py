from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.dependencies import get_current_group, get_current_user, get_settings, require_family_write
from app.db import family_repository, share_repository
from app.db.database import get_db

router = APIRouter(prefix="/shares", tags=["doctor shares"])


class ShareCreateBody(BaseModel):
    member_id: str
    title: str
    scope: list[str] = Field(default_factory=lambda: ["Summary", "Report list", "Wearable snapshot"])
    expires_in_days: int = Field(default=7, ge=1, le=30)


@router.get("/public/{token}")
async def public_share(token: str, s: Settings = Depends(get_settings)):
    async with get_db(s) as db:
        share = await share_repository.get_share_by_token(db, token)
        if not share:
            raise HTTPException(status_code=404, detail="Share not found")
        if share["status"] != "active" or datetime.fromisoformat(share["expires_at"]) < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Share expired or revoked")
        member = await family_repository.get_member(db, share["member_id"])
    return {
        "title": share["title"],
        "scope": share["scope"],
        "expires_at": share["expires_at"],
        "member_name": (member or {}).get("display_name") or (member or {}).get("name") or "Family member",
    }


@router.get("")
async def list_shares(
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        shares = await share_repository.list_shares(db, group["id"])
    return {
        "shares": [
            {**share, "share_link": f"{s.app_base_url}/share/{share['token']}"}
            for share in shares
        ]
    }


@router.post("", status_code=201)
async def create_share(
    body: ShareCreateBody,
    user: dict = Depends(get_current_user),
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        member = await family_repository.get_member(db, body.member_id)
        if not member or member["group_id"] != group["id"]:
            raise HTTPException(status_code=404, detail="Member not found")
        share = await share_repository.create_share(
            db,
            group_id=group["id"],
            member_id=body.member_id,
            created_by=user["id"],
            title=body.title,
            scope=body.scope,
            expires_in_days=body.expires_in_days,
        )
    return {**share, "share_link": f"{s.app_base_url}/share/{share['token']}"}


@router.patch("/{share_id}/revoke")
async def revoke_share(
    share_id: str,
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        share = await share_repository.revoke_share(db, group["id"], share_id)
    if not share or share["group_id"] != group["id"]:
        raise HTTPException(status_code=404, detail="Share not found")
    return share
