"""Integration tests for POST /api/v1/whatsapp/generate-update."""
import asyncio
import unicodedata
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_llm, get_settings
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
def client(test_settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_llm] = lambda: MagicMock()

    asyncio.get_event_loop().run_until_complete(init_db(test_settings))
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


HINDI_PAYLOAD = {
    "parent_id": "parent_1",
    "ward_id": "ward_1",
    "language": "hindi",
    "phone_number": "+919876543210",
}

ENGLISH_PAYLOAD = {
    "parent_id": "parent_1",
    "ward_id": "ward_1",
    "language": "english",
    "phone_number": "+919876543210",
}

HINDI_SAMPLE = "नमस्ते माँ 🙏\nआप ठीक हैं! आपका ख्याल रखना ❤️"
ENGLISH_SAMPLE = "Hi Maa 🙏\nYou're doing great today! Take care, love you 💙"


def test_should_return_200_for_hindi_request(client):
    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = lambda language, wearable_summary: HINDI_SAMPLE
        resp = client.post("/api/v1/whatsapp/generate-update", json=HINDI_PAYLOAD)

    assert resp.status_code == 200


def test_should_return_correct_fields_in_response(client):
    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = lambda language, wearable_summary: ENGLISH_SAMPLE
        resp = client.post("/api/v1/whatsapp/generate-update", json=ENGLISH_PAYLOAD)

    body = resp.json()
    assert "message" in body
    assert "whatsapp_link" in body
    assert "language" in body


def test_should_echo_language_in_response(client):
    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = lambda language, wearable_summary: HINDI_SAMPLE
        resp = client.post("/api/v1/whatsapp/generate-update", json=HINDI_PAYLOAD)

    assert resp.json()["language"] == "hindi"


def test_should_return_hindi_message_with_devanagari(client):
    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = lambda language, wearable_summary: HINDI_SAMPLE
        resp = client.post("/api/v1/whatsapp/generate-update", json=HINDI_PAYLOAD)

    message = resp.json()["message"]
    has_devanagari = any("ऀ" <= ch <= "ॿ" for ch in message)
    assert has_devanagari, "Hindi message must contain Devanagari script characters"


def test_should_return_english_message_without_devanagari(client):
    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = lambda language, wearable_summary: ENGLISH_SAMPLE
        resp = client.post("/api/v1/whatsapp/generate-update", json=ENGLISH_PAYLOAD)

    message = resp.json()["message"]
    has_devanagari = any("ऀ" <= ch <= "ॿ" for ch in message)
    assert not has_devanagari, "English message must not contain Devanagari script"


def test_should_whatsapp_link_start_with_wa_me(client):
    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = lambda language, wearable_summary: ENGLISH_SAMPLE
        resp = client.post("/api/v1/whatsapp/generate-update", json=ENGLISH_PAYLOAD)

    assert resp.json()["whatsapp_link"].startswith("https://wa.me/")


def test_should_strip_plus_from_phone_in_link(client):
    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = lambda language, wearable_summary: ENGLISH_SAMPLE
        resp = client.post("/api/v1/whatsapp/generate-update", json=ENGLISH_PAYLOAD)

    link = resp.json()["whatsapp_link"]
    # Should contain 919876543210 without the leading +
    assert "919876543210" in link
    # The + must not appear in the phone number portion
    phone_part = link.replace("https://wa.me/", "").split("?")[0]
    assert "+" not in phone_part


def test_should_not_contain_forbidden_words_in_message(client):
    forbidden = ["diagnos", "emergency", "critical", "serious condition"]
    sample = "Hi Maa! Your steps look good. Take care 💙"

    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = lambda language, wearable_summary: sample
        resp = client.post("/api/v1/whatsapp/generate-update", json=ENGLISH_PAYLOAD)

    message = resp.json()["message"].lower()
    for word in forbidden:
        assert word not in message, f"Message contains forbidden word: {word}"


def test_should_include_wearable_data_in_chain_call_when_available(client):
    client.post("/api/v1/wearable/sync", json={"snapshots": [{
        "parent_id": "parent_1",
        "date": str(date.today()),
        "steps": 7777, "sleep_hours": 7.5,
        "resting_heart_rate": 66, "active_minutes": 45, "mood_score": 8,
    }]})

    captured = {}

    def fake_chain(language, wearable_summary):
        captured["wearable_summary"] = wearable_summary
        return ENGLISH_SAMPLE

    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = fake_chain
        client.post("/api/v1/whatsapp/generate-update", json=ENGLISH_PAYLOAD)

    assert "7777" in captured.get("wearable_summary", "")


def test_should_return_500_when_chain_raises(client):
    def boom(language, wearable_summary):
        raise RuntimeError("LLM unavailable")

    with patch("app.api.v1.endpoints.whatsapp.build_whatsapp_chain") as mock_builder:
        mock_builder.return_value = boom
        resp = client.post("/api/v1/whatsapp/generate-update", json=ENGLISH_PAYLOAD)

    assert resp.status_code == 500
    assert "Message generation failed" in resp.json()["detail"]
