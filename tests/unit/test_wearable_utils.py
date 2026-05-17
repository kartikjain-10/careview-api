"""Unit tests for format_wearable_summary utility."""
from datetime import date, datetime
from app.ai.utils import format_wearable_summary
from app.models.schemas import WearableSnapshotRecord


def _snap(**kwargs) -> WearableSnapshotRecord:
    defaults = dict(
        id=1, parent_id="p1",
        date=date(2025, 1, 15),
        steps=6000, sleep_hours=7.0,
        resting_heart_rate=68, active_minutes=40,
        mood_score=7, created_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return WearableSnapshotRecord(**defaults)


def test_should_return_no_data_message_when_empty():
    result = format_wearable_summary([])
    assert "No recent wearable data" in result


def test_should_include_steps_in_output():
    snap = _snap(steps=8500)
    result = format_wearable_summary([snap])
    assert "8500" in result


def test_should_include_sleep_in_output():
    snap = _snap(sleep_hours=6.5)
    result = format_wearable_summary([snap])
    assert "6.5" in result


def test_should_include_averages_section():
    snaps = [_snap(steps=5000, id=i) for i in range(1, 4)]
    result = format_wearable_summary(snaps)
    assert "averages" in result.lower()


def test_should_show_all_snapshot_dates():
    snaps = [
        _snap(id=1, date=date(2025, 1, 10)),
        _snap(id=2, date=date(2025, 1, 11)),
    ]
    result = format_wearable_summary(snaps)
    assert "2025-01-10" in result
    assert "2025-01-11" in result


def test_should_compute_correct_average_steps():
    snaps = [
        _snap(id=1, steps=4000),
        _snap(id=2, steps=8000),
    ]
    result = format_wearable_summary(snaps)
    assert "6000" in result
