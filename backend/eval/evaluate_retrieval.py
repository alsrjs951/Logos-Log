"""
검색 전략 비교 평가 — 정답지(qrels) 기반.

    label_qrels.py 로 만든 정답지에 대해 검색 전략의 순위 품질을 비교한다:
  - vector   : bge-m3 임베딩 + multi-query $vectorSearch RRF
  - production_vector : vector-only RRF + production focus boost (현재 프로덕션 후보 정렬)
  - keyword  : $text 키워드 검색 (실험 전용)
  - hybrid   : vector + keyword RRF (실험 전용)

LLM 채점이 필요 없으므로 맥에서 바로 실행된다(MongoDB + bge-m3 + OpenAI 쿼리확장만).
'관련'은 정답지의 grade==2(두 채점관 모두 직접 관련)로 정의하며, nDCG는 등급(1/2)을 이득으로 쓴다.

실행:
  cd backend && python eval/evaluate_retrieval.py
"""
import os
import sys
import json
import math
import asyncio
import atexit
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_DIR)
GOLDEN_PATH = os.path.join(EVAL_DIR, "golden_set.json")
QRELS_PATH = os.path.join(EVAL_DIR, "qrels", "qrels_draft.json")
TOPK = 10

try:
    from dotenv import load_dotenv
    for _env in (os.path.join(BACKEND_DIR, ".env"), os.path.join(os.path.dirname(BACKEND_DIR), ".env")):
        if os.path.exists(_env):
            load_dotenv(_env)
            break
except ImportError:
    pass


def precision_at_k(ranked, rel, k):
    if not rel:
        return None
    topk = ranked[:k]
    return sum(1 for d in topk if d in rel) / k


def recall_at_k(ranked, rel, k):
    if not rel:
        return None
    topk = ranked[:k]
    return sum(1 for d in topk if d in rel) / len(rel)


def reciprocal_rank(ranked, rel):
    if not rel:
        return None
    for i, d in enumerate(ranked):
        if d in rel:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(ranked, grades, k):
    """grades: {chunk_id: grade(1/2)} — 등급을 이득으로 쓰는 nDCG."""
    if not grades:
        return None
    dcg = sum(grades.get(d, 0) / math.log2(i + 2) for i, d in enumerate(ranked[:k]))
    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else None


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else float("nan")


def _existing_qrel_ids(db, qrels):
    ids = sorted({chunk_id for grades in qrels.values() for chunk_id in grades})
    if not ids:
        return set(), 0
    existing = set(db.documents.distinct("chunk_id", {"chunk_id": {"$in": ids}}))
    return existing, len(ids) - len(existing)


