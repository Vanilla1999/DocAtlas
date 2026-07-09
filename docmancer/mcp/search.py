"""Tool Search corpus + ranking (spec 2.7 / D10).

Keep this dependency-light so `doc-atlas mcp serve` works in a minimal
install, but rank with BM25-style IDF instead of raw token overlap.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from docmancer.mcp.manifest import InstalledPackage
from docmancer.mcp.slug import tool_name as build_tool_name


@dataclass
class ToolEntry:
    name: str
    package: str
    version: str
    operation_id: str
    description: str
    safety: dict[str, Any]
    input_schema: dict[str, Any]


def build_corpus(packages: list[InstalledPackage]) -> list[ToolEntry]:
    out: list[ToolEntry] = []
    for pkg in packages:
        try:
            tools = pkg.tools()
        except FileNotFoundError:
            continue
        for raw in tools:
            op_id = raw.get("operation_id") or raw.get("id") or raw.get("name")
            if not op_id:
                continue
            out.append(
                ToolEntry(
                    name=build_tool_name(pkg.package, pkg.version, op_id),
                    package=pkg.package,
                    version=pkg.version,
                    operation_id=op_id,
                    description=raw.get("description") or raw.get("summary") or "",
                    safety=raw.get("safety", {}),
                    input_schema=raw.get("inputSchema", {}),
                )
            )
    return out


_WORD_RE = re.compile(r"[A-Za-z0-9]+")

_SYNONYMS: dict[str, tuple[str, ...]] = {
    "create": ("open", "add", "new"),
    "open": ("create",),
    "issue": ("ticket", "bug"),
    "ticket": ("issue",),
    "delete": ("remove", "destroy"),
    "remove": ("delete",),
    "list": ("search", "find"),
    "find": ("search", "list"),
}


def _tokens(text: str, *, expand: bool = False) -> list[str]:
    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    if not expand:
        return tokens
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(_SYNONYMS.get(token, ()))
    return expanded


def search(
    corpus: list[ToolEntry],
    query: str,
    *,
    package: str | None = None,
    limit: int = 5,
) -> list[ToolEntry]:
    q = _tokens(query, expand=True)
    if not q:
        return []
    candidates = [t for t in corpus if package is None or t.package == package]
    documents = [_tokens(f"{t.operation_id} {t.description}") for t in candidates]
    if not documents:
        return []
    doc_freq: Counter[str] = Counter()
    for tokens in documents:
        doc_freq.update(set(tokens))
    avg_len = sum(len(tokens) for tokens in documents) / len(documents)
    query_terms = Counter(q)
    scored: list[tuple[float, ToolEntry]] = []
    for t, haystack in zip(candidates, documents):
        if not haystack:
            continue
        term_freq = Counter(haystack)
        score = 0.0
        for term, qf in query_terms.items():
            tf = term_freq.get(term, 0)
            if tf == 0:
                continue
            idf = math.log(1 + (len(documents) - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denom = tf + 1.2 * (1 - 0.75 + 0.75 * (len(haystack) / avg_len))
            score += qf * idf * (tf * (1.2 + 1)) / denom
        if score <= 0:
            continue
        scored.append((score, t))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:limit]]
