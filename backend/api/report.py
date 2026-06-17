import asyncio
import datetime
import json
import os
from fastapi import APIRouter, HTTPException, Depends
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from api.deps import get_current_user
from services.encryption import decrypt
from services.observability import log_event, safe_hash
from services.rate_limit import enforce_env_rate_limit
from db import get_db

router = APIRouter()

DEFAULT_WEEKLY_REPORT_TIMEOUT_SECONDS = 15.0
MAX_WEEKLY_REPORT_INPUT_CHARS = 12000
MAX_WEEKLY_SUMMARY_CHARS = 800
MAX_WEEKLY_QUESTION_CHARS = 240
MAX_WEEKLY_KEYWORD_CHARS = 24
MAX_WEEKLY_KEYWORDS = 3


class WeeklyReportQualityError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        return max(1.0, value)
    except ValueError:
        return default


def _enforce_weekly_report_rate_limit(user_id: str):
    enforce_env_rate_limit(
        scope="llm_weekly_report",
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


def _clean_report_text(value, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:max_chars].strip()


def _normalize_keywords(value) -> list[str]:
    if isinstance(value, str):
        candidates = [part.strip() for part in value.replace(";", ",").split(",")]
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []

    keywords = []
    seen = set()
    for candidate in candidates:
        keyword = _clean_report_text(candidate, MAX_WEEKLY_KEYWORD_CHARS)
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        keywords.append(keyword)
        if len(keywords) >= MAX_WEEKLY_KEYWORDS:
            break
    return keywords


def _normalize_weekly_report_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise WeeklyReportQualityError("payload_not_object")

    summary = _clean_report_text(payload.get("summary"), MAX_WEEKLY_SUMMARY_CHARS)
    next_question = _clean_report_text(payload.get("next_question"), MAX_WEEKLY_QUESTION_CHARS)
    keywords = _normalize_keywords(payload.get("keywords"))

    if not summary:
        raise WeeklyReportQualityError("missing_summary")
    if not next_question:
        raise WeeklyReportQualityError("missing_next_question")

    return {
        "summary": summary,
        "keywords": keywords,
        "next_question": next_question,
    }


def _build_weekly_journal_text(journals: list[dict]) -> str:
    parts = []
    remaining_chars = MAX_WEEKLY_REPORT_INPUT_CHARS

    for journal in journals:
        date_str = str(journal.get("created_at", ""))[:10]
        entry = (
            f"[{date_str}] 감정: {journal.get('emotion', '?')} | "
            f"제목: {decrypt(journal.get('title')) or '제목 없음'}\n"
            f"{decrypt(journal.get('content')) or ''}\n\n"
        )
        if len(entry) > remaining_chars:
            parts.append(entry[:remaining_chars].rstrip())
            break
        parts.append(entry)
        remaining_chars -= len(entry)
        if remaining_chars <= 0:
            break

    return "".join(parts).strip()


@router.get("/journals/weekly-report")
async def get_weekly_report(current_user: dict = Depends(get_current_user)):
    """
    최근 7일간의 일기를 기반으로 GPT가 주간 성찰 리포트를 생성합니다.
    - 감정 흐름 요약
    - 핵심 가치 키워드 3개
    - 다음 주 탐구 추천 질문 1개
    """
    db = get_db()
    user_id = current_user["id"]
    _enforce_weekly_report_rate_limit(user_id)

    # 7일 전 날짜 계산
    seven_days_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat()

    try:
        cursor = db.journals.find(
            {"user_id": user_id, "created_at": {"$gte": seven_days_ago}},
            {"title": 1, "content": 1, "emotion": 1, "created_at": 1}
        ).sort("created_at", 1)

        journals = list(cursor)

        # 일기가 없는 경우
        if not journals:
            return {
                "status": "empty",
                "has_data": False,
                "message": "최근 7일간 작성된 일기가 없습니다.",
                "summary": None,
                "keywords": [],
                "next_question": None,
                "journal_count": 0,
            }

        journal_text = _build_weekly_journal_text(journals)

        system_prompt = (
            "당신은 긍정 심리학과 로고테라피 전문가입니다. "
            "사용자가 이번 주에 작성한 일기들을 읽고, 따뜻하고 통찰력 있는 주간 성찰 리포트를 작성해주세요.\n\n"
            "반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요:\n"
            "{\n"
            '  "summary": "이번 주 감정 흐름과 주요 성찰 내용을 2~3문장으로 따뜻하게 요약",\n'
            '  "keywords": ["핵심가치1", "핵심가치2", "핵심가치3"],\n'
            '  "next_question": "다음 주에 스스로에게 던져볼 소크라테스식 탐구 질문 1개"\n'
            "}"
        )

        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.5)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"--- 이번 주 일기 ---\n{journal_text}"),
        ]

        try:
            timeout_seconds = _float_env(
                "WEEKLY_REPORT_LLM_TIMEOUT_SECONDS",
                DEFAULT_WEEKLY_REPORT_TIMEOUT_SECONDS,
            )
            response = await asyncio.wait_for(llm.ainvoke(messages), timeout=timeout_seconds)
            parsed = _normalize_weekly_report_payload(_parse_llm_json(response.content))
        except Exception as e:
            log_event(
                "weekly_report_llm_error",
                level="warning",
                user_hash=safe_hash(user_id),
                error_type=type(e).__name__,
                error_code=getattr(e, "code", None),
            )
            raise HTTPException(status_code=502, detail="주간 리포트 생성 응답을 완성하지 못했습니다.")

        return {
            "status": "ready",
            "has_data": True,
            "summary": parsed["summary"],
            "keywords": parsed["keywords"],
            "next_question": parsed["next_question"],
            "journal_count": len(journals),
        }

    except HTTPException:
        raise
    except Exception as e:
        log_event("weekly_report_error", level="error", user_hash=safe_hash(user_id), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="주간 리포트 생성 중 오류가 발생했습니다.")
