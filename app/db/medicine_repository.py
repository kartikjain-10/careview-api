from __future__ import annotations

import json
import uuid
from typing import Optional

import aiosqlite


# ── Medicines ────────────────────────────────────────────────────────────────

async def list_medicines(db: aiosqlite.Connection, group_id: str) -> list[dict]:
    async with db.execute(
        "SELECT * FROM medicines WHERE group_id = ? ORDER BY created_at", (group_id,)
    ) as cur:
        rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["schedules"] = json.loads(d.get("schedules") or "[]")
        result.append(d)
    return result


async def get_medicine(db: aiosqlite.Connection, mid: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM medicines WHERE id = ?", (mid,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["schedules"] = json.loads(d.get("schedules") or "[]")
    return d


async def create_medicine(db: aiosqlite.Connection, group_id: str, data: dict) -> dict:
    mid = data.get("id") or str(uuid.uuid4())
    schedules = json.dumps(data.get("schedules", []))
    await db.execute(
        """
        INSERT INTO medicines
            (id, profile_id, group_id, name, brand_name, dosage, form,
             instructions, color, is_active, prescribed_by, start_date, end_date, schedules)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mid,
            data["profile_id"],
            group_id,
            data["name"],
            data.get("brand_name"),
            data["dosage"],
            data.get("form", "tablet"),
            data.get("instructions"),
            data.get("color", "#00C9A7"),
            int(data.get("is_active", True)),
            data.get("prescribed_by"),
            data.get("start_date"),
            data.get("end_date"),
            schedules,
        ),
    )
    await db.commit()
    return await get_medicine(db, mid)


async def update_medicine(db: aiosqlite.Connection, mid: str, data: dict) -> Optional[dict]:
    allowed = {
        "name", "brand_name", "dosage", "form", "instructions",
        "color", "is_active", "prescribed_by", "start_date", "end_date",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if "schedules" in data:
        updates["schedules"] = json.dumps(data["schedules"])
    if not updates:
        return await get_medicine(db, mid)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [mid]
    await db.execute(f"UPDATE medicines SET {set_clause} WHERE id = ?", values)
    await db.commit()
    return await get_medicine(db, mid)


async def delete_medicine(db: aiosqlite.Connection, mid: str) -> bool:
    await db.execute("DELETE FROM medicines WHERE id = ?", (mid,))
    await db.commit()
    return True


# ── Medicine Logs ────────────────────────────────────────────────────────────

async def list_medicine_logs(db: aiosqlite.Connection, group_id: str, profile_id: Optional[str] = None) -> list[dict]:
    if profile_id:
        sql = "SELECT * FROM medicine_logs WHERE group_id = ? AND profile_id = ? ORDER BY scheduled_for DESC"
        params = (group_id, profile_id)
    else:
        sql = "SELECT * FROM medicine_logs WHERE group_id = ? ORDER BY scheduled_for DESC"
        params = (group_id,)
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def upsert_medicine_log(db: aiosqlite.Connection, group_id: str, data: dict) -> dict:
    lid = data.get("id") or str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO medicine_logs
            (id, schedule_id, profile_id, group_id, scheduled_for, status,
             taken_at, skipped_reason, marked_by, is_late)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status         = excluded.status,
            taken_at       = excluded.taken_at,
            skipped_reason = excluded.skipped_reason,
            marked_by      = excluded.marked_by,
            is_late        = excluded.is_late
        """,
        (
            lid,
            data["schedule_id"],
            data["profile_id"],
            group_id,
            data["scheduled_for"],
            data["status"],
            data.get("taken_at"),
            data.get("skipped_reason"),
            data.get("marked_by"),
            int(data.get("is_late", False)),
        ),
    )
    await db.commit()
    async with db.execute("SELECT * FROM medicine_logs WHERE id = ?", (lid,)) as cur:
        row = await cur.fetchone()
    return dict(row)


# ── Medicine Streaks ─────────────────────────────────────────────────────────

async def get_streak(db: aiosqlite.Connection, profile_id: str) -> Optional[dict]:
    async with db.execute("SELECT * FROM medicine_streaks WHERE profile_id = ?", (profile_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["streak_history"] = json.loads(d.get("streak_history") or "[]")
    return d


async def list_streaks(db: aiosqlite.Connection, group_id: str) -> list[dict]:
    async with db.execute("SELECT * FROM medicine_streaks WHERE group_id = ?", (group_id,)) as cur:
        rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["streak_history"] = json.loads(d.get("streak_history") or "[]")
        result.append(d)
    return result


async def upsert_streak(db: aiosqlite.Connection, group_id: str, data: dict) -> dict:
    await db.execute(
        """
        INSERT INTO medicine_streaks
            (profile_id, group_id, current_streak, longest_streak,
             last_updated, freeze_tokens_remaining, streak_history)
        VALUES (?, ?, ?, ?, datetime('now'), ?, ?)
        ON CONFLICT(profile_id) DO UPDATE SET
            current_streak          = excluded.current_streak,
            longest_streak          = excluded.longest_streak,
            last_updated            = datetime('now'),
            freeze_tokens_remaining = excluded.freeze_tokens_remaining,
            streak_history          = excluded.streak_history
        """,
        (
            data["profile_id"],
            group_id,
            data.get("current_streak", 0),
            data.get("longest_streak", 0),
            data.get("freeze_tokens_remaining", 3),
            json.dumps(data.get("streak_history", [])),
        ),
    )
    await db.commit()
    return await get_streak(db, data["profile_id"])


# ── XP Events ────────────────────────────────────────────────────────────────

async def list_xp_events(db: aiosqlite.Connection, group_id: str) -> list[dict]:
    async with db.execute(
        "SELECT * FROM xp_events WHERE group_id = ? ORDER BY created_at DESC", (group_id,)
    ) as cur:
        rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d.get("metadata") or "{}")
        result.append(d)
    return result


async def add_xp_event(db: aiosqlite.Connection, group_id: str, data: dict) -> dict:
    eid = data.get("id") or str(uuid.uuid4())
    await db.execute(
        "INSERT INTO xp_events (id, profile_id, group_id, action_type, xp_amount, metadata) VALUES (?, ?, ?, ?, ?, ?)",
        (eid, data["profile_id"], group_id, data["action_type"], data["xp_amount"], json.dumps(data.get("metadata", {}))),
    )
    await db.commit()
    async with db.execute("SELECT * FROM xp_events WHERE id = ?", (eid,)) as cur:
        row = await cur.fetchone()
    d = dict(row)
    d["metadata"] = json.loads(d.get("metadata") or "{}")
    return d


# ── Member Badges ────────────────────────────────────────────────────────────

async def list_badges(db: aiosqlite.Connection, group_id: str) -> list[dict]:
    async with db.execute("SELECT * FROM member_badges WHERE group_id = ?", (group_id,)) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def award_badge(db: aiosqlite.Connection, group_id: str, profile_id: str, badge_key: str) -> dict:
    await db.execute(
        """
        INSERT INTO member_badges (profile_id, badge_key, group_id)
        VALUES (?, ?, ?)
        ON CONFLICT(profile_id, badge_key) DO NOTHING
        """,
        (profile_id, badge_key, group_id),
    )
    await db.commit()
    async with db.execute(
        "SELECT * FROM member_badges WHERE profile_id = ? AND badge_key = ?", (profile_id, badge_key)
    ) as cur:
        row = await cur.fetchone()
    return dict(row)


async def mark_badges_seen(db: aiosqlite.Connection, profile_id: str) -> None:
    await db.execute("UPDATE member_badges SET seen = 1 WHERE profile_id = ?", (profile_id,))
    await db.commit()
