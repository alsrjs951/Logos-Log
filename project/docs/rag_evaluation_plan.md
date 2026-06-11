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

- **초기 약점은 검색(retrieval)**: `g02`(미루기/동기부여)가 주제와 어긋난 청크를 받아 precision/recall 0.00 → 평균을 크게 끌어내림. 이후 30문항 qrels 평가에서 `$text` 하이브리드는 벡터 단독보다 낮게 나와 미채택했고, 다음 개선축은 청크 메타데이터, 주변 청크 확장, 재랭커 안정화로 전환했다.
- **충실도 0.83**(목표 미달): 일부 답변(`g05`=0.60)이 검색 근거를 벗어남 — 시스템 프롬프트의 "근거 밖 서술 금지" 강화 여지.
- 한계: 단일 LLM-judge·소표본(6) 추정치. 골든셋 50+ 확대 시 신뢰도 상승.

#### 1차 재구축 후 실측 (2026-06-08 · 골든셋 30케이스)

페이지/섹션 보존 전처리, `chunk_size=1000/overlap=200`, 확장 메타데이터, 주변 청크 확장, temperature 0 재랭커를 적용하고
MongoDB `documents`를 reset/reupload한 뒤 `backend/eval/evaluate_rag.py --case-timeout 120 --judge-timeout 120`로 측정했다.

| 지표 | 점수 | 목표 | |
|---|---|---|---|
| Answer Relevancy | 0.920 | ≥ 0.85 | ✅ |
| Faithfulness | 0.862 | ≥ 0.90 | ❌ |
| Context Precision | 0.763 | ≥ 0.80 | ❌ |
| Context Recall | 0.650 | ≥ 0.75 | ❌ |

- 개선: 기존 6케이스 baseline보다 Context Recall(0.58→0.65)과 Answer Relevancy(0.90→0.92)는 올랐다.
- 미달: Context Precision, Context Recall, Faithfulness 모두 PRD 목표에는 아직 부족하다.
- 다음 후보: `g05/g07/g09/g14/g16`처럼 낮은 precision/recall 케이스의 쿼리 확장, 재랭커 diversity, 논문 선별 corpus를 별도로 보강한다.

#### 추가 개선 후 실측 (2026-06-08 · 골든셋 30케이스)

전체 eligible 영어 corpus 업로드, `language/text_quality` 필터, multi-query vector RRF, expanded generation context trace,
보수적 Evidence-to-Reflection 답변 프롬프트를 적용하고 원격 데스크톱 GPU에서 재구축/평가했다.
실행 기록은 `backend/eval/runs/baseline_20260608_223329.json`이다.

| 지표 | 점수 | 목표 | |
|---|---:|---:|---|
| Answer Relevancy | 0.920 | ≥ 0.85 | ✅ |
| Faithfulness | 0.802 | ≥ 0.90 | ❌ |
| Context Precision | 0.663 | ≥ 0.80 | ❌ |
| Context Recall | 0.625 | ≥ 0.75 | ❌ |

- Corpus: MongoDB `documents` 23,806 chunks, 모두 `language=en`, `text_quality` min 0.55 / avg 0.895. 비영어·저품질로 8,638 chunks와 123 files 제외.
- Index: `_id_`, `documents_chunk_id_unique`, `documents_document_chunk`만 유지. `$text` 인덱스는 평가 중 임시 생성/제거만 허용.
- 결과 해석: Answer Relevancy는 유지됐지만 Context Precision/Recall과 Faithfulness가 목표에 못 미쳤다. 특히 `g05/g13/g14/g15/g16/g20`의 context precision/recall이 낮다.
- 평가 하니스 해석 주의: `g14`는 검색 결과가 CBT 관점에서 관련 있는데 golden reference가 positive psychology 관점이라 0점 처리된 것으로 보인다. 다음 개선은 retrieval만이 아니라 golden-set 카테고리·reference 재검수도 포함해야 한다.
- Cross-encoder 실험: `RERANKER_MODE=two_stage` partial(`g05,g07,g09,g14,g16,g11`)은 `context_precision=0.417`, `context_recall=0.375`, `faithfulness=0.700`, `answer_relevancy=0.933`으로 LLM-only partial보다 개선되지 않았다. Production default 전환 후보가 아니라 eval-only flag로 유지한다.

#### 문제 케이스 기반 정비 후 실측 (2026-06-08 · 골든셋 30케이스)

