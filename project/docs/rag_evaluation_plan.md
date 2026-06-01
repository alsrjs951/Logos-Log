> ⚠️ **본 문서는 생성형 AI(Claude Opus 4.8)를 활용하여 작성되었습니다.**

# RAG 평가 파이프라인 설계 (RAG Evaluation Plan)

본 문서는 Logos-Log의 RAG·안전 품질을 **측정 가능한 파이프라인**으로 보장하기 위한 설계다.
[vision.md](./vision.md)의 Horizon 1(믿을 만한 핵심 루프)과 원칙 4.2(인식론적 정직)의 직접적 실행안이며,
지표 목표는 [PRD.md](./PRD.md) §6.2를 기준으로 한다.

---

## 1. 왜 평가인가

이 제품은 "논문을 인용한다"는 점이 브랜드의 핵심이다. 인용이 실제 논문 내용과 다르거나(환각),
검색이 엉뚱한 청크를 가져오면 제품의 전제 자체가 무너진다. 따라서 검색·답변 품질은
**데모로 '좋아 보인다'가 아니라 수치로 회귀 추적**되어야 한다. (PRD 13주차: 베이스라인 측정 → 14주차 개선폭 비교)

---

## 2. 무엇을 측정하는가

| 지표 | 정의 | 목표 | 도구 |
|---|---|---|---|
| **Crisis Detection Recall** | 위기 표현을 놓치지 않는 비율(안전) | ≥ 0.95 | 자체(`evaluate_crisis.py`) |
| **Context Precision** | 검색 청크 중 실제 관련 비율 | ≥ 0.80 | LLM-judge |
| **Context Recall** | 정답에 필요한 컨텍스트 회수율 | ≥ 0.75 | LLM-judge |
| **Faithfulness** | 답변이 검색 컨텍스트에 충실한 정도(환각 역지표) | ≥ 0.90 | LLM-judge |
| **Answer Relevancy** | 답변이 질문에 적절한 정도 | ≥ 0.85 | LLM-judge |

---

## 3. 2단계(Tier) 구조

평가 비용·인프라 의존성에 따라 두 단계로 나눈다. 코드는 `backend/eval/`에 있다.

### Tier 1 — 위기 감지 (구현 완료)
- 대상: `services/safety.py`의 `detect_crisis` (RAG·LLM·DB와 분리된 경량 모듈)
- 데이터셋: `backend/eval/crisis_set.json`
- 실행기: `backend/eval/evaluate_crisis.py` — Recall/Precision/F1 산출, Recall < 0.95 시 종료 코드 1
- 특징: 무거운 의존성이 없어 **모든 PR CI에서 게이트로 상시 실행 가능**

### Tier 2 — RAG 검색·답변 품질 (구현 + 베이스라인 측정 완료)
- 실행기: `backend/eval/evaluate_rag.py` — 별도 의존성 불필요(메인 `requirements.txt`만)
- 데이터셋: `backend/eval/golden_set.json` (카테고리별 질문 + 기대 학술 개념 + 기준 논지)
- 전제: MongoDB `documents` 적재 + `vector_index`, `OPENAI_API_KEY`
- 흐름:
  1. 각 `question`을 **프로덕션 경로**(`get_streaming_response`)로 실행 → 검색 청크(`contexts`)와 생성 답변(`answer`) 수집
  2. `question / answer / contexts / ground_truth` 를 LLM-judge(gpt-4o-mini)로 채점
  3. `context_precision, context_recall, faithfulness, answer_relevancy` 산출 → `eval/runs/`에 기록
  4. PRD §6.2 목표와 비교, 미달 시 종료 코드 1
- ℹ️ 초기 계획은 Ragas였으나 설치된 langchain 1.x 스택과 버전 비호환(모듈 경로 변경)이라, 동일 지표 정의를 langchain-openai 기반 LLM-judge로 직접 구현했다.

#### 베이스라인 (2026-06-02 · 골든셋 6케이스, 실측)

| 지표 | 점수 | 목표 | |
|---|---|---|---|
| Answer Relevancy | 0.90 | ≥ 0.85 | ✅ |
| Faithfulness | 0.83 | ≥ 0.90 | ❌ |
| Context Precision | 0.73 | ≥ 0.80 | ❌ |
| Context Recall | 0.58 | ≥ 0.75 | ❌ |

- **가장 약한 축은 검색(retrieval)**: `g02`(미루기/동기부여)가 주제와 어긋난 청크를 받아 precision/recall 0.00 → 평균을 크게 끌어내림. Horizon 2 하이브리드 검색(BM25+Vector)의 1순위 타깃.
- **충실도 0.83**(목표 미달): 일부 답변(`g05`=0.60)이 검색 근거를 벗어남 — 시스템 프롬프트의 "근거 밖 서술 금지" 강화 여지.
- 한계: 단일 LLM-judge·소표본(6) 추정치. 골든셋 50+ 확대 시 신뢰도 상승.

---

## 4. 검색 경로 분리 (완료)

검색 로직을 `RAGService.retrieve()` 로 추출하여 스트리밍·답변 생성과 분리했다.
`get_streaming_response`(프로덕션)와 `evaluate_rag.py`(평가)가 **동일한 검색 경로**를 공유하므로,
평가 점수가 실제 사용자 경험과 일치한다.

```python
async def retrieve(self, query, english_query=None) -> tuple:
    """쿼리 확장 → 임베딩 → $vectorSearch → 필터(≥0.30) → 재랭킹.
    (재랭킹 청크, 원시 검색 결과) 반환. 스트리밍/생성 부수효과 없음."""
    ...
```

---

## 5. 골든셋 운영

- 시작본은 카테고리(logotherapy/positive_psych/sdt/cbt)별 소수 케이스다. `reference_points`는 **전문가 검수 필요**.
- PRD 운영안(§6.3)대로 매주 운영자 샘플을 라벨링해 골든셋을 50+ 케이스로 키운다.
- 위기 골든셋은 실제 오탐/미감지 사례를 지속 추가해 안전 회귀를 막는다.
- 알려진 한계: 키워드 기반 위기 감지는 `자살골` 같은 합성어에서 오탐 가능(재현율 우선 설계). 정밀도가 필요하면 LLM 분류기 보강을 검토한다.

---

## 6. CI 통합 (로드맵)

1. **완료:** `evaluate_crisis.py`를 PR CI 게이트로 추가(`.github/workflows/safety-eval.yml`)해 안전 회귀를 차단(빠르고 무료).
2. **완료:** `retrieve()` 추출 + `evaluate_rag.py` 구현 + **베이스라인 측정 완료**(위 표). 검색 품질이 최우선 개선 영역으로 확인됨.
3. **다음:** RAG 평가는 비용·시간이 크므로 야간 스케줄 또는 RAG 관련 파일 변경 시에만 실행하고, 점수를 시계열로 기록해 개선폭(예: 하이브리드 검색 도입 전후)을 비교한다. 골든셋을 50+로 확대한다.
