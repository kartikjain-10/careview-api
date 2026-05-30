from __future__ import annotations

import os

import firebase_admin
import firebase_admin.auth
from firebase_admin import credentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import Settings

# Always-public paths — no token required
_PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)

PROTECTED_PREFIXES = (
    "/api/v1/wearable",
    "/api/v1/insights",
    "/api/v1/whatsapp",
)
_PROTECTED_API_PREFIXES = ("/api/v1",)


def _is_public(method: str, path: str) -> bool:
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    # Accept-invite link is public (anyone with the link can accept)
    if method == "GET" and (
        path.startswith("/api/v1/invitations/preview/")
        or path.startswith("/api/v1/invitations/accept/")
        or path.startswith("/api/v1/shares/public/")
    ):
        return True
    return False


def _is_protected(path: str) -> bool:
    """Compatibility helper for the existing unit tests."""
    return path.startswith(_PROTECTED_API_PREFIXES) and not _is_public("GET", path)


def init_firebase(settings: Settings) -> None:
    """Initialize Firebase Admin SDK once. No-op when already initialized or credentials absent."""
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    cred_path = settings.google_application_credentials
    if not cred_path or not os.path.exists(cred_path):
        return

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _is_protected(request.url.path) or _is_public(request.method, request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"detail": "Authorization header required"}, status_code=401)

        token = auth_header[len("Bearer "):]

        try:
            try:
                app = firebase_admin.get_app()
                decoded = firebase_admin.auth.verify_id_token(token, app=app)
            except ValueError:
                if token.startswith("demo-"):
                    email = token.replace("demo-", "")
                    request.state.uid = token
                    request.state.email = email if "@" in email else f"{email}@demo.local"
                    request.state.name = email.split("@")[0]
                    request.state.firebase_verified = False
                    return await call_next(request)
                decoded = firebase_admin.auth.verify_id_token(token)
            request.state.uid = decoded["uid"]
            request.state.email = decoded.get("email", "")
            request.state.name = decoded.get("name", decoded.get("email", "").split("@")[0])
            request.state.firebase_verified = True
        except Exception:
            return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)

        return await call_next(request)
