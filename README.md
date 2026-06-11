# Logos-Log

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/alsrjs951/Logos-Log)](https://github.com/alsrjs951/Logos-Log/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/alsrjs951/Logos-Log)](https://github.com/alsrjs951/Logos-Log/pulls)
[![DORA Metrics](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml/badge.svg)](https://github.com/alsrjs951/Logos-Log/actions/workflows/metrics.yml)

> ⚠️ **본 문서의 일부는 생성형 AI(Claude, GPT 등)를 활용하여 작성되었습니다.**

---

## 프로젝트명

- **국문:** 로고스 로그 (Logos Log) — 학술 기반 RAG를 활용한 실존적 의미 탐구 저널링 플랫폼
- **영문:** Logos Log: An Evidence-based Meaning-Making Journaling Platform using RAG

---

## 문제 정의

- **시대적 배경:** 자동화와 AI의 발전으로 '생존을 위한 노동'이 감소하면서, 개인에게 주어지는 잉여 시간은 폭발적으로 증가하고 있습니다. 이는 역설적으로 삶의 목적을 상실하는 '실존적 공허함(Existential Vacuum)'과 번아웃을 초래할 위험이 큽니다.
- **기존 서비스의 한계:** 현재의 저널링 앱이나 심리 상담 챗봇은 대부분 단순한 텍스트 저장소에 불과하거나, "힘드셨겠네요" 식의 피상적이고 획일화된 위로를 제공하는 데 그칩니다.
- **해결 방안:** 사용자의 일상과 감정을 **긍정 심리학 및 의미 치료(Logotherapy) 등 검증된 학술 논문 데이터**를 기반으로 분석합니다. 이를 통해 일시적인 위안이 아닌, 객관적이고 과학적인 자아 성찰과 삶의 의미 재구성(Meaning-Making)을 돕습니다.

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

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **LLM** | GPT-4o-mini (응답 생성·스트리밍), GPT-3.5 Turbo (가치 카드 추출) |
| **임베딩 모델** | `BAAI/bge-m3` (로컬, 1024차원, 무료) |
| **RAG Framework** | LangChain + LangChain-HuggingFace |
| **Vector DB** | MongoDB Atlas Vector Search (`$vectorSearch`, 1024차원) |
| **인증** | 자체 JWT + bcrypt (PyJWT) |
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
SEMANTIC_SCHOLAR_API_KEY=...                    # (선택) 논문 수집 스크립트용
```

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
