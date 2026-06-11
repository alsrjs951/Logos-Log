"""
RAG 검색·답변 품질 평가 (Tier 2).

골든셋(golden_set.json)의 각 질문을 프로덕션 경로(RAGService.get_streaming_response)로
그대로 실행하여 검색 청크(contexts)와 생성 답변(answer)을 수집하고, LLM-judge로
Context Precision / Context Recall / Faithfulness / Answer Relevancy 를 산출한다.

설계 노트: 초기엔 Ragas를 쓰려 했으나, 설치된 langchain 1.x 스택과 Ragas의 langchain_community
의존성이 버전 비호환이라(전형적 버전 충돌), 동일 지표를 이미 설치된 langchain-openai 기반
LLM-judge 로 직접 구현했다. Ragas 지표 역시 내부적으로 LLM-judge이며, 여기서는 동등한 정의를
명시적 프롬프트로 채점한다. (지표 정의는 rag_evaluation_plan.md 참조)

전제 조건:
  - MongoDB Atlas `documents` 적재 + `vector_index` (1024차원)
  - .env: MONGODB_URI, OPENAI_API_KEY
  - 메인 백엔드 의존성(requirements.txt)만 있으면 된다(별도 평가 의존성 불필요).

실행:
  cd backend && python eval/evaluate_rag.py
"""
import os
import sys
import json
import asyncio
import argparse
import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN_PATH = os.path.join(EVAL_DIR, "golden_set.json")
RUNS_DIR = os.path.join(EVAL_DIR, "runs")

# .env 로드 (환경변수 가드보다 먼저)
try:
    from dotenv import load_dotenv
    for _env in (os.path.join(BACKEND_DIR, ".env"), os.path.join(os.path.dirname(BACKEND_DIR), ".env")):
        if os.path.exists(_env):
            load_dotenv(_env)
            break
except ImportError:
    pass


def _parse_sse(line: str):
    line = line.strip()
    if not line.startswith("data: "):
        return None
    try:
        return json.loads(line[len("data: "):])
    except (ValueError, json.JSONDecodeError):
        return None


async def _run_case(rag, question: str, is_journal: bool):
    """질문 하나를 프로덕션 스트리밍 경로로 실행해 (contexts, answer) 수집."""
    source_contexts, answer = [], ""
    async for evt in rag.get_streaming_response(
        query=question, history=[], is_journal=is_journal, journal_id=None, user_id=None
    ):
        payload = _parse_sse(evt)
        if not payload:
            continue
        ptype = payload.get("type")
        if ptype == "sources":
            source_contexts = [s.get("content", "") for s in payload.get("data", []) if s.get("content")]
        elif ptype == "chunk":
            answer += payload.get("data", "")
    trace = getattr(rag, "last_generation_trace", {}) or {}
    generation_contexts = [ctx for ctx in trace.get("expanded_contexts", []) if ctx]
    return generation_contexts or source_contexts, answer, trace, source_contexts


# ---------------------------------------------------------------------------
# LLM-judge: Ragas 지표와 동등한 정의를 명시적 프롬프트로 0~1 점수화한다.
# ---------------------------------------------------------------------------
def _make_judge():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model_name="gpt-4o-mini", temperature=0.0)


async def _judge_score(judge, instruction: str, payload: str) -> float:
    """지시문+자료를 주고 {"score": 0~1} JSON 을 받아 float 반환. 실패 시 None."""
    from langchain_core.messages import SystemMessage, HumanMessage
    sys_prompt = (
        instruction
        + "\nRespond ONLY with a raw JSON object: {\"score\": <float between 0 and 1>}. "
        "No explanation."
    )
    try:
        resp = await judge.ainvoke(
            [SystemMessage(content=sys_prompt), HumanMessage(content=payload)],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.content.strip())
        s = float(data.get("score"))
        return max(0.0, min(1.0, s))
    except Exception as e:
        print(f"    [judge error] {str(e)[:100]}", flush=True)
        return None


