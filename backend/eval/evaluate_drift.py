"""
변화 감지(compute_trends) 평가 — 합성 궤적 기반.

게이트(plan):
- clear-drift recall ≥ 0.80  : 주입된 주된 이동(to)을 정확히 명명하는가
- flat/noisy false-positive ≤ 0.10 : 추세 없는 궤적에 '유의미한 변화'를 단언하지 않는가

후자가 '예쁜 그래프'와의 차별 = 과잉 정밀 방지(vision §3/§4.2).
LLM·DB 불필요, 결정론적. 실행: cd backend && python eval/evaluate_drift.py
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from services.value_trends import compute_trends  # noqa: E402
from eval.synth_trajectories import build_dataset  # noqa: E402

DRIFT_RECALL_TARGET = 0.80
FALSE_POSITIVE_TARGET = 0.10


def evaluate(trajectories):
    clear = [t for t in trajectories if t["kind"] == "clear_drift"]
    stable = [t for t in trajectories if t["kind"] in ("flat", "noisy")]

    # clear-drift recall: top_shift.to 가 주입된 to 와 일치
    detected = 0
    to_and_from = 0
    missed = []
    for t in clear:
        r = compute_trends(t["cards"])
        ts = r["then_vs_now"]["top_shift"]
        if ts and ts["to"] == t["to"]:
            detected += 1
            if ts["from"] == t["from"]:
                to_and_from += 1
        else:
            missed.append((t["from"], t["to"], ts))
    recall = detected / len(clear) if clear else 1.0
    from_recall = to_and_from / len(clear) if clear else 1.0

    # false positive: 안정/잡음 궤적인데 significant=True
    fp = 0
    fp_examples = []
    for t in stable:
        r = compute_trends(t["cards"])
        if r["then_vs_now"]["significant"]:
            fp += 1
            fp_examples.append((t["kind"], r["then_vs_now"]["top_shift"]))
    fp_rate = fp / len(stable) if stable else 0.0

    return {
        "n_clear": len(clear), "n_stable": len(stable),
        "recall": recall, "from_recall": from_recall,
        "fp_rate": fp_rate,
        "missed": missed, "fp_examples": fp_examples,
    }


def main():
    trajectories = build_dataset()
    r = evaluate(trajectories)

    print("=" * 56)
    print("  변화 감지(compute_trends) 평가 결과")
    print("=" * 56)
    print(f"  합성 궤적: {len(trajectories)}개 "
          f"(clear={r['n_clear']}, flat/noisy={r['n_stable']})")
    print(f"  Clear-drift Recall (to)     : {r['recall']:.3f}  (목표 ≥ {DRIFT_RECALL_TARGET})")
    print(f"  Clear-drift Recall (from&to): {r['from_recall']:.3f}  (참고)")
    print(f"  Flat/Noisy False-Positive   : {r['fp_rate']:.3f}  (목표 ≤ {FALSE_POSITIVE_TARGET})")

    if r["missed"]:
        print("\n  ⚠️ 미검출(주된 이동을 놓침):")
        for frm, to, ts in r["missed"][:10]:
            got = (ts["from"], ts["to"]) if ts else None
            print(f"    - 주입 {frm}→{to} | 검출 {got}")
    if r["fp_examples"]:
        print("\n  ⚠️ 오탐(무변화인데 변화 단언):")
        for kind, ts in r["fp_examples"][:10]:
            print(f"    - [{kind}] {(ts['from'], ts['to']) if ts else None}")

    passed = (r["recall"] >= DRIFT_RECALL_TARGET) and (r["fp_rate"] <= FALSE_POSITIVE_TARGET)
    print("\n  " + ("✅ PASS" if passed else "❌ FAIL"))
    print("=" * 56)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
