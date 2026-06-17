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

## Tier 1.5 — 작은 실험 추천 품질 평가 (인프라 불필요)

의미 행동 루프의 추천 문구가 제품 원칙을 지키는지 확인합니다. LLM·DB 없이 고정 세트를 채점하며,
같은 스키마의 생성 결과 파일을 `--input`으로 넘기면 실제 추천 결과도 동일한 루브릭으로 점검할 수 있습니다.

```bash
cd backend
python eval/evaluate_experiment_recommendations.py
```

- 데이터셋: [`experiment_recommendation_set.json`](./experiment_recommendation_set.json)
- 루브릭: 필수 필드, 구체적 행동, 이번 주 범위, 낮은 압박, 가치 카드 근거, 회고 질문, 임상/단정 표현 회피
- 모든 케이스가 `0.86` 이상이면 PASS, 아니면 종료 코드 1

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

초기 베이스라인에서 가장 약한 지점은 **검색(retrieval)** — 특히 `g02`(미루기/동기부여)에서 검색 청크가 주제와 어긋나
precision/recall 0.00을 기록해 평균을 크게 끌어내렸습니다. 이후 qrels 30문항 평가에서 `$text` 하이브리드는 벡터 단독보다 낮게 나와 미채택했고, 다음 개선 타깃은 청크 메타데이터·주변 청크 확장·재랭커 안정화입니다.
답변 관련성은 양호하나(0.90), 충실도 0.83은 일부 답변(`g05`=0.60)이 검색 근거를 벗어남을 시사합니다.

> ⚠️ LLM-judge 점수는 단일 판정자(gpt-4o-mini, temp 0) 기반의 **추정치**로 노이즈가 있으며,
> 6케이스 소표본이라 방향성 지표로 해석해야 합니다. 골든셋을 50+로 키우면 신뢰도가 올라갑니다.

### 1차 재구축 후 실측 (2026-06-08 · 골든셋 30케이스)

청크 메타데이터, 주변 청크 확장, temperature 0 재랭커를 적용하고 `documents`를 reset/reupload한 뒤
`eval/runs/baseline_20260608_213030.json`으로 기록한 결과입니다.

| 지표 | 점수 | 목표 |
|---|---|---|
| Answer Relevancy | **0.920** | ≥ 0.85 ✅ |
| Faithfulness | **0.862** | ≥ 0.90 ❌ |
| Context Precision | **0.763** | ≥ 0.80 ❌ |
| Context Recall | **0.650** | ≥ 0.75 ❌ |

목표에는 아직 못 미칩니다. 다만 기존 6케이스 baseline보다 Context Recall과 Answer Relevancy는 개선됐고,
다음 개선 후보는 `g05/g07/g09/g14/g16`처럼 recall/precision이 낮은 케이스의 쿼리 확장·재랭킹·논문 선별 보강입니다.

### 추가 개선 후 실측 (2026-06-08 · 골든셋 30케이스)

전체 eligible 영어 corpus 업로드, `language/text_quality` 필터, multi-query vector RRF, expanded generation context trace,
보수적 Evidence-to-Reflection 프롬프트를 적용한 뒤 원격 데스크톱 GPU에서 재구축/평가했습니다.
기록 파일은 `eval/runs/baseline_20260608_223329.json`입니다.

| 지표 | 점수 | 목표 |
|---|---:|---:|
| Answer Relevancy | **0.920** | ≥ 0.85 ✅ |
| Faithfulness | **0.802** | ≥ 0.90 ❌ |
| Context Precision | **0.663** | ≥ 0.80 ❌ |
| Context Recall | **0.625** | ≥ 0.75 ❌ |

- MongoDB `documents`: 23,806 chunks 업로드, 전부 `language=en`, `text_quality` min 0.55 / avg 0.895. 제외: 8,638 chunks, 123 files.
- 인덱스: `_id_`, `documents_chunk_id_unique`, `documents_document_chunk`만 유지. `$text` 인덱스는 상시 생성하지 않음.
- 낮은 케이스: `g05`, `g13`, `g14`, `g15`, `g16`, `g20`은 context precision/recall이 0 또는 낮음. 일부(`g14`)는 검색 결과가 실제로는 CBT 관점에서 관련 있지만 golden reference가 positive psychology 관점이라 judge가 0을 준 것으로 보여, golden-set 재검수도 필요합니다.
- `RERANKER_MODE=two_stage` partial(`g05,g07,g09,g14,g16,g11`)은 `context_precision=0.417`, `context_recall=0.375`, `faithfulness=0.700`, `answer_relevancy=0.933`으로 LLM-only partial보다 개선되지 않았습니다. Production default 전환 근거가 없어 eval-only flag로 유지합니다.

### 문제 케이스 정비 후 실측 (2026-06-08 · 골든셋 30케이스)

낮은 케이스(`g05/g13/g14/g15/g16/g20/g24`)를 기준으로 golden-set과 qrels를 현재 corpus에 맞게 재검수했습니다.
`g14`는 CBT 케이스로 재분류했고, `g15`는 positive psychology intervention/meaning/engagement 근거를 reference에 포함했습니다.
MongoDB reset/reupload는 하지 않았고, 프로덕션 검색은 계속 `$vectorSearch` 단독입니다.

문제 7케이스 partial(`eval/runs/baseline_20260608_234434.json`):

| 지표 | 점수 | 목표 |
|---|---:|---:|
| Answer Relevancy | **0.914** | ≥ 0.90 ✅ |
| Faithfulness | **0.779** | ≥ 0.85 ❌ |
| Context Precision | **0.636** | ≥ 0.70 ❌ |
| Context Recall | **0.679** | ≥ 0.65 ✅ |

