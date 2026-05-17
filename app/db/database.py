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
)


async def init_db(settings: Settings) -> None:
    async with aiosqlite.connect(settings.sqlite_db_path) as db:
        await db.execute(CREATE_SNAPSHOTS_TABLE)
        await db.execute(CREATE_SNAPSHOTS_INDEX)
        await db.execute(CREATE_DOCUMENTS_TABLE)
        await db.execute(CREATE_DOCUMENTS_INDEX)
        await db.commit()


@asynccontextmanager
async def get_db(settings: Settings) -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(settings.sqlite_db_path) as db:
        db.row_factory = aiosqlite.Row
        yield db
