from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectQueryIntent:
    name: str
    broad: bool = False
    wants_release_history: bool = False
    wants_docs_mcp: bool = False
    wants_packs_mcp: bool = False
    wants_architecture: bool = False
    wants_how_to: bool = False
    wants_troubleshooting: bool = False
    wants_code_symbols: bool = False


PACKS_MCP_PHRASES = [
    "mcp pack",
    "mcp packs",
    "action pack",
    "action packs",
    "install pack",
    "install packs",
    "install-pack",
    "install-packs",
    "api action",
    "api actions",
]


def _contains_phrase(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _contains_word(text: str, words: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def classify_project_query_intent(question: str) -> ProjectQueryIntent:
    q_raw = (question or "").lower().replace("_", " ")
    q = q_raw.replace("-", " ")

    def has_any(terms: list[str]) -> bool:
        return any(term in q for term in terms)

    wants_architecture = has_any([
        "architecture", "architectural", "project structure", "structured", "structure", "layout", "components", "design", "overview", "workflow", "convention", "conventions", "runbook", "runbooks", "adr",
        "архитектура", "архитектур", "структура проекта", "структура", "компоненты", "обзор", "конвенции", "соглашения",
    ])
    wants_how_to = has_any(["how do i", "how to", "how does", "usage", "use", "setup", "configure", "config", "install", "quickstart", "getting started"])
    wants_ingestion = has_any(["ingest", "ingestion", "index", "indexing", "indexed", "retrieval", "retrieve", "chunk", "chunking", "embedding", "vector", "fts", "qdrant"])
    wants_release = has_any(["changelog", "release", "released", "changed", "added", "removed", "breaking", "migration", "version history", "what changed", "recently changed"])
    explicit_release = has_any(["changelog", "release", "version history", "what changed", "recently changed"])
    wants_troubleshooting = has_any(["error", "bug", "fail", "failed", "why doesn't", "why does not", "not working", "stale", "missing", "diagnose", "doctor", "fix", "troubleshoot"])
    wants_code_symbols = has_any(["class", "classes", "function", "functions", "method", "methods", "file", "files", "module", "implementation", "implements", "where is implemented", "key files", "responsibilities"])
    wants_docs_mcp = has_any(["docs mcp", "documentation mcp", "mcp docs", "docs serve", "docs serve", "get project context", "get project docs", "get library docs", "resolve library id", "context7"])
    wants_packs_mcp = _contains_phrase(q, PACKS_MCP_PHRASES) or _contains_phrase(q_raw, PACKS_MCP_PHRASES)
    wants_packs_mcp = wants_packs_mcp or ("mcp" in q and _contains_word(q, ["packs"]))
    mentions_mcp = "mcp" in q

    if explicit_release or (wants_release and not wants_how_to and not wants_architecture):
        return ProjectQueryIntent(name="release_history", wants_release_history=True, wants_code_symbols=wants_code_symbols)
    if wants_docs_mcp and not wants_packs_mcp:
        return ProjectQueryIntent(name="docs_mcp", wants_docs_mcp=True, wants_how_to=wants_how_to, wants_code_symbols=wants_code_symbols)
    if wants_packs_mcp and not wants_docs_mcp:
        return ProjectQueryIntent(name="packs_mcp", wants_packs_mcp=True, wants_how_to=wants_how_to, wants_code_symbols=wants_code_symbols)
    if mentions_mcp and not wants_docs_mcp and not wants_packs_mcp:
        return ProjectQueryIntent(name="mcp_disambiguation", broad=True, wants_docs_mcp=True, wants_packs_mcp=True, wants_how_to=wants_how_to, wants_code_symbols=wants_code_symbols)
    if wants_docs_mcp and wants_packs_mcp:
        return ProjectQueryIntent(name="mcp_disambiguation", broad=True, wants_docs_mcp=True, wants_packs_mcp=True, wants_how_to=wants_how_to, wants_code_symbols=wants_code_symbols)
    if wants_ingestion and wants_how_to:
        return ProjectQueryIntent(name="ingestion_how_to", wants_how_to=True, wants_code_symbols=wants_code_symbols)
    if wants_ingestion:
        return ProjectQueryIntent(name="ingestion_internals", wants_architecture=True, wants_code_symbols=wants_code_symbols)
    if wants_architecture:
        return ProjectQueryIntent(name="architecture", broad=True, wants_architecture=True, wants_code_symbols=wants_code_symbols)
    if wants_troubleshooting:
        return ProjectQueryIntent(name="troubleshooting", wants_troubleshooting=True, wants_code_symbols=wants_code_symbols)
    if wants_how_to:
        return ProjectQueryIntent(name="how_to", wants_how_to=True, wants_code_symbols=wants_code_symbols)
    return ProjectQueryIntent(name="general", wants_code_symbols=wants_code_symbols)
