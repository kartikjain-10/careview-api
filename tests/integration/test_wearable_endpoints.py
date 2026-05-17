"""Integration tests for wearable endpoints — real SQLite in a temp file."""
import pytest
import tempfile
import os
from datetime import date

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.db.database import init_db
from app.main import create_app


@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    return db_path


@pytest.fixture
def test_settings(temp_db):
    return Settings(
        groq_api_key="test_key",
        chroma_persist_dir="./data/chroma",
        sqlite_db_path=temp_db,
    )


@pytest.fixture
def client(test_settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings

    # Initialise DB synchronously before test client starts
    import asyncio
    asyncio.get_event_loop().run_until_complete(init_db(test_settings))

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


SNAPSHOT_PAYLOAD = {
    "snapshots": [
        {
            "parent_id": "parent_1",
            "date": str(date.today()),
            "steps": 7500,
            "sleep_hours": 7.5,
            "resting_heart_rate": 65,
            "active_minutes": 45,
            "mood_score": 8,
        }
    ]
}


def test_should_return_200_when_valid_sync_request(client):
    resp = client.post("/api/v1/wearable/sync", json=SNAPSHOT_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["inserted"] == 1


def test_should_insert_multiple_snapshots_in_one_request(client):
    payload = {
        "snapshots": [
            {
                "parent_id": "parent_2",
                "date": "2025-01-10",
                "steps": 5000,
                "sleep_hours": 6.0,
                "resting_heart_rate": 70,
                "active_minutes": 30,
                "mood_score": 6,
            },
            {
                "parent_id": "parent_2",
                "date": "2025-01-11",
                "steps": 8000,
                "sleep_hours": 8.0,
                "resting_heart_rate": 62,
                "active_minutes": 60,
                "mood_score": 9,
            },
        ]
    }
    resp = client.post("/api/v1/wearable/sync", json=payload)
    assert resp.status_code == 200
    assert resp.json()["inserted"] == 2


def test_should_return_422_when_empty_snapshots_list(client):
    resp = client.post("/api/v1/wearable/sync", json={"snapshots": []})
    assert resp.status_code == 422


def test_should_return_snapshots_after_sync(client):
    client.post("/api/v1/wearable/sync", json=SNAPSHOT_PAYLOAD)
    resp = client.get("/api/v1/wearable/parent_1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["parent_id"] == "parent_1"
    assert data[0]["steps"] == 7500


def test_should_return_404_when_no_data_for_parent(client):
    resp = client.get("/api/v1/wearable/nonexistent_parent")
    assert resp.status_code == 404


def test_should_return_correct_snapshot_fields(client):
    client.post("/api/v1/wearable/sync", json=SNAPSHOT_PAYLOAD)
    resp = client.get("/api/v1/wearable/parent_1")
    assert resp.status_code == 200
    record = resp.json()[0]
    for field in ("id", "parent_id", "date", "steps", "sleep_hours",
                  "resting_heart_rate", "active_minutes", "mood_score", "created_at"):
        assert field in record, f"Missing field: {field}"


def test_should_not_return_other_parents_data(client):
    payload_a = {"snapshots": [{
        "parent_id": "alice", "date": str(date.today()),
        "steps": 3000, "sleep_hours": 5.0, "resting_heart_rate": 75,
        "active_minutes": 20, "mood_score": 5,
    }]}
    payload_b = {"snapshots": [{
        "parent_id": "bob", "date": str(date.today()),
        "steps": 9000, "sleep_hours": 8.5, "resting_heart_rate": 60,
        "active_minutes": 70, "mood_score": 10,
    }]}
    client.post("/api/v1/wearable/sync", json=payload_a)
    client.post("/api/v1/wearable/sync", json=payload_b)

    resp = client.get("/api/v1/wearable/alice")
    assert all(r["parent_id"] == "alice" for r in resp.json())
