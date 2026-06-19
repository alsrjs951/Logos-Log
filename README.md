# Logos-Log

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/alsrjs951/Logos-Log)](https://github.com/alsrjs951/Logos-Log/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/alsrjs951/Logos-Log)](https://github.com/alsrjs951/Logos-Log/pulls)
[![Final Submission Gate](https://github.com/alsrjs951/Logos-Log/actions/workflows/final-submission-gate.yml/badge.svg)](https://github.com/alsrjs951/Logos-Log/actions/workflows/final-submission-gate.yml)
[![DORA Metrics](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml/badge.svg)](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml)

> ⚠️ **본 문서의 일부는 생성형 AI(Claude, GPT 등)를 활용하여 작성되었습니다.**

---

## 한눈에 보기

**Logos-Log**는 사용자의 일기와 성찰 대화를 가치 카드로 정리하고, 그 가치를 이번 주의 작은 실험과 며칠 뒤 회고로 이어주는 의미 행동 도구입니다. 단순히 좋은 답변을 주는 AI가 아니라, 누적 기록을 다음 선택으로 바꾸는 개인 의미 루프를 목표로 합니다.

### 포트폴리오 하이라이트

- **의미 행동 루프:** 일기 작성 → 성찰 대화 → 가치 카드 저장 → 작은 실험 채택 → 회고 기록으로 이어지는 제품 루프를 제공합니다.
- **개인 기록 기반 추천:** 저장된 가치 카드 흐름을 바탕으로 LLM이 이번 주에 시도할 수 있는 구체적이고 부담 낮은 실험을 제안합니다.
- **근거 기반 답변:** 사용자의 한국어 고민을 영어 학술 검색 표현으로 확장한 뒤, MongoDB Atlas Vector Search로 관련 연구 발췌를 검색합니다.
- **정직한 출처 표시:** UI에서 `논문 전체 요약`이 아니라 `근거 발췌`로 표현하고, 인용 배지·출처 카드·출처 모달로 실제 사용된 근거를 보여줍니다.
- **평가 기반 의사결정:** `$text` 하이브리드/RRF 검색은 실험 결과 벡터 단독 검색보다 낮아 프로덕션 기본값에서 제외했습니다.
- **RAG 품질 개선 기록:** 청크 메타데이터, 페이지/섹션 보존, 주변 청크 확장, 다중 쿼리 벡터 검색, 평가 trace를 개선했습니다.
- **한계의 명시:** 승인 기준으로 삼은 평가 실행에서 검색 지표는 목표를 통과한 적이 있지만, Faithfulness는 아직 개선 대상입니다.

### RAG 평가 요약

| 지표 | 승인 기준 평가 | 목표 | 상태 |
|------|--------------|------|------|
| Context Precision | `0.813` | `0.80` 이상 | 통과 |
| Context Recall | `0.767` | `0.75` 이상 | 통과 |
| Faithfulness | `0.828` | `0.90` 이상 | 개선 필요 |
| Answer Relevancy | `0.910` | `0.90` 이상 | 통과 |

> 평가 기준 파일: `baseline_20260609_003413.json`. 현재 다음 개선 목표는 검색보다 답변 충실도(Faithfulness)입니다.

### 발표·시연 자료

- [데모 플레이북](project/docs/demo_playbook.md): 시연 질문, Tailscale 실행 방식, 발표 전 체크리스트
- [발표 스크립트](project/docs/presentation_script.md): 3분 발표, 30초 데모 멘트, 예상 질문 답변
- [RAG 아키텍처 다이어그램](project/docs/rag_architecture_diagram.md): 검색·재랭킹·근거 표시 흐름 다이어그램

---

## Final Submission

| 항목 | 링크 / 증빙 |
|------|-------------|
| GitHub 저장소 | [alsrjs951/Logos-Log](https://github.com/alsrjs951/Logos-Log) — public, default branch `main` |
| 프론트엔드 배포 | [Vercel production](https://frontend-eight-nu-21.vercel.app) |
| 백엔드 배포 헬스체크 | `${RENDER_BACKEND_URL}/health` — Render secret 기반, `GET /health` 구현 |
| PR 게이트 | [Final Submission Gate](https://github.com/alsrjs951/Logos-Log/actions/workflows/final-submission-gate.yml): frontend lint/test/build + AI mini eval |
| main 배포 | [Frontend Vercel workflow](https://github.com/alsrjs951/Logos-Log/actions/workflows/week10-frontend-deploy.yml), [Backend Render workflow](https://github.com/alsrjs951/Logos-Log/actions/workflows/week10-backend-deploy.yml) |
| 보안 | [Dependabot config](.github/dependabot.yml): frontend npm, backend pip, GitHub Actions |
| 관측성 | 구조화 JSON 로그 + `X-Request-ID`, [DORA metrics workflow](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml), [dashboard source](dashboard/index.html) |
| 운영 문서 | [RUNBOOK.md](RUNBOOK.md), [CHANGELOG.md](CHANGELOG.md), [RETROSPECTIVE.md](RETROSPECTIVE.md) |
| 릴리스 | [`v1.0.0` GitHub Release](https://github.com/alsrjs951/Logos-Log/releases/tag/v1.0.0) |
| 3분 이내 영상 데모 | [logos-log-demo-v1.0.0.mp4](https://github.com/alsrjs951/Logos-Log/releases/download/v1.0.0/logos-log-demo-v1.0.0.mp4) — `v1.0.0` Release asset |

최종 smoke test는 `RUNBOOK.md`의 배포 체크리스트를 따릅니다. 백엔드 헬스체크는 외부 DB나 LLM에 의존하지 않는 liveness probe로 유지합니다.

---

## 프로젝트명

- **국문:** 로고스 로그 (Logos Log) — 기록을 작은 실험과 회고로 이어주는 의미 행동 도구
- **영문:** Logos Log: A Meaning Action Loop for Journaling, Reflection, and Small Experiments

---

## 문제 정의

- **시대적 배경:** 자동화와 AI의 발전으로 '생존을 위한 노동'이 감소하면서, 개인에게 주어지는 잉여 시간은 폭발적으로 증가하고 있습니다. 이는 역설적으로 삶의 목적을 상실하는 '실존적 공허함(Existential Vacuum)'과 번아웃을 초래할 위험이 큽니다.
- **기존 서비스의 한계:** 현재의 저널링 앱이나 심리 상담 챗봇은 대부분 단순한 텍스트 저장소에 불과하거나, "힘드셨겠네요" 식의 피상적이고 획일화된 위로를 제공하는 데 그칩니다.
- **해결 방안:** 사용자의 일상과 감정을 **긍정 심리학 및 의미 치료(Logotherapy) 등 심리학 논문 발췌**와 연결하고, 대화에서 발견한 가치를 작은 행동 실험으로 바꿉니다. 이를 통해 일시적인 위안에 머무르지 않고, 사용자가 자신의 선택이 실제로 도움이 되는지 회고할 수 있게 돕습니다.

---

## 핵심 기능

1. **논문 기반 심리 분석 RAG 엔진 (Evidence-Based RAG Analysis)**
   - 사용자가 작성한 일기를 단순 LLM이 아닌, 심리학 논문이 임베딩된 벡터 DB를 거쳐 분석합니다.
   - 사용자의 감정 상태를 학술적 프레임워크(예: 자기결정성 이론 등)에 맵핑하여 논리적이고 객관적인 피드백을 제공합니다.

2. **소크라테스식 딥다이브 챗봇 (Socratic Deep-Dive Chat)**
   - 정답이나 위로를 던져주는 대신, 논문에서 추출한 질문 기법을 활용해 사용자 스스로 깨달음을 얻도록 유도하는 다이얼로그 시스템입니다.
   - 대화의 맥락(Context)을 기억하며 점진적으로 깊은 내면의 가치를 끌어냅니다.

3. **의미 네트워크 아카이브 (Meaning Network Archive)**
   - 사용자가 대화 중 '아하 모먼트(Aha-moment)'에 도달했을 때, AI가 해당 문맥을 요약하여 하나의 '가치 카드'로 추출합니다.
   - 이 카드들을 노드(Node)로 연결하여, 사용자의 지적/심리적 성장을 시각화된 그래프 형태로 제공합니다.

4. **작은 실험과 회고 루프 (Meaning Action Loop)**
   - 저장된 가치 카드 흐름을 바탕으로 사용자가 이번 주에 시도할 수 있는 작은 실험을 제안합니다.
   - 사용자가 채택한 실험은 며칠 뒤 회고 대상으로 돌아오며, 결과와 도움 정도를 기록해 다음 선택의 근거로 쌓입니다.

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **LLM** | GPT-4o-mini (응답 생성·스트리밍), GPT-3.5 Turbo (가치 카드 추출) |
| **임베딩 모델** | `BAAI/bge-m3` (로컬, 1024차원, 무료) |
| **RAG Framework** | LangChain + LangChain-HuggingFace |
| **Vector DB** | MongoDB Atlas Vector Search (`$vectorSearch`, 1024차원) |
| **인증** | 자체 JWT + bcrypt (PyJWT), httpOnly refresh cookie, 서버 측 refresh session 회전 |
| **Backend** | FastAPI (Python) |
| **Frontend** | React 19 + Vite, lucide-react, react-markdown |
| **Deployment** | Vercel (FE), Render/Railway · Docker (BE) |
| **로그 수집** | Fluentd |
| **로그 저장** | Elasticsearch 8.11.0 |
| **시각화** | Kibana, Grafana |
| **메트릭 수집** | Prometheus |
| **DORA 자동화** | GitHub Actions + Octokit REST |
| **CI/CD** | GitHub Actions |
| **인프라** | Docker 24.0+, Docker Compose 2.20+ |

> 💡 **임베딩 파이프라인은 완전 로컬 실행**으로, OpenAI API 비용 없이 Apple Silicon MPS GPU 가속을 활용합니다.

---

## DevOps 파이프라인 아키텍처

```
[App Logs]
    │
    ▼
[Fluentd]  ──────────────────────────────
    │                                    │
    ▼                                    ▼
[Elasticsearch]                    [Prometheus]
    │                                    │
    ▼                                    ▼
[Kibana]                           [Grafana]
```

---

## 주요 DevOps 기능

- **로그 수집**: Fluentd 에이전트로 애플리케이션 로그 수집 및 파싱
- **로그 저장**: Elasticsearch 인덱싱 및 ILM 보존 정책
- **시각화**: Kibana 대시보드
- **DORA 메트릭**: GitHub Actions로 Lead Time, Deploy Frequency, MTTR, Change Failure Rate 자동 측정
- **스프린트 관리**: GitHub Projects 칸반 보드 운영

---

## 16주 마일스톤

단순한 웹 개발을 넘어, RAG 시스템의 평가와 최적화 과정이 포함된 엔지니어링 중심의 일정입니다.

### Phase 1: 기획 및 데이터 파이프라인 구축 (1~4주차)

- **1주차:** 요구사항 정의서 작성 및 시스템 아키텍처 설계 (FE/BE/AI 분리)
- **2주차:** 긍정 심리학, 의미 치료 관련 논문(PDF 등) 데이터셋 수집 및 전처리 계획 수립
- **3주차:** 텍스트 청킹(Chunking) 전략 수립 및 임베딩 모델(`BAAI/bge-m3` 등) 테스트·선정
- **4주차:** Vector DB(MongoDB Atlas Vector Search) 구축 및 베이스라인 RAG 검색 모듈(Retriever) 구현

### Phase 2: 코어 AI 엔진 및 백엔드 개발 (5~8주차)

- **5주차:** 논문 데이터를 활용한 분석용 시스템 프롬프트 엔지니어링
- **6주차:** 소크라테스식 역질문 유도를 위한 메모리(Chat History) 모듈 연동
- **7주차:** FastAPI 기반 백엔드 API 설계 및 AI 로직 통합
- **8주차:** 중간 점검 — 터미널 환경에서 대화 파이프라인 테스트 및 병목 구간 확인

### Phase 3: 프론트엔드 연동 및 MVP 완성 (9~12주차)

- **9주차:** React + Vite 기반 UI 레이아웃 및 컴포넌트 설계
- **10주차:** FE-BE API 연동 (일기 작성 및 실시간 채팅 인터페이스 연동)
- **11주차:** 의미 네트워크(아하 모먼트 시각화) 컴포넌트 및 대시보드 구현
- **12주차:** MVP 버전 배포 및 내부 테스트 (핵심 기능 정상 작동 여부 검증)

### Phase 4: RAG 최적화 및 시스템 고도화 (13~16주차)

- **13주차:** Ragas 등을 활용한 검색 정확도(Retrieval Accuracy) 및 답변 품질 정량 평가
- **14주차:** 벡터 검색 유지, 청크 메타데이터/주변 청크 확장/재랭커 안정화를 통한 RAG 성능 최적화
- **15주차:** UI/UX 폴리싱(애니메이션 추가, 로딩 속도 개선) 및 사용성 테스트 피드백 반영
- **16주차:** 최종 버그 픽스, 아키텍처 다이어그램 포함 최종 보고서/포트폴리오 작성 및 프로젝트 마감

---

## 빠른 시작

### 사전 요구 사항

- Python 3.11+
- Node.js 20.0+
- MongoDB Atlas 클러스터 (Vector Search 인덱스 `vector_index`, 1024차원)
- OpenAI API Key

### 환경변수 (`.env`)

프로젝트 루트(또는 `backend/`)에 `.env` 파일을 생성합니다.

```bash
MONGODB_URI=mongodb+srv://...                  # MongoDB Atlas 연결 문자열
OPENAI_API_KEY=sk-...                           # LLM 응답 생성
JWT_SECRET=<충분히 긴 무작위 문자열>            # 필수 — 미설정 시 백엔드 부팅 거부
ENCRYPTION_KEY=<32바이트 base64>                # 일기/대화 본문 AES-256 암호화 키
INTENTION_HASH_SECRET=<충분히 긴 무작위 문자열> # (선택) 실험 중복 판단 HMAC 키, 미설정 시 JWT_SECRET 사용
CORS_ALLOW_ORIGINS=http://localhost:5173        # (선택) 쉼표로 구분한 허용 프론트엔드 Origin
VALUE_EXPERIMENT_LLM_TIMEOUT_SECONDS=12         # (선택) 작은 실험 추천 LLM 호출 타임아웃
AUTH_RATE_LIMIT_PER_MINUTE=8                    # (선택) 로그인/회원가입 IP+이메일 기준 제한
AUTH_RATE_LIMIT_WINDOW_SECONDS=60               # (선택) 인증 rate limit 윈도우
LLM_RATE_LIMIT_PER_MINUTE=20                    # (선택) 사용자별 LLM 비용 경로 제한
LLM_RATE_LIMIT_WINDOW_SECONDS=60                # (선택) LLM rate limit 윈도우
REFRESH_COOKIE_NAME=logos_refresh_token         # (선택) httpOnly refresh token 쿠키 이름
REFRESH_COOKIE_SECURE=false                     # (선택) HTTPS 배포에서는 true 권장
REFRESH_COOKIE_SAMESITE=lax                     # (선택) 프론트/백엔드 도메인이 다르면 none 검토
CSRF_REQUIRE_ORIGIN=true                        # (선택) cookie auth 요청의 Origin/Referer 요구 여부
CSRF_TRUSTED_ORIGINS=https://app.example.com    # (선택) CORS 외 추가로 신뢰할 Origin 목록
STRUCTURED_LOGS_ENABLED=true                    # (선택) request_id 포함 JSON 로그 출력 여부
SEMANTIC_SCHOLAR_API_KEY=...                    # (선택) 논문 수집 스크립트용
```

인증 세션은 메모리 보관 access token과 httpOnly refresh cookie로 분리됩니다. 프론트엔드는 access token을 `localStorage`에 저장하지 않으며, 새로고침 시 refresh cookie로 세션을 조용히 복구합니다. refresh token은 JWT의 `jti` 해시를 MongoDB `refresh_tokens` 컬렉션에 저장하며, refresh 시 기존 세션을 폐기하고 새 세션으로 회전합니다. 로그아웃 시 현재 refresh session을 폐기하고, 회전된 옛 refresh token이 재사용되면 같은 세션 패밀리의 활성 토큰도 폐기합니다. 쿠키를 발급·회전·폐기하는 auth 요청은 `CORS_ALLOW_ORIGINS` 또는 `CSRF_TRUSTED_ORIGINS`에 포함된 Origin/Referer에서 온 요청만 허용합니다.

모든 요청은 `X-Request-ID` 응답 헤더를 받습니다. 프론트엔드 API 래퍼는 기본적으로 `X-Request-ID`를 생성해 보내며, 클라이언트가 값을 보내지 않은 외부 요청은 서버가 생성합니다. auth 실패, rate limit, 추천 실험 LLM 실패, RAG 스트리밍 오류 등 주요 운영 이벤트는 같은 `request_id`가 포함된 JSON 로그로 출력됩니다. 성찰 본문과 원본 일기/실험 ID는 로그에 남기지 않고, 운영 추적이 필요한 경우 `journal_hash`, `intention_id_hash`처럼 해시 필드만 사용합니다. 중앙 로그 유틸은 `user_id`, `email`, `journal_id`, `intention_id`, `card_id` 같은 원본 필드가 들어와도 자동으로 해시 필드로 변환합니다.

행동 루프의 핵심 전환도 민감 본문 없이 구조화 로그로 남깁니다. `meaning_experiment_adopted`, `meaning_experiment_reflected`, `meaning_experiment_dismissed` 이벤트에는 해시 처리된 사용자/실험/카드 식별자, canonical 가치, 화면 출처(`dashboard_action_loop`, `meaning_network`, `meaning_change_review`, `value_card_modal`), 글자 수·도움 정도 같은 비식별 지표만 포함됩니다.

LLM이 생성한 작은 실험 문구는 캐시·노출 전에 품질 가드레일을 통과해야 합니다. 너무 길거나, 치료/진단처럼 들리거나, “반드시 해야 한다”처럼 압박적인 문구이거나, 7일 안에 해볼 작은 행동으로 보기 어려운 문구는 거절되고 `recommended_experiment_error` 로그의 `error_code`로만 기록됩니다. 이 경우 기존 캐시나 프론트엔드 규칙 기반 추천으로 fallback됩니다.

추천 실험 캐시는 반복 LLM 호출을 줄이기 위해 저장하지만, 사용자 가치 흐름에서 파생된 `reason`, `experiment`, `reflection_question` 텍스트는 일기/가치 카드/다짐 본문과 마찬가지로 `ENCRYPTION_KEY`로 암호화해 저장합니다. 암호화 도입 전의 평문 캐시는 레거시 값으로 읽되, 새로 생성되는 캐시는 암호문으로 저장됩니다.

대시보드의 행동 루프 지표는 채근용 성과표가 아니라 사용자가 자신의 선택 흐름을 알아보기 위한 기록입니다. `due_count`는 지금 돌아볼 수 있는 열린 실험 수, `next_review_available_at`은 아직 회고 시점이 오지 않은 실험 중 가장 가까운 회고 가능 시점입니다. `follow_through_rate`는 `회고 완료 / (회고 완료 + 열린 실험)`으로 계산하며, 사용자가 부담 없이 접어둔 실험은 실패로 세지 않고 별도 `dismissed` 기록으로 보여줍니다.

각 실험 응답에는 저장 후 언제부터 회고 대상으로 보여줄지 계산한 `review_available_at`과 현재 회고 대상인지 나타내는 `is_due`가 포함됩니다. 기본값은 저장 후 3일이며, 알림을 보내는 대신 사용자가 대시보드나 변화 화면에 돌아왔을 때만 조용히 보여줍니다.

같은 가치 카드에서 같은 열린 실험을 다시 담는 경우에는 새 레코드를 만들지 않고 기존 열린 실험을 반환합니다. 중복 판단은 정규화한 실험 문구의 서버 비밀키 기반 HMAC `intention_hash`로 처리하며, `INTENTION_HASH_SECRET`이 있으면 이 값을, 없으면 `JWT_SECRET`을 사용합니다. 실험 원문은 기존처럼 암호화된 `intention` 필드에만 저장합니다. 앱 로직의 사전 조회와 MongoDB partial unique index(`status=open`, `intention_hash=string`)를 함께 사용해 빠른 연속 클릭이나 동시 요청에서도 같은 열린 실험이 중복 생성되지 않게 합니다. 단순 SHA 해시, JWT_SECRET 기반 HMAC 해시, 또는 해시 없이 생성된 기존 열린 실험은 같은 문구가 다시 들어올 때 한 번 확인해 새 `intention_hash`로 갱신합니다. 이 경우 응답의 `was_duplicate`가 `true`가 되어 프론트엔드는 “이미 담긴 실험입니다”로 안내합니다.

`ENCRYPTION_KEY` 생성:
```bash
python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

### 백엔드 (FastAPI · 포트 8000)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload     # http://localhost:8000  (docs: /docs)
```

> 최초 실행 시 임베딩 모델 `BAAI/bge-m3`를 내려받습니다(Apple Silicon은 MPS 가속).

### 프론트엔드 (React + Vite · 포트 5173)

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

### (선택) 로깅 인프라

`docker-compose-es.yml`은 로그 분석용 Elasticsearch 단일 노드만 띄웁니다(앱 자체는 위 uvicorn/Vite로 구동).

```bash
docker compose -f docker-compose-es.yml up -d   # Elasticsearch → http://localhost:9200
```

---

## 프로젝트 구조

```
Logos-Log/
├── .github/
│   ├── workflows/          # GitHub Actions (DORA 메트릭, 배포)
│   └── ISSUE_TEMPLATE/     # 이슈 템플릿 (Bug / Feature)
├── backend/                # FastAPI 백엔드
│   ├── main.py             # 앱 진입점 (CORS, 라우터 등록)
│   ├── db.py               # MongoDB 연결
│   ├── api/                # 라우터: auth · chat · journals · value_cards
│   ├── services/           # rag_service.py (LangChain RAG 파이프라인)
│   ├── models/             # Pydantic 스키마
│   └── scripts/
│       ├── collect_semantic_scholar_pdfs.py  # Semantic Scholar API로 논문 수집
│       ├── preprocess.py                     # PDF 텍스트 추출 및 정규화
│       ├── chunk_and_embed.py                # 청킹 + BAAI/bge-m3 로컬 임베딩
│       ├── upload_to_mongodb.py              # MongoDB Atlas Vector Search 업로드
│       └── test_retriever.py                 # RAG 검색기 테스트
├── data/
│   ├── raw/                # 수집된 PDF 원본 (gitignore)
│   ├── processed/          # 전처리된 JSON 텍스트 (gitignore)
│   └── embeddings/         # 임베딩 벡터 JSON (gitignore)
├── frontend/               # React + Vite 프론트엔드
├── assignments/            # 주차별 과제 결과물
├── dashboard/              # DORA 메트릭 정적 대시보드
├── scripts/                # Kibana 대시보드 임포트 스크립트
├── docker-compose-es.yml
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── LICENSE
```

---

## 데이터 파이프라인

500개의 오픈 액세스 심리학 논문을 수집하여 MongoDB Atlas Vector Search에 인덱싱하는 파이프라인입니다.

```
[Semantic Scholar API] → [PDF 수집] → [텍스트 추출] → [청킹]
                                                              ↓
[MongoDB Atlas Vector Search] ← [업로드] ← [BAAI/bge-m3 임베딩 (로컬)]
```

| 단계 | 스크립트 | 결과 |
|------|----------|------|
| 논문 수집 | `collect_semantic_scholar_pdfs.py` | 498개 PDF |
| 텍스트 전처리 | `preprocess.py` | 498개 JSON |
| 청킹 + 임베딩 | `chunk_and_embed.py` | 25,289개 벡터 청크 |
| DB 업로드 | `upload_to_mongodb.py` | MongoDB Atlas에 저장 완료 |

**수집 카테고리**: Logotherapy (150) · Positive Psychology (150) · SDT (100) · CBT (98)


---

## 문서

| 문서 | 링크 |
|------|------|
| 시작 가이드 | [Wiki](https://github.com/alsrjs951/Logos-Log/wiki/Getting-Started) |
| 개발 가이드 | [Wiki](https://github.com/alsrjs951/Logos-Log/wiki/Development-Guide) |
| 문제 해결 | [Wiki](https://github.com/alsrjs951/Logos-Log/wiki/Troubleshooting) |
| 데모 플레이북 | [project/docs/demo_playbook.md](project/docs/demo_playbook.md) |
| 발표 스크립트 | [project/docs/presentation_script.md](project/docs/presentation_script.md) |
| RAG 아키텍처 다이어그램 | [project/docs/rag_architecture_diagram.md](project/docs/rag_architecture_diagram.md) |
| 운영 Runbook | [RUNBOOK.md](RUNBOOK.md) |
| 변경 이력 | [CHANGELOG.md](CHANGELOG.md) |
| 회고문 | [RETROSPECTIVE.md](RETROSPECTIVE.md) |
| 기여 가이드 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 행동 강령 | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |

---

## 기여하기

버그 제보, 기능 제안, 문서 개선 모두 환영합니다.  
기여 전에 반드시 [CONTRIBUTING.md](CONTRIBUTING.md) 를 읽어주세요.

---

## 행동 강령

이 프로젝트는 [Contributor Covenant](CODE_OF_CONDUCT.md) 행동 강령을 따릅니다.

---

## 라이선스

이 프로젝트는 [MIT License](LICENSE) 하에 배포됩니다.  
Copyright (c) 2026 Mingeon Lee
