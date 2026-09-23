"""API Security — API key authentication and token-bucket rate limiting.

NOTE: The demo key 'dev-demo-key' fallback is permitted ONLY when ENV=dev
(or development/local/test). In production (ENV=production), API_KEYS must
be configured in the environment, and any request missing a valid key is
strictly rejected with a 401 Unauthorized response.
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("storage_advisor.security")

# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------

API_KEY_HEADER = "X-API-Key"
DEV_DEMO_KEY = "dev-demo-key"
RATE_LIMIT_CAPACITY = 60.0  # 60 tokens
RATE_LIMIT_REFILL_RATE = 1.0  # 60 req / 60 sec = 1 token/sec

EXEMPT_PATHS = {
    "/health",
    "/api/v1/health",
    "/api/v1/config",
    "/metrics",
}


def get_environment() -> str:
    """Return the normalized environment name."""
    return os.getenv("ENV", os.getenv("ENVIRONMENT", "dev")).lower()


def is_dev_mode() -> bool:
    """Return True if running in development or testing mode.

    The demo key fallback is permitted ONLY when this returns True.
    """
    return get_environment() in ("dev", "development", "local", "test")


def get_configured_api_keys() -> set[str]:
    """Parse comma-separated API keys from the API_KEYS environment variable."""
    raw = os.getenv("API_KEYS", "")
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    return keys


def get_valid_api_keys() -> set[str]:
    """Return set of valid API keys.

    In development (ENV=dev), the demo key 'dev-demo-key' is included automatically.
    In production, ONLY explicitly configured keys from API_KEYS are accepted.
    """
    keys = get_configured_api_keys()
    if is_dev_mode():
        keys.add(DEV_DEMO_KEY)
    return keys


def get_client_api_key() -> str:
    """Return the API key to expose to the frontend.

    In dev mode, returns the first configured key or the demo key fallback.
    In production, returns the first configured key, or empty string.
    """
    configured = list(get_configured_api_keys())
    if configured:
        return configured[0]
    if is_dev_mode():
        return DEV_DEMO_KEY
    return ""


# ---------------------------------------------------------------------------
# Token Bucket Rate Limiter
# ---------------------------------------------------------------------------


class TokenBucket:
    """Thread-safe token bucket rate limiter for a single entity."""

    def __init__(
        self,
        capacity: float = RATE_LIMIT_CAPACITY,
        refill_rate: float = RATE_LIMIT_REFILL_RATE,
    ) -> None:
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> tuple[bool, int]:
        """Attempt to consume tokens.

        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= amount:
                self.tokens -= amount
                return True, 0

            deficit = amount - self.tokens
            retry_after = max(1, math.ceil(deficit / self.refill_rate))
            return False, retry_after

    def reset(self) -> None:
        """Reset the bucket back to full capacity."""
        with self._lock:
            self.tokens = self.capacity
            self.last_refill = time.monotonic()


class RateLimiterRegistry:
    """Registry maintaining per-key TokenBucket instances."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Check rate limit for a specific key."""
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket()
            bucket = self._buckets[key]

        return bucket.consume(1.0)

    def reset(self) -> None:
        """Clear all rate limit buckets."""
        with self._lock:
            self._buckets.clear()


_rate_limiter = RateLimiterRegistry()


def get_rate_limiter() -> RateLimiterRegistry:
    """Return the global rate limiter registry."""
    return _rate_limiter


# ---------------------------------------------------------------------------
# Middleware Inspection Function
# ---------------------------------------------------------------------------


async def authenticate_and_rate_limit(request: Request) -> JSONResponse | None:
    """Validate API key and apply token-bucket rate limiting to /api/v1/* routes.

    Returns:
        JSONResponse with 401/429 if rejected, or None to proceed.
    """
    path = request.url.path

    # Only protect /api/v1/* routes, excluding health and public config
    if not path.startswith("/api/v1/"):
        return None

    if path in EXEMPT_PATHS or path.startswith("/health") or path.startswith("/api/v1/health"):
        return None

    if path == "/api/v1/config":
        return None

    # Extract API key header (case-insensitive)
    api_key = request.headers.get(API_KEY_HEADER)

    # In dev mode, missing key falls back to DEV_DEMO_KEY for convenience
    if not api_key and is_dev_mode():
        api_key = DEV_DEMO_KEY

    valid_keys = get_valid_api_keys()

    if not api_key or api_key not in valid_keys:
        logger.warning(
            "Authentication failed for path %s from %s (key provided: %s)",
            path,
            request.client.host if request.client else "unknown",
            bool(api_key),
        )
        return JSONResponse(
            status_code=401,
            content={
                "error": "Unauthorized",
                "detail": f"Invalid or missing {API_KEY_HEADER} header.",
            },
        )

    # Apply token-bucket rate limit (60 req/min/key)
    allowed, retry_after = _rate_limiter.check(api_key)
    if not allowed:
        logger.warning(
            "Rate limit exceeded for key %s... on path %s. Retry after %d s",
            api_key[:6] if len(api_key) >= 6 else api_key,
            path,
            retry_after,
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too Many Requests",
                "detail": "Rate limit exceeded (60 requests per minute per key). Please retry later.",
            },
            headers={"Retry-After": str(retry_after)},
        )

    # Attach verified api_key to request state
    request.state.api_key = api_key
    return None
