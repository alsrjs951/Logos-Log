# RAG 평가 하니스 (Evaluation Harness)

Logos-Log의 "인식론적 정직"([vision.md](../../project/docs/vision.md) §4.2)을 사람의 감(感)이 아니라
**측정 가능한 파이프라인**으로 보장하기 위한 평가 자산입니다. 설계 배경과 지표 정의는
[rag_evaluation_plan.md](../../project/docs/rag_evaluation_plan.md)를 참고하세요.

평가는 두 단계(tier)로 나뉩니다.

---

## Tier 1 — 위기 감지 평가 (인프라 불필요, 지금 실행 가능)

안전 지표(Crisis Detection Recall ≥ 0.95)를 측정합니다. 무거운 모델·LLM·DB 없이
`services/safety.py`의 순수 함수만 평가하므로 **CI 게이트**로 바로 쓸 수 있습니다.

```bash
cd backend
python eval/evaluate_crisis.py
```

- 데이터셋: [`crisis_set.json`](./crisis_set.json) (위기 표현 + 위기가 아닌 감정 표현)
- 출력: Recall / Precision / F1, 미감지(FN)·오탐(FP) 목록
- Recall이 목표(0.95) 미만이면 **종료 코드 1** → CI 실패 처리 가능

---

## Tier 2 — RAG 품질 평가 (MongoDB + OpenAI 필요)

검색·답변 품질(Context Precision/Recall, Faithfulness, Answer Relevancy)을 측정합니다.
각 질문을 **프로덕션 경로**(`RAGService.get_streaming_response`)로 그대로 실행해
검색 청크와 생성 답변을 수집한 뒤 Ragas로 채점합니다.

**전제 조건**
- MongoDB Atlas에 `documents`가 적재되고 `vector_index`가 생성되어 있을 것
  ([mongodb_atlas_setup_guide.md](../../project/docs/mongodb_atlas_setup_guide.md))
- `.env`에 `MONGODB_URI`, `OPENAI_API_KEY` 설정
- 평가 의존성 설치: `pip install -r eval/requirements-eval.txt`

```bash
cd backend
python eval/evaluate_rag.py
```

- 데이터셋: [`golden_set.json`](./golden_set.json) — 카테고리별 질문 + 기대 학술 개념 + 기준 논지
- 출력: 지표별 점수와 PRD §6.2 목표 대비 PASS/FAIL (목표 미달 시 종료 코드 1)

> ⚠️ `evaluate_rag.py`는 외부 인프라(적재된 MongoDB + OpenAI 키)가 필요하여 **레포 작성 환경에서는
> 실행 검증되지 않았습니다.** Ragas는 버전에 민감하므로 `requirements-eval.txt`에 핀된 버전을 사용하고,
> 다른 버전에서는 임포트/컬럼명 조정이 필요할 수 있습니다. 검색 로직은 프로덕션과 동일한
> `RAGService.retrieve()`를 공유합니다.

---

## 지표 목표 (PRD §6.2)

| 지표 | 목표 | Tier |
|---|---|---|
| Crisis Detection Recall | ≥ 0.95 | 1 |
| Context Precision | ≥ 0.80 | 2 |
| Context Recall | ≥ 0.75 | 2 |
| Answer Faithfulness | ≥ 0.90 | 2 |
| Answer Relevancy | ≥ 0.85 | 2 |
