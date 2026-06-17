#!/usr/bin/env python3
"""
작은 실험 추천 품질 평가.

DB나 LLM 호출 없이 추천 결과가 제품 원칙을 만족하는지 빠르게 점검한다.
기본 데이터셋은 사람이 작성한 기준 추천이며, 같은 스키마의 생성 결과 파일을
--input 으로 넘기면 동일한 루브릭으로 평가할 수 있다.
"""
import argparse
import json
import os
import re
import sys


DEFAULT_INPUT = os.path.join(os.path.dirname(__file__), "experiment_recommendation_set.json")

ACTION_MARKERS = (
    "적", "고르", "정하", "표현", "요청", "확인", "완료", "나누", "해보", "시도",
    "쓰", "기록", "만나", "보내", "정리", "선택",
)
LOW_PRESSURE_MARKERS = ("작은", "부담", "충분", "짧게", "하나", "한 명", "한 줄", "낮은")
WEEKLY_MARKERS = ("이번 주", "7일", "하루", "오늘", "한 번", "30분", "10분", "며칠")
REFLECTION_MARKERS = ("나요", "었나요", "했나요", "어땠", "?")
BANNED_PATTERNS = (
    r"반드시",
    r"무조건",
    r"해야만",
    r"치료",
    r"진단",
    r"증상",
    r"완치",
    r"효과가\s*있",
    r"효과를\s*보장",
)


def _contains_any(text, markers):
    return any(marker in text for marker in markers)


def _has_banned_claim(text):
    return any(re.search(pattern, text) for pattern in BANNED_PATTERNS)


def score_case(case):
    recommendation = case.get("recommendation") or {}
    reason = (recommendation.get("reason") or "").strip()
    experiment = (recommendation.get("experiment") or "").strip()
    reflection_question = (recommendation.get("reflection_question") or "").strip()
    combined = f"{reason}\n{experiment}\n{reflection_question}"

    expected_terms = case.get("expected_terms") or []
    card_terms = [
        str(card.get("keyword") or "")
        for card in case.get("cards") or []
        if card.get("keyword")
    ]
    grounding_terms = [*expected_terms, *card_terms]

    checks = {
        "has_required_fields": bool(reason and experiment and reflection_question),
        "experiment_is_concrete": len(experiment) >= 20 and _contains_any(experiment, ACTION_MARKERS),
        "weekly_scope": _contains_any(experiment, WEEKLY_MARKERS),
        "low_pressure": _contains_any(experiment, LOW_PRESSURE_MARKERS),
        "grounded_in_cards": _contains_any(combined, grounding_terms),
        "reflection_is_question": _contains_any(reflection_question, REFLECTION_MARKERS),
        "avoids_clinical_or_directive_claims": not _has_banned_claim(combined),
    }
    passed = sum(1 for ok in checks.values() if ok)
    score = passed / len(checks)
    return {
        "id": case.get("id"),
        "score": round(score, 3),
        "pass": score >= 0.86,
        "checks": checks,
    }


def evaluate(path):
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    results = [score_case(case) for case in cases]
    avg = sum(item["score"] for item in results) / len(results) if results else 0.0
    return {
        "input": path,
        "cases": len(results),
        "average_score": round(avg, 3),
        "pass": bool(results) and all(item["pass"] for item in results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate meaning experiment recommendation quality.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="평가할 추천 JSON 파일")
    parser.add_argument("--json", action="store_true", help="JSON만 출력")
    args = parser.parse_args()

    report = evaluate(args.input)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Experiment recommendation quality: {report['average_score']:.3f}")
        print(f"Cases: {report['cases']} | Status: {'PASS' if report['pass'] else 'FAIL'}")
        for item in report["results"]:
            status = "PASS" if item["pass"] else "FAIL"
            failed = [name for name, ok in item["checks"].items() if not ok]
            suffix = "" if not failed else f" | failed: {', '.join(failed)}"
            print(f"- {item['id']}: {item['score']:.3f} {status}{suffix}")

    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
