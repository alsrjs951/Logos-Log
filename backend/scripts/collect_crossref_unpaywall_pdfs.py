#!/usr/bin/env python3
"""
Collect open-access psychology PDFs with Crossref and Unpaywall.

Crossref is used to discover DOI candidates by topic. Unpaywall is then used
to resolve legally available open-access PDF URLs. Downloaded PDFs are saved in
data/raw using the Logos-Log naming convention:

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


ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "crossref_collection_manifest.csv"
STATE_PATH = RAW_DIR / "crossref_collection_state.json"

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
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
            "logotherapy Viktor Frankl",
            "meaning in life existential vacuum",
            "tragic optimism Frankl",
            "meaning-centered therapy logotherapy",
            "purpose in life logotherapy",
        ),
    ),
    Topic(
        category="positive_psych",
        target=150,
        queries=(
            "positive psychology PERMA",
            "well-being character strengths positive psychology",
            "resilience positive psychology",
            "gratitude positive psychology intervention",
            "flourishing Seligman PERMA",
        ),
    ),
    Topic(
        category="sdt",
        target=100,
        queries=(
            "self-determination theory intrinsic motivation",
            "autonomy competence relatedness",
            "basic psychological needs self-determination theory",
            "Deci Ryan self-determination theory",
            "intrinsic motivation autonomy competence relatedness",
        ),
    ),
    Topic(
        category="cbt",
        target=100,
        queries=(
            "cognitive behavioral therapy cognitive distortions",
            "cognitive restructuring Socratic questioning",
            "cognitive distortions Socratic questioning",
            "Beck cognitive therapy cognitive restructuring",
            "cognitive behavioral therapy thinking errors",
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
    return f"Logos-Log-OA-Collector/1.0 (mailto:{email})"


def request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    retries: int = 4,
    delay: float = 1.0,
) -> dict[str, Any] | None:
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, timeout=timeout)
            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", delay * (attempt + 2)))
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
            time.sleep(delay * (attempt + 1))
    return None


def crossref_search(
    session: requests.Session,
    query: str,
    *,
    offset: int,
    rows: int,
    email: str,
) -> list[dict[str, Any]]:
    params = {
        "query.bibliographic": query,
        "rows": rows,
        "offset": offset,
        "mailto": email,
        "filter": "type:journal-article",
        "select": "DOI,title,issued,published-print,published-online,author,URL,type",
    }
    data = request_json(session, CROSSREF_WORKS_URL, params=params, timeout=30)
    return list(((data or {}).get("message") or {}).get("items") or [])


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


def title_of(work: dict[str, Any]) -> str:
    title = work.get("title")
    if isinstance(title, list) and title:
        return str(title[0])
    if isinstance(title, str):
        return title
    return "untitled"


def year_from_date_parts(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    parts = value.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        return str(parts[0][0])
    return None


def year_of(work: dict[str, Any]) -> str:
    for key in ("published-print", "published-online", "issued"):
        year = year_from_date_parts(work.get(key))
        if year:
            return year
    return "unknown"


def first_author_slug(work: dict[str, Any]) -> str:
    authors = work.get("author") or []
    if not authors:
        return "unknown"
    first = authors[0]
    family = first.get("family")
    given = first.get("given")
    name = family or given or "unknown"
    return slugify(str(name), max_len=28)


def author_names(work: dict[str, Any]) -> str:
    names = []
    for author in work.get("author") or []:
        given = author.get("given") or ""
        family = author.get("family") or ""
        name = " ".join(part for part in (given, family) if part).strip()
        if name:
            names.append(name)
    return "; ".join(names)


def normalize_doi(work: dict[str, Any]) -> str | None:
    doi = work.get("DOI")
    if isinstance(doi, str) and doi.strip():
        return doi.strip().lower()
    return None


def filename_for(topic: Topic, work: dict[str, Any], existing: set[str]) -> str:
    author = first_author_slug(work)
    year = year_of(work)
    title = slugify(title_of(work), max_len=56)
    base = f"{topic.category}_{author}_{year}_{title}"
    name = f"{base}.pdf"
    index = 2
    while name in existing or (RAW_DIR / name).exists():
        name = f"{base}_{index}.pdf"
        index += 1
    existing.add(name)
    return name


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"seen": [], "counts": {}}
    with STATE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state: dict[str, Any]) -> None:
    with STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)


def seen_dois_from_manifests() -> set[str]:
    seen: set[str] = set()
    for manifest in RAW_DIR.glob("*collection_manifest.csv"):
        try:
            with manifest.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    doi = (row.get("doi") or "").strip().lower()
                    if doi:
                        seen.add(f"doi:{doi}")
        except OSError:
            continue
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
            "crossref_url",
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
            with session.get(url, headers=headers, timeout=10, stream=True, allow_redirects=True) as response:
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
        time.sleep(1.5 * (attempt + 1))
    return False


def collect(args: argparse.Namespace) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent(args.email)})

    state = load_state()
    seen = set(state.get("seen") or []) | seen_dois_from_manifests()
    existing_names = {path.name for path in RAW_DIR.glob("*.pdf")}
    counts = already_collected_counts()
    failed_hosts: set[str] = set()

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
                for offset in range(0, args.max_results_per_query, args.page_size):
                    if collected >= target:
                        break
                    works = crossref_search(
                        session,
                        query,
                        offset=offset,
                        rows=args.page_size,
                        email=args.email,
                    )
                    if not works:
                        break
                    time.sleep(args.crossref_delay)

                    for work in works:
                        if collected >= target:
                            break
                        doi = normalize_doi(work)
                        if not doi:
                            continue
                        key = f"doi:{doi}"
                        if key in seen:
                            continue
                        seen.add(key)

                        pdf_url = unpaywall_pdf_url(session, doi, email=args.email)
                        time.sleep(args.unpaywall_delay)
                        if not pdf_url:
                            continue

                        host = urlparse(pdf_url).netloc.lower()
                        if host.startswith("www."):
                            host = host[4:]
                        if host in failed_hosts:
                            continue

                        filename = filename_for(topic, work, existing_names)
                        destination = RAW_DIR / filename
                        if not download_pdf(session, pdf_url, destination, min_bytes=args.min_bytes):
                            failed_hosts.add(host)
                            continue

                        collected += 1
                        counts[topic.category] = collected
                        writer.writerow(
                            {
                                "category": topic.category,
                                "filename": filename,
                                "title": title_of(work),
                                "year": year_of(work),
                                "authors": author_names(work),
                                "doi": doi,
                                "crossref_url": work.get("URL") or f"https://doi.org/{doi}",
                                "pdf_url": pdf_url,
                                "source": "crossref+unpaywall",
                                "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            }
                        )
                        handle.flush()
                        state["seen"] = sorted(seen)
                        state["counts"] = counts
                        save_state(state)
                        print(f"  saved {collected}/{target}: {filename}", flush=True)
                        time.sleep(args.download_delay)
    finally:
        handle.close()
        state["seen"] = sorted(seen)
        state["counts"] = counts
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
    parser = argparse.ArgumentParser(description="Collect OA PDFs into data/raw using Crossref and Unpaywall.")
    parser.add_argument(
        "--targets",
        type=parse_targets,
        default=parse_targets(None),
        help="Comma-separated category targets, e.g. logotherapy=150,positive_psych=150,sdt=100,cbt=100",
    )
    parser.add_argument("--email", default=default_email(), help="Contact email for Crossref polite pool and Unpaywall.")
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--max-results-per-query", type=int, default=1000)
    parser.add_argument("--min-bytes", type=int, default=20_000)
    parser.add_argument("--crossref-delay", type=float, default=0.05)
    parser.add_argument("--unpaywall-delay", type=float, default=0.05)
    parser.add_argument("--download-delay", type=float, default=0.1)
    args = parser.parse_args()

    if not args.email:
        raise SystemExit("Crossref and Unpaywall require a contact email. Set UNPAYWALL_EMAIL or pass --email.")

    collect(args)


if __name__ == "__main__":
    main()
