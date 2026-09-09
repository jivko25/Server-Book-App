from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import RULIT_RATE_LIMIT_PER_MINUTE


class RulitRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limit for /api/rulit routes."""

    def __init__(self, app, *, limit_per_minute: int = RULIT_RATE_LIMIT_PER_MINUTE) -> None:
        super().__init__(app)
        self.limit_per_minute = limit_per_minute
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client is None:
            return "unknown"
        return request.client.host

    def _is_allowed(self, client_ip: str) -> bool:
        now = time.monotonic()
        window_start = now - 60.0
        bucket = self._requests[client_ip]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self.limit_per_minute:
            return False
        bucket.append(now)
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith("/api/rulit"):
            return await call_next(request)

        client_ip = self._client_ip(request)
        if not self._is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
            )
        return await call_next(request)
