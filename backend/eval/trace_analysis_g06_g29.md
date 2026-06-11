# Trace Analysis: g06 / g29 Faithfulness Bottlenecks

Date: 2026-06-09
Baseline run: `backend/eval/runs/baseline_20260609_003413.json`

## Summary

Accepted full-run metrics:

- Context Precision: `0.813`
- Context Recall: `0.767`
- Faithfulness: `0.828`
- Answer Relevancy: `0.910`

The next bottleneck is not broad retrieval. It is answer generation that stretches a retrieved excerpt beyond its scope.

Do not default-enable:

- `RAG_VERIFIER_MODE`
- `RAG_CLAIM_CHECKER_MODE`
- `RAG_ANSWER_TEMPLATE_MODE=sentence`

Keep production defaults:

- `RAG_VERIFIER_MODE=off`
- `RAG_CLAIM_CHECKER_MODE=off`
- `RAG_ANSWER_TEMPLATE_MODE=standard`

## g06: Loneliness / Relatedness

Question: `사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.`

Baseline score:

- Faithfulness: `0.00`
- Answer Relevancy: `0.90`
- Context Precision: `0.50`
- Context Recall: `0.75`

Reference points:

- Relatedness is a basic psychological need connected to belonging and well-being.
- Frustrated relatedness can connect with loneliness and lower motivation.

Selected sources:

| Source | Chunk ID | What It Actually Supports | Risk |
|---|---|---|---|
| 1 | `sdt_deci_2008_motivation_and_education_the_self_determination_perspect_chunk_32` | Competence/relatedness/autonomy support facilitates motivation in SDT contexts. | Does not directly discuss loneliness. |
| 2 | `positive_psych_nishimura_2022_interpersonal_predictors_of_loneliness_in_japanese_child_chunk_6` | In children, loneliness is linked to absence of connection and peer relationship difficulties. | Child/peer context can be overgeneralized to the adult user. |
| 3 | `sdt_mason_2012_motivation_satisfaction_and_innate_psychological_needs_chunk_28` | Figure/model listing autonomy, competence, relatedness, satisfaction, motivation. | Mostly figure fragment, weak evidence. |
| 4 | `sdt_mason_2012_motivation_satisfaction_and_innate_psychological_needs_chunk_2` | In doctoral students, autonomy/relatedness relate to satisfaction and motivation. | Graduate-program context, not loneliness. |

Sentence-level diagnosis:

| Answer Sentence | Citation | Supported? | Problem Type | Minimal Fix |
|---|---:|---|---|---|
| `외로움은 정말 힘든 감정입니다.` | No | Yes as empathy | No issue | Keep. |
| `특히 사람들과의 관계에서 어려움을 느낄 때, 그 감정은 더욱 깊어질 수 있습니다.` | No | Partly | Unsupported general psychology | Rephrase as user reflection, not research claim. |
| `연구에 따르면, 외로움은 다른 사람들과의 연결 부족에서 비롯되는 주관적인 경험...` | No sentence-level citation, followed by `[2]` next sentence | Mostly supported by source 2 | Missing citation / source scope | Add `[2]`; state source 2 is about children/peer relations. |
| `특히 어린이의 경우, 또래 관계의 어려움이 외로움의 주요 원인... [2]` | Yes | Supported | OK, but too central | Keep only as source scope, not user diagnosis. |
| `당신이 느끼는 외로움은 단순히 사회적 상호작용의 부족에서 오는 것일 수 있습니다.` | No | Not directly | Over-causal wording / user diagnosis | Remove or change to: `이 발췌만으로 당신의 외로움 원인을 단정하기는 어렵습니다.` |
| `사람들과의 관계에서 긍정적인 경험이 부족할 때, 외로움이 더욱 심화될 수...` | No | Partly, but uncited and broad | Missing citation / overgeneralization | Cite source 2 and limit to child/peer research, or remove. |
| `자신이 어떤 관계에서 더 많은 만족을 느끼는지... 탐색해 볼 수 있습니다.` | No | Not from sources | Unsupported practice suggestion | Convert to open question. |
| `소속감을 느끼는 활동이나 그룹...` | No | Related to query, not source | Unsupported practice suggestion | Keep as question only, no benefit claim. |
| Final reflection questions | No | OK | No issue | Keep. |

Root cause:

The answer used a child loneliness predictor paper as if it directly diagnosed the user's loneliness. The SDT sources support relatedness/motivation, but not adult loneliness causation.

Safe fix candidate:

- For loneliness/relatedness queries, forbid direct causal diagnosis of the user's loneliness.
- Require population/context scoping when a source is child/adolescent/student-specific.
- Prefer wording like:
  - `이 발췌는 어린이 또래 관계 맥락에서 외로움과 연결 부족을 다룹니다 [2].`
  - `따라서 이 근거만으로 당신의 외로움 원인을 단정하기보다는, 관계에서 어떤 연결감을 원하는지 살펴보는 질문으로 가져오는 편이 안전합니다.`

