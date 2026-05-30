from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite


def _expiry(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _row_to_share(row: aiosqlite.Row | None) -> Optional[dict]:
    if not row:
        return None
    share = dict(row)
    share["scope"] = json.loads(share.get("scope") or "[]")
    return share


async def create_share(
    db: aiosqlite.Connection,
    group_id: str,
    member_id: str,
    created_by: str,
    title: str,
    scope: list[str],
    expires_in_days: int = 7,
) -> dict:
    sid = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    await db.execute(
        """
        INSERT INTO doctor_shares
            (id, group_id, member_id, created_by, title, token, scope, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sid, group_id, member_id, created_by, title, token, json.dumps(scope), _expiry(expires_in_days)),
    )
    await db.commit()
    return await get_share(db, sid)


async def get_share(db: aiosqlite.Connection, share_id: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM doctor_shares WHERE id = ?", (share_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_share(row)


async def get_share_by_token(db: aiosqlite.Connection, token: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM doctor_shares WHERE token = ?", (token,)) as cur:
        row = await cur.fetchone()
    return _row_to_share(row)


async def list_shares(db: aiosqlite.Connection, group_id: str) -> list[dict]:
    async with db.execute(
        "SELECT * FROM doctor_shares WHERE group_id = ? ORDER BY created_at DESC",
        (group_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_share(row) for row in rows]


async def revoke_share(db: aiosqlite.Connection, group_id: str, share_id: str) -> Optional[dict]:
    await db.execute(
        """
        UPDATE doctor_shares
        SET status = 'revoked', revoked_at = datetime('now')
        WHERE id = ? AND group_id = ?
        """,
        (share_id, group_id),
    )
    await db.commit()
    return await get_share(db, share_id)
