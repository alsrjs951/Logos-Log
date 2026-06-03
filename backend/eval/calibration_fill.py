"""
캘리브레이션 표본 사람 라벨링 도우미 — 한 번에 한 쌍씩 보고 0/1/2만 입력.

논문 발췌(영문)를 한국어로 번역해 보여주므로 영어를 몰라도 채점할 수 있다.
번역은 최초 1회 수행해 calibration_sample.json 에 저장(content_ko)하고, 이후엔 바로 표시한다.
편향을 막기 위해 AI 채점관(A/B) 점수는 보여주지 않는다. 중간에 멈춰도(q) 이어서 할 수 있다.

실행:
  cd backend && python eval/calibration_fill.py
이후:
  python eval/calibration_report.py   # 사람 vs AI 일치도(kappa) 확인
"""
import os
import sys
import json
import asyncio

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(EVAL_DIR, "qrels", "calibration_sample.json")
GOLDEN = os.path.join(EVAL_DIR, "golden_set.json")
CONTENT_CHARS = 700

# .env 로드 (OPENAI_API_KEY — 번역용)
try:
    from dotenv import load_dotenv
    for _env in (os.path.join(BACKEND_DIR, ".env"), os.path.join(os.path.dirname(BACKEND_DIR), ".env")):
        if os.path.exists(_env):
            load_dotenv(_env)
            break
except ImportError:
    pass


def _save(rows):
    with open(SAMPLE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def translate_missing(rows):
    """content_ko 가 없는 발췌를 한국어로 번역해 저장(최초 1회)."""
    targets = [r for r in rows if not r.get("content_ko") and r.get("content")]
    if not targets:
        return
    if not os.getenv("OPENAI_API_KEY"):
        print("[!] OPENAI_API_KEY 가 없어 번역할 수 없습니다. (.env 확인)", file=sys.stderr)
        sys.exit(2)

    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
    sys_prompt = (
        "You are an expert academic translator specializing in psychology. "
        "Translate the English paper excerpt into natural, fluent Korean that a general reader can understand. "
        "Output ONLY the Korean translation — no notes, no original text."
    )
    print(f"논문 발췌 {len(targets)}개 번역 중... (최초 1회, 잠시만요)", flush=True)

    sem = asyncio.Semaphore(6)

    async def one(r):
        async with sem:
            try:
                resp = await llm.ainvoke([
                    SystemMessage(content=sys_prompt),
                    HumanMessage(content=r["content"][:CONTENT_CHARS]),
                ])
                r["content_ko"] = resp.content.strip()
            except Exception as e:
                print(f"  번역 실패(원문 표시): {str(e)[:60]}", flush=True)
                r["content_ko"] = None

    async def run():
        await asyncio.gather(*[one(r) for r in targets])

    asyncio.run(run())
    _save(rows)
    print("번역 완료.\n", flush=True)


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

    # 표시 전에 (남은 항목의) 한국어 번역 보장
    translate_missing(todo)

    print("=" * 60)
    print("  캘리브레이션 라벨링 — 질문에 이 논문이 얼마나 관련 있나요?")
    print("  0 = 무관 | 1 = 약간 관련 | 2 = 확실히 직접 관련")
    print("  (s = 건너뛰기, q = 저장 후 종료)")
    print(f"  남은 {len(todo)}쌍 (완료 {done}/{len(rows)})")
    print("=" * 60)

    for i, r in enumerate(todo, 1):
        q = questions.get(r["case_id"], r.get("query", ""))
        body = r.get("content_ko") or r.get("content", "")
        print(f"\n[{i}/{len(todo)}]  질문: {q}")
        print("  ── 논문 발췌(한국어 번역) " + "─" * 32)
        print("  " + body[:CONTENT_CHARS].replace("\n", "\n  "))
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


if __name__ == "__main__":
    main()
