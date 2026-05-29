from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.chat import ChatRequest
from services.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    사용자의 질문(query)을 받아 검색된 논문을 바탕으로
    LLM의 답변을 실시간 스트리밍(SSE)으로 반환합니다.
    """
    return StreamingResponse(
        rag_service.get_streaming_response(
            query=request.query, 
            history=request.history, 
            is_journal=request.is_journal,
            journal_id=request.journal_id
        ),
        media_type="text/event-stream"
    )

@router.get("/chat/history/{journal_id}")
async def get_chat_history_endpoint(journal_id: str):
    """
    특정 일기 ID에 대응하는 과거 대화 이력을 반환합니다.
    """
    try:
        history = rag_service.get_chat_history(journal_id)
        # 프론트엔드가 요구하는 형식에 맞추어 {role, content, sources} 형태로 반환
        formatted_history = []
        for msg in history:
            formatted_history.append({
                "role": msg.get("role"),
                "content": msg.get("content"),
                "sources": msg.get("sources") or []
            })
        return formatted_history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"대화 이력 조회 중 오류 발생: {str(e)}")
