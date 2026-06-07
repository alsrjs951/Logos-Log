> ⚠️ **본 문서는 생성형 AI(Claude Opus 4.7)를 활용하여 작성되었습니다.**

# 📋 Product Requirements Document (PRD)
## Logos Log — 학술 기반 RAG 의미 탐구 저널링 플랫폼

| 항목 | 내용 |
|---|---|
| **문서 버전** | v1.0 |
| **작성일** | 2026-05-04 |
| **작성자** | Product Management Team |
| **상태** | Draft for Engineering Kickoff |
| **관련 문서** | [plan.md](./plan.md) |

---

> ## 🛠️ 구현 현황 노트 (Implementation Note)
> 본 PRD는 **2026-05-04 엔지니어링 킥오프 시점의 계획안**입니다. 이후 실제 구현 과정에서 기술 스택이 아래와 같이 변경되었습니다. 현재 코드 기준의 사실은 이 표를 따릅니다.
>
> | 항목 | PRD 계획 | 실제 구현 |
> |---|---|---|
> | Vector DB | Supabase pgvector | **MongoDB Atlas Vector Search** (`$vectorSearch`) |
> | 사용자 인증 (M1) | Supabase Auth (소셜 로그인) | **자체 JWT + bcrypt** (이메일/비밀번호) |
> | 프론트엔드 | Next.js (App Router) + Tailwind | **React 19 + Vite** (plain CSS, lucide-react) |
> | 임베딩 모델 (M3) | `text-embedding-3-large` | **`BAAI/bge-m3`** (로컬, 1024차원) |
> | LLM | GPT-4o / Claude | **GPT-4o-mini** (응답), GPT-3.5 Turbo (가치 카드 추출) |
> | 위기 감지 | (계획) | **구현됨** — 키워드 기반 감지 + 상담 핫라인(1393) 배너 + 안전 응답 |
> | 일기 본문 암호화 (M10) | AES-256 at-rest | **구현됨** — AES-256-GCM (일기·대화·가치카드 본문, `services/encryption.py`) |
>
> **아직 미구현(향후 과제):** PII 마스킹, Row-Level Security. (하이브리드 검색 S2는 평가에서 효과 없어 미채택 — 벡터 단독 유지. 상세: rag_evaluation_plan.md §5.2)

---

## 1. Product Overview (제품 개요)

### 1.1 Elevator Pitch
> **Logos Log는 사용자의 일기를 검증된 심리학·의미치료(Logotherapy) 논문으로 분석하고, 소크라테스식 역질문을 통해 사용자가 스스로 '삶의 의미(Logos)'를 발견하도록 돕는 학술 기반 RAG 저널링 AI 플랫폼이다.** 단순 위로가 아닌, 데이터에 기반한 자기 성찰의 도구를 제공한다.

### 1.2 Target Audience (Core Personas)

#### 🧑‍💻 Persona 1: "번아웃 시니어 개발자, 박지훈(34)"
- **상황:** 7년 차 백엔드 엔지니어. 승진과 연봉은 올랐지만 "내가 왜 이걸 하고 있지?"라는 공허함에 시달림.
- **고민(Pain):** 친구나 상담사에게 털어놓기엔 사치 같고, 기존 명상앱·저널앱은 며칠 쓰다 그만둠. ChatGPT는 너무 표면적인 답을 줌.
- **니즈(Needs):** 논리적이고 객관적인 자기 분석. "왜 공허한지"에 대한 **근거 기반(evidence-based) 진단**.

#### 🎓 Persona 2: "진로 고민 대학원생, 이수민(26)"
- **상황:** 석사 졸업을 앞두고 박사 진학 vs 취업 사이에서 결정 장애.
- **고민(Pain):** 주변의 조언은 다 다르고, 결국 "네가 좋아하는 거 해"라는 말로 끝남.
- **니즈(Needs):** 자신의 가치관을 체계적으로 파악할 수 있는 **구조화된 사고 도구**와 그 흐름의 시각화.