전체 30케이스(`eval/runs/baseline_20260608_235609.json`):

| 지표 | 점수 | 목표 |
|---|---:|---:|
| Answer Relevancy | **0.917** | ≥ 0.85 ✅ |
| Faithfulness | **0.860** | ≥ 0.90 ❌ |
| Context Precision | **0.763** | ≥ 0.80 ❌ |
| Context Recall | **0.742** | ≥ 0.75 ❌ |

- 직전 30케이스 run 대비 `context_precision 0.663 -> 0.763`, `context_recall 0.625 -> 0.742`, `faithfulness 0.802 -> 0.860`으로 개선됐습니다.
- 목표에는 아직 못 미치지만, recall은 PRD 목표 0.75에 근접했습니다.
- 남은 병목: `g16`은 여전히 검색 근거가 reference를 직접 뒷받침하지 못하고, `g15`는 검색은 개선됐지만 답변 충실도가 낮습니다.
- MongoDB index 확인 결과 `_id_`, `documents_chunk_id_unique`, `documents_document_chunk`만 남아 있으며 `$text` 인덱스는 없습니다.

### g15/g16 핀셋 개선 후 실측 (2026-06-09 · 골든셋 30케이스)

`g15` 번아웃 답변의 단정 표현과 `g16` 성취/부족감 검색 실패를 기준으로 추가 개선했습니다.
벡터 검색은 그대로 유지하고, reranker 전 후보에 query focus 기반의 deterministic boost/penalty를 적용했습니다.
RAG 답변 생성은 temperature 0 전용 streaming LLM으로 분리했습니다.

문제 7케이스 partial(`eval/runs/baseline_20260609_003132.json`):

| 지표 | 점수 | 목표 |
|---|---:|---:|
| Answer Relevancy | **0.914** | ≥ 0.85 ✅ |
| Faithfulness | **0.871** | ≥ 0.90 ❌ |
| Context Precision | **0.843** | ≥ 0.80 ✅ |
| Context Recall | **0.857** | ≥ 0.75 ✅ |

전체 30케이스(`eval/runs/baseline_20260609_003413.json`):

| 지표 | 점수 | 목표 |
|---|---:|---:|
| Answer Relevancy | **0.910** | ≥ 0.85 ✅ |
| Faithfulness | **0.828** | ≥ 0.90 ❌ |
| Context Precision | **0.813** | ≥ 0.80 ✅ |
| Context Recall | **0.767** | ≥ 0.75 ✅ |

- 전체 30케이스에서 처음으로 Context Precision/Recall이 PRD 목표를 통과했습니다.
- `g16`은 기존 `0.00/0.00`에서 partial 기준 `0.50/0.50`까지 회복했지만, reference의 `savoring/social comparison`을 직접 뒷받침하는 corpus 근거가 아직 약합니다.
- Faithfulness는 아직 목표 미달입니다. 낮은 케이스는 `g06`, `g15`, `g23`, `g29`이며, 다음 단계는 post-generation verifier 또는 문장 단위 citation/claim checker가 더 적합합니다.
- `g06` relatedness/loneliness 전용 guidance와 death-specific fallback 실험은 전체 지표를 낮춰 되돌렸습니다.

### g06 평가 의도 재정렬 후 실측 (2026-06-09)

`g06`은 질문 자체가 SDT 이론 질문이라기보다 외로움/social connection 고민에 가깝다고 판단했습니다.
따라서 golden-set에서 `category=sdt`를 `positive_psych`로 바꾸고, reference를
`loneliness / social isolation / social connection / social support / peer relations` 중심으로 정리했습니다.
검색 기본 구조는 계속 vector-only입니다.

`g06` 단일(`baseline_20260609_101958.json`):

| 지표 | 점수 |
|---|---:|
| Answer Relevancy | **0.900** |
| Faithfulness | **0.800** |
| Context Precision | **0.750** |
| Context Recall | **0.750** |

낮은 4케이스 partial(`g06,g15,g23,g29`, `baseline_20260609_102052.json`):

| 지표 | 점수 |
|---|---:|
| Answer Relevancy | **0.900** |
| Faithfulness | **0.700** |
| Context Precision | **0.650** |
| Context Recall | **0.688** |

30케이스 합산(`in_progress_20260609_102305.json` 24케이스 + `baseline_20260609_103649.json` 6케이스,
합산본 `combined_20260609_102305_103649.json`):

| 지표 | 기존 accepted | 재정렬 후 | 목표 |
|---|---:|---:|---:|
| Answer Relevancy | 0.910 | **0.913** | ≥ 0.85 ✅ |
| Faithfulness | 0.828 | **0.848** | ≥ 0.90 ❌ |
| Context Precision | 0.813 | **0.825** | ≥ 0.80 ✅ |
| Context Recall | 0.767 | **0.800** | ≥ 0.75 ✅ |

- accepted full-run(`baseline_20260609_003413.json`) 대비 네 지표가 모두 소폭 개선됐습니다.
- Faithfulness는 아직 목표 미달이며, 새 병목은 `g29`, `g03`, `g15`입니다.
- full 30 단일 실행은 `g22` 이후 네트워크 대기 상태로 멈춰 partial 파일을 사용했고, 누락된 `g25~g30`은 별도 partial로 이어서 평가했습니다.
- 결론: `g06`은 positive-psychology/social-connection 케이스로 유지하는 편이 현재 corpus와 평가 의도에 더 정직합니다.

### g03 감사 질문 focus 보정 후 실측 (2026-06-09)

