"""Unit tests for insight_chain — no real LLM or DB calls."""
import pytest
from unittest.mock import MagicMock, patch
from app.ai.chains.insight_chain import build_insight_chain, SYSTEM_PROMPT


def _make_mock_chain(return_value="Wellness looks good."):
    """
    Build a MagicMock that survives two | operators:
      _PROMPT | llm   →  mock_chain
      mock_chain | StrOutputParser()  →  mock_chain  (via __or__ returning self)
    So mock_chain.invoke(...) is always what gets called.
    """
    mock_chain = MagicMock()
    mock_chain.invoke = MagicMock(return_value=return_value)
    # Make further piping return itself so the StrOutputParser pipe is a no-op
    mock_chain.__or__ = MagicMock(return_value=mock_chain)
    return mock_chain


def _patched_chain(return_value="Wellness looks good."):
    mock_chain = _make_mock_chain(return_value)
    patcher = patch("app.ai.chains.insight_chain._PROMPT")
    mock_prompt = patcher.start()
    mock_prompt.__or__ = MagicMock(return_value=mock_chain)
    return patcher, mock_chain


def test_should_return_string_when_chain_invoked():
    llm = MagicMock()
    patcher, mock_chain = _patched_chain("You seem to be doing well.")
    try:
        chain = build_insight_chain(llm, vectorstore=None)
        result = chain("parent_1", "How am I doing?", "6000 steps, 7h sleep")
        assert isinstance(result, str)
        assert result == "You seem to be doing well."
    finally:
        patcher.stop()


def test_should_not_contain_diagnosis_language():
    """System prompt must not contain diagnostic language."""
    forbidden = ["diagnos", "emergency", "critical", "treatment", "medication"]
    for word in forbidden:
        assert word not in SYSTEM_PROMPT.lower(), f"System prompt contains forbidden word: {word}"


def test_should_handle_none_vectorstore():
    """Chain should be callable when no vectorstore is provided."""
    llm = MagicMock()
    chain = build_insight_chain(llm, vectorstore=None)
    assert callable(chain)


def test_should_retrieve_context_when_vectorstore_provided():
    """Chain should call vectorstore retriever when vectorstore is present."""
    llm = MagicMock()
    mock_vs = MagicMock()
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = []
    mock_vs.as_retriever.return_value = mock_retriever

    patcher, _ = _patched_chain()
    try:
        chain = build_insight_chain(llm, vectorstore=mock_vs)
        chain("parent_1", "How are my steps?")
    finally:
        patcher.stop()

    mock_vs.as_retriever.assert_called_once()


def test_should_include_relevant_chunks_in_health_records_section():
    """When vectorstore returns docs, chunks should appear in health_records_section."""
    from langchain_core.documents import Document

    llm = MagicMock()
    mock_vs = MagicMock()
    mock_retriever = MagicMock()
    doc = Document(page_content="Cholesterol: 180 mg/dL", metadata={"parent_id": "p1"})
    mock_retriever.invoke.return_value = [doc]
    mock_vs.as_retriever.return_value = mock_retriever

    captured = {}
    mock_chain = _make_mock_chain()

    def capture_invoke(kwargs):
        captured.update(kwargs)
        return "Good."

    mock_chain.invoke = MagicMock(side_effect=capture_invoke)

    patcher = patch("app.ai.chains.insight_chain._PROMPT")
    mock_prompt = patcher.start()
    mock_prompt.__or__ = MagicMock(return_value=mock_chain)

    try:
        chain = build_insight_chain(llm, vectorstore=mock_vs)
        chain("p1", "What do my labs say?")
    finally:
        patcher.stop()

    assert "health_records_section" in captured
    assert "Cholesterol" in captured["health_records_section"]


def test_should_handle_vectorstore_exception_gracefully():
    """If vectorstore raises, chain should still run with empty health_records_section."""
    llm = MagicMock()
    mock_vs = MagicMock()
    mock_vs.as_retriever.side_effect = RuntimeError("DB error")

    patcher, mock_chain = _patched_chain("Looks fine.")
    try:
        chain = build_insight_chain(llm, vectorstore=mock_vs)
        result = chain("p1", "How am I?")
        assert isinstance(result, str)
        assert result == "Looks fine."
    finally:
        patcher.stop()


def test_should_pass_wearable_summary_to_prompt():
    """Wearable summary should be present in the prompt invocation kwargs."""
    llm = MagicMock()
    captured = {}

    mock_chain = _make_mock_chain()

    def capture(kwargs):
        captured.update(kwargs)
        return "Good."

    mock_chain.invoke = MagicMock(side_effect=capture)

    patcher = patch("app.ai.chains.insight_chain._PROMPT")
    mock_prompt = patcher.start()
    mock_prompt.__or__ = MagicMock(return_value=mock_chain)

    try:
        chain = build_insight_chain(llm, vectorstore=None)
        chain("p1", "How are my steps?", wearable_summary="8000 steps, 6.5h sleep")
    finally:
        patcher.stop()

    assert captured.get("wearable_summary") == "8000 steps, 6.5h sleep"


def test_should_use_trend_language_in_system_prompt():
    trend_words = ["seems", "appears", "might", "trend"]
    found = any(w in SYSTEM_PROMPT.lower() for w in trend_words)
    assert found, "System prompt should include trend-based language guidance"


def test_should_enforce_no_gps_tracking_constraint():
    forbidden = ["gps", "location tracking", "track location"]
    for word in forbidden:
        assert word not in SYSTEM_PROMPT.lower(), f"System prompt mentions: {word}"


def test_should_use_fallback_when_no_wearable_summary():
    """Empty wearable_summary should be replaced with fallback text, not blank."""
    llm = MagicMock()
    captured = {}

    mock_chain = _make_mock_chain()

    def capture(kwargs):
        captured.update(kwargs)
        return "All good."

    mock_chain.invoke = MagicMock(side_effect=capture)

    patcher = patch("app.ai.chains.insight_chain._PROMPT")
    mock_prompt = patcher.start()
    mock_prompt.__or__ = MagicMock(return_value=mock_chain)

    try:
        chain = build_insight_chain(llm, vectorstore=None)
        chain("p1", "How am I?", wearable_summary="")
    finally:
        patcher.stop()

    assert captured["wearable_summary"] != ""
    assert "No wearable data" in captured["wearable_summary"]
