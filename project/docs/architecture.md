# Logos-Log 시스템 아키텍처 설계 (System Architecture Design)

본 문서는 **Logos-Log** 서비스의 전반적인 시스템 아키텍처와 Frontend, Backend, AI 모델 간의 데이터 흐름을 정의합니다.

> 📌 본 문서는 **실제 구현 기준**으로 갱신되었습니다. 초기 기획 단계의 스택(Supabase/Next.js/PostgreSQL)에서 구현 과정에 변경된 사항이 반영되어 있습니다. 기획 원안은 [PRD.md](./PRD.md)·[plan.md](./plan.md)를 참고하세요.

---

## 1. 시스템 개요 (System Overview)

Logos-Log는 모노레포(Monorepo) 구조 하에서 프론트엔드(React + Vite)와 백엔드(FastAPI)가 분리되어 통신하는 구조를 가집니다. AI 모듈은 FastAPI 백엔드 내에 통합되어 비동기적으로 처리되며, 기존에 구축한 DevOps 인프라(Elasticsearch 로깅, CI/CD)와 연계됩니다.

* **Frontend:** React 19 + Vite (plain CSS, lucide-react, react-markdown), Vercel 배포
* **Backend:** FastAPI (Python), 비동기 처리, SSE 스트리밍
* **인증:** 자체 JWT(PyJWT) + bcrypt — MongoDB `users` 컬렉션
* **Database & Vector DB:** MongoDB Atlas 단일 스토어 — 앱 데이터(`users`/`journals`/`value_cards`/`chat_messages`)와 논문 임베딩(`documents`, Atlas Vector Search)을 함께 보관
* **AI Engine:** LangChain — 응답 생성 `gpt-4o-mini`(OpenAI), 임베딩 `BAAI/bge-m3`(로컬, 1024차원)
* **안전 레이어:** 자해/자살 위기 신호 감지 → 상담 핫라인 안내 + 안전 응답
* **DevOps / Infra:** GitHub Actions(CI/CD·DORA 메트릭), Fluentd, Elasticsearch, Docker

---

## 2. 시스템 아키텍처 다이어그램 (Architecture Diagram)

아래는 사용자 요청부터 AI 처리, 로깅까지 이어지는 전체 시스템 아키텍처 다이어그램입니다.

```mermaid
graph TD
    %% User Layer
    User((사용자))

    %% Frontend Layer
    subgraph Frontend [Frontend - React + Vite · Vercel 배포]
        React[React 19 SPA]
        UI[채팅/일기 UI]
        Graph[의미 네트워크 시각화]
        React --- UI
        React --- Graph
    end

    %% Backend Layer
    subgraph Backend [Backend - FastAPI]
        API[API Router]
        Auth[JWT 인증 의존성]
        Crisis[위기 감지 안전 레이어]
        RAG[RAG & AI Engine<br/>LangChain]
        API --> Auth
        Auth --> Crisis
        Crisis --> RAG
    end

    %% Database Layer
    subgraph Data [Data & AI Layer]
        Mongo[(MongoDB Atlas<br/>앱 데이터 + Vector Search)]
        Embed[로컬 임베딩<br/>BAAI/bge-m3]
        LLM((LLM API<br/>OpenAI gpt-4o-mini))
    end

    %% DevOps Layer
    subgraph DevOps [Logging & Monitoring Infra]
        Fluentd[Fluentd]
        ES[(Elasticsearch)]
        Kibana[Kibana]
    end

    %% Data Flow
    User <-->|HTTPS| React
    React <-->|REST API / SSE (Streaming)| API

    Auth <-->|Read/Write| Mongo
    RAG <-->|"$vectorSearch (Top-K)"| Mongo
    RAG -->|쿼리 임베딩| Embed
    RAG <-->|Prompt & Context| LLM

    %% Logging Flow
    API -.->|App Logs| Fluentd
    Fluentd -.->|Forward| ES
    ES -.->|Visualize| Kibana
```

---

## 3. 데이터 흐름 (Data Flow)

모든 API는 `/api` 프리픽스를 가지며, 인증이 필요한 엔드포인트는 `Authorization: Bearer <JWT>` 헤더를 검증합니다.