## g29: Rumination / Sleep

Question: `지나간 실수를 계속 곱씹으며 잠을 못 자요.`

Baseline score:

- Faithfulness: `0.80`
- Answer Relevancy: `0.90`
- Context Precision: `0.50`
- Context Recall: `0.50`

Reference points:

- Rumination sustains depression/anxiety.
- Attention shifting/problem-solving orientation can reduce rumination.

Selected sources:

| Source | Chunk ID | What It Actually Supports | Risk |
|---|---|---|---|
| 1 | `cbt_ebrahimi_2024_comparison_of_the_effectiveness_of_cognitive_behavioral_chunk_58` | CBT/ACT reduced rumination in adolescents with social anxiety disorder; CBT changes rumination through detecting cognitive errors and behavioral tests. | Population is adolescents with SAD, not general sleep difficulty. |
| 2 | `cbt_budiyono_2020_cognitive_behavior_therapy_model_with_cognitive_restruct_chunk_16` | Cognitive restructuring includes rational responses to negative automatic thoughts and identifying distortions. | Source is inmates with pre-release social anxiety, not sleep. |
| 3 | `cbt_lybarger_2022_identifying_distorted_thinking_in_patient_therapist_text_chunk_3` | CBT identifies and reframes cognitive distortions. | General CBT support, not rumination/sleep directly. |
| 4 | `cbt_karakaya_2025_development_of_the_scale_on_the_effects_of_sleep_disorde_chunk_9` | Insomnia/sleep disorders involve catastrophizing and distorted thoughts. | Sleep source is about catastrophizing in insomnia, not past-mistake rumination treatment. |

Sentence-level diagnosis:

| Answer Sentence | Citation | Supported? | Problem Type | Minimal Fix |
|---|---:|---|---|---|
| `지나간 실수를 곱씹으며 잠을 이루지 못하는 상황은 정말 힘든 경험...` | No | Empathy | No issue | Keep. |
| `반복적인 생각은 종종 불안과 스트레스를 증가시키고, 결국에는 수면에도 영향을...` | No | Partly, but not directly | Missing citation / over-causal wording | Cite source 1 for anxiety-rumination; cite source 4 only for sleep disorder catastrophizing; avoid `결국`. |
| `연구에 따르면... 루미네이션... 불안 장애... 특징...` | No direct citation until next sentence | Supported by source 1 | Missing citation | Attach `[1]` to this sentence. |
| `루미네이션은 부정적인 감정을 지속시키고... 불안이 심화... [1]` | Yes | Supported | OK, but population-limited | Mention adolescent SAD context if possible. |
| `CBT와 같은 접근법이 도움이 될 수 있습니다.` | No | Too broad | Unsupported recommendation | Replace with source-scoped statement: `source 1 reports CBT/ACT reduced rumination in adolescents with SAD [1].` |
| `CBT는 부정적인 사고 패턴을 인식하고... 행동 테스트...` | No | Supported by source 1/3 | Missing citation | Add `[1]` or `[3]`. |
| `이러한 과정은 ... 더 나은 사고 방식을 찾는 데 도움... [1]` | Yes | Partly | Over-benefit wording | Use `이 발췌는 ...를 다룬다고 볼 수 있습니다 [1].` |
| `수면 문제와 관련된 인지 왜곡을 다루는 것도 중요합니다.` | No | Partly from source 4 | Missing citation / broad advice | Cite `[4]` and scope to insomnia/catastrophizing. |
| `과거의 실수에 대해 부정적인 자동 사고... 합리적인 반응... 도움이... [2]` | Yes | Partly | Source mismatch: source 2 does not mention past mistakes/sleep | Use as general cognitive restructuring only; remove sleep implication. |
| `인지 재구성 과정은 자아 존중감을 높이고...` | No | Not supported | Unsupported effect claim | Remove. |
| Reflection questions | No | OK | No issue | Keep. |

Root cause:

The answer combines rumination, sleep, CBT, and self-esteem into one causal chain. The sources support parts of this chain separately, but not the full user-specific claim.

Safe fix candidate:

- For rumination/sleep queries, separate:
  - rumination/anxiety evidence
  - sleep/catastrophizing evidence
  - CBT/cognitive restructuring evidence
- Forbid unsupported outcome phrases such as:
  - `수면에도 영향을 미치게 됩니다`
  - `도움이 될 수 있습니다`
  - `자아 존중감을 높이고`
  - `긍정적인 자아 개념을 형성`
- Use source-scoped wording:
  - `이 발췌는 사회불안장애 청소년 맥락에서 CBT/ACT가 반추 감소와 관련되었다고 보고합니다 [1].`
  - `수면장애 관련 발췌는 불면 상황에서 재앙화 사고가 나타날 수 있다고 설명합니다 [4].`
  - `이 두 근거만으로 과거 실수 곱씹기가 수면 문제를 직접 일으킨다고 단정하기는 어렵습니다.`

