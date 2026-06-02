"""
검색 정답지(qrels) 반자동 구축 — 로컬 LLM 2-채점관(Ollama).

파이프라인:
  1) 골든셋 각 질문 → 영어 확장(_expand_query) → 후보 풀링(벡터 ∪ 키워드)
  2) 채점관 A 전체 패스 → 채점관 B 전체 패스 (GPU 1장 모델 스왑 최소화)
  3) 두 채점관의 '관련 여부(이진)'가 일치하면 자동 확정, 불일치만 사람 큐로
  4) 무작위 40쌍을 calibration_sample.json 으로 추출(사람이 라벨 후 신뢰도 검증)

실행 위치: 맥북(오케스트레이션). MongoDB 조회 + bge-m3 임베딩은 로컬, 무거운 LLM 채점은
원격 Ollama(윈도우 데스크톱, Tailscale)로 오프로드한다.

환경변수:
  OLLAMA_BASE_URL  원격 Ollama 주소 (예: http://<windows-tailscale-ip-or-name>:11434)
  JUDGE_A_MODEL    기본 'qwen2.5:14b-instruct-q4_K_M'
  JUDGE_B_MODEL    기본 'gemma2:9b-instruct-q4_K_M'
  MONGODB_URI, OPENAI_API_KEY  (.env)

사용:
  cd backend
  python eval/label_qrels.py --check          # Ollama 연결/모델 확인
  python eval/label_qrels.py                  # 전체 라벨링
  python eval/label_qrels.py --limit 3        # 앞 3문항만 (시범)
"""
import os
import sys
import json
import time
import random
import asyncio
import argparse

import requests

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN_PATH = os.path.join(EVAL_DIR, "golden_set.json")
OUT_DIR = os.path.join(EVAL_DIR, "qrels")

try:
    from dotenv import load_dotenv
    for _env in (os.path.join(BACKEND_DIR, ".env"), os.path.join(os.path.dirname(BACKEND_DIR), ".env")):
        if os.path.exists(_env):
            load_dotenv(_env)
            break
except ImportError:
    pass

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
JUDGE_A = os.getenv("JUDGE_A_MODEL", "qwen2.5:14b-instruct-q4_K_M")
JUDGE_B = os.getenv("JUDGE_B_MODEL", "gemma2:9b-instruct-q4_K_M")
CALIBRATION_N = 40
CHUNK_CHARS = 2000

JUDGE_SYSTEM = (
    "You are a relevance assessor for an academic retrieval system on psychology and logotherapy. "
    "Given a QUERY (a person's concern, in English) and a PAPER CHUNK from an academic paper, "
    "rate how useful the chunk is for grounding an evidence-based answer to the query.\n"
    "Scale: 0 = irrelevant; 1 = related but tangential/weak; 2 = directly relevant and useful.\n"
    "Briefly reason, then output ONLY JSON: {\"reasoning\": \"<one short sentence>\", \"relevance\": 0|1|2}."
)


def _run(coro):
    return asyncio.run(coro)


def ollama_judge(model: str, query: str, chunk: str, timeout: int = 180):
    """원격 Ollama 채점관에게 (query, chunk) 관련성을 묻고 0/1/2 정수 반환. 실패 시 None."""
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"QUERY: {query}\n\nPAPER CHUNK:\n{chunk[:CHUNK_CHARS]}"},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    try:
        r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=body, timeout=timeout)
        r.raise_for_status()
        content = r.json()["message"]["content"]
        grade = int(json.loads(content).get("relevance"))
        return grade if grade in (0, 1, 2) else None
    except Exception as e:
        print(f"    [judge {model} error] {str(e)[:120]}", flush=True)
        return None


def check_ollama():
    print(f"Ollama: {OLLAMA_BASE_URL}")
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=15)
        r.raise_for_status()
        have = {m["name"] for m in r.json().get("models", [])}
    except Exception as e:
        print(f"  ❌ 연결 실패: {str(e)[:160]}")
        print("  → 윈도우에서 Ollama 가 0.0.0.0:11434 로 떠 있고 Tailscale 로 접근 가능한지 확인하세요.")
        return False
    print(f"  ✅ 연결 OK. 보유 모델 {len(have)}개")
    ok = True
    for j in (JUDGE_A, JUDGE_B):
        present = j in have or any(h.startswith(j.split(':')[0]) for h in have)
        print(f"  {'✅' if present else '❌'} {j}")
        ok = ok and present
    if not ok:
        print("  → 누락 모델: 윈도우에서 `ollama pull <model>` 후 다시 시도.")
    return ok


def build_pairs(rag, db, cases):
    """각 질문을 영어 확장 → 풀링하여 (case, candidate) 쌍 목록을 만든다."""
    from pooling import ensure_text_index, pool
    created = ensure_text_index(db)
    if created:
        print("  · documents.content 텍스트 인덱스 생성됨(content_text)")
    pairs, pools = [], {}
    for c in cases:
        eq = _run(rag._expand_query(c["question"]))
        cands = pool(rag, db, eq, keyword_query=eq)
        pools[c["id"]] = {"question": c["question"], "english_query": eq, "n_candidates": len(cands)}
        for cand in cands:
            pairs.append({"case_id": c["id"], "query": eq, "chunk_id": cand["id"],
                          "content": cand["content"], "sources": cand["sources"]})
        print(f"  · [{c['id']}] 후보 {len(cands)}개 (확장: {eq[:60]}...)", flush=True)
    return pairs, pools


