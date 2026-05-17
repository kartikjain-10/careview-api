"""
Root conftest — makes FirebaseAuthMiddleware transparent for all tests
except those marked @pytest.mark.real_firebase_auth.

Two patches applied together:
  1. _is_protected → always returns False  (middleware never blocks)
  2. verify_id_token → returns a fake user  (safe fallback if somehow reached)

Auth-specific tests opt out via the marker and control both patches themselves.
"""
import pytest
from unittest.mock import patch

MOCK_USER = {"uid": "test_uid", "email": "test@example.com", "name": "Test User"}


@pytest.fixture(autouse=True)
def mock_firebase_auth(request):
    if "real_firebase_auth" in request.keywords:
        yield
        return

    with patch("app.core.middleware.auth._is_protected", return_value=False), \
         patch("firebase_admin.auth.verify_id_token", return_value=MOCK_USER):
        yield