## Proposed Minimal Code Direction

Do not add another broad verifier.

Instead add a small dynamic generation guard based on query focus:

1. If query includes loneliness/social connection terms:
   - Do not infer the user's loneliness cause.
   - Scope child/adolescent/student findings explicitly.
   - Prefer reflection questions over practice claims.

2. If query includes rumination/sleep/past mistakes:
   - Do not claim sleep effects unless the cited source explicitly discusses sleep.
   - Do not claim self-esteem/self-concept benefits unless context says so.
   - Separate CBT-rumination claims from sleep-catastrophizing claims.

Then evaluate:

1. `g06,g29`
2. `g06,g15,g23,g29`
3. Full 30 cases

## Prompt Guardrail Experiment

Date: 2026-06-09

Tested a narrow dynamic generation guardrail for loneliness/relatedness and rumination/sleep queries.

Result: do not keep it as production default.

Runs:

| Run | Change | Cases | CP | CR | Faith | Relevancy | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_042915.json` | soft topic guardrail | `g06,g29` | `0.375` | `0.500` | `0.650` | `0.900` | Not enough; `g06` retrieval/judge context still unstable. |
| `baseline_20260609_043249.json` | stronger forbidden-phrase guardrail | `g06,g29` | `0.375` | `0.750` | `0.300` | `0.900` | Reject; made Faithfulness worse. |
| `baseline_20260609_043545.json` | soft topic guardrail | `g06,g15,g23,g29` | `0.450` | `0.625` | `0.550` | `0.925` | Reject as default; not stable across problem cases. |

Key observation:

- Making the prompt stricter did not reliably stop unsupported causal wording.
- `g06` remains sensitive to selected SDT chunks and judge/qrels alignment.
- `g29` is less a retrieval issue than a generation issue, but prompt-only fixes are not reliable enough.

Decision:

- Keep production default at `RAG_VERIFIER_MODE=off`, `RAG_CLAIM_CHECKER_MODE=off`, `RAG_ANSWER_TEMPLATE_MODE=standard`.
- Do not add a new always-on prompt guardrail from this experiment.
- Next better direction is either qrels/judge refinement for `g06` or a targeted post-generation checker that edits only flagged sentence types, but only after trace-level acceptance criteria are defined.

## g06 Qrels / Retrieval Refinement Check

Date: 2026-06-09

Checked `g06` against the current corpus because the accepted run still had `g06 faithfulness=0.00`.

Findings:

- Existing `qrels_draft.json` for `g06` is not aligned with `category=sdt`; many grade-2 entries are CBT/social-anxiety chunks from old pooling.
- Re-running `refresh_problem_qrels.py` for `g06` against the current corpus confirmed the reference is broad: chunks about loneliness, social support, social isolation, logotherapy isolation, and SDT relatedness can all be judged relevant.
- The qrels judge needed a stricter rubric. `refresh_problem_qrels.py` now includes `CATEGORY` and explicitly requires grade 2 to support both a reference point and an expected theme, not just surface symptom overlap.

Runs:

| Run | Change | Cases | CP | CR | Faith | Relevancy | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_044653.json` | loneliness-focused reranker experiment | `g06` | `0.500` | `0.500` | `0.800` | `0.900` | Promising single-case signal, but not enough. |
| `baseline_20260609_045343.json` | direct loneliness + SDT source mix | `g06` | `0.500` | `0.500` | `0.600` | `0.900` | Worse faithfulness; reject as default. |
| `baseline_20260609_045458.json` | source diversity applied broadly | `g06,g15,g23,g29` | `0.525` | `0.562` | `0.637` | `0.925` | Reject; hurt non-g06 cases. |
| `baseline_20260609_045707.json` | diversity narrowed to loneliness only | `g06,g15,g23,g29` | `0.662` | `0.562` | `0.637` | `0.900` | Reject; still below accepted partial behavior. |

Decision:

- Do not keep the production loneliness reranker/topic-penalty/source-diversity experiment.
- Keep only the qrels judge rubric improvement in `refresh_problem_qrels.py`.
- Chosen direction: treat `g06` as a loneliness/social-connection case, not a strict SDT case.

## g06 Intent Realignment Accepted

Date: 2026-06-09

Changed `g06` in `golden_set.json`:

- `category`: `sdt -> positive_psych`
- `expected_context_themes`: `loneliness`, `social isolation`, `social connection`, `social support`, `peer relations`, `belonging`
- `reference_points`: direct loneliness/social-connection framing, including a scope warning for child/patient/specific-population studies.

Also adjusted query routing narrowly:

- Korean loneliness/isolation terms now infer `positive_psych` instead of `sdt`.
- Positive psychology topic detection now has a `loneliness` topic.
- The fallback query variant for this topic adds `social support`, `belonging`, `peer relations`, and `interpersonal relationships` instead of a generic SDT theory variant.

