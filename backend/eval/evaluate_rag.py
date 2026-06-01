"""
RAG 검색·답변 품질 평가 (Tier 2).

골든셋(golden_set.json)의 각 질문을 프로덕션 경로(RAGService.get_streaming_response)로
그대로 실행하여 검색 청크(contexts)와 생성 답변(answer)을 수집하고, Ragas로
Context Precision/Recall, Faithfulness, Answer Relevancy 를 산출한다.

⚠️ 이 스크립트는 외부 인프라가 필요하여 레포 작성 환경에서는 실행 검증되지 않았다.
   아래 전제를 갖춘 환경에서 실행/검증해야 한다.

전제 조건:
  - MongoDB Atlas `documents` 적재 + `vector_index` (1024차원) 생성
  - .env: MONGODB_URI, OPENAI_API_KEY
  - 평가 의존성: pip install -r backend/eval/requirements-eval.txt
    (Ragas API는 버전에 민감하다. requirements-eval.txt 에 핀된 버전 기준으로 작성되었으며,
     다른 버전 사용 시 컬럼명/임포트 조정이 필요할 수 있다 — 예: ground_truth ↔ reference.)

실행:
  cd backend && python eval/evaluate_rag.py
"""
import os
import sys
import json
import asyncio

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_set.json")

# .env 로드 (backend/.env 우선, 없으면 프로젝트 루트) — 환경변수 가드보다 먼저 수행해야 한다.
try:
    from dotenv import load_dotenv
    for _env in (os.path.join(BACKEND_DIR, ".env"), os.path.join(os.path.dirname(BACKEND_DIR), ".env")):
        if os.path.exists(_env):
            load_dotenv(_env)
            break
except ImportError:
    pass


def _parse_sse(line: str):
    """get_streaming_response 가 내보내는 'data: {json}\\n\\n' 한 줄을 파싱한다."""
    line = line.strip()
    if not line.startswith("data: "):
        return None
    try:
        return json.loads(line[len("data: "):])
    except (ValueError, json.JSONDecodeError):
        return None


async def _run_case(rag, question: str, is_journal: bool):
    """질문 하나를 프로덕션 스트리밍 경로로 실행하여 (contexts, answer)를 수집한다."""
    contexts, answer = [], ""
    async for evt in rag.get_streaming_response(
        query=question, history=[], is_journal=is_journal, journal_id=None, user_id=None
    ):
        payload = _parse_sse(evt)
        if not payload:
            continue
        ptype = payload.get("type")
        if ptype == "sources":
            contexts = [s.get("content", "") for s in payload.get("data", []) if s.get("content")]
        elif ptype == "chunk":
            answer += payload.get("data", "")
    return contexts, answer


async def _collect(cases):
    """RAGService 를 1회 생성하여 모든 케이스를 실행한다(모델 로드 비용 절약)."""
    from services.rag_service import RAGService  # 무거운 import (torch/bge-m3) — 실행 시점에만
    rag = RAGService()
    rows = []
    for c in cases:
        contexts, answer = await _run_case(rag, c["question"], bool(c.get("is_journal")))
        rows.append({
            "question": c["question"],
            "answer": answer,
            "contexts": contexts,
            "ground_truth": " ".join(c.get("reference_points", [])),
            "category": c.get("category", ""),
        })
        print(f"  · [{c['id']}] contexts={len(contexts)} answer_len={len(answer)}", flush=True)
    return rows


def _score_with_ragas(rows):
    """Ragas 로 4개 지표를 산출한다. (requirements-eval.txt 핀 버전 기준)"""
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness, answer_relevancy, context_precision, context_recall,
        )
    except ImportError as e:
        print(f"\n[!] 평가 의존성 미설치: {e}\n    pip install -r backend/eval/requirements-eval.txt", file=sys.stderr)
        sys.exit(2)

    ds = Dataset.from_dict({
        "question":     [r["question"] for r in rows],
        "answer":       [r["answer"] for r in rows],
        "contexts":     [r["contexts"] for r in rows],
        "ground_truth": [r["ground_truth"] for r in rows],
    })
    result = evaluate(
        ds,
        metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
    )
    return result


def main():
    if not os.getenv("MONGODB_URI") or not os.getenv("OPENAI_API_KEY"):
        print("[!] MONGODB_URI / OPENAI_API_KEY 가 필요합니다. (.env 확인)", file=sys.stderr)
        sys.exit(2)

    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        golden = json.load(f)
    cases = golden.get("cases", [])
    targets = golden.get("metric_targets", {})

    print("=" * 60)
    print(f"  RAG 품질 평가 — 골든셋 {len(cases)}개 케이스")
    print("=" * 60)

    rows = asyncio.run(_collect(cases))
    result = _score_with_ragas(rows)

    # Ragas 결과 객체에서 지표별 평균을 추출 (버전에 따라 dict 유사 접근)
    print("\n  지표 결과 (목표 / PRD §6.2):")
    metric_keys = {
        "context_precision": targets.get("context_precision", 0.80),
        "context_recall": targets.get("context_recall", 0.75),
        "faithfulness": targets.get("faithfulness", 0.90),
        "answer_relevancy": targets.get("answer_relevancy", 0.85),
    }
    all_pass = True
    for key, target in metric_keys.items():
        try:
            score = float(result[key])
        except (KeyError, TypeError, ValueError):
            score = None
        if score is None:
            print(f"    - {key:18s}:   N/A   (목표 ≥ {target})")
            all_pass = False
            continue
        ok = score >= target
        all_pass = all_pass and ok
        print(f"    - {key:18s}: {score:.3f} {'✅' if ok else '❌'} (목표 ≥ {target})")

    print("\n  " + ("✅ PASS" if all_pass else "❌ FAIL — 일부 지표가 목표 미달"))
    print("=" * 60)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