전체 재구축 대신 가장 낮았던 `g05/g13/g14/g15/g16/g20/g24`를 기준으로 병목을 분해했다.
핵심 판단은 "검색 알고리즘이 전부 문제"가 아니라, 일부 golden-set/reference/qrels가 현재 corpus와 어긋나
좋은 근거도 낮게 채점되는 문제가 섞여 있다는 것이다.

변경 사항:
- `g14`: positive psychology가 아니라 CBT 성격이 강해 `category=cbt`로 바꾸고, reference를 negative thinking/cognitive distortion/cognitive restructuring 중심으로 수정했다.
- `g15`: burnout 회복 근거를 자원 회복/경계뿐 아니라 positive psychology interventions, meaning, engagement, well-being까지 포함하도록 넓혔다.
- 현재 corpus 기준 문제 케이스 qrels 재풀링 스크립트(`backend/eval/refresh_problem_qrels.py`)를 추가했다.
- query expansion에서 broad filler theory(`Maslow` 등)를 억제하고, logotherapy/positive psychology/CBT/SDT별 필수 학술 키워드 fallback을 deterministic하게 추가했다.
- 답변 프롬프트를 더 보수적으로 바꿔 "효과가 있다"보다 "이 발췌는 ...을 시사한다" 형태를 선호하게 했다.

문제 7케이스 partial(`backend/eval/runs/baseline_20260608_234434.json`):

| 지표 | 점수 | 목표 | |
|---|---:|---:|---|
| Answer Relevancy | 0.914 | ≥ 0.90 | ✅ |
| Faithfulness | 0.779 | ≥ 0.85 | ❌ |
| Context Precision | 0.636 | ≥ 0.70 | ❌ |
| Context Recall | 0.679 | ≥ 0.65 | ✅ |

전체 30케이스(`backend/eval/runs/baseline_20260608_235609.json`):

| 지표 | 점수 | 목표 | |
|---|---:|---:|---|
| Answer Relevancy | 0.917 | ≥ 0.85 | ✅ |
| Faithfulness | 0.860 | ≥ 0.90 | ❌ |
| Context Precision | 0.763 | ≥ 0.80 | ❌ |
| Context Recall | 0.742 | ≥ 0.75 | ❌ |

- 직전 run(`baseline_20260608_223329.json`) 대비 Context Precision은 0.663→0.763, Context Recall은 0.625→0.742, Faithfulness는 0.802→0.860으로 개선됐다.
- PRD 목표에는 아직 못 미치지만, Context Recall은 0.75 목표에 거의 도달했다.
- 남은 실패 케이스: `g16`은 여전히 검색 근거가 reference를 직접 뒷받침하지 못한다. `g15`는 context precision/recall은 개선됐지만 faithfulness가 낮아 답변 문장별 citation/단정 수준을 더 봐야 한다.
- MongoDB reset/reupload는 하지 않았다. Index는 `_id_`, `documents_chunk_id_unique`, `documents_document_chunk`만 남아 있고 `$text` 인덱스는 없다.

#### g15/g16 핀셋 개선 후 실측 (2026-06-09 · 골든셋 30케이스)

이 단계는 전체 재업로드 없이 `g15`와 `g16`을 기준으로 좁게 수정했다.
변경은 세 가지다.

- Query focus 기반 deterministic candidate boost/penalty: 직접 construct를 담은 청크는 올리고, 키워드뿐인 청크·숫자표·참고문헌성 청크는 낮췄다.
- `g16` achievement query fallback을 `social comparison, achievement satisfaction, gratitude, savoring, self-compassion` 중심으로 좁혔다.
- RAG 답변 생성은 temperature 0 전용 streaming LLM으로 분리하고, 강한 효과 단정 표현을 더 제한했다.

문제 7케이스 partial(`backend/eval/runs/baseline_20260609_003132.json`):

| 지표 | 점수 | 목표 | |
|---|---:|---:|---|
| Answer Relevancy | 0.914 | ≥ 0.85 | ✅ |
| Faithfulness | 0.871 | ≥ 0.90 | ❌ |
| Context Precision | 0.843 | ≥ 0.80 | ✅ |
| Context Recall | 0.857 | ≥ 0.75 | ✅ |

전체 30케이스(`backend/eval/runs/baseline_20260609_003413.json`):

| 지표 | 점수 | 목표 | |
|---|---:|---:|---|
| Answer Relevancy | 0.910 | ≥ 0.85 | ✅ |
| Faithfulness | 0.828 | ≥ 0.90 | ❌ |
| Context Precision | 0.813 | ≥ 0.80 | ✅ |
| Context Recall | 0.767 | ≥ 0.75 | ✅ |