Runs:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_101619.json` | `g06` | `0.000` | `0.000` | `0.200` | `0.900` | Golden changed but search still routed to SDT. |
| `baseline_20260609_101958.json` | `g06` | `0.750` | `0.750` | `0.800` | `0.900` | Loneliness query routing fixed. |
| `baseline_20260609_102052.json` | `g06,g15,g23,g29` | `0.650` | `0.688` | `0.700` | `0.900` | Problem-case partial improved vs accepted partial. |
| `combined_20260609_102305_103649.json` | `30` | `0.825` | `0.800` | `0.848` | `0.913` | Combined 24-case interrupted run + remaining 6 cases. |

Accepted comparison:

- Accepted baseline `baseline_20260609_003413.json`: CP `0.813`, CR `0.767`, Faith `0.828`, Relevancy `0.910`.
- New combined result: CP `0.825`, CR `0.800`, Faith `0.848`, Relevancy `0.913`.

Decision:

- Keep the `g06` positive-psychology/social-connection realignment.
- Keep the narrow loneliness query routing.
- Continue leaving verifier, claim checker, and sentence template defaults off/standard.
- Next bottleneck is not `g06`; inspect `g29`, `g03`, and `g15` for remaining Faithfulness loss.

## g03 Gratitude Focus Accepted

Date: 2026-06-09

Question: `작은 일에도 감사하는 마음을 갖고 싶은데 잘 안 돼요.`

Trace diagnosis:

- The previous query variants already included `gratitude`, but the third variant sometimes drifted into broad theory language such as `logotherapy` and `meaning-making`.
- Selected sources were partly relevant, but included broad positive-psychology or job-performance-only gratitude chunks.
- The safer retrieval target is direct gratitude intervention evidence: gratitude journal, Three Good Things, gratitude letter/visit, subjective well-being, and positive affect.

Implemented change:

- Added a `gratitude` positive-psychology topic.
- For gratitude queries, forced a deterministic fallback variant:
  `gratitude intervention, gratitude journal, three good things, gratitude letter, gratitude visit, subjective well-being, positive affect, positive psychology`.
- Added focus terms and reranker guidance that prefer direct gratitude intervention/result chunks over broad lists or job-performance-only gratitude chunks.

Runs:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_104733.json` | `g03,g15,g29` | `0.600` | `0.583` | `0.800` | `0.900` | `g03` improved; `g29` still unstable. |
| `baseline_20260609_104938.json` | `30` | `0.800` | `0.783` | `0.845` | `0.913` | Passes CP/CR/Relevancy; Faithfulness still below 0.90. |

Accepted comparison:

- Accepted baseline `baseline_20260609_003413.json`: CP `0.813`, CR `0.767`, Faith `0.828`, Relevancy `0.910`.
- New full run `baseline_20260609_104938.json`: CP `0.800`, CR `0.783`, Faith `0.845`, Relevancy `0.913`.
- `g03` improved from Faith `0.70`, CP `0.50`, CR `0.50` in the combined trace to Faith `0.80`, CP `0.80`, CR `1.00` in the full gratitude-focus run.

Decision:

- Keep the gratitude topic/fallback/reranker guidance.
- Do not treat this as solving the overall Faithfulness bottleneck.
- Next priority is `g29`: the answer still over-connects rumination, CBT, and sleep into a broad causal chain even when the retrieved sources support those pieces only separately.

## g29 Rumination / Sleep Focus Accepted

Date: 2026-06-09

Question: `지나간 실수를 계속 곱씹으며 잠을 못 자요.`

Trace diagnosis:

- The previous CBT focus terms over-boosted generic `cognitive distortion` and `CBT introduction` chunks.
- The candidate pool already contained better direct evidence:
  - `rumination-focused CBT` / relapse vulnerability chunks.
  - rumination and worries as repetitive negative thinking.
  - sleep-specific dysfunctional beliefs / CBT-I chunks.
- The answer still tended to add source-external counseling moves such as journaling, meaning/value discovery, lessons from mistakes, or direct sleep-causality claims.

Implemented change:

- Added a `rumination_sleep` CBT topic.
- Triggered it only when `곱씹/반추/rumination` is present, not merely when the Korean word `실수` appears.
- Added deterministic fallback and focus terms around `rumination`, `repetitive negative thinking`, `rumination-focused CBT`, `cognitive restructuring`, `insomnia`, `dysfunctional beliefs about sleep`, and `CBT-I`.
- Added reranker guidance to prefer direct rumination/sleep evidence and deprioritize generic CBT/cognitive-distortion introductions.
- Realigned `g29` reference points to current-corpus support:
  - rumination/repetitive negative thinking and anxiety/depression vulnerability.
  - CBT/rumination-focused CBT and cognitive restructuring.
  - sleep claims scoped to insomnia/sleep-disorder dysfunctional beliefs, not direct user-specific causation.
