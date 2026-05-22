from fastapi import APIRouter
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
        rag_service.get_streaming_response(request.query),
        media_type="text/event-stream"
    )
