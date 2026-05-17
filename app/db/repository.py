from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List

import aiosqlite

from app.models.schemas import WearableSnapshot, WearableSnapshotRecord


class WearableRepository:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def insert_snapshot(self, snapshot: WearableSnapshot) -> None:
        await self._db.execute(
            """
            INSERT INTO wearable_snapshots
                (parent_id, date, steps, sleep_hours, resting_heart_rate,
                 active_minutes, mood_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.parent_id,
                snapshot.date.isoformat(),
                snapshot.steps,
                snapshot.sleep_hours,
                snapshot.resting_heart_rate,
                snapshot.active_minutes,
                snapshot.mood_score,
                datetime.utcnow().isoformat(),
            ),
        )
        await self._db.commit()

    async def get_snapshots_by_parent(
        self, parent_id: str, days: int = 30
    ) -> List[WearableSnapshotRecord]:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        async with self._db.execute(
            """
            SELECT id, parent_id, date, steps, sleep_hours, resting_heart_rate,
                   active_minutes, mood_score, created_at
            FROM   wearable_snapshots
            WHERE  parent_id = ? AND date >= ?
            ORDER  BY date DESC
            """,
            (parent_id, cutoff),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            WearableSnapshotRecord(
                id=row["id"],
                parent_id=row["parent_id"],
                date=date.fromisoformat(row["date"]),
                steps=row["steps"],
                sleep_hours=row["sleep_hours"],
                resting_heart_rate=row["resting_heart_rate"],
                active_minutes=row["active_minutes"],
                mood_score=row["mood_score"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
