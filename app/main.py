from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.insights import router as insights_router
from app.api.v1.endpoints.wearable import router as wearable_router
from app.api.v1.endpoints.whatsapp import router as whatsapp_router
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
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(FirebaseAuthMiddleware)

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(insights_router, prefix="/api/v1")
    app.include_router(wearable_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(whatsapp_router, prefix="/api/v1")

    return app


app = create_app()