#### 🏃 Persona 3: "FIRE 달성 후 무기력감의 30대, 김유나(38)"
- **상황:** 경제적 자유를 달성했으나 "다음 목표"를 찾지 못해 무기력.
- **니즈(Needs):** 잉여 시간을 의미 있게 재정의할 수 있는 **자기 발견 프로세스**.

### 1.3 Value Proposition (3가지 핵심 가치)
1. **🎯 Evidence-based Insight** — 검증된 학술 논문(긍정 심리학·Logotherapy·자기결정성 이론)에 근거한 객관적 피드백.
2. **🧠 Socratic Self-Discovery** — 정답을 주는 AI가 아닌, 질문하는 AI를 통해 사용자 스스로 깨달음에 도달.
3. **🌐 Visualized Meaning Growth** — 흩어진 깨달음을 '가치 카드' 노드로 연결하여, 자아 성장 과정을 그래프로 시각화.

---

## 2. Problem & Solution (문제와 해결책)

### 2.1 User Pain Points (PM 관점의 구체적 전환)

| # | Pain Point | 기존 시장의 한계 |
|---|---|---|
| **P1** | "AI에게 고민을 털어놨더니 '힘드셨겠어요'만 반복한다." | 일반 챗봇 LLM은 학술적 근거 없이 동정 응답에 최적화됨. |
| **P2** | "저널 앱은 그냥 텍스트 저장소다. 다시 들여다볼 동기가 없다." | Day One·Notion 등은 기록은 잘 되지만 통찰을 제공하지 않음. |
| **P3** | "심리 상담은 비싸고 예약이 어렵다. 매일의 작은 고민에 쓰기엔 과하다." | 전문 상담의 접근성·즉시성 한계. |
| **P4** | "내 생각의 변화를 시간순으로 추적하고 싶은데, 흐름이 안 보인다." | 단편적 기록만 누적될 뿐, 사용자의 가치관 변화 추이를 시각화하는 도구 부재. |
| **P5** | "AI가 내 일기 데이터를 학습에 쓰는 건 아닐까?" | 민감 정보 처리에 대한 신뢰 부족. |

### 2.2 Logos Log의 기술적 해결책

| Pain | Logos Log의 해결 방식 |
|---|---|
| P1 | **학술 RAG 엔진** — 사용자 입력을 임베딩해 심리학 논문 청크를 검색, 학술적 프레임워크에 맵핑한 응답 생성. |
| P2 | **소크라테스식 역질문 챗봇** — 정답이 아닌 질문을 던져 사용자의 재방문·재성찰 동기 유발. |
| P3 | **언제든 접근 가능한 AI** — 24/7 즉시성, 무료에 가까운 한계 비용. |
| P4 | **의미 네트워크 그래프** — '아하 모먼트' 카드 노드 + 의미 연결 엣지 시각화. |
| P5 | **데이터 보호 아키텍처** — 일기 본문 암호화 저장, LLM 호출 시 PII 마스킹, OpenAI Zero Data Retention 옵션 사용. |

---

## 3. User Flow (핵심 유저 여정)

### 3.1 Happy Path (Step-by-step)

