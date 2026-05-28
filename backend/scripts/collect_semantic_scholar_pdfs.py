#!/usr/bin/env python3
"""
Collect open-access psychology PDFs using Semantic Scholar and Unpaywall.

Semantic Scholar is used to search for papers by keywords. If a paper has a DOI,
Unpaywall is queried to resolve a legally available open-access PDF URL.
If Unpaywall fails or the paper has no DOI, the Semantic Scholar openAccessPdf URL is used.
Downloaded PDFs are saved in data/raw using the Logos-Log naming convention:

    [category]_[first_author]_[year]_[title_keyword].pdf
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        pass

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "semantic_scholar_collection_manifest.csv"
STATE_PATH = RAW_DIR / "semantic_scholar_collection_state.json"

SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
UNPAYWALL_URL = "https://api.unpaywall.org/v2/{doi}"


@dataclass(frozen=True)
class Topic:
    category: str
    target: int
    queries: tuple[str, ...]


TOPICS = (
    Topic(
        category="logotherapy",
        target=150,
        queries=(
            "Viktor Frankl logotherapy",
            "Meaning in life existential vacuum",
            "Tragic optimism Frankl",
            "logotherapy meaning-centered therapy",
            "existential psychology purpose in life",
        ),
    ),
    Topic(
        category="positive_psych",
        target=150,
        queries=(
            "Positive psychology PERMA model",
            "well-being character strengths positive psychology",
            "resilience positive psychology",
            "gratitude positive psychology intervention",
            "flourishing Seligman",
        ),
    ),
    Topic(
        category="sdt",
        target=100,
        queries=(
            "Self-Determination Theory intrinsic motivation",
            "autonomy competence relatedness basic needs",
            "basic psychological needs self-determination theory",
            "Deci Ryan self-determination theory",
            "intrinsic motivation autonomy competence",
        ),
    ),
    Topic(
        category="cbt",
        target=100,
        queries=(
            "cognitive behavioral therapy cognitive distortions",
            "cognitive restructuring Socratic questioning",
            "Beck cognitive therapy cognitive restructuring",
            "cognitive distortions thinking errors",
            "Socratic questioning cognitive distortions",
        ),
    ),
)


def default_email() -> str | None:
    env_email = os.getenv("UNPAYWALL_EMAIL") or os.getenv("CROSSREF_EMAIL")
    if env_email:
        return env_email
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    email = result.stdout.strip()
    return email or None


def user_agent(email: str) -> str:
    return f"Logos-Log-SS-Collector/1.0 (mailto:{email})"


def request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 5,
    delay: float = 2.0,
) -> dict[str, Any] | None:
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", delay * (2 ** attempt)))
                wait = min(wait, 60.0)
                print(f"Rate limited by {urlparse(url).netloc}; waiting {wait:.1f}s", flush=True)
                time.sleep(wait)
                continue
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            if attempt == retries - 1:
                print(f"Request failed for {urlparse(url).netloc}: {exc}", flush=True)
                return None
            wait_time = delay * (2 ** attempt)
            print(f"Request failed. Retrying in {wait_time:.1f}s... Error: {exc}", flush=True)
            time.sleep(wait_time)
    return None


def semantic_scholar_search(
    session: requests.Session,
    query: str,
    *,
    offset: int,
    limit: int,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "offset": offset,
        "limit": limit,
        "fields": "paperId,title,authors,year,externalIds,openAccessPdf,url",
    }
    data = request_json(session, SEMANTIC_SCHOLAR_SEARCH_URL, params=params, headers=headers, timeout=30)
    return list((data or {}).get("data") or [])


def unpaywall_pdf_url(session: requests.Session, doi: str, *, email: str) -> str | None:
    data = request_json(
        session,
        UNPAYWALL_URL.format(doi=quote(doi, safe="")),
        params={"email": email},
        timeout=20,
    )
    if not data or not data.get("is_oa"):
        return None

    locations = []
    best = data.get("best_oa_location")
    if isinstance(best, dict):
        locations.append(best)
    locations.extend(data.get("oa_locations") or [])

    for location in locations:
        if not isinstance(location, dict):
            continue
        pdf_url = location.get("url_for_pdf")
        if pdf_url:
            return pdf_url
        landing_url = location.get("url")
        if landing_url and str(landing_url).lower().endswith(".pdf"):
            return landing_url
    return None


def slugify(value: str, *, max_len: int = 48) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return (value[:max_len].strip("_") or "untitled")


def first_author_slug(paper: dict[str, Any]) -> str:
    authors = paper.get("authors") or []
    if not authors:
        return "unknown"
    first = authors[0]
    name = first.get("name", "").strip()
    if not name:
        return "unknown"
    
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v", "md", "phd", "esq"}
    parts = [p for p in re.split(r'[\s,]+', name) if p]
    while parts and parts[-1].lower().replace(".", "") in suffixes:
        parts.pop()
    
    if not parts:
        return "unknown"
    
    family = parts[-1]
    return slugify(family, max_len=28)


def author_names(paper: dict[str, Any]) -> str:
    names = []
    for author in paper.get("authors") or []:
        name = author.get("name", "").strip()
        if name:
            names.append(name)
    return "; ".join(names)


def normalize_doi(paper: dict[str, Any]) -> str | None:
    external_ids = paper.get("externalIds") or {}
    doi = external_ids.get("DOI")
    if isinstance(doi, str) and doi.strip():
        return doi.strip().lower()
    return None


def filename_for(topic: Topic, paper: dict[str, Any], existing: set[str]) -> str:
    author = first_author_slug(paper)
    year = paper.get("year")
    year_str = str(year) if year is not None else "unknown"
    title = slugify(paper.get("title") or "untitled", max_len=56)
    base = f"{topic.category}_{author}_{year_str}_{title}"
    name = f"{base}.pdf"
    index = 2
    while name in existing or (RAW_DIR / name).exists():
        name = f"{base}_{index}.pdf"
        index += 1
    existing.add(name)
    return name


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"seen": [], "counts": {}, "failed_hosts": []}
    try:
        with STATE_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {"seen": [], "counts": {}, "failed_hosts": []}


def save_state(state: dict[str, Any]) -> None:
    with STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)


def seen_keys_from_manifests() -> set[str]:
    seen: set[str] = set()
    if MANIFEST_PATH.exists():
        try:
            with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    paper_key = (row.get("paper_key") or "").strip().lower()
                    if paper_key:
                        seen.add(paper_key)
                    doi = (row.get("doi") or "").strip().lower()
                    if doi:
                        seen.add(f"doi:{doi}")
        except OSError:
            pass
    return seen


def already_collected_counts() -> dict[str, int]:
    counts = {topic.category: 0 for topic in TOPICS}
    for path in RAW_DIR.glob("*.pdf"):
        for topic in TOPICS:
            if path.name.startswith(f"{topic.category}_"):
                counts[topic.category] += 1
                break
    return counts


def manifest_writer() -> tuple[Any, csv.DictWriter]:
    needs_header = not MANIFEST_PATH.exists() or MANIFEST_PATH.stat().st_size == 0
    handle = MANIFEST_PATH.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        handle,
        fieldnames=(
            "category",
            "filename",
            "title",
            "year",
            "authors",
            "doi",
            "paper_key",
            "semantic_scholar_url",
            "pdf_url",
            "source",
            "collected_at",
        ),
    )
    if needs_header:
        writer.writeheader()
    return handle, writer


def looks_like_pdf(content: bytes, content_type: str) -> bool:
    if content.startswith(b"%PDF-"):
        return True
    return "pdf" in content_type.lower() and b"<html" not in content[:1024].lower()


def download_pdf(
    session: requests.Session,
    url: str,
    path: Path,
    *,
    min_bytes: int,
    retries: int = 1,
) -> bool:
    headers = {"Accept": "application/pdf,*/*"}
    for attempt in range(retries):
        try:
            with session.get(url, headers=headers, timeout=8, stream=True, allow_redirects=True) as response:
                if response.status_code == 429:
                    wait = float(response.headers.get("Retry-After", 5 * (attempt + 1)))
                    print(f"Rate limited by {urlparse(url).netloc}; waiting {wait:.1f}s", flush=True)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                first = b""
                total = 0
                with path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if not chunk:
                            continue
                        if not first:
                            first = chunk[:2048]
                        total += len(chunk)
                        handle.write(chunk)
                content_type = response.headers.get("Content-Type", "")
                if total >= min_bytes and looks_like_pdf(first, content_type):
                    return True
        except requests.RequestException as exc:
            print(f"Download failed from {urlparse(url).netloc}: {exc}", flush=True)
        if path.exists():
            path.unlink()
        time.sleep(1.0 * (attempt + 1))
    return False


def collect(args: argparse.Namespace) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent(args.email)})

    # Build Semantic Scholar Headers
    ss_headers = {}
    if args.api_key:
        ss_headers["x-api-key"] = args.api_key
        print("Using Semantic Scholar API Key for requests.", flush=True)

    state = load_state()
    seen = set(state.get("seen") or []) | seen_keys_from_manifests()
    existing_names = {path.name for path in RAW_DIR.glob("*.pdf")}
    counts = already_collected_counts()
    failed_hosts = set(state.get("failed_hosts") or [])

    handle, writer = manifest_writer()
    try:
        for topic in TOPICS:
            target = args.targets.get(topic.category, topic.target)
            collected = counts.get(topic.category, 0)
            print(f"[{topic.category}] target={target}, existing={collected}", flush=True)
            if collected >= target:
                continue

            for query in topic.queries:
                if collected >= target:
                    break
                print(f"  Searching query: '{query}'", flush=True)
                for offset in range(0, args.max_results_per_query, args.page_size):
                    if collected >= target:
                        break
                    
                    papers = semantic_scholar_search(
                        session,
                        query,
                        offset=offset,
                        limit=args.page_size,
                        headers=ss_headers,
                    )
                    if not papers:
                        print("    No more papers found for this query.", flush=True)
                        break
                    
                    time.sleep(args.semantic_scholar_delay)

                    for paper in papers:
                        if collected >= target:
                            break
                        
                        paper_id = paper.get("paperId")
                        doi = normalize_doi(paper)
                        
                        paper_key = f"s2:{paper_id}" if paper_id else None
                        doi_key = f"doi:{doi}" if doi else None
                        
                        if (paper_key and paper_key in seen) or (doi_key and doi_key in seen):
                            continue
                        
                        if paper_key:
                            seen.add(paper_key)
                        if doi_key:
                            seen.add(doi_key)

                        pdf_url = None
                        source = ""
                        
                        # 1. Try Semantic Scholar openAccessPdf URL first (already in payload!)
                        oa_pdf = paper.get("openAccessPdf")
                        if isinstance(oa_pdf, dict):
                            pdf_url = oa_pdf.get("url")
                            source = "semantic_scholar"
                            
                        # 2. Query Unpaywall only as fallback if DOI is available
                        if not pdf_url and doi:
                            pdf_url = unpaywall_pdf_url(session, doi, email=args.email)
                            source = "unpaywall"
                            time.sleep(args.unpaywall_delay)

                        if not pdf_url:
                            continue

                        host = urlparse(pdf_url).netloc.lower()
                        if host.startswith("www."):
                            host = host[4:]
                        if host in failed_hosts:
                            continue

                        filename = filename_for(topic, paper, existing_names)
                        destination = RAW_DIR / filename
                        
                        print(f"    Downloading {filename} from {host}...", flush=True)
                        if not download_pdf(session, pdf_url, destination, min_bytes=args.min_bytes):
                            failed_hosts.add(host)
                            continue

                        collected += 1
                        counts[topic.category] = collected
                        
                        s2_url = paper.get("url") or (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else "")
                        
                        writer.writerow(
                            {
                                "category": topic.category,
                                "filename": filename,
                                "title": paper.get("title") or "untitled",
                                "year": paper.get("year") if paper.get("year") is not None else "",
                                "authors": author_names(paper),
                                "doi": doi or "",
                                "paper_key": paper_key or "",
                                "semantic_scholar_url": s2_url,
                                "pdf_url": pdf_url,
                                "source": f"{source}+semantic_scholar",
                                "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            }
                        )
                        handle.flush()
                        
                        state["seen"] = sorted(seen)
                        state["counts"] = counts
                        state["failed_hosts"] = sorted(failed_hosts)
                        save_state(state)
                        
                        print(f"    Saved {collected}/{target}: {filename}", flush=True)
                        time.sleep(args.download_delay)
    finally:
        handle.close()
        state["seen"] = sorted(seen)
        state["counts"] = counts
        state["failed_hosts"] = sorted(failed_hosts)
        save_state(state)

    print("Done.", flush=True)
    for category, count in counts.items():
        print(f"  {category}: {count}", flush=True)


def parse_targets(value: str | None) -> dict[str, int]:
    if not value:
        return {topic.category: topic.target for topic in TOPICS}
    targets = {topic.category: topic.target for topic in TOPICS}
    for item in value.split(","):
        if not item.strip():
            continue
        key, raw_count = item.split("=", 1)
        targets[key.strip()] = int(raw_count)
    return targets


def main() -> None:
    # Load dotenv from backend folder or root
    dotenv_paths = [ROOT_DIR / "backend" / ".env", ROOT_DIR / ".env"]
    for path in dotenv_paths:
        if path.exists():
            load_dotenv(path)
            break

    parser = argparse.ArgumentParser(description="Collect open-access psychology PDFs using Semantic Scholar & Unpaywall.")
    parser.add_argument(
        "--targets",
        type=parse_targets,
        default=parse_targets(None),
        help="Comma-separated category targets, e.g. logotherapy=150,positive_psych=150,sdt=100,cbt=100",
    )
    parser.add_argument("--email", default=default_email(), help="Contact email for Unpaywall requests.")
    parser.add_argument("--api-key", default=os.getenv("SEMANTIC_SCHOLAR_API_KEY"), help="Semantic Scholar API Key.")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-results-per-query", type=int, default=1000)
    parser.add_argument("--min-bytes", type=int, default=20_000)
    
    # We will adjust delay arguments later in the script depending on API key availability
    parser.add_argument("--semantic-scholar-delay", type=float, default=None, help="Delay between Semantic Scholar searches.")
    parser.add_argument("--unpaywall-delay", type=float, default=0.2, help="Delay between Unpaywall queries.")
    parser.add_argument("--download-delay", type=float, default=0.1, help="Delay between downloads.")
    args = parser.parse_args()

    if not args.email:
        args.email = "logos-log-agent@example.com"

    # Set default Semantic Scholar delay dynamically
    if args.semantic_scholar_delay is None:
        if args.api_key:
            args.semantic_scholar_delay = 0.2  # Fast delay when using API key
        else:
            args.semantic_scholar_delay = 3.5  # Polite delay when not using API key

    collect(args)


if __name__ == "__main__":
    main()