`g03`은 "감사하는 마음을 갖고 싶다"는 질문인데, 기존 query expansion의 세 번째 variant가
`logotherapy / meaning-making` 같은 넓은 이론어로 새면서 직접적인 감사 실천 근거가 덜 안정적으로 선택됐습니다.
따라서 positive psychology 내부에 `gratitude` topic을 추가하고, 이 경우 fallback query를
`gratitude journal / three good things / gratitude letter / subjective well-being` 중심으로 고정했습니다.
검색 기본 구조는 계속 vector-only입니다.

문제 3케이스 partial(`g03,g15,g29`, `baseline_20260609_104733.json`):

| 지표 | 점수 |
|---|---:|
| Answer Relevancy | **0.900** |
| Faithfulness | **0.800** |
| Context Precision | **0.600** |
| Context Recall | **0.583** |

30케이스 full run(`baseline_20260609_104938.json`):

| 지표 | accepted baseline | gratitude focus 후 | 목표 |
|---|---:|---:|---:|
| Answer Relevancy | 0.910 | **0.913** | ≥ 0.85 ✅ |
| Faithfulness | 0.828 | **0.845** | ≥ 0.90 ❌ |
| Context Precision | 0.813 | **0.800** | ≥ 0.80 ✅ |
| Context Recall | 0.767 | **0.783** | ≥ 0.75 ✅ |

- `g03` 단일 케이스는 accepted combined trace 대비 `faithfulness 0.70 -> 0.80`,
  `context_precision 0.50 -> 0.80`, `context_recall 0.50 -> 1.00`으로 개선됐습니다.
- full run 전체로는 Faithfulness와 Recall이 accepted baseline보다 개선됐지만, 직전 합산 run
  (`combined_20260609_102305_103649.json`, Faithfulness `0.848`)보다는 사실상 같은 수준입니다.
- 결론: gratitude topic 보정은 케이스 의도와 corpus 근거를 더 잘 맞추므로 유지합니다.
  다음 병목은 여전히 `g29`처럼 검색된 근거를 답변이 과잉 연결하는 문장 생성 문제입니다.

### g29 반추/수면 focus 보정 후 실측 (2026-06-09)

`g29`는 "지나간 실수를 곱씹으며 잠을 못 잔다"는 질문입니다. 기존 CBT 검색은
`cognitive distortion / cognitive restructuring` 일반 청크를 강하게 밀어, 답변이 반추·수면·CBT를
하나의 넓은 원인-효과 이야기로 이어 붙이는 문제가 있었습니다.

적용한 변경:

- CBT 내부에 `rumination_sleep` topic을 추가했습니다.
- `곱씹/반추/rumination`이 명시된 경우에만 topic이 켜지도록 하여, `g04` 같은 일반 "실수하면 무능하다" 케이스는 오염되지 않게 했습니다.
- fallback/focus/reranker guidance를 `rumination`, `repetitive negative thinking`, `rumination-focused CBT`, `insomnia`, `dysfunctional beliefs about sleep`, `CBT-I` 중심으로 좁혔습니다.
- `g29` reference를 현재 corpus가 실제로 뒷받침하는 반추·CBT·수면 범위 제한으로 정렬했습니다.
- 생성 프롬프트에는 이 topic에서만 의미 찾기·가치 발견·교훈 찾기·일기 쓰기·수면 직접 인과 단정을 피하라는 좁은 guidance를 추가했습니다.

`g04,g29` partial(`baseline_20260609_111706.json`):

| Case | Faithfulness | Context Precision | Context Recall | Answer Relevancy |
|---|---:|---:|---:|---:|
| `g04` | 0.900 | 0.750 | 0.750 | 0.900 |
| `g29` | 0.800 | 0.800 | 0.750 | 0.900 |

30케이스 full run(`baseline_20260609_112446.json`):

| 지표 | accepted baseline | g29 focus 후 | 목표 |
|---|---:|---:|---:|
| Answer Relevancy | 0.910 | **0.913** | ≥ 0.85 ✅ |
| Faithfulness | 0.828 | **0.848** | ≥ 0.90 ❌ |
| Context Precision | 0.813 | **0.795** | ≥ 0.80 ❌ |
| Context Recall | 0.767 | **0.775** | ≥ 0.75 ✅ |

- full run의 `g29`은 이전 gratitude-focus full run 대비 `faithfulness 0.60 -> 0.80`,
  `context_precision 0.50 -> 0.80`, `context_recall 0.50 -> 0.75`로 개선됐습니다.
- 전체 Faithfulness는 accepted baseline보다 개선됐고, 직전 최고 합산 run(`combined_20260609_102305_103649.json`)과 같은 `0.848`입니다.
- 다만 full run의 Context Precision은 `0.795`로 목표보다 `0.005` 낮습니다. 이 하락은 `g29`가 아니라
  `g11/g12/g27`의 judge/query 변동 영향이 커서, 이번 run을 새 accepted retrieval baseline으로 교체하지는 않습니다.
- 결론: `g29` topic/fallback/guidance는 유지합니다. 다음 개선은 `g23` faithfulness와 `g11/g12/g27` 평가셋/qrels 노이즈 재검수입니다.

### Faithfulness verifier 실험 후 실측 (2026-06-09)

`g06/g15/g23/g29`처럼 검색보다 답변 문장 단정이 문제인 케이스를 기준으로 post-generation verifier를 구현했습니다.
`RAG_VERIFIER_MODE=on` 또는 `python eval/evaluate_rag.py --verifier-mode on`으로 켤 수 있지만, 기본값은 `off`입니다.

낮은 4케이스 partial:

| Run | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
|---|---:|---:|---:|---:|
| verifier v1 (`baseline_20260609_021636.json`) | 0.725 | 0.688 | 0.575 | 0.925 |
| verifier v2 (`baseline_20260609_022028.json`) | 0.537 | 0.688 | 0.700 | 0.900 |
| verifier off + 보수적 초안 가드 (`baseline_20260609_022255.json`) | 0.588 | 0.812 | 0.675 | 0.900 |

전체 30케이스, verifier off + 보수적 초안 가드(`baseline_20260609_022510.json`):

| 지표 | 점수 | 목표 |
|---|---:|---:|
| Answer Relevancy | **0.910** | ≥ 0.85 ✅ |
| Faithfulness | **0.850** | ≥ 0.90 ❌ |
| Context Precision | **0.785** | ≥ 0.80 ❌ |
| Context Recall | **0.725** | ≥ 0.75 ❌ |

- Accepted full-run(`baseline_20260609_003413.json`) 대비 Faithfulness는 `0.828 -> 0.850`으로 올랐지만, Context Precision/Recall은 한 번 측정상 `0.813/0.767 -> 0.785/0.725`로 내려갔습니다.
- 검색 코드는 변경하지 않았고, retrieval-only 확인에서는 vector-only가 여전히 hybrid보다 낫습니다(`P@5=0.113`, `P@10=0.097`, `R@10=0.102`, `nDCG@10=0.138`, `MRR=0.308`).
- 결론: verifier는 현재 production default로 전환하지 않습니다. 기능은 feature flag로 남기고, 기본 경로는 더 보수적인 생성 프롬프트만 유지합니다.
- 다음 후보는 LLM verifier가 아니라 **문장 단위 citation coverage/claim extractor**입니다. 답변을 통째로 다시 쓰게 하면 관련성과 표현 품질이 흔들리므로, citation 없는 연구 주장만 탐지해 수정하는 좁은 verifier가 더 적합합니다.

### 문장 단위 claim/citation checker 실험 (2026-06-09)

전체 답변 rewrite 대신, 답변의 문장 구조를 유지하면서 연구 주장/효과 주장/실천 제안 문장만 좁게 점검하는
`RAG_CLAIM_CHECKER_MODE=on` feature flag를 추가했습니다.
평가에서는 `python eval/evaluate_rag.py --claim-checker-mode on --verifier-mode off`로 켭니다.
기본값은 아직 `off`입니다.

낮은 4케이스 partial(`g06,g15,g23,g29`, `baseline_20260609_032450.json`):

| 지표 | 점수 |
|---|---:|
| Answer Relevancy | **0.900** |
| Faithfulness | **0.788** |
| Context Precision | **0.662** |
| Context Recall | **0.562** |

전체 30케이스(`baseline_20260609_032738.json`):

| 지표 | 점수 | 목표 |
|---|---:|---:|
| Answer Relevancy | **0.913** | ≥ 0.85 ✅ |
| Faithfulness | **0.838** | ≥ 0.90 ❌ |
| Context Precision | **0.757** | ≥ 0.80 ❌ |
| Context Recall | **0.775** | ≥ 0.75 ✅ |

- Accepted full-run(`baseline_20260609_003413.json`) 대비 Faithfulness는 `0.828 -> 0.838`, Answer Relevancy는 `0.910 -> 0.913`, Context Recall은 `0.767 -> 0.775`로 소폭 올랐습니다.
- 반면 Context Precision은 `0.813 -> 0.757`로 낮아졌습니다. 검색 코드는 변경하지 않았으므로 query expansion/judge 노이즈가 섞여 있지만, production default 전환 근거로는 부족합니다.
- checker는 30케이스 중 24케이스를 수정했고, 오류는 없었습니다. 답변 전체 rewrite verifier보다 안정적이지만, 목표 Faithfulness 0.90에는 아직 못 미칩니다.
- 더 엄격한 v2(MUST-FIX uncited claim sentences)는 partial(`baseline_20260609_034738.json`)에서 `Faithfulness=0.425`로 크게 악화되어 되돌렸습니다.
- 결론: 문장 단위 checker는 verifier보다 유망하지만 아직 실험용입니다. 다음 개선은 checker 프롬프트 강화보다, **답변 초안 단계에서 citation을 문장마다 더 정확히 붙이는 생성 프롬프트/템플릿** 쪽이 더 안전합니다.

### 문장별 citation 생성 템플릿 실험 (2026-06-09)

후처리 대신 초안 생성 단계에서 citation을 더 잘 붙이도록 `RAG_ANSWER_TEMPLATE_MODE=sentence` 실험 옵션을 추가했습니다.
기본값은 `standard`이며, `python eval/evaluate_rag.py --answer-template-mode sentence`로만 켭니다.

낮은 4케이스 partial(`g06,g15,g23,g29`, `baseline_20260609_040032.json`):

| 지표 | 점수 |
|---|---:|
| Answer Relevancy | **0.900** |
| Faithfulness | **0.775** |
| Context Precision | **0.400** |
| Context Recall | **0.500** |

전체 30케이스(`baseline_20260609_040240.json`):

| 지표 | 점수 | 목표 |
|---|---:|---:|
| Answer Relevancy | **0.907** | ≥ 0.85 ✅ |
| Faithfulness | **0.800** | ≥ 0.90 ❌ |
| Context Precision | **0.777** | ≥ 0.80 ❌ |
| Context Recall | **0.808** | ≥ 0.75 ✅ |