```
[Step 1] 진입 & 온보딩
  └─ 첫 방문 시 가치관 진단 미니 설문(5문항) → 사용자 컨텍스트 시드 생성

[Step 2] 일기 작성 (Journal Entry)
  └─ 에디터 진입 → 자유 작성 (감정 태그 옵션) → "분석 시작" 클릭

[Step 3] RAG 분석 단계 (Backend)
  ├─ ① 일기 텍스트 임베딩 (text-embedding-3)
  ├─ ② Vector DB(pgvector)에서 관련 논문 청크 Top-K 검색
  ├─ ③ 학술 프레임워크 맵핑 + 시스템 프롬프트 결합
  └─ ④ LLM(GPT-4o/Claude) → 첫 번째 소크라테스식 질문 생성

[Step 4] 딥다이브 대화 (Socratic Deep-Dive Chat)
  └─ 스트리밍 응답 → 사용자 답변 → 챗봇 후속 질문(맥락 누적)
       └─ 5~10턴 반복하며 점진적 심층화

[Step 5] 아하 모먼트 감지
  └─ AI가 "통찰의 순간" 패턴 감지 (감정어·확신어·메타인지 표현 가중치)
       └─ 사용자에게 "지금 발견하신 가치를 카드로 저장할까요?" 제안

[Step 6] 가치 카드(Value Card) 생성
  └─ 대화 요약 → 키 가치(예: "자율성", "관계") + 한 줄 인사이트 → 카드 저장

[Step 7] 의미 네트워크 확인 (Meaning Network)
  └─ 대시보드 → 누적 카드 노드 시각화 → 유사 가치끼리 클러스터·엣지 연결
       └─ 사용자가 자신의 성장 경로를 회고 가능
```

### 3.2 시각적 흐름

```
  [Onboarding] → [Journal Editor] → [RAG Analysis] → [Socratic Chat]
                                                          │
                                                          ▼
  [Meaning Network Dashboard] ← [Value Card Archive] ← [Aha-Moment Detection]
```

---

## 4. Functional Requirements (MoSCoW 기법 적용)

### 🔴 Must-have (16주 내 필수 구현)

| ID | Feature | 상세 |
|---|---|---|
| M1 | **사용자 인증** | 이메일/소셜(Google) 로그인. Supabase Auth 활용. |
| M2 | **일기 작성 에디터** | 기본 마크다운 에디터, 자동 저장, 감정 태그(5종). |
| M3 | **학술 RAG 검색 모듈** | pgvector 기반, Top-K(5~10) 검색. 임베딩 모델: `text-embedding-3-large`. |
| M4 | **소크라테스식 챗봇** | LLM 기반 멀티턴 대화. 시스템 프롬프트에 학술적 질문 기법 주입. |
| M5 | **대화 메모리 모듈** | Chat history를 LLM 컨텍스트에 누적, 세션 단위 저장. |
| M6 | **아하 모먼트 카드 생성** | 사용자 트리거(수동 "저장") + AI 추천(자동 감지) 병행. |
| M7 | **카드 아카이브 뷰** | 리스트/그리드 형태로 누적 카드 열람. |
| M8 | **의미 네트워크 시각화** | 노드-엣지 그래프 (D3.js 또는 React Flow). 가치 키워드 기반 클러스터링. |
| M9 | **스트리밍 응답 UX** | SSE 기반 실시간 토큰 출력. |
| M10 | **데이터 암호화** | 일기 본문 AES-256 at-rest 암호화. |

### 🟡 Should-have (권장)

| ID | Feature | 상세 |
|---|---|---|
| S1 | **Ragas 평가 대시보드** | 내부 운영자용, Faithfulness/Context Relevance 모니터링. |
| S2 | **하이브리드 검색** | BM25 키워드 + Vector 유사도 결합 (RRF 알고리즘). |
| S3 | **인용(Citation) 표시** | AI 응답에 참조 논문 출처 표시 (신뢰도 ↑). |
| S4 | **주간 리포트 이메일** | 한 주의 카드 요약 + 가치관 변화 트렌드. |

### 🟢 Could-have (시간 여유 시)

| ID | Feature | 상세 |
|---|---|---|
| C1 | **음성 입력(STT)** | Whisper API 활용, 일기 음성 작성. |
| C2 | **다크모드 + 테마 커스터마이징** | UX 폴리싱 단계에서 추가. |
| C3 | **카드 공유 기능** | 익명화된 카드를 SNS 카드뉴스 형태로 export. |

### ⚫ Won't-have (이번 MVP에서는 제외)

| ID | Feature | 제외 사유 |
|---|---|---|
| W1 | **실시간 1:1 전문가 상담 매칭** | 라이센스·법적 이슈, MVP 범위 초과. |
| W2 | **모바일 네이티브 앱(iOS/Android)** | 16주 내 PWA로 대체 권장. |
| W3 | **그룹 저널링(소셜 기능)** | 프라이버시 정책 복잡도 증가. |
| W4 | **수익화(결제·구독)** | MVP 검증 이후 단계로 분리. |

