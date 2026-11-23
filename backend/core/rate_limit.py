"""A small sliding-window rate limiter for the unauthenticated auth endpoints.

State is kept per process, which is enough to blunt password guessing against a
single server. With several workers or instances, enforce limits at the gateway
(nginx, Cloudflare, API gateway) or swap this for a Redis-backed limiter.

Behind a reverse proxy, run uvicorn with --proxy-headers and
--forwarded-allow-ips so request.client.host is the real client address.
"""

import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

from config import get_settings


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int | None:
        """Record a hit. Returns None if allowed, else seconds until a slot frees up."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(self.window - (now - hits[0])))
            hits.append(now)
            if len(self._hits) > 10_000:
                self._prune(now)
            return None

    def _prune(self, now: float) -> None:
        stale = [k for k, h in self._hits.items() if not h or now - h[-1] >= self.window]
        for key in stale:
            del self._hits[key]


_limiters: dict[str, SlidingWindowLimiter] = {}


def rate_limit(scope: str):
    """FastAPI dependency factory: limits requests per client IP for `scope`."""

    async def dependency(request: Request) -> None:
        limit = get_settings().rate_limit_auth_per_minute
        if limit <= 0:
            return
        limiter = _limiters.get(scope)
        if limiter is None or limiter.limit != limit:
            limiter = _limiters[scope] = SlidingWindowLimiter(limit)
        client_ip = request.client.host if request.client else "unknown"
        retry_after = limiter.retry_after(f"{scope}:{client_ip}")
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
