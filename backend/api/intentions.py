"""
insight→행동→결과 루프 API.

가치 카드(insight)에 연결된 '다짐(intention)'을 만들고, 나중에 '결과(outcome)'를
기록해 루프를 닫는다. 다짐/결과 본문은 insight급 민감정보이므로 encrypt/decrypt.

재질문은 pull-not-push: GET /intentions/due 가 '며칠 지난 열린 다짐'을 돌려주고,
프론트는 사용자가 변화뷰에 들렀을 때만 노출한다(알림 푸시 없음).
"""
import datetime
import hashlib
import hmac
import os
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Depends, Request
from pymongo.errors import DuplicateKeyError
from typing import List, Optional

from models.intentions import IntentionCreate, IntentionReflect, IntentionResponse
from api.deps import JWT_SECRET, get_current_user
from services.encryption import encrypt, decrypt
from services.intention_loop import (
    due_intentions, compute_intention_stats,
    is_intention_due, review_available_at,
    STATUS_OPEN, STATUS_REFLECTED, STATUS_DISMISSED,
)
from services.observability import log_event, safe_hash
from db import get_db

router = APIRouter()

KNOWN_ACTION_SOURCES = {
    "dashboard_action_loop",
    "meaning_network",
    "meaning_change_review",
    "value_card_modal",
    "unknown",
}


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="올바르지 않은 ID 형식입니다.")


def serialize_intention(doc, card_map=None) -> dict:
    if not doc:
        return {}
    card = (card_map or {}).get(doc.get("card_id")) if card_map else None
    created_at = doc.get("created_at")
    return {
        "id": str(doc["_id"]),
        "card_id": doc.get("card_id"),
        "intention": decrypt(doc.get("intention")),
        "status": doc.get("status", STATUS_OPEN),
        "created_at": created_at,
        "outcome": decrypt(doc.get("outcome")) if doc.get("outcome") else None,
        "outcome_logged_at": doc.get("outcome_logged_at"),
        "dismissed_at": doc.get("dismissed_at"),
        "helpfulness": doc.get("helpfulness"),
        "review_available_at": review_available_at(created_at),
        "is_due": is_intention_due(doc),
        "was_duplicate": bool(doc.get("_was_duplicate")),
        "card_keyword": card.get("keyword") if card else None,
        "card_canonical_value": card.get("canonical_value") if card else None,
    }


def _card_map(db, user_id, card_ids):
    """card_id(str) → {keyword, canonical_value} 일괄 조회(N+1 방지)."""
    oids = []
    for cid in set(card_ids):
        try:
            oids.append(ObjectId(cid))
        except (InvalidId, TypeError):
            continue
    if not oids:
        return {}
    cursor = db.value_cards.find(
        {"_id": {"$in": oids}, "user_id": user_id},
        {"keyword": 1, "canonical_value": 1},
    )
    return {str(c["_id"]): c for c in cursor}


def _clean_action_source(value: str | None) -> str:
    source = (value or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    source = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in source).strip("_")
    if not source:
        return "unknown"
    return source if source in KNOWN_ACTION_SOURCES else "other"


def _action_source(request: Request, explicit_source: str | None = None) -> str:
    return _clean_action_source(explicit_source or request.headers.get("x-logos-action-source"))


def _card_value(card: dict | None) -> str:
    return (card or {}).get("canonical_value") or "uncategorized"


def _normalize_intention_text(value: str) -> str:
    return " ".join((value or "").strip().split()).casefold()


def _intention_hash_secret() -> str:
    return str(os.getenv("INTENTION_HASH_SECRET") or JWT_SECRET)


