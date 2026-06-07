"""
insight→행동→결과 루프 API.

가치 카드(insight)에 연결된 '다짐(intention)'을 만들고, 나중에 '결과(outcome)'를
기록해 루프를 닫는다. 다짐/결과 본문은 insight급 민감정보이므로 encrypt/decrypt.

재질문은 pull-not-push: GET /intentions/due 가 '며칠 지난 열린 다짐'을 돌려주고,
프론트는 사용자가 변화뷰에 들렀을 때만 노출한다(알림 푸시 없음).
"""
import datetime
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional

from models.intentions import IntentionCreate, IntentionReflect, IntentionResponse
from api.deps import get_current_user
from services.encryption import encrypt, decrypt
from services.intention_loop import (
    due_intentions, compute_intention_stats,
    STATUS_OPEN, STATUS_REFLECTED, STATUS_DISMISSED,
)
from db import get_db

router = APIRouter()


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="올바르지 않은 ID 형식입니다.")


def serialize_intention(doc, card_map=None) -> dict:
    if not doc:
        return {}
    card = (card_map or {}).get(doc.get("card_id")) if card_map else None
    return {
        "id": str(doc["_id"]),
        "card_id": doc.get("card_id"),
        "intention": decrypt(doc.get("intention")),
        "status": doc.get("status", STATUS_OPEN),
        "created_at": doc.get("created_at"),
        "outcome": decrypt(doc.get("outcome")) if doc.get("outcome") else None,
        "outcome_logged_at": doc.get("outcome_logged_at"),
        "helpfulness": doc.get("helpfulness"),
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


@router.post("/intentions", response_model=IntentionResponse)
async def create_intention(body: IntentionCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    # 연결될 가치 카드가 본인 것인지 확인
    card = db.value_cards.find_one({"_id": _oid(body.card_id), "user_id": user_id})
    if not card:
        raise HTTPException(status_code=404, detail="연결할 가치 카드를 찾을 수 없습니다.")
    if not body.intention.strip():
        raise HTTPException(status_code=400, detail="다짐 내용이 비어 있습니다.")
    try:
        data = {
            "card_id": body.card_id,
            "user_id": user_id,
            "intention": encrypt(body.intention.strip()),
            "status": STATUS_OPEN,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "outcome": None,
            "outcome_logged_at": None,
            "helpfulness": None,
        }
        result = db.intentions.insert_one(data)
        data["_id"] = result.inserted_id
        return serialize_intention(data, {body.card_id: card})
    except HTTPException:
        raise
    except Exception as e:
        print(f"[intentions] DB error: {e}", flush=True)
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
        print(f"[intentions] DB error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.get("/intentions/stats")
async def get_intention_stats(current_user: dict = Depends(get_current_user)):
    """후속 이행률·도움정도 통계(측정 지표)."""
    db = get_db()
    user_id = current_user["id"]
    try:
        items = list(db.intentions.find(
            {"user_id": user_id},
            {"status": 1, "helpfulness": 1},
        ))
        return compute_intention_stats(items)
    except Exception as e:
        print(f"[intentions] DB error: {e}", flush=True)
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
        print(f"[intentions] DB error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.patch("/intentions/{intention_id}/reflect", response_model=IntentionResponse)
async def reflect_intention(
    intention_id: str,
    body: IntentionReflect,
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
    try:
        update = {
            "outcome": encrypt(body.outcome.strip()),
            "outcome_logged_at": datetime.datetime.utcnow().isoformat(),
            "helpfulness": body.helpfulness,
            "status": STATUS_REFLECTED,
        }
        db.intentions.update_one({"_id": doc["_id"]}, {"$set": update})
        doc.update(update)
        cmap = _card_map(db, user_id, [doc.get("card_id")])
        return serialize_intention(doc, cmap)
    except Exception as e:
        print(f"[intentions] DB error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.post("/intentions/{intention_id}/dismiss", response_model=IntentionResponse)
async def dismiss_intention(intention_id: str, current_user: dict = Depends(get_current_user)):
    """이 다짐은 접어두기(status→dismissed). 채근 압박을 피하는 출구."""
    db = get_db()
    user_id = current_user["id"]
    doc = db.intentions.find_one({"_id": _oid(intention_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="다짐을 찾을 수 없습니다.")
    try:
        db.intentions.update_one({"_id": doc["_id"]}, {"$set": {"status": STATUS_DISMISSED}})
        doc["status"] = STATUS_DISMISSED
        cmap = _card_map(db, user_id, [doc.get("card_id")])
        return serialize_intention(doc, cmap)
    except Exception as e:
        print(f"[intentions] DB error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")
