from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from backend.app.core.config import get_settings
from backend.app.core.database import engine
from backend.app.core.middleware import RequestProtectionMiddleware
from backend.app.core.migrations import run_database_migrations
from backend.app.modules.administration.presentation import (
    router as administration_router,
)
from backend.app.modules.delivery.presentation import router as delivery_router
from backend.app.modules.identity.presentation import router as auth_router
from backend.app.modules.reports.presentation import router as reports_router
from backend.app.modules.reports.storage import ReportFileStorage

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_for_startup()
    run_database_migrations()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret,
    same_site="lax",
    https_only=settings.environment == "production",
)
app.add_middleware(RequestProtectionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(delivery_router, prefix="/api/v1")
app.include_router(administration_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def swagger_redirect():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "healthy", "environment": settings.environment}


@app.get("/ready", tags=["Operations"])
def readiness():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    ReportFileStorage().ensure_ready()
    return {"status": "ready"}
