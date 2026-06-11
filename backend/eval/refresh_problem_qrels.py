"""
Refresh qrels for known low-scoring problem cases against the current corpus.

The script builds a small candidate pool per case from:
  - current multi-query vector candidates,
  - existing qrels that still exist in MongoDB,
  - source chunks selected in a previous evaluate_rag trace.

It grades candidates with a deterministic OpenAI judge against the current
golden_set reference points, then writes ignored qrels artifacts under
backend/eval/qrels/.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
EVAL_DIR = BACKEND_DIR / "eval"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(EVAL_DIR))

GOLDEN_PATH = EVAL_DIR / "golden_set.json"
DEFAULT_INPUT_QRELS = EVAL_DIR / "qrels" / "qrels_draft.json"
DEFAULT_TRACE = EVAL_DIR / "runs" / "baseline_20260608_223329.json"
DEFAULT_OUTPUT_QRELS = EVAL_DIR / "qrels" / "qrels_problem_cases.json"
DEFAULT_OUTPUT_JUDGMENTS = EVAL_DIR / "qrels" / "judgments_problem_cases.json"
DEFAULT_CASE_IDS = "g05,g13,g14,g15,g16,g20,g24"

try:
    from dotenv import load_dotenv

    for env_path in (BACKEND_DIR / ".env", PROJECT_DIR / ".env"):
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass


def _case_map():
    payload = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    return {case["id"]: case for case in payload.get("cases", [])}


def _trace_source_ids(trace_path: Path) -> dict[str, list[str]]:
    if not trace_path.exists():
        return {}
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    out = {}
    for row in payload.get("rows", []):
        ids = []
        for source in (row.get("trace") or {}).get("sources", []):
            chunk_id = source.get("chunk_id")
            if chunk_id and chunk_id not in ids:
                ids.append(chunk_id)
        out[row.get("id")] = ids
    return out


def merge_candidate_ids(vector_ids, existing_qrels, trace_ids, max_candidates: int) -> list[str]:
    grade2 = [chunk_id for chunk_id, grade in existing_qrels.items() if int(grade) == 2]
    other_qrels = [chunk_id for chunk_id, grade in existing_qrels.items() if int(grade) != 2]
    merged = []
    for group in (grade2, trace_ids, vector_ids, other_qrels):
        for chunk_id in group:
            if chunk_id and chunk_id not in merged:
                merged.append(chunk_id)
            if len(merged) >= max_candidates:
                return merged
    return merged


def _fetch_docs(db, chunk_ids: list[str]) -> dict[str, dict]:
    if not chunk_ids:
        return {}
    docs = {}
    projection = {
        "content": 1,
        "chunk_id": 1,
        "document_id": 1,
        "title": 1,
        "filename": 1,
        "section": 1,
        "page_start": 1,
        "page_end": 1,
        "chunk_index": 1,
        "metadata": 1,
    }
    for doc in db.documents.find({"chunk_id": {"$in": chunk_ids}}, projection):
        docs[doc["chunk_id"]] = doc
    return docs


def _quality_flags(doc: dict) -> list[str]:
    content = (doc.get("content") or "").strip()
    lower = content.lower()
    flags = []
    if len(content) < 220:
        flags.append("very_short_fragment")
    if lower.startswith("keywords:") or lower.startswith("| abstract") or " references " in lower[:300]:
        flags.append("metadata_or_reference_fragment")
    if "table" in lower[:200] and any(marker in lower for marker in ("study outcome", "intervention", "measure")):
        flags.append("table_fragment")

    portuguese_markers = (
        " não ", " uma ", " para ", " porém ", " também ", " sentido ",
        " vida ", " morte ", " sofrimento ", " que ", " com ", " dos ", " das ",
    )
    marker_hits = sum(1 for marker in portuguese_markers if marker in f" {lower} ")
    accented = sum(1 for ch in content if ch in "áàâãçéêíóôõúüÁÀÂÃÇÉÊÍÓÔÕÚÜ")
    if marker_hits >= 4 or accented >= 8:
        flags.append("probable_non_english")

    quality = doc.get("text_quality")
    try:
        if quality is not None and float(quality) < 0.80:
            flags.append("low_text_quality")
    except (TypeError, ValueError):
        pass
    return flags


def _case_specific_rules(case_id: str) -> str:
    rules = {
        "g11": (
            "Case g11 is about aging, fear of death, finitude, existential anxiety, and meaning. "
            "Grade 2 requires an explicit connection between death/finitude/aging/existential anxiety and meaning. "
            "Generic logotherapy or generic meaning-in-life chunks without death/finitude/aging anxiety are grade 1 at most."
        ),
        "g12": (
            "Case g12 is about grief/bereavement after losing a close person and meaning reconstruction. "
            "Grade 2 requires explicit grief, bereavement, loss of a loved one, continuing bonds, or relationship-derived meaning. "
            "Generic suffering/meaning/logotherapy chunks without bereavement or loss are grade 1 at most."
        ),
        "g15": (
            "Case g15 is about burnout/lethargy recovery in positive psychology. "
            "Grade 2 requires burnout, exhaustion, workplace stress, healthcare/worker burnout, or work engagement together with "
            "positive psychology intervention, well-being, meaning, engagement, strengths, or resource recovery. "
            "Generic stress coping, resilience, or well-being chunks without burnout/work engagement are grade 1 at most."
        ),
        "g27": (
            "Case g27 is about social anxiety and worrying how others see the user. "
            "Grade 2 requires social anxiety, fear of being judged, mind-reading assumptions, self-focused attention, "
            "or CBT/Socratic reality testing for social-evaluative thoughts. "
            "Generic cognitive restructuring or generic anxiety chunks without social-evaluative concern are grade 1 at most."
        ),
        "g29": (
            "Case g29 is about rumination over past mistakes and sleep difficulty. "
            "Grade 2 requires rumination/repetitive negative thinking/worry plus CBT, cognitive restructuring, relapse vulnerability, "
            "or sleep-specific dysfunctional beliefs/insomnia. "
            "Generic CBT, generic depression, or generic sleep chunks without rumination/worry or sleep-specific beliefs are grade 1 at most."
        ),
    }
    return rules.get(case_id, "")


async def _vector_ids_for_case(rag, case: dict, limit_per_variant: int = 20) -> tuple[list[str], list[str]]:
    from pooling import rrf_fuse, vector_candidates

    variants = await rag._expand_query_variants(case["question"])
    rankings = []
    for variant in variants[:3]:
        rankings.append([cand["id"] for cand in vector_candidates(rag, variant, limit=limit_per_variant)])
    return rrf_fuse(rankings), variants


async def _judge_candidate(judge, case: dict, doc: dict, semaphore: asyncio.Semaphore) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage

    reference = "\n".join(f"- {point}" for point in case.get("reference_points", []))
    themes = ", ".join(case.get("expected_context_themes", []))
    category = case.get("category") or "unknown"
    case_id = case.get("id") or ""
    content = (doc.get("content") or "")[:2400]
    title = doc.get("title") or (doc.get("metadata") or {}).get("title") or ""
    location = f"{doc.get('section') or 'unknown'}, page {doc.get('page_start') or 'unknown'}"
    quality_flags = _quality_flags(doc)
    quality_text = ", ".join(quality_flags) if quality_flags else "none"
    case_rules = _case_specific_rules(case_id) or "No additional case-specific rule."
    system = (
        "You are a strict relevance judge for a psychology RAG evaluation set.\n"
        "Grade whether the PAPER CHUNK supports the REFERENCE POINTS for the QUESTION.\n"
        "Use EXPECTED THEMES and CATEGORY as the rubric, not just surface-level symptom overlap.\n"
        "Scale: 0 = irrelevant; 1 = related but weak/tangential; 2 = directly supports at least one reference point and at least one expected theme.\n"
        "For category=sdt, a chunk that only discusses clinical symptoms, social anxiety, or loneliness without basic psychological needs, relatedness, belonging, social connection/support, or well-being should be grade 1 at most.\n"
        "For any category, do not assign grade 2 merely because the chunk mentions the user's problem; it must support the evaluation reference point.\n"
        "If QUALITY FLAGS include probable_non_english, table_fragment, metadata_or_reference_fragment, very_short_fragment, or low_text_quality, grade 2 is allowed only when clear English prose directly supports the case-specific reference. Otherwise grade 1 at most.\n"
        "Return ONLY raw JSON: {\"grade\": 0|1|2, \"reason\": \"short reason\"}."
    )
    user = (
        f"QUESTION:\n{case['question']}\n\n"
        f"CASE ID:\n{case_id}\n\n"
        f"CATEGORY:\n{category}\n\n"
        f"EXPECTED THEMES:\n{themes}\n\n"
        f"REFERENCE POINTS:\n{reference}\n\n"
        f"CASE-SPECIFIC STRICT RULES:\n{case_rules}\n\n"
        f"QUALITY FLAGS:\n{quality_text}\n\n"
        f"PAPER TITLE: {title}\nLOCATION: {location}\nPAPER CHUNK:\n{content}"
    )
    async with semaphore:
        try:
            response = await judge.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)],
                response_format={"type": "json_object"},
            )
            parsed = json.loads(response.content.strip())
            grade = int(parsed.get("grade", 0))
            if grade not in (0, 1, 2):
                grade = 0
            return {"grade": grade, "reason": str(parsed.get("reason", ""))[:240]}
        except Exception as exc:
            return {"grade": 0, "reason": f"judge_error: {str(exc)[:120]}"}


async def refresh(case_ids: list[str], max_candidates: int, trace_path: Path,
                  input_qrels: Path, output_qrels: Path, output_judgments: Path):
    from db import get_db
    from langchain_openai import ChatOpenAI
    from services.rag_service import RAGService

    cases = _case_map()
    qrels_payload = json.loads(input_qrels.read_text(encoding="utf-8")) if input_qrels.exists() else {"qrels": {}}
    existing_qrels = qrels_payload.get("qrels", {})
    trace_ids = _trace_source_ids(trace_path)
    db = get_db()
    rag = RAGService()
    judge = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.0, streaming=False)
    semaphore = asyncio.Semaphore(6)

    output = {"pools": {}, "qrels": {}}
    judgments = []

    for case_id in case_ids:
        case = cases[case_id]
        vector_ids, variants = await _vector_ids_for_case(rag, case)
        docs_for_existing = _fetch_docs(db, list(existing_qrels.get(case_id, {})))
        existing_for_case = {
            chunk_id: grade
            for chunk_id, grade in existing_qrels.get(case_id, {}).items()
            if chunk_id in docs_for_existing
        }
        candidate_ids = merge_candidate_ids(
            vector_ids=vector_ids,
            existing_qrels=existing_for_case,
            trace_ids=trace_ids.get(case_id, []),
            max_candidates=max_candidates,
        )
        docs = _fetch_docs(db, candidate_ids)
        candidate_ids = [chunk_id for chunk_id in candidate_ids if chunk_id in docs]

        print(f"  · [{case_id}] candidates={len(candidate_ids)} variants={variants}", flush=True)
        judged = await asyncio.gather(*[
            _judge_candidate(judge, case, docs[chunk_id], semaphore)
            for chunk_id in candidate_ids
        ])

        output["pools"][case_id] = {
            "question": case["question"],
            "category": case.get("category"),
            "query_variants": variants,
            "candidate_ids": candidate_ids,
            "n_candidates": len(candidate_ids),
        }
        for chunk_id, verdict in zip(candidate_ids, judged):
            grade = int(verdict["grade"])
            judgments.append({
                "case_id": case_id,
                "chunk_id": chunk_id,
                "grade": grade,
                "reason": verdict["reason"],
            })
            if grade >= 1:
                output["qrels"].setdefault(case_id, {})[chunk_id] = grade

    output_qrels.parent.mkdir(parents=True, exist_ok=True)
    output_qrels.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    output_judgments.write_text(json.dumps(judgments, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output_qrels}")
    print(f"wrote {output_judgments}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", default=DEFAULT_CASE_IDS)
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--input-qrels", type=Path, default=DEFAULT_INPUT_QRELS)
    parser.add_argument("--output-qrels", type=Path, default=DEFAULT_OUTPUT_QRELS)
    parser.add_argument("--output-judgments", type=Path, default=DEFAULT_OUTPUT_JUDGMENTS)
    args = parser.parse_args()

    if not os.getenv("MONGODB_URI") or not os.getenv("OPENAI_API_KEY"):
        print("[!] MONGODB_URI / OPENAI_API_KEY are required", file=sys.stderr)
        sys.exit(2)

    case_ids = [case_id.strip() for case_id in args.case_id.split(",") if case_id.strip()]
    asyncio.run(refresh(case_ids, args.max_candidates, args.trace, args.input_qrels,
                        args.output_qrels, args.output_judgments))


if __name__ == "__main__":
    main()
