from __future__ import annotations

import aiosqlite
from typing import Optional


async def upsert_user(db: aiosqlite.Connection, uid: str, email: str, name: str) -> dict:
    """Create or update user on login. Returns the user row."""
    await db.execute(
        """
        INSERT INTO users (id, email, name, last_login)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            email      = excluded.email,
            name       = CASE WHEN excluded.name != '' THEN excluded.name ELSE users.name END,
            last_login = datetime('now')
        """,
        (uid, email, name),
    )
    await db.commit()
    return await get_user(db, uid)


async def get_user(db: aiosqlite.Connection, uid: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM users WHERE id = ?", (uid,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_user_by_email(db: aiosqlite.Connection, email: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM users WHERE email = ?", (email,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def set_admin(db: aiosqlite.Connection, uid: str, is_admin: bool) -> None:
    await db.execute("UPDATE users SET is_admin = ? WHERE id = ?", (int(is_admin), uid))
    await db.commit()


async def set_active(db: aiosqlite.Connection, uid: str, is_active: bool) -> None:
    await db.execute("UPDATE users SET is_active = ? WHERE id = ?", (int(is_active), uid))
    await db.commit()


async def list_users(db: aiosqlite.Connection, limit: int = 100, offset: int = 0) -> list[dict]:
    async with db.execute(
        "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def count_users(db: aiosqlite.Connection) -> int:
    async with db.execute("SELECT COUNT(*) FROM users") as cur:
        row = await cur.fetchone()
    return row[0] if row else 0


async def admin_stats(db: aiosqlite.Connection) -> dict:
    async with db.execute("SELECT COUNT(*) FROM users") as cur:
        total = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as cur:
        active = (await cur.fetchone())[0]
    async with db.execute(
        "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"
    ) as cur:
        today = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM family_groups") as cur:
        groups = (await cur.fetchone())[0]
    async with db.execute(
        "SELECT COUNT(*) FROM invitations WHERE status = 'pending'"
    ) as cur:
        pending_invites = (await cur.fetchone())[0]
    return {
        "total_users": total,
        "active_users": active,
        "signups_today": today,
        "family_groups": groups,
        "pending_invitations": pending_invites,
    }