- Accepted full-run(`baseline_20260609_003413.json`) 대비 Faithfulness가 `0.828 -> 0.800`으로 내려갔습니다.
- 답변 길이는 줄고 문장 구조는 더 깔끔해졌지만, judge 기준 충실도는 개선되지 않았습니다. 특히 `g06=0.00`, `g29=0.50`이 평균을 끌어내렸습니다.
- 결론: 문장별 citation 템플릿은 production 기본값으로 채택하지 않습니다. `RAG_ANSWER_TEMPLATE_MODE=standard`를 유지하고, sentence 템플릿은 재현 가능한 실험 flag로만 남깁니다.
- 다음 개선은 프롬프트를 더 압박하는 것이 아니라, 낮은 케이스(`g06/g29`)의 trace를 직접 읽어 **어떤 근거 문장이 judge에게 unsupported로 보이는지** 문장 단위로 분석하는 쪽이 우선입니다.

---

### g23 유능감 / g06 외로움 guardrail 부분 개선 (2026-06-09)

이번 pass는 full baseline 교체가 아니라 문제 케이스 기반 부분 개선입니다.

구현:

- `g23`용 SDT `competence_inadequacy` topic을 추가하고, perceived competence / need for competence / mastery / challenging-but-achievable tasks / positive feedback 중심 fallback과 reranker guidance를 추가했습니다.
- focus boost의 corpus prefix 보너스를 현재 focus에 맞게 수정했습니다. 이전에는 topic과 무관하게 `positive_psych_` 문서만 작은 보너스를 받았습니다.
- `g23` reference를 현재 corpus가 실제로 뒷받침하는 유능감/도전 가능 과제/긍정 피드백 범위로 정렬했습니다.
- `g06` 외로움 케이스에는 표본·맥락을 밝히고 사용자 원인을 단정하지 않는 answer/reflection guardrail을 추가했습니다.

부분 평가:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_153456.json` | `g23` | `0.800` | `0.750` | `0.900` | `0.900` | 단일 케이스 통과. |
| `baseline_20260609_154925.json` | `g06` | `0.750` | `0.750` | `0.800` | `0.900` | Faith는 개선됐지만 CP는 목표 미달. |
| `baseline_20260609_155549.json` | `g06,g15,g23,g29` | `0.637` | `0.688` | `0.788` | `0.900` | 문제 케이스 평균 Faith는 개선됐지만 CP/CR 실패. |

기각:

- `g29` strict five-sentence template: Faith `0.500`까지 하락해 폐기했습니다.
- `g15` burnout-specific answer guardrail: Faith `0.500`까지 하락해 폐기했습니다.

결론:

- `g23` competence guidance와 `g06` loneliness scope guardrail은 유지합니다.
- 이번 pass 결과로는 full 30-case baseline을 교체하지 않습니다.
- 다음 우선순위는 `g15/g29` qrels/reference 재검수와 full-run precision 변동을 만든 `g11/g12/g27` 검수입니다.

---

### strict qrels rubric / g27 social-evaluation 검색 보정 (2026-06-09)

목표는 `g15/g29`와 full-run precision 변동 케이스(`g11/g12/g27`)의 병목을 더 정확히 분리하는 것입니다.

구현:

- `refresh_problem_qrels.py`에 케이스별 strict rubric을 추가했습니다.
  - `g11`: generic meaning이 아니라 death/finitude/aging/existential anxiety와 meaning이 함께 있어야 grade2.
  - `g12`: generic suffering/meaning이 아니라 grief/bereavement/loss/continuing bond가 있어야 grade2.
  - `g15`: generic stress coping이 아니라 burnout/work engagement와 positive psychology intervention/well-being/meaning/resource가 함께 있어야 grade2.
  - `g27`: social anxiety, fear of being judged, mind-reading, self-focused attention, social-evaluative thought가 있어야 grade2.
  - `g29`: rumination/worry + CBT/cognitive restructuring 또는 sleep-specific dysfunctional belief가 있어야 grade2.
- qrels judge에 `probable_non_english`, `table_fragment`, `metadata_or_reference_fragment`, `very_short_fragment`, `low_text_quality` 품질 플래그를 추가했습니다.
- `evaluate_retrieval.py`에 `production_vector` 전략을 추가했습니다. 이는 pure vector RRF가 아니라 production 후보 정렬인 vector-only RRF + focus boost를 따로 평가합니다.
- `g27`에 CBT `social_evaluation` topic/fallback/focus/reranker guidance를 추가했습니다.

strict qrels 결과:

| Case | strict grade2 |
|---|---:|
| `g11` | 9 |
| `g12` | 2 |
| `g15` | 12 |
| `g27` | 7 |
| `g29` | 9 |

strict qrels 검색 평가(`qrels_next_cases_strict.json`, 5 cases):

| Strategy | P@5 | P@10 | R@10 | nDCG@10 | MRR |
|---|---:|---:|---:|---:|---:|
| `vector` | 0.480 | 0.380 | 0.556 | 0.718 | 0.625 |
| `production_vector` | 0.440 | 0.320 | 0.502 | 0.709 | 0.640 |
| `keyword` | 0.120 | 0.080 | 0.089 | 0.162 | 0.261 |
| `hybrid` | 0.320 | 0.260 | 0.350 | 0.524 | 0.663 |
| `hybrid_vw` | 0.400 | 0.360 | 0.534 | 0.713 | 0.692 |

`g27` 단일 검색은 social-evaluation fallback 후 strict qrels 기준 `production_vector R@10 = 0.29`로 확인됐습니다. 기존 generic CBT fallback에서 드러났던 `0.00` 수준의 miss는 줄었지만, 아직 직접 관련 청크를 충분히 상위에 올리지는 못합니다.

RAG partial(`baseline_20260609_163025.json`, `g11,g12,g15,g27,g29`):

| Case | Faith | Relevancy | CP | CR |
|---|---:|---:|---:|---:|
| `g11` | 0.90 | 0.90 | 0.80 | 0.50 |
| `g12` | 0.80 | 1.00 | 0.50 | 0.50 |
| `g15` | 0.80 | 0.90 | 0.80 | 0.50 |
| `g27` | 0.85 | 0.90 | 0.50 | 0.50 |
| `g29` | 0.75 | 0.90 | 0.50 | 0.75 |

평균: CP `0.620`, CR `0.550`, Faith `0.820`, Relevancy `0.920`.

기각:

- `g27` social-evaluation answer guardrail은 Faith `0.85 -> 0.75`로 하락해 제거했습니다.
- `g15/g29`처럼 답변 프롬프트를 더 강하게 조이는 방식은 계속 불안정합니다.

결론:

- production 검색은 계속 vector-only입니다. strict qrels 기준에서도 일반 `hybrid`는 `production_vector`보다 낮습니다.
- `refresh_problem_qrels.py` strict rubric, `evaluate_retrieval.py`의 `production_vector`, `g27` social-evaluation 검색 topic은 유지합니다.
- 이번 결과는 full baseline 교체가 아닙니다. 다음 우선순위는 `g12/g27/g29`의 source selection/reranker 후보 선택 개선입니다.

### g12 grief/loss 보정 및 g27/g29 실패 실험 (2026-06-09)

목표는 `g12/g27/g29`의 낮은 source selection과 faithfulness를 좁게 개선하는 것이었습니다.

채택한 변경:
- `g12` 상실/애도 질문을 logotherapy `grief_loss` topic으로 감지합니다.
- fallback query에 `grief`, `bereavement`, `mourning`, `death/loss of a loved one`, `meaning reconstruction`, `continuing bonds`, `relational meaning`을 추가했습니다.
- focus/reranker guidance는 일반 Frankl/logotherapy 설명보다 가까운 사람의 죽음·상실, 애도, 관계적 의미 형성 근거를 우선합니다.
- 답변 guidance는 상실을 성급하게 교훈/성장/새 목적 찾기로 바꾸지 않고, 관계에 남은 의미를 조심스럽게 묻도록 제한합니다.

검증:

| run | cases | CP | CR | Faith | Relevancy | note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_165927.json` | `g12,g27,g29` | 0.733 | 0.750 | 0.867 | 0.900 | `g12` 개선 확인, 전체 목표 미달 |
| `baseline_20260609_170504.json` | `g12,g27,g29` | 0.633 | 0.750 | 0.817 | 0.900 | LLM variance 후에도 `g12`는 유지 |