---

## 5. Non-Functional Requirements (비기능 요구사항)

### 5.1 보안 & 프라이버시 (Security & Privacy)

| 항목 | 요구사항 |
|---|---|
| **저장 암호화** | 일기 본문 AES-256 at-rest 암호화. 키는 Supabase Vault 또는 AWS KMS 분리 관리. |
| **전송 암호화** | 모든 통신 TLS 1.3 강제. |
| **PII 마스킹** | LLM 호출 전, 정규식 + NER로 이름·전화·주소·이메일 마스킹 후 전송. |
| **LLM 사용 정책** | OpenAI/Anthropic Zero Data Retention(ZDR) 옵션 활성. 학습 데이터 수집 거부. |
| **벡터 DB 분리** | 사용자 일기 임베딩과 학술 논문 임베딩은 **별도 네임스페이스**로 격리. RLS(Row-Level Security) 적용. |
| **삭제권(Right to be Forgotten)** | 계정 삭제 시 일기·임베딩·대화 로그 완전 삭제 (cascade). |
| **감사 로그** | 관리자 접근 로그 90일 보관. |
| **컴플라이언스** | GDPR / 개인정보보호법 준수. 명시적 동의 기반 데이터 처리. |

### 5.2 성능 (Performance)

| 지표 | 목표 |
|---|---|
| **RAG 검색 지연 (Top-K)** | P95 < 800ms |
| **LLM 첫 토큰 응답 시간 (TTFT)** | P95 < 1.5s |
| **전체 응답 완료 시간** | P95 < 6s (스트리밍 포함) |
| **API Throughput** | 100 RPS 동시 처리 (FastAPI + uvicorn workers) |
| **FE 초기 로딩(LCP)** | < 2.5s |

**UX 완화 전략:**
- **스트리밍 응답(SSE)** — 첫 토큰 즉시 출력으로 체감 지연 ↓
- **Skeleton UI + 지능형 로딩 메시지** — "관련 논문을 찾는 중..." 등 단계별 피드백
- **Optimistic UI** — 일기 저장은 즉시 UI 반영, 백엔드 비동기 처리
- **응답 캐싱** — 유사 쿼리 임베딩 LRU 캐시 (cosine sim > 0.95 시 재사용)

### 5.3 AI 품질 (AI Quality & Safety)

| 항목 | 전략 |
|---|---|
| **환각(Hallucination) 방지** | ① RAG 컨텍스트 외 답변 금지하는 시스템 프롬프트 ② Faithfulness 점수 0.8 미만 응답은 fallback 메시지로 대체 ③ 답변에 인용 출처 명시. |
| **프롬프트 인젝션 방어** | ① 사용자 입력과 시스템 프롬프트를 명확히 구분(role separation) ② "이전 지시를 무시하라" 류 패턴 필터링 ③ Output guardrail로 시스템 프롬프트 노출 차단. |
| **위기 감지(Crisis Detection)** | 자해·자살 관련 키워드 감지 시, AI 응답 차단 + 전문기관(자살예방상담전화 1393) 안내 배너 노출. |
| **편향(Bias) 모니터링** | 분기별 다양한 페르소나 시뮬레이션으로 응답 편향성 점검. |
| **회귀 테스트** | 골든 데이터셋 50개 케이스에 대한 정기 회귀 평가. |

---

## 6. Success Metrics (성공 지표 / KPI)

### 6.1 Product Metrics

