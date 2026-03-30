"""CLI for paperpile-search."""

from __future__ import annotations

import argparse
import json
import sys

from .library import (
    get_cache_info,
    list_folders,
    list_tags,
    load_library,
    resolve_pdf_path,
    resolve_pdf_paths,
    search,
)
from .ranker import rerank


def _json_out(data, compact: bool = False):
    indent = None if compact else 2
    print(json.dumps(data, ensure_ascii=False, indent=indent))


def cmd_fetch(args):
    entries = load_library(force_refresh=args.force)
    info = get_cache_info()
    print(json.dumps({
        "status": "ok",
        "entry_count": len(entries),
        "fetched_at": info.get("fetched_at"),
    }, indent=2))


def cmd_status(args):
    info = get_cache_info()
    info["status"] = "ok" if info.get("cache_exists") else "no_cache"
    _json_out(info)


def cmd_search(args):
    entries = load_library()
    limit = args.limit
    # When reranking, fetch more candidates so ranking is meaningful
    search_limit = max(limit * 5, 200) if args.rerank else limit
    results = search(
        entries,
        text=args.text,
        author=args.author,
        tags=args.tag,
        folder=args.folder,
        year=args.year,
        limit=search_limit,
    )
    if args.rerank and results:
        results = rerank(results, args.rerank)
        results = results[:limit]
    # Add resolved PDF paths
    for r in results:
        r["pdf_path"] = resolve_pdf_path(r)
        r["all_pdf_paths"] = resolve_pdf_paths(r)
    _json_out({"count": len(results), "results": results}, compact=args.compact)


def cmd_info(args):
    entries = load_library()
    for e in entries:
        if e["citekey"] == args.citekey:
            e["pdf_path"] = resolve_pdf_path(e)
            _json_out(e)
            return
    print(json.dumps({"error": f"Citekey '{args.citekey}' not found"}), file=sys.stderr)
    sys.exit(1)


def cmd_pdf_path(args):
    entries = load_library()
    for e in entries:
        if e["citekey"] == args.citekey:
            path = resolve_pdf_path(e)
            if path:
                print(path)
            else:
                print("No file field for this entry", file=sys.stderr)
                sys.exit(1)
            return
    print(f"Citekey '{args.citekey}' not found", file=sys.stderr)
    sys.exit(1)


def cmd_folders(args):
    entries = load_library()
    _json_out(list_folders(entries))


def cmd_tags(args):
    entries = load_library()
    tags = list_tags(entries, min_count=args.min_count)
    if args.limit:
        tags = tags[: args.limit]
    _json_out(tags)


def main():
    parser = argparse.ArgumentParser(
        prog="paperpile-search",
        description="Search your Paperpile library",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # fetch
    p = sub.add_parser("fetch", help="Fetch/refresh BibTeX cache")
    p.add_argument("--force", "-f", action="store_true", help="Force refresh even if cache is fresh")
    p.set_defaults(func=cmd_fetch)

    # status
    p = sub.add_parser("status", help="Show cache status")
    p.set_defaults(func=cmd_status)

    # search
    p = sub.add_parser("search", help="Search library metadata")
    p.add_argument("--text", "-t", help="Free-text search (title, abstract, journal, author)")
    p.add_argument("--author", "-a", help="Author name")
    p.add_argument("--tag", "-k", action="append", help="Paperpile tag/keyword (repeatable, ANDed)")
    p.add_argument("--folder", "-d", help="Paperpile folder name")
    p.add_argument("--year", "-y", help="Year or year range (e.g. 2020, 2018-2023)")
    p.add_argument("--limit", "-n", type=int, default=50, help="Max results (default 50)")
    p.add_argument("--rerank", "-r", help="Rerank results by semantic similarity to this query")
    p.add_argument("--compact", "-c", action="store_true", help="Compact JSON output")
    p.set_defaults(func=cmd_search)

    # info
    p = sub.add_parser("info", help="Full metadata for a citekey")
    p.add_argument("citekey", help="BibTeX citekey")
    p.set_defaults(func=cmd_info)

    # pdf-path
    p = sub.add_parser("pdf-path", help="Get PDF path for a citekey")
    p.add_argument("citekey", help="BibTeX citekey")
    p.set_defaults(func=cmd_pdf_path)

    # folders
    p = sub.add_parser("folders", help="List Paperpile folders")
    p.set_defaults(func=cmd_folders)

    # tags
    p = sub.add_parser("tags", help="List Paperpile tags/keywords")
    p.add_argument("--min-count", "-m", type=int, default=2, help="Min usage count (default 2)")
    p.add_argument("--limit", "-n", type=int, default=None, help="Max tags to show")
    p.set_defaults(func=cmd_tags)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
