# Logos-Log 시스템 아키텍처 설계 (System Architecture Design)

본 문서는 **Logos-Log** 서비스의 전반적인 시스템 아키텍처와 Frontend, Backend, AI 모델 간의 데이터 흐름을 정의합니다.

---

## 1. 시스템 개요 (System Overview)

Logos-Log는 모노레포(Monorepo) 구조 하에서 프론트엔드(Next.js)와 백엔드(FastAPI)가 분리되어 통신하는 구조를 가집니다. AI 모듈은 FastAPI 백엔드 내에 통합되어 비동기적으로 처리되며, 기존에 구축한 DevOps 인프라(Elasticsearch 로깅, CI/CD)와 연계됩니다.

* **Frontend:** Next.js (App Router), Tailwind CSS, Vercel 배포
* **Backend:** FastAPI (Python), 비동기 처리
* **Database:** PostgreSQL (사용자 데이터)
* **Vector DB:** Supabase pgvector (논문 임베딩 데이터)
* **AI Engine:** LangChain, OpenAI API / Claude API
* **DevOps / Infra:** GitHub Actions, Fluentd, Elasticsearch, Docker

---

## 2. 시스템 아키텍처 다이어그램 (Architecture Diagram)

아래는 사용자 요청부터 AI 처리, 로깅까지 이어지는 전체 시스템 아키텍처 다이어그램입니다.

```mermaid
graph TD
    %% User Layer
    User((사용자))
    
    %% Frontend Layer
    subgraph Frontend [Frontend - Vercel 배포]
        NextJS[Next.js App Router]
        UI[채팅/일기 UI]
        Graph[의미 네트워크 시각화]
        NextJS --- UI
        NextJS --- Graph
    end
    
    %% Backend Layer
    subgraph Backend [Backend - FastAPI]
        API[API Gateway / Router]
        Auth[인증/인가 미들웨어]
        RAG[RAG & AI Engine<br/>LangChain]
        API --> Auth
        Auth --> RAG
    end
    
    %% Database Layer
    subgraph Data [Data & AI Layer]
        UserDB[(User DB<br/>PostgreSQL)]
        VectorDB[(Vector DB<br/>Supabase pgvector)]
        LLM((LLM API<br/>OpenAI / Claude))
    end
    
    %% DevOps Layer
    subgraph DevOps [Logging & Monitoring Infra]
        Fluentd[Fluentd]
        ES[(Elasticsearch)]
        Kibana[Kibana]
    end

    %% Data Flow
    User <-->|HTTP / WebSocket| NextJS
    NextJS <-->|REST API / SSE (Streaming)| API
    
    Auth <-->|Read/Write| UserDB
    RAG <-->|Retrieve/Search| VectorDB
    RAG <-->|Prompt & Context| LLM
    
    %% Logging Flow
    API -.->|App Logs| Fluentd
    Fluentd -.->|Forward| ES
    ES -.->|Visualize| Kibana
```

---

## 3. 데이터 흐름 (Data Flow)

### 3.1. 일기 작성 및 심리 분석 흐름
1. **User Action:** 사용자가 프론트엔드(Next.js)에서 일기를 작성 후 제출합니다.
2. **API Request:** 프론트엔드가 백엔드(FastAPI)의 `/api/journal` 엔드포인트로 POST 요청을 보냅니다.
3. **Save Data:** 백엔드는 작성된 일기를 사용자 DB에 일차적으로 저장합니다.
4. **Vector Search:** 백엔드의 RAG 모듈은 일기 텍스트를 임베딩(text-embedding-3)하여 Vector DB(Supabase)에서 가장 유사한 심리학 논문 청크(Chunk)를 검색합니다.
5. **AI Inference:** 검색된 논문 맥락(Context)과 일기 내용을 바탕으로 LLM에 프롬프트를 전송하여 피드백 및 감정 분석 결과를 생성합니다.
6. **Response:** 생성된 분석 결과를 프론트엔드에 응답으로 전달하고, 사용자 화면에 표시합니다.

### 3.2. 소크라테스식 대화 흐름 (Streaming)
1. **User Action:** 사용자가 AI 챗봇에 메시지를 입력합니다.
2. **API Request:** `/api/chat` 엔드포인트로 메시지 전송. 이전 대화 기록(Chat History)을 함께 로드합니다.
3. **Prompt Generation:** RAG 모듈에서 "직접적인 답을 주지 말고 역질문을 던져라"는 시스템 프롬프트와 함께 컨텍스트를 구성합니다.
4. **LLM Streaming:** LLM으로부터 응답을 토큰 단위로 받아오는 즉시(SSE 방식), 프론트엔드로 스트리밍 전송하여 사용자가 대기 시간 없이 타자 치듯 볼 수 있게 합니다.

### 3.3. 아하 모먼트 (의미 네트워크) 추출 흐름
1. **Trigger:** 대화 내용이 특정 기준(예: 사용자의 깊은 성찰, 행동 변화 다짐 등)에 도달하면 백엔드 워커가 백그라운드에서 실행됩니다.
2. **Summarize:** LLM이 대화 흐름을 요약하여 '가치 카드(Value Card)' 텍스트를 생성합니다.
3. **Save Node:** 생성된 카드를 의미 네트워크의 노드 데이터로 사용자 DB에 저장합니다.
4. **Visualize:** 프론트엔드 접속 시 해당 데이터를 불러와 d3.js 또는 유사 라이브러리를 통해 연결망 그래프로 렌더링합니다.

---

## 4. 디렉터리 분리 전략 (Repository Structure)

Monorepo 내에서 다음과 같이 디렉터리를 분리하여 개발을 진행합니다.

```text
Logos-Log/
├── .github/              # 기존 CI/CD 파이프라인
├── frontend/             # Next.js 프론트엔드 코드
│   ├── src/
│   ├── package.json
│   └── ...
├── backend/              # FastAPI 백엔드 코드
│   ├── app/
│   │   ├── api/          # 라우터
│   │   ├── core/         # 설정
│   │   ├── services/     # RAG, AI 비즈니스 로직
│   │   └── models/       # DB 모델
│   ├── requirements.txt
│   └── ...
├── project/docs/         # 프로젝트 산출물 및 문서
└── docker-compose-es.yml # 기존 인프라 설정
```
