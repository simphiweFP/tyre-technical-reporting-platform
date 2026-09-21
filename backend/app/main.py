from fastapi import FastAPI

from backend.app.core.config import get_settings
from backend.app.modules.identity.presentation import router as auth_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "healthy", "environment": settings.environment}

