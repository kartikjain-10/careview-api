from __future__ import annotations

import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.core.config import Settings
from app.db.models import (
    # existing
    CREATE_SNAPSHOTS_TABLE, CREATE_SNAPSHOTS_INDEX,
    CREATE_DOCUMENTS_TABLE, CREATE_DOCUMENTS_INDEX,
    CREATE_HEALTH_INSIGHTS_TABLE, CREATE_HEALTH_INSIGHTS_INDEX,
    # new
    CREATE_USERS_TABLE, CREATE_USERS_EMAIL_INDEX,
    CREATE_FAMILY_GROUPS_TABLE,
    CREATE_FAMILY_GROUP_USERS_TABLE, CREATE_FAMILY_GROUP_USERS_USER_INDEX,
    CREATE_FAMILY_MEMBERS_TABLE, CREATE_FAMILY_MEMBERS_INDEX,
    CREATE_INVITATIONS_TABLE, CREATE_INVITATIONS_TOKEN_INDEX, CREATE_INVITATIONS_GROUP_INDEX,
    CREATE_MEDICINES_TABLE, CREATE_MEDICINES_INDEX,
    CREATE_MEDICINE_LOGS_TABLE, CREATE_MEDICINE_LOGS_INDEX,
    CREATE_MEDICINE_STREAKS_TABLE,
    CREATE_HABIT_LOGS_TABLE, CREATE_HABIT_LOGS_INDEX,
    CREATE_XP_EVENTS_TABLE, CREATE_XP_EVENTS_INDEX,
    CREATE_MEMBER_BADGES_TABLE,
    CREATE_ONBOARDING_STATES_TABLE,
    CREATE_DOCTOR_SHARES_TABLE, CREATE_DOCTOR_SHARES_GROUP_INDEX, CREATE_DOCTOR_SHARES_TOKEN_INDEX,
)


async def init_db(settings: Settings) -> None:
    async with aiosqlite.connect(settings.sqlite_db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # Existing tables
        await db.execute(CREATE_SNAPSHOTS_TABLE)
        await db.execute(CREATE_SNAPSHOTS_INDEX)
        await db.execute(CREATE_DOCUMENTS_TABLE)
        await db.execute(CREATE_DOCUMENTS_INDEX)
        await _ensure_column(db, "documents", "processing_status", "TEXT NOT NULL DEFAULT 'indexed'")
        await _ensure_column(db, "documents", "extraction_error", "TEXT")
        await _ensure_column(db, "documents", "summary", "TEXT")
        await _ensure_column(db, "documents", "report_type", "TEXT")
        await _ensure_column(db, "documents", "report_date", "TEXT")
        await _ensure_column(db, "documents", "provider", "TEXT")
        await _ensure_column(db, "documents", "status", "TEXT NOT NULL DEFAULT 'active'")
        await db.execute(CREATE_HEALTH_INSIGHTS_TABLE)
        await db.execute(CREATE_HEALTH_INSIGHTS_INDEX)

        # Users
        await db.execute(CREATE_USERS_TABLE)
        await db.execute(CREATE_USERS_EMAIL_INDEX)

        # Family
        await db.execute(CREATE_FAMILY_GROUPS_TABLE)
        await db.execute(CREATE_FAMILY_GROUP_USERS_TABLE)
        await db.execute(CREATE_FAMILY_GROUP_USERS_USER_INDEX)
        await db.execute(CREATE_FAMILY_MEMBERS_TABLE)
        await db.execute(CREATE_FAMILY_MEMBERS_INDEX)

        # Invitations
        await db.execute(CREATE_INVITATIONS_TABLE)
        await db.execute(CREATE_INVITATIONS_TOKEN_INDEX)
        await db.execute(CREATE_INVITATIONS_GROUP_INDEX)

        # Medicines
        await db.execute(CREATE_MEDICINES_TABLE)
        await db.execute(CREATE_MEDICINES_INDEX)
        await db.execute(CREATE_MEDICINE_LOGS_TABLE)
        await db.execute(CREATE_MEDICINE_LOGS_INDEX)
        await db.execute(CREATE_MEDICINE_STREAKS_TABLE)

        # Habits / XP / Badges
        await db.execute(CREATE_HABIT_LOGS_TABLE)
        await db.execute(CREATE_HABIT_LOGS_INDEX)
        await db.execute(CREATE_XP_EVENTS_TABLE)
        await db.execute(CREATE_XP_EVENTS_INDEX)
        await db.execute(CREATE_MEMBER_BADGES_TABLE)

        # Onboarding / sharing
        await db.execute(CREATE_ONBOARDING_STATES_TABLE)
        await db.execute(CREATE_DOCTOR_SHARES_TABLE)
        await db.execute(CREATE_DOCTOR_SHARES_GROUP_INDEX)
        await db.execute(CREATE_DOCTOR_SHARES_TOKEN_INDEX)

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
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
