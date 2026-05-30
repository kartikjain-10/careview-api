from __future__ import annotations

import json
import uuid
from typing import Optional

import aiosqlite


async def list_habit_logs(
    db: aiosqlite.Connection,
    group_id: str,
    profile_id: Optional[str] = None,
    limit: int = 90,
) -> list[dict]:
    if profile_id:
        sql = """
            SELECT * FROM habit_logs
            WHERE group_id = ? AND profile_id = ?
            ORDER BY date DESC LIMIT ?
        """
        params = (group_id, profile_id, limit)
    else:
        sql = "SELECT * FROM habit_logs WHERE group_id = ? ORDER BY date DESC LIMIT ?"
        params = (group_id, limit)
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["activity"] = json.loads(d["activity"]) if d.get("activity") else None
        d["sleep"] = json.loads(d["sleep"]) if d.get("sleep") else None
        result.append(d)
    return result


async def upsert_habit_log(db: aiosqlite.Connection, group_id: str, data: dict) -> dict:
    hid = data.get("id") or str(uuid.uuid4())
    activity = json.dumps(data["activity"]) if data.get("activity") else None
    sleep = json.dumps(data["sleep"]) if data.get("sleep") else None
    await db.execute(
        """
        INSERT INTO habit_logs
            (id, profile_id, group_id, date, water_glasses, mood, activity, sleep)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, date) DO UPDATE SET
            water_glasses = excluded.water_glasses,
            mood          = excluded.mood,
            activity      = excluded.activity,
            sleep         = excluded.sleep
        """,
        (
            hid,
            data["profile_id"],
            group_id,
            data["date"],
            data.get("water_glasses", 0),
            data.get("mood"),
            activity,
            sleep,
        ),
    )
    await db.commit()
    async with db.execute(
        "SELECT * FROM habit_logs WHERE profile_id = ? AND date = ?",
        (data["profile_id"], data["date"]),
    ) as cur:
        row = await cur.fetchone()
    d = dict(row)
    d["activity"] = json.loads(d["activity"]) if d.get("activity") else None
    d["sleep"] = json.loads(d["sleep"]) if d.get("sleep") else None
    return d
