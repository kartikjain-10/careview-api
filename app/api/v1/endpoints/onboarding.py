from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings
from app.core.dependencies import get_current_user, get_settings
from app.db import onboarding_repository
from app.db.database import get_db

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingPatch(BaseModel):
    current_step: Optional[str] = None
    completed: Optional[bool] = None
    steps: Optional[dict[str, bool]] = None


@router.get("")
async def get_onboarding(
    user: dict = Depends(get_current_user),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        return await onboarding_repository.get_or_create_state(db, user["id"])


@router.patch("")
async def patch_onboarding(
    body: OnboardingPatch,
    user: dict = Depends(get_current_user),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        return await onboarding_repository.update_state(
            db,
            user_id=user["id"],
            current_step=body.current_step,
            completed=body.completed,
            steps=body.steps,
        )
