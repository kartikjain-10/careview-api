from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.onboarding import router as onboarding_router
from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.family import router as family_router
from app.api.v1.endpoints.invitations import router as invitations_router
from app.api.v1.endpoints.medicines import router as medicines_router
from app.api.v1.endpoints.habits import router as habits_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.insights import router as insights_router
from app.api.v1.endpoints.wearable import router as wearable_router
from app.api.v1.endpoints.nori import router as nori_router
from app.api.v1.endpoints.whatsapp import router as whatsapp_router
from app.api.v1.endpoints.shares import router as shares_router
from app.core.config import settings
from app.core.middleware.auth import FirebaseAuthMiddleware, init_firebase
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(settings)
    init_firebase(settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="CareView API",
        description="Privacy-first AI-powered family wellness monitoring platform",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # De-duplicate origins and enumerate methods/headers explicitly.
    # Wildcard methods/headers with allow_credentials=True is blocked by browsers (CORS spec).
    origins = list({settings.app_base_url, "http://localhost:3000"})
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    app.add_middleware(FirebaseAuthMiddleware)

    prefix = "/api/v1"
    app.include_router(health_router,      prefix=prefix)
    app.include_router(auth_router,        prefix=prefix)
    app.include_router(onboarding_router,  prefix=prefix)
    app.include_router(admin_router,       prefix=prefix)
    app.include_router(family_router,      prefix=prefix)
    app.include_router(invitations_router, prefix=prefix)
    app.include_router(medicines_router,   prefix=prefix)
    app.include_router(habits_router,      prefix=prefix)
    app.include_router(insights_router,    prefix=prefix)
    app.include_router(wearable_router,    prefix=prefix)
    app.include_router(documents_router,   prefix=prefix)
    app.include_router(nori_router,        prefix=prefix)
    app.include_router(whatsapp_router,    prefix=prefix)
    app.include_router(shares_router,      prefix=prefix)

    return app


app = create_app()