| 지표 | 정의 | MVP 목표 (런칭 후 3개월) |
|---|---|---|
| **WAU / MAU** | Weekly / Monthly Active Users | WAU 500 / MAU 1,500 |
| **WAU/MAU Ratio (Stickiness)** | 재방문 점착성 | ≥ 0.30 |
| **평균 세션 길이** | 1회 접속당 대화 시간 | ≥ 8분 |
| **세션당 평균 대화 턴 수** | Socratic Chat 깊이 지표 | ≥ 6턴 |
| **'아하 모먼트' 카드 생성률** | 세션당 카드 생성 횟수 | ≥ 0.6 cards/session |
| **D7 Retention** | 7일 후 재방문율 | ≥ 35% |
| **NPS** | 추천 의향 | ≥ 40 |

### 6.2 AI / RAG Metrics (Ragas 기반)

| 지표 | 정의 | 목표 점수 |
|---|---|---|
| **Context Precision** | 검색된 컨텍스트 중 실제 관련 비율 | ≥ 0.80 |
| **Context Recall** | 정답 생성에 필요한 컨텍스트 회수율 | ≥ 0.75 |
| **Answer Faithfulness** | 응답이 컨텍스트에 충실한 정도 (환각 역지표) | ≥ 0.90 |
| **Answer Relevancy** | 응답이 사용자 질문에 적절한 정도 | ≥ 0.85 |
| **Response Latency (P95)** | 전체 응답 시간 | ≤ 6s |
| **Crisis Detection Recall** | 위기 신호 감지율 (안전 지표) | ≥ 0.95 |

### 6.3 평가 운영
- 매주 운영자 50개 샘플 라벨링 → Ragas 자동 평가 파이프라인
- 13주차 베이스라인 측정 → 14주차 하이브리드 검색 도입 후 개선폭 비교

---

## 7. Future Scope (추후 확장 계획 — v2.0)

### 7.1 🪞 Multi-Modal Reflection Companion
**컨셉:** 텍스트뿐 아니라 사진·음성 메모·심박 데이터(Apple Watch 연동)까지 통합 분석하는 멀티모달 저널링.
- 예: 산책 중 찍은 풍경 사진 + 음성 메모 + 그 시각의 심박 패턴 → AI가 "이 순간 당신은 평온함을 느꼈고, 이는 지난주 가치 카드 '자연과의 연결'과 일치합니다"라는 다층적 통찰 제공.
- **기술:** GPT-4o Vision + Whisper + HealthKit 연동.
- **가치:** 일기는 텍스트만이 아니라는 인식 전환. 일상의 모든 순간이 데이터가 되는 라이프 로깅 통합.

### 7.2 🌳 Generational Wisdom Graph (세대 간 지혜 그래프)
**컨셉:** 익명화·동의 기반으로 사용자들의 가치 카드를 연합학습(Federated Learning)으로 통합, "나와 비슷한 고민을 했던 동시대 사람들이 도달한 깨달음"을 추천.
- 예: 30대 번아웃 개발자가 도달한 깨달음 패턴 → 비슷한 페르소나에게 prior로 제공.
- **기술:** Federated Learning + 차등 프라이버시(Differential Privacy)로 개인 프라이버시 완벽 보호.
- **가치:** 개인 저널링 → 집단 지성 플랫폼으로의 진화. "혼자가 아니다"라는 정서적 연대 + 경험적 지혜 공유.

---

## 📎 Appendix: 핵심 데이터 흐름 다이어그램

```
[User] ──일기 입력──▶ [Next.js FE]
                          │
                          ▼
                   [FastAPI Backend]
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  [PII Masker]    [Embedding API]    [Chat History DB]
        │                 │                 │
        └────────┬────────┘                 │
                 ▼                          │
        [pgvector Hybrid Search]            │
        (Vector + BM25 + RRF)               │
                 │                          │
                 ▼                          │
        [Top-K Paper Chunks]                │
                 │                          │
                 ▼                          │
        [Prompt Composer] ◀─────────────────┘
                 │
                 ▼
        [LLM (GPT-4o / Claude)] ──스트리밍──▶ [User]
                 │
                 ▼
        [Aha-moment Detector]
                 │
                 ▼
        [Value Card → Meaning Graph DB]
```

---

**문서 작성 완료** — Engineering Kickoff Ready ✅
