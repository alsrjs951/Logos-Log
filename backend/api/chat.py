from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from bson import ObjectId
from models.chat import ChatRequest
from api.deps import get_current_user
from db import get_db
from functools import lru_cache
from services.observability import get_request_id, log_event, reset_request_id, safe_hash, set_request_id
from services.rate_limit import enforce_env_rate_limit

router = APIRouter()

@lru_cache(maxsize=1)
def get_rag_service():
    from services.rag_service import RAGService
    return RAGService()


async def stream_with_rag_logging(stream, *, user_id: str, journal_id: str | None, is_journal: bool):
    request_id = get_request_id()
    token = set_request_id(request_id) if request_id else None
    try:
        async for chunk in stream:
            yield chunk
    except Exception as exc:
        log_event(
            "rag_stream_error",
            level="error",
            user_hash=safe_hash(user_id),
            journal_hash=safe_hash(journal_id),
            is_journal=is_journal,
            error_type=type(exc).__name__,
        )
        raise
    finally:
        if token:
            reset_request_id(token)


@router.post("/chat")
async def chat_endpoint(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    사용자의 질문(query)을 받아 검색된 논문을 바탕으로
    LLM의 답변을 실시간 스트리밍(SSE)으로 반환합니다.
    """
    user_id = current_user["id"]
    enforce_env_rate_limit(
        scope="llm_chat",
        identifier=user_id,
        limit_env="LLM_RATE_LIMIT_PER_MINUTE",
        default_limit=20,
        window_env="LLM_RATE_LIMIT_WINDOW_SECONDS",
        default_window_seconds=60,
    )
    rag_service = get_rag_service()
    stream = rag_service.get_streaming_response(
        query=request.query,
        history=request.history,
        is_journal=request.is_journal,
        journal_id=request.journal_id,
        user_id=user_id,
    )
    return StreamingResponse(
        stream_with_rag_logging(
            stream,
            user_id=user_id,
            journal_id=request.journal_id,
            is_journal=request.is_journal,
        ),
        media_type="text/event-stream"
    )

@router.get("/chat/history/{journal_id}")
async def get_chat_history_endpoint(journal_id: str, current_user: dict = Depends(get_current_user)):
    """
    특정 일기 ID에 대응하는 과거 대화 이력을 반환합니다.
    (데이터 접근 소유권 검증 포함)
    """
    db = get_db()
    rag_service = get_rag_service()
    user_id = current_user["id"]
    try:
        # MongoDB ObjectId 파싱 검증
        try:
            journal_oid = ObjectId(journal_id)
        except Exception:
            raise HTTPException(status_code=400, detail="유효하지 않은 일기 ID 포맷입니다.")

        # 1. 일기의 소유주 검증 (조회 권한 체크)
        journal = db.journals.find_one({"_id": journal_oid, "user_id": user_id}, {"user_id": 1})
        if not journal:
            raise HTTPException(status_code=404, detail="해당 일기를 찾을 수 없습니다.")

        # 2. 대화 이력 로드
        history = rag_service.get_chat_history(journal_id, user_id=user_id)
        
        # 과거 대화의 sources 내부에 content_ko 또는 summary_ko 가 누락된 경우 실시간 번역/요약 복구
        import asyncio
        translation_tasks = []
        task_info = [] # (msg_idx, src_idx)
        
        for msg_idx, msg in enumerate(history):
            sources = msg.get("sources") or []
            for src_idx, src in enumerate(sources):
                has_content_ko = "content_ko" in src and src["content_ko"]
                has_summary_ko = "summary_ko" in src and src["summary_ko"]
                if not has_content_ko or not has_summary_ko:
                    content_to_trans = src.get("content", "")
                    if content_to_trans:
                        translation_tasks.append(rag_service._translate_and_summarize_paper(content_to_trans))
                        task_info.append((msg_idx, src_idx))
                        
        if translation_tasks:
            translated_results = await asyncio.gather(*translation_tasks)
            changed_msg_indices = set()
            for (msg_idx, src_idx), trans_res in zip(task_info, translated_results):
                if "sources" in history[msg_idx] and len(history[msg_idx]["sources"]) > src_idx:
                    history[msg_idx]["sources"][src_idx]["content_ko"] = trans_res.get("content_ko")
                    history[msg_idx]["sources"][src_idx]["summary_ko"] = trans_res.get("summary_ko")
                    changed_msg_indices.add(msg_idx)
            
            # 번역 복원 결과를 DB에 영구 업데이트 (캐싱 최적화)
            for msg_idx in changed_msg_indices:
                msg_doc = history[msg_idx]
                msg_id = msg_doc.get("_id")
                if msg_id:
                    try:
                        db.chat_messages.update_one(
                            {"_id": msg_id, "journal_id": journal_id, "user_id": user_id},
                            {"$set": {"sources": msg_doc["sources"]}}
                        )
                    except Exception as cache_err:
                        log_event(
                            "chat_history_translation_cache_error",
                            level="warning",
                            user_hash=safe_hash(user_id),
                            journal_hash=safe_hash(journal_id),
                            error_type=type(cache_err).__name__,
                        )

        formatted_history = []
        for msg in history:
            formatted_history.append({
                "role": msg.get("role"),
                "content": msg.get("content"),
                "sources": msg.get("sources") or [],
                "crisis": msg.get("crisis", False)
            })
        return formatted_history
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            "chat_history_error",
            level="error",
            user_hash=safe_hash(user_id),
            journal_hash=safe_hash(journal_id),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail="대화 이력 조회 중 오류가 발생했습니다.")
