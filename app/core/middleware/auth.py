from __future__ import annotations

import os

import firebase_admin
import firebase_admin.auth
from firebase_admin import credentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import Settings

# Paths whose prefix requires a valid Firebase Bearer token
PROTECTED_PREFIXES = (
    "/api/v1/wearable",
    "/api/v1/whatsapp",
)

# Paths that are always public (checked before prefix matching)
_PUBLIC_PREFIXES = ("/api/v1/health", "/docs", "/redoc", "/openapi.json")


def _is_protected(path: str) -> bool:
    for public in _PUBLIC_PREFIXES:
        if path.startswith(public):
            return False
    return any(path.startswith(p) for p in PROTECTED_PREFIXES)


def init_firebase(settings: Settings) -> None:
    """Initialize Firebase Admin SDK once. No-op when already initialized or credentials absent."""
    try:
        firebase_admin.get_app()
        return  # Already initialized
    except ValueError:
        pass

    cred_path = settings.google_application_credentials
    if not cred_path or not os.path.exists(cred_path):
        # TODO: Set GOOGLE_APPLICATION_CREDENTIALS to a valid service-account.json for production
        return

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _is_protected(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Missing or invalid Authorization header"},
                status_code=401,
            )

        token = auth_header[len("Bearer "):]
        try:
            decoded = firebase_admin.auth.verify_id_token(token)
            request.state.user = decoded
        except Exception:
            return JSONResponse(
                {"detail": "Invalid or expired token"},
                status_code=401,
            )

        return await call_next(request)
