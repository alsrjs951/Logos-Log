import os
import json
import datetime
import hashlib
import asyncio
import time
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from models.value_cards import (
    ValueCardCreate, 
    ValueCardResponse, 
    AnalysisExtractRequest, 
    AnalysisExtractResponse,
    RecommendedExperimentResponse,
)
from api.deps import get_current_user
from services.encryption import encrypt, decrypt
from services.value_taxonomy import classify_value, public_taxonomy
from services.value_trends import compute_trends
from services.observability import log_event
from services.rate_limit import enforce_env_rate_limit
from db import get_db

router = APIRouter()

EXPERIMENT_PROMPT_VERSION = "meaning-action-v2"
DEFAULT_EXPERIMENT_LLM_TIMEOUT_SECONDS = 12.0
MAX_EXPERIMENT_CHARS = 180
MAX_REASON_CHARS = 220
MAX_REFLECTION_QUESTION_CHARS = 160

CLINICAL_COPY_PATTERNS = [
    "치료",
    "진단",
    "처방",
    "복용",
    "임상",
    "우울증",
    "불안장애",
    "공황장애",
    "ptsd",
    "외상 후 스트레스",
    "자살",
    "자해",
]

PRESSURE_COPY_PATTERNS = [
    "반드시",
    "무조건",
    "꼭 해야",
    "해야 합니다",
    "해야 한다",
    "하지 않으면",
    "실패입니다",
    "극복해야",
]

SMALL_ACTION_MARKERS = [
    "이번 주",
    "오늘",
    "하루",
    "한 번",
    "한 가지",
    "하나",
    "짧게",
    "작게",
    "작은",
    "10분",
    "15분",
    "30분",
]


class ExperimentCopyQualityError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        return max(1.0, value)
    except ValueError:
        return default


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def _safe_user_hash(user_id: str) -> str:
    return hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:12]


def _log_experiment_event(event: str, **fields):
    log_event(
        f"recommended_experiment_{event}",
        domain="value_cards",
        feature="recommended_experiment",
        **fields,
    )


def _enforce_llm_rate_limit(user_id: str, scope: str):
    enforce_env_rate_limit(
        scope=scope,
        identifier=user_id,
        limit_env="LLM_RATE_LIMIT_PER_MINUTE",
        default_limit=20,
        window_env="LLM_RATE_LIMIT_WINDOW_SECONDS",
        default_window_seconds=60,
    )


def _parse_llm_json(content: str) -> dict:
    content_str = (content or "").strip()
    if content_str.startswith("```"):
        content_str = content_str.strip("`")
        if content_str.lstrip().lower().startswith("json"):
            content_str = content_str.lstrip()[4:]
    try:
        return json.loads(content_str)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", content_str, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def _contains_any(text: str, patterns: list[str]) -> bool:
    source = (text or "").lower()
    return any(pattern.lower() in source for pattern in patterns)


def _sentence_like_count(text: str) -> int:
    return sum(text.count(marker) for marker in [".", "!", "?", "。", "！", "？", "\n"])


def _validate_experiment_copy(experiment: str, reason: str, reflection_question: str):
    combined = " ".join([experiment or "", reason or "", reflection_question or ""])

    if len(experiment) < 8:
        raise ExperimentCopyQualityError("experiment_too_short")
    if len(experiment) > MAX_EXPERIMENT_CHARS:
        raise ExperimentCopyQualityError("experiment_too_long")
    if len(reason) > MAX_REASON_CHARS:
        raise ExperimentCopyQualityError("reason_too_long")
    if len(reflection_question) > MAX_REFLECTION_QUESTION_CHARS:
        raise ExperimentCopyQualityError("reflection_question_too_long")
    if _contains_any(combined, CLINICAL_COPY_PATTERNS):
        raise ExperimentCopyQualityError("clinical_or_crisis_copy")
    if _contains_any(combined, PRESSURE_COPY_PATTERNS):
        raise ExperimentCopyQualityError("high_pressure_copy")
    if not _contains_any(experiment, SMALL_ACTION_MARKERS):
        raise ExperimentCopyQualityError("not_small_action_copy")
    if _sentence_like_count(experiment) > 2:
        raise ExperimentCopyQualityError("too_many_steps")


