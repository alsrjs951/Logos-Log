import csv
import json
import os
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
from tqdm import tqdm

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/raw"))
PROCESSED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/processed"))

KNOWN_CATEGORIES = ("positive_psych", "logotherapy", "cbt", "sdt")

ENGLISH_STOPWORDS = {
    "the", "and", "that", "with", "this", "from", "were", "are", "for", "was",
    "have", "has", "had", "not", "but", "their", "they", "these", "those",
    "study", "research", "participants", "results", "findings", "discussion",
    "conclusion", "method", "methods", "analysis", "between", "among", "effect",
    "effects", "psychology", "psychological", "well", "being", "motivation",
    "meaning", "life", "positive", "cognitive", "therapy", "autonomy",
}

SECTION_ALIASES = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "background": "Introduction",
    "literature review": "Introduction",
    "method": "Methods",
    "methods": "Methods",
    "methodology": "Methods",
    "materials and methods": "Methods",
    "study design": "Methods",
    "participants": "Methods",
    "sample": "Methods",
    "results": "Results",
    "findings": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "conclusions": "Conclusion",
    "limitations": "Discussion",
}

REFERENCE_HEADINGS = {
    "references",
    "bibliography",
    "works cited",
    "reference",
}


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def clean_text(text: str) -> str:
    """
    Clean PDF page text while preserving paragraph and line boundaries for section-aware chunking.
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"http[s]?://\S+", "", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    lines = []
    for line in text.split("\n"):
        cleaned = line.strip()
        if re.fullmatch(r"\d{1,4}", cleaned):
            continue
        lines.append(cleaned)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_quality_score(text: str) -> float:
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return 0.0

    alpha_ratio = sum(1 for char in compact if char.isalpha()) / len(compact)
    bad_ratio = sum(1 for char in compact if char in {"�", "□", "■"}) / len(compact)
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or "")
    word_score = min(1.0, len(words) / 120)
    score = (alpha_ratio * 0.55) + (word_score * 0.45) - (bad_ratio * 2.5)
    return round(max(0.0, min(1.0, score)), 3)


def detect_language(text: str) -> str:
    sample_words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", (text or "").lower())[:800]
    if len(sample_words) < 80:
        return "unknown"

    english_hits = sum(1 for word in sample_words if word in ENGLISH_STOPWORDS)
    english_ratio = english_hits / len(sample_words)
    non_ascii_ratio = sum(1 for char in (text or "")[:8000] if ord(char) > 127) / max(1, len((text or "")[:8000]))

    if english_ratio >= 0.08 and non_ascii_ratio <= 0.08:
        return "en"
    return "non_en"


def document_id_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    document_id = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_").lower()
    return document_id or "unknown_document"


def title_from_slug(value: str) -> str:
    value = re.sub(r"[_-]+", " ", Path(value).stem)
    value = re.sub(r"\s+", " ", value).strip()
    return value.title() if value else "Untitled"


def parse_filename_metadata(filename: str) -> dict:
    stem = Path(filename).stem
    category = "unknown"
    remainder = stem

    for known in sorted(KNOWN_CATEGORIES, key=len, reverse=True):
        if stem == known or stem.startswith(f"{known}_"):
            category = known
            remainder = stem[len(known):].lstrip("_")
            break

    tokens = [token for token in remainder.split("_") if token]
    year_index = next(
        (idx for idx, token in enumerate(tokens) if re.fullmatch(r"(19|20)\d{2}", token)),
        None,
    )

    if year_index is None:
        author_tokens = tokens[:1]
        year = "unknown"
        title_tokens = tokens[1:]
    else:
        author_tokens = tokens[:year_index]
        year = tokens[year_index]
        title_tokens = tokens[year_index + 1:]

    author = title_from_slug("_".join(author_tokens)) if author_tokens else "Unknown"
    title_hint = title_from_slug("_".join(title_tokens)) if title_tokens else title_from_slug(stem)

    return {
        "category": category,
        "author": author,
        "year": year,
        "title_hint": title_hint,
    }


def first_author(authors: str) -> str:
    authors = normalize_spaces(authors)
    if not authors:
        return ""
    return normalize_spaces(authors.split(";")[0])


def load_sidecar_metadata(raw_dir: str = RAW_DIR) -> dict:
    metadata = {}
    if not os.path.exists(raw_dir):
        return metadata

    for name in os.listdir(raw_dir):
        if not name.endswith(".csv") or "manifest" not in name.lower():
            continue
        path = os.path.join(raw_dir, name)
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    filename = row.get("filename")
                    if filename:
                        metadata[filename] = row
        except Exception as e:
            print(f"Warning: failed to load metadata sidecar {path}: {e}")
    return metadata


def extract_title_from_first_page(first_page_text: str, fallback: str) -> str:
    lines = [normalize_spaces(line) for line in first_page_text.split("\n")]
    lines = [line for line in lines if line]

    stop_words = ("abstract", "how to cite", "issn", "doi", "www.", "http")
    candidates = []
    for line in lines[:24]:
        lower = line.lower()
        if any(marker in lower for marker in stop_words):
            continue
        if len(line) < 12 or len(line) > 180:
            continue
        if re.fullmatch(r"[\d\s.,:-]+", line):
            continue
        candidates.append(line)
        if len(candidates) >= 3:
            break

    if candidates:
        return max(candidates, key=len)
    return fallback


def normalized_heading(line: str) -> str:
    heading = normalize_spaces(line).strip(" .:-")
    heading = re.sub(r"^\d+(\.\d+)*\s*", "", heading)
    return heading.lower().strip(" .:-")


def detect_section_heading(line: str) -> str:
    heading = normalized_heading(line)
    if not heading or len(heading) > 90:
        return None

    for alias, canonical in SECTION_ALIASES.items():
        if heading == alias or heading.startswith(f"{alias} "):
            return canonical
    return None


def is_references_heading(line: str) -> bool:
    heading = normalized_heading(line)
    if len(heading) > 60:
        return False
    return heading in REFERENCE_HEADINGS


def split_page_sections(text: str, current_section: str = None) -> tuple[list[dict], str, bool]:
    """
    Split one page into section-bearing text blocks and stop before references.
    """
    sections = []
    section = current_section
    buffer = []

    def flush():
        segment = "\n".join(buffer).strip()
        if len(segment) > 50:
            sections.append({"section": section, "text": segment})
        buffer.clear()

    for line in text.split("\n"):
        if is_references_heading(line):
            flush()
            return sections, section, True

        detected = detect_section_heading(line)
        if detected:
            flush()
            section = detected
            buffer.append(line.strip())
            continue

        buffer.append(line)

    flush()
    return sections, section, False


def build_metadata(filename: str, sidecar: dict = None) -> tuple[str, dict]:
    parsed = parse_filename_metadata(filename)
    sidecar = sidecar or {}

    title = normalize_spaces(sidecar.get("title")) or parsed["title_hint"]
    authors = normalize_spaces(sidecar.get("authors"))
    author = first_author(authors) or parsed["author"]
    year = normalize_spaces(sidecar.get("year")) or parsed["year"]
    category = normalize_spaces(sidecar.get("category")) or parsed["category"]

    metadata = {
        "category": category,
        "author": author,
        "year": year,
        "filename": filename,
        "title": title,
    }

    for key in ("authors", "doi", "paper_key", "semantic_scholar_url", "pdf_url", "source"):
        value = normalize_spaces(sidecar.get(key))
        if value:
            metadata[key] = value

    return title, metadata


def process_pdf(file_path: str, metadata_lookup: dict = None) -> dict:
    """
    Extract page-preserving, section-aware text and document metadata from a PDF.
    """
    filename = os.path.basename(file_path)
    document_id = document_id_from_filename(filename)
    sidecar = (metadata_lookup or {}).get(filename, {})
    title, metadata = build_metadata(filename, sidecar)

    doc = fitz.open(file_path)
    pages = []
    current_section = None
    first_page_cleaned = ""

    try:
        for page_index, page in enumerate(doc, start=1):
            cleaned = clean_text(page.get_text("text"))
            if page_index == 1:
                first_page_cleaned = cleaned
            if len(cleaned) <= 50:
                continue

            sections, current_section, reached_references = split_page_sections(cleaned, current_section)
            for segment in sections:
                pages.append({
                    "page": page_index,
                    "section": segment["section"],
                    "text": segment["text"],
                })

            if reached_references:
                break
    finally:
        doc.close()

    content = "\n\n".join(page["text"] for page in pages)
    language = detect_language(content)
    text_quality = text_quality_score(content)

    metadata["language"] = language
    metadata["text_quality"] = text_quality

    if not sidecar.get("title"):
        title = extract_title_from_first_page(first_page_cleaned, title)
        metadata["title"] = title

    return {
        "filename": filename,
        "document_id": document_id,
        "title": title,
        "language": language,
        "text_quality": text_quality,
        "metadata": metadata,
        "pages": pages,
        "content": content,
    }


def output_is_current(out_path: str, source_path: str) -> bool:
    if not os.path.exists(out_path):
        return False
    if os.path.getmtime(source_path) > os.path.getmtime(out_path):
        return False

    try:
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            bool(data.get("pages"))
            and bool(data.get("title"))
            and bool(data.get("document_id"))
            and "language" in data
            and "text_quality" in data
        )
    except Exception:
        return False


def main():
    force = "--force" in sys.argv

    if not os.path.exists(RAW_DIR):
        print(f"Error: {RAW_DIR} 폴더가 없습니다.")
        return

    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    pdf_files = [f for f in os.listdir(RAW_DIR) if f.endswith(".pdf")]

    if not pdf_files:
        print(f"[{RAW_DIR}] 폴더에 처리할 PDF 파일이 없습니다.")
        return

    track_file = os.path.join(PROCESSED_DIR, "processed_files.json")
    processed_files = []
    if os.path.exists(track_file):
        with open(track_file, "r") as f:
            processed_files = json.load(f)

    metadata_lookup = load_sidecar_metadata(RAW_DIR)
    print(f"총 {len(pdf_files)}개의 PDF를 페이지/섹션 보존 구조로 전처리합니다...")

    for file in tqdm(pdf_files):
        file_path = os.path.join(RAW_DIR, file)
        out_filename = file.replace(".pdf", ".json")
        out_path = os.path.join(PROCESSED_DIR, out_filename)

        if not force and output_is_current(out_path, file_path):
            if file not in processed_files:
                processed_files.append(file)
            continue

        try:
            processed_data = process_pdf(file_path, metadata_lookup=metadata_lookup)

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)

            if file not in processed_files:
                processed_files.append(file)
            with open(track_file, "w") as f:
                json.dump(processed_files, f)

        except Exception as e:
            print(f"Error processing {file} (Skipping): {str(e)}")

    print("전처리 완료! 결과물이 data/processed/ 폴더에 저장되었습니다.")


if __name__ == "__main__":
    main()
