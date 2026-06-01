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
| **Context Precision** | 검색 청크 중 실제 관련 비율 | ≥ 0.80 | Ragas |
| **Context Recall** | 정답에 필요한 컨텍스트 회수율 | ≥ 0.75 | Ragas |
| **Faithfulness** | 답변이 검색 컨텍스트에 충실한 정도(환각 역지표) | ≥ 0.90 | Ragas |
| **Answer Relevancy** | 답변이 질문에 적절한 정도 | ≥ 0.85 | Ragas |

---

## 3. 2단계(Tier) 구조

평가 비용·인프라 의존성에 따라 두 단계로 나눈다. 코드는 `backend/eval/`에 있다.

### Tier 1 — 위기 감지 (구현 완료)
- 대상: `services/safety.py`의 `detect_crisis` (RAG·LLM·DB와 분리된 경량 모듈)
- 데이터셋: `backend/eval/crisis_set.json`
- 실행기: `backend/eval/evaluate_crisis.py` — Recall/Precision/F1 산출, Recall < 0.95 시 종료 코드 1
- 특징: 무거운 의존성이 없어 **모든 PR CI에서 게이트로 상시 실행 가능**

### Tier 2 — RAG 검색·답변 품질 (설계됨, 구현 예정)
- 데이터셋: `backend/eval/golden_set.json` (카테고리별 질문 + 기대 학술 개념 + 기준 논지)
- 전제: MongoDB `documents` 적재 + `vector_index`, `OPENAI_API_KEY`, `pip install ragas datasets`
- 흐름:
  1. 각 `question`으로 실제 검색 실행 → 검색 청크(`contexts`)와 생성 답변(`answer`) 수집
  2. `question / answer / contexts / reference` 를 Ragas 입력 포맷으로 구성
  3. `faithfulness, answer_relevancy, context_precision, context_recall` 산출
  4. 카테고리별·전체 평균을 리포트하고 목표 임계값과 비교

---

## 4. 권장 선행 리팩터링

현재 검색 로직은 `RAGService.get_streaming_response` 안에 스트리밍 생성과 뒤섞여 있어
평가에서 "검색 결과만" 떼어내기 어렵다. 다음 추출을 권장한다.

```python
# 검색 단계만 분리하여 평가·재사용을 쉽게 한다
async def retrieve(self, query: str) -> list[dict]:
    """쿼리 확장 → 임베딩 → $vectorSearch → 재랭킹까지 수행하고 청크 리스트를 반환."""
    ...
```

이렇게 하면 `evaluate_rag.py`가 답변 생성·스트리밍 부수효과 없이 `contexts`를 얻을 수 있고,
프로덕션 코드와 평가가 **같은 검색 경로**를 공유해 신뢰도가 올라간다.

---

## 5. 골든셋 운영

- 시작본은 카테고리(logotherapy/positive_psych/sdt/cbt)별 소수 케이스다. `reference_points`는 **전문가 검수 필요**.
- PRD 운영안(§6.3)대로 매주 운영자 샘플을 라벨링해 골든셋을 50+ 케이스로 키운다.
- 위기 골든셋은 실제 오탐/미감지 사례를 지속 추가해 안전 회귀를 막는다.
- 알려진 한계: 키워드 기반 위기 감지는 `자살골` 같은 합성어에서 오탐 가능(재현율 우선 설계). 정밀도가 필요하면 LLM 분류기 보강을 검토한다.

---

## 6. CI 통합 (로드맵)

1. **지금:** `evaluate_crisis.py`를 PR CI에 추가해 안전 회귀를 차단(빠르고 무료).
2. **다음:** `retrieve()` 추출 → `evaluate_rag.py` 구현 → 골든셋으로 베이스라인 측정.
3. **이후:** RAG 평가는 비용·시간이 크므로 야간 스케줄 또는 RAG 관련 파일 변경 시에만 실행하고, 점수를 시계열로 기록해 개선폭(예: 하이브리드 검색 도입 전후)을 비교한다.
