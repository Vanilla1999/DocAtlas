"""Bounded natural-language aliases used only for project-document retrieval.

The strict answer parser remains authoritative for ``docs_answer``. This module
never creates proof obligations and never authorizes an answer or edit. It only
emits a small number of auditable lookup aliases inside the already resolved
project identity, analogous to Context7 querying inside a library ID.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


_MAX_ALIASES = 4
_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_.:/+-]+")
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_PRODUCT_NAME_RE = re.compile(
    r"(?<![\w])(?:docatlas|doc[ -]atlas|docmancer)(?![\w])", re.I,
)


@dataclass(frozen=True, slots=True)
class ProjectRetrievalAlias:
    """One canonical lookup that is never an answer-equivalence claim."""

    intent_id: str
    text: str
    force_context_only: bool
    source_language: str


def _normal(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            token.casefold().replace("ё", "е")
            for token in _TOKEN_RE.findall(value)
        )
    )


def _has(tokens: tuple[str, ...], *stems: str) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in stems)


def _has_phrase(text: str, *phrases: str) -> bool:
    return any(phrase in text for phrase in phrases)


def build_project_retrieval_aliases(
    question: str,
) -> tuple[ProjectRetrievalAlias, ...]:
    """Return bounded English aliases for common EN/RU project questions.

    The mapping is concept-oriented rather than a translation or answer parser.
    It handles broad documentation intents where retrieval is useful but answer
    certification is too strong. Named contracts, policies, rules, and
    invariants remain on the strict parser/exact-term path so an unknown premise
    cannot be collapsed into a nearby broad topic.
    """

    source = str(question or "").strip()[:4_000]
    if not source:
        return ()

    normalized = _normal(source)
    tokens = _tokens(source)
    language = "ru" if _CYRILLIC_RE.search(source) else "en"
    mentions_product = bool(_PRODUCT_NAME_RE.search(source))
    product_prefix = "DocAtlas " if mentions_product else ""
    rows: list[ProjectRetrievalAlias] = []
    seen: set[str] = set()

    def emit(intent_id: str, force_context_only: bool, *queries: str) -> None:
        for query in queries:
            text = " ".join(query.split())[:500]
            key = text.casefold()
            if not text or key in seen or len(rows) >= _MAX_ALIASES:
                continue
            seen.add(key)
            rows.append(ProjectRetrievalAlias(
                intent_id=intent_id,
                text=text,
                force_context_only=force_context_only,
                source_language=language,
            ))

    mentions_docs = _has(tokens, "документ", "док", "docs", "documentation")
    mentions_project = _has(
        tokens,
        "проект", "репозитор", "систем", "продукт",
        "project", "repo", "repository", "system", "product",
    )
    mentions_mcp = _has(tokens, "mcp")
    mentions_command = _has(tokens, "команд", "command", "cli")
    mentions_start = _has(tokens, "запуст", "запуск", "старт", "start", "serve", "run")
    specific_contract_request = _has(
        tokens,
        "политик", "policy", "contract", "контракт", "правил", "rule",
        "инвариант", "invariant", "governance", "retention",
    )

    # Narrow, reviewed facts remain eligible for strict proof and docs_answer.
    if _has(tokens, "маркер", "marker") and _has(tokens, "pytest"):
        emit(
            "pytest_markers",
            False,
            f"{product_prefix}pytest markers offline test suite documentation",
        )
    if mentions_mcp and mentions_command and mentions_start:
        emit(
            "docs_mcp_server_command",
            False,
            f"{product_prefix}command start Docs MCP server docs-serve",
        )
    if (
        _has(tokens, "где", "where", "location")
        and _has(tokens, "конфиг", "настро", "config")
        and (mentions_docs or mentions_project)
    ):
        emit(
            "project_docs_config_location",
            False,
            f"{product_prefix}project documentation configuration catalog path",
        )
    if (
        _has_phrase(normalized, "корень состояния", "state root")
        and _has(tokens, "переменн", "variable", "environment", "env")
    ):
        emit(
            "state_home_variable",
            False,
            "DOCATLAS_HOME state root environment variable",
        )

    if specific_contract_request:
        return tuple(rows)

    # Broad newcomer/workflow questions deliberately return docs_context.
    if _has(tokens, "офлайн", "offline") or _has_phrase(
        normalized, "без интернета", "без сети", "without internet", "no network",
    ):
        emit(
            "offline_usage",
            True,
            f"{product_prefix}offline mode",
            "DOCATLAS_OFFLINE",
            f"{product_prefix}offline test suite",
        )
    if _has(tokens, "установ", "инстал", "install", "setup") or _has_phrase(
        normalized, "как поставить", "how to install",
    ):
        emit(
            "installation_verification",
            True,
            f"{product_prefix}local installation setup verification getting started",
            f"{product_prefix}install quickstart command line help",
        )
    if (
        not any(row.intent_id == "docs_mcp_server_command" for row in rows)
        and (
            (
                _has(tokens, "перв", "нач", "quickstart", "getting", "start")
                and (mentions_command or mentions_product or mentions_project)
            )
            or _has_phrase(
                normalized,
                "с чего начать",
                "после установки",
                "first commands",
                "first steps",
            )
        )
    ):
        emit(
            "getting_started",
            True,
            f"{product_prefix}getting started first commands first steps quickstart",
            f"{product_prefix}command line help setup initialization workflow",
        )
    if (
        (mentions_product or mentions_project)
        and (
            _has_phrase(normalized, "что такое", "для чего", "зачем")
            or re.search(r"\bwhat\s+is\b|\bwhat\s+problem\b", normalized)
            or _has(tokens, "назначен", "purpose", "overview")
        )
    ):
        emit(
            "product_overview",
            True,
            f"{product_prefix}project overview",
            f"{product_prefix}project purpose",
            f"{product_prefix}problem statement",
        )
    if (
        (
            _has(tokens, "контриб", "вклад", "contribut", "разработчик", "developer")
            and _has(tokens, "репозитор", "читать", "read", "start", "project", "нач")
        )
        or (
            _has(tokens, "карт", "map", "модул", "module", "код", "codebase")
            and _has(tokens, "где", "where", "читать", "read", "нач", "start")
        )
    ):
        emit(
            "contributor_start",
            True,
            f"{product_prefix}new contributor repository reading order contributing project map",
        )
    if mentions_mcp and _has(
        tokens, "работ", "устро", "процесс", "поток", "workflow", "fit",
    ):
        emit(
            "docs_mcp_workflow",
            True,
            f"{product_prefix}Docs MCP server workflow",
            "get_docs_context prepare_docs docs_status",
            "docs/mcp-docs-server.md",
        )
    if (
        (_has(tokens, "синхрон", "обнов", "refresh", "sync") and (
            mentions_docs or mentions_project
        ))
        or (
            _has(tokens, "редакт", "измен", "edit", "change", "markdown")
            and _has(tokens, "поиск", "search", "документ", "docs", "file")
        )
    ):
        emit(
            "project_docs_sync",
            True,
            f"{product_prefix}sync refresh project documentation after file changes",
        )
    if (
        _has(tokens, "настро", "конфиг", "configure", "configuration")
        and (mentions_docs or mentions_project or mentions_product)
        and not any(row.intent_id == "project_docs_config_location" for row in rows)
    ):
        emit(
            "project_docs_configuration",
            True,
            f"{product_prefix}configure project documentation catalog and index settings",
        )
    if _has(tokens, "очист", "clear", "cleanup") and _has(tokens, "индекс", "index"):
        emit(
            "index_cleanup",
            True,
            f"{product_prefix}inspect safely clear local index preview cleanup plan",
        )
    if _has(
        tokens,
        "ошиб", "проблем", "диагност", "troubleshoot", "fail", "stale",
        "insufficient_evidence",
    ) or _has_phrase(
        normalized,
        "не работает",
        "не находится",
        "ничего не находит",
        "nothing found",
        "что проверить",
        "what should i check",
    ):
        emit(
            "troubleshooting",
            True,
            f"{product_prefix}troubleshooting stale documentation no results diagnostics",
        )
    if (
        _has(tokens, "хран", "storage", "изоляц", "isolat", "баз", "database", "пиш")
        and (
            _has(tokens, "индекс", "index", "проект", "project", "документ", "docs")
            or mentions_product
        )
    ):
        emit(
            "project_storage",
            True,
            f"{product_prefix}project documentation storage index path per-project isolation",
        )
    if _has(tokens, "чанк", "секци", "разбив", "chunk", "section", "split"):
        emit(
            "index_chunking",
            True,
            f"{product_prefix}indexing split documentation sections parent child chunks",
        )
    if _has(tokens, "доказател", "evidence") and _has(
        tokens, "выбор", "кандидат", "select", "candidate",
    ):
        emit(
            "evidence_selection",
            True,
            f"{product_prefix}evidence selection candidates proof assignment ranking",
        )
    if _has(tokens, "тест", "протест", "test", "pytest") and not any(
        row.intent_id == "pytest_markers" for row in rows
    ):
        emit(
            "testing_contribution",
            True,
            "tests before pull request",
            "CONTRIBUTING.md tests",
            "docs/testing.md pytest",
        )
    if _has(tokens, "архитект", "architecture", "устройств", "components"):
        emit(
            "project_architecture",
            True,
            f"{product_prefix}project architecture overview components indexing retrieval storage",
        )

    # Conservative RU fallback for unanticipated wording. At least two
    # independent concepts are required, so one vague noun cannot create a
    # synthetic topic.
    if not rows and language == "ru":
        mapping = (
            (("установ", "инстал"), "installation"),
            (("провер",), "verification"),
            (("команд",), "commands"),
            (("нач", "перв"), "getting started"),
            (("архитект", "устройств"), "architecture"),
            (("хран",), "storage"),
            (("индекс",), "index"),
            (("изоляц",), "project isolation"),
            (("настро", "конфиг"), "configuration"),
            (("офлайн", "интернет", "сеть"), "offline"),
            (("тест", "протест"), "testing"),
            (("ошиб", "проблем", "диагност"), "troubleshooting"),
            (("секци", "чанк", "разбив"), "sections chunks"),
            (("доказател", "кандидат"), "evidence selection"),
            (("обнов", "синхрон"), "sync project docs"),
            (("очист",), "clear index"),
            (("репозитор", "контриб", "вклад"), "repository contributor"),
            (("пользова",), "usage"),
        )
        concepts = [label for stems, label in mapping if _has(tokens, *stems)]
        if len(concepts) >= 2:
            emit(
                "mapped_ru_project_query",
                True,
                " ".join((product_prefix.strip() or "project", *concepts[:5])),
            )

    return tuple(rows)


def project_retrieval_requires_context_only(question: str) -> bool:
    """Return whether retrieval is useful but certification is too strong."""

    return any(
        alias.force_context_only
        for alias in build_project_retrieval_aliases(question)
    )


__all__ = [
    "ProjectRetrievalAlias",
    "build_project_retrieval_aliases",
    "project_retrieval_requires_context_only",
]
