from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from backend.app.core.config import get_settings
from backend.app.core.database import engine
from backend.app.core.middleware import RequestProtectionMiddleware
from backend.app.modules.delivery.presentation import router as delivery_router
from backend.app.modules.identity.presentation import router as auth_router
from backend.app.modules.reports.presentation import router as reports_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
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


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "healthy", "environment": settings.environment}


@app.get("/ready", tags=["Operations"])
def readiness():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready"}
