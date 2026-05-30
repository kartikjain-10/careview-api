from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the current user profile. Also acts as the registration endpoint —
    calling this after Firebase sign-up creates the user record automatically."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "is_admin": bool(user.get("is_admin")),
        "is_active": bool(user.get("is_active", True)),
        "created_at": user.get("created_at"),
        "last_login": user.get("last_login"),
    }
