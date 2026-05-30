from __future__ import annotations

import secrets
import uuid
from typing import Optional

import aiosqlite


# ── Family Groups ────────────────────────────────────────────────────────────

async def get_group_for_owner(db: aiosqlite.Connection, owner_id: str) -> Optional[dict]:
    async with db.execute(
        "SELECT * FROM family_groups WHERE owner_id = ?", (owner_id,)
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def create_group(db: aiosqlite.Connection, owner_id: str, name: str = "My Family") -> dict:
    gid = str(uuid.uuid4())
    invite_code = secrets.token_urlsafe(8).upper()
    await db.execute(
        "INSERT INTO family_groups (id, owner_id, name, invite_code) VALUES (?, ?, ?, ?)",
        (gid, owner_id, name, invite_code),
    )
    await add_user_to_group(db, gid, owner_id, role="owner")
    await db.commit()
    return await get_group(db, gid)


async def get_group(db: aiosqlite.Connection, gid: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM family_groups WHERE id = ?", (gid,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_or_create_group(db: aiosqlite.Connection, owner_id: str) -> dict:
    membership = await get_active_membership_for_user(db, owner_id)
    if membership:
        group = await get_group(db, membership["group_id"])
        if group:
            return group

    group = await get_group_for_owner(db, owner_id)
    if group:
        await add_user_to_group(db, group["id"], owner_id, role="owner")
    else:
        group = await create_group(db, owner_id)
    return group


# ── Household membership ────────────────────────────────────────────────────

async def add_user_to_group(
    db: aiosqlite.Connection,
    group_id: str,
    user_id: str,
    role: str = "caregiver",
) -> dict:
    await db.execute(
        """
        INSERT INTO family_group_users (group_id, user_id, role, status)
        VALUES (?, ?, ?, 'active')
        ON CONFLICT(group_id, user_id) DO UPDATE SET
            role = CASE
                WHEN family_group_users.role = 'owner' THEN family_group_users.role
                ELSE excluded.role
            END,
            status = 'active'
        """,
        (group_id, user_id, role),
    )
    await db.commit()
    return await get_membership(db, group_id, user_id)


async def get_membership(db: aiosqlite.Connection, group_id: str, user_id: str) -> Optional[dict]:
    async with db.execute(
        "SELECT * FROM family_group_users WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_active_membership_for_user(db: aiosqlite.Connection, user_id: str) -> Optional[dict]:
    async with db.execute(
        """
        SELECT * FROM family_group_users
        WHERE user_id = ? AND status = 'active'
        ORDER BY joined_at DESC
        LIMIT 1
        """,
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def list_memberships(db: aiosqlite.Connection, group_id: str) -> list[dict]:
    async with db.execute(
        """
        SELECT fgu.group_id, fgu.user_id, fgu.role, fgu.status, fgu.joined_at,
               users.email, users.name
        FROM family_group_users fgu
        JOIN users ON users.id = fgu.user_id
        WHERE fgu.group_id = ?
        ORDER BY fgu.joined_at
        """,
        (group_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def update_membership_role(
    db: aiosqlite.Connection,
    group_id: str,
    user_id: str,
    role: str,
) -> Optional[dict]:
    await db.execute(
        """
        UPDATE family_group_users
        SET role = ?
        WHERE group_id = ? AND user_id = ? AND role != 'owner'
        """,
        (role, group_id, user_id),
    )
    await db.commit()
    return await get_membership(db, group_id, user_id)


async def get_group_by_invite_code(db: aiosqlite.Connection, code: str) -> Optional[dict]:
    async with db.execute(
        "SELECT * FROM family_groups WHERE invite_code = ?", (code.upper(),)
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def rename_group(db: aiosqlite.Connection, gid: str, name: str) -> dict:
    await db.execute("UPDATE family_groups SET name = ? WHERE id = ?", (name, gid))
    await db.commit()
    return await get_group(db, gid)


# ── Family Members ───────────────────────────────────────────────────────────

async def list_members(db: aiosqlite.Connection, group_id: str) -> list[dict]:
    async with db.execute(
        "SELECT * FROM family_members WHERE group_id = ? ORDER BY created_at", (group_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_member(db: aiosqlite.Connection, member_id: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM family_members WHERE id = ?", (member_id,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def create_member(
    db: aiosqlite.Connection,
    group_id: str,
    name: str,
    relationship: str,
    age: Optional[int] = None,
    sex: Optional[str] = None,
    focus: Optional[str] = None,
    formal_name: Optional[str] = None,
    display_name: Optional[str] = None,
    color: str = "#00C9A7",
) -> dict:
    mid = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO family_members
            (id, group_id, name, formal_name, display_name, color, relationship, age, sex, focus)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mid, group_id, name,
            formal_name or name,
            display_name or name.split()[0],
            color, relationship, age, sex, focus,
        ),
    )
    await db.commit()
    return await get_member(db, mid)


async def update_member(db: aiosqlite.Connection, member_id: str, fields: dict) -> Optional[dict]:
    allowed = {"name", "formal_name", "display_name", "color", "relationship", "age", "sex", "focus"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return await get_member(db, member_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [member_id]
    await db.execute(f"UPDATE family_members SET {set_clause} WHERE id = ?", values)
    await db.commit()
    return await get_member(db, member_id)


async def delete_member(db: aiosqlite.Connection, member_id: str) -> bool:
    await db.execute("DELETE FROM family_members WHERE id = ?", (member_id,))
    await db.commit()
    return True
