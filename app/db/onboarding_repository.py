from __future__ import annotations

import json

import aiosqlite


DEFAULT_STEPS = {
    "account": False,
    "household": False,
    "family": False,
    "report": False,
    "medicine": False,
    "done": False,
}


async def get_or_create_state(db: aiosqlite.Connection, user_id: str) -> dict:
    async with db.execute("SELECT * FROM onboarding_states WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        await db.execute(
            "INSERT INTO onboarding_states (user_id, steps) VALUES (?, ?)",
            (user_id, json.dumps(DEFAULT_STEPS)),
        )
        await db.commit()
        return await get_or_create_state(db, user_id)
    state = dict(row)
    state["steps"] = {**DEFAULT_STEPS, **json.loads(state.get("steps") or "{}")}
    state["completed"] = bool(state.get("completed"))
    return state


async def update_state(
    db: aiosqlite.Connection,
    user_id: str,
    current_step: str | None = None,
    completed: bool | None = None,
    steps: dict | None = None,
) -> dict:
    state = await get_or_create_state(db, user_id)
    next_steps = {**state["steps"], **(steps or {})}
    next_step = current_step or state["current_step"]
    next_completed = state["completed"] if completed is None else completed
    await db.execute(
        """
        UPDATE onboarding_states
        SET current_step = ?, completed = ?, steps = ?, updated_at = datetime('now')
        WHERE user_id = ?
        """,
        (next_step, int(next_completed), json.dumps(next_steps), user_id),
    )
    await db.commit()
    return await get_or_create_state(db, user_id)