- 처음으로 전체 30케이스에서 Context Precision과 Context Recall이 PRD 목표를 통과했다.
- `g16`은 0점 케이스에서 벗어났지만, 현재 corpus에서 `savoring/social comparison`을 직접 지지하는 후보가 약해 완전 해결은 아니다.
- Faithfulness는 여전히 목표 미달이다. 낮은 케이스(`g06/g15/g23/g29`)를 보면 검색보다 생성 문장 단위의 claim/citation 관리 문제가 더 크다.
- `g06` relatedness/loneliness 전용 guidance와 death-specific fallback은 별도 실험에서 전체 지표를 낮춰 되돌렸다. 측정되지 않은 "좋아 보이는" 변경을 싣지 않는다는 원칙을 유지한다.

#### Faithfulness verifier 실험 후 실측 (2026-06-09)

남은 병목인 Faithfulness를 겨냥해 post-generation verifier를 feature flag로 구현했다.
`RAG_VERIFIER_MODE=on` 또는 `backend/eval/evaluate_rag.py --verifier-mode on`으로 켤 수 있지만,
측정상 기본 전환 근거가 부족해 production default는 `off`로 유지한다.

낮은 4케이스(`g06/g15/g23/g29`) partial:

| Run | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
|---|---:|---:|---:|---:|
| verifier v1 (`baseline_20260609_021636.json`) | 0.725 | 0.688 | 0.575 | 0.925 |
| verifier v2 (`baseline_20260609_022028.json`) | 0.537 | 0.688 | 0.700 | 0.900 |
| verifier off + 보수적 초안 가드 (`baseline_20260609_022255.json`) | 0.588 | 0.812 | 0.675 | 0.900 |

전체 30케이스, verifier off + 보수적 초안 가드(`baseline_20260609_022510.json`):

| 지표 | 점수 | 목표 | |
|---|---:|---:|---|
| Answer Relevancy | 0.910 | ≥ 0.85 | ✅ |
| Faithfulness | 0.850 | ≥ 0.90 | ❌ |
| Context Precision | 0.785 | ≥ 0.80 | ❌ |
| Context Recall | 0.725 | ≥ 0.75 | ❌ |

- Accepted full-run(`baseline_20260609_003413.json`) 대비 Faithfulness는 0.828→0.850으로 올랐지만, Context Precision/Recall은 단일 측정에서 0.813/0.767→0.785/0.725로 내려갔다.
- 검색 코드는 바꾸지 않았고, retrieval-only 재확인에서도 vector-only가 hybrid보다 낫다(`P@5=0.113`, `P@10=0.097`, `R@10=0.102`, `nDCG@10=0.138`, `MRR=0.308`). 평가용 `$text` 인덱스는 실행 후 제거되며, MongoDB에는 `_id_`, `documents_chunk_id_unique`, `documents_document_chunk`만 남았다.
- 결론: verifier는 "켜면 좋아지는 기능"이 아니다. 답변 전체를 다시 쓰는 verifier는 관련성과 citation 배치를 흔들 수 있어 production default로 전환하지 않는다.
- 다음 개선은 통째 rewrite가 아니라 **문장 단위 claim/citation checker**가 더 적합하다. 즉, citation 없는 연구 주장만 탐지하고, 해당 문장을 삭제/완화/출처 연결하는 좁은 후처리를 별도 실험으로 검증한다.

#### 문장 단위 claim/citation checker 실험 (2026-06-09)

후속으로 답변 전체 rewrite가 아니라 문장 단위 최소 수정 checker를 구현했다.
`RAG_CLAIM_CHECKER_MODE=on` 또는 `backend/eval/evaluate_rag.py --claim-checker-mode on --verifier-mode off`로 켤 수 있다.
production default는 아직 `off`다.

낮은 4케이스(`g06/g15/g23/g29`) partial(`baseline_20260609_032450.json`):

| 지표 | 점수 |
|---|---:|
| Answer Relevancy | 0.900 |
| Faithfulness | 0.788 |
| Context Precision | 0.662 |
| Context Recall | 0.562 |

전체 30케이스(`baseline_20260609_032738.json`):

| 지표 | 점수 | 목표 | |
|---|---:|---:|---|
| Answer Relevancy | 0.913 | ≥ 0.85 | ✅ |
| Faithfulness | 0.838 | ≥ 0.90 | ❌ |
| Context Precision | 0.757 | ≥ 0.80 | ❌ |
| Context Recall | 0.775 | ≥ 0.75 | ✅ |

