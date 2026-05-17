"""Integration tests for POST /api/v1/insights — mocked LLM + vectorstore."""
import asyncio
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_llm, get_settings, get_vectorstore
from app.db.database import init_db
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path):
    return Settings(
        groq_api_key="test_key",
        chroma_persist_dir=str(tmp_path / "chroma"),
        sqlite_db_path=str(tmp_path / "test.db"),
    )


@pytest.fixture
def mock_vs():
    vs = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = []
    vs.as_retriever.return_value = mock_retriever
    return vs


@pytest.fixture
def client(test_settings, mock_vs):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_llm] = lambda: MagicMock()
    app.dependency_overrides[get_vectorstore] = lambda: mock_vs

    asyncio.get_event_loop().run_until_complete(init_db(test_settings))
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _mock_chain_fn(return_value="Wellness trend looks positive."):
    """Return a fake chain function that records its last call."""
    calls = []

    def run(parent_id, query, wearable_summary=""):
        calls.append({"parent_id": parent_id, "query": query, "wearable_summary": wearable_summary})
        return return_value

    run.calls = calls
    return run


def test_should_return_200_with_insight_text(client):
    mock_run = _mock_chain_fn("Your wellness seems on a good track.")
    with patch("app.api.v1.endpoints.insights.build_insight_chain", return_value=mock_run):
        resp = client.post(
            "/api/v1/insights",
            json={"parent_id": "p1", "query": "How are my steps this week?"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["insight"] == "Your wellness seems on a good track."
    assert body["parent_id"] == "p1"


def test_should_include_wearable_data_in_prompt_when_available(client):
    # Seed wearable data first
    client.post("/api/v1/wearable/sync", json={"snapshots": [{
        "parent_id": "p2",
        "date": str(date.today()),
        "steps": 9000, "sleep_hours": 8.0,
        "resting_heart_rate": 60, "active_minutes": 55, "mood_score": 9,
    }]})

    mock_run = _mock_chain_fn()
    with patch("app.api.v1.endpoints.insights.build_insight_chain", return_value=mock_run):
        client.post("/api/v1/insights", json={"parent_id": "p2", "query": "Steps update?"})

    assert len(mock_run.calls) == 1
    assert "9000" in mock_run.calls[0]["wearable_summary"]


def test_should_use_fallback_summary_when_no_wearable_data(client):
    mock_run = _mock_chain_fn()
    with patch("app.api.v1.endpoints.insights.build_insight_chain", return_value=mock_run):
        client.post("/api/v1/insights", json={"parent_id": "no_data_parent", "query": "How am I?"})

    assert len(mock_run.calls) == 1
    assert "No recent wearable data" in mock_run.calls[0]["wearable_summary"]


def test_should_return_500_when_chain_raises(client):
    def boom(parent_id, query, wearable_summary=""):
        raise RuntimeError("Groq down")

    with patch("app.api.v1.endpoints.insights.build_insight_chain", return_value=boom):
        resp = client.post(
            "/api/v1/insights",
            json={"parent_id": "p1", "query": "How am I?"},
        )
    assert resp.status_code == 500
    assert "Insight generation failed" in resp.json()["detail"]
