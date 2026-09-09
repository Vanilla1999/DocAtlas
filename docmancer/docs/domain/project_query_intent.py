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

PUBLIC_DOCS_MCP_TOOL_NAMES = (
    "get_docs_context",
    "prepare_docs",
    "docs_status",
)

_DOCS_MCP_PHRASES = (
    "docs mcp",
    "documentation mcp",
    "mcp docs",
    "docs serve",
    "get project context",
    "get project docs",
    "get library docs",
    "resolve library id",
    "context7",
)
_PRODUCT_NAME_RE = re.compile(r"(?<![\w])(?:docatlas|docmancer)(?![\w])", re.I)


def _contains_phrase(text: str, phrases: list[str] | tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _contains_word(text: str, words: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def _normalized_question(question: str) -> tuple[str, str]:
    raw = (question or "").casefold()
    normalized = " ".join(raw.replace("_", " ").replace("-", " ").split())
    return raw, normalized


def is_product_purpose_question(question: str) -> bool:
    """Recognize product-definition/purpose questions without incident wording."""

    raw, normalized = _normalized_question(question)
    mentions_product = bool(_PRODUCT_NAME_RE.search(raw))
    explicit_named_definition = bool(
        re.search(
            r"\bwhat\s+is\s+(?:the\s+)?(?:docatlas|docmancer)\b"
            r"(?=\s*(?:[?,;]|$|\band\b))",
            normalized,
        )
        or re.search(
            r"\b(?:что\s+такое|что\s+это\s+за)\s+(?:docatlas|docmancer)\b"
            r"(?=\s*(?:[?,;]|$|\bи\b))",
            normalized,
        )
    )
    generic_definition = bool(
        re.search(
            r"\bwhat\s+is\s+(?:this|the)\s+(?:project|product|system)"
            r"(?=\s*(?:[?,;]|$|\band\b))",
            normalized,
        )
        or re.search(r"\bчто\s+это\s+за\s+(?:проект|продукт|систем[ау])\b", normalized)
    )
    purpose_relation = bool(
        re.search(r"\bproblems?\b[^?]{0,120}\b(?:solve|solves|solved)\b", normalized)
        or re.search(r"\b(?:purpose|intended\s+for|designed\s+to\s+solve)\b", normalized)
        or ("проблем" in normalized and re.search(r"\bреша(?:ет|ют|ть|ющ)\w*\b", normalized))
        or "назначен" in normalized
    )
    generic_product_subject = bool(
        re.search(r"\b(?:this|the)\s+(?:project|product|system)\b", normalized)
        or re.search(r"\b(?:проект|продукт|систем[ау])\b", normalized)
    )
    return (
        explicit_named_definition
        or generic_definition
        or (mentions_product and purpose_relation)
        or (generic_product_subject and purpose_relation)
    )


def mentions_docs_mcp_surface(question: str) -> bool:
    """Recognize the current public Docs MCP surface and narrow workflow wording."""

    raw, normalized = _normalized_question(question)
    if any(name in raw for name in PUBLIC_DOCS_MCP_TOOL_NAMES):
        return True
    if _contains_phrase(normalized, _DOCS_MCP_PHRASES):
        return True
    public_tool_phrases = tuple(name.replace("_", " ") for name in PUBLIC_DOCS_MCP_TOOL_NAMES)
    if _contains_phrase(normalized, public_tool_phrases):
        return True
    return bool(
        re.search(r"\bmcp\b", normalized)
        and re.search(r"\b(?:project\s+)?documentation\b", normalized)
        and re.search(r"\b(?:sequence|workflow|tool\s+calls?|call\s+sequence|answering)\b", normalized)
    )


def is_concept_definition_or_contrast(question: str) -> bool:
    """Distinguish concept questions from reports of an operational incident."""

    _, normalized = _normalized_question(question)
    return bool(
        re.search(r"\bwhat\s+does\b[^?]{0,180}\bmean\b", normalized)
        or re.search(r"\b(?:what\s+is\s+the\s+)?difference\s+between\b", normalized)
        or re.search(r"\bmeaning\s+of\b", normalized)
        or re.search(r"\bdefine\b", normalized)
        or re.search(r"\bчто\s+означа(?:ет|ют)\b", normalized)
        or re.search(r"\bв\s+ч[её]м\s+разниц[аы]\s+между\b", normalized)
    )


def classify_project_query_intent(question: str) -> ProjectQueryIntent:
    q_raw = (question or "").lower().replace("_", " ")
    q = q_raw.replace("-", " ")

    def has_any(terms: list[str]) -> bool:
        return any(term in q for term in terms)

    product_purpose = is_product_purpose_question(question)
    named_product_purpose = product_purpose and bool(_PRODUCT_NAME_RE.search(question or ""))
    concept_definition = is_concept_definition_or_contrast(question)
    explicit_architecture = has_any([
        "architecture", "architectural", "project structure", "structured", "structure", "layout", "components", "design", "overview", "workflow", "convention", "conventions", "runbook", "runbooks", "adr",
        "архитектура", "архитектур", "структура проекта", "структура", "компоненты", "обзор", "конвенции", "соглашения",
    ])
    wants_architecture = explicit_architecture
    wants_architecture = wants_architecture or (
        not named_product_purpose
        and has_any(["project", "repository", "docatlas", "docmancer", "проект", "систем"])
        and (
            re.search(r"\bwhat\s+problems?\b.+\bsolves?\b", q) is not None
            or (has_any(["проблем"]) and has_any(["решает"]))
        )
    )
    wants_how_to = has_any(["how do i", "how to", "how does", "usage", "use", "setup", "configure", "config", "install", "quickstart", "getting started", "как ", "настро", "установ", "запуст", "пользова", "с чего начать", "первые команд"])
    wants_ingestion = has_any(["ingest", "ingestion", "index", "indexing", "indexed", "retrieval", "retrieve", "chunk", "chunking", "embedding", "vector", "fts", "qdrant", "индекс", "поиск", "чанк", "секци", "эмбед", "вектор", "хран"])
    wants_release = has_any(["changelog", "release", "released", "changed", "added", "removed", "breaking", "migration", "version history", "what changed", "recently changed"])
    explicit_release = has_any(["changelog", "release", "version history", "what changed", "recently changed"])
    wants_troubleshooting = has_any(["error", "bug", "fail", "failed", "why doesn't", "why does not", "not working", "stale", "missing", "diagnose", "doctor", "fix", "troubleshoot", "ошиб", "проблем", "не работает", "не наход", "устар", "диагност"])
    wants_troubleshooting = wants_troubleshooting or _contains_word(q, ["problem", "problems"])
    if concept_definition:
        wants_troubleshooting = False
    # Code-symbol routing must be explicit.  Treating every occurrence of
    # ``file``/``files`` as source-navigation intent makes ordinary
    # documentation questions require implementation evidence and fail closed.
    wants_code_symbols = has_any([
        "class", "classes", "function", "functions", "method", "methods",
        "module", "implementation", "implements", "implemented", "defined",
        "responsibilities",
    ]) or _contains_phrase(q, [
        "source file", "source files", "code file", "code files",
        "implementation file", "implementation files", "key file", "key files",
        "where is implemented", "where is defined", "implemented in", "defined in",
        "file path", "source path",
    ])
    wants_docs_mcp = mentions_docs_mcp_surface(question)
    wants_packs_mcp = _contains_phrase(q, PACKS_MCP_PHRASES) or _contains_phrase(q_raw, PACKS_MCP_PHRASES)
    wants_packs_mcp = wants_packs_mcp or ("mcp" in q and _contains_word(q, ["packs"]))
    mentions_mcp = "mcp" in q

    if named_product_purpose and not explicit_architecture:
        return ProjectQueryIntent(name="product_overview", broad=True)
    if explicit_release:
        return ProjectQueryIntent(name="release_history", wants_release_history=True, wants_code_symbols=wants_code_symbols)
    if wants_docs_mcp and not wants_packs_mcp:
        return ProjectQueryIntent(
            name="docs_mcp",
            wants_docs_mcp=True,
            wants_how_to=wants_how_to,
            wants_troubleshooting=wants_troubleshooting,
            wants_code_symbols=wants_code_symbols,
        )
    if wants_packs_mcp and not wants_docs_mcp:
        return ProjectQueryIntent(name="packs_mcp", wants_packs_mcp=True, wants_how_to=wants_how_to, wants_code_symbols=wants_code_symbols)
    if mentions_mcp and not wants_docs_mcp and not wants_packs_mcp:
        return ProjectQueryIntent(name="mcp_disambiguation", broad=True, wants_docs_mcp=True, wants_packs_mcp=True, wants_how_to=wants_how_to, wants_code_symbols=wants_code_symbols)
    if wants_docs_mcp and wants_packs_mcp:
        return ProjectQueryIntent(name="mcp_disambiguation", broad=True, wants_docs_mcp=True, wants_packs_mcp=True, wants_how_to=wants_how_to, wants_code_symbols=wants_code_symbols)
    if wants_release and not wants_how_to and not wants_architecture:
        return ProjectQueryIntent(name="release_history", wants_release_history=True, wants_code_symbols=wants_code_symbols)
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