### 3.1. 일기 작성 및 심리 분석 흐름
1. **User Action:** 사용자가 프론트엔드(React)에서 일기를 작성 후 제출합니다.
2. **Save Journal:** `POST /api/journals` 로 일기를 MongoDB `journals` 컬렉션에 저장합니다.
3. **Analysis Request:** 저장된 일기 본문을 쿼리로 하여 `POST /api/chat` (SSE)를 호출합니다(`is_journal=true`, `journal_id` 포함).
4. **Safety Check:** RAG에 앞서 위기 신호(자해/자살)를 우선 감지합니다. 감지 시 RAG를 우회하고 상담 핫라인 안내 + 안전 응답만 스트리밍합니다.
5. **Query Expansion:** 한국어 고민을 영어 학술 검색문 + 키워드로 번역·확장합니다.
6. **Vector Search:** 확장 쿼리를 `BAAI/bge-m3`(로컬)로 임베딩하여 MongoDB Atlas `$vectorSearch`(`documents`, Top-K)에서 유사 논문 청크를 검색합니다.
7. **Re-rank & Translate:** LLM 재랭킹으로 상위 청크를 선별하고, 한국어 번역 + 1줄 인사이트를 병렬 생성합니다.
8. **AI Inference (SSE):** 논문 컨텍스트 + 의미치료 기반 시스템 프롬프트로 `gpt-4o-mini` 응답을 토큰 단위로 스트리밍합니다.
9. **Persist:** 사용자/AI 메시지와 출처(sources)를 `chat_messages` 컬렉션에 저장합니다.

### 3.2. 소크라테스식 대화 흐름 (Streaming)
1. **User Action:** 사용자가 AI 챗봇에 메시지를 입력합니다.
2. **API Request:** `POST /api/chat` 로 메시지를 전송하며, 이전 대화 기록(history)을 함께 보냅니다. 과거 이력은 `GET /api/chat/history/{journal_id}` 로 복원합니다(소유권 검증 포함).
3. **Prompt Generation:** RAG 모듈에서 "직접적인 답을 주지 말고 역질문을 던져라"는 시스템 프롬프트와 컨텍스트, 사용자 가치 프로필을 구성합니다.
4. **LLM Streaming:** LLM 응답을 SSE(`type: status/sources/crisis/chunk/done`)로 즉시 전송하여 사용자가 대기 없이 타자 치듯 볼 수 있게 합니다.

### 3.3. 아하 모먼트 (의미 네트워크) 추출 흐름
1. **Trigger:** 사용자가 대화 중 "가치 카드로 저장하기"를 누르면 `POST /api/value-cards/extract` 가 대화 내역을 분석합니다.
2. **Summarize:** LLM(`gpt-3.5-turbo`)이 대화에서 핵심 가치(keyword)와 1인칭 인사이트(insight)를 추출합니다.
3. **Save Node:** `POST /api/value-cards` 로 카드를 `value_cards` 컬렉션에 저장합니다.
4. **Visualize:** 의미 네트워크 화면에서 `GET /api/value-cards` 로 카드를 불러와 연결망 그래프로 렌더링합니다.

---

## 4. 디렉터리 분리 전략 (Repository Structure)

Monorepo 내에서 다음과 같이 디렉터리를 분리하여 개발을 진행합니다.

```text
Logos-Log/
├── .github/workflows/      # CI/CD 파이프라인, DORA 메트릭
├── frontend/               # React + Vite 프론트엔드
│   ├── src/
│   │   ├── components/      # ChatWindow, JournalEditor, Dashboard, AuthModal 등
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
├── backend/                # FastAPI 백엔드
│   ├── main.py             # 진입점 (CORS, 라우터 등록)
│   ├── db.py               # MongoDB 연결
│   ├── api/                # 라우터: auth · chat · journals · value_cards · deps
│   ├── services/           # rag_service.py (LangChain RAG 파이프라인)
│   ├── models/             # Pydantic 스키마
│   ├── scripts/            # 데이터 수집·전처리·임베딩·업로드 스크립트
│   └── requirements.txt
├── data/                   # raw / processed / embeddings (gitignore)
├── project/docs/           # 프로젝트 산출물 및 문서
└── docker-compose-es.yml   # Elasticsearch 로깅 인프라
```
