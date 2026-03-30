"""Semantic reranking using sentence-transformers."""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

DEFAULT_MODEL = "all-MiniLM-L6-v2"

_model_cache: dict[str, Any] = {}


def _get_model(model_name: str = DEFAULT_MODEL):
    """Lazy-load and cache the sentence transformer model."""
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer

        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def _build_doc_text(entry: dict[str, Any]) -> str:
    """Build document text from title and abstract."""
    title = entry.get("title", "")
    abstract = entry.get("abstract", "")
    if abstract:
        return f"{title}. {abstract}"
    return title


def rerank(
    entries: list[dict[str, Any]],
    query: str,
    model_name: str = DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    """Rerank entries by semantic similarity to query. Returns entries with added rerank_score."""
    if not entries or not query:
        return entries

    from sentence_transformers import util

    model = _get_model(model_name)
    docs = [_build_doc_text(e) for e in entries]

    q_emb = model.encode([query.strip()], normalize_embeddings=True)
    d_emb = model.encode(docs, normalize_embeddings=True)
    sims = util.cos_sim(q_emb, d_emb).tolist()[0]

    for entry, score in zip(entries, sims):
        entry["rerank_score"] = round(score, 4)

    return sorted(entries, key=lambda e: e["rerank_score"], reverse=True)
