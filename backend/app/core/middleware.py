import json
import logging
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.config import get_settings

logger = logging.getLogger("api.requests")


class RequestProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.requests: dict[str, deque[datetime]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        client = request.client.host if request.client else "unknown"
        now = datetime.now(UTC)
        window = self.requests[client]
        while window and window[0] < now - timedelta(minutes=1):
            window.popleft()
        settings = get_settings()
        limit = (
            10_000
            if settings.environment == "test"
            else 30
            if request.url.path.endswith("/auth/login")
            else settings.request_rate_limit_per_minute
        )
        if len(window) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60", "X-Request-ID": request_id},
            )
        window.append(now)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                json.dumps(
                    {
                        "event": "http_request_failed",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "client": client,
                    }
                )
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An unexpected server error occurred",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )
        content_security_policy = "default-src 'none'; frame-ancestors 'none'"
        if request.url.path in {"/docs", "/redoc"}:
            content_security_policy = (
                "default-src 'none'; "
                "script-src https://cdn.jsdelivr.net 'unsafe-inline'; "
                "style-src https://cdn.jsdelivr.net 'unsafe-inline'; "
                "img-src https://fastapi.tiangolo.com data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )

        response.headers.update(
            {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Permissions-Policy": "camera=(self)",
                "Content-Security-Policy": content_security_policy,
            }
        )
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "client": client,
                }
            )
        )
        return response
