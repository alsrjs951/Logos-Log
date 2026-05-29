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

    async def _expand_query(self, query: str) -> str:
        # 한글이 아예 없으면 번역/확장 없이 그대로 반환
        import re
        if not re.search('[ㄱ-ㅎㅏ-ㅣ가-힣]', query):
            return query
            
        try:
            system_prompt = (
                "You are an academic search query optimization assistant.\n"
                "Translate and expand the user's psychological concern or question in Korean into a natural English search sentence followed by key academic search terms (synonyms, theories, or related terms).\n"
                "Output format: 'Translated sentence. Keywords: term1, term2, term3, ...'\n"
                "Output ONLY the result in English (no explanation, no extra markdown, no quotes).\n"
                "Examples:\n"
                "Input: '오늘 회사에서 너무 무기력하고 번아웃이 왔어'\n"
                "Output: 'I feel helpless and burned out at work today. Keywords: occupational burnout, exhaustion, coping strategies, logotherapy, employee stress'\n"
                "Input: '인간의 기본 욕구가 무엇인가요?'\n"
                "Output: 'What are the basic psychological needs of humans? Keywords: basic psychological needs, self-determination theory, autonomy, competence, relatedness'"
            )
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ]
            
            response = await self.llm.ainvoke(messages)
            expanded = response.content.strip().replace('"', '').replace("'", "")
            print(f"RAG Optimization: Original: '{query}' -> Expanded English Search Query: '{expanded}'", flush=True)
            return expanded
        except Exception as e:
            print(f"Error in query expansion: {e}", flush=True)
            return query

    async def get_streaming_response(self, query: str, history: list = None, is_journal: bool = False, journal_id: str = None) -> AsyncGenerator[str, None]:
        if history is None:
            history = []
            
        # 1단계: 쿼리 영어 번역 및 학술 키워드 확장 (Query Expansion)
        yield f"data: {json.dumps({'type': 'status', 'data': 'translating'}, ensure_ascii=False)}\n\n"
        english_query = await self._expand_query(query)
            
        # 2단계: 질문 임베딩 및 하이브리드 검색
        yield f"data: {json.dumps({'type': 'status', 'data': 'searching'}, ensure_ascii=False)}\n\n"
        query_embedding = self.embeddings.embed_query(english_query)
        
        # Supabase에서 하이브리드(Vector + FTS) 관련 문서 검색 (임계치 0.50 적용 및 8개 후보 수집)
        response = self.supabase.rpc("match_documents_hybrid", {
            "query_embedding": query_embedding,
            "query_text": english_query,
            "match_threshold": 0.50,
            "match_count": 8
        }).execute()
        
        results = response.data or []
        
        # 1차 후보군 파싱 (최소 하이브리드 점수 0.30 이상인 실질 후보군만 필터링)
        candidates = []
        for res in results:
            sim = res.get("similarity", 0)
            if sim >= 0.30:
                candidates.append({
                    "id": res.get("id"),
                    "content": res.get("content"),
                    "metadata": res.get("metadata") or {},
                    "similarity": sim
                })

        # LLM Re-ranking 적용
        reranked_results = await self._rerank_documents(query, candidates)

        sources = []
        context_text = ""
        
        for res in reranked_results:
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

        # 3단계: RAG 답변 생성 돌입
        yield f"data: {json.dumps({'type': 'status', 'data': 'generating'}, ensure_ascii=False)}\n\n"

        # 3. 소크라테스식 대화법 & 의미치료 기반 시스템 프롬프트 생성
        if is_journal:
            # 일기 분석 전용 프롬프트
            if results:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 일기(저널)를 분석하고 깊이 있는 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 사용자가 작성한 일기 내용과 감정을 따뜻하고 분석적인 시선으로 살펴보고 공감해주세요. 피상적인 위로는 삼가고, 사용자가 털어놓은 마음에 귀를 기울이고 있음을 느끼게 하십시오.\n"
                    "2. 제공된 [학술 논문 내용]의 학술적/심리학적 통찰을 자연스럽게 녹여 일기의 고민을 새로운 각도에서 볼 수 있도록 지원하세요. 절대 딱딱하게 논문을 요약하지 말고 스며들듯이 전달하세요.\n"
                    "3. 일기 성찰이 성공적으로 분석되고 논문 정보가 포함되었으므로, '논문 자료를 찾지 못했다' 또는 '매칭되는 논문이 없다'는 뉘앙스의 부정적인 안내 문구를 절대로 답변에 출력하지 마십시오.\n"
                    "4. 사용자의 일기 속 고민을 의미치료 관점(예: 태도의 가치, 시련 속 의미 찾기, 선택과 책임)으로 전환할 수 있는 가능성을 정중히 제안해 보세요.\n"
                    "5. 답변 마무리에는 일기 내용을 토대로 사용자가 스스로 내면의 답을 찾아가도록 돕는 '소크라테스식 열린 역질문'을 1~2개 반드시 던져 대화를 이어가십시오.\n\n"
                    f"[학술 논문 내용]\n{context_text}"
                )
            else:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 일기(저널)를 분석하고 깊이 있는 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 사용자가 쓴 일기의 주제와 관련하여 직접 매칭되는 특정 논문 자료를 찾지 못했습니다. 답변의 서두에 다음과 같이 자연스럽게 안내하십시오: "
                    "\"작성하신 일기와 밀접하게 부합하는 논문 자료는 찾지 못했지만, 의미치료와 심리학적 원칙을 바탕으로 마음에 대해 깊은 대화를 나누고 싶습니다.\"\n"
                    "2. 논문 직접 인용 없이도, 빅터 프랭클의 의미 치료 이론 및 긍정 심리학 지식을 기반으로 깊이 있고 따뜻한 대답과 공감을 구성하십시오.\n"
                    "3. 답변의 마지막에는 사용자가 자신의 상황을 찬찬히 되돌아볼 수 있게 돕는 열린 소크라테스식 역질문을 1~2개 포함하세요."
                )
        else:
            # 일반 챗 대화용 프롬프트
            if results:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 자아 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 제공된 [학술 논문 내용]의 학술적 통찰을 자연스럽게 대화에 녹여 설명하되, 딱딱한 논문 요약이 아닌 따뜻하고 신뢰감 있는 상담 톤을 유지하세요.\n"
                    "2. 답변에 검색된 논문 지식이 성공적으로 포함되었으므로, 절대로 '학술 자료를 찾지 못했다'거나 '직접 매칭되는 논문은 없다'는 부정적인 안내 문구를 출력하지 마십시오. 논문 내용을 아하 모먼트의 핵심 학술 근거로 활용하여 답변하세요.\n"
                    "3. 상투적인 위로(\"힘드셨겠네요\", \"힘내세요\")는 피하고, 사용자의 마음에 깊이 공감한 후 그 안의 감정을 정돈해 주는 반영적 태도를 취하세요.\n"
                    "4. 해결책을 성급하게 직접 주지 마십시오. 대신 사용자가 스스로 가치와 의미(창조적 가치, 경험적 가치, 태도적 가치)를 깨달을 수 있도록 유도하세요.\n"
                    "5. 대화의 마무리에는 사용자가 자신의 상황을 되돌아보고 성찰할 수 있는 구체적이고 깊이 있는 '소크라테스식 열린 질문(역질문)'을 1~2개 던져주세요.\n\n"
                    f"[학술 논문 내용]\n{context_text}"
                )
            else:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 자아 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 사용자의 질문/고민과 완벽히 매칭되는 논문을 데이터베이스에서 찾지 못했습니다. 따라서 답변의 서두는 반드시 다음 안내 문구로 시작하십시오: "
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
        
        # 5. LLM 스트리밍 응답 (한 글자씩 Yield & 누적)
        full_answer = ""
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                full_answer += chunk.content
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"
                
        # 6. 대화 이력 데이터베이스 저장 (journal_id가 전달된 경우에만 수행)
        if journal_id:
            try:
                # 사용자 질문 내용 가공 (일기 분석 시작 요청일 시 마크다운 형태로 변환)
                user_content = query
                if query.startswith("[일기 분석 요청]"):
                    lines = query.split('\n')
                    title = ""
                    emotion = ""
                    body = ""
                    if len(lines) > 1:
                        title = lines[1].replace("제목: ", "").strip()
                    if len(lines) > 2:
                        emotion = lines[2].replace("감정 상태: ", "").strip()
                    if len(lines) > 4:
                        body = "\n".join(lines[4:]).strip()
                    user_content = f"📖 **[일기 분석 시작]**\n\n**제목:** {title}\n**감정:** {emotion}\n\n{body}"

                # 1) 사용자 질문 메시지 저장
                user_msg = {
                    "journal_id": journal_id,
                    "role": "user",
                    "content": user_content,
                    "sources": []
                }
                self.supabase.table("chat_messages").insert(user_msg).execute()

                # 2) AI 답변 메시지 저장
                bot_msg = {
                    "journal_id": journal_id,
                    "role": "bot",
                    "content": full_answer,
                    "sources": sources
                }
                self.supabase.table("chat_messages").insert(bot_msg).execute()
            except Exception as e:
                # 저장 오류 시 전체 대화 흐름이 실패하지 않도록 로깅만 수행
                print(f"Error saving chat message to database: {e}", flush=True)

        # 7. 스트리밍 종료 알림
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    def get_chat_history(self, journal_id: str) -> list:
        """
        특정 일기 ID에 종속된 대화 이력을 생성 시간 순으로 조회합니다.
        """
        try:
            response = self.supabase.table("chat_messages")\
                .select("*")\
                .eq("journal_id", journal_id)\
                .order("created_at", desc=False)\
                .execute()
            return response.data or []
        except Exception as e:
            print(f"Error fetching chat history from database: {e}", flush=True)
            return []

    async def _rerank_documents(self, query: str, documents: list) -> list:
        """
        LLM(GPT-3.5-turbo)을 사용하여 검색된 후보 문서들과 사용자 질문의 문맥적 일치도를 평가하고,
        가장 관련성이 높은 상위 3개의 문서만을 선별하여 정렬된 순서대로 반환합니다.
        """
        if not documents:
            return []

        try:
            # 평가용 프롬프트 작성
            docs_text = ""
            for idx, doc in enumerate(documents):
                docs_text += f"\n[Document {idx}]\nContent: {doc.get('content')}\n"

            system_prompt = (
                "You are an academic document retrieval re-ranking assistant.\n"
                "Your task is to evaluate the relevance of the retrieved academic paper chunks to the user's query.\n"
                "Select up to 3 chunks that are most relevant and directly helpful in addressing the user's psychological concern or question.\n"
                "Output ONLY the indices of the selected chunks in order of relevance, separated by a single space (e.g., '2 0 4').\n"
                "If less than 3 chunks are relevant, output only the indices of those relevant chunks (e.g., '1 3').\n"
                "If none of the chunks are relevant, output 'NONE'.\n"
                "Do NOT provide any explanations, code, markdown, or extra text."
            )

            user_prompt = f"User Query: {query}\n\nRetrieved Academic Chunks:{docs_text}"

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self.llm.ainvoke(messages)
            result = response.content.strip().upper()
            print(f"RAG Re-ranking Result: '{result}' for Query: '{query}'", flush=True)

            if result == "NONE":
                return []

            import re
            indices = [int(idx) for idx in re.findall(r'\d+', result) if 0 <= int(idx) < len(documents)]
            
            # 중복 제거 및 상위 3개 선별
            seen = set()
            unique_indices = []
            for idx in indices:
                if idx not in seen:
                    seen.add(idx)
                    unique_indices.append(idx)
            
            # 재정렬된 문서 리스트 생성
            reranked_docs = [documents[idx] for idx in unique_indices[:3]]
            return reranked_docs

        except Exception as e:
            print(f"Error during RAG re-ranking: {e}", flush=True)
            # 재정렬 오류 시 안전하게 상위 3개 기본 리턴
            return documents[:3]
