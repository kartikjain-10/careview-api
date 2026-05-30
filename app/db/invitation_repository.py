from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expiry_iso(hours: int = 72) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


async def create_invitation(
    db: aiosqlite.Connection,
    group_id: str,
    invited_by: str,
    channel: str,           # 'email' | 'whatsapp'
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    iid = str(uuid.uuid4())
    token = secrets.token_urlsafe(24)
    await db.execute(
        """
        INSERT INTO invitations
            (id, group_id, invited_by, email, phone, channel, token, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (iid, group_id, invited_by, email, phone, channel, token, _expiry_iso()),
    )
    await db.commit()
    return await get_invitation(db, iid)


async def get_invitation(db: aiosqlite.Connection, iid: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM invitations WHERE id = ?", (iid,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_invitation_by_token(db: aiosqlite.Connection, token: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM invitations WHERE token = ?", (token,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def list_invitations(db: aiosqlite.Connection, group_id: str) -> list[dict]:
    async with db.execute(
        "SELECT * FROM invitations WHERE group_id = ? ORDER BY created_at DESC", (group_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def accept_invitation(db: aiosqlite.Connection, token: str) -> Optional[dict]:
    inv = await get_invitation_by_token(db, token)
    if not inv:
        return None
    if inv["status"] != "pending":
        return inv
    if datetime.fromisoformat(inv["expires_at"]) < datetime.now(timezone.utc):
        await db.execute("UPDATE invitations SET status = 'expired' WHERE token = ?", (token,))
        await db.commit()
        return None
    await db.execute(
        "UPDATE invitations SET status = 'accepted', accepted_at = ? WHERE token = ?",
        (_now_iso(), token),
    )
    await db.commit()
    return await get_invitation_by_token(db, token)


async def revoke_invitation(db: aiosqlite.Connection, iid: str) -> None:
    await db.execute("UPDATE invitations SET status = 'expired' WHERE id = ?", (iid,))
    await db.commit()
