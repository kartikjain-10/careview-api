"""
Integration tests for FirebaseAuthMiddleware.
Marked real_firebase_auth so the autouse mock is bypassed — these tests
control firebase_admin.auth.verify_id_token themselves.
"""
import asyncio
import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_settings
from app.db.database import init_db
from app.main import create_app

pytestmark = pytest.mark.real_firebase_auth


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        groq_api_key="test_key",
        chroma_persist_dir=str(tmp_path / "chroma"),
        sqlite_db_path=str(tmp_path / "test.db"),
    )


@pytest.fixture
def client(test_settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    asyncio.get_event_loop().run_until_complete(init_db(test_settings))
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


VALID_USER = {"uid": "user_123", "email": "ward@example.com"}

# ── Public paths — always accessible ─────────────────────────────────────────

def test_should_allow_health_without_token(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_should_allow_docs_without_token(client):
    resp = client.get("/docs")
    assert resp.status_code == 200


# ── Protected paths — no token ────────────────────────────────────────────────

def test_should_return_401_for_wearable_sync_without_token(client):
    with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("no token")):
        resp = client.post("/api/v1/wearable/sync", json={"snapshots": []})
    assert resp.status_code == 401


def test_should_return_401_for_insights_without_token(client):
    resp = client.post(
        "/api/v1/insights",
        json={"parent_id": "p1", "query": "How am I?"},
    )
    assert resp.status_code == 401


def test_should_return_401_for_whatsapp_without_token(client):
    resp = client.post(
        "/api/v1/whatsapp/generate-update",
        json={
            "parent_id": "p1", "ward_id": "w1",
            "language": "english", "phone_number": "+911234567890",
        },
    )
    assert resp.status_code == 401


# ── Protected paths — missing/malformed header ────────────────────────────────

def test_should_return_401_when_bearer_prefix_missing(client):
    resp = client.get(
        "/api/v1/wearable/parent_1",
        headers={"Authorization": "Token abc123"},
    )
    assert resp.status_code == 401


def test_should_return_401_when_authorization_header_absent(client):
    resp = client.get("/api/v1/wearable/parent_1")
    assert resp.status_code == 401


def test_should_return_401_detail_message_on_missing_header(client):
    resp = client.get("/api/v1/wearable/parent_1")
    assert "Authorization" in resp.json()["detail"]


# ── Protected paths — invalid token ───────────────────────────────────────────

def test_should_return_401_when_token_is_invalid(client):
    with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("bad token")):
        resp = client.get(
            "/api/v1/wearable/parent_1",
            headers={"Authorization": "Bearer invalid_token"},
        )
    assert resp.status_code == 401
    assert "Invalid or expired token" in resp.json()["detail"]


# ── Protected paths — valid token ─────────────────────────────────────────────

def test_should_pass_through_when_token_is_valid(client, test_settings):
    with patch("firebase_admin.auth.verify_id_token", return_value=VALID_USER):
        # Seed wearable data first (needs valid token too)
        client.post(
            "/api/v1/wearable/sync",
            json={"snapshots": [{
                "parent_id": "p1", "date": str(date.today()),
                "steps": 5000, "sleep_hours": 7.0,
                "resting_heart_rate": 70, "active_minutes": 30, "mood_score": 7,
            }]},
            headers={"Authorization": "Bearer valid_token"},
        )
        resp = client.get(
            "/api/v1/wearable/p1",
            headers={"Authorization": "Bearer valid_token"},
        )
    assert resp.status_code == 200


def test_should_call_verify_id_token_with_bearer_value(client):
    with patch("firebase_admin.auth.verify_id_token", return_value=VALID_USER) as mock_verify:
        client.get(
            "/api/v1/wearable/parent_1",
            headers={"Authorization": "Bearer my_token_value"},
        )
    mock_verify.assert_called_once_with("my_token_value")
