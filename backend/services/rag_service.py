import os
import json
from supabase import create_client, Client
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import AsyncGenerator
from models.chat import ChatSource

class RAGService:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError("Supabase credentials not found in env")
            
        self.supabase: Client = create_client(url, key)
        
        import torch
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": device}
        )
        
        # 스트리밍을 지원하는 LLM 인스턴스 생성
        self.llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.3,
            streaming=True
        )

    async def get_streaming_response(self, query: str, history: list = None) -> AsyncGenerator[str, None]:
        if history is None:
            history = []
            
        # 1. 질문 임베딩
        query_embedding = self.embeddings.embed_query(query)
        
        # 2. Supabase에서 관련 문서 검색
        response = self.supabase.rpc("match_documents", {
            "query_embedding": query_embedding,
            "match_threshold": 0.0,
            "match_count": 3
        }).execute()
        
        results = response.data
        sources = []
        context_text = ""
        
        for res in results:
            meta = res.get("metadata", {})
            sources.append({
                "id": res.get("id"),
                "content": res.get("content")[:100] + "...", # 프리뷰
                "author": meta.get("author", "Unknown"),
                "year": meta.get("year", ""),
                "category": meta.get("category", ""),
                "similarity": res.get("similarity", 0)
            })
            context_text += f"\n- {res.get('content')}"

        # 3. LLM 프롬프트 생성
        system_prompt = (
            "당신은 심리학 논문을 기반으로 답변하는 전문적인 챗봇 Logos-Log 입니다.\n"
            "사용자의 질문에 대해 제공된 논문 내용을 바탕으로 친절하게 답변해주세요.\n"
            "만약 제공된 내용으로 알 수 없다면 솔직하게 모른다고 대답하세요.\n"
            f"--- 제공된 논문 내용 ---\n{context_text}"
        )
        
        messages = [SystemMessage(content=system_prompt)]
        
        # 이전 대화 내역(히스토리) 추가
        for h in history:
            if h.role == "user":
                messages.append(HumanMessage(content=h.content))
            elif h.role == "bot":
                messages.append(AIMessage(content=h.content))
                
        # 현재 질문 추가
        messages.append(HumanMessage(content=query))
        
        # 4. 소스(출처) 데이터를 첫 번째 이벤트로 전송 (클라이언트에서 파싱할 수 있게 특수 포맷 사용)
        yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"
        
        # 5. LLM 스트리밍 응답 (한 글자씩 Yield)
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"
                
        # 6. 스트리밍 종료 알림
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