def _card_group_key(card: dict) -> str:
    return card.get("canonical_value") or (card.get("keyword") or "").strip()


def _cards_fingerprint(cards: list[dict]) -> str:
    payload = [
        {
            "id": card.get("id"),
            "keyword": card.get("keyword"),
            "insight": card.get("insight"),
            "canonical_value": card.get("canonical_value"),
            "created_at": str(card.get("created_at") or ""),
        }
        for card in cards
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_text(value: str) -> str:
    return encrypt(value or "")


def _cached_text(doc: dict, field: str, fallback: str = "") -> str:
    return decrypt(doc.get(field)) or fallback


def _experiment_cache_text_fields(reason: str, experiment: str, reflection_question: str) -> dict:
    return {
        "reason": _cache_text(reason),
        "experiment": _cache_text(experiment),
        "reflection_question": _cache_text(reflection_question),
    }


def _cached_experiment_response(doc: dict) -> RecommendedExperimentResponse:
    return RecommendedExperimentResponse(
        status="ready",
        anchor_card_id=doc.get("anchor_card_id"),
        related_card_ids=doc.get("related_card_ids") or [],
        reason=_cached_text(doc, "reason", "최근 가치 카드에서 이어진 작은 실험입니다."),
        experiment=_cached_text(doc, "experiment", ""),
        reflection_question=_cached_text(
            doc,
            "reflection_question",
            "그 선택은 내 가치와 실제 행동 사이를 조금 더 가깝게 만들었나요?",
        ),
        source="llm_cache",
        cache_key=doc.get("cache_key"),
    )


def _safe_cached_experiment_response(
    doc: dict,
    *,
    user_hash: Optional[str] = None,
    event: str = "cache_read_error",
) -> Optional[RecommendedExperimentResponse]:
    try:
        response = _cached_experiment_response(doc)
        if not response.experiment.strip():
            raise ValueError("cached experiment is empty")
        return response
    except Exception as cache_error:
        _log_experiment_event(
            event,
            user_hash=user_hash,
            cache_key=doc.get("cache_key"),
            error_type=type(cache_error).__name__,
        )
        return None


def _build_experiment_prompt(cards: list[dict], anchor: dict, related: list[dict]) -> str:
    def line(card: dict) -> str:
        date = str(card.get("created_at") or "")[:10]
        canonical = card.get("canonical_value") or "미분류"
        return (
            f"- id={card.get('id')} | date={date} | keyword={card.get('keyword')} | "
            f"canonical={canonical} | insight={card.get('insight')}"
        )

    related_text = "\n".join(line(card) for card in related[:8])
    recent_text = "\n".join(line(card) for card in cards[:8])

    return (
        "[기준 가치 카드]\n"
        f"{line(anchor)}\n\n"
        "[같은 가치 흐름의 카드]\n"
        f"{related_text or '(없음)'}\n\n"
        "[최근 가치 카드 참고]\n"
        f"{recent_text}\n"
    )

def serialize_value_card(doc) -> dict:
    """
    MongoDB 문서 객체를 Pydantic 모델에 호환되는 직렬화된 사전 객체로 변환합니다.
    """
    if not doc:
        return {}
    return {
        "id": str(doc["_id"]),
        "keyword": doc.get("keyword"),
        "insight": decrypt(doc.get("insight")),
        "emotion": doc.get("emotion"),
        "user_id": doc.get("user_id"),
        "created_at": doc.get("created_at"),
        "canonical_value": doc.get("canonical_value"),
        "canonical_confidence": doc.get("canonical_confidence"),
        "canonical_method": doc.get("canonical_method"),
    }


@router.get("/value-cards/recommended-experiment", response_model=RecommendedExperimentResponse)
async def recommend_value_experiment(
    refresh: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    가치 카드에서 이번 주에 해볼 작은 실험을 LLM으로 생성한다.
    저장은 하지 않고, 사용자가 명시적으로 채택할 때 /intentions 로 저장한다.
    """
    db = get_db()
    user_id = current_user["id"]
    user_hash = _safe_user_hash(user_id)
    cached_for_fallback = None
    started_at = time.monotonic()
    try:
        cursor = db.value_cards.find({"user_id": user_id}).sort("created_at", -1)
        cards = [serialize_value_card(doc) for doc in cursor]

        if not cards:
            _log_experiment_event(
                "empty",
                user_hash=user_hash,
                refresh=refresh,
                latency_ms=round((time.monotonic() - started_at) * 1000),
            )
            return RecommendedExperimentResponse(
                status="empty",
                source="llm",
                reason="아직 추천할 가치 카드가 없습니다.",
                related_card_ids=[],
            )

        anchor = next((card for card in cards if card.get("canonical_value")), cards[0])
        group_key = _card_group_key(anchor)
        related = [card for card in cards if _card_group_key(card) == group_key]
        fingerprint = _cards_fingerprint(cards)
        cache_key = f"{EXPERIMENT_PROMPT_VERSION}:{fingerprint[:16]}"
        cache_query = {
            "user_id": user_id,
            "fingerprint": fingerprint,
            "prompt_version": EXPERIMENT_PROMPT_VERSION,
        }
        cached_for_fallback = db.value_experiment_recommendations.find_one(cache_query)

        if cached_for_fallback and not refresh:
            cached_response = _safe_cached_experiment_response(
                cached_for_fallback,
                user_hash=user_hash,
                event="cache_hit_read_error",
            )
            if not cached_response:
                cached_for_fallback = None
            else:
                _log_experiment_event(
                    "cache_hit",
                    user_hash=user_hash,
                    refresh=refresh,
                    cache_key=cache_key,
                    card_count=len(cards),
                    related_count=len(related),
                    latency_ms=round((time.monotonic() - started_at) * 1000),
                )
                return cached_response

            _log_experiment_event(
                "cache_ignored",
                user_hash=user_hash,
                refresh=refresh,
                cache_key=cache_key,
                card_count=len(cards),
                related_count=len(related),
                latency_ms=round((time.monotonic() - started_at) * 1000),
            )

        _enforce_llm_rate_limit(user_id, "llm_experiment")

        system_prompt = (
            "당신은 Logos-Log의 의미 행동 코치입니다. 사용자의 가치 카드들을 읽고, "
            "치료나 진단이 아니라 이번 주에 부담 없이 시도할 수 있는 작은 행동 실험을 제안합니다.\n\n"
            "원칙:\n"
            "- 반드시 사용자의 카드에 나온 가치와 인사이트를 바탕으로 씁니다.\n"
            "- '해야 한다'가 아니라 '시도해보세요' 수준의 낮은 압박으로 씁니다.\n"
            "- 추상적 조언 대신 7일 안에 실행 가능한 구체적 행동으로 씁니다.\n"
            "- 임상적 조언, 증상 판단, 치료 효과 단정은 금지합니다.\n"
            "- 실험 문구는 사용자가 그대로 다짐으로 저장할 수 있게 1문장으로 씁니다.\n"
            "- 이유와 회고 질문은 따뜻하지만 과장 없이 씁니다.\n\n"
            "다른 텍스트 없이 아래 JSON만 출력하세요:\n"
            "{\n"
            '  "reason": "왜 이 실험이 지금 사용자의 가치 흐름과 맞는지 1문장",\n'
            '  "experiment": "이번 주에 해볼 구체적인 작은 실험 1문장",\n'
            '  "reflection_question": "며칠 뒤 돌아볼 회고 질문 1개"\n'
            "}"
        )

        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.45)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=_build_experiment_prompt(cards, anchor, related)),
        ]
        timeout_seconds = _float_env(
            "VALUE_EXPERIMENT_LLM_TIMEOUT_SECONDS",
            DEFAULT_EXPERIMENT_LLM_TIMEOUT_SECONDS,
        )
        response = await asyncio.wait_for(llm.ainvoke(messages), timeout=timeout_seconds)
        parsed = _parse_llm_json(response.content)

        experiment = (parsed.get("experiment") or "").strip()
        reason = (parsed.get("reason") or "").strip()
        reflection_question = (parsed.get("reflection_question") or "").strip()
        if not experiment:
            raise ValueError("LLM recommendation missing experiment")
        reason = reason or "최근 가치 카드에서 이어진 작은 실험입니다."
        reflection_question = reflection_question or "그 선택은 내 가치와 실제 행동 사이를 조금 더 가깝게 만들었나요?"
        _validate_experiment_copy(experiment, reason, reflection_question)

        now = _utc_now_iso()
        cache_doc = {
            "user_id": user_id,
            "fingerprint": fingerprint,
            "prompt_version": EXPERIMENT_PROMPT_VERSION,
            "cache_key": cache_key,
            "anchor_card_id": anchor["id"],
            "related_card_ids": [card["id"] for card in related],
            **_experiment_cache_text_fields(reason, experiment, reflection_question),
            "updated_at": now,
        }
        try:
            db.value_experiment_recommendations.update_one(
                cache_query,
                {
                    "$set": cache_doc,
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        except Exception as cache_error:
            _log_experiment_event(
                "cache_write_error",
                user_hash=user_hash,
                cache_key=cache_key,
                error_type=type(cache_error).__name__,
            )

        _log_experiment_event(
            "generated",
            user_hash=user_hash,
            refresh=refresh,
            cache_key=cache_key,
            card_count=len(cards),
            related_count=len(related),
            timeout_seconds=timeout_seconds,
            latency_ms=round((time.monotonic() - started_at) * 1000),
        )

        return RecommendedExperimentResponse(
            status="ready",
            anchor_card_id=anchor["id"],
            related_card_ids=[card["id"] for card in related],
            reason=reason,
            experiment=experiment,
            reflection_question=reflection_question,
            source="llm",
            cache_key=cache_key,
        )
    except Exception as e:
        _log_experiment_event(
            "error",
            user_hash=user_hash,
            refresh=refresh,
            error_type=type(e).__name__,
            error_code=getattr(e, "code", None),
            has_cached_fallback=bool(cached_for_fallback),
            latency_ms=round((time.monotonic() - started_at) * 1000),
        )
        if cached_for_fallback:
            cached_response = _safe_cached_experiment_response(
                cached_for_fallback,
                user_hash=user_hash,
                event="fallback_cache_read_error",
            )
            if not cached_response:
                raise HTTPException(status_code=502, detail="추천 실험 생성 중 오류가 발생했습니다.")
            _log_experiment_event(
                "fallback_cache",
                user_hash=user_hash,
                refresh=refresh,
                cache_key=cached_for_fallback.get("cache_key"),
            )
            return cached_response
        raise HTTPException(status_code=502, detail="추천 실험 생성 중 오류가 발생했습니다.")

@router.post("/value-cards/extract", response_model=AnalysisExtractResponse)
async def extract_value_card(
    request: AnalysisExtractRequest,
    current_user: dict = Depends(get_current_user)
):
    if not request.history:
        raise HTTPException(status_code=400, detail="대화 내역이 비어 있습니다.")
    _enforce_llm_rate_limit(current_user["id"], "llm_value_extract")
        
    try:
        # ChatOpenAI 초기화 (비스트리밍으로 빠르게 JSON 받아오기)
        llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.3
        )
        
        system_prompt = (
            "당신은 심리 상담 대화록에서 사용자가 깨달은 가치와 삶의 태도를 분석하고 요약하는 전문가입니다.\n"
            "제공되는 대화 내역(사용자와 챗봇의 대화)을 읽고, 사용자가 대화 과정에서 최종적으로 도달한 '아하 모먼트(Aha-moment/깨달음의 순간)'를 찾아내어 가치 카드로 만드십시오.\n\n"
            "답변은 반드시 아래 형식을 갖춘 JSON 문자열 형태로만 출력해야 합니다. 다른 텍스트는 절대 포함하지 마십시오:\n"
            "{\n"
            "  \"keyword\": \"사용자가 깨달은 핵심 실존적 가치 (예: 자유, 책임, 관계, 용기, 수용, 태도, 연대 등 딱 한 단어로 작성)\",\n"
            "  \"insight\": \"사용자의 고민과 성찰을 반영하여, 이 대화를 통해 얻은 구체적인 깨달음과 삶의 태도를 1인칭 관점의 따뜻한 문장으로 한 줄 요약한 것\"\n"
            "}"
        )
        
        # 대화 히스토리를 텍스트로 가공
        history_text = ""
        for item in request.history:
            role_name = "사용자" if item.role == "user" else "상담가"
            history_text += f"{role_name}: {item.content}\n"
            
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"--- 대화 내역 ---\n{history_text}")
        ]
        
        response = await llm.ainvoke(messages)
        content_str = response.content.strip()
        
        # JSON 파싱 시도
        try:
            parsed_data = json.loads(content_str)
            return AnalysisExtractResponse(
                keyword=parsed_data.get("keyword", "성찰").strip(),
                insight=parsed_data.get("insight", "삶의 가치를 돌아보았습니다.").strip()
            )
        except json.JSONDecodeError:
            # LLM이 JSON 형식을 맞추지 못했을 경우 백업 문자열 파싱 시도
            if "keyword" in content_str and "insight" in content_str:
                import re
                kw_match = re.search(r'"keyword"\s*:\s*"([^"]+)"', content_str)
                is_match = re.search(r'"insight"\s*:\s*"([^"]+)"', content_str)
                return AnalysisExtractResponse(
                    keyword=kw_match.group(1) if kw_match else "성찰",
                    insight=is_match.group(1) if is_match else "대화에서 의미 있는 가치를 발견했습니다."
                )
            raise HTTPException(status_code=500, detail="AI가 올바른 JSON 형식으로 가치를 추출하지 못했습니다.")
            
    except Exception as e:
        log_event(
            "value_card_extract_error",
            level="error",
            user_hash=_safe_user_hash(current_user["id"]),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail="가치 추출 처리 중 오류가 발생했습니다.")

@router.post("/value-cards", response_model=ValueCardResponse)
async def create_value_card(card: ValueCardCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    try:
        # 자유 keyword 는 표면 라벨로 보존하고, 그 아래 Schwartz canonical 값을 부여한다.
        # (사용자가 모달에서 편집한 최종 keyword/insight 기준으로 서버가 권위 분류)
        canonical_value, canonical_confidence, canonical_method = classify_value(
            card.keyword, card.insight
        )
        data = {
            "keyword": card.keyword,
            "insight": encrypt(card.insight),
            "emotion": card.emotion,
            "user_id": user_id,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "canonical_value": canonical_value,
            "canonical_confidence": canonical_confidence,
            "canonical_method": canonical_method,
        }
        result = db.value_cards.insert_one(data)
        data["_id"] = result.inserted_id
        
        return serialize_value_card(data)
    except Exception as e:
        log_event("value_card_create_db_error", level="error", user_hash=_safe_user_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")

@router.get("/value-cards/count")
async def get_value_cards_count(current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    try:
        count = db.value_cards.count_documents({"user_id": user_id})
        return {"count": count}
    except Exception as e:
        log_event("value_card_count_db_error", level="error", user_hash=_safe_user_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")

@router.get("/value-cards/taxonomy")
async def get_value_taxonomy():
    """프론트 시각화용 Schwartz 택소노미(라벨·상위차원·circumplex 각도). 인증 불필요(정적 메타)."""
    return {"values": public_taxonomy()}


@router.get("/value-cards/trends")
async def get_value_card_trends(current_user: dict = Depends(get_current_user)):
    """
    사용자 가치카드의 종단 변화(then-vs-now, 월별 타임라인, 정직 요약).
    canonical_value·created_at 만 사용하므로 insight 복호화는 불필요하다.
    """
    db = get_db()
    user_id = current_user["id"]
    try:
        cursor = db.value_cards.find(
            {"user_id": user_id},
            {"canonical_value": 1, "created_at": 1}
        )
        cards = [
            {"canonical_value": doc.get("canonical_value"), "created_at": doc.get("created_at")}
            for doc in cursor
        ]
        return compute_trends(cards)
    except Exception as e:
        log_event("value_card_trends_db_error", level="error", user_hash=_safe_user_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")


@router.get("/value-cards", response_model=List[ValueCardResponse])
async def get_value_cards(current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    try:
        cursor = db.value_cards.find({"user_id": user_id}).sort("created_at", -1)
        cards = [serialize_value_card(doc) for doc in cursor]
        return cards
    except Exception as e:
        log_event("value_card_list_db_error", level="error", user_hash=_safe_user_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="데이터베이스 처리 중 오류가 발생했습니다.")
