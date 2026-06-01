import os
import json
import datetime
from pymongo import MongoClient
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import AsyncGenerator
from models.chat import ChatSource
from db import get_db

class RAGService:
    # 자해/자살 위기 신호 키워드 (공백 제거 후 매칭). 안전을 위해 재현율(Recall)을 우선한다.
    CRISIS_KEYWORDS = [
        "자살", "자해",
        "죽고싶", "죽어버리", "죽어야겠", "죽는게나아", "죽는편이",
        "목숨을끊", "목숨끊", "목숨을버리",
        "생을마감", "생을포기", "삶을포기", "삶을마감",
        "세상을떠나", "세상에서사라지", "세상에서없어지",
        "사라지고싶", "없어지고싶", "사라져버리고싶",
        "살고싶지않", "살기싫", "살아갈이유가없", "살이유가없", "살아갈힘이없", "살아갈자신이없",
        "다끝내고싶", "끝내버리고싶", "다끝내버리",
        "뛰어내리", "목을매", "목매달", "손목을긋", "손목긋", "약을먹고죽", "수면제를먹고",
    ]

    def __init__(self):
        # OpenAI LLM 및 임베딩 로드
        import torch
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": device}
        )
        
        # 스트리밍을 지원하는 LLM 인스턴스 생성
        self.llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.3,
            streaming=True
        )

    async def _expand_query(self, query: str) -> str:
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

    async def _translate_to_korean(self, text: str) -> str:
        """
        영문 학술 논문 문단을 자연스럽고 전문적인 한국어로 번역합니다.
        (이미 한글 텍스트인 경우에는 번역 없이 반환)
        """
        import re
        if not text:
            return ""
        if re.search('[ㄱ-ㅎㅏ-ㅣ가-힣]', text):
            return text
            
        try:
            system_prompt = (
                "You are an expert academic translator specializing in psychology and logotherapy.\n"
                "Translate the following English paper chunk into natural, fluent, and highly professional Korean academic language.\n"
                "Maintain precise psychological terminologies and appropriate academic tone.\n"
                "Output ONLY the translated Korean text without any extra explanation, greetings, or formatting."
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=text)
            ]
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
        except Exception as e:
            print(f"Error translating paper chunk to Korean: {e}", flush=True)
            return text

    async def _translate_and_summarize_paper(self, text: str) -> dict:
        """
        영문 학술 논문 문단을 한국어로 번역하고, 동시에 1줄 요약(insight summary)을 생성합니다.
        결과는 JSON 형식을 따르며 {"content_ko": "번역문", "summary_ko": "1줄 요약문"} 구조를 가집니다.
        """
        import re
        if not text:
            return {"content_ko": "", "summary_ko": ""}
            
        if re.search('[ㄱ-ㅎㅏ-ㅣ가-힣]', text):
            summary = text.split('.')[0].strip() + "."
            if len(summary) > 80:
                summary = summary[:80] + "..."
            return {"content_ko": text, "summary_ko": summary}

        try:
            system_prompt = (
                "You are an expert academic translator and psychologist specializing in logotherapy and positive psychology.\n"
                "Your task is to translate the given English paper chunk into professional Korean AND provide a one-line warm, intuitive Korean insight summary for general users.\n"
                "You MUST output the result as a raw JSON object with the following keys:\n"
                "  - 'content_ko': The precise, academic translation of the paper chunk into natural Korean.\n"
                "  - 'summary_ko': A warm, concise, and intuitive one-line summary in Korean of the key research finding (within 100 characters). This summary will be shown in a popover when users hover on citations, so it should be easy to understand (e.g., '목표를 설정하고 이를 시각화하는 활동이 일상의 성취감과 무력감 개선에 긍정적인 영향을 미친다는 연구 결과입니다.').\n"
                "Output ONLY the JSON object, no explanation, no markdown wrappers."
            )
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=text)
            ]
            
            response = await self.llm.ainvoke(messages, response_format={"type": "json_object"})
            data = json.loads(response.content.strip())
            return {
                "content_ko": data.get("content_ko", "").strip(),
                "summary_ko": data.get("summary_ko", "").strip()
            }
        except Exception as e:
            print(f"Error translating and summarizing paper: {e}", flush=True)
            try:
                translated = await self._translate_to_korean(text)
                summary = translated.split('.')[0].strip() + "."
                if len(summary) > 80:
                    summary = summary[:80] + "..."
                return {"content_ko": translated, "summary_ko": summary}
            except Exception:
                return {"content_ko": text, "summary_ko": text[:80] + "..."}

    def detect_crisis(self, text: str) -> bool:
        """
        사용자 입력에서 자해/자살 등 위기 신호를 감지한다.
        공백을 제거해 '죽 고 싶다'처럼 띄어쓰기로 회피하는 표현까지 포착하며,
        안전을 위해 정밀도(Precision)보다 재현율(Recall)을 우선하는 키워드 필터다.
        """
        import re
        if not text:
            return False
        normalized = re.sub(r"\s+", "", text)
        return any(kw in normalized for kw in self.CRISIS_KEYWORDS)

    def is_casual_query(self, query: str, is_journal: bool) -> bool:
        if is_journal:
            return False
        
        # 1. 공백 제거 후 12자 이하의 짧은 단문은 무조건 캐주얼 쿼리로 분류
        clean_query = query.replace(" ", "").strip()
        if len(clean_query) <= 12:
            return True
            
        # 2. 특수문자/구두점 제거
        import re
        normalized = re.sub(r'[^\w\s]', '', query)
        normalized_clean = normalized.replace(" ", "").strip()
        
        # 3. 일상어 및 질문 오프닝용 스톱워드 목록 (공백이 제거된 상태에서 매칭)
        casual_stop_words = [
            "안녕하세요", "안녕", "하이", "반가워", "반갑네", "반갑습니다", "하이요",
            "고민이있습니다", "고민이있어요", "고민있습니다", "고민있어요", "고민이있어", "고민있어", "고민",
            "이야기", "대화하자", "대화하고", "대화해", "대화", "도와줘", "도와주세요", "도움",
            "질문이있습니다", "질문있습니다", "질문이있어요", "질문있어요", "질문이있어", "질문있어", "질문",
            "제가", "저기", "혹시", "요즘", "있어서요", "있습니다", "있어요", "있어", "바랍니다",
            "누구", "이름", "소개", "자기소개", "너는", "당신은", "뭐해", "뭐하니", "심심",
            "말동무", "상담", "받고", "받고싶어", "해줘", "해줘요", "해주세요", "합니다",
            "궁금", "궁금해서", "궁금해요", "물어볼게", "물어볼것이", "물어볼게있어", "물어볼게있습니다"
        ]
        
        temp = normalized_clean
        for word in casual_stop_words:
            temp = temp.replace(word, "")
            
        # 스톱워드 제거 후 남은 의미 있는 글자 수가 3자 이하인 경우 일상 쿼리로 판정
        if len(temp) <= 3:
            return True
            
        return False

    async def get_streaming_response(self, query: str, history: list = None, is_journal: bool = False, journal_id: str = None, user_id: str = None) -> AsyncGenerator[str, None]:
        if history is None:
            history = []
            
        db = get_db()

        # 0단계: 위기 신호(자해/자살) 우선 감지 — RAG/소크라테스식 질문보다 먼저 처리한다.
        if self.detect_crisis(query):
            yield f"data: {json.dumps({'type': 'status', 'data': 'generating'}, ensure_ascii=False)}\n\n"
            # 프론트엔드가 검증된 전문 상담 핫라인 배너를 노출하도록 신호를 보낸다.
            yield f"data: {json.dumps({'type': 'crisis'}, ensure_ascii=False)}\n\n"

            crisis_system_prompt = (
                "당신은 위기 상황에 처한 사용자를 돕는 따뜻하고 침착한 정신건강 동반자 'Logos-Log'입니다.\n"
                "사용자의 메시지에서 자해 또는 자살과 관련된 신호가 감지되었습니다. 지금은 학술적 분석이나 소크라테스식 역질문을 하는 시간이 아닙니다.\n\n"
                "[반드시 지켜야 할 응답 원칙]\n"
                "1. 사용자의 고통을 가볍게 여기지 말고, 진심 어린 공감으로 지금의 감정을 따뜻하게 인정해 주십시오.\n"
                "2. '당신은 혼자가 아니며, 당신의 안전이 무엇보다 소중하다'는 메시지를 분명하게 전하십시오.\n"
                "3. 지금 즉시 신뢰할 수 있는 전문가의 도움을 받도록 부드럽지만 분명하게 권유하고, 24시간 운영되는 '자살예방 상담전화 1393'으로 연락할 것을 따뜻하게 안내하십시오.\n"
                "4. 자해 방법이나 위험한 행동에 관한 구체적 정보는 어떤 경우에도 절대 언급하지 마십시오.\n"
                "5. 섣부른 해결책 제시나 가치 분석, 논문 인용을 하지 말고, 짧고 진솔하며 인간적인 어조로 3~5문장 이내로 답하십시오.\n"
                "6. 곁에 있어 주겠다는 안정감과 함께, 도움을 요청하는 것이 결코 약함이 아니라 용기 있는 일임을 전하며 마무리하십시오."
            )

            messages = [SystemMessage(content=crisis_system_prompt)]
            for h in history:
                if h.role == "user":
                    messages.append(HumanMessage(content=h.content))
                elif h.role == "bot":
                    messages.append(AIMessage(content=h.content))
            messages.append(HumanMessage(content=query))

            full_answer = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_answer += chunk.content
                    yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"

            if journal_id:
                try:
                    db.chat_messages.insert_one({
                        "journal_id": journal_id,
                        "role": "user",
                        "content": query,
                        "sources": [],
                        "user_id": user_id,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    })
                    db.chat_messages.insert_one({
                        "journal_id": journal_id,
                        "role": "bot",
                        "content": full_answer,
                        "sources": [],
                        "crisis": True,
                        "user_id": user_id,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    print(f"Error saving crisis chat message to database: {e}", flush=True)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 장기 기억: 사용자 가치 프로필 로드
        value_profile = self._get_user_value_profile(user_id)
        
        # 쿼리가 일상적(인사, 단순 오프닝 등)인지 확인
        is_casual = self.is_casual_query(query, is_journal)
        
        if is_casual:
            # RAG 검색 우회: 빈 리스트 및 가이드 생략
            sources = []
            yield f"data: {json.dumps({'type': 'status', 'data': 'generating'}, ensure_ascii=False)}\n\n"
            
            system_prompt = (
                "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 내면 성찰을 돕는 따뜻하고 다정한 카운셀러 AI 'Logos-Log'입니다.\n\n"
                "[대화 원칙]\n"
                "1. 사용자가 구체적인 고민 대신 단순한 인사나 짧은 오프닝 멘트를 건넸습니다. 친절하고 열린 태도로 사용자를 따뜻하게 환대해 주세요.\n"
                "2. 답변에 '논문 자료를 찾지 못했다'거나 '학술 자료가 없다'는 식의 투박하거나 부정적인 시스템 안내 문구를 절대로 출력하지 마십시오. 자연스럽고 일상적인 대화 톤으로 응답하십시오.\n"
                "3. 상투적인 리액션을 넘어, 사용자가 오늘 하루 느낀 구체적인 감정이나 직면하고 있는 마음속 고민을 편안하게 털어놓을 수 있도록 다정하게 유도하십시오.\n"
                "4. 답변의 마무리에는 사용자가 자신의 마음을 돌아보거나 오늘의 이야기를 구체적으로 시작할 수 있도록 돕는 따뜻하고 열린 질문을 1~2개 건네주십시오.\n\n"
                f"{value_profile}"
            )
            
            messages = [SystemMessage(content=system_prompt)]
            for h in history:
                if h.role == "user":
                    messages.append(HumanMessage(content=h.content))
                elif h.role == "bot":
                    messages.append(AIMessage(content=h.content))
            messages.append(HumanMessage(content=query))
            
            # 소스 데이터 전송 (RAG 우회이므로 빈 배열 전달)
            yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"
            
            full_answer = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_answer += chunk.content
                    yield f"data: {json.dumps({'type': 'chunk', 'data': chunk.content}, ensure_ascii=False)}\n\n"
            
            if journal_id:
                try:
                    user_msg = {
                        "journal_id": journal_id,
                        "role": "user",
                        "content": query,
                        "sources": [],
                        "user_id": user_id,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    }
                    db.chat_messages.insert_one(user_msg)
                    
                    bot_msg = {
                        "journal_id": journal_id,
                        "role": "bot",
                        "content": full_answer,
                        "sources": sources,
                        "user_id": user_id,
                        "created_at": datetime.datetime.utcnow().isoformat()
                    }
                    db.chat_messages.insert_one(bot_msg)
                except Exception as e:
                    print(f"Error saving chat message to database: {e}", flush=True)
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
            
        # 1단계: 쿼리 영어 번역 및 학술 키워드 확장 (Query Expansion)
        yield f"data: {json.dumps({'type': 'status', 'data': 'translating'}, ensure_ascii=False)}\n\n"
        english_query = await self._expand_query(query)
            
        # 2단계: 질문 임베딩 및 하이브리드 검색
        yield f"data: {json.dumps({'type': 'status', 'data': 'searching'}, ensure_ascii=False)}\n\n"
        query_embedding = self.embeddings.embed_query(english_query)
        
        # MongoDB Atlas Vector Search Pipeline 실행
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 50,
                    "limit": 8
                }
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1,
                    "similarity": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        
        try:
            results = list(db.documents.aggregate(pipeline))
        except Exception as e:
            print(f"Error during MongoDB Vector Search: {e}. Falling back to empty search.", flush=True)
            results = []
            
        # 1차 후보군 파싱 (유사도 점수 0.30 이상인 후보 필터링)
        candidates = []
        for res in results:
            sim = res.get("similarity", 0)
            if sim >= 0.30:
                candidates.append({
                    "id": str(res.get("_id")),
                    "content": res.get("content"),
                    "metadata": res.get("metadata") or {},
                    "similarity": sim
                })

        # LLM Re-ranking 적용
        if len(candidates) <= 3:
            reranked_results = candidates
            print(f"RAG Optimization: Candidates count is {len(candidates)} (<= 3). Skipping LLM re-ranking.", flush=True)
        else:
            reranked_results = await self._rerank_documents(query, candidates)

        # 최종 선별된 문서들에 대해 병렬 한국어 번역 및 요약 수행
        import asyncio
        yield f"data: {json.dumps({'type': 'status', 'data': 'translating_sources'}, ensure_ascii=False)}\n\n"
        
        translation_tasks = [self._translate_and_summarize_paper(res.get("content")) for res in reranked_results]
        translated_results = await asyncio.gather(*translation_tasks)

        sources = []
        context_text = ""
        
        for idx, res in enumerate(reranked_results):
            meta = res.get("metadata", {})
            author = meta.get("author", "Unknown")
            year = meta.get("year", "")
            trans_res = translated_results[idx]
            
            # 원문, 번역본, 그리고 1줄 요약본을 모두 프론트엔드로 전달
            sources.append({
                "id": res.get("id"),
                "content": res.get("content"),        # 영어 원문
                "content_ko": trans_res.get("content_ko"), # 한국어 번역본
                "summary_ko": trans_res.get("summary_ko"), # 한국어 1줄 요약본
                "author": author,
                "year": year,
                "category": meta.get("category", ""),
                "similarity": res.get("similarity", 0)
            })
            context_text += f"\n- [논문 {idx+1}] 저자: {author}, 연도: {year} | 내용: {res.get('content')}"

        # 3단계: RAG 답변 생성 돌입
        yield f"data: {json.dumps({'type': 'status', 'data': 'generating'}, ensure_ascii=False)}\n\n"

        # 소크라테스식 대화법 & 의미치료 기반 시스템 프롬프트 생성
        if is_journal:
            if results:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 일기(저널)를 분석하고 깊이 있는 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 사용자가 작성한 일기 내용과 감정을 따뜻하고 분석적인 시선으로 살펴보고 공감해주세요. 피상적인 위로는 삼가고, 사용자가 털어놓은 마음에 귀를 기울이고 있음을 느끼게 하십시오.\n"
                    "2. 제공된 [학술 논문 내용]의 학술적/심리학적 통찰을 자연스럽게 녹여 일기의 고민을 새로운 각도에서 볼 수 있도록 지원하세요. 절대 딱딱하게 논문을 요약하지 말고 스며들듯이 전달하세요.\n"
                    "3. 일기 성찰이 성공적으로 분석되고 논문 정보가 포함되었으므로, '논문 자료를 찾지 못했다' 또는 '매칭되는 논문이 없다'는 뉘앙스의 부정적인 안내 문구를 절대로 답변에 출력하지 마십시오.\n"
                    "4. 사용자의 일기 속 고민을 의미치료 관점(예: 태도의 가치, 시련 속 의미 찾기, 선택과 책임)으로 전환할 수 있는 가능성을 정중히 제안해 보세요.\n"
                    "5. 답변 마무리에는 일기 내용을 토대로 사용자가 스스로 내면의 답을 찾아가도록 돕는 '소크라테스식 열린 역질문'을 1~2개 반드시 던져 대화를 이어가십시오.\n"
                    "6. [학술 논문 내용]에 기재된 특정 논문의 학술 근거나 구절을 활용하는 서술문 끝에는 반드시 괄호 형식의 인라인 마크다운 링크로 출처를 추가하십시오 (예: `[1](#source-1)` 또는 `[2](#source-2)`). 인덱스 번호는 `[논문 N]`의 번호 N과 정확히 매칭되도록 하십시오.\n"
                    "7. 답변 본문 구성 시 반드시 [실증적 행동 연계(Evidence-to-Action)] 구조를 논리 흐름의 핵심 뼈대로 삼으십시오. 사용자가 일기 속 고민 상황에서 새로운 선택을 내렸을 때의 변화를 연구 결과와 매핑하여 체감하도록 하는 것이 핵심입니다:\n"
                    "   - **구체적 서술 방식**:\n"
                    "     * 1단계: '[논문 N]에 따르면 [이러한 연구 결과/학술적 사실]이 밝혀져 있습니다'와 같이 학술적 근거를 짚어줍니다.\n"
                    "     * 2단계: '이 연구 결과에 비추어 볼 때, 오늘 쓰신 일기 속의 [구체적인 고민이나 행동 부분]은 바로 이 연구가 말하는 핵심 지점과 연결됩니다'라고 일기 내용과 연구 결과를 직접 1:1로 매핑해 줍니다.\n"
                    "     * 3단계: '따라서 이 연구 결과를 바탕으로 만약 일상에서 [이러한 대안 행동이나 태도적 선택]을 해보신다면,'\n"
                    "     * 4단계: '[이러이러한 구체적이고 긍정적인 정서적/실존적 결과]가 일어날 수 있을 것입니다'라고 앞으로의 가능성과 기대를 인과적으로 제안하십시오.\n"
                    "   - **서술 템플릿 준수**:\n"
                    "     반드시 답변의 흐름 속에서 '[연구 결과]가 있기 때문에, 일기의 [이 부분]에서 [이러한 선택]을 했을 때 [이러할 수 있다]'는 명확한 논리 구조(근거 -> 일기 상황 매핑 -> 선택 -> 예상되는 효과)가 사용자에게 직관적으로 와닿도록 한국어 문장을 정교하게 직조하십시오.\n\n"
                    f"{value_profile}"
                    f"[학술 논문 내용]\n{context_text}"
                )
            else:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 일기(저널)를 분석하고 깊이 있는 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 사용자가 쓴 일기의 주제와 관련하여 직접 매칭되는 특정 논문 자료를 찾지 못했습니다. 답변의 서두에 다음과 같이 자연스럽게 안내하십시오: "
                    "\"작성하신 일기와 밀접하게 부합하는 논문 자료는 찾지 못했지만, 의미치료와 심리학적 원칙을 바탕으로 마음에 대해 깊은 대화를 나누고 싶습니다.\"\n"
                    "2. 논문 직접 인용 없이도, 빅터 프랭클의 의미 치료 이론 및 긍정 심리학 지식을 기반으로 깊이 있고 따뜻한 대답과 공감을 구성하십시오.\n"
                    "3. 답변의 마지막에는 사용자가 자신의 상황을 찬찬히 되돌아볼 수 있게 돕는 열린 소크라테스식 역질문을 1~2개 포함하세요.\n\n"
                    f"{value_profile}"
                )
        else:
            if results:
                system_prompt = (
                    "당신은 의미치료(Logotherapy) 및 긍정 심리학을 기반으로 사용자의 자아 성찰을 돕는 전문 카운셀러 AI 'Logos-Log'입니다.\n\n"
                    "[대화 원칙]\n"
                    "1. 제공된 [학술 논문 내용]의 학술적 통찰을 자연스럽게 대화에 녹여 설명하되, 딱딱한 논문 요약이 아닌 따뜻하고 신뢰감 있는 상담 톤을 유지하세요.\n"
                    "2. 답변에 검색된 논문 지식이 성공적으로 포함되었으므로, 절대로 '학술 자료를 찾지 못했다'거나 '직접 매칭되는 논문은 없다'는 부정적인 안내 문구를 출력하지 마십시오. 논문 내용을 아하 모먼트의 핵심 학술 근거로 활용하여 답변하세요.\n"
                    "3. 상투적인 위로(\"힘드셨겠네요\", \"힘내세요\")는 피하고, 사용자의 마음에 깊이 공감한 후 그 안의 감정을 정돈해 주는 반영적 태도를 취하세요.\n"
                    "4. 해결책을 성급하게 직접 주지 마십시오. 대신 사용자가 스스로 가치와 의미(창조적 가치, 경험적 가치, 태도적 가치)를 깨달을 수 있도록 유도하세요.\n"
                    "5. 대화의 마무리에는 사용자가 자신의 상황을 되돌아보고 성찰할 수 있는 구체적이고 깊이 있는 '소크라테스식 열린 질문(역질문)'을 1~2개 던져주세요.\n"
                    "6. [학술 논문 내용]에 기재된 특정 논문의 학술 근거나 구절을 활용하는 서술문 끝에는 반드시 괄호 형식의 인라인 마크다운 링크로 출처를 추가하십시오 (예: `[1](#source-1)` 또는 `[2](#source-2)`). 인덱스 번호는 `[논문 N]`의 번호 N과 정확히 매칭되도록 하십시오.\n"
                    "7. 답변 본문 구성 시 반드시 [실증적 행동 연계(Evidence-to-Action)] 구조를 논리 흐름의 핵심 뼈대로 삼으십시오. 사용자가 고민 상황에서 새로운 선택을 내렸을 때의 변화를 연구 결과와 매핑하여 체감하도록 하는 것이 핵심입니다:\n"
                    "   - **구체적 서술 방식**:\n"
                    "     * 1단계: '[논문 N]에 따르면 [이러한 연구 결과/학술적 사실]이 밝혀져 있습니다'와 같이 학술적 근거를 짚어줍니다.\n"
                    "     * 2단계: '이 연구 결과에 비추어 볼 때, 고민하고 계신 [구체적인 생각이나 상황 부분]은 바로 이 연구가 말하는 핵심 지점과 연결됩니다'라고 사용자의 고민 맥락과 연구 결과를 직접 1:1로 매핑해 줍니다.\n"
                    "     * 3단계: '따라서 이 연구 결과를 바탕으로 만약 일상에서 [이러한 대안 행동이나 태도적 선택]을 해보신다면,'\n"
                    "     * 4단계: '[이러이러한 구체적이고 긍정적인 정서적/실존적 결과]가 일어날 수 있을 것입니다'라고 앞으로의 가능성과 기대를 인과적으로 제안하십시오.\n"
                    "   - **서술 템플릿 준수**:\n"
                    "     반드시 답변의 흐름 속에서 '[연구 결과]가 있기 때문에, 고민하고 계신 [이 부분]에서 [이러한 선택]을 했을 때 [이러할 수 있다]'는 명확한 논리 구조(근거 -> 고민 상황 매핑 -> 선택 -> 예상되는 효과)가 사용자에게 직관적으로 와닿도록 한국어 문장을 정교하게 직조하십시오.\n\n"
                    f"{value_profile}"
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
                    "4. 답변 끝에는 성찰을 이끌어낼 수 있는 열린 질문(역질문)을 반드시 1~2개 포함하세요.\n\n"
                    f"{value_profile}"
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
        
        # 4. 소스(출처) 데이터를 첫 번째 이벤트로 전송
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
                    "sources": [],
                    "user_id": user_id,
                    "created_at": datetime.datetime.utcnow().isoformat()
                }
                db.chat_messages.insert_one(user_msg)

                # 2) AI 답변 메시지 저장
                bot_msg = {
                    "journal_id": journal_id,
                    "role": "bot",
                    "content": full_answer,
                    "sources": sources,
                    "user_id": user_id,
                    "created_at": datetime.datetime.utcnow().isoformat()
                }
                db.chat_messages.insert_one(bot_msg)
            except Exception as e:
                print(f"Error saving chat message to database: {e}", flush=True)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    def get_chat_history(self, journal_id: str) -> list:
        """
        특정 일기 ID에 종속된 대화 이력을 생성 시간 순으로 조회합니다.
        """
        db = get_db()
        try:
            cursor = db.chat_messages.find({"journal_id": journal_id}).sort("created_at", 1)
            return list(cursor)
        except Exception as e:
            print(f"Error fetching chat history from database: {e}", flush=True)
            return []

    async def _rerank_documents(self, query: str, documents: list) -> list:
        if not documents:
            return []

        try:
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
            
            seen = set()
            unique_indices = []
            for idx in indices:
                if idx not in seen:
                    seen.add(idx)
                    unique_indices.append(idx)
            
            reranked_docs = [documents[idx] for idx in unique_indices[:3]]
            return reranked_docs

        except Exception as e:
            print(f"Error during RAG re-ranking: {e}", flush=True)
            return documents[:3]

    def _get_user_value_profile(self, user_id: str = None) -> str:
        if not user_id:
            return ""
        db = get_db()
        try:
            cursor = db.value_cards.find(
                {"user_id": user_id},
                {"keyword": 1, "insight": 1}
            ).sort("created_at", -1).limit(5)
            
            cards = list(cursor)
            if not cards:
                return ""
                
            profile_text = "\n[사용자가 과거 성찰을 통해 깨달아 저장한 핵심 가치 목록]\n"
            for card in cards:
                keyword = card.get("keyword", "").strip()
                insight = card.get("insight", "").strip()
                if keyword and insight:
                    profile_text += f"- 핵심 가치: **{keyword}** | 인사이트: \"{insight}\"\n"
            profile_text += "\n[행동 지침] 대화 시 사용자의 과거 가치 목록을 은연중에 상기시키거나, 오늘의 고민과 자연스럽게 결합하여 1인칭 반영 및 질문을 전개하십시오. 단, 과거 가치를 부자연스럽게 나열하지 말고 대화의 흐름 속에 자연스럽게 스며들도록 인용하십시오.\n"
            return profile_text
        except Exception as e:
            print(f"Error fetching user value profile: {e}", flush=True)
            return ""
