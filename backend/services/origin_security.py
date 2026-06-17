import os
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from services.observability import log_event


DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_origin(value: str | None) -> str | None:
    if not value:
        return None
    origin = value.strip().rstrip("/")
    if origin == "*":
        return origin

    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return None

    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if not host:
        return None

    port = f":{parsed.port}" if parsed.port else ""
    return f"{scheme}://{host}{port}"


def parse_origin_list(value: str | None, default: list[str] | None = None) -> list[str]:
    raw_origins = default if not value else [origin.strip() for origin in value.split(",") if origin.strip()]
    normalized = []
    for origin in raw_origins or []:
        normalized_origin = normalize_origin(origin)
        if normalized_origin and normalized_origin not in normalized:
            normalized.append(normalized_origin)
    return normalized


def cors_allowed_origins() -> list[str]:
    return parse_origin_list(os.getenv("CORS_ALLOW_ORIGINS"), DEFAULT_CORS_ORIGINS)


def csrf_trusted_origins() -> set[str]:
    trusted = set(origin for origin in cors_allowed_origins() if origin != "*")
    trusted.update(
        origin
        for origin in parse_origin_list(os.getenv("CSRF_TRUSTED_ORIGINS"))
        if origin != "*"
    )
    return trusted


def request_origin(request: Request) -> str | None:
    origin = normalize_origin(request.headers.get("origin"))
    if origin:
        return origin

    referer = request.headers.get("referer")
    if referer:
        return normalize_origin(referer)
    return None


def request_self_origin(request: Request) -> str | None:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    scheme = (forwarded_proto.split(",")[0].strip() if forwarded_proto else request.url.scheme).lower()
    host = (forwarded_host.split(",")[0].strip() if forwarded_host else request.headers.get("host", "")).lower()
    if not scheme or not host:
        return None
    return normalize_origin(f"{scheme}://{host}")


def is_trusted_origin(origin: str | None, request: Request | None = None) -> bool:
    normalized = normalize_origin(origin)
    if not normalized or normalized == "*":
        return False
    if normalized in csrf_trusted_origins():
        return True
    if request:
        return normalized == request_self_origin(request)
    return False


def enforce_trusted_origin(request: Request):
    origin = request_origin(request)
    if not origin:
        if get_bool_env("CSRF_REQUIRE_ORIGIN", True):
            log_event(
                "csrf_origin_missing",
                level="warning",
                method=request.method,
                path=request.url.path,
            )
            raise HTTPException(status_code=403, detail="요청 출처를 확인할 수 없습니다.")
        return

    if not is_trusted_origin(origin, request):
        log_event(
            "csrf_origin_rejected",
            level="warning",
            method=request.method,
            path=request.url.path,
            origin=origin,
        )
        raise HTTPException(status_code=403, detail="허용되지 않은 요청 출처입니다.")
