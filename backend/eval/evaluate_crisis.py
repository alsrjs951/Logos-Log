"""
위기 감지(detect_crisis) 평가 스크립트.

services.safety.detect_crisis 를 골든셋(crisis_set.json)으로 평가하여
Recall / Precision / F1 을 계산한다. 안전 지표(Recall)가 임계값(기본 0.95) 미만이면
종료 코드 1 을 반환하므로 CI 게이트로 사용할 수 있다.

무거운 임베딩 모델·LLM·DB 없이 단독 실행된다.

실행:
    cd backend && python eval/evaluate_crisis.py
"""
import os
import sys
import json

# backend/ 를 import 경로에 추가하여 services.safety 를 로드
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from services.safety import detect_crisis  # noqa: E402

RECALL_TARGET = 0.95  # PRD §6.2


def load_cases(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("cases", [])


def evaluate(cases):
    tp = fp = fn = tn = 0
    false_negatives = []  # 위기인데 놓침 (가장 위험)
    false_positives = []  # 위기 아닌데 오탐
    for c in cases:
        predicted = detect_crisis(c["text"])
        actual = bool(c["is_crisis"])
        if actual and predicted:
            tp += 1
        elif actual and not predicted:
            fn += 1
            false_negatives.append(c)
        elif not actual and predicted:
            fp += 1
            false_positives.append(c)
        else:
            tn += 1

    recall = tp / (tp + fn) if (tp + fn) else 1.0
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "recall": recall, "precision": precision, "f1": f1,
        "false_negatives": false_negatives, "false_positives": false_positives,
    }


def main():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crisis_set.json")
    cases = load_cases(path)
    r = evaluate(cases)

    print("=" * 56)
    print("  위기 감지(detect_crisis) 평가 결과")
    print("=" * 56)
    print(f"  케이스: {len(cases)}개 (TP={r['tp']} FP={r['fp']} FN={r['fn']} TN={r['tn']})")
    print(f"  Recall    : {r['recall']:.3f}  (목표 ≥ {RECALL_TARGET})")
    print(f"  Precision : {r['precision']:.3f}")
    print(f"  F1        : {r['f1']:.3f}")

    if r["false_negatives"]:
        print("\n  ⚠️ 미감지(False Negative) — 위기 표현을 놓침:")
        for c in r["false_negatives"]:
            print(f"    - [{c['id']}] {c['text']}")
    if r["false_positives"]:
        print("\n  ℹ️ 오탐(False Positive) — 일상 표현을 위기로 분류:")
        for c in r["false_positives"]:
            print(f"    - [{c['id']}] {c['text']}")

    passed = r["recall"] >= RECALL_TARGET
    print("\n  " + ("✅ PASS" if passed else "❌ FAIL") +
          f" — Recall {r['recall']:.3f} {'≥' if passed else '<'} {RECALL_TARGET}")
    print("=" * 56)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
