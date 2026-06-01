> ⚠️ **본 문서는 생성형 AI(Claude, GPT 등)를 활용하여 작성되었습니다.**

> 🛠️ **구현 현황 노트:** 본 문서는 **초기 기획 초안**입니다. 실제 구현에서 스택이 일부 변경되었습니다 — Vector DB는 **MongoDB Atlas Vector Search**(Supabase 아님), 프론트엔드는 **React + Vite**(Next.js 아님), 임베딩은 **`BAAI/bge-m3` 로컬**(text-embedding-3 아님), LLM은 **gpt-4o-mini**, 인증은 **자체 JWT + bcrypt**입니다. 현재 아키텍처의 정확한 기준은 [architecture.md](./architecture.md)를 참고하세요.

### **1. 프로젝트명**
*   **국문:** 로고스 로그 (Logos Log) - 학술 기반 RAG를 활용한 실존적 의미 탐구 저널링 플랫폼
*   **영문:** Logos Log: An Evidence-based Meaning-Making Journaling Platform using RAG

### **2. 문제 정의 (Problem Statement)**
*   **시대적 배경:** 자동화와 AI의 발전으로 '생존을 위한 노동'이 감소하면서, 개인에게 주어지는 잉여 시간은 폭발적으로 증가하고 있습니다. 이는 역설적으로 삶의 목적을 상실하는 '실존적 공허함(Existential Vacuum)'과 번아웃을 초래할 위험이 큽니다.
*   **기존 서비스의 한계:** 현재의 저널링 앱이나 심리 상담 챗봇은 대부분 단순한 텍스트 저장소에 불과하거나, "힘드셨겠네요" 식의 피상적이고 획일화된 위로를 제공하는 데 그칩니다. 
*   **해결 방안:** 사용자의 일상과 감정을 **긍정 심리학 및 의미 치료(Logotherapy) 등 검증된 학술 논문 데이터**를 기반으로 분석해야 합니다. 이를 통해 일시적인 위안이 아닌, 객관적이고 과학적인 자아 성찰과 삶의 의미 재구성(Meaning-Making)을 돕는 도구가 필요합니다.

### **3. 핵심 기능 3가지 (Core Features)**
1.  **논문 기반 심리 분석 RAG 엔진 (Evidence-Based RAG Analysis)**
    *   사용자가 작성한 일기를 단순 LLM이 아닌, 심리학 논문이 임베딩된 벡터 DB를 거쳐 분석합니다. 
    *   사용자의 감정 상태를 학술적 프레임워크(예: 자기결정성 이론 등)에 맵핑하여 논리적이고 객관적인 피드백을 제공합니다.
2.  **소크라테스식 딥다이브 챗봇 (Socratic Deep-Dive Chat)**
    *   정답이나 위로를 던져주는 대신, 논문에서 추출한 질문 기법을 활용해 사용자 스스로 깨달음을 얻도록 유도하는 다이얼로그 시스템입니다.
    *   대화의 맥락(Context)을 기억하며 점진적으로 깊은 내면의 가치를 끌어냅니다.
3.  **의미 네트워크 아카이브 (Meaning Network Archive)**
    *   사용자가 대화 중 '아하 모먼트(Aha-moment, 깊은 깨달음의 순간)'에 도달했을 때, AI가 해당 문맥을 요약하여 하나의 '가치 카드'로 추출합니다.
    *   이 카드들을 노드(Node)로 연결하여, 사용자의 지적/심리적 성장을 시각화된 그래프 형태로 제공합니다.

### **4. 기술 스택 (Tech Stack)**
*   **AI & Data Pipeline:**
    *   **LLM:** GPT-4o 또는 Claude 3.5 Sonnet (추론 및 대화 생성)
    *   **RAG Framework:** LangChain, LlamaIndex
    *   **Vector DB:** Supabase (pgvector) 또는 Pinecone
    *   **Evaluation:** Ragas (RAG 파이프라인 성능 및 환각 평가)
*   **Backend:** FastAPI (Python) - 비동기 AI 파이프라인 처리
*   **Frontend:** Next.js (App Router), Tailwind CSS, Framer Motion (부드러운 UX 구현)
*   **Deployment:** Vercel (FE), Render/Railway (BE)

---

### **5. 16주 (1학기) 마일스톤 초안**
단순한 웹 개발을 넘어, RAG 시스템의 평가와 최적화 과정이 포함된 엔지니어링 중심의 일정입니다.

#### **Phase 1: 기획 및 데이터 파이프라인 구축 (1~4주차)**
*   **1주차:** 요구사항 정의서 작성 및 시스템 아키텍처 설계 (FE/BE/AI 분리)
*   **2주차:** 긍정 심리학, 의미 치료 관련 논문(PDF 등) 데이터셋 수집 및 전처리 계획 수립
*   **3주차:** 텍스트 청킹(Chunking) 전략 수립 및 임베딩 모델(OpenAI text-embedding-3 등) 테스트
*   **4주차:** Vector DB(Supabase) 구축 및 베이스라인 RAG 검색 모듈(Retriever) 구현

#### **Phase 2: 코어 AI 엔진 및 백엔드 개발 (5~8주차)**
*   **5주차:** 논문 데이터를 활용한 분석용 시스템 프롬프트 엔지니어링 
*   **6주차:** 소크라테스식 역질문 유도를 위한 메모리(Chat History) 모듈 연동
*   **7주차:** FastAPI 기반 백엔드 API 설계 및 AI 로직 통합
*   **8주차:** 중간 점검 - 터미널 환경에서 대화 파이프라인 테스트 및 병목 구간 확인

#### **Phase 3: 프론트엔드 연동 및 MVP 완성 (9~12주차)**
*   **9주차:** Next.js 기반 UI 레이아웃 및 컴포넌트 설계
*   **10주차:** FE-BE API 연동 (일기 작성 및 실시간 채팅 인터페이스 연동)
*   **11주차:** 의미 네트워크(아하 모먼트 시각화) 컴포넌트 및 대시보드 구현
*   **12주차:** MVP 버전 배포 및 내부 테스트 (핵심 기능 정상 작동 여부 검증)

#### **Phase 4: RAG 최적화 및 시스템 고도화 (13~16주차)**
*   **13주차:** Ragas 등을 활용한 검색 정확도(Retrieval Accuracy) 및 답변 품질 정량 평가
*   **14주차:** 하이브리드 검색(Keyword + Vector) 도입 또는 라우팅 전략을 통한 RAG 성능 최적화
*   **15주차:** UI/UX 폴리싱(애니메이션 추가, 로딩 속도 개선) 및 사용성 테스트 피드백 반영
*   **16주차:** 최종 버그 픽스, 아키텍처 다이어그램 포함 최종 보고서/포트폴리오 작성 및 프로젝트 마감