def _hmac_intention_text_hash(value: str, secret: str) -> str:
    normalized = _normalize_intention_text(value)
    return hmac.new(
        str(secret).encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _intention_text_hash(value: str) -> str:
    return _hmac_intention_text_hash(value, _intention_hash_secret())


def _legacy_jwt_intention_text_hash(value: str) -> str:
    return _hmac_intention_text_hash(value, JWT_SECRET)


def _legacy_intention_text_hash(value: str) -> str:
    normalized = _normalize_intention_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _backfill_intention_hash(db, user_id: str, candidate: dict, intention_hash: str):
    try:
        db.intentions.update_one(
            {"_id": candidate["_id"], "user_id": user_id},
            {"$set": {"intention_hash": intention_hash}},
        )
        candidate["intention_hash"] = intention_hash
    except Exception as e:
        log_event(
            "intention_hash_backfill_error",
            level="warning",
            user_hash=safe_hash(user_id),
            intention_id_hash=safe_hash(str(candidate.get("_id"))),
            error_type=type(e).__name__,
        )


def _find_duplicate_by_hash(db, user_id: str, card_id: str, intention_hash: str):
    return db.intentions.find_one({
        "user_id": user_id,
        "card_id": card_id,
        "status": STATUS_OPEN,
        "intention_hash": intention_hash,
    })


def _find_duplicate_open_intention(db, user_id: str, card_id: str, intention_hash: str, intention_text: str):
    existing = _find_duplicate_by_hash(db, user_id, card_id, intention_hash)
    if existing:
        return existing

    legacy_hashes = []
    for legacy_hash in (
        _legacy_jwt_intention_text_hash(intention_text),
        _legacy_intention_text_hash(intention_text),
    ):
        if legacy_hash != intention_hash and legacy_hash not in legacy_hashes:
            legacy_hashes.append(legacy_hash)

    for legacy_hash in legacy_hashes:
        existing = _find_duplicate_by_hash(db, user_id, card_id, legacy_hash)
        if existing:
            _backfill_intention_hash(db, user_id, existing, intention_hash)
            return existing

    normalized_text = _normalize_intention_text(intention_text)
    legacy_candidates = db.intentions.find({
        "user_id": user_id,
        "card_id": card_id,
        "status": STATUS_OPEN,
        "$or": [
            {"intention_hash": {"$exists": False}},
            {"intention_hash": None},
        ],
    })

    for candidate in legacy_candidates:
        if _normalize_intention_text(decrypt(candidate.get("intention"))) != normalized_text:
            continue
        _backfill_intention_hash(db, user_id, candidate, intention_hash)
        return candidate

    return None


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def _intention_age_days(doc: dict) -> int | None:
    created_at = doc.get("created_at")
    if not created_at:
        return None
    try:
        created = datetime.datetime.fromisoformat(created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=datetime.UTC)
        else:
            created = created.astimezone(datetime.UTC)
        return max(0, (datetime.datetime.now(datetime.UTC) - created).days)
    except (TypeError, ValueError):
        return None


def _experiment_event_fields(user_id: str, doc: dict, card: dict | None, source: str) -> dict:
    return {
        "user_hash": safe_hash(user_id),
        "intention_id_hash": safe_hash(str(doc.get("_id"))) if doc.get("_id") else None,
        "card_hash": safe_hash(doc.get("card_id")),
        "card_value": _card_value(card),
        "source": source,
    }


def _ensure_open_intention(doc: dict):
    if doc.get("status", STATUS_OPEN) != STATUS_OPEN:
        raise HTTPException(status_code=409, detail="이미 처리된 실험입니다. 행동 루프를 새로고침해 주세요.")


def _duplicate_intention_response(
    user_id: str,
    card_id: str,
    existing: dict,
    card: dict,
    source: str,
    intention_text: str,
) -> dict:
    existing["_was_duplicate"] = True
    log_event(
        "meaning_experiment_duplicate_reused",
        **_experiment_event_fields(user_id, existing, card, source),
        intention_chars=len(intention_text),
    )
    return serialize_intention(existing, {card_id: card})


@router.post("/intentions", response_model=IntentionResponse)
async def create_intention(
    body: IntentionCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    user_id = current_user["id"]
    # 연결될 가치 카드가 본인 것인지 확인
    card = db.value_cards.find_one({"_id": _oid(body.card_id), "user_id": user_id})
    if not card:
        raise HTTPException(status_code=404, detail="연결할 가치 카드를 찾을 수 없습니다.")
    if not body.intention.strip():
        raise HTTPException(status_code=400, detail="다짐 내용이 비어 있습니다.")
    try:
        source = _action_source(request, body.source)
        intention_text = body.intention.strip()
        intention_hash = _intention_text_hash(intention_text)
        existing = _find_duplicate_open_intention(db, user_id, body.card_id, intention_hash, intention_text)
        if existing:
            return _duplicate_intention_response(user_id, body.card_id, existing, card, source, intention_text)

        data = {
            "card_id": body.card_id,
            "user_id": user_id,
            "intention": encrypt(intention_text),
            "intention_hash": intention_hash,
            "status": STATUS_OPEN,
            "created_at": _utc_now_iso(),
            "outcome": None,
            "outcome_logged_at": None,
            "helpfulness": None,
        }
        try:
            result = db.intentions.insert_one(data)
        except DuplicateKeyError:
            existing = _find_duplicate_by_hash(db, user_id, body.card_id, intention_hash)
            if existing:
                return _duplicate_intention_response(user_id, body.card_id, existing, card, source, intention_text)
            log_event(
                "meaning_experiment_duplicate_key_unresolved",
                level="warning",
                user_hash=safe_hash(user_id),
                card_hash=safe_hash(body.card_id),
                source=source,
            )
            raise HTTPException(status_code=409, detail="이미 담긴 실험입니다. 목록을 새로고침해 주세요.")
        data["_id"] = result.inserted_id
        log_event(
            "meaning_experiment_adopted",
            **_experiment_event_fields(user_id, data, card, source),
            intention_chars=len(intention_text),
        )
        return serialize_intention(data, {body.card_id: card})
    except HTTPException:
        raise
    except Exception as e:
        log_event("intention_create_db_error", level="error", user_hash=safe_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.get("/intentions/due", response_model=List[IntentionResponse])
async def get_due_intentions(current_user: dict = Depends(get_current_user)):
    """돌아볼 다짐(pull 재질문 대상). 며칠 지난 열린 다짐만."""
    db = get_db()
    user_id = current_user["id"]
    try:
        all_open = list(db.intentions.find({"user_id": user_id, "status": STATUS_OPEN}))
        due = due_intentions(all_open)
        cmap = _card_map(db, user_id, [it.get("card_id") for it in due])
        return [serialize_intention(it, cmap) for it in due]
    except Exception as e:
        log_event("intention_due_db_error", level="error", user_hash=safe_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.get("/intentions/stats")
async def get_intention_stats(current_user: dict = Depends(get_current_user)):
    """후속 이행률·도움정도 통계(측정 지표)."""
    db = get_db()
    user_id = current_user["id"]
    try:
        items = list(db.intentions.find(
            {"user_id": user_id},
            {"status": 1, "helpfulness": 1, "created_at": 1},
        ))
        return compute_intention_stats(items)
    except Exception as e:
        log_event("intention_stats_db_error", level="error", user_hash=safe_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.get("/intentions", response_model=List[IntentionResponse])
async def list_intentions(
    card_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    user_id = current_user["id"]
    query = {"user_id": user_id}
    if card_id:
        query["card_id"] = card_id
    try:
        items = list(db.intentions.find(query).sort("created_at", -1))
        cmap = _card_map(db, user_id, [it.get("card_id") for it in items])
        return [serialize_intention(it, cmap) for it in items]
    except Exception as e:
        log_event("intention_list_db_error", level="error", user_hash=safe_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.patch("/intentions/{intention_id}/reflect", response_model=IntentionResponse)
async def reflect_intention(
    intention_id: str,
    body: IntentionReflect,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """그 다짐, 해보니 어땠나 — 결과 + 도움정도 기록(status→reflected)."""
    db = get_db()
    user_id = current_user["id"]
    if not body.outcome.strip():
        raise HTTPException(status_code=400, detail="결과 내용이 비어 있습니다.")
    doc = db.intentions.find_one({"_id": _oid(intention_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="다짐을 찾을 수 없습니다.")
    _ensure_open_intention(doc)
    try:
        update = {
            "outcome": encrypt(body.outcome.strip()),
            "outcome_logged_at": _utc_now_iso(),
            "helpfulness": body.helpfulness,
            "status": STATUS_REFLECTED,
        }
        result = db.intentions.update_one({"_id": doc["_id"], "user_id": user_id, "status": STATUS_OPEN}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=409, detail="이미 처리된 실험입니다. 행동 루프를 새로고침해 주세요.")
        doc.update(update)
        cmap = _card_map(db, user_id, [doc.get("card_id")])
        card = cmap.get(doc.get("card_id"))
        log_event(
            "meaning_experiment_reflected",
            **_experiment_event_fields(user_id, doc, card, _action_source(request, body.source)),
            helpfulness=body.helpfulness,
            outcome_chars=len(body.outcome.strip()),
            age_days=_intention_age_days(doc),
        )
        return serialize_intention(doc, cmap)
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            "intention_reflect_db_error",
            level="error",
            user_hash=safe_hash(user_id),
            intention_id_hash=safe_hash(intention_id),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.post("/intentions/{intention_id}/dismiss", response_model=IntentionResponse)
async def dismiss_intention(
    intention_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """이 다짐은 접어두기(status→dismissed). 채근 압박을 피하는 출구."""
    db = get_db()
    user_id = current_user["id"]
    doc = db.intentions.find_one({"_id": _oid(intention_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="다짐을 찾을 수 없습니다.")
    _ensure_open_intention(doc)
    try:
        update = {
            "status": STATUS_DISMISSED,
            "dismissed_at": _utc_now_iso(),
        }
        result = db.intentions.update_one({"_id": doc["_id"], "user_id": user_id, "status": STATUS_OPEN}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=409, detail="이미 처리된 실험입니다. 행동 루프를 새로고침해 주세요.")
        doc.update(update)
        cmap = _card_map(db, user_id, [doc.get("card_id")])
        card = cmap.get(doc.get("card_id"))
        log_event(
            "meaning_experiment_dismissed",
            **_experiment_event_fields(user_id, doc, card, _action_source(request)),
            age_days=_intention_age_days(doc),
        )
        return serialize_intention(doc, cmap)
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            "intention_dismiss_db_error",
            level="error",
            user_hash=safe_hash(user_id),
            intention_id_hash=safe_hash(intention_id),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")