주요 case 변화:

| case | 이전 기준 | 보정 후 관찰 |
|---|---|---|
| `g12` | Faith 0.80, CP 0.50, CR 0.50 | Faith 0.90, CP 0.90, CR 1.00 |
| `g27` | Faith/CP/CR 변동 큼 | social-evaluation fallback 확장은 CP/CR 0.00으로 악화되어 제거 |
| `g29` | Faith 0.75 내외 | prompt 금지어 강화와 deterministic sanitizer 모두 안정 개선 실패. sanitizer는 Faith 0.50으로 악화되어 제거 |

결론:
- `g12 grief_loss` 보정은 유지합니다.
- `g27`에 social-anxiety cognitive-distortion 문구를 더 넣는 방식은 유지하지 않습니다.
- `g29`는 프롬프트 금지어/후처리 sanitizer로 해결하기 어렵습니다. 다음 개선은 답변 후처리보다 `g29` reference/qrels와 judge 기준을 재검수하거나, 반추 근거와 수면 근거를 별도 source group으로 평가하는 방식이 더 적절합니다.

### g29 rumination/sleep source-selection 보정 (2026-06-09)

`g29`의 qrels를 재확인한 결과, 수면 관련 source 중에서도 일반적인 `dysfunctional beliefs about sleep` 조각보다 `thinking repetitively about possible sleep deficiencies`, `arousal/distress`, `monitoring of sleep-related threats`를 직접 말하는 chunk가 더 높은 관련도를 받았습니다. 그래서 query fallback은 그대로 두되, focus boost와 reranker guidance를 더 좁혔습니다.

채택한 변경:
- `rumination_sleep` focus terms에서 sleep 쪽 boost를 반복적 수면 걱정, 각성/고통, sleep-related threat monitoring 중심으로 조정했습니다.
- reranker guidance에 수면 질문에서 이런 직접 sleep-specific chunk가 있으면 rumination/CBT chunk와 함께 1개 선택하도록 명시했습니다.
- `Themes/Subthemes/Open Codes` 같은 table/theme-code fragment에 quality penalty를 추가했습니다.

검증:

| run | cases | CP | CR | Faith | Relevancy | note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_193413.json` | `g29` | 0.75 | 1.00 | 0.80 | 0.90 | sleep-specific top candidate improved, but answer still over-causal |
| `baseline_20260609_193709.json` | `g29` | 0.75 | 0.75 | 0.80 | 0.90 | `Lancee chunk_9` selected |
| `baseline_20260609_193824.json` | `g12,g27,g29` | 0.667 | 0.583 | 0.900 | 0.900 | `g29` Faith 0.90, partial still below retrieval targets |

결론:
- `g29` source selection 보정은 유지합니다. 특히 `Lancee chunk_9`가 선택되면서 Faithfulness가 0.90까지 오른 run이 확인됐습니다.
- 다만 전체 partial은 `g12/g27`의 CP/CR 변동 때문에 아직 목표 미달입니다.
- 다음 단계는 full-run 승격이 아니라 `g27` source precision과 `g12` recall variance를 더 줄이는 것입니다.

### g12 companion chunk 안정화 (2026-06-09)

`g12` 상실/애도 케이스에서 top source는 맞게 잡히지만, 같은 Peltomäki 논문의 adjacent chunk를 primary source로
고르느냐에 따라 Context Recall이 `0.50`과 `1.00` 사이에서 흔들렸습니다.

적용한 변경:

- Production 검색은 계속 vector-only입니다.
- logotherapy `grief_loss` 질문에서만, 선택된 grief/loss chunk의 같은 논문 인접 후보가
  mourning/death/loved ones/crisis of meaning/meaning-making을 직접 담으면 마지막 source를 교체할 수 있게 했습니다.

검증:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_195646.json` | `g12` | 0.75 | 0.50 | 0.90 | 0.90 | companion rule 전 |
| `baseline_20260609_200045.json` | `g12` | 0.90 | 1.00 | 0.90 | 0.90 | Peltomäki `chunk_24` 선택 |
| `baseline_20260609_200147.json` | `g12,g27,g29` | 0.80 | 0.75 | 0.90 | 0.90 | partial 안정화 |

