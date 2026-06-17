import contextvars
import datetime
import hashlib
import json
import os
import uuid


_request_id = contextvars.ContextVar("request_id", default=None)

SENSITIVE_LOG_FIELD_HASHES = {
    "user_id": "user_hash",
    "email": "email_hash",
    "journal_id": "journal_hash",
    "intention_id": "intention_id_hash",
    "card_id": "card_hash",
    "token": "token_hash",
    "access_token": "access_token_hash",
    "refresh_token": "refresh_token_hash",
    "jti": "jti_hash",
}


def new_request_id() -> str:
    return uuid.uuid4().hex


def normalize_request_id(value: str | None) -> str:
    request_id = (value or "").strip()
    if not request_id or len(request_id) > 128:
        return new_request_id()
    return "".join(ch for ch in request_id if ch.isalnum() or ch in "-_:.") or new_request_id()


def set_request_id(request_id: str):
    return _request_id.set(request_id)


def reset_request_id(token):
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()


def safe_hash(value: str | None, length: int = 12) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:length]


def sanitized_log_fields(fields: dict) -> dict:
    sanitized = {}
    for key, value in fields.items():
        hash_key = SENSITIVE_LOG_FIELD_HASHES.get(key)
        if hash_key:
            sanitized.setdefault(hash_key, safe_hash(value))
            continue
        sanitized[key] = value
    return sanitized


def log_event(event: str, level: str = "info", **fields):
    if os.getenv("STRUCTURED_LOGS_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
        return

    safe_fields = sanitized_log_fields(fields)
    payload = {
        "ts": datetime.datetime.now(datetime.UTC).isoformat(),
        "level": level,
        "event": event,
        "service": "logos_log",
        **safe_fields,
    }
    request_id = get_request_id()
    if request_id:
        payload["request_id"] = request_id

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str), flush=True)
