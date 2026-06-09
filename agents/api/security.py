"""API authentication + rate limiting middleware.

Both protections are opt-in via environment so the localhost-native deployment
keeps working with zero configuration:

- Auth: set ``KIA_API_KEY`` and every request must carry it as
  ``Authorization: Bearer <key>`` or ``X-API-Key: <key>``.
- Rate limiting: ``RATE_LIMIT_PER_MINUTE`` (default 120) applies a per-client
  sliding window; set to 0 to disable.

``/health`` and ``/metrics`` stay open: the watchdog and Prometheus must be
able to probe a misconfigured instance, and neither endpoint exposes data.
"""

import secrets
import time
from collections import deque
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from brain_core.config import settings

# Liveness + scrape endpoints stay reachable without credentials.
EXEMPT_PATHS = {"/health", "/metrics"}

_WINDOW_SECONDS = 60.0


class SlidingWindowLimiter:
    """Per-client sliding-window rate limiter (in-process, no dependencies).

    Suitable for the single-instance deployments KIA runs in (native Windows
    or one container). A multi-replica deployment would need a shared store.
    """

    def __init__(self, limit: int, window: float = _WINDOW_SECONDS) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = {}

    def allow(self, client: str) -> tuple[bool, float]:
        """Record a hit; return (allowed, seconds-until-a-slot-frees)."""
        now = time.monotonic()
        hits = self._hits.setdefault(client, deque())
        cutoff = now - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            return False, max(0.0, hits[0] + self.window - now)
        hits.append(now)
        # Opportunistic cleanup so idle clients don't accumulate forever.
        if len(self._hits) > 10_000:
            self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > cutoff}
        return True, 0.0


_limiter: SlidingWindowLimiter | None = None


def _get_limiter() -> SlidingWindowLimiter | None:
    """Lazily build the limiter from settings (0 disables)."""
    global _limiter
    limit = settings.rate_limit_per_minute
    if limit <= 0:
        return None
    if _limiter is None or _limiter.limit != limit:
        _limiter = SlidingWindowLimiter(limit)
    return _limiter


def _client_id(request: Request) -> str:
    """Identify the caller: first X-Forwarded-For hop (behind the tunnel) or peer IP."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _presented_key(request: Request) -> str:
    """Extract the API key from Authorization: Bearer or X-API-Key."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key", "")


async def security_middleware(request: Request, call_next: Any) -> Any:
    """Enforce API key auth (when configured) and per-client rate limits."""
    path = request.url.path
    if request.method == "OPTIONS" or path in EXEMPT_PATHS:
        return await call_next(request)

    expected = settings.kia_api_key
    if expected:
        presented = _presented_key(request)
        if not presented or not secrets.compare_digest(presented, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
                headers={"WWW-Authenticate": "Bearer"},
            )

    limiter = _get_limiter()
    if limiter is not None:
        allowed, retry_after = limiter.allow(_client_id(request))
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(max(1, int(retry_after + 0.5)))},
            )

    return await call_next(request)
