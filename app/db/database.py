from __future__ import annotations

import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.core.config import Settings
from app.db.models import (
    CREATE_SNAPSHOTS_TABLE,
    CREATE_SNAPSHOTS_INDEX,
    CREATE_DOCUMENTS_TABLE,
    CREATE_DOCUMENTS_INDEX,
    CREATE_HEALTH_INSIGHTS_TABLE,
    CREATE_HEALTH_INSIGHTS_INDEX,
)


async def init_db(settings: Settings) -> None:
    async with aiosqlite.connect(settings.sqlite_db_path) as db:
        await db.execute(CREATE_SNAPSHOTS_TABLE)
        await db.execute(CREATE_SNAPSHOTS_INDEX)
        await db.execute(CREATE_DOCUMENTS_TABLE)
        await db.execute(CREATE_DOCUMENTS_INDEX)
        await _ensure_column(db, "documents", "processing_status", "TEXT NOT NULL DEFAULT 'indexed'")
        await _ensure_column(db, "documents", "extraction_error", "TEXT")
        await _ensure_column(db, "documents", "summary", "TEXT")
        await db.execute(CREATE_HEALTH_INSIGHTS_TABLE)
        await db.execute(CREATE_HEALTH_INSIGHTS_INDEX)
        await db.commit()


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    async with db.execute(f"PRAGMA table_info({table})") as cursor:
        rows = await cursor.fetchall()
    if column not in {row[1] for row in rows}:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@asynccontextmanager
async def get_db(settings: Settings) -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(settings.sqlite_db_path) as db:
        db.row_factory = aiosqlite.Row
        yield db
