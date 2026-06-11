import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables (API Key) from backend/.env or root .env
dotenv_paths = [
    os.path.join(os.path.dirname(__file__), "../.env"),
    os.path.join(os.path.dirname(__file__), "../../.env"),
]
for path in dotenv_paths:
    if os.path.exists(path):
        load_dotenv(path)

PROCESSED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/processed"))
EMBEDDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/embeddings"))


def document_id_from_data(data: dict) -> str:
    document_id = data.get("document_id")
    if document_id:
        return document_id
    return Path(data.get("filename", "unknown_document")).stem


def text_quality_score(text: str) -> float:
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return 0.0
    alpha_ratio = sum(1 for char in compact if char.isalpha()) / len(compact)
    bad_ratio = sum(1 for char in compact if char in {"�", "□", "■"}) / len(compact)
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or "")
    word_score = min(1.0, len(words) / 80)
    score = (alpha_ratio * 0.55) + (word_score * 0.45) - (bad_ratio * 2.5)
    return round(max(0.0, min(1.0, score)), 3)


def make_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def build_chunk_records(data: dict, text_splitter: RecursiveCharacterTextSplitter) -> list[dict]:
    document_id = document_id_from_data(data)
    filename = data.get("filename", f"{document_id}.pdf")
    title = data.get("title") or data.get("metadata", {}).get("title") or Path(filename).stem
    language = data.get("language") or data.get("metadata", {}).get("language") or "unknown"
    document_quality = data.get("text_quality")
    if document_quality is None:
        document_quality = data.get("metadata", {}).get("text_quality", 0.0)
    metadata = {
        **(data.get("metadata") or {}),
        "filename": filename,
        "title": title,
        "language": language,
        "text_quality": document_quality,
    }

    pages = data.get("pages") or []
    if not pages and data.get("content"):
        pages = [{"page": None, "section": None, "text": data["content"]}]

    chunked_data = []
    chunk_index = 0

    for page in pages:
        text = (page.get("text") or "").strip()
        if not text:
            continue

        page_chunks = text_splitter.split_text(text)
        for chunk in page_chunks:
            chunk_quality = text_quality_score(chunk)
            record = {
                "chunk_id": f"{document_id}_chunk_{chunk_index}",
                "document_id": document_id,
                "filename": filename,
                "title": title,
                "language": language,
                "text_quality": min(float(document_quality or 0.0), chunk_quality) if document_quality is not None else chunk_quality,
                "section": page.get("section"),
                "page_start": page.get("page"),
                "page_end": page.get("page"),
                "chunk_index": chunk_index,
                "text": chunk,
                "metadata": metadata,
            }
            chunked_data.append(record)
            chunk_index += 1

    return chunked_data


def output_is_current(out_path: str, source_path: str) -> bool:
    if not os.path.exists(out_path):
        return False
    if os.path.getmtime(source_path) > os.path.getmtime(out_path):
        return False

    try:
        with open(out_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        if not records:
            return False
        first = records[0]
        required = ("chunk_id", "document_id", "chunk_index", "page_start", "title", "language", "text_quality", "metadata")
        return all(key in first for key in required)
    except Exception:
        return False


def main():
    force = "--force" in sys.argv
    print("Using local HuggingFace Embeddings (BAAI/bge-m3)...")

    if not os.path.exists(EMBEDDING_DIR):
        os.makedirs(EMBEDDING_DIR)

    json_files = [
        f for f in os.listdir(PROCESSED_DIR)
        if f.endswith(".json") and f != "processed_files.json"
    ]
    if not json_files:
        print(f"[{PROCESSED_DIR}] 폴더에 처리할 JSON 파일이 없습니다.")
        return

    text_splitter = make_text_splitter()

    import torch
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    print(f"Running embeddings on device: {device}")

    embeddings_model = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        model_kwargs={"device": device},
    )

    @retry(wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(5))
    def embed_with_retry(chunks):
        return embeddings_model.embed_documents(chunks)

    print(f"총 {len(json_files)}개의 문서를 청킹하고 임베딩합니다...")

    for file in tqdm(json_files):
        out_filename = file.replace(".json", "_embedded.json")
        out_path = os.path.join(EMBEDDING_DIR, out_filename)
        file_path = os.path.join(PROCESSED_DIR, file)

        if not force and output_is_current(out_path, file_path):
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        chunked_data = build_chunk_records(data, text_splitter)
        if not chunked_data:
            continue

        try:
            embeddings = embed_with_retry([record["text"] for record in chunked_data])

            for record, embedding in zip(chunked_data, embeddings):
                record["embedding"] = embedding

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(chunked_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to embed {file} after retries: {e}")

    print("청킹 및 임베딩 완료! 결과물이 data/embeddings/ 폴더에 임시 저장되었습니다.")


if __name__ == "__main__":
    main()