def main():
    if not os.getenv("MONGODB_URI") or not os.getenv("OPENAI_API_KEY"):
        print("[!] MONGODB_URI / OPENAI_API_KEY 필요 (.env)", file=sys.stderr)
        sys.exit(2)

    parser = argparse.ArgumentParser()
    parser.add_argument("--qrels", default=QRELS_PATH, help="qrels JSON 경로")
    parser.add_argument("--case-id", default=None, help="쉼표로 구분한 특정 케이스 ID만 평가")
    args = parser.parse_args()

    if not os.path.exists(args.qrels):
        print(f"[!] 정답지 없음: {args.qrels}\n    먼저 label_qrels.py 또는 refresh_problem_qrels.py 를 실행하세요.", file=sys.stderr)
        sys.exit(2)

    cases = json.load(open(GOLDEN_PATH, encoding="utf-8"))["cases"]
    if args.case_id:
        selected = {case_id.strip() for case_id in args.case_id.split(",") if case_id.strip()}
        cases = [case for case in cases if case.get("id") in selected]
    qrels = json.load(open(args.qrels, encoding="utf-8"))["qrels"]

    from services.rag_service import RAGService
    from db import get_db
    from pooling import drop_text_index, ensure_text_index, keyword_candidates, rrf_fuse, vector_candidates
    rag, db = RAGService(), get_db()
    atexit.register(drop_text_index, db)
    created_text_index = ensure_text_index(db)
    if created_text_index:
        print("  · 실험용 documents.content 텍스트 인덱스 생성됨(content_text)", flush=True)
    existing_qrel_ids, missing_qrel_ids = _existing_qrel_ids(db, qrels)
    if missing_qrel_ids:
        print(f"  · 현재 corpus에 없는 qrels chunk {missing_qrel_ids}개 제외 후 평가", flush=True)

    strategies = ("vector", "production_vector", "keyword", "hybrid", "hybrid_vw")
    acc = {s: {"P@5": [], f"P@{TOPK}": [], f"R@{TOPK}": [], f"nDCG@{TOPK}": [], "MRR": []} for s in strategies}
    n_eval = 0

    print(f"=== 검색 전략 비교 - {len(cases)}문항 (관련=grade2) ===", flush=True)
    for c in cases:
        cid = c["id"]
        grades = {k: int(v) for k, v in qrels.get(cid, {}).items() if k in existing_qrel_ids}
        rel = {k for k, g in grades.items() if g == 2}
        if not rel:
            print(f"  · [{cid}] grade2 정답 없음 - 건너뜀", flush=True)
            continue
        n_eval += 1

        variants = asyncio.run(rag._expand_query_variants(c["question"]))
        eq = variants[0] if variants else c["question"]
        vec_rankings = [[x["id"] for x in vector_candidates(rag, variant, limit=20)] for variant in variants[:3]]
        vec = rrf_fuse(vec_rankings)[:20]
        production_doc_rankings = []
        for variant_index, variant in enumerate(variants[:3]):
            results = rag._vector_search(db, variant, variant_index=variant_index, limit=15)
            production_doc_rankings.append([
                rag._candidate_from_result(res)
                for res in results
                if res.get("content")
            ])
        production_vector = [
            doc.get("chunk_id") or doc.get("id")
            for doc in rag._apply_focus_boosts(
                rag._merge_vector_rankings(production_doc_rankings, limit=24),
                c["question"],
                variants,
            )
        ][:20]
        kw = [x["id"] for x in keyword_candidates(db, eq, limit=20)]
        hyb = rrf_fuse([vec, kw])
        hyb_vw = rrf_fuse([vec, kw], weights=[2.0, 1.0])  # 벡터 가중 하이브리드

        ranked = {
            "vector": vec,
            "production_vector": production_vector,
            "keyword": kw,
            "hybrid": hyb,
            "hybrid_vw": hyb_vw,
        }
        for s in strategies:
            r = ranked[s]
            acc[s]["P@5"].append(precision_at_k(r, rel, 5))
            acc[s][f"P@{TOPK}"].append(precision_at_k(r, rel, TOPK))
            acc[s][f"R@{TOPK}"].append(recall_at_k(r, rel, TOPK))
            acc[s][f"nDCG@{TOPK}"].append(ndcg_at_k(r, grades, TOPK))
            acc[s]["MRR"].append(reciprocal_rank(r, rel))
        print(f"  · [{cid}] 정답 {len(rel)}개 | "
              f"R@{TOPK} vec={recall_at_k(vec,rel,TOPK):.2f} prod={recall_at_k(production_vector,rel,TOPK):.2f} kw={recall_at_k(kw,rel,TOPK):.2f} "
              f"hyb={recall_at_k(hyb,rel,TOPK):.2f}", flush=True)

    metrics = ["P@5", f"P@{TOPK}", f"R@{TOPK}", f"nDCG@{TOPK}", "MRR"]
    print("\n" + "=" * 64)
    print(f"  결과 (평균, {n_eval}문항)")
    print("=" * 64)
    print(f"  {'전략':<10}" + "".join(f"{m:>11}" for m in metrics))
    for s in strategies:
        print(f"  {s:<10}" + "".join(f"{_avg(acc[s][m]):>11.3f}" for m in metrics))
    print("=" * 64)

    # 하이브리드 vs 벡터(프로덕션) 개선폭
    print("  하이브리드 - production_vector(프로덕션 후보 정렬) 개선폭:")
    for m in metrics:
        d = _avg(acc["hybrid"][m]) - _avg(acc["production_vector"][m])
        print(f"    {m:>10}: {d:+.3f}")
    print("=" * 64)
    if drop_text_index(db):
        print("  실험용 텍스트 인덱스 제거 완료(content_text)")


if __name__ == "__main__":
    main()