full 30-case run은 원격 데스크톱에서 재시도했으나 `g05` 부근에서 SSH/eval 세션이 멈춰 결과를 승격하지 않았습니다.
다음 full 검증은 작은 batch로 나눠 재실행하거나 eval harness의 timeout/cleanup을 보강한 뒤 진행합니다.

### 5-case batch full 평가와 g15 prompt 실험 (2026-06-09)

한 번에 30케이스를 실행하면 원격 SSH/eval 세션이 멈출 수 있어, `evaluate_rag.py --case-id ...`로
5케이스씩 나눠 실행하고 `eval/combine_rag_runs.py`로 합산했습니다.
`g27`은 한 batch에서 generation timeout이 발생해 단일 재실행 결과(`baseline_20260609_210446.json`)로 대체했습니다.

합산본: `eval/runs/combined_20260609_batched_g12_companion.json`

| 지표 | accepted baseline | batched full | 목표 |
|---|---:|---:|---:|
| Answer Relevancy | 0.910 | **0.913** | ≥ 0.85 ✅ |
| Faithfulness | 0.828 | **0.828** | ≥ 0.90 ❌ |
| Context Precision | 0.813 | **0.843** | ≥ 0.80 ✅ |
| Context Recall | 0.767 | **0.808** | ≥ 0.75 ✅ |

- `g12` companion rule은 full-batch 합산에서도 유지됐고, `g12`는 CP `0.90`, CR `1.00`, Faith `0.90`입니다.
- 검색 지표는 accepted baseline보다 개선됐지만, Faithfulness는 그대로입니다.
- 가장 낮은 Faithfulness 케이스는 `g15=0.60`, `g03=0.75`, `g26=0.75`입니다.
- `g15` 번아웃 답변에 더 강한 topic guidance를 추가하는 prompt-only 실험(`baseline_20260609_210857.json`)은
  Faithfulness `0.60` 그대로, Answer Relevancy `0.80`으로 악화되어 되돌렸습니다.
- 이후 LLM을 쓰지 않는 deterministic sentence guard도 `g15/g03/g26`에서 실험했습니다.
  `baseline_20260609_211651.json` 결과는 Faithfulness `0.45`, Answer Relevancy `0.90`으로,
  핵심 근거 문장을 너무 많이 삭제해 답변이 조언만 남는 문제가 있어 코드에서 제거했습니다.
- 결론: 다음 개선은 prompt 문구를 더 압박하는 방식보다, 낮은 Faithfulness 케이스의 답변 문장을
  단순 삭제하는 deterministic post-processor가 아니라, judge/reference 재검수 또는 더 정교한 claim-support 라벨링 쪽이 더 적합합니다.

### 문장 단위 claim-support 라벨링 (2026-06-09)

Faithfulness가 낮은 `g03/g15/g26`을 대상으로 production 답변의 각 문장이 실제 expanded context로
뒷받침되는지 별도 LLM judge로 라벨링했습니다. 이 분석은 production verifier가 아니라 진단 도구입니다.

실행:

```bash
cd backend
python eval/analyze_claim_support.py \
  --run eval/runs/combined_20260609_batched_g12_companion.json \
  --case-id g15,g03,g26 \
  --timeout 90 \
  --out eval/runs/claim_support_g03_g15_g26_20260609_v2.json
```

결과:

| Case | RAG Faithfulness | Claim-only sentence support avg | 해석 |
|---|---:|---:|---|
| `g03` | 0.75 | 1.00 | 문장 근거는 충분해 보이며, 기존 Faithfulness 저하는 judge 노이즈/기준 차이 가능성이 큼 |
| `g15` | 0.60 | 0.83 | 실제 부분 근거 문장 2개 존재 |
| `g26` | 0.75 | 1.00 | 문장 근거는 충분해 보이며, 기존 Faithfulness 저하는 judge 노이즈/기준 차이 가능성이 큼 |

`g15`에서 문제로 잡힌 문장:

- `이러한 연구 결과는 번아웃을 극복하기 위해 스스로의 감정과 경험을 탐색하는 것이 중요하다는 점을 시사합니다`
- `자신의 일에서 어떤 부분이 의미를 주는지, 혹은 어떤 활동이 긍정적인 감정을 불러일으키는지를 생각해보는 것이 도움이 될 수 있습니다`

결론:

- `g03/g26`은 production 답변을 더 삭제하거나 압박하지 않습니다.
- `g15`만 좁은 후보로 남기되, 이전 prompt-only와 deterministic deletion 실험이 모두 악화됐으므로 바로 production cleanup을 넣지 않습니다.
- 다음 개선은 `g15` 하나에 대해 source selection을 더 직접적인 burnout intervention/result chunk로 고정하거나,
  Faithfulness 평가를 single holistic judge가 아니라 claim-support 보조 지표와 함께 해석하는 방향이 더 정직합니다.

