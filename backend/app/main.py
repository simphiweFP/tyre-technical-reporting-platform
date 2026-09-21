from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import get_settings
from backend.app.modules.identity.presentation import router as auth_router
from backend.app.modules.delivery.presentation import router as delivery_router
from backend.app.modules.reports.presentation import router as reports_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
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
