"""
Sentence-level claim support analysis for evaluate_rag.py run files.

This is a diagnostic tool, not a production verifier. It reads an existing
RAG evaluation run, splits selected answers into sentences, and asks an LLM
judge whether each sentence is supported by the expanded generation contexts.

Usage:
  cd backend
  python eval/analyze_claim_support.py \
    --run eval/runs/combined_20260609_batched_g12_companion.json \
    --case-id g15,g03,g26
"""
import argparse
import asyncio
import datetime
import json
import os
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
RUNS_DIR = EVAL_DIR / "runs"
sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv

    for env_path in (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    citation_map = {}

    def protect(match):
        token = f"__CITATION_{len(citation_map)}__"
        citation_map[token] = match.group(0)
        return token

    protected = re.sub(r"\[\d+\]\(#source-\d+\)", protect, text)
    parts = [
        part.strip()
        for part in re.split(r"(?<=[.!?。！？])\s+|(?<=[다요죠까나요])\.\s+", protected)
        if part.strip()
    ]
    restored = []
    for part in parts:
        for token, citation in citation_map.items():
            part = part.replace(token, citation)
        restored.append(part)
    return restored


def _context_block(row: dict) -> str:
    contexts = row.get("contexts") or []
    return "\n\n".join(f"[Context {idx}]\n{ctx}" for idx, ctx in enumerate(contexts, start=1))


def _source_block(row: dict) -> str:
    sources = ((row.get("trace") or {}).get("sources") or [])
    lines = []
    for idx, src in enumerate(sources, start=1):
        title = src.get("title") or src.get("filename") or "Untitled"
        chunk_id = src.get("chunk_id") or "unknown"
        page = src.get("page_start") or "unknown"
        lines.append(f"[{idx}] {title} | chunk_id={chunk_id} | page={page}")
    return "\n".join(lines) or "(none)"


async def judge_sentence(judge, row: dict, sentence: str, index: int) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage

    system = (
        "You are a strict sentence-level faithfulness judge for Korean RAG answers.\n"
        "Classify whether ONE answer sentence is directly supported by the supplied academic contexts.\n"
        "Empathy-only sentences and open reflective questions can be marked not_applicable.\n"
        "For factual psychology, intervention, effect, causal, method/sample, or practice claims, require direct support.\n"
        "Return ONLY raw JSON with this shape:\n"
        "{"
        "\"sentence_index\": 1, "
        "\"claim_type\": \"empathy|open_question|research|effect|practice|causal|method_sample|interpretation|other\", "
        "\"support\": \"supported|partially_supported|unsupported|not_applicable\", "
        "\"support_score\": 0.0, "
        "\"source_numbers\": [1], "
        "\"problem_type\": \"none|unsupported_general_psychology|over_causal_wording|missing_citation|source_mismatch|over_generalized_context|other\", "
        "\"reason\": \"short reason\", "
        "\"minimal_fix\": \"short suggested edit\""
        "}"
    )
    payload = (
        f"CASE ID: {row.get('id')}\n"
        f"QUESTION:\n{row.get('question')}\n\n"
        f"REFERENCE POINTS:\n{row.get('ground_truth')}\n\n"
        f"SOURCES:\n{_source_block(row)}\n\n"
        f"CONTEXTS:\n{_context_block(row)}\n\n"
        f"SENTENCE INDEX: {index}\n"
        f"SENTENCE:\n{sentence}"
    )
    response = await judge.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=payload)],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.content.strip())
    data["sentence"] = sentence
    data["sentence_index"] = index
    return data


async def analyze(run: dict, case_ids: list[str], timeout: int) -> dict:
    from langchain_openai import ChatOpenAI

    selected = set(case_ids)
    rows = [row for row in run.get("rows", []) if not selected or row.get("id") in selected]
    judge = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.0)
    cases = []
    for row in rows:
        labels = []
        for idx, sentence in enumerate(split_sentences(row.get("answer") or ""), start=1):
            try:
                label = await asyncio.wait_for(judge_sentence(judge, row, sentence, idx), timeout=timeout)
            except Exception as exc:
                label = {
                    "sentence_index": idx,
                    "sentence": sentence,
                    "claim_type": "other",
                    "support": "unsupported",
                    "support_score": 0.0,
                    "source_numbers": [],
                    "problem_type": "judge_error",
                    "reason": str(exc)[:200],
                    "minimal_fix": "rerun sentence judge",
                }
            labels.append(label)
        scored = [
            item.get("support_score")
            for item in labels
            if item.get("support") != "not_applicable"
            and isinstance(item.get("support_score"), (int, float))
        ]
        cases.append({
            "id": row.get("id"),
            "question": row.get("question"),
            "answer": row.get("answer"),
            "faithfulness": next(
                (case.get("faithfulness") for case in run.get("cases", []) if case.get("id") == row.get("id")),
                None,
            ),
            "sentence_support_avg": sum(scored) / len(scored) if scored else None,
            "sentences": labels,
        })
    return {"cases": cases}


def write_markdown(report: dict, out_path: Path) -> None:
    lines = ["# Claim Support Analysis", ""]
    for case in report.get("cases", []):
        lines.extend([
            f"## {case.get('id')}",
            "",
            f"- Faithfulness: `{case.get('faithfulness')}`",
            f"- Sentence support avg: `{case.get('sentence_support_avg')}`",
            "",
            "| # | Support | Type | Problem | Sentence | Minimal fix |",
            "|---:|---|---|---|---|---|",
        ])
        for item in case.get("sentences", []):
            sentence = (item.get("sentence") or "").replace("|", "\\|")
            fix = (item.get("minimal_fix") or "").replace("|", "\\|")
            lines.append(
                f"| {item.get('sentence_index')} | {item.get('support')} | "
                f"{item.get('claim_type')} | {item.get('problem_type')} | {sentence} | {fix} |"
            )
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BACKEND_DIR.resolve()))
    except ValueError:
        return str(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, help="evaluate_rag.py run JSON")
    parser.add_argument("--case-id", default="", help="comma-separated case ids")
    parser.add_argument("--timeout", type=int, default=60, help="judge timeout per sentence")
    parser.add_argument("--out", default=None, help="output JSON path")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("[!] OPENAI_API_KEY is required", file=sys.stderr)
        sys.exit(2)

    run_path = Path(args.run)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    case_ids = [case_id.strip() for case_id in args.case_id.split(",") if case_id.strip()]
    report = asyncio.run(analyze(run, case_ids, timeout=args.timeout))

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else RUNS_DIR / f"claim_support_{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_out = out.with_suffix(".md")
    write_markdown(report, md_out)

    print(f"Saved JSON: {_display_path(out)}")
    print(f"Saved Markdown: {_display_path(md_out)}")
    for case in report.get("cases", []):
        print(f"{case.get('id')}: sentence_support_avg={case.get('sentence_support_avg')}")


if __name__ == "__main__":
    main()