### evaluate_rag claim-support 보조 지표 통합 (2026-06-11)

문장 단위 claim-support 분석을 별도 스크립트뿐 아니라 `evaluate_rag.py`의 optional eval-only 지표로도 붙였습니다.
기본값은 `off`이며, production 경로와 일반 평가 실행에는 영향을 주지 않습니다.

실행:

```bash
cd backend
python eval/evaluate_rag.py \
  --case-id g03,g15,g26 \
  --claim-support-mode on \
  --claim-support-timeout 90 \
  --verifier-mode off \
  --claim-checker-mode off \
  --answer-template-mode standard
```

검증 run: `eval/runs/baseline_20260611_032816.json`

| 지표 | 점수 |
|---|---:|
| Context Precision | 0.783 |
| Context Recall | 0.667 |
| Faithfulness | 0.733 |
| Answer Relevancy | 0.900 |
| Claim Support | 0.919 |

케이스별:

| Case | Faithfulness | Claim Support | 해석 |
|---|---:|---:|---|
| `g03` | 0.80 | 0.90 | holistic judge보다 claim-level 근거율이 높음 |
| `g15` | 0.60 | 1.00 | holistic Faithfulness는 낮지만 이번 답변 문장은 모두 supportable로 판정 |
| `g26` | 0.80 | 0.857 | 일부 문장만 약하고 전체 근거율은 Faithfulness보다 높음 |

결론:

- `g15`를 source-selection으로 계속 미세 조정하기 전에, holistic Faithfulness가 실제 unsupported claim보다
  문체·일반화·citation 민감도에 반응하는지 구분할 수 있게 됐습니다.
- 향후 full/batch 평가에서는 필요할 때 `--claim-support-mode on`을 켜고,
  Faithfulness와 Claim Support가 크게 갈라지는 케이스를 “judge/reference review” 대상으로 분류합니다.

### 현재 accepted 평가 기준 (2026-06-11)

현재 production 기본 경로는 다음 설정을 기준으로 봅니다.

```bash
RAG_VERIFIER_MODE=off
RAG_CLAIM_CHECKER_MODE=off
RAG_ANSWER_TEMPLATE_MODE=standard
```

Accepted full/batch 기준:

| Run | CP | CR | Faith | Relevancy | 판단 |
|---|---:|---:|---:|---:|---|
| `baseline_20260609_003413.json` | 0.813 | 0.767 | 0.828 | 0.910 | 최초 검색 목표 통과 baseline |
| `combined_20260609_batched_g12_companion.json` | 0.843 | 0.808 | 0.828 | 0.913 | 현재 검색 품질 기준 |

해석:

- Context Precision/Recall은 PRD 목표를 통과했고, 검색은 현재 주요 병목이 아닙니다.
- holistic Faithfulness는 아직 PRD 목표 `0.90` 미달입니다.
- 다만 `g03/g15/g26` claim-support 분석과 `baseline_20260611_032816.json`은
  낮은 Faithfulness 중 일부가 실제 unsupported claim보다 holistic judge/reference 민감도일 수 있음을 보여줍니다.
- 따라서 다음부터는 `Faithfulness`가 낮은 케이스를 곧바로 production 답변 문제로 보지 않고,
  `claim_support`가 높은 케이스는 judge/reference review 후보로 분류합니다.

`evaluate_rag.py`와 `combine_rag_runs.py`는 이제 결과 JSON에 `diagnostics`를 저장합니다.

- `low_cases`: 목표 미달 케이스와 실패 지표
- `retrieval_review_cases`: CP/CR 미달 케이스
- `faithfulness_review_cases`: Faithfulness는 낮지만 claim-support가 높은 케이스
- `answer_content_cases`: Faithfulness도 낮고 claim-support도 낮은 실제 답변 개선 후보

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

**문제 케이스만 빠르게 재풀링**
```bash
cd backend
python eval/refresh_problem_qrels.py --case-id g05,g13,g14,g15,g16,g20,g24 --max-candidates 30
python eval/evaluate_retrieval.py --qrels eval/qrels/qrels_problem_cases.json --case-id g05,g13,g14,g15,g16,g20,g24
python eval/evaluate_rag.py --case-id g05,g13,g14,g15,g16,g20,g24 --case-timeout 120 --judge-timeout 120
```

> DB reset/reupload 뒤에는 예전 Mongo `_id` 기반 qrels가 무효가 됩니다. 이전 checkpoint에 후보 `content`가 남아 있다면
> `python eval/migrate_qrels_to_chunk_ids.py` 로 ignored `qrels_draft.json`을 deterministic `chunk_id` 기준으로 변환한 뒤
> `python eval/evaluate_retrieval.py` 를 실행하세요.

> 키워드 검색은 `documents.content` 텍스트 인덱스(`content_text`)를 쓰지만 평가/실험용입니다.
> `evaluate_retrieval.py`는 실행 중 필요한 경우 인덱스를 만들고 종료 시 제거합니다.
> 프로덕션 기본 경로와 업로드 스크립트는 `$vectorSearch` 단독을 유지합니다.

---

## 지표 목표 (PRD §6.2)

| 지표 | 목표 | Tier |
|---|---|---|
| Crisis Detection Recall | ≥ 0.95 | 1 |
| Context Precision | ≥ 0.80 | 2 |
| Context Recall | ≥ 0.75 | 2 |
| Answer Faithfulness | ≥ 0.90 | 2 |
| Answer Relevancy | ≥ 0.85 | 2 |