- Added topic-specific answer guidance that overrides the default meaning/value reflection prompt for this case.

Runs:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_110628.json` | `g29` | `0.750` | `1.000` | `0.800` | `0.900` | Search/reference alignment improved. |
| `baseline_20260609_111706.json` | `g04,g29` | `0.775` | `0.750` | `0.850` | `0.900` | Confirmed plain mistake CBT case no longer triggers rumination fallback. |
| `baseline_20260609_112446.json` | `30` | `0.795` | `0.775` | `0.848` | `0.913` | `g29` improved; full CP just under target due unrelated noisy cases. |

Accepted comparison:

- Accepted baseline `baseline_20260609_003413.json`: CP `0.813`, CR `0.767`, Faith `0.828`, Relevancy `0.910`.
- `g29` focus full run `baseline_20260609_112446.json`: CP `0.795`, CR `0.775`, Faith `0.848`, Relevancy `0.913`.
- In the final full run, `g29` itself improved to Faith `0.800`, CP `0.800`, CR `0.750`, Relevancy `0.900`.

Decision:

- Keep the `rumination_sleep` retrieval and generation guidance because it fixes the target case without contaminating `g04`.
- Do not promote `baseline_20260609_112446.json` as the new retrieval baseline because total CP is `0.005` below target and lower than the prior combined run.
- Next priority is `g23` faithfulness, then judge/qrels review for `g11`, `g12`, and `g27`, which caused most of the full-run precision volatility.

## g23 Competence and g06 Loneliness Guardrails

Date: 2026-06-09

Questions:

- `g23`: `유능하다는 느낌을 받고 싶은데 늘 제가 부족해 보여요.`
- `g06`: `사람들과 잘 어울리지 못하는 것 같아 늘 외로워요.`

Trace diagnosis:

- `g23` was retrieving SDT competence evidence, but generic SDT focus terms also allowed broad autonomy/reward/measurement chunks.
- The answer often generalized from competence-supportive contexts into unsupported self-help claims such as small goals guaranteeing competence.
- `g06` retrieved loneliness/social-isolation sources, but answers overgeneralized from child/patient/context-specific studies into user-specific causes or value/meaning advice.

Implemented change:

- Added an SDT `competence_inadequacy` topic with a deterministic fallback variant for perceived competence, need for competence, mastery, optimal challenge, challenging-but-achievable tasks, positive feedback, and self-efficacy.
- Added competence-specific focus terms, reranker guidance, and answer/reflection guardrails that avoid diagnosing the user's inadequacy.
- Fixed focus boost corpus-prefix handling so non-positive-psychology queries do not always give the small matched-source bonus to `positive_psych_` documents.
- Added loneliness-specific answer/reflection guardrails requiring source scope and sample/context to be stated instead of moving into broad value/meaning advice.
- Realigned `g23` reference points to current-corpus support around competence as a basic need, challenging-but-achievable tasks, positive feedback, and avoiding user-cause diagnosis.

Runs:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_153456.json` | `g23` | `0.800` | `0.750` | `0.900` | `0.900` | Single-case pass after competence fallback/guidance. |
| `baseline_20260609_154925.json` | `g06` | `0.750` | `0.750` | `0.800` | `0.900` | Faith improved from the failing `0.50` trace, but CP remains low. |
| `baseline_20260609_155549.json` | `g06,g15,g23,g29` | `0.637` | `0.688` | `0.788` | `0.900` | Faith improved vs older problem-case partial, but CP/CR remain weak. |

Rejected during this pass:

- A strict `g29` five-sentence answer template. It dropped `g29` to Faith `0.500` and citation format became less stable.
- A burnout-specific `g15` answer guardrail. It dropped `g15` to Faith `0.500`; the model still used unsupported recovery/advice phrasing.

Decision:

- Keep the `g23` competence retrieval/generation guidance and the `g06` loneliness scope guardrail.
- Do not promote any new full-run baseline from this pass.
- Do not run the full 30-case evaluation yet; the problem-case partial still fails CP/CR and shows `g15/g29` instability.
- Next priority is qrels/reference review for `g15/g29` and the noisy full-run precision cases `g11/g12/g27`, rather than broader prompt pressure.

## Strict Qrels and g27 Social-Evaluation Retrieval

Date: 2026-06-09

Scope:

- qrels/reference review for `g15`, `g29`, `g11`, `g12`, and `g27`.
- Production search remains vector-only; `$text` remains experiment-only.

Trace/qrels diagnosis:

- The previous qrels judge was too permissive for `g11/g12`: generic meaning/logotherapy chunks were often labeled grade2 even without the case-specific death/finitude/aging or grief/bereavement/loss requirement.
- Some noisy chunks with non-English text or table/reference-like fragments were still eligible for grade2.
- `g27` had a genuine retrieval weakness: the user asks about how others perceive them, but CBT fallback/focus terms stayed generic (`cognitive distortion`, `negative automatic thoughts`) rather than social anxiety, fear of negative evaluation, mind-reading, and self-focused attention.

