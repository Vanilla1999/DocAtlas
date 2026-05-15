"""Small ad-hoc eval over the public-domain story corpus.

A query has a target ``(file_substring, heading_substring)`` pair. A hit at
rank ``k`` counts as a recall@k hit if any of the top-k chunks references a
matching file *and* a matching heading. The harness runs each retrieval
mode and prints a comparison table so phase 4 regressions are visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docmancer.core.config import DocmancerConfig
    from docmancer.embeddings.base import EmbeddingsProvider
    from docmancer.stores.base import VectorStore


# Heuristic targets. Each entry: query, file substring (lowercased), heading substring (lowercased).
DEFAULT_QUERIES: list[tuple[str, str, str]] = [
    ("the chapter where Alice meets the caterpillar", "alice", "caterpillar"),
    ("Alice falls down a rabbit hole", "alice", "rabbit"),
    ("the Mad Hatter's tea party", "alice", "tea"),
    ("the Emperor wearing no clothes", "andersen", "emperor"),
    ("the Wizard of Oz behind the curtain", "oz", "wizard"),
    ("Sherlock Holmes investigates a snake in a bedroom", "speckled", "speckled"),
    ("Holmes meets a king disguising himself", "scandal", "bohemia"),
    ("the wolf blows down a house", "three", "pigs"),
    ("a girl in a red hood meets a wolf", "red", "riding"),
    ("Hansel and Gretel find a gingerbread house", "hansel", "gretel"),
]


@dataclass
class EvalRow:
    mode: str
    recall_at_5: float
    recall_at_10: float
    notes: str = ""


def _hit(chunk, file_sub: str, heading_sub: str) -> bool:
    src = (chunk.source or "").lower()
    meta = chunk.metadata or {}
    title = (meta.get("title") or "").lower()
    text = (chunk.text or "").lower()
    return file_sub in src and (heading_sub in title or heading_sub in text[:600])


def _recall(chunks: list, file_sub: str, heading_sub: str, k: int) -> float:
    for c in chunks[:k]:
        if _hit(c, file_sub, heading_sub):
            return 1.0
    return 0.0


def run_story_corpus_eval(
    *,
    agent,
    config: "DocmancerConfig",
    vector_store: "VectorStore | None" = None,
    provider: "EmbeddingsProvider | None" = None,
    collection: str | None = None,
    queries: list[tuple[str, str, str]] | None = None,
) -> list[EvalRow]:
    from docmancer.retrieval.dispatch import RetrievalDispatcher

    queries = queries or DEFAULT_QUERIES
    modes = ["lexical"]
    if vector_store is not None and provider is not None:
        modes.extend(["dense", "hybrid"])
        if collection is None:
            collection = agent._vector_collection_name()

    rows: list[EvalRow] = []
    for mode in modes:
        r5 = 0.0
        r10 = 0.0
        for qtext, file_sub, heading_sub in queries:
            if mode == "lexical":
                chunks = agent.query(qtext, limit=10, budget=10_000)
            else:
                dispatcher = RetrievalDispatcher(
                    store=agent.store,
                    config=config,
                    vector_store=vector_store,
                    provider=provider,
                    collection=collection,
                )
                chunks = dispatcher.run(qtext, mode=mode, limit=10, budget=10_000).chunks
            r5 += _recall(chunks, file_sub, heading_sub, 5)
            r10 += _recall(chunks, file_sub, heading_sub, 10)
        n = len(queries)
        rows.append(EvalRow(mode=mode, recall_at_5=r5 / n, recall_at_10=r10 / n))

    return rows


def format_table(rows: list[EvalRow]) -> str:
    lines = ["mode        recall@5  recall@10"]
    for r in rows:
        lines.append(f"{r.mode:11s} {r.recall_at_5:8.2f}  {r.recall_at_10:9.2f}")
    return "\n".join(lines)
