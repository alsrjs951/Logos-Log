"""
캘리브레이션 리포트 — 로컬 LLM 채점관을 믿어도 되는지 사람 표본으로 검증.

사용:
  1) eval/qrels/calibration_sample.json 의 각 항목 "human_grade" 를 0/1/2 로 채운다(사람).
  2) cd backend && python eval/calibration_report.py

사람 라벨(이진 관련성 = grade>=1)과 각 채점관(A/B)의 일치율 및 Cohen's kappa 를 출력한다.
kappa 가 낮으면(<0.6) 채점관을 키우거나 채점 기준/프롬프트를 다듬어 재측정한다.
"""
import os
import sys
import json

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(EVAL_DIR, "qrels", "calibration_sample.json")


def cohen_kappa(a, b):
    """이진 라벨 두 리스트의 Cohen's kappa."""
    n = len(a)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1 = sum(a) / n
    pb1 = sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def main():
    if not os.path.exists(PATH):
        print(f"[!] 없음: {PATH}\n    먼저 label_qrels.py 를 실행하세요.", file=sys.stderr)
        sys.exit(2)
    with open(PATH, encoding="utf-8") as f:
        rows = json.load(f)

    labeled = [r for r in rows if r.get("human_grade") is not None]
    if not labeled:
        print(f"[!] human_grade 가 채워진 항목이 없습니다. ({len(rows)}쌍 중 0개)\n"
              f"    {os.path.relpath(PATH, EVAL_DIR)} 의 human_grade 를 0/1/2 로 채운 뒤 다시 실행.", file=sys.stderr)
        sys.exit(2)

    print("=" * 60)
    print(f"  캘리브레이션 — 사람 라벨 {len(labeled)}쌍")
    print("=" * 60)
    # 두 임계값으로 본다: ≥1(관련 전체)과 ==2(직접 관련). 코퍼스가 전부 심리학이라
    # ≥1은 base rate가 높아(거의 다 관련) 변별력이 낮다 → ==2가 의미 있는 기준이다.
    for thr_name, thr in (("관련 전체 (grade ≥ 1)", 1), ("직접 관련 (grade == 2)", 2)):
        def binr(g, t=thr):
            return 1 if (g is not None and g >= t) else 0
        h = [binr(r["human_grade"]) for r in labeled]
        base = sum(h) / len(h)
        print(f"\n  [{thr_name}]  사람 양성률 {base:.0%}")
        for judge in ("grade_a", "grade_b"):
            usable = [(binr(r["human_grade"]), binr(r.get(judge)))
                      for r in labeled if r.get(judge) is not None]
            if not usable:
                continue
            hh = [x for x, _ in usable]
            jj = [y for _, y in usable]
            agree = sum(1 for x, y in zip(hh, jj) if x == y) / len(usable)
            k = cohen_kappa(hh, jj)
            print(f"    {judge}: 일치율 {agree:.2f} | kappa {k:.2f}")
    print("\n" + "=" * 60)
    print("  기준: kappa 0.2~0.4 약함 · 0.4~0.6 보통 · 0.6~0.8 양호 · >0.8 매우좋음")
    print("  ※ '직접 관련(==2)' kappa 를 주 지표로 보라(≥1은 base rate가 높아 왜곡).")


if __name__ == "__main__":
    main()
