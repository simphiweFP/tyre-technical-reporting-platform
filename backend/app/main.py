import asyncio
from contextlib import asynccontextmanager, suppress

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
from backend.app.modules.delivery.bounce_monitor import process_microsoft_bounces
from backend.app.modules.delivery.presentation import router as delivery_router
from backend.app.modules.identity.presentation import router as auth_router
from backend.app.modules.reports.customer_lookup import refresh_customer_cache_if_due
from backend.app.modules.reports.presentation import router as reports_router

settings = get_settings()


async def customer_cache_scheduler() -> None:
    while True:
        try:
            await refresh_customer_cache_if_due()
        except Exception:
            # SAP/customer sync must never prevent the reporting API from running.
            pass
        await asyncio.sleep(60 * 60)


async def bounce_monitor_scheduler() -> None:
    while True:
        try:
            await process_microsoft_bounces(settings)
        except Exception:
            # Mailbox monitoring must never prevent the reporting API from running.
            pass
        await asyncio.sleep(max(settings.bounce_monitor_poll_seconds, 30))


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_for_startup()
    if settings.environment != "test":
        run_database_migrations()
    customer_sync_task = asyncio.create_task(customer_cache_scheduler())
    bounce_monitor_task = asyncio.create_task(bounce_monitor_scheduler())
    try:
        yield
    finally:
        customer_sync_task.cancel()
        bounce_monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await customer_sync_task
        with suppress(asyncio.CancelledError):
            await bounce_monitor_task


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
    return {"status": "ready"}
