"""
캘리브레이션 표본 사람 라벨링 도우미 — 한 번에 한 쌍씩 보고 0/1/2만 입력.

JSON을 손으로 고칠 필요 없이, 질문과 논문 발췌를 보여주고 점수를 받아 즉시 저장한다.
편향을 막기 위해 AI 채점관(A/B) 점수는 보여주지 않는다. 중간에 멈춰도(q) 이어서 할 수 있다.

실행:
  cd backend && python eval/calibration_fill.py
이후:
  python eval/calibration_report.py   # 사람 vs AI 일치도(kappa) 확인
"""
import os
import sys
import json

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(EVAL_DIR, "qrels", "calibration_sample.json")
GOLDEN = os.path.join(EVAL_DIR, "golden_set.json")
CONTENT_CHARS = 700


def main():
    if not os.path.exists(SAMPLE):
        print(f"[!] 없음: {SAMPLE}\n    먼저 label_qrels.py 를 실행하세요.", file=sys.stderr)
        sys.exit(2)

    questions = {c["id"]: c["question"] for c in json.load(open(GOLDEN, encoding="utf-8"))["cases"]}
    with open(SAMPLE, encoding="utf-8") as f:
        rows = json.load(f)

    todo = [r for r in rows if r.get("human_grade") is None]
    done = len(rows) - len(todo)
    if not todo:
        print(f"이미 {len(rows)}쌍 모두 라벨링됨. python eval/calibration_report.py 를 실행하세요.")
        return

    print("=" * 60)
    print("  캘리브레이션 라벨링 — 질문에 이 논문이 얼마나 관련 있나요?")
    print("  0 = 무관 | 1 = 약간 관련 | 2 = 확실히 직접 관련")
    print("  (s = 건너뛰기, q = 저장 후 종료)")
    print(f"  남은 {len(todo)}쌍 (완료 {done}/{len(rows)})")
    print("=" * 60)

    for i, r in enumerate(todo, 1):
        q = questions.get(r["case_id"], r.get("query", ""))
        print(f"\n[{i}/{len(todo)}]  질문: {q}")
        print("  ── 논문 발췌 " + "─" * 44)
        print("  " + r.get("content", "")[:CONTENT_CHARS].replace("\n", "\n  "))
        print("  " + "─" * 56)
        while True:
            ans = input("  점수 (0/1/2, s=건너뛰기, q=종료): ").strip().lower()
            if ans == "q":
                _save(rows)
                print(f"\n저장됨. 다시 실행하면 이어서 진행됩니다. (남은 {len(todo)-i+1}쌍)")
                return
            if ans == "s":
                break
            if ans in ("0", "1", "2"):
                r["human_grade"] = int(ans)
                _save(rows)  # 즉시 저장(중단 대비)
                break
            print("  → 0, 1, 2, s, q 중 하나를 입력하세요.")

    _save(rows)
    n = sum(1 for r in rows if r.get("human_grade") is not None)
    print(f"\n완료! {n}/{len(rows)}쌍 라벨링됨.")
    print("다음: python eval/calibration_report.py  (사람 vs AI 채점관 일치도 확인)")


def _save(rows):
    with open(SAMPLE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