def judge_pass(pairs, model, label):
    print(f"\n=== 채점관 패스: {label} ({model}) — {len(pairs)}쌍 ===", flush=True)
    t0 = time.time()
    for i, p in enumerate(pairs):
        p[label] = ollama_judge(model, p["query"], p["content"])
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(pairs)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"  완료 ({time.time()-t0:.0f}s)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Ollama 연결/모델만 확인")
    ap.add_argument("--limit", type=int, default=None, help="앞 N개 질문만")
    ap.add_argument("--resume", action="store_true", help="Judge A 체크포인트에서 이어서(Judge B만)")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if check_ollama() else 1)

    if not os.getenv("MONGODB_URI") or not os.getenv("OPENAI_API_KEY"):
        print("[!] MONGODB_URI / OPENAI_API_KEY 필요 (.env)", file=sys.stderr)
        sys.exit(2)
    if not check_ollama():
        sys.exit(1)

    with open(GOLDEN_PATH, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    if args.limit:
        cases = cases[:args.limit]

    os.makedirs(OUT_DIR, exist_ok=True)
    ckpt = os.path.join(OUT_DIR, "_checkpoint_after_a.json")

    if args.resume and os.path.exists(ckpt):
        with open(ckpt, encoding="utf-8") as f:
            saved = json.load(f)
        pairs, pools = saved["pairs"], saved["pools"]
        print(f"체크포인트 로드: {len(pairs)}쌍 (Judge A 완료) → Judge B 만 실행", flush=True)
    else:
        from services.rag_service import RAGService
        from db import get_db
        rag, db = RAGService(), get_db()

        print(f"\n=== 후보 풀링 — {len(cases)}문항 ===", flush=True)
        pairs, pools = build_pairs(rag, db, cases)
        print(f"\n총 {len(pairs)}쌍 채점 예정 (채점관 2명 × {len(pairs)} = {len(pairs)*2}회)")

        judge_pass(pairs, JUDGE_A, "grade_a")
        _save(ckpt, {"pairs": pairs, "pools": pools})  # Judge A 결과 체크포인트(중단 대비)
        print(f"  체크포인트 저장: {os.path.relpath(ckpt, BACKEND_DIR)} (중단 시 --resume 로 이어서)", flush=True)

    judge_pass(pairs, JUDGE_B, "grade_b")

    # 합의/불일치 집계 (이진 관련성 = grade >= 1)
    qrels, disagreements, errors = {}, [], []
    for p in pairs:
        ga, gb = p.get("grade_a"), p.get("grade_b")
        if ga is None or gb is None:
            errors.append(p)
            continue
        ba, bb = ga >= 1, gb >= 1
        if ba == bb:
            if ba:  # 둘 다 관련 → 보수적으로 낮은 등급 채택
                qrels.setdefault(p["case_id"], {})[p["chunk_id"]] = min(ga, gb)
        else:
            disagreements.append({**{k: p[k] for k in ("case_id", "chunk_id", "query", "sources")},
                                  "grade_a": ga, "grade_b": gb, "content": p["content"][:500]})

    # 캘리브레이션 표본(사람 검증용) — content 포함, human_grade 빈칸
    rng = random.Random(42)
    sample = rng.sample(pairs, min(CALIBRATION_N, len(pairs)))
    calibration = [{"case_id": p["case_id"], "chunk_id": p["chunk_id"], "query": p["query"],
                    "content": p["content"][:1200], "grade_a": p.get("grade_a"),
                    "grade_b": p.get("grade_b"), "human_grade": None} for p in sample]

    os.makedirs(OUT_DIR, exist_ok=True)
    _save(os.path.join(OUT_DIR, "qrels_draft.json"), {"pools": pools, "qrels": qrels})
    _save(os.path.join(OUT_DIR, "disagreements.json"), disagreements)
    _save(os.path.join(OUT_DIR, "calibration_sample.json"), calibration)
    _save(os.path.join(OUT_DIR, "judgments_full.json"),
          [{k: p.get(k) for k in ("case_id", "chunk_id", "sources", "grade_a", "grade_b")} for p in pairs])

    n_rel = sum(len(v) for v in qrels.values())
    auto = len(pairs) - len(disagreements) - len(errors)
    print("\n" + "=" * 56)
    print("  qrels 구축 요약")
    print("=" * 56)
    print(f"  총 쌍: {len(pairs)} | 자동 확정: {auto} | 사람 검토 필요: {len(disagreements)} | 오류: {len(errors)}")
    print(f"  관련(relevant) 판정: {n_rel}쌍, {len(qrels)}문항에 분포")
    print(f"  사람 손이 닿는 곳: ① 불일치 {len(disagreements)}쌍 ② 캘리브레이션 {len(calibration)}쌍")
    print(f"  출력: {os.path.relpath(OUT_DIR, BACKEND_DIR)}/ (qrels_draft·disagreements·calibration_sample·judgments_full)")
    print("  다음: calibration_sample.json 의 human_grade 를 채운 뒤 `python eval/calibration_report.py`")
    print("=" * 56)


def _save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