async def _score_case(judge, row: dict) -> dict:
    q = row["question"]
    ans = row["answer"]
    ctx = row["contexts"]
    ref = row["ground_truth"]
    ctx_block = "\n\n".join(f"[Context {i+1}]\n{c}" for i, c in enumerate(ctx)) or "(none)"

    # Faithfulness: 답변의 사실 주장 중 컨텍스트로 뒷받침되는 비율. 컨텍스트 없으면 0.
    if ctx:
        faith = await _judge_score(
            judge,
            "You evaluate FAITHFULNESS: the fraction of factual claims in the ANSWER that are "
            "directly supported by the given CONTEXTS (academic paper chunks). Higher = less hallucination.",
            f"CONTEXTS:\n{ctx_block}\n\nANSWER:\n{ans}",
        )
    else:
        faith = 0.0

    # Answer Relevancy: 답변이 질문에 얼마나 직접적으로 답하는가.
    relev = await _judge_score(
        judge,
        "You evaluate ANSWER RELEVANCY: how directly and completely the ANSWER addresses the QUESTION "
        "(ignore factual accuracy; judge relevance/topicality only).",
        f"QUESTION:\n{q}\n\nANSWER:\n{ans}",
    )

    # Context Precision: 검색된 컨텍스트 중 질문 해결에 유의미한 비율.
    if ctx:
        cprec = await _judge_score(
            judge,
            "You evaluate CONTEXT PRECISION: the fraction of the retrieved CONTEXTS that are relevant "
            "and useful for answering the QUESTION (given the REFERENCE key points).",
            f"QUESTION:\n{q}\n\nREFERENCE KEY POINTS:\n{ref}\n\nCONTEXTS:\n{ctx_block}",
        )
    else:
        cprec = 0.0

    # Context Recall: 기준 논지(reference) 중 검색 컨텍스트로 뒷받침되는 비율.
    if ref:
        crec = await _judge_score(
            judge,
            "You evaluate CONTEXT RECALL: the fraction of the REFERENCE key points that are supported by "
            "(can be attributed to) the retrieved CONTEXTS.",
            f"REFERENCE KEY POINTS:\n{ref}\n\nCONTEXTS:\n{ctx_block}",
        ) if ctx else 0.0
    else:
        crec = None

    return {
        "id": row.get("id"), "category": row.get("category"),
        "n_contexts": len(ctx), "answer_len": len(ans),
        "faithfulness": faith, "answer_relevancy": relev,
        "context_precision": cprec, "context_recall": crec,
    }


def _timeout_score(row: dict, reason: str) -> dict:
    return {
        "id": row.get("id"), "category": row.get("category"),
        "n_contexts": len(row.get("contexts") or []),
        "answer_len": len(row.get("answer") or ""),
        "faithfulness": 0.0,
        "answer_relevancy": None,
        "context_precision": 0.0,
        "context_recall": 0.0,
        "error": reason,
    }


def _save_partial(path: str, rows: list, scores: list):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "cases": scores}, f, ensure_ascii=False, indent=2)


async def _collect(cases, partial_path: str = None, case_timeout: int = 180, judge_timeout: int = 120):
    from services.rag_service import RAGService  # 무거운 import — 실행 시점에만
    rag = RAGService()
    judge = _make_judge()
    rows, scores = [], []
    for c in cases:
        try:
            contexts, answer, trace, source_contexts = await asyncio.wait_for(
                _run_case(rag, c["question"], bool(c.get("is_journal"))),
                timeout=case_timeout,
            )
        except asyncio.TimeoutError:
            contexts, answer, trace, source_contexts = [], "", {}, []
            print(f"  · [{c['id']}] generation timeout after {case_timeout}s", flush=True)

        row = {
            "id": c["id"], "category": c.get("category", ""),
            "question": c["question"], "answer": answer, "contexts": contexts,
            "source_contexts": source_contexts,
            "trace": trace,
            "ground_truth": " ".join(c.get("reference_points", [])),
        }
        rows.append(row)
        print(f"  · [{c['id']}] contexts={len(contexts)} answer_len={len(answer)} - judging...", flush=True)
        try:
            score = await asyncio.wait_for(_score_case(judge, row), timeout=judge_timeout)
        except asyncio.TimeoutError:
            print(f"    [judge timeout] {c['id']} after {judge_timeout}s", flush=True)
            score = _timeout_score(row, f"judge timeout after {judge_timeout}s")
        scores.append(score)
        if partial_path:
            _save_partial(partial_path, rows, scores)
    return rows, scores


