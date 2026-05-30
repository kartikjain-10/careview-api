from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import Settings
from app.core.dependencies import get_settings, require_admin
from app.db.database import get_db
from app.db import user_repository

router = APIRouter(prefix="/admin", tags=["admin"])


class PatchUserBody(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


@router.get("/stats")
async def get_stats(
    _: dict = Depends(require_admin),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        stats = await user_repository.admin_stats(db)
    return stats


@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    _: dict = Depends(require_admin),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        users = await user_repository.list_users(db, limit=limit, offset=offset)
        total = await user_repository.count_users(db)
    return {"users": users, "total": total}


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: str,
    body: PatchUserBody,
    admin: dict = Depends(require_admin),
    s: Settings = Depends(get_settings),
):
    if user_id == admin["id"] and body.is_admin is False:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin rights")

    async with get_db(s) as db:
        user = await user_repository.get_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if body.is_active is not None:
            await user_repository.set_active(db, user_id, body.is_active)
        if body.is_admin is not None:
            await user_repository.set_admin(db, user_id, body.is_admin)
        updated = await user_repository.get_user(db, user_id)
    return updated
