"""Unit tests for whatsapp_chain — link builder and prompt constraint checks."""
import unicodedata
from unittest.mock import MagicMock, patch

import pytest

from app.ai.chains.whatsapp_chain import (
    ENGLISH_SYSTEM_PROMPT,
    HINDI_SYSTEM_PROMPT,
    build_whatsapp_chain,
    build_whatsapp_link,
)

# ── build_whatsapp_link ───────────────────────────────────────────────────────

def test_should_strip_plus_from_phone_number():
    link = build_whatsapp_link("+919876543210", "Hello")
    assert "919876543210" in link
    assert "+" not in link


def test_should_start_with_wa_me():
    link = build_whatsapp_link("+919876543210", "Hello Maa")
    assert link.startswith("https://wa.me/")


def test_should_url_encode_message():
    link = build_whatsapp_link("+91123", "नमस्ते माँ")
    # Devanagari characters must be percent-encoded
    assert "नमस्ते" not in link
    assert "%" in link


def test_should_url_encode_spaces():
    link = build_whatsapp_link("+91123", "Hello Maa how are you")
    assert " " not in link


def test_should_handle_phone_without_plus():
    link = build_whatsapp_link("919876543210", "Hi")
    assert link.startswith("https://wa.me/919876543210")


def test_should_include_text_query_param():
    link = build_whatsapp_link("+91123", "Hi")
    assert "?text=" in link


# ── System prompt constraint checks ──────────────────────────────────────────

FORBIDDEN_IN_ANY_PROMPT = [
    "diagnos", "emergency", "critical", "serious condition",
]


def test_should_not_contain_forbidden_words_in_hindi_prompt():
    for word in FORBIDDEN_IN_ANY_PROMPT:
        assert word not in HINDI_SYSTEM_PROMPT.lower(), (
            f"Hindi system prompt contains forbidden word: {word}"
        )


def test_should_not_contain_forbidden_words_in_english_prompt():
    for word in FORBIDDEN_IN_ANY_PROMPT:
        assert word not in ENGLISH_SYSTEM_PROMPT.lower(), (
            f"English system prompt contains forbidden word: {word}"
        )


def test_hindi_prompt_contains_devanagari_instructions():
    """Hindi prompt must contain actual Devanagari script guidance."""
    has_devanagari = any(
        unicodedata.category(ch).startswith("L") and "ऀ" <= ch <= "ॿ"
        for ch in HINDI_SYSTEM_PROMPT
    )
    assert has_devanagari, "Hindi system prompt should contain Devanagari script"


def test_english_prompt_does_not_contain_devanagari():
    """English system prompt must not contain Devanagari characters."""
    has_devanagari = any("ऀ" <= ch <= "ॿ" for ch in ENGLISH_SYSTEM_PROMPT)
    assert not has_devanagari, "English system prompt must not contain Devanagari script"


def test_hindi_prompt_instructs_warm_tone():
    warm_indicators = ["warm", "loving", "माँ", "caring"]
    found = any(w in HINDI_SYSTEM_PROMPT for w in warm_indicators)
    assert found, "Hindi prompt should instruct a warm, family-member tone"


def test_english_prompt_instructs_warm_tone():
    warm_indicators = ["warm", "loving", "caring", "affectionate"]
    found = any(w in ENGLISH_SYSTEM_PROMPT.lower() for w in warm_indicators)
    assert found, "English prompt should instruct a warm, family-member tone"


# ── build_whatsapp_chain — chain selection ────────────────────────────────────

def _make_mock_chain(return_value: str):
    """Chain mock that survives two | operators (same pattern as insight chain tests)."""
    mock_chain = MagicMock()
    mock_chain.invoke = MagicMock(return_value=return_value)
    mock_chain.__or__ = MagicMock(return_value=mock_chain)
    return mock_chain


def test_should_use_hindi_chain_for_hindi_language():
    llm = MagicMock()
    hindi_mock = _make_mock_chain("नमस्ते माँ 🙏")

    with patch("app.ai.chains.whatsapp_chain._HINDI_PROMPT") as mock_hindi_prompt, \
         patch("app.ai.chains.whatsapp_chain._ENGLISH_PROMPT"):
        mock_hindi_prompt.__or__ = MagicMock(return_value=hindi_mock)
        chain = build_whatsapp_chain(llm)
        result = chain(language="hindi", wearable_summary="6000 steps")

    hindi_mock.invoke.assert_called_once()
    assert result == "नमस्ते माँ 🙏"


def test_should_use_english_chain_for_english_language():
    llm = MagicMock()
    english_mock = _make_mock_chain("Hi Maa 🙏 You're doing great!")

    with patch("app.ai.chains.whatsapp_chain._HINDI_PROMPT"), \
         patch("app.ai.chains.whatsapp_chain._ENGLISH_PROMPT") as mock_en_prompt:
        mock_en_prompt.__or__ = MagicMock(return_value=english_mock)
        chain = build_whatsapp_chain(llm)
        result = chain(language="english", wearable_summary="8000 steps")

    english_mock.invoke.assert_called_once()
    assert result == "Hi Maa 🙏 You're doing great!"


def test_should_pass_wearable_summary_to_chain():
    llm = MagicMock()
    captured = {}
    mock_chain = _make_mock_chain("Good.")

    def capture(kwargs):
        captured.update(kwargs)
        return "Good."

    mock_chain.invoke = MagicMock(side_effect=capture)

    with patch("app.ai.chains.whatsapp_chain._ENGLISH_PROMPT") as mock_en_prompt, \
         patch("app.ai.chains.whatsapp_chain._HINDI_PROMPT"):
        mock_en_prompt.__or__ = MagicMock(return_value=mock_chain)
        chain = build_whatsapp_chain(llm)
        chain(language="english", wearable_summary="7500 steps, 8h sleep")

    assert captured.get("wearable_summary") == "7500 steps, 8h sleep"
