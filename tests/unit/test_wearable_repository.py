"""Unit tests for WearableRepository — mocked aiosqlite connection."""
import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.repository import WearableRepository
from app.models.schemas import WearableSnapshot, WearableSnapshotRecord


def _make_snapshot(**kwargs) -> WearableSnapshot:
    defaults = dict(
        parent_id="parent_1",
        date=date(2025, 1, 15),
        steps=6000,
        sleep_hours=7.0,
        resting_heart_rate=68,
        active_minutes=40,
        mood_score=7,
    )
    defaults.update(kwargs)
    return WearableSnapshot(**defaults)


def _make_row(snapshot: WearableSnapshot, row_id: int = 1) -> dict:
    return {
        "id": row_id,
        "parent_id": snapshot.parent_id,
        "date": snapshot.date.isoformat(),
        "steps": snapshot.steps,
        "sleep_hours": snapshot.sleep_hours,
        "resting_heart_rate": snapshot.resting_heart_rate,
        "active_minutes": snapshot.active_minutes,
        "mood_score": snapshot.mood_score,
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.mark.asyncio
async def test_should_insert_snapshot_when_valid_data_provided():
    snapshot = _make_snapshot()
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    repo = WearableRepository(db)
    await repo.insert_snapshot(snapshot)

    db.execute.assert_called_once()
    call_args = db.execute.call_args
    assert "INSERT INTO wearable_snapshots" in call_args[0][0]
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_should_pass_correct_values_to_insert():
    snapshot = _make_snapshot(steps=8000, mood_score=9)
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    repo = WearableRepository(db)
    await repo.insert_snapshot(snapshot)

    params = db.execute.call_args[0][1]
    assert params[0] == "parent_1"
    assert params[2] == 8000
    assert params[6] == 9


@pytest.mark.asyncio
async def test_should_return_snapshots_for_parent():
    snapshot = _make_snapshot()
    row = _make_row(snapshot)

    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[row])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    db = AsyncMock()
    db.execute = MagicMock(return_value=mock_cursor)

    # Make row subscriptable like aiosqlite.Row
    row_obj = MagicMock()
    row_obj.__getitem__ = lambda self, k: row[k]
    mock_cursor.fetchall = AsyncMock(return_value=[row_obj])

    repo = WearableRepository(db)
    results = await repo.get_snapshots_by_parent("parent_1")

    assert len(results) == 1
    assert isinstance(results[0], WearableSnapshotRecord)
    assert results[0].parent_id == "parent_1"
    assert results[0].steps == 6000


@pytest.mark.asyncio
async def test_should_return_empty_list_when_no_snapshots():
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    db = AsyncMock()
    db.execute = MagicMock(return_value=mock_cursor)

    repo = WearableRepository(db)
    results = await repo.get_snapshots_by_parent("unknown_parent")

    assert results == []


@pytest.mark.asyncio
async def test_should_filter_by_parent_id_in_query():
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    db = AsyncMock()
    db.execute = MagicMock(return_value=mock_cursor)

    repo = WearableRepository(db)
    await repo.get_snapshots_by_parent("parent_42")

    call_args = db.execute.call_args
    query = call_args[0][0]
    params = call_args[0][1]
    assert "parent_id" in query
    assert params[0] == "parent_42"