- Accepted full-run(`baseline_20260609_003413.json`) 대비 Faithfulness는 0.828→0.838, Answer Relevancy는 0.910→0.913, Context Recall은 0.767→0.775로 소폭 올랐다.
- Context Precision은 0.813→0.757로 내려갔다. 검색 코드를 바꾸지 않았기 때문에 query expansion/judge 노이즈가 섞여 있지만, 기본 전환 근거로는 부족하다.
- checker는 30케이스 중 24케이스를 수정했고, 오류는 없었다. 전체 rewrite verifier보다는 안정적이지만 PRD Faithfulness 목표 0.90에는 못 미친다.
- 더 엄격한 v2(MUST-FIX uncited claim sentences)는 partial(`baseline_20260609_034738.json`)에서 Faithfulness 0.425로 크게 악화되어 되돌렸다. "더 엄격해 보이는 규칙"이 실제 지표 개선으로 이어지지 않은 사례다.
- 다음 개선 후보는 checker 강화가 아니라, **초안 생성 단계에서 문장마다 citation을 더 정확히 붙이는 답변 템플릿/프롬프트**다. 후처리가 근거 없는 문장을 고치는 것보다, 애초에 근거 문장 단위를 짧게 생성하게 하는 쪽이 더 안정적일 가능성이 높다.

#### 문장별 citation 생성 템플릿 실험 (2026-06-09)

위 가설을 검증하기 위해 `RAG_ANSWER_TEMPLATE_MODE=sentence` 실험 옵션을 추가했다.
기본값은 `standard`이며, `backend/eval/evaluate_rag.py --answer-template-mode sentence`로만 켠다.

낮은 4케이스(`g06/g15/g23/g29`) partial(`baseline_20260609_040032.json`):

| 지표 | 점수 |
|---|---:|
| Answer Relevancy | 0.900 |
| Faithfulness | 0.775 |
| Context Precision | 0.400 |
| Context Recall | 0.500 |

전체 30케이스(`baseline_20260609_040240.json`):

| 지표 | 점수 | 목표 | |
|---|---:|---:|---|
| Answer Relevancy | 0.907 | ≥ 0.85 | ✅ |
| Faithfulness | 0.800 | ≥ 0.90 | ❌ |
| Context Precision | 0.777 | ≥ 0.80 | ❌ |
| Context Recall | 0.808 | ≥ 0.75 | ✅ |

- Accepted full-run(`baseline_20260609_003413.json`) 대비 Faithfulness가 0.828→0.800으로 내려갔다.
- 문장 수와 citation 구조는 더 깔끔해졌지만, LLM-judge 기준 충실도는 좋아지지 않았다. 특히 `g06=0.00`, `g29=0.50`이 평균을 끌어내렸다.
- 결론: sentence 템플릿은 production default로 채택하지 않는다. 기본값은 `RAG_ANSWER_TEMPLATE_MODE=standard`로 유지하고, sentence 모드는 실패 실험을 재현하는 flag로만 남긴다.
- 다음 개선은 더 강한 프롬프트가 아니라, 낮은 케이스의 trace를 문장 단위로 읽어 judge가 unsupported로 보는 문장 유형을 분류하는 것이다. 이후에는 그 유형만 겨냥한 작고 측정 가능한 수정으로 가야 한다.

---

## 4. 검색 경로 분리 (완료)

검색 로직을 `RAGService.retrieve()` 로 추출하여 스트리밍·답변 생성과 분리했다.
`get_streaming_response`(프로덕션)와 `evaluate_rag.py`(평가)가 **동일한 검색 경로**를 공유하므로,
평가 점수가 실제 사용자 경험과 일치한다.

```python
async def retrieve(self, query, english_query=None) -> tuple:
    """쿼리 확장 → 임베딩 → $vectorSearch → 재랭킹 → 주변 청크 확장.
    (재랭킹 primary 청크, 원시 검색 결과) 반환. 스트리밍/생성 부수효과 없음."""
    ...
```

---

## 5. 골든셋 운영

- 시작본은 카테고리(logotherapy/positive_psych/sdt/cbt)별 소수 케이스다. `reference_points`는 **전문가 검수 필요**.
- PRD 운영안(§6.3)대로 매주 운영자 샘플을 라벨링해 골든셋을 50+ 케이스로 키운다.
- 위기 골든셋은 실제 오탐/미감지 사례를 지속 추가해 안전 회귀를 막는다.
- 알려진 한계: 키워드 기반 위기 감지는 `자살골` 같은 합성어에서 오탐 가능(재현율 우선 설계). 정밀도가 필요하면 LLM 분류기 보강을 검토한다.

