"""Bounded per-client-IP sliding-window limits for API requests.

The limiter runs before authentication, so every API request (including login
and unauthorized protected paths) uses the same configurable client-IP budget.
Login-specific lockout remains enforced by the auth routes.

Environment:
  RATE_LIMIT_REQUESTS_PER_MIN: requests allowed per window (default 100)
  RATE_LIMIT_WINDOW_SECONDS: sliding-window length (default 60)
  RATE_LIMIT_MAX_CLIENTS: maximum remembered client IPs (default 10000)
  DMS_TRUSTED_FRONTEND_IP: exact reverse-proxy peer allowed to supply XFF
"""

import ipaddress
import math
import os
import threading
import time
from collections import OrderedDict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

REQUEST_LIMIT = max(1, int(os.getenv("RATE_LIMIT_REQUESTS_PER_MIN", "100")))
WINDOW_SECONDS = max(1, int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")))
MAX_CLIENTS = max(1, int(os.getenv("RATE_LIMIT_MAX_CLIENTS", "10000")))
TRUSTED_FRONTEND_IP = os.getenv("DMS_TRUSTED_FRONTEND_IP", "172.31.254.3").strip()


def _client_ip(request: Request) -> str:
    """Trust X-Forwarded-For only from the exact configured proxy peer.

    A single valid IP is required; chains and malformed values fall back to the
    immediate peer. Untrusted peers cannot choose or rotate their bucket key.
    """
    peer_ip = request.client.host if request.client else "unknown"
    if peer_ip != TRUSTED_FRONTEND_IP:
        return peer_ip

    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    try:
        return str(ipaddress.ip_address(forwarded_for))
    except ValueError:
        return peer_ip


class SlidingWindowRateLimiter:
    """Per-key sliding-window counter with expiry and a hard bucket cap."""

    def __init__(self, max_buckets: int = MAX_CLIENTS) -> None:
        self._buckets: OrderedDict[str, tuple[deque[float], float]] = OrderedDict()
        self._max_buckets = max(1, max_buckets)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = WINDOW_SECONDS) -> tuple[bool, int]:
        """Return whether the request is allowed and integer seconds to retry."""
        with self._lock:
            now = time.monotonic()
            cutoff = now - window
            # Buckets are ordered by last use, so expire idle clients from the
            # front without scanning the whole client table on each request.
            while self._buckets:
                oldest_key, (_, last_seen) = next(iter(self._buckets.items()))
                if now - last_seen < window:
                    break
                self._buckets.pop(oldest_key)

            bucket = self._buckets.get(key)
            if bucket is None:
                while len(self._buckets) >= self._max_buckets:
                    self._buckets.popitem(last=False)
                timestamps: deque[float] = deque()
            else:
                timestamps, _ = bucket
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()

            allowed = len(timestamps) < limit
            retry_after = 0
            if allowed:
                timestamps.append(now)
            elif timestamps:
                retry_after = max(1, math.ceil(timestamps[0] + window - now))
            self._buckets[key] = (timestamps, now)
            self._buckets.move_to_end(key)
            return allowed, retry_after

    def is_allowed(self, key: str, limit: int, window: float = WINDOW_SECONDS) -> bool:
        """Compatibility helper returning only the decision."""
        return self.check(key, limit, window)[0]


_limiter = SlidingWindowRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply one per-client IP limit to all versioned API routes before auth."""

    API_PREFIXES = ("/api/p0", "/api/p1", "/api/p2", "/api/p3")

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in self.API_PREFIXES):
            return await call_next(request)

        ip = _client_ip(request)
        allowed, retry_after = _limiter.check(ip, REQUEST_LIMIT)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again shortly."},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