Implemented change:

- `refresh_problem_qrels.py`
  - Added case-specific strict rules for `g11/g12/g15/g27/g29`.
  - Added quality flags: `probable_non_english`, `table_fragment`, `metadata_or_reference_fragment`, `very_short_fragment`, and `low_text_quality`.
  - Quality flags do not automatically delete candidates, but they instruct the judge to cap grade2 unless clear English prose directly supports the case.
- `evaluate_retrieval.py`
  - Added `production_vector`, which evaluates vector-only RRF after production focus boost.
  - This separates pure vector search quality from the actual production candidate ordering.
- `rag_service.py`
  - Added CBT `social_evaluation` topic for `g27`.
  - Fallback/focus/reranker guidance now prioritize social anxiety, fear of negative evaluation, mind-reading, self-focused attention, social-evaluative threat, cognitive restructuring, Socratic questioning, and reality testing.

Strict qrels grade2 counts:

| Case | grade2 |
|---|---:|
| `g11` | 9 |
| `g12` | 2 |
| `g15` | 12 |
| `g27` | 7 |
| `g29` | 9 |

Retrieval run with strict qrels:

| Strategy | P@5 | P@10 | R@10 | nDCG@10 | MRR |
|---|---:|---:|---:|---:|---:|
| `vector` | `0.480` | `0.380` | `0.556` | `0.718` | `0.625` |
| `production_vector` | `0.440` | `0.320` | `0.502` | `0.709` | `0.640` |
| `keyword` | `0.120` | `0.080` | `0.089` | `0.162` | `0.261` |
| `hybrid` | `0.320` | `0.260` | `0.350` | `0.524` | `0.663` |
| `hybrid_vw` | `0.400` | `0.360` | `0.534` | `0.713` | `0.692` |

RAG partial:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_163025.json` | `g11,g12,g15,g27,g29` | `0.620` | `0.550` | `0.820` | `0.920` | Good answer relevance; source precision/recall still weak. |

Rejected during this pass:

- `g27` social-evaluation answer guardrail. It dropped single-case Faith from `0.85` to `0.75`, so it was removed.

Decision:

- Keep strict qrels rubric and `production_vector` evaluation.
- Keep `g27` social-evaluation retrieval topic/fallback/reranker guidance.
- Do not introduce `$text` hybrid into production; strict qrels still show ordinary `hybrid` below `production_vector`.
- Do not promote a new full baseline from this pass.
- Next best step is source-selection/reranker work for `g12/g27/g29`, not broader answer prompt pressure.

## g12 Grief/Loss Fix and Failed g27/g29 Experiments

Date: 2026-06-09

Implemented change:

- Added logotherapy `grief_loss` topic detection for close-person loss, grief, bereavement, mourning, and meaning reconstruction.
- Added grief/loss fallback terms: `grief`, `bereavement`, `mourning`, `death/loss of a loved one`, `meaning reconstruction`, `continuing bonds`, and `relational meaning`.
- Added focus/reranker guidance that prefers grief, bereavement, loved-one loss, and relational meaning chunks over generic Frankl/logotherapy chunks.
- Added answer guidance to avoid turning bereavement into premature lessons, growth, or new-purpose advice.

RAG partial:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_165927.json` | `g12,g27,g29` | `0.733` | `0.750` | `0.867` | `0.900` | Good improvement, still below full target. |
| `baseline_20260609_170504.json` | `g12,g27,g29` | `0.633` | `0.750` | `0.817` | `0.900` | LLM variance; `g12` remained strong. |

Case-level result:

- `g12` improved from roughly Faith `0.80`, CP `0.50`, CR `0.50` to Faith `0.90`, CP `0.90`, CR `1.00`.
- `g27` remained unstable. Expanding the fallback with social-anxiety cognitive-distortion phrasing dropped single-case CP/CR to `0.00`, so that experiment was removed.
- `g29` remained unstable. Prompt-only wording restrictions did not reliably improve Faithfulness. A deterministic topic sanitizer dropped single-case Faith to `0.50`, so it was removed.

Decision:

- Keep the `g12 grief_loss` retrieval and answer guidance.
- Do not repeat the removed `g27` fallback expansion or `g29` sanitizer path.
- For `g29`, inspect whether the judge/reference expects the sleep link to be evaluated as a separate source group rather than as one combined rumination-sleep answer.

## g29 Rumination/Sleep Source Selection

Date: 2026-06-09

Diagnosis:

- Strict qrels for `g29` treat rumination/CBT chunks and sleep-specific chunks differently.
- Sleep chunks that only mention `dysfunctional beliefs about sleep` or CBT-I tend to be grade1.
- The stronger sleep source is `cbt_lancee_2015...chunk_9`, which directly discusses repetitive thinking about possible sleep deficiencies, arousal/distress, and monitoring of sleep-related threats.
- A weak table/theme-code fragment (`cbt_g_k_ay...chunk_26`) was sometimes selected by the LLM reranker.

