import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, ReplaceOne
from tqdm import tqdm

# Load environment variables
dotenv_paths = [
    os.path.join(os.path.dirname(__file__), "../.env"),
    os.path.join(os.path.dirname(__file__), "../../.env"),
]
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)

EMBEDDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/embeddings"))
TRACK_FILE = os.path.join(EMBEDDING_DIR, "uploaded_to_mongodb_files.json")


def ensure_document_indexes(db):
    for index in db.documents.list_indexes():
        key = index.get("key", {})
        if index.get("name") != "_id_" and any(field.startswith("_fts") for field in key):
            db.documents.drop_index(index["name"])
            print(f"Legacy text index removed: {index['name']}")

    db.documents.create_index(
        [("chunk_id", ASCENDING)],
        name="documents_chunk_id_unique",
        unique=True,
        partialFilterExpression={"chunk_id": {"$type": "string"}},
    )
    db.documents.create_index(
        [("document_id", ASCENDING), ("chunk_index", ASCENDING)],
        name="documents_document_chunk",
    )


def document_id_from_record(record: dict) -> str:
    if record.get("document_id"):
        return record["document_id"]
    filename = record.get("filename") or record.get("metadata", {}).get("filename") or "unknown_document.pdf"
    return Path(filename).stem


def build_mongodb_document(record: dict) -> dict:
    metadata = dict(record.get("metadata") or {})
    document_id = document_id_from_record(record)
    filename = record.get("filename") or metadata.get("filename") or f"{document_id}.pdf"
    title = record.get("title") or metadata.get("title") or Path(filename).stem
    language = record.get("language") or metadata.get("language") or "unknown"
    text_quality = record.get("text_quality")
    if text_quality is None:
        text_quality = metadata.get("text_quality")
    chunk_index = record.get("chunk_index")

    if chunk_index is None:
        chunk_id = record.get("chunk_id", "")
        try:
            chunk_index = int(str(chunk_id).rsplit("_chunk_", 1)[1])
        except Exception:
            chunk_index = 0

    chunk_id = record.get("chunk_id") or f"{document_id}_chunk_{chunk_index}"
    metadata.update({
        "filename": filename,
        "title": title,
        "language": language,
        "text_quality": text_quality,
    })

    return {
        "content": record["text"],
        "embedding": record["embedding"],
        "chunk_id": chunk_id,
        "document_id": document_id,
        "filename": filename,
        "title": title,
        "language": language,
        "text_quality": text_quality,
        "section": record.get("section"),
        "page_start": record.get("page_start"),
        "page_end": record.get("page_end"),
        "chunk_index": chunk_index,
        "metadata": metadata,
    }


def cli_value(name: str, default=None):
    prefix = f"{name}="
    for arg in sys.argv:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
    return default


def record_is_eligible(record: dict, include_non_english: bool, min_quality: float) -> bool:
    metadata = record.get("metadata") or {}
    language = record.get("language") or metadata.get("language") or "unknown"
    quality = record.get("text_quality")
    if quality is None:
        quality = metadata.get("text_quality", 0.0)

    try:
        quality = float(quality)
    except (TypeError, ValueError):
        quality = 0.0

    if not include_non_english and language != "en":
        return False
    return quality >= min_quality


def main():
    include_non_english = "--include-non-english" in sys.argv
    min_quality = float(cli_value("--min-quality", "0.55"))

    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("Error: MONGODB_URI가 설정되지 않았습니다.")
        sys.exit(1)

    try:
        client = MongoClient(uri)
        db = client.get_default_database("logos_log")
        print(f"Connected successfully to MongoDB Atlas database: {db.name}")
    except Exception as e:
        print(f"MongoDB 연결 실패: {e}")
        sys.exit(1)

    if "--reset" in sys.argv:
        print("Reset flag detected. MongoDB의 documents 컬렉션을 초기화합니다...")
        db.documents.delete_many({})
        if os.path.exists(TRACK_FILE):
            os.remove(TRACK_FILE)
        print("documents 컬렉션 초기화 완료.")

    ensure_document_indexes(db)

    uploaded_files = []
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, "r") as f:
            uploaded_files = json.load(f)

    json_files = sorted(f for f in os.listdir(EMBEDDING_DIR) if f.endswith("_embedded.json"))
    if not json_files:
        print(f"[{EMBEDDING_DIR}] 폴더에 업로드할 임베딩 JSON 파일이 없습니다.")
        return

    print(
        f"\n전체 eligible set 업로드를 진행합니다. "
        f"include_non_english={include_non_english}, min_quality={min_quality}"
    )

    print(f"총 {len(json_files)}개 중, 이미 업로드된 {len(uploaded_files)}개를 제외하고 업로드를 진행합니다...")
    total_chunks_uploaded = 0
    total_chunks_skipped = 0
    skipped_files = 0

    for file in json_files:
        if file in uploaded_files:
            continue

        file_path = os.path.join(EMBEDDING_DIR, file)
        with open(file_path, "r", encoding="utf-8") as f:
            chunked_data = json.load(f)

        eligible_chunks = [
            record for record in chunked_data
            if record_is_eligible(record, include_non_english, min_quality)
        ]
        total_chunks_skipped += len(chunked_data) - len(eligible_chunks)

        if not eligible_chunks:
            print(f"\n[{file}] 스킵됨: 영어/품질 기준을 통과한 청크가 없습니다. ({len(chunked_data)} 청크)")
            uploaded_files.append(file)
            with open(TRACK_FILE, "w") as f:
                json.dump(uploaded_files, f)
            skipped_files += 1
            continue

        print(f"\n[{file}] 파일 업로드 중... ({len(eligible_chunks)}/{len(chunked_data)} 청크 eligible)")

        batch_size = 50
        for i in tqdm(range(0, len(eligible_chunks), batch_size)):
            batch = eligible_chunks[i:i + batch_size]
            operations = [
                ReplaceOne(
                    {"chunk_id": doc["chunk_id"]},
                    doc,
                    upsert=True,
                )
                for doc in (build_mongodb_document(record) for record in batch)
            ]

            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    db.documents.bulk_write(operations, ordered=False)
                    total_chunks_uploaded += len(batch)
                    time.sleep(0.1)
                    break
                except Exception as e:
                    print(f"\n배치 업로드 실패 (시도 {attempt}/{max_retries}): {e}")
                    if attempt == max_retries:
                        raise e
                    time.sleep(attempt * 2)

        uploaded_files.append(file)
        with open(TRACK_FILE, "w") as f:
            json.dump(uploaded_files, f)

    print(
        f"\n업로드 완료! 총 {total_chunks_uploaded}개의 청크가 MongoDB에 성공적으로 저장되었습니다. "
        f"스킵 청크: {total_chunks_skipped}, 스킵 파일: {skipped_files}"
    )


if __name__ == "__main__":
    main()