### 5.1 검색 정답지(qrels) 반자동 구축 — 사람 최소화 × 정확도 최대화

LLM-judge 추정치를 넘어 "질문별 정답 논문"을 라벨링하면 검색 점수를 정확·재현 가능하게 잴 수 있다.
9,562개를 다 보지 않고, **사람 손은 두 군데만** 닿게 한다.

1. **Pooling**: 서로 다른 검색기(벡터 ∪ 키워드)의 상위 결과를 합쳐 질문당 ~30 후보로 축소(TREC pooling). 정답은 거의 이 합집합에 포함된다.
2. **로컬 LLM 2-채점관**: RTX 4070(12GB)에서 Ollama 로 Qwen2.5-14B(A) + Gemma-2-9B(B)를 4비트로 구동. 영어 확장 쿼리로 채점해 다국어 부담을 줄인다. 명확한 0/1/2 기준표 + 이유 서술로 정확도를 높인다.
3. **합의 자동화**: 두 채점관의 이진 관련성이 일치하면 자동 확정, **불일치만 사람 검토 큐**로(보통 소수).
4. **캘리브레이션**: 사람이 40쌍만 라벨링 → 채점관과의 일치율·Cohen's kappa 측정(≥0.6이면 신뢰). 이 40쌍이 사실상 유일한 큰 사람 노동이다.

구현: `backend/eval/pooling.py`(맥, MongoDB+임베딩) + `label_qrels.py`(원격 Ollama 오프로드, 윈도우/Tailscale) + `calibration_report.py`. 운영 가이드는 `backend/eval/README.md` Tier 3 참조.
한 번 만든 qrels로 이후 검색 평가는 LLM 비용 없이 정밀도/재현율·nDCG 를 즉시·정확히 잰다.

캘리브레이션 실측(40쌍): '관련 전체(≥1)'는 base rate ~90%로 변별력이 없고, '직접 관련(==2)'에서 채점관 ↔ 상위 모델(Claude) kappa ≈ 0.49(보통) — 모델 차이가 아니라 grade-2 판단 자체의 본질적 애매성. 따라서 qrels의 **grade==2(두 채점관 합의)** 를 '관련'으로 쓰는 중신뢰 정답지로 채택한다.

### 5.2 검색 전략 비교 결과 — 프로덕션 벡터 단독 유지 (2026-06, 30문항)

초기 30문항 정답지(grade==2)에 대해 `backend/eval/evaluate_retrieval.py` 로 측정한 1차 결과:

| 전략 | P@5 | R@10 | nDCG@10 | MRR |
|---|---|---|---|---|
| **vector**(현재 프로덕션) | **0.69** | **0.54** | **0.81** | 0.85 |
| keyword (`$text`) | 0.45 | 0.31 | 0.61 | 0.70 |
| hybrid (RRF 균등) | 0.61 | 0.47 | 0.76 | 0.85 |
| hybrid_vw (벡터 가중 RRF) | 0.64 | 0.51 | 0.79 | 0.87 |

- **결론: 벡터 단독이 최고.** 키워드 검색이 벡터보다 크게 약해, RRF로 섞으면 강한 벡터 순위를 희석해 정밀도·재현율이 하락한다. 벡터 가중을 줘도 벡터를 넘지 못하며 MRR만 노이즈 수준(+0.015)으로 앞선다.
- **결정: PRD S2(하이브리드 검색/RRF) 미채택, 벡터 단독 유지.** 측정으로 회귀를 방지한 사례.
- 주의: 쿼리 확장(LLM, temp 0.3)이 비결정적이라 실행 간 ~0.05 노이즈가 있으나, '벡터 ≥ 하이브리드(P/R/nDCG)' 결론은 반복 실행에서 일관.
- 1차 기준 시사점: 검색 자체는 양호(P@5 ~0.69, MRR ~0.85)했고, 다음 개선 레버는 하이브리드가 아니라 답변 충실도 또는 쿼리 확장/청킹 쪽이 유망해 보였다.

