"""Unit tests for auth middleware helpers — no I/O."""
import pytest
from app.core.middleware.auth import _is_protected, PROTECTED_PREFIXES


# ── _is_protected path classification ────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/v1/wearable/sync",
    "/api/v1/wearable/parent_1",
    "/api/v1/insights",
    "/api/v1/whatsapp/generate-update",
])
def test_should_mark_protected_paths_as_protected(path):
    assert _is_protected(path) is True


@pytest.mark.parametrize("path", [
    "/api/v1/health",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
])
def test_should_mark_public_paths_as_not_protected(path):
    assert _is_protected(path) is False


def test_documents_endpoint_is_not_in_protected_prefixes():
    """Documents is not in the protected list per spec."""
    assert not any("/api/v1/documents".startswith(p) for p in PROTECTED_PREFIXES)


def test_health_endpoint_is_not_protected():
    assert _is_protected("/api/v1/health") is False


def test_wearable_sub_paths_are_protected():
    assert _is_protected("/api/v1/wearable/any/sub/path") is True


def test_whatsapp_sub_paths_are_protected():
    assert _is_protected("/api/v1/whatsapp/any-action") is True
