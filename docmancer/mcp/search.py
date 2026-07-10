"""Tool Search corpus + ranking (spec 2.7 / D10).

Keep this dependency-light so `doc-atlas mcp packs-serve` works in a minimal
install. The default backend is lexical BM25 over enriched operation metadata;
the API is hybrid-ready so semantic hits can be fused later without replacing
lexical matching.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from docmancer.mcp import search_semantic
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
    search_text: str
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class SearchHit:
    entry: ToolEntry
    score: float
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    rank_reason: list[str] = field(default_factory=list)


def build_corpus(packages: list[InstalledPackage]) -> list[ToolEntry]:
    out: list[ToolEntry] = []
    for pkg in packages:
        try:
            tools = pkg.tools()
        except FileNotFoundError:
            continue
        operations = _operations_by_id(pkg)
        for raw in tools:
            op_id = raw.get("operation_id") or raw.get("id") or raw.get("name")
            if not op_id:
                continue
            operation = operations.get(str(op_id), {})
            merged = {**operation, **raw}
            input_schema = merged.get("inputSchema", {})
            aliases = _string_list(merged.get("aliases"))
            tags = _string_list(merged.get("tags"))
            description = merged.get("description") or merged.get("summary") or ""
            out.append(
                ToolEntry(
                    name=build_tool_name(pkg.package, pkg.version, op_id),
                    package=pkg.package,
                    version=pkg.version,
                    operation_id=str(op_id),
                    description=description,
                    safety=merged.get("safety", {}),
                    input_schema=input_schema,
                    search_text=_operation_search_text(merged),
                    aliases=aliases,
                    tags=tags,
                )
            )
    return out


def _operations_by_id(pkg: InstalledPackage) -> dict[str, dict[str, Any]]:
    try:
        contract = pkg.contract()
    except FileNotFoundError:
        return {}
    return {
        str(operation.get("id") or operation.get("operation_id") or operation.get("name")): operation
        for operation in contract.get("operations", []) or []
        if operation.get("id") or operation.get("operation_id") or operation.get("name")
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _schema_terms(schema: dict[str, Any]) -> list[str]:
    terms: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"title", "description"} and isinstance(value, str):
                    terms.append(value)
                elif key in {"properties", "$defs", "definitions"} and isinstance(value, dict):
                    terms.extend(str(name) for name in value)
                    walk(value)
                elif key == "enum" and isinstance(value, list):
                    terms.extend(str(item) for item in value if item is not None)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return terms


def _operation_search_text(raw: dict[str, Any]) -> str:
    bits: list[str] = []
    for key in ("id", "operation_id", "name", "summary", "description"):
        value = raw.get(key)
        if isinstance(value, str):
            bits.append(value)
    for key in ("aliases", "intents", "tags"):
        bits.extend(_string_list(raw.get(key)))
    for example in raw.get("examples") or []:
        if isinstance(example, dict):
            query = example.get("query")
            if isinstance(query, str):
                bits.append(query)
    bits.extend(_schema_terms(raw.get("inputSchema") or {}))
    return "\n".join(bit for bit in bits if bit)


_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
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


def _normalize_text(text: str) -> str:
    text = text.replace("_", " ").replace("-", " ").replace("/", " ")
    return _CAMEL_RE.sub(" ", text)


def _tokens(text: str, *, expand: bool = False) -> list[str]:
    tokens = [t.lower() for t in _WORD_RE.findall(_normalize_text(text))]
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
) -> list[SearchHit]:
    hits, _metadata = search_with_metadata(corpus, query, package=package, limit=limit)
    return hits


def search_with_metadata(
    corpus: list[ToolEntry],
    query: str,
    *,
    package: str | None = None,
    limit: int = 5,
    env: dict[str, str] | None = None,
) -> tuple[list[SearchHit], dict[str, Any]]:
    candidates = [t for t in corpus if package is None or t.package == package]
    lexical = _lexical_search(candidates, query, package=package, limit=limit)
    metadata: dict[str, Any] = {"mode": "lexical", "semantic": False, "lowConfidence": low_confidence(lexical)}
    source = env or os.environ
    if source.get("DOCMANCER_MCP_SEARCH", "lexical").lower() != "hybrid" or not query:
        return lexical, metadata
    try:
        provider = search_semantic.embedding_provider_from_env(source)
        semantic = search_semantic.SemanticBackend(provider).search(query, candidates, limit=limit)
    except search_semantic.SemanticUnavailable as exc:
        metadata["warning"] = str(exc)
        return lexical, metadata
    hybrid = _merge_hits(lexical, semantic, limit=limit)
    return hybrid, {"mode": "hybrid", "semantic": True, "lowConfidence": low_confidence(hybrid)}


def _lexical_search(
    candidates: list[ToolEntry],
    query: str,
    *,
    package: str | None = None,
    limit: int = 5,
) -> list[SearchHit]:
    q = _tokens(query, expand=True)
    if not q:
        if package is None:
            return []
        return [SearchHit(entry=entry, score=0.0, lexical_score=0.0, rank_reason=["package-list"]) for entry in candidates[:limit]]
    documents = [_tokens(t.search_text or f"{t.operation_id} {t.description}") for t in candidates]
    if not documents:
        return []
    doc_freq: Counter[str] = Counter()
    for tokens in documents:
        doc_freq.update(set(tokens))
    avg_len = sum(len(tokens) for tokens in documents) / len(documents)
    query_terms = Counter(q)
    scored: list[SearchHit] = []
    for entry, haystack in zip(candidates, documents):
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
        scored.append(SearchHit(entry=entry, score=score, lexical_score=score, rank_reason=["lexical"]))
    scored.sort(key=lambda hit: hit.score, reverse=True)
    return scored[:limit]


def _rrf(rank: int, *, k: int = 60) -> float:
    return 1.0 / (k + rank)


def _merge_hits(lexical: list[SearchHit], semantic: list[SearchHit], *, limit: int) -> list[SearchHit]:
    by_name: dict[str, SearchHit] = {}
    for rank, hit in enumerate(lexical, start=1):
        merged = by_name.setdefault(hit.entry.name, SearchHit(entry=hit.entry, score=0.0, rank_reason=[]))
        merged.score += _rrf(rank)
        merged.lexical_score = hit.lexical_score or hit.score
        if "lexical" not in merged.rank_reason:
            merged.rank_reason.append("lexical")
    for rank, hit in enumerate(semantic, start=1):
        merged = by_name.setdefault(hit.entry.name, SearchHit(entry=hit.entry, score=0.0, rank_reason=[]))
        merged.score += _rrf(rank)
        merged.semantic_score = hit.semantic_score or hit.score
        if "semantic" not in merged.rank_reason:
            merged.rank_reason.append("semantic")
    out = list(by_name.values())
    out.sort(key=lambda hit: hit.score, reverse=True)
    return out[:limit]


def low_confidence(hits: list[SearchHit]) -> bool:
    if not hits:
        return True
    if len(hits) == 1:
        return False
    top = hits[0].score
    second = hits[1].score
    if top <= 0:
        return False
    return top / max(second, 1e-12) < 1.15
