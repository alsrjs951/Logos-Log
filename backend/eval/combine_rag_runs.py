"""
Combine multiple evaluate_rag.py run JSON files into one aggregate report.

Usage:
  cd backend
  python eval/combine_rag_runs.py eval/runs/baseline_a.json eval/runs/baseline_b.json
"""
import argparse
import datetime
import json
import os
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent
RUNS_DIR = EVAL_DIR / "runs"


def _avg(values):
    nums = [value for value in values if isinstance(value, (int, float))]
    return sum(nums) / len(nums) if nums else None


def _build_diagnostics(cases: list[dict], targets: dict) -> dict:
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

    for case in cases:
        failures = []
        for key, target in (
            ("context_precision", cp_target),
            ("context_recall", cr_target),
            ("faithfulness", faith_target),
            ("answer_relevancy", relev_target),
        ):
            value = case.get(key)
            if isinstance(value, (int, float)) and value < target:
                failures.append({"metric": key, "value": value, "target": target})
        if failures:
            diagnostics["low_cases"].append({
                "id": case.get("id"),
                "category": case.get("category"),
                "failures": failures,
                "metrics": {
                    "context_precision": case.get("context_precision"),
                    "context_recall": case.get("context_recall"),
                    "faithfulness": case.get("faithfulness"),
                    "answer_relevancy": case.get("answer_relevancy"),
                    "claim_support": case.get("claim_support"),
                },
            })

        cp = case.get("context_precision")
        cr = case.get("context_recall")
        if (
            (isinstance(cp, (int, float)) and cp < cp_target)
            or (isinstance(cr, (int, float)) and cr < cr_target)
        ):
            diagnostics["retrieval_review_cases"].append(case.get("id"))

        faith = case.get("faithfulness")
        claim_support = case.get("claim_support")
        if isinstance(faith, (int, float)) and faith < faith_target:
            if isinstance(claim_support, (int, float)) and (
                claim_support >= 0.85 or claim_support - faith >= 0.15
            ):
                diagnostics["faithfulness_review_cases"].append({
                    "id": case.get("id"),
                    "faithfulness": faith,
                    "claim_support": claim_support,
                    "reason": "holistic_faithfulness_low_but_claim_support_high",
                })
            else:
                diagnostics["answer_content_cases"].append({
                    "id": case.get("id"),
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


def _load_run(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("cases"), list) or not isinstance(data.get("rows"), list):
        raise ValueError(f"{path} is not an evaluate_rag.py run JSON")
    return data


def combine_payloads(payloads: list[dict]) -> dict:
    cases_by_id = {}
    rows_by_id = {}
    targets = None
    settings = []

    for data in payloads:
        if targets is None:
            targets = data.get("targets", {})
        settings.append(data.get("settings") or {})
        for case in data.get("cases", []):
            case_id = case.get("id")
            if case_id:
                cases_by_id[case_id] = case
        for row in data.get("rows", []):
            row_id = row.get("id")
            if row_id:
                rows_by_id[row_id] = row

    ordered_ids = sorted(cases_by_id)
    cases = [cases_by_id[case_id] for case_id in ordered_ids]
    rows = [rows_by_id[case_id] for case_id in ordered_ids if case_id in rows_by_id]
    metric_keys = ["context_precision", "context_recall", "faithfulness", "answer_relevancy"]
    optional_keys = sorted({
        key
        for case in cases
        for key, value in case.items()
        if key not in {"id", "category", "n_contexts", "answer_len", "error"}
        and isinstance(value, (int, float))
        and key not in metric_keys
    })
    summary = {
        key: _avg([case.get(key) for case in cases])
        for key in [*metric_keys, *optional_keys]
    }
    diagnostics = _build_diagnostics(cases, targets or {})
    return {
        "summary": summary,
        "targets": targets or {},
        "diagnostics": diagnostics,
        "settings": {"combined_from": settings},
        "cases": cases,
        "rows": rows,
    }


def combine(paths: list[Path]) -> dict:
    payloads = []
    for path in paths:
        data = _load_run(path)
        data["settings"] = {"path": str(path), **(data.get("settings") or {})}
        payloads.append(data)
    return combine_payloads(payloads)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", help="evaluate_rag.py JSON files to combine")
    parser.add_argument("--out", default=None, help="output JSON path")
    args = parser.parse_args()

    paths = [Path(path) for path in args.runs]
    combined = combine(paths)

    if args.out:
        out = Path(args.out)
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = RUNS_DIR / f"combined_{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"Combined {len(paths)} run files into {os.path.relpath(out, BACKEND_DIR)}")
    print(f"Cases: {len(combined['cases'])}")
    for key, value in combined["summary"].items():
        print(f"{key}: {value:.3f}" if isinstance(value, (int, float)) else f"{key}: N/A")


if __name__ == "__main__":
    main()
