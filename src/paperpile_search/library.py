"""Core library: fetch, parse, cache, and search Paperpile BibTeX data."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "paperpile-search"
CACHE_FILE = CACHE_DIR / "library.json"
META_FILE = CACHE_DIR / "meta.json"

DEFAULT_BIBTEX_URL = "https://paperpile.com/eb/QDCSfGwpzr"
DEFAULT_PAPERPILE_ROOT = (
    Path.home()
    / "Library"
    / "CloudStorage"
    / "GoogleDrive-nemesp@gmail.com"
    / "My Drive"
    / "Paperpile"
)
MAX_CACHE_AGE_S = 24 * 3600  # 24 hours


# ---------------------------------------------------------------------------
# BibTeX parsing — lightweight, no external dependency needed
# ---------------------------------------------------------------------------

_ENTRY_RE = re.compile(
    r"@(\w+)\s*\{([^,]+),\s*(.*?)\n\}",
    re.DOTALL,
)

_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"((?:[^\"]|\"\")*)\"|(\d+))",
    re.DOTALL,
)


def _clean(value: str) -> str:
    """Collapse whitespace and strip wrapping braces/quotes."""
    value = re.sub(r"\s+", " ", value).strip()
    # Remove BibTeX braces used for case protection
    value = re.sub(r"\{([^{}]*)\}", r"\1", value)
    return value


def parse_bibtex(text: str) -> list[dict[str, Any]]:
    """Parse a BibTeX string into a list of entry dicts."""
    entries: list[dict[str, Any]] = []
    for m in _ENTRY_RE.finditer(text):
        entry_type = m.group(1).upper()
        citekey = m.group(2).strip()
        body = m.group(3)

        record: dict[str, Any] = {
            "entry_type": entry_type,
            "citekey": citekey,
        }
        for fm in _FIELD_RE.finditer(body):
            key = fm.group(1).lower()
            val = fm.group(2) or fm.group(3) or fm.group(4) or ""
            record[key] = _clean(val)

        # Post-process keywords into a list
        if "keywords" in record:
            raw = record["keywords"]
            # Paperpile uses semicolons, some use commas
            sep = ";" if ";" in raw else ","
            record["keywords"] = [k.strip() for k in raw.split(sep) if k.strip()]
        else:
            record["keywords"] = []

        # Post-process year to int
        if "year" in record:
            try:
                record["year"] = int(record["year"])
            except (ValueError, TypeError):
                pass

        entries.append(record)
    return entries


# ---------------------------------------------------------------------------
# Fetch and cache
# ---------------------------------------------------------------------------


def _read_meta() -> dict[str, Any]:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text())
    return {}


def _write_meta(meta: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    META_FILE.write_text(json.dumps(meta))


def fetch_bibtex(url: str = DEFAULT_BIBTEX_URL) -> str:
    """Download BibTeX from the Paperpile export URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "paperpile-search/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def cache_is_fresh(max_age: int = MAX_CACHE_AGE_S) -> bool:
    meta = _read_meta()
    fetched = meta.get("fetched_at", 0)
    return (time.time() - fetched) < max_age and CACHE_FILE.exists()


def load_library(force_refresh: bool = False, url: str = DEFAULT_BIBTEX_URL) -> list[dict[str, Any]]:
    """Load the library, fetching and caching BibTeX if needed."""
    if not force_refresh and cache_is_fresh():
        return json.loads(CACHE_FILE.read_text())

    bibtex = fetch_bibtex(url)
    entries = parse_bibtex(bibtex)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(entries, ensure_ascii=False))
    _write_meta({"fetched_at": time.time(), "entry_count": len(entries), "url": url})
    return entries


def get_cache_info() -> dict[str, Any]:
    """Return cache metadata."""
    meta = _read_meta()
    meta["cache_exists"] = CACHE_FILE.exists()
    if meta.get("fetched_at"):
        age_h = (time.time() - meta["fetched_at"]) / 3600
        meta["age_hours"] = round(age_h, 1)
    return meta


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _matches_text(entry: dict, query: str) -> bool:
    """Case-insensitive text match against title, abstract, journal, author."""
    q = query.lower()
    for field in ("title", "abstract", "journal", "author"):
        val = entry.get(field, "")
        if isinstance(val, str) and q in val.lower():
            return True
    return False


def _matches_author(entry: dict, author: str) -> bool:
    a = author.lower()
    return a in entry.get("author", "").lower()


def _matches_tag(entry: dict, tag: str) -> bool:
    t = tag.lower()
    return any(t in kw.lower() for kw in entry.get("keywords", []))


def _matches_folder(entry: dict, folder: str) -> bool:
    f = folder.lower()
    file_path = entry.get("file", "")
    return f in file_path.lower()


def _matches_year(entry: dict, year_spec: str) -> bool:
    """Match year or year range (e.g. '2020', '2018-2023')."""
    y = entry.get("year")
    if y is None:
        return False
    if isinstance(y, str):
        try:
            y = int(y)
        except ValueError:
            return False
    if "-" in year_spec:
        parts = year_spec.split("-", 1)
        try:
            return int(parts[0]) <= y <= int(parts[1])
        except ValueError:
            return False
    try:
        return y == int(year_spec)
    except ValueError:
        return False


def search(
    entries: list[dict[str, Any]],
    *,
    text: str | None = None,
    author: str | None = None,
    tag: str | None = None,
    folder: str | None = None,
    year: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search entries. All criteria are ANDed together."""
    results = entries
    if text:
        results = [e for e in results if _matches_text(e, text)]
    if author:
        results = [e for e in results if _matches_author(e, author)]
    if tag:
        results = [e for e in results if _matches_tag(e, tag)]
    if folder:
        results = [e for e in results if _matches_folder(e, folder)]
    if year:
        results = [e for e in results if _matches_year(e, year)]
    return results[:limit]


def resolve_pdf_paths(entry: dict[str, Any], root: Path = DEFAULT_PAPERPILE_ROOT) -> list[str]:
    """Return absolute PDF paths for an entry (handles semicolon-separated files)."""
    rel = entry.get("file", "")
    if not rel:
        return []
    parts = [p.strip() for p in rel.split(";") if p.strip()]
    return [str(root / p) for p in parts]


def resolve_pdf_path(entry: dict[str, Any], root: Path = DEFAULT_PAPERPILE_ROOT) -> str | None:
    """Return the first absolute PDF path for an entry, or None."""
    paths = resolve_pdf_paths(entry, root)
    return paths[0] if paths else None


def list_folders(entries: list[dict[str, Any]]) -> list[dict[str, str | int]]:
    """Extract unique folder names from the file field, with counts."""
    folders: dict[str, int] = {}
    for e in entries:
        f = e.get("file", "")
        parts = f.split("/")
        if len(parts) >= 3:
            # file = "All Papers/FolderName/file.pdf"
            folder_name = parts[1]
            folders[folder_name] = folders.get(folder_name, 0) + 1
    return sorted(
        [{"name": k, "count": v} for k, v in folders.items()],
        key=lambda x: x["count"],
        reverse=True,
    )


def list_tags(entries: list[dict[str, Any]], min_count: int = 1) -> list[dict[str, str | int]]:
    """Extract unique tags/keywords with counts."""
    tags: dict[str, int] = {}
    for e in entries:
        for kw in e.get("keywords", []):
            kw_lower = kw.lower().strip()
            if kw_lower:
                tags[kw_lower] = tags.get(kw_lower, 0) + 1
    return sorted(
        [{"tag": k, "count": v} for k, v in tags.items() if v >= min_count],
        key=lambda x: x["count"],
        reverse=True,
    )
