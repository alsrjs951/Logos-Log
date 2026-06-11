"""
Migrate ignored qrels artifacts from transient Mongo _id keys to stable chunk_id keys.

This is useful after rebuilding the documents collection. The old qrels were labeled
against Mongo ObjectIds, so a reset/reupload makes them unusable for retrieval evals.
The checkpoint artifact still contains the labeled chunk text; this script maps that
text to the current collection and rewrites qrels with deterministic chunk_id keys.

Usage:
  cd backend
  python eval/migrate_qrels_to_chunk_ids.py
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
EVAL_DIR = BACKEND_DIR / "eval"
DEFAULT_QRELS = EVAL_DIR / "qrels" / "qrels_draft.json"
DEFAULT_CHECKPOINT = EVAL_DIR / "qrels" / "_checkpoint_after_a.json"

try:
    from dotenv import load_dotenv

    for env_path in (BACKEND_DIR / ".env", PROJECT_DIR / ".env"):
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

WORD_RE = re.compile(r"[a-z0-9]{3,}")


def tokens(text: str) -> set[str]:
    return set(WORD_RE.findall((text or "").lower()))


def overlap_score(source: set[str], target: set[str]) -> float:
    if not source or not target:
        return 0.0
    return len(source & target) / min(len(source), len(target))


def current_documents(db):
    docs = list(db.documents.find({}, {"content": 1, "chunk_id": 1}))
    doc_tokens = [tokens(doc.get("content", "")) for doc in docs]
    freq = Counter()
    for doc_token_set in doc_tokens:
        freq.update(doc_token_set)

    inverted = defaultdict(list)
    for idx, doc_token_set in enumerate(doc_tokens):
        for token in doc_token_set:
            if freq[token] <= 300:
                inverted[token].append(idx)

    return docs, doc_tokens, freq, inverted


def best_match(source_tokens, docs, doc_tokens, freq, inverted):
    votes = Counter()
    query_terms = sorted(source_tokens, key=lambda token: freq[token])[:80]
    for token in query_terms:
        for idx in inverted.get(token, []):
            votes[idx] += 1

    best_score, best_doc = 0.0, None
    for idx, _ in votes.most_common(100):
        score = overlap_score(source_tokens, doc_tokens[idx])
        if score > best_score:
            best_score, best_doc = score, docs[idx]
    return best_score, best_doc


def migrate(qrels_path: Path, checkpoint_path: Path, output_path: Path, threshold: float, dry_run: bool):
    from db import get_db

    qrels_payload = json.loads(qrels_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    content_by_old_id = {pair["chunk_id"]: pair.get("content", "") for pair in checkpoint.get("pairs", [])}

    db = get_db()
    docs, doc_tokens, freq, inverted = current_documents(db)

    migrated_qrels = {}
    total_ids = 0
    mapped_ids = 0
    skipped_ids = []
    scores = []

    for case_id, grades in qrels_payload.get("qrels", {}).items():
        migrated_qrels[case_id] = {}
        for old_id, grade in grades.items():
            total_ids += 1
            source_tokens = tokens(content_by_old_id.get(old_id, ""))
            score, doc = best_match(source_tokens, docs, doc_tokens, freq, inverted)
            if not doc or score < threshold:
                skipped_ids.append({"case_id": case_id, "old_id": old_id, "score": round(score, 3)})
                continue

            chunk_id = doc.get("chunk_id")
            previous = migrated_qrels[case_id].get(chunk_id, 0)
            migrated_qrels[case_id][chunk_id] = max(int(grade), int(previous))
            mapped_ids += 1
            scores.append(score)

    output_payload = {
        **qrels_payload,
        "qrels": {case_id: grades for case_id, grades in migrated_qrels.items() if grades},
        "migration": {
            "source": str(qrels_path),
            "checkpoint": str(checkpoint_path),
            "id_type": "chunk_id",
            "threshold": threshold,
            "total_ids": total_ids,
            "mapped_ids": mapped_ids,
            "skipped_ids": skipped_ids,
            "mean_match_score": round(sum(scores) / len(scores), 3) if scores else None,
        },
    }

    print(f"qrels ids: {total_ids}")
    print(f"mapped: {mapped_ids}")
    print(f"skipped: {len(skipped_ids)}")
    if scores:
        print(f"mean match score: {sum(scores) / len(scores):.3f}")
    if skipped_ids[:10]:
        print("first skipped ids:")
        for item in skipped_ids[:10]:
            print(f"  {item['case_id']} {item['old_id']} score={item['score']}")

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_QRELS)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_QRELS)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not os.getenv("MONGODB_URI"):
        print("[!] MONGODB_URI is required", file=sys.stderr)
        sys.exit(2)
    migrate(args.input, args.checkpoint, args.output, args.threshold, args.dry_run)


if __name__ == "__main__":
    main()