def _avg(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else None


def _build_diagnostics(scores: list[dict], targets: dict) -> dict:
    diagnostics = {
        "low_cases": [],
        "retrieval_review_cases": [],
        "faithfulness_review_cases": [],
        "answer_content_cases": [],
    }
    faith_target = targets.get("faithfulness", 0.90)
    cp_target = targets.get("context_precision", 0.80)
    cr_target = targets.get("context_recall", 0.75)
    relev_target = targets.get("answer_relevancy", 0.85)

    for score in scores:
        metric_values = {
            "context_precision": score.get("context_precision"),
            "context_recall": score.get("context_recall"),
            "faithfulness": score.get("faithfulness"),
            "answer_relevancy": score.get("answer_relevancy"),
        }
        failures = []
        for key, target in (
            ("context_precision", cp_target),
            ("context_recall", cr_target),
            ("faithfulness", faith_target),
            ("answer_relevancy", relev_target),
        ):
            value = metric_values.get(key)
            if isinstance(value, (int, float)) and value < target:
                failures.append({"metric": key, "value": value, "target": target})

        if failures:
            diagnostics["low_cases"].append({
                "id": score.get("id"),
                "category": score.get("category"),
                "failures": failures,
                "metrics": {
                    **metric_values,
                    "claim_support": score.get("claim_support"),
                },
            })

        cp = score.get("context_precision")
        cr = score.get("context_recall")
        if (
            (isinstance(cp, (int, float)) and cp < cp_target)
            or (isinstance(cr, (int, float)) and cr < cr_target)
        ):
            diagnostics["retrieval_review_cases"].append(score.get("id"))

        faith = score.get("faithfulness")
        claim_support = score.get("claim_support")
        if isinstance(faith, (int, float)) and faith < faith_target:
            if isinstance(claim_support, (int, float)) and (
                claim_support >= 0.85 or claim_support - faith >= 0.15
            ):
                diagnostics["faithfulness_review_cases"].append({
                    "id": score.get("id"),
                    "faithfulness": faith,
                    "claim_support": claim_support,
                    "reason": "holistic_faithfulness_low_but_claim_support_high",
                })
            else:
                diagnostics["answer_content_cases"].append({
                    "id": score.get("id"),
                    "faithfulness": faith,
                    "claim_support": claim_support,
                    "reason": "low_faithfulness_without_high_claim_support",
                })

    diagnostics["low_cases"].sort(
        key=lambda item: (
            len(item["failures"]),
            max((failure["target"] - failure["value"] for failure in item["failures"]), default=0),
        ),
        reverse=True,
    )
    diagnostics["retrieval_review_cases"] = sorted(set(filter(None, diagnostics["retrieval_review_cases"])))
    return diagnostics


def main():
    if not os.getenv("MONGODB_URI") or not os.getenv("OPENAI_API_KEY"):
        print("[!] MONGODB_URI / OPENAI_API_KEY 가 필요합니다. (.env 확인)", file=sys.stderr)
        sys.exit(2)

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="앞 N개 문항만 평가")
    ap.add_argument("--case-id", default=None, help="쉼표로 구분한 특정 케이스 ID만 평가 (예: g05,g09,g16)")
    ap.add_argument("--case-timeout", type=int, default=180, help="문항별 생성 타임아웃(초)")
    ap.add_argument("--judge-timeout", type=int, default=120, help="문항별 LLM-judge 타임아웃(초)")
    ap.add_argument(
        "--verifier-mode",
        default=None,
        help="RAG answer verifier mode override (예: on/off). 지정하면 RAG_VERIFIER_MODE 환경변수를 덮어씁니다.",
    )
    ap.add_argument(
        "--claim-checker-mode",
        default=None,
        help="Sentence-level claim checker override (예: on/off). 지정하면 RAG_CLAIM_CHECKER_MODE 환경변수를 덮어씁니다.",
    )
    ap.add_argument(
        "--claim-support-mode",
        default="off",
        help="Optional eval-only sentence claim support metric (on/off). 기본값 off.",
    )
    ap.add_argument(
        "--claim-support-timeout",
        type=int,
        default=60,
        help="claim support judge timeout per sentence (seconds)",
    )
    ap.add_argument(
        "--answer-template-mode",
        default=None,
        help="Answer template override (예: standard/sentence). 지정하면 RAG_ANSWER_TEMPLATE_MODE 환경변수를 덮어씁니다.",
    )
    args = ap.parse_args()
    if args.verifier_mode is not None:
        os.environ["RAG_VERIFIER_MODE"] = args.verifier_mode
    if args.claim_checker_mode is not None:
        os.environ["RAG_CLAIM_CHECKER_MODE"] = args.claim_checker_mode
    if args.answer_template_mode is not None:
        os.environ["RAG_ANSWER_TEMPLATE_MODE"] = args.answer_template_mode

    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        golden = json.load(f)
    cases = golden.get("cases", [])
    if args.case_id:
        selected = {case_id.strip() for case_id in args.case_id.split(",") if case_id.strip()}
        cases = [case for case in cases if case.get("id") in selected]
    if args.limit:
        cases = cases[:args.limit]
    targets = golden.get("metric_targets", {})

    print("=" * 60)
    print(f"  RAG 품질 평가 (LLM-judge) - 골든셋 {len(cases)}개 케이스")
    print(f"  verifier_mode={os.getenv('RAG_VERIFIER_MODE', 'off')}")
    print(f"  claim_checker_mode={os.getenv('RAG_CLAIM_CHECKER_MODE', 'off')}")
    print(f"  claim_support_mode={args.claim_support_mode}")
    print(f"  answer_template_mode={os.getenv('RAG_ANSWER_TEMPLATE_MODE', 'standard')}")
    print("=" * 60)

    os.makedirs(RUNS_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    partial_out = os.path.join(RUNS_DIR, f"in_progress_{ts}.json")
    rows, scores = asyncio.run(
        _collect(
            cases,
            partial_path=partial_out,
            case_timeout=args.case_timeout,
            judge_timeout=args.judge_timeout,
        )
    )

    claim_support_report = None
    if str(args.claim_support_mode).strip().lower() in {"1", "true", "on", "yes"}:
        print("\n  claim-support 보조 지표 산출 중...", flush=True)
        import analyze_claim_support

        claim_support_report = asyncio.run(
            analyze_claim_support.analyze(
                {"rows": rows, "cases": scores},
                [score["id"] for score in scores],
                timeout=args.claim_support_timeout,
            )
        )
        claim_by_id = {case["id"]: case for case in claim_support_report.get("cases", [])}
        for score in scores:
            support_case = claim_by_id.get(score["id"])
            if support_case:
                score["claim_support"] = support_case.get("sentence_support_avg")
        for row in rows:
            support_case = claim_by_id.get(row["id"])
            if support_case:
                row["claim_support"] = {
                    "sentence_support_avg": support_case.get("sentence_support_avg"),
                    "sentences": support_case.get("sentences", []),
                }

    metrics = {
        "context_precision": targets.get("context_precision", 0.80),
        "context_recall": targets.get("context_recall", 0.75),
        "faithfulness": targets.get("faithfulness", 0.90),
        "answer_relevancy": targets.get("answer_relevancy", 0.85),
    }
    print("\n  케이스별 점수:")
    for s in scores:
        print(f"    [{s['id']:>3}] {s['category']:<14} "
              f"faith={_fmt(s['faithfulness'])} relev={_fmt(s['answer_relevancy'])} "
              f"cprec={_fmt(s['context_precision'])} crec={_fmt(s['context_recall'])} (ctx={s['n_contexts']})")

    print("\n  평균 (목표 / PRD 6.2):")
    summary, all_pass = {}, True
    for key, target in metrics.items():
        avg = _avg([s[key] for s in scores])
        summary[key] = avg
        if avg is None:
            print(f"    - {key:18s}:   N/A   (목표 >= {target})")
            continue
        ok = avg >= target
        all_pass = all_pass and ok
        print(f"    - {key:18s}: {avg:.3f} {'[PASS]' if ok else '[FAIL]'} (목표 >= {target})")

    if any("claim_support" in score for score in scores):
        avg = _avg([score.get("claim_support") for score in scores])
        summary["claim_support"] = avg
        print(f"    - {'claim_support':18s}: {avg:.3f} [INFO] (보조 지표, 목표 없음)")

    diagnostics = _build_diagnostics(scores, metrics)
    if diagnostics["low_cases"]:
        print("\n  낮은 케이스 / review 후보:")
        for item in diagnostics["low_cases"][:10]:
            failed = ", ".join(f"{failure['metric']}={failure['value']:.2f}" for failure in item["failures"])
            print(f"    - [{item['id']}] {failed}")
    if diagnostics["faithfulness_review_cases"]:
        ids = ", ".join(item["id"] for item in diagnostics["faithfulness_review_cases"])
        print(f"  judge/reference review 후보: {ids}")
    if diagnostics["answer_content_cases"]:
        ids = ", ".join(item["id"] for item in diagnostics["answer_content_cases"])
        print(f"  답변 내용 개선 후보: {ids}")
    if diagnostics["retrieval_review_cases"]:
        print(f"  검색/qrels review 후보: {', '.join(diagnostics['retrieval_review_cases'])}")

    # 결과 저장 (재현/추적용)
    out = os.path.join(RUNS_DIR, f"baseline_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "targets": metrics,
            "diagnostics": diagnostics,
            "settings": {
                "reranker_mode": os.getenv("RERANKER_MODE", "llm"),
                "verifier_mode": os.getenv("RAG_VERIFIER_MODE", "off"),
                "claim_checker_mode": os.getenv("RAG_CLAIM_CHECKER_MODE", "off"),
                "claim_support_mode": args.claim_support_mode,
                "answer_template_mode": os.getenv("RAG_ANSWER_TEMPLATE_MODE", "standard"),
            },
            "claim_support": claim_support_report,
            "cases": scores,
            "rows": rows,
        },
                  f, ensure_ascii=False, indent=2)

    print(f"\n  결과 저장: {os.path.relpath(out, BACKEND_DIR)}")
    print("  " + ("PASS" if all_pass else "FAIL - 일부 지표 목표 미달 (베이스라인)"))
    print("=" * 60)
    sys.exit(0 if all_pass else 1)


def _fmt(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else " N/A"


if __name__ == "__main__":
    main()
