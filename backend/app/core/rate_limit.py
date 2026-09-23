"""Small in-process rate limiter for the single-instance V1 deployment."""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class InMemoryRateLimiter:
    """Count requests per client for a bounded rolling time window."""

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit <= 0 or window_seconds <= 0:
            return False

        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._requests[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        """Clear state for deterministic tests and controlled local restarts."""
        with self._lock:
            self._requests.clear()


rate_limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply the configured limit to API requests in this process."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        is_api_request = path == settings.API_PREFIX or path.startswith(f"{settings.API_PREFIX}/")
        # CORS preflight is a browser negotiation, not a business request.
        if request.method == "OPTIONS" or not settings.RATE_LIMIT_ENABLED or not is_api_request:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        allowed = rate_limiter.allow(
            client_host,
            settings.RATE_LIMIT_REQUESTS,
            settings.RATE_LIMIT_WINDOW_SECONDS,
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "请求过于频繁，请稍后重试",
                    }
                },
                headers={"Retry-After": str(settings.RATE_LIMIT_WINDOW_SECONDS)},
            )

        return await call_next(request)
