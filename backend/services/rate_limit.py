"""
Lightweight in-memory rate limiting for abuse-prone endpoints.

This is intentionally process-local. It protects the single-process/dev and small
deployment case without adding infrastructure; multi-instance production should
replace it with Redis or an API gateway limit.
"""
import hashlib
import os
import threading
import time
from dataclasses import dataclass
from math import ceil

from fastapi import HTTPException, Request
from services.observability import log_event


def get_int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def client_identifier(request: Request, suffix: str = "") -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        host = forwarded_for.split(",")[0].strip()
    else:
        host = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    return f"{host}:{suffix}" if suffix else host


def safe_identifier_hash(identifier: str) -> str:
    return hashlib.sha256(str(identifier).encode("utf-8")).hexdigest()[:12]


@dataclass
class RateLimitDecision:
    allowed: bool
    count: int
    limit: int
    retry_after: int
    reset_at: float


class FixedWindowRateLimiter:
    def __init__(self, now_func=None):
        self._now = now_func or time.monotonic
        self._buckets = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = self._now()
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket or now >= bucket["reset_at"]:
                bucket = {"count": 0, "reset_at": now + window_seconds}
                self._buckets[key] = bucket

            bucket["count"] += 1
            retry_after = max(1, ceil(bucket["reset_at"] - now))
            allowed = bucket["count"] <= limit
            return RateLimitDecision(
                allowed=allowed,
                count=bucket["count"],
                limit=limit,
                retry_after=retry_after,
                reset_at=bucket["reset_at"],
            )

    def clear(self):
        with self._lock:
            self._buckets.clear()


_limiter = FixedWindowRateLimiter()


def log_rate_limit_event(scope: str, identifier: str, decision: RateLimitDecision):
    log_event(
        "rate_limit_exceeded",
        scope=scope,
        identifier_hash=safe_identifier_hash(identifier),
        count=decision.count,
        limit=decision.limit,
        retry_after=decision.retry_after,
    )


def enforce_rate_limit(
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    detail: str = "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
):
    decision = _limiter.check(f"{scope}:{identifier}", limit, window_seconds)
    if decision.allowed:
        return decision

    log_rate_limit_event(scope, identifier, decision)
    raise HTTPException(
        status_code=429,
        detail=detail,
        headers={"Retry-After": str(decision.retry_after)},
    )


def enforce_env_rate_limit(
    *,
    scope: str,
    identifier: str,
    limit_env: str,
    default_limit: int,
    window_env: str,
    default_window_seconds: int,
):
    return enforce_rate_limit(
        scope=scope,
        identifier=identifier,
        limit=get_int_env(limit_env, default_limit),
        window_seconds=get_int_env(window_env, default_window_seconds),
    )
