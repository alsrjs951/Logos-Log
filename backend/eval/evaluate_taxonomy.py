"""
가치 택소노미 분류(classify_value) 평가.

(keyword, insight) → Schwartz canonical value 분류 정확도를 라벨셋(taxonomy_set.json)으로
측정한다. top-1 accuracy 가 게이트(기본 0.80) 미만이면 종료 코드 1.

LLM(gpt-4o-mini)을 호출하므로 OPENAI_API_KEY 가 필요하다(DB·임베딩 불필요).
실행: cd backend && python eval/evaluate_taxonomy.py
"""
import os
import sys
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

# .env 로드 (OPENAI_API_KEY)
try:
    from dotenv import load_dotenv
    for _env in (os.path.join(BACKEND_DIR, ".env"), os.path.join(os.path.dirname(BACKEND_DIR), ".env")):
        if os.path.exists(_env):
            load_dotenv(_env)
            break
except ImportError:
    pass

from services.value_taxonomy import classify_value, VALUE_KEYS  # noqa: E402

TOP1_TARGET = 0.80


def load_cases(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("cases", [])


def _macro_f1(rows):
    """rows: [(gold, pred)] (pred 가 None 이면 미분류). 클래스별 F1의 단순 평균."""
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    golds = set(g for g, _ in rows)
    for gold, pred in rows:
        if pred == gold:
            tp[gold] += 1
        else:
            fn[gold] += 1
            if pred in VALUE_KEYS:
                fp[pred] += 1
    f1s = []
    for cls in golds:
        prec = tp[cls] / (tp[cls] + fp[cls]) if (tp[cls] + fp[cls]) else 0.0
        rec = tp[cls] / (tp[cls] + fn[cls]) if (tp[cls] + fn[cls]) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        f1s.append(f1)
    return sum(f1s) / len(f1s) if f1s else 0.0


def main():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomy_set.json")
    cases = load_cases(path)
    print(f"분류 평가 시작: {len(cases)}개 케이스 (gpt-4o-mini)...", flush=True)

    def run(case):
        pred, conf, method = classify_value(case["keyword"], case.get("insight", ""))
        return case, pred, conf, method

    results = list(ThreadPoolExecutor(max_workers=8).map(run, cases))

    rows = []
    correct = 0
    unmapped = 0
    errors = []
    for case, pred, conf, method in results:
        gold = case["gold"]
        rows.append((gold, pred))
        if pred == gold:
            correct += 1
        else:
            if pred is None:
                unmapped += 1
            errors.append((case["id"], case["keyword"], gold, pred, round(conf, 2)))

    n = len(cases)
    top1 = correct / n if n else 0.0
    macro_f1 = _macro_f1(rows)

    print("=" * 56)
    print("  가치 택소노미 분류 평가 결과")
    print("=" * 56)
    print(f"  케이스    : {n}개")
    print(f"  Top-1 Acc : {top1:.3f}  (목표 ≥ {TOP1_TARGET})")
    print(f"  Macro-F1  : {macro_f1:.3f}")
    print(f"  미분류    : {unmapped}개 (confidence < 임계)")

    if errors:
        print("\n  오분류/미분류:")
        for cid, kw, gold, pred, conf in errors:
            print(f"    - [{cid}] '{kw}' gold={gold} pred={pred} conf={conf}")

    passed = top1 >= TOP1_TARGET
    print("\n  " + ("✅ PASS" if passed else "❌ FAIL") +
          f" — Top-1 {top1:.3f} {'≥' if passed else '<'} {TOP1_TARGET}")
    print("=" * 56)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
