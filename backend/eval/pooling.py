"""
후보 풀링 (Pooling) — 검색 정답지(qrels) 구축용.

질문 하나당 9,562개 문서를 모두 채점할 수 없으므로, 서로 다른 검색기(벡터 + 키워드)의
상위 결과를 합쳐 작은 후보 풀(보통 ~30개)을 만든다. 정답 문서는 거의 다 이 합집합 안에
들어오므로(TREC pooling), 이 풀만 채점하면 충분하다.

이 모듈은 맥북(오케스트레이션)에서 실행된다 — MongoDB 조회 + bge-m3 임베딩(가벼움).
무거운 LLM 채점은 label_qrels.py 가 원격 Ollama(윈도우/Tailscale)로 오프로드한다.
"""
TEXT_INDEX_NAME = "content_text"


def ensure_text_index(db):
    """documents.content 에 키워드 검색용 텍스트 인덱스를 보장(idempotent)."""
    existing = {ix.get("name") for ix in db.documents.list_indexes()}
    if TEXT_INDEX_NAME in existing:
        return False
    db.documents.create_index([("content", "text")], name=TEXT_INDEX_NAME, default_language="english")
    return True


def vector_candidates(rag, english_query: str, limit: int = 15) -> list:
    """bge-m3 임베딩 + $vectorSearch 로 broad 후보(필터·재랭킹 없이)."""
    db = rag_db(rag)
    emb = rag.embeddings.embed_query(english_query)
    pipeline = [
        {"$vectorSearch": {
            "index": "vector_index", "path": "embedding",
            "queryVector": emb, "numCandidates": max(100, limit * 8), "limit": limit,
        }},
        {"$project": {"content": 1, "metadata": 1, "score": {"$meta": "vectorSearchScore"}}},
    ]
    out = []
    for r in db.documents.aggregate(pipeline):
        out.append({"id": str(r["_id"]), "content": r.get("content", ""),
                    "metadata": r.get("metadata") or {}, "vector_score": r.get("score")})
    return out


def keyword_candidates(db, query_text: str, limit: int = 15) -> list:
    """$text 키워드 검색으로 broad 후보."""
    cur = (db.documents
           .find({"$text": {"$search": query_text}},
                 {"content": 1, "metadata": 1, "score": {"$meta": "textScore"}})
           .sort([("score", {"$meta": "textScore"})])
           .limit(limit))
    out = []
    for r in cur:
        out.append({"id": str(r["_id"]), "content": r.get("content", ""),
                    "metadata": r.get("metadata") or {}, "text_score": r.get("score")})
    return out


def pool(rag, db, english_query: str, keyword_query: str = None,
         k_vector: int = 15, k_keyword: int = 15) -> list:
    """벡터 ∪ 키워드 후보를 합치고 중복 제거. 각 후보가 어떤 검색기에서 나왔는지 기록."""
    keyword_query = keyword_query or english_query
    vec = vector_candidates(rag, english_query, k_vector)
    kw = keyword_candidates(db, keyword_query, k_keyword)

    merged = {}
    for rank, c in enumerate(vec):
        merged[c["id"]] = {**c, "sources": ["vector"], "vector_rank": rank}
    for rank, c in enumerate(kw):
        if c["id"] in merged:
            merged[c["id"]]["sources"].append("keyword")
            merged[c["id"]]["text_score"] = c.get("text_score")
            merged[c["id"]]["keyword_rank"] = rank
        else:
            merged[c["id"]] = {**c, "sources": ["keyword"], "keyword_rank": rank}
    return list(merged.values())


def rag_db(rag):
    """RAGService 가 쓰는 동일 DB 핸들."""
    from db import get_db
    return get_db()