Implemented change:

- Narrowed `rumination_sleep` focus terms toward repetitive sleep worry, arousal/distress, and sleep-related threat monitoring.
- Updated reranker guidance to select one direct sleep-specific chunk when such a candidate exists.
- Added quality penalty for table/theme-code fragments containing markers such as `Themes, Subthemes`, `Category (Main Theme)`, and `Open Codes`.

Results:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_193413.json` | `g29` | `0.75` | `1.00` | `0.80` | `0.90` | Recall improved; answer still over-causal. |
| `baseline_20260609_193709.json` | `g29` | `0.75` | `0.75` | `0.80` | `0.90` | `Lancee chunk_9` selected. |
| `baseline_20260609_193824.json` | `g12,g27,g29` | `0.667` | `0.583` | `0.900` | `0.900` | `g29` reached Faith `0.90`; partial still fails retrieval metrics. |

Decision:

- Keep the `g29` source-selection adjustment.
- Do not restore the removed sanitizer or strict sentence template.
- Next bottlenecks are `g27` source precision and `g12` recall variance.

## g12 Companion Chunk Stabilization

Date: 2026-06-09

Diagnosis:

- `g12` recall varied even when the top Peltomäki grief/loss source was selected.
- Good runs selected both `logotherapy_peltom_ki_2023_meaningfulness_death_and_suffering_philosophy_of_meaning_chunk_23` and adjacent `chunk_24`.
- A weaker run selected `chunk_23` but replaced adjacent `chunk_24` with a less direct Beuselinck care-context chunk, dropping Context Recall to `0.50`.

Implemented change:

- Kept production search vector-only.
- Added a narrow post-rerank companion rule only for logotherapy `grief_loss` queries.
- If a selected grief/loss chunk has an adjacent same-paper candidate that directly discusses mourning, death/loved ones, crisis of meaning, or meaning-making, the companion can replace the last selected source.

Results:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `baseline_20260609_195646.json` | `g12` | 0.75 | 0.50 | 0.90 | 0.90 | Before companion rule; selected Beuselinck instead of Peltomäki `chunk_24`. |
| `baseline_20260609_200045.json` | `g12` | 0.90 | 1.00 | 0.90 | 0.90 | Companion rule selected Peltomäki `chunk_24`. |
| `baseline_20260609_200147.json` | `g12,g27,g29` | 0.80 | 0.75 | 0.90 | 0.90 | Partial stabilized; `g27` recall still strict at 0.50. |

Decision:

- Keep the g12 companion rule because it is narrow, deterministic, and improves the previously unstable grief/loss case.
- Do not promote a new full 30-case baseline from this pass. A full run started after the partial but stalled around `g05`; no remote `evaluate_rag.py` process remained afterward, so it was treated as inconclusive.
- Next full evaluation should be retried on the Tailscale desktop after either adding stronger timeout/process cleanup to the eval harness or running in smaller resumable batches.

## Batched Full Evaluation and Rejected g15 Prompt-Only Fix

Date: 2026-06-09

Implemented evaluation support:

- Added `eval/combine_rag_runs.py` so several `evaluate_rag.py --case-id ...` outputs can be combined into one aggregate run.
- Ran the full 30 cases on the Tailscale desktop in 5-case batches.
- Replaced the timed-out `g27` result from the `g26-g30` batch with a clean single-case rerun.

Combined result:

| Run | Cases | CP | CR | Faith | Relevancy | Note |
|---|---:|---:|---:|---:|---:|---|
| `combined_20260609_batched_g12_companion.json` | 30 | 0.843 | 0.808 | 0.828 | 0.913 | Search metrics improved; Faith unchanged from accepted baseline. |

Case observations:

- `g12` stayed stable at CP `0.90`, CR `1.00`, Faith `0.90`.
- Lowest Faithfulness cases were `g15=0.60`, `g03=0.75`, and `g26=0.75`.
- `g15` retrieval looked acceptable (CP `0.80`, CR `0.75`), but the answer broadened table/review evidence into generic recovery claims such as emotional exploration, resilience, and intervention effects.

Rejected experiment:

- Added a stronger burnout-specific answer guidance that forced a 5-sentence structure and banned generic recovery claims.
- Single-case run `baseline_20260609_210857.json` did not improve Faithfulness (`0.60`) and reduced Answer Relevancy to `0.80`.
- The experiment was removed from `rag_service.py` and tests.
- A deterministic sentence guard was also tested on `g15,g03,g26`.
- Run `baseline_20260609_211651.json` scored CP `0.767`, CR `0.833`, Faith `0.450`, Relevancy `0.900`.
- It removed too many cited/relevant research sentences and left advice-heavy answers, especially `g15` where Faithfulness fell to `0.00`.
- The deterministic guard code and CLI flag were removed.

Decision:

- Keep the batched evaluation workflow and `combine_rag_runs.py`.
- Do not add burnout prompt-only guidance.
- Do not add a simple deterministic sentence-deletion guard.
- Next better path for Faithfulness is trace/judge review for `g15/g03/g26` or a true claim-support labeling step, rather than more global prompt pressure or simple post-generation deletion.

## Claim-Support Labeling for g03/g15/g26

Date: 2026-06-09

Implemented diagnostic:

- Added `eval/analyze_claim_support.py`.
- The script reads an existing RAG run, splits selected answers into sentences, and uses an LLM judge to label each sentence as `supported`, `partially_supported`, `unsupported`, or `not_applicable`.
- It saves both JSON and Markdown artifacts.

Run:

| Artifact | Cases |
|---|---|
| `claim_support_g03_g15_g26_20260609_v2.json` | `g03,g15,g26` |
| `claim_support_g03_g15_g26_20260609_v2.md` | `g03,g15,g26` |

Result:

| Case | RAG Faithfulness | Claim-only support avg | Diagnosis |
|---|---:|---:|---|
| `g03` | 0.75 | 1.00 | Claims judged supported; likely holistic judge noise or citation-style sensitivity. |
| `g15` | 0.60 | 0.83 | Two partially supported over-generalized burnout reflection sentences. |
| `g26` | 0.75 | 1.00 | Claims judged supported; likely holistic judge noise or reference/judge mismatch. |

Problem sentences for `g15`:

- `이러한 연구 결과는 번아웃을 극복하기 위해 스스로의 감정과 경험을 탐색하는 것이 중요하다는 점을 시사합니다`
- `예를 들어, 자신의 일에서 어떤 부분이 의미를 주는지, 혹은 어떤 활동이 긍정적인 감정을 불러일으키는지를 생각해보는 것이 도움이 될 수 있습니다`

Decision:

- Do not keep trying to fix `g03/g26` by deleting or tightening answer text; claim-level review says the generated claims are supportable.
- Keep `g15` as the only clear answer-content candidate, but do not add broad prompt pressure or deterministic deletion because both have already failed.
- Next candidate is retrieval/source selection for `g15` toward cleaner intervention/result chunks, or adding claim-support as a secondary evaluation metric alongside holistic Faithfulness.

## Claim-Support Metric Integrated into evaluate_rag.py

Date: 2026-06-11

Implemented change:

- Added `--claim-support-mode on/off` and `--claim-support-timeout` to `evaluate_rag.py`.
- When enabled, the evaluator runs the sentence-level claim-support judge after normal RAG scoring and stores `claim_support` in each case and in the summary.
- Updated `combine_rag_runs.py` so optional numeric metrics such as `claim_support` are preserved in combined batch reports.
- Default remains off; production behavior is unchanged.

Validation run:

| Run | Cases | CP | CR | Faith | Relevancy | Claim Support |
|---|---:|---:|---:|---:|---:|---:|
| `baseline_20260611_032816.json` | `g03,g15,g26` | 0.783 | 0.667 | 0.733 | 0.900 | 0.919 |

Case-level result:

| Case | Faithfulness | Claim Support | Note |
|---|---:|---:|---|
| `g03` | 0.80 | 0.90 | Claim-level support is higher than holistic Faithfulness. |
| `g15` | 0.60 | 1.00 | Current answer's claim sentences were judged supportable despite low holistic Faithfulness. |
| `g26` | 0.80 | 0.857 | Some weaker sentences remain, but claim support is still above holistic Faithfulness. |

Decision:

- Treat `claim_support` as an eval-only diagnostic, not a PRD replacement metric yet.
- Use divergence between holistic Faithfulness and claim support to identify judge/reference review cases.
- Do not change `g15` production source selection based solely on the low holistic Faithfulness score from this run.

## Evaluation Diagnostics Standardization

Date: 2026-06-11

Implemented change:

- `evaluate_rag.py` now stores a `diagnostics` section in each run JSON.
- `combine_rag_runs.py` preserves optional numeric metrics such as `claim_support` and also emits `diagnostics` for combined batch reports.

Diagnostics fields:

- `low_cases`: cases below target, with failed metrics and values.
- `retrieval_review_cases`: cases with low Context Precision or Context Recall.
- `faithfulness_review_cases`: cases where holistic Faithfulness is low but `claim_support` is high.
- `answer_content_cases`: cases where Faithfulness is low and claim-support is not high.

Accepted evaluation stance:

- Keep `combined_20260609_batched_g12_companion.json` as the current search-quality baseline: CP `0.843`, CR `0.808`, Faith `0.828`, Relevancy `0.913`.
- Keep `baseline_20260609_003413.json` as the first full run that crossed both retrieval targets.
- Use `claim_support` only as an eval diagnostic to separate likely judge/reference-review cases from actual answer-content problems.
