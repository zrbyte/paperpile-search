# paperpile-search

CLI tool to search your [Paperpile](https://paperpile.com) library metadata from the terminal. Parses the BibTeX export, caches it locally, and provides fast search by author, title, year, tags, folders, and free text.

Built to work as a backend for agentic paper search and analysis in [Claude Code](https://claude.ai/code).

## Install

```bash
pip install -e .
```

## Setup

The tool fetches your library from a Paperpile BibTeX export URL. The default URL and PDF root path are configured in `library.py` — edit them to match your setup, or the tool will prompt on first use.

The BibTeX cache is stored in `~/.cache/paperpile-search/` and auto-refreshes after 24 hours.

## Usage

```bash
# Fetch/refresh the BibTeX cache
paperpile-search fetch
paperpile-search fetch --force        # force refresh

# Search
paperpile-search search --text "graphene transport"
paperpile-search search --author "Castro Neto" --year 2009
paperpile-search search --tag STM --tag graphene --year 2020-2025
paperpile-search search --folder "ABC STM" --limit 10

# Semantic reranking (uses sentence-transformers, scores against title + abstract)
paperpile-search search --tag rhombohedral-graphite --rerank "superconductivity mechanisms"

# Browse
paperpile-search folders              # list folders with paper counts
paperpile-search tags --limit 20      # list most-used tags

# Single entry
paperpile-search info Castro_Neto2009-xy
paperpile-search pdf-path Castro_Neto2009-xy

# Cache status
paperpile-search status
```

All search flags are ANDed together. `--tag` can be repeated to require multiple tags. Output is JSON.

## Semantic reranking

The `--rerank` flag scores search results by cosine similarity between your query and each paper's title + abstract, using the `all-MiniLM-L6-v2` sentence transformer. This is useful when metadata filters return many results and you want the most semantically relevant ones at the top. Each result gets a `rerank_score` (0–1) in the JSON output.

When reranking, the tool automatically widens the initial search (up to 5x the requested limit) before scoring and truncating, so you get the best matches even from a large candidate pool.

## How it works

Paperpile can export your entire library as a continuously updated BibTeX file at a stable URL. This tool downloads that export, parses it into a searchable JSON cache, and provides CLI access to the metadata — including the `file` field that maps each entry to its PDF in Google Drive.

No files in your Paperpile PDF folder are ever read, modified, or created by this tool.

## License

MIT
