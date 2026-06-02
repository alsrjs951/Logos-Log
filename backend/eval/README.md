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
검색 청크와 생성 답변을 수집한 뒤 **LLM-judge**(gpt-4o-mini)로 채점합니다.

**전제 조건**
- MongoDB Atlas에 `documents`가 적재되고 `vector_index`가 생성되어 있을 것
  ([mongodb_atlas_setup_guide.md](../../project/docs/mongodb_atlas_setup_guide.md))
- `.env`에 `MONGODB_URI`, `OPENAI_API_KEY` 설정
- 별도 평가 의존성 불필요 — 메인 `requirements.txt`만으로 동작

```bash
cd backend
python eval/evaluate_rag.py
```

- 데이터셋: [`golden_set.json`](./golden_set.json) — 카테고리별 질문 + 기대 학술 개념 + 기준 논지
- 출력: 지표별 평균과 PRD §6.2 목표 대비 PASS/FAIL (미달 시 종료 코드 1), `eval/runs/`에 JSON 기록(gitignore)

> ℹ️ 초기엔 Ragas를 쓰려 했으나, 설치된 langchain 1.x 스택과 Ragas의 `langchain_community` 의존성이
> 버전 비호환이라(모듈 경로 변경) 동일 지표 정의를 **langchain-openai 기반 LLM-judge**로 직접 구현했습니다.
> 검색 로직은 프로덕션과 동일한 `RAGService.retrieve()`를 공유합니다.

### 베이스라인 (2026-06-02 · 골든셋 6케이스)

| 지표 | 점수 | 목표 |
|---|---|---|
| Answer Relevancy | **0.90** | ≥ 0.85 ✅ |
| Faithfulness | **0.83** | ≥ 0.90 ❌ |
| Context Precision | **0.73** | ≥ 0.80 ❌ |
| Context Recall | **0.58** | ≥ 0.75 ❌ |

가장 약한 지점은 **검색(retrieval)** — 특히 `g02`(미루기/동기부여)에서 검색 청크가 주제와 어긋나
precision/recall 0.00을 기록해 평균을 크게 끌어내립니다. → Horizon 2 하이브리드 검색의 우선 개선 타깃.
답변 관련성은 양호하나(0.90), 충실도 0.83은 일부 답변(`g05`=0.60)이 검색 근거를 벗어남을 시사합니다.

> ⚠️ LLM-judge 점수는 단일 판정자(gpt-4o-mini, temp 0) 기반의 **추정치**로 노이즈가 있으며,
> 6케이스 소표본이라 방향성 지표로 해석해야 합니다. 골든셋을 50+로 키우면 신뢰도가 올라갑니다.

---

## Tier 3 — 검색 정답지(qrels) 반자동 구축 (로컬 LLM 2-채점관)

LLM-judge 추정치를 넘어, 질문마다 **"정답 논문"을 라벨링한 정답지(qrels)**를 만들면 검색 점수를
AI 눈대중 없이 정확·재현 가능하게 잴 수 있습니다. 사람 노동을 최소화하기 위해, **로컬 LLM 채점관
2명**이 후보를 라벨링하고 **둘이 갈리는 것만 사람이** 봅니다.

**연산 분산 (맥 + 윈도우/Tailscale)**
- 맥북(오케스트레이션): MongoDB 풀링 + bge-m3 임베딩(가벼움)
- 윈도우 데스크톱(RTX 4070, Tailscale): Ollama 로 2-채점관 LLM 추론(무거움)

**윈도우 측 준비**
```powershell
# Ollama 설치 후 — 모델 받기 (4비트, 12GB VRAM 적합)
ollama pull qwen2.5:14b-instruct-q4_K_M   # 채점관 A (다국어 추론 강함)
ollama pull gemma2:9b-instruct-q4_K_M      # 채점관 B (계열이 달라 오류 비상관)
# Tailscale 너머에서 접근 가능하도록 0.0.0.0 바인딩
setx OLLAMA_HOST "0.0.0.0:11434"           # 재시작 후 ollama serve
```

**맥 측 실행**
```bash
cd backend
export OLLAMA_BASE_URL="http://<windows-tailscale-ip-or-name>:11434"
python eval/label_qrels.py --check     # 연결/모델 확인
python eval/label_qrels.py --limit 3   # 시범(앞 3문항)
python eval/label_qrels.py             # 전체(30문항)
```

**워크플로**
1. 각 질문 → 영어 확장 → 후보 풀링(벡터 ∪ 키워드, 질문당 ~30개)
2. 채점관 A 전체 → 채점관 B 전체 (GPU 1장이라 모델별 2-패스로 스왑 최소화)
3. 두 채점관의 관련 여부(이진)가 **일치 → 자동 확정**, **불일치 → 사람 큐**
4. 무작위 40쌍 `calibration_sample.json` 의 `human_grade` 를 채운 뒤:
   ```bash
   python eval/calibration_report.py   # 채점관 신뢰도(일치율·kappa) 검증
   ```

**출력** (`backend/eval/qrels/`, gitignore — 사람 검수 후 최종본만 커밋 권장)
- `qrels_draft.json` 자동 확정 정답지 · `disagreements.json` 사람 검토 큐
- `calibration_sample.json` 사람 검증 표본 · `judgments_full.json` 전체 판정 기록

> 키워드 검색은 `documents.content` 텍스트 인덱스(`content_text`)를 쓰며 `pooling.ensure_text_index()`가
> 최초 1회 자동 생성합니다. 이 인덱스는 추후 **하이브리드 검색(Horizon 2)**에도 재사용됩니다.

---

## 지표 목표 (PRD §6.2)

| 지표 | 목표 | Tier |
|---|---|---|
| Crisis Detection Recall | ≥ 0.95 | 1 |
| Context Precision | ≥ 0.80 | 2 |
| Context Recall | ≥ 0.75 | 2 |
| Answer Faithfulness | ≥ 0.90 | 2 |
| Answer Relevancy | ≥ 0.85 | 2 |