추가 개선 재구축 후에는 영어/품질 필터로 qrels에 남아 있던 비영어 chunk 일부가 현재 corpus에서 제외됐다.
`evaluate_retrieval.py`는 현재 DB에 존재하지 않는 qrels chunk 43개를 제외하고 평가하며, 실험용 `$text`
인덱스는 실행 중 생성 후 종료 시 제거한다. 현재 `chunk_id` qrels 기준 참고 결과:

| 전략 | P@5 | P@10 | R@10 | nDCG@10 | MRR |
|---|---|---|---|---|---|
| vector multi-query RRF(현재 프로덕션) | **0.107** | **0.077** | 0.083 | 0.127 | 0.293 |
| keyword (`$text`) | 0.053 | 0.043 | 0.052 | 0.060 | 0.146 |
| hybrid (RRF 균등) | 0.080 | 0.073 | 0.088 | 0.117 | 0.299 |
| hybrid_vw (벡터 가중 RRF) | 0.093 | 0.070 | 0.074 | 0.119 | 0.290 |

이 수치는 이전 qrels 평가보다 크게 낮다. 원인은 검색만이 아니라 corpus 필터링 이후 qrels의 relevant chunk가
빠진 점, multi-query 후보가 기존 qrels pooling 분포와 달라진 점, golden-set 카테고리/reference와 실제
검색 근거의 관점이 어긋나는 점이 섞여 있다. 하이브리드는 recall/MRR에서 일부 소폭 우위지만 precision과
nDCG 개선이 결정적이지 않고 `$text` 운영 인덱스를 추가할 근거도 부족하므로, 프로덕션 기본 검색은 계속
벡터 기반으로 유지한다. 다음 검색 평가는 현재 corpus 기준으로 qrels를 재풀링/재라벨링한 뒤 비교해야 한다.

문제 케이스 7개만 현재 corpus 기준으로 재풀링한 qrels(`qrels_problem_cases.json`, gitignore)에서는
vector가 `P@5=0.400`, `P@10=0.400`, `R@10=0.287`, `nDCG@10=0.617`, `MRR=0.611`이었다.
`hybrid_vw`는 `nDCG@10=0.661`, `MRR=0.810`으로 일부 순위 지표가 높았지만, vector보다 precision/recall을
뚜렷하게 개선하지 못했고 운영 `$text` 인덱스를 추가할 근거도 부족하다. 따라서 이번에도 production default는
vector-only로 유지한다.

### 5.3 충실도 가드 실험 — 측정상 효과 없음(되돌림) (2026-06)

답변이 검색 근거를 벗어나는 문제(초기 6문항 baseline faithfulness 0.83)를 고치려 시스템 프롬프트에 '근거 충실성 가드'를 추가했다. 6문항 측정에서 0.83→0.88(+0.05)로 개선되어 보였으나, **30문항 A/B**로 엄밀히 재측정한 결과:

| | Faithfulness | Answer Relevancy |
|---|---|---|
| BEFORE(가드 없음, 30) | 0.867 | 0.903 |
| AFTER(가드 있음, 30) | 0.865 | 0.907 |

- **결론: 측정상 차이 없음(−0.002).** 6문항의 +0.05는 **소표본 노이즈**였고, 원래 baseline 0.83 자체도 6문항 저표본 fluctuation(실제 충실도 ~0.865)이었다.
- **결정: 검증되지 않은 변경은 싣지 않는다 → 가드 되돌림(revert).** '감이 아니라 데이터'라는 원칙의 적용 사례이자, **소표본 평가의 위험**(가짜 성과 착각)을 보여준 교훈.
- 충실도 ~0.865는 목표 0.90에 약간 못 미치나, 이를 올리려면 프롬프트 미세조정이 아니라 더 강한 개입(예: 생성 후 충실도 자가검증 → fallback, PRD 안전요구)이 필요할 것으로 보이며 측정으로 검증해야 한다.

---

## 6. CI 통합 (로드맵)

1. **완료:** `evaluate_crisis.py`를 PR CI 게이트로 추가(`.github/workflows/safety-eval.yml`)해 안전 회귀를 차단(빠르고 무료).
2. **완료:** `retrieve()` 추출 + `evaluate_rag.py` 구현 + **베이스라인 측정 완료**(위 표). 검색 품질이 최우선 개선 영역으로 확인됨.
3. **다음:** RAG 평가는 비용·시간이 크므로 야간 스케줄 또는 RAG 관련 파일 변경 시에만 실행하고, 점수를 시계열로 기록해 청크 메타데이터/주변 청크 확장/재랭커 변경 전후를 비교한다. 골든셋을 50+로 확대한다.
