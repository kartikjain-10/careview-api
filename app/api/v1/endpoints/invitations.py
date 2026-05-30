from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import Settings
from app.core.dependencies import get_settings, get_current_user, get_current_group, require_family_write
from app.db.database import get_db
from app.db import invitation_repository, family_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/invitations", tags=["invitations"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SendInviteBody(BaseModel):
    channel: str            # 'email' | 'whatsapp'
    email: Optional[str] = None
    phone: Optional[str] = None


# ── Notification helpers ──────────────────────────────────────────────────────

async def _send_email(settings: Settings, to_email: str, invite_link: str, inviter_name: str) -> None:
    if not settings.resend_api_key:
        logger.info("[CareView] Email invite would be sent to %s → %s", to_email, invite_link)
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from_email,
                    "to": [to_email],
                    "subject": f"{inviter_name} invited you to CareView",
                    "html": f"""
                        <h2>You're invited to CareView</h2>
                        <p>{inviter_name} has invited you to join their family health dashboard.</p>
                        <a href="{invite_link}" style="background:#00C9A7;color:#fff;padding:12px 24px;
                           border-radius:8px;text-decoration:none;display:inline-block;margin-top:16px;">
                          Accept Invitation
                        </a>
                        <p style="color:#888;font-size:12px;margin-top:24px;">
                          This link expires in 72 hours.
                        </p>
                    """,
                },
                timeout=10,
            )
    except Exception as exc:
        logger.warning("[CareView] Email send failed: %s", exc)


async def _send_whatsapp(settings: Settings, phone: str, invite_link: str, inviter_name: str) -> None:
    if not settings.twilio_account_sid:
        logger.info("[CareView] WhatsApp invite would be sent to %s → %s", phone, invite_link)
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                data={
                    "From": settings.twilio_whatsapp_from,
                    "To": f"whatsapp:{phone}",
                    "Body": (
                        f"👋 {inviter_name} invited you to CareView — a family health dashboard.\n\n"
                        f"Accept here: {invite_link}\n\n"
                        "_Link expires in 72 hours._"
                    ),
                },
                timeout=10,
            )
    except Exception as exc:
        logger.warning("[CareView] WhatsApp send failed: %s", exc)


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def send_invitation(
    body: SendInviteBody,
    user: dict = Depends(get_current_user),
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    if body.channel == "email" and not body.email:
        raise HTTPException(status_code=422, detail="Email required for email channel")
    if body.channel == "whatsapp" and not body.phone:
        raise HTTPException(status_code=422, detail="Phone required for whatsapp channel")

    async with get_db(s) as db:
        inv = await invitation_repository.create_invitation(
            db,
            group_id=group["id"],
            invited_by=user["id"],
            channel=body.channel,
            email=body.email,
            phone=body.phone,
        )

    invite_link = f"{s.app_base_url}/invite/{inv['token']}"
    inviter_name = user.get("name") or user.get("email", "Someone")

    if body.channel == "email" and body.email:
        await _send_email(s, body.email, invite_link, inviter_name)
    elif body.channel == "whatsapp" and body.phone:
        await _send_whatsapp(s, body.phone, invite_link, inviter_name)

    return {**inv, "invite_link": invite_link}


@router.get("")
async def list_invitations(
    group: dict = Depends(get_current_group),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        invites = await invitation_repository.list_invitations(db, group["id"])
    return {"invitations": invites}


@router.get("/preview/{token}")
async def preview_invitation(
    token: str,
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        inv = await invitation_repository.get_invitation_by_token(db, token)
        if not inv:
            raise HTTPException(status_code=404, detail="Invitation not found or expired")
        group = await family_repository.get_group(db, inv["group_id"])

    return {
        "group_id": inv["group_id"],
        "group_name": group["name"] if group else "Family",
        "status": inv["status"],
        "channel": inv["channel"],
        "email": inv["email"],
        "phone": inv["phone"],
        "expires_at": inv["expires_at"],
    }


@router.get("/accept/{token}")
async def preview_invitation_legacy(
    token: str,
    s: Settings = Depends(get_settings),
):
    return await preview_invitation(token, s)


@router.post("/accept/{token}")
async def accept_invitation(
    token: str,
    user: dict = Depends(get_current_user),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        inv = await invitation_repository.accept_invitation(db, token)
        if not inv:
            raise HTTPException(status_code=404, detail="Invitation not found or expired")
        group = await family_repository.get_group(db, inv["group_id"])
        await family_repository.add_user_to_group(db, inv["group_id"], user["id"], role="caregiver")
        membership = await family_repository.get_membership(db, inv["group_id"], user["id"])

    return {
        "group_id": inv["group_id"],
        "group_name": group["name"] if group else "Family",
        "status": inv["status"],
        "membership": membership,
    }


@router.delete("/{invitation_id}", status_code=204)
async def revoke_invitation(
    invitation_id: str,
    group: dict = Depends(get_current_group),
    _membership: dict = Depends(require_family_write),
    s: Settings = Depends(get_settings),
):
    async with get_db(s) as db:
        inv = await invitation_repository.get_invitation(db, invitation_id)
        if not inv or inv["group_id"] != group["id"]:
            raise HTTPException(status_code=404, detail="Invitation not found")
        await invitation_repository.revoke_invitation(db, invitation_id)
