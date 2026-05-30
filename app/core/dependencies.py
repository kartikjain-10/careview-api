from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from langchain_groq import ChatGroq
from langchain_chroma import Chroma

from app.core.config import Settings, settings as _default_settings
from app.ai.llm import build_llm
from app.ai.vectorstore import build_vectorstore
from app.db.database import get_db
from app.db import user_repository, family_repository


@lru_cache
def get_settings() -> Settings:
    return _default_settings


def get_llm(s: Settings = Depends(get_settings)) -> ChatGroq:
    return build_llm(s)


def get_vectorstore(s: Settings = Depends(get_settings)) -> Chroma:
    return build_vectorstore(s)


# ── Auth dependencies ────────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    s: Settings = Depends(get_settings),
) -> dict:
    """Resolve Firebase token (set by middleware) into a DB user row.
    Auto-creates the user record on first login."""
    uid: str = getattr(request.state, "uid", None)
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    email: str = getattr(request.state, "email", "")
    name: str = getattr(request.state, "name", "")

    async with get_db(s) as db:
        user = await user_repository.upsert_user(db, uid, email, name)

        # Auto-promote the seed admin email on their first login
        if email and email == s.admin_seed_email and not user.get("is_admin"):
            await user_repository.set_admin(db, uid, True)
            user["is_admin"] = 1

    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Account suspended")

    return user


async def get_current_group(
    user: dict = Depends(get_current_user),
    s: Settings = Depends(get_settings),
) -> dict:
    """Return the active family group for this user, creating their own if needed."""
    async with get_db(s) as db:
        group = await family_repository.get_or_create_group(db, user["id"])
    return group


async def get_current_membership(
    user: dict = Depends(get_current_user),
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
) -> dict:
    async with get_db(s) as db:
        membership = await family_repository.get_membership(db, group["id"], user["id"])
    if not membership or membership.get("status") != "active":
        raise HTTPException(status_code=403, detail="Family access required")
    return membership


async def require_family_write(
    membership: dict = Depends(get_current_membership),
) -> dict:
    if membership.get("role") not in {"owner", "caregiver"}:
        raise HTTPException(status_code=403, detail="Caregiver access required")
    return membership


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
