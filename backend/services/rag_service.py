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
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError("Supabase credentials not found in env")

        # /rest/v1 경로가 붙어있으면 제거 (supabase 클라이언트가 자체적으로 추가함)
        if url.endswith("/rest/v1"):
            url = url[: -len("/rest/v1")]

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
        
        # 2. Supabase에서 관련 문서 검색 (유사도 임계치 0.57로 미세 조정)
        response = self.supabase.rpc("match_documents", {
            "query_embedding": query_embedding,
            "match_threshold": 0.57,
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

        # 3. 소크라테스식 대화법 & 의미치료 기반 시스템 프롬프트 생성
        if results:
            system_prompt = (
                "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 자아 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                "[대화 원칙]\n"
                "1. 제공된 [학술 논문 내용]이 사용자의 질문이나 처한 상황과 실질적인 연관성이 전혀 없는 경우(예: 일상적인 인사, 음식 메뉴 추천, 단순 잡담 등), 논문 내용을 무시하고 논문을 인용하지 마십시오. "
                "이 경우 관련 논문이 없는 것으로 간주하고 정중하게 '고민하신 주제와 직접 매칭되는 학술 자료는 없지만...'으로 시작하며 따뜻하게 상담해 주세요.\n"
                "2. 논문 내용이 연관성이 있다면, 학술적 통찰을 자연스럽게 대화에 녹여 설명하되 딱딱한 요약체가 아닌 부드럽고 따뜻한 상담 톤을 유지하세요.\n"
                "3. 상투적인 위로(\"힘드셨겠네요\", \"힘내세요\")는 피하고, 사용자의 마음에 깊이 공감한 후 그 안의 감정을 정돈해 주는 반영적 태도를 취하세요.\n"
                "4. 해결책을 성급하게 직접 주지 마십시오. 대신 사용자가 스스로 가치와 의미(창조적 가치, 경험적 가치, 태도적 가치)를 깨달을 수 있도록 유도하세요.\n"
                "5. 대화의 마무리에는 사용자가 자신의 상황을 되돌아보고 성찰할 수 있는 구체적이고 깊이 있는 '소크라테스식 열린 질문(역질문)'을 1~2개 던져주세요.\n\n"
                f"[학술 논문 내용]\n{context_text}"
            )
        else:
            system_prompt = (
                "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 자아 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                "[대화 원칙]\n"
                "1. 사용자의 질문/고민과 완벽히 매칭되는 논문을 데이터베이스에서 찾지 못했습니다. 따라서 답변의 서두에 다음과 같이 자연스럽게 이를 안내하십시오: "
                "\"고민하신 내용과 직접적으로 매칭되는 특정 학술 논문은 찾지 못했지만, 의미치료와 심리학적 관점에서 이야기를 나누어보고 싶습니다.\"\n"
                "2. 특정 논문 인용 없이도, 빅터 프랭클의 의미 치료 이론(시련을 가치로 승화하기, 고통 속에서 태도 선택하기) 및 긍정 심리학 지식을 기반으로 깊이 있고 따뜻한 대답을 구성하세요.\n"
                "3. 해결책을 직접 제시하지 말고, 사용자가 스스로 생각하여 내면의 자유와 책임을 인식하도록 소크라테스식 질문을 건네세요.\n"
                "4. 답변 끝에는 성찰을 이끌어낼 수 있는 열린 질문(역질문)을 반드시 1~2개 포함하세요."
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
