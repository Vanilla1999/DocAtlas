#!/usr/bin/env python3
"""Apply the retrieval-first project-chat patch on the exact PR worktree.

This file is intentionally temporary.  The companion workflow removes it and
itself in the implementation commit after applying the deterministic edits.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def create(path: str, content: str) -> None:
    target = ROOT / path
    if target.exists():
        raise RuntimeError(f"refusing to overwrite new file: {path}")
    write(path, content)


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, found {count}: {old[:120]!r}")
    write(path, content.replace(old, new, 1))


def replace_all_exact(path: str, old: str, new: str, *, expected: int) -> None:
    content = read(path)
    count = content.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} replacements, found {count}: {old!r}")
    write(path, content.replace(old, new))


def replace_in_block(path: str, start_marker: str, end_marker: str, old: str, new: str) -> None:
    content = read(path)
    start = content.index(start_marker)
    end = content.index(end_marker, start)
    block = content[start:end]
    count = block.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: block replacement count={count}: {old[:120]!r}")
    write(path, content[:start] + block.replace(old, new, 1) + content[end:])


PROJECT_RETRIEVAL_INTENT = '''\
"""Bounded natural-language aliases used only for project-document retrieval.

The strict answer parser remains authoritative for ``docs_answer``.  This
module never creates proof obligations and never authorizes an answer or edit.
It only emits a small number of auditable lookup aliases inside the already
resolved project identity, analogous to Context7 querying inside a library ID.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


_MAX_ALIASES = 4
_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_.:/+-]+")
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_EXACT_TERM_RE = re.compile(
    r"`([^`\\n]{2,120})`|\\b([A-Za-z_][A-Za-z0-9_]*(?:(?:::|\\.)[A-Za-z_][A-Za-z0-9_]*)+)\\b"
    r"|\\b([A-Za-z][A-Za-z0-9_]*_[A-Za-z0-9_]+)\\b"
)
_UNSUPPORTED_FANTASY_RE = re.compile(
    r"\\b(?:lunar|quantum|квант\\w*|лунн\\w*)\\b", re.IGNORECASE,
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
    return tuple(dict.fromkeys(token.casefold().replace("ё", "е") for token in _TOKEN_RE.findall(value)))



def _has(tokens: tuple[str, ...], *stems: str) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in stems)



def _has_phrase(text: str, *phrases: str) -> bool:
    return any(phrase in text for phrase in phrases)



def _exact_terms(question: str) -> tuple[str, ...]:
    values: list[str] = []
    for match in _EXACT_TERM_RE.finditer(question):
        value = next((group for group in match.groups() if group), "").strip("`")
        if value and value.casefold() not in {"docatlas", "docmancer"}:
            values.append(value)
    return tuple(dict.fromkeys(values))[:4]



def build_project_retrieval_aliases(question: str) -> tuple[ProjectRetrievalAlias, ...]:
    """Return bounded EN lookup aliases for common EN/RU project-doc questions.

    Matching is token/stem based rather than whole-question ``fullmatch`` so
    ordinary paraphrases remain retrievable.  An unknown or fantastical premise
    produces no alias and therefore retains fail-closed behavior.
    """

    source = str(question or "").strip()[:4_000]
    if not source or _UNSUPPORTED_FANTASY_RE.search(source):
        return ()
    normalized = _normal(source)
    tokens = _tokens(source)
    language = "ru" if _CYRILLIC_RE.search(source) else "en"
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

    mentions_docatlas = _has_phrase(normalized, "docatlas", "doc atlas", "docmancer")
    mentions_docs = _has(tokens, "документ", "док", "docs", "documentation")
    mentions_project = _has(tokens, "проект", "project", "repo", "репозитор")
    mentions_mcp = _has(tokens, "mcp")
    mentions_command = _has(tokens, "команд", "command", "cli")
    mentions_start = _has(tokens, "запуст", "старт", "start", "serve", "run")

    # Narrow facts remain eligible for strict proof and possible docs_answer.
    if _has(tokens, "маркер", "marker") and _has(tokens, "pytest"):
        emit("pytest_markers", False, "DocAtlas pytest markers offline test suite docs/testing.md")
    if mentions_mcp and mentions_command and mentions_start:
        emit(
            "docs_mcp_server_command",
            False,
            "DocAtlas command start Docs MCP server doc-atlas mcp docs-serve",
        )
    if (
        _has(tokens, "где", "where", "location")
        and _has(tokens, "конфиг", "настро", "config")
        and (mentions_docs or mentions_project)
    ):
        emit(
            "project_docs_config_location",
            False,
            "DocAtlas project documentation configuration docatlas.project-docs.yaml",
        )

    # Broad newcomer/workflow questions deliberately return docs_context.
    if _has(tokens, "офлайн", "offline") or _has_phrase(
        normalized, "без интернета", "без сети", "without internet", "no network",
    ):
        emit(
            "offline_usage",
            True,
            "DocAtlas provider-free offline mode local retrieval no network",
            "DOCATLAS_OFFLINE offline test suite docs/testing.md",
        )
    if _has(tokens, "установ", "инстал", "install", "setup") or _has_phrase(
        normalized, "как поставить", "how to install",
    ):
        emit(
            "installation_verification",
            True,
            "DocAtlas local installation verification pipx install doc-atlas --help",
            "DocAtlas getting started setup install targets",
        )
    if (
        _has(tokens, "перв", "нач", "quickstart", "getting", "start")
        and (mentions_command or mentions_docatlas or mentions_project)
    ) or _has_phrase(normalized, "с чего начать", "после установки", "first commands"):
        emit(
            "getting_started",
            True,
            "DocAtlas getting started first commands quickstart README",
            "doc-atlas setup init mcp docs-serve command workflow",
        )
    if _has_phrase(normalized, "что такое", "для чего", "зачем", "what is") or _has(
        tokens, "назначен", "purpose", "overview",
    ):
        emit(
            "product_overview",
            True,
            "DocAtlas overview purpose problem local documentation runtime coding agents",
        )
    if (
        _has(tokens, "контриб", "вклад", "contribut", "разработчик")
        and _has(tokens, "репозитор", "читать", "read", "start", "project")
    ):
        emit(
            "contributor_start",
            True,
            "DocAtlas new contributor repository reading order README CONTRIBUTING PROJECT_MAP INDEX",
        )
    if mentions_mcp and _has(tokens, "работ", "устро", "процесс", "поток", "workflow", "fit"):
        emit(
            "docs_mcp_workflow",
            True,
            "DocAtlas Docs MCP workflow get_docs_context prepare_docs docs_status",
        )
    if _has(tokens, "синхрон", "обнов", "refresh", "sync") and (mentions_docs or mentions_project):
        emit(
            "project_docs_sync",
            True,
            "sync_project_docs refresh project documentation after file changes",
        )
    if _has(tokens, "настро", "конфиг", "configure", "configuration") and (
        mentions_docs or mentions_project or mentions_docatlas
    ):
        emit(
            "project_docs_configuration",
            True,
            "DocAtlas configure project documentation docatlas.project-docs.yaml docatlas.yaml",
        )
    if _has(tokens, "очист", "clear", "cleanup") and _has(tokens, "индекс", "index"):
        emit(
            "index_cleanup",
            True,
            "DocAtlas inspect safely clear local index clear-index preview plan digest",
        )
    if _has(tokens, "ошиб", "проблем", "диагност", "troubleshoot", "fail", "stale") or _has_phrase(
        normalized, "не работает", "не находится", "ничего не находит", "nothing found",
    ):
        emit(
            "troubleshooting",
            True,
            "DocAtlas troubleshooting project documentation stale no results diagnostics",
        )
    if _has(tokens, "хран", "storage", "изоляц", "isolat") and (
        _has(tokens, "индекс", "index", "проект", "project", "документ", "docs")
        or mentions_docatlas
    ):
        emit(
            "project_storage",
            True,
            "DocAtlas project documentation storage index path per-project isolation",
        )
    if _has(tokens, "чанк", "секци", "разбив", "chunk", "section", "split"):
        emit(
            "index_chunking",
            True,
            "DocAtlas indexing split documentation semantic sections parent child chunks",
        )
    if _has(tokens, "доказател", "evidence") and _has(tokens, "выбор", "кандидат", "select", "candidate"):
        emit(
            "evidence_selection",
            True,
            "DocAtlas evidence selection candidate normalization proof assignment ranking",
        )
    if _has(tokens, "тест", "test", "pytest") and not any(row.intent_id == "pytest_markers" for row in rows):
        emit(
            "testing_contribution",
            True,
            "DocAtlas tests before pull request provider-free pytest contribution workflow",
        )
    if _has(tokens, "архитект", "architecture", "устройств", "components"):
        emit(
            "project_architecture",
            True,
            "DocAtlas architecture overview indexing retrieval project storage context packs",
        )

    # Bounded RU fallback for unanticipated wording.  It maps concepts, not
    # grammar, and requires at least two independent concepts (or one concept
    # plus an exact technical identity) before emitting a lookup.
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
            (("тест",), "testing"),
            (("ошиб", "проблем", "диагност"), "troubleshooting"),
            (("секци", "чанк", "разбив"), "sections chunks"),
            (("доказател", "кандидат"), "evidence selection"),
            (("обнов", "синхрон"), "sync project docs"),
            (("очист",), "clear index"),
            (("маркер",), "pytest markers"),
            (("репозитор", "контриб", "вклад"), "repository contributor"),
            (("пользова",), "usage"),
        )
        concepts = [label for stems, label in mapping if _has(tokens, *stems)]
        exact = _exact_terms(source)
        if len(concepts) >= 2 or (concepts and exact):
            emit(
                "mapped_ru_project_query",
                True,
                " ".join(("DocAtlas", *concepts[:5], *exact[:3])),
            )

    return tuple(rows)


__all__ = ["ProjectRetrievalAlias", "build_project_retrieval_aliases"]
'''

STATE_CUTOVER = '''\
"""Read-only diagnostics for the removed pre-DocAtlas project-state namespace."""
from __future__ import annotations

from pathlib import Path


def legacy_project_state_candidates(project_path: str | Path) -> tuple[Path, ...]:
    """Return existing legacy derived DBs without reading or migrating them."""

    root = Path(project_path).expanduser().resolve() / ".docmancer"
    if not root.is_dir() or root.is_symlink():
        return ()
    candidates = tuple(sorted(
        path for path in root.glob("*.db")
        if path.is_file() and not path.is_symlink()
    ))
    nested = root / "docs-indexes"
    if nested.is_dir() and not nested.is_symlink():
        candidates += tuple(sorted(
            path for path in nested.glob("*.db")
            if path.is_file() and not path.is_symlink()
        ))
    return tuple(dict.fromkeys(candidates))[:20]


__all__ = ["legacy_project_state_candidates"]
'''

ADR = '''\
# ADR 0002: Retrieve project documentation before certifying an answer

- Status: accepted
- Date: 2026-08-30

## Context

Project chat used the same strict semantic contract both to retrieve documents
and to certify a complete answer.  That is safe for narrow facts, but it makes a
normal Context7-style question fail before relevant project documentation can
reach the model.  The failure is especially visible when a Russian question is
asked against English repository documentation.

The repository identity already supplies the hard corpus boundary that a
Context7 library ID supplies: project path, repository identity, scope,
lifecycle, freshness, and source class are verified before projection.

## Decision

Project documentation delivery has two independent stages.

1. **Bounded retrieval** accepts a natural-language question and may add a small
   number of deterministic retrieval-only aliases.  These aliases can improve
   recall but never create a fact, proof obligation, answer claim, or edit
   permission.
2. **Answer certification** may upgrade the retrieved material to
   `docs_answer` only when the strict answer contract is completely parsed and
   every mandatory obligation has a local source witness.

When safe current project documentation is relevant but answer certification is
not available, the result is `docs_context`, not `insufficient_evidence`.
`docs_context` is bounded, source-attributed, non-complete, and never authorizes
an edit.  Explicit mutation requests continue to use strict `patch_context`.

Semantic/dense retrieval is also a context-only signal.  It may qualify a chunk
for `docs_context` only through an explicit calibrated `semantic_match` trace;
it cannot by itself satisfy an answer proof.

## Invariants

- Cross-project, stale, historical (unless requested), risky, or unowned sources
  never become visible context.
- Parser uncertainty prevents `docs_answer`, not project-scoped retrieval.
- Retrieval aliases are auditable and remain tied to the original query plan.
- A broad workflow, overview, architecture, installation, or troubleshooting
  request returns `docs_context` even when a narrower sentence inside a source
  could be proved.
- `insufficient_evidence` remains the result for an operational block, an
  authoritative conflict, or no qualified relevant project documentation.
- No legacy public MCP tools, implicit legacy-state discovery, or unbounded
  payload is restored.

## Consequences

Weak models receive useful documentation more often and need fewer recovery
turns.  Narrow exact facts retain stronger proof semantics.  The system gains a
small retrieval-language adapter, but that adapter is intentionally unable to
certify answers and is covered by negative and wrong-intent tests.
'''

EVAL_README = '''\
# Context7-style project-chat protocol v1

This protocol freezes natural newcomer questions that must traverse the public
project-documentation path.  The primary success is useful bounded
`docs_context`; only narrow closed facts may become `docs_answer`.

The corpus contains Russian questions, English semantic pairs, and a nonexistent
premise.  Contract tests verify that broad queries receive retrieval-only
aliases, generic CLI commands are not rewritten as the Docs MCP tool inventory,
and an unknown premise receives no canonical alias.

Run the provider-free contract gate with:

```bash
python -m eval.project_chat_context7_v1_protocol
```

Run the heavier self-hosted public-path gate explicitly with:

```bash
python -m eval.project_chat_context7_v1_protocol --live
```
'''

EVAL_CASES = {
    "schema_version": "project-chat-context7-corpus-v1",
    "cases": [
        {"id": "ru-install", "question": "Как установить DocAtlas локально и проверить, что он работает?", "pair": "How do I install and verify DocAtlas locally?", "intent": "installation_verification", "expected_kind": "docs_context", "sources": ["README.md", "wiki/Install-Targets.md"]},
        {"id": "ru-overview", "question": "Что такое DocAtlas и зачем он нужен разработчику?", "pair": "What is DocAtlas and what problem does it solve?", "intent": "product_overview", "expected_kind": "docs_context", "sources": ["README.md", "docs/DOCMANCER_PRODUCT_BRIEF.md"]},
        {"id": "ru-first-commands", "question": "Какие первые команды выполнить после установки?", "pair": "Which first commands should I run after installation?", "intent": "getting_started", "expected_kind": "docs_context", "sources": ["README.md", "wiki/Commands.md"]},
        {"id": "ru-contributor", "question": "С чего новому разработчику начать читать репозиторий?", "pair": "Where should a new contributor start reading the repository?", "intent": "contributor_start", "expected_kind": "docs_context", "sources": ["CONTRIBUTING.md", "docs/PROJECT_MAP.md"]},
        {"id": "ru-mcp-flow", "question": "Как устроен полный процесс работы Docs MCP?", "pair": "How does the Docs MCP workflow fit together?", "intent": "docs_mcp_workflow", "expected_kind": "docs_context", "sources": ["docs/mcp-docs-server.md", "docs/project-docs-mcp-workflow.md"]},
        {"id": "ru-sync", "question": "Как обновить проектную документацию после изменения файлов?", "pair": "How should I refresh project documentation after editing files?", "intent": "project_docs_sync", "expected_kind": "docs_context", "sources": ["docs/project-docs-mcp-workflow.md"]},
        {"id": "ru-config", "question": "Как настроить проектную документацию для репозитория?", "pair": "How do I configure project documentation for a repository?", "intent": "project_docs_configuration", "expected_kind": "docs_context", "sources": ["wiki/Configuration.md", "docs/project-docs-mcp-workflow.md"]},
        {"id": "ru-clean", "question": "Как безопасно проверить и очистить локальный индекс?", "pair": "How can I inspect and safely clear a local index?", "intent": "index_cleanup", "expected_kind": "docs_context", "sources": ["docs/index-cleanup.md", "wiki/Commands.md"]},
        {"id": "ru-troubleshoot", "question": "Что проверить, если проектная документация устарела или ничего не находится?", "pair": "What should I check when project documentation looks stale?", "intent": "troubleshooting", "expected_kind": "docs_context", "sources": ["wiki/Troubleshooting.md", "docs/project-docs-mcp-workflow.md"]},
        {"id": "ru-storage", "question": "Где хранится индекс и как он изолирован для каждого проекта?", "pair": "Where is the index stored and how is it isolated per project?", "intent": "project_storage", "expected_kind": "docs_context", "sources": ["wiki/Architecture.md", "docs/modules/storage-mutation-coordination.md"]},
        {"id": "ru-chunks", "question": "Как индексирование разбивает документацию на секции и чанки?", "pair": "How does indexing split documentation into sections and chunks?", "intent": "index_chunking", "expected_kind": "docs_context", "sources": ["wiki/Architecture.md"]},
        {"id": "ru-selection", "question": "Как выбор доказательств определяет подходящие кандидаты?", "pair": "How does evidence selection choose candidates?", "intent": "evidence_selection", "expected_kind": "docs_context", "sources": ["docs/modules/evidence-selection.md"]},
        {"id": "ru-tests", "question": "Что нужно протестировать перед открытием pull request?", "pair": "What should I test before opening a pull request?", "intent": "testing_contribution", "expected_kind": "docs_context", "sources": ["CONTRIBUTING.md", "docs/testing.md"]},
        {"id": "ru-offline", "question": "Как пользоваться DocAtlas без интернета и запустить офлайн-тесты?", "pair": "How do I use DocAtlas offline and run the provider-free suite?", "intent": "offline_usage", "expected_kind": "docs_context", "sources": ["docs/testing.md", "wiki/Configuration.md"]},
        {"id": "ru-server-command", "question": "Какая команда запускает Docs MCP сервер?", "pair": "Which command starts the Docs MCP server?", "intent": "docs_mcp_server_command", "expected_kind": "docs_answer", "sources": ["docs/mcp-docs-server.md", "wiki/Commands.md"]},
        {"id": "negative-quantum", "question": "Какую лунную квантовую политику хранения использует DocAtlas?", "pair": "What lunar quantum retention policy does DocAtlas use?", "intent": None, "expected_kind": "insufficient_evidence", "sources": []},
    ],
}

EVAL_PROTOCOL = '''\
#!/usr/bin/env python3
"""Provider-free and optional live gate for Context7-style project chat."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval/project_chat_context7_v1/cases.json"


def load_cases() -> tuple[dict[str, Any], ...]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project-chat-context7-corpus-v1":
        raise ValueError("unsupported project-chat Context7 corpus schema")
    rows = tuple(dict(item) for item in payload.get("cases") or ())
    ids = [str(item.get("id") or "") for item in rows]
    if len(rows) != 16 or len(set(ids)) != 16 or not all(ids):
        raise ValueError("Context7-style project-chat corpus requires 16 unique cases")
    return rows


def run_contract() -> dict[str, Any]:
    results = []
    for case in load_cases():
        aliases = build_project_retrieval_aliases(str(case["question"]))
        plan = build_documentation_query_plan(str(case["question"]), requirements=())
        contract = build_project_answer_contract(str(case["question"]))
        intent_ids = {alias.intent_id for alias in aliases}
        expected = case.get("intent")
        public_tools = any(
            obligation.attribute == "public_tools"
            for obligation in contract.proof_obligations
        )
        passed = (
            (expected in intent_ids if expected else not aliases)
            and any(item.origin == "canonical_intent" for item in plan.queries) == bool(expected)
            and not (case["id"] == "ru-first-commands" and public_tools)
        )
        results.append({
            "id": case["id"],
            "intent_ids": sorted(intent_ids),
            "public_tools": public_tools,
            "passed": passed,
        })
    report = {
        "schema_version": "project-chat-context7-contract-result-v1",
        "case_count": len(results),
        "passed_count": sum(row["passed"] for row in results),
        "results": results,
    }
    report["verdict"] = "PASS" if report["passed_count"] == report["case_count"] else "FAIL"
    return report


def run_live() -> dict[str, Any]:
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    cases = tuple(
        LiveCase(
            question=str(item["question"]),
            relevant_paths=tuple(str(value) for value in item.get("sources") or ()),
            expected_kind=str(item["expected_kind"]),
            required_facts_by_path=(),
            forbidden_source_prefixes=("eval/", ".hermes/plans/", "roadmap/"),
            forbidden_answer_fragments=(
                ("get_docs_context", "prepare_docs", "docs_status")
                if item["id"] == "ru-first-commands" else ()
            ),
        )
        for item in load_cases()
    )
    return run(cases=cases, negative_cases=())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    report = run_live() if args.live else run_contract()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

TESTS = '''\
from __future__ import annotations

from pathlib import Path

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._project_docs_service_part03 import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import (
    build_project_answer_contract,
    can_authorize_docs_answer,
)
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
from docmancer.docs.domain.state_cutover import legacy_project_state_candidates
from docmancer.docs.application.recovery import _suggested_questions


@pytest.mark.parametrize(
    ("question", "intent_id"),
    [
        ("Как установить DocAtlas и проверить запуск?", "installation_verification"),
        ("Какие первые команды выполнить после установки?", "getting_started"),
        ("Где хранится индекс и как он изолирован по проектам?", "project_storage"),
        ("Как пользоваться без интернета?", "offline_usage"),
        ("Что делать, когда ничего не находится?", "troubleshooting"),
        ("Архитектура?", "project_architecture"),
    ],
)
def test_russian_newcomer_queries_get_retrieval_only_aliases(question: str, intent_id: str):
    aliases = build_project_retrieval_aliases(question)

    assert intent_id in {alias.intent_id for alias in aliases}
    assert all(alias.force_context_only for alias in aliases)
    assert all(alias.text for alias in aliases)


def test_nonexistent_fantasy_premise_gets_no_alias():
    assert build_project_retrieval_aliases(
        "Какую лунную квантовую политику хранения использует DocAtlas?"
    ) == ()


def test_broad_intent_suppresses_mandatory_proof_queries_for_retrieval():
    plan = build_documentation_query_plan(
        "Какие первые команды выполнить после установки?",
        requirements=(),
    )

    canonical = [item for item in plan.queries if item.origin == "canonical_intent"]
    original = next(item for item in plan.queries if item.origin == "original")
    assert canonical
    assert original.coverage_required is False
    assert any(item.facet_id == "intent-context:getting_started" for item in canonical)


def test_generic_first_commands_are_not_docs_mcp_public_tool_inventory():
    contract = build_project_answer_contract(
        "Какие первые команды выполнить после установки?"
    )

    assert not any(
        obligation.attribute == "public_tools"
        for obligation in contract.proof_obligations
    )


def test_explicit_docs_mcp_tool_inventory_remains_supported():
    contract = build_project_answer_contract(
        "Какие публичные инструменты есть у Docs MCP?"
    )

    assert any(
        obligation.attribute == "public_tools"
        for obligation in contract.proof_obligations
    )


def test_generic_architecture_cannot_be_certified_as_complete_answer():
    contract = build_project_answer_contract("Архитектура?")

    assert can_authorize_docs_answer(contract) is False


def test_explicit_semantic_match_can_qualify_context_query_without_claiming_proof():
    chunk = RetrievedChunk(
        source="project::architecture",
        chunk_index=0,
        text="Project documentation storage is isolated per repository.",
        score=0.81,
        metadata={
            "semantic_match": {
                "qualified_for_context": True,
                "channel": "dense",
                "score": 0.81,
                "threshold": 0.75,
            },
        },
    )

    tagged = _tag_retrieval_query([chunk], "query-intent-1", "project storage")
    match = tagged[0].metadata["retrieval_query_matches"]["query-intent-1"]
    assert match["qualified"] is True
    assert match["semantic_match"]["qualified_for_context"] is True


class _EmptyRequirements:
    retrieval_hints = ()
    query_requirement_spans = ()

    def __iter__(self):
        return iter(())


def test_russian_parser_failure_does_not_generate_mixed_language_rephrase():
    assert _suggested_questions(
        "Как пользоваться DocAtlas?",
        _EmptyRequirements(),
        evidence_path=None,
    ) == []


def test_legacy_state_detection_is_read_only_and_bounded(tmp_path: Path):
    legacy = tmp_path / ".docmancer"
    legacy.mkdir()
    db = legacy / "docmancer.db"
    db.write_bytes(b"legacy")

    assert legacy_project_state_candidates(tmp_path) == (db,)
    assert db.read_bytes() == b"legacy"
'''

ANALYSIS_DOC = '''\
# Context7-style project-chat regression evidence

The regression was caused by two changes becoming visible at the same time.

1. The current `.docatlas` namespace no longer reads the former `.docmancer`
   project database, so a first process after the cutover legitimately starts
   with no current index and must run `sync_project_docs`.
2. The removal of compatibility delivery made the bounded model projection the
   only public path.  The strict answer parser had always covered only audited
   language surfaces; without the former context/navigation path, parser
   uncertainty began suppressing otherwise useful retrieval.

The fix deliberately does not restore the old public tools or unbounded output.
It adds deterministic retrieval-only aliases, lets qualified aliases satisfy a
bounded `docs_context` projection, and keeps strict local proof as the only path
to `docs_answer`.

## Acceptance evidence

- Generic first CLI commands must not become the three Docs MCP tools.
- Generic architecture must be context-only.
- Russian recovery must not produce mixed-language generated questions.
- A nonexistent fantastical premise must receive no canonical retrieval alias.
- Legacy state may be diagnosed but is never read or migrated implicitly.
- Semantic retrieval may qualify context only through an explicit calibrated
  trace and never proves an answer by itself.
'''


def main() -> None:
    create("docmancer/docs/domain/project_retrieval_intent.py", PROJECT_RETRIEVAL_INTENT)
    create("docmancer/docs/domain/state_cutover.py", STATE_CUTOVER)
    create("docs/adr/0002-context-retrieval-vs-answer-proof.md", ADR)
    create("docs/analysis/context7-style-project-chat-regression.md", ANALYSIS_DOC)
    create("eval/project_chat_context7_v1/README.md", EVAL_README)
    create("eval/project_chat_context7_v1/cases.json", json.dumps(EVAL_CASES, ensure_ascii=False, indent=2) + "\n")
    create("eval/project_chat_context7_v1_protocol.py", EVAL_PROTOCOL)
    create("tests/docs/test_context7_style_project_chat.py", TESTS)

    # Retrieval aliases become part of the query plan but remain incapable of
    # creating proof requirements.
    replace_once(
        "docmancer/docs/domain/documentation_query_plan.py",
        "from docmancer.docs.domain.question_frame_core import split_question_clauses\n",
        "from docmancer.docs.domain.question_frame_core import split_question_clauses\n"
        "from docmancer.docs.domain.project_retrieval_intent import (\n"
        "    build_project_retrieval_aliases,\n"
        ")\n",
    )
    replace_once(
        "docmancer/docs/domain/documentation_query_plan.py",
        """    mandatory = tuple(\n        item for item in requirements or ()\n        if getattr(item, \"mandatory\", False)\n        and getattr(item, \"kind\", \"\") == \"proof_obligation\"\n    )[:4]\n    queries = [DocumentationLookup(\n        \"query-original\", question.strip(), \"original\", not bool(mandatory),\n    )]\n""",
        """    retrieval_aliases = build_project_retrieval_aliases(question)\n    force_context_only = any(alias.force_context_only for alias in retrieval_aliases)\n    mandatory = (() if force_context_only else tuple(\n        item for item in requirements or ()\n        if getattr(item, \"mandatory\", False)\n        and getattr(item, \"kind\", \"\") == \"proof_obligation\"\n    )[:4])\n    queries = [DocumentationLookup(\n        \"query-original\", question.strip(), \"original\",\n        not bool(mandatory) and not force_context_only,\n    )]\n""",
    )
    replace_once(
        "docmancer/docs/domain/documentation_query_plan.py",
        """    queries.extend(\n        DocumentationLookup(\n            f\"query-lookup-{index}\", text.strip(), \"host_lookup\", False,\n        )\n""",
        """    seen_aliases = {query.text.casefold() for query in queries}\n    for index, alias in enumerate(retrieval_aliases, start=1):\n        if alias.text.casefold() in seen_aliases:\n            continue\n        queries.append(DocumentationLookup(\n            f\"query-intent-{index}\", alias.text, \"canonical_intent\", False,\n            (\n                f\"intent-context:{alias.intent_id}\"\n                if alias.force_context_only else f\"intent:{alias.intent_id}\"\n            ),\n        ))\n        seen_aliases.add(alias.text.casefold())\n    queries.extend(\n        DocumentationLookup(\n            f\"query-lookup-{index}\", text.strip(), \"host_lookup\", False,\n        )\n""",
    )

    # Canonical intent queries are executed by the production project-doc lane.
    replace_all_exact(
        "docmancer/docs/application/_project_docs_service_part03.py",
        '{"mandatory_facet", "host_lookup", "auto_clause", "concept_alias", "retrieval_hint"}',
        '{"mandatory_facet", "host_lookup", "auto_clause", "canonical_intent", "concept_alias", "retrieval_hint"}',
        expected=2,
    )
    replace_once(
        "docmancer/docs/application/_project_docs_service_part03.py",
        "from docmancer.core.models import RetrievedChunk\n",
        "from docmancer.core.models import RetrievedChunk\n"
        "from docmancer.docs.domain.state_cutover import legacy_project_state_candidates\n",
    )
    replace_once(
        "docmancer/docs/application/_project_docs_service_part03.py",
        """        trace = dict(metadata.get(\"lexical_match\") or {})\n        # Retrieval is candidate generation. Only a lexical relevance trace or\n        # an explicitly resolved exact path may qualify model-visible context.\n        trace.setdefault(\"qualified\", bool(metadata.get(\"exact_path_match\")))\n        trace.setdefault(\"lexical_score\", float(chunk.score))\n""",
        """        trace = dict(metadata.get(\"lexical_match\") or {})\n        semantic = (\n            dict(metadata.get(\"semantic_match\") or {})\n            if isinstance(metadata.get(\"semantic_match\"), dict) else {}\n        )\n        # Candidate generation and answer proof remain separate.  A calibrated\n        # semantic trace may qualify a chunk for docs_context, while only local\n        # answer-unit proof can authorize docs_answer.\n        semantic_qualified = bool(\n            semantic.get(\"qualified_for_context\") is True\n            or semantic.get(\"qualified\") is True\n        )\n        trace[\"qualified\"] = bool(\n            trace.get(\"qualified\") is True\n            or metadata.get(\"exact_path_match\")\n            or semantic_qualified\n        )\n        trace.setdefault(\"lexical_score\", float(chunk.score))\n        if semantic:\n            trace[\"semantic_match\"] = {\n                key: semantic[key]\n                for key in (\n                    \"qualified_for_context\", \"qualified\", \"channel\",\n                    \"score\", \"threshold\", \"model\",\n                )\n                if semantic.get(key) is not None\n            }\n""",
    )
    replace_once(
        "docmancer/docs/application/_project_docs_service_part03.py",
        """        if not indexed_sources_all:\n            if preflight_inspect:\n""",
        """        legacy_state_candidates = legacy_project_state_candidates(root)\n        if not indexed_sources_all:\n            if preflight_inspect:\n""",
    )
    replace_in_block(
        "docmancer/docs/application/_project_docs_service_part03.py",
        "        if not indexed_sources_all:\n",
        "        chunks = self.query_project_docs(\n",
        """                warnings=metadata.warnings,\n                candidate_sources=candidate_sources,\n""",
        """                warnings=[\n                    *metadata.warnings,\n                    *([\n                        \"Legacy .docmancer project index detected; it is not read or migrated. Run sync_project_docs to build current .docatlas state.\"\n                    ] if legacy_state_candidates else []),\n                ],\n                diagnostics={\n                    \"legacy_project_state_detected\": bool(legacy_state_candidates),\n                    \"legacy_state_candidate_count\": len(legacy_state_candidates),\n                },\n                candidate_sources=candidate_sources,\n""",
    )

    # Context projection may use canonical aliases, but only as bounded context.
    replace_once(
        "docmancer/docs/application/docs_context_projection.py",
        """    broad_context_only = bool(context_only_relations & {\n        \"behavior\", \"chunking\", \"contract_fact\", \"contrast\", \"implementation\",\n        \"location\", \"purpose\", \"procedure\", \"selection_policy\", \"usage\", \"workflow\",\n    }) or bool(query_plan.get(\"unresolved_parts\"))\n""",
        """    intent_context_only = any(\n        isinstance(item, dict)\n        and item.get(\"origin\") == \"canonical_intent\"\n        and str(item.get(\"facet_id\") or \"\").startswith(\"intent-context:\")\n        for item in query_plan.get(\"queries\") or ()\n    )\n    broad_context_only = bool(context_only_relations & {\n        \"architecture\", \"behavior\", \"chunking\", \"contract_fact\", \"contrast\",\n        \"implementation\", \"location\", \"purpose\", \"procedure\",\n        \"selection_policy\", \"usage\", \"workflow\",\n    }) or bool(query_plan.get(\"unresolved_parts\")) or intent_context_only\n""",
    )
    replace_once(
        "docmancer/docs/application/docs_context_projection.py",
        """    host_query_ids = _query_ids_for_origins(query_plan, {\"host_lookup\"})\n    relation_claim_query_ids = {\n""",
        """    host_query_ids = _query_ids_for_origins(query_plan, {\"host_lookup\"})\n    canonical_intent_query_ids = _query_ids_for_origins(\n        query_plan, {\"canonical_intent\"},\n    )\n    relation_claim_query_ids = {\n""",
    )
    replace_once(
        "docmancer/docs/application/docs_context_projection.py",
        """        host_ids = qualified_ids & host_query_ids\n        relation_claim_ids = qualified_ids & relation_claim_query_ids\n        if not required_ids and not original_hit and not host_ids:\n            continue\n        if (\n            broad_context_only\n            and not original_hit\n            and not host_ids\n            and not relation_claim_ids\n        ):\n""",
        """        host_ids = qualified_ids & host_query_ids\n        canonical_intent_ids = qualified_ids & canonical_intent_query_ids\n        relation_claim_ids = qualified_ids & relation_claim_query_ids\n        if not required_ids and not original_hit and not host_ids and not canonical_intent_ids:\n            continue\n        if (\n            broad_context_only\n            and not original_hit\n            and not host_ids\n            and not canonical_intent_ids\n            and not relation_claim_ids\n        ):\n""",
    )
    replace_once(
        "docmancer/docs/application/docs_context_projection.py",
        """    decision = context_selection_decision(sources, public_query_ids)\n    if (\n        required_query_ids\n        and not (set(decision.covered_query_ids) & required_query_id_set)\n        and (\n            bool(query_plan.get(\"unresolved_parts\"))\n            or not broad_context_only\n        )\n    ):\n""",
        """    decision = context_selection_decision(sources, public_query_ids)\n    covered_query_ids = set(decision.covered_query_ids)\n    context_fallback_ids = (\n        canonical_intent_query_ids | host_query_ids | relation_claim_query_ids\n    )\n    if (\n        required_query_ids\n        and not (covered_query_ids & required_query_id_set)\n        and not (broad_context_only and covered_query_ids & context_fallback_ids)\n    ):\n""",
    )
    replace_once(
        "docmancer/docs/application/docs_context_projection.py",
        '{"original", "mandatory_facet", "host_lookup", "auto_clause", "exact_path"}',
        '{"original", "mandatory_facet", "host_lookup", "auto_clause", "canonical_intent", "exact_path"}',
    )

    # Broad architecture/workflow material is context, not a complete answer.
    replace_once(
        "docmancer/docs/domain/project_answer_contract.py",
        """_CONTEXT_ONLY_RELATIONS = frozenset({\n    \"behavior\", \"contrast\", \"implementation\", \"purpose\", \"procedure\",\n    \"selection_policy\",\n})\n""",
        """_CONTEXT_ONLY_RELATIONS = frozenset({\n    \"architecture\", \"behavior\", \"contrast\", \"implementation\", \"purpose\",\n    \"procedure\", \"selection_policy\", \"workflow\",\n})\n""",
    )
    replace_once(
        "docmancer/docs/domain/project_answer_contract.py",
        """        if obligation.kind == \"definition\":\n            return False\n""",
        """        if obligation.kind in {\"definition\", \"workflow\"}:\n            return False\n""",
    )

    # A plural CLI command is not automatically an inventory of Docs MCP tools.
    replace_once(
        "docmancer/docs/domain/_project_answer_contract_shared.py",
        'r"\\b(?:tools|commands|methods|инструмент(?:ы|ов)|команд(?:ы|ах))\\b", re.I,',
        'r"\\b(?:tools|инструмент(?:ы|ов))\\b", re.I,',
    )

    # Do not manufacture English wrappers around Russian fragments.
    replace_once(
        "docmancer/docs/application/recovery.py",
        """def _suggested_questions(\n    question: str,\n    requirements: Any,\n    *,\n    evidence_path: str | None,\n) -> list[str]:\n    candidates = _requirement_spans(requirements, question)\n""",
        """def _suggested_questions(\n    question: str,\n    requirements: Any,\n    *,\n    evidence_path: str | None,\n) -> list[str]:\n    # The fixed English wrapper cannot preserve Russian grammar or semantics.\n    # Prefer the typed local-source recovery until a reviewed same-language\n    # rephrase family exists.\n    if re.search(r\"[А-Яа-яЁё]\", question):\n        return []\n    candidates = _requirement_spans(requirements, question)\n""",
    )

    # Improve ranking intent without translating proof semantics.
    replace_once(
        "docmancer/docs/domain/project_query_intent.py",
        '    wants_how_to = has_any(["how do i", "how to", "how does", "usage", "use", "setup", "configure", "config", "install", "quickstart", "getting started"])\n',
        '    wants_how_to = has_any(["how do i", "how to", "how does", "usage", "use", "setup", "configure", "config", "install", "quickstart", "getting started", "как ", "настро", "установ", "запуст", "пользова", "с чего начать", "первые команд"])\n',
    )
    replace_once(
        "docmancer/docs/domain/project_query_intent.py",
        '    wants_ingestion = has_any(["ingest", "ingestion", "index", "indexing", "indexed", "retrieval", "retrieve", "chunk", "chunking", "embedding", "vector", "fts", "qdrant"])\n',
        '    wants_ingestion = has_any(["ingest", "ingestion", "index", "indexing", "indexed", "retrieval", "retrieve", "chunk", "chunking", "embedding", "vector", "fts", "qdrant", "индекс", "поиск", "чанк", "секци", "эмбед", "вектор", "хран"])\n',
    )
    replace_once(
        "docmancer/docs/domain/project_query_intent.py",
        '    wants_troubleshooting = has_any(["error", "bug", "fail", "failed", "why doesn\'t", "why does not", "not working", "stale", "missing", "diagnose", "doctor", "fix", "troubleshoot"])\n',
        '    wants_troubleshooting = has_any(["error", "bug", "fail", "failed", "why doesn\'t", "why does not", "not working", "stale", "missing", "diagnose", "doctor", "fix", "troubleshoot", "ошиб", "проблем", "не работает", "не наход", "устар", "диагност"])\n',
    )
    replace_once(
        "docmancer/docs/domain/project_doc_ranking.py",
        """    source_type = taxonomy[\"source_type\"]\n    authority = taxonomy[\"authority\"]\n\n    if authority == \"artifact\":\n""",
        """    source_type = taxonomy[\"source_type\"]\n    authority = taxonomy[\"authority\"]\n\n    if (\n        any(term in h for term in (\"legacy\", \"compatibility\", \"migration\", \"deprecated\"))\n        and not getattr(intent, \"wants_release_history\", False)\n    ):\n        return 0.15\n\n    if authority == \"artifact\":\n""",
    )
    replace_once(
        "docmancer/docs/domain/project_doc_ranking.py",
        """    if name == \"troubleshooting\":\n        if p.endswith(\"readme.md\") or p.startswith(\"docs/\") or \"/docs/\" in p:\n            return 1.25\n""",
        """    if name == \"troubleshooting\":\n        if \"troubleshooting\" in p:\n            return 2.2\n        if p.endswith(\"readme.md\") or p.startswith(\"docs/\") or \"/docs/\" in p:\n            return 1.25\n""",
    )

    # Register the new maintained documents in the project-doc catalog.
    replace_once(
        "docatlas.project-docs.yaml",
        """  - path: docs/adr/0001-mcp-boundary-contracts.md\n    role: project_architecture\n    scope: project\n    description: MCP transport boundary, response, and compatibility decisions.\n    authority: source_of_truth\n    status: active\n    impact: track\n""",
        """  - path: docs/adr/0001-mcp-boundary-contracts.md\n    role: project_architecture\n    scope: project\n    description: MCP transport boundary, response, and compatibility decisions.\n    authority: source_of_truth\n    status: active\n    impact: track\n\n  - path: docs/adr/0002-context-retrieval-vs-answer-proof.md\n    role: project_architecture\n    scope: project\n    description: Retrieval-first project-chat delivery and strict answer-certification boundary.\n    authority: source_of_truth\n    status: active\n    impact: track\n\n  - path: docs/analysis/context7-style-project-chat-regression.md\n    role: development\n    scope: project\n    description: Evidence for the legacy-delivery regression and bounded replacement.\n    authority: supporting\n    status: active\n    impact: search_only\n""",
    )
    replace_once(
        "docatlas.project-docs.yaml",
        """  - path: eval/project_chat_quality_v1/README.md\n    role: development\n    scope: project\n    description: Novel adversarial project-chat gate for false support, predicate specificity, closed inventories, and contamination.\n    authority: source_of_truth\n    status: active\n    impact: search_only\n""",
        """  - path: eval/project_chat_quality_v1/README.md\n    role: development\n    scope: project\n    description: Novel adversarial project-chat gate for false support, predicate specificity, closed inventories, and contamination.\n    authority: source_of_truth\n    status: active\n    impact: search_only\n\n  - path: eval/project_chat_context7_v1/README.md\n    role: development\n    scope: project\n    description: RU/EN retrieval-first project-chat corpus and public-path gate.\n    authority: source_of_truth\n    status: active\n    impact: search_only\n""",
    )

    replace_once(
        "README.md",
        """This makes `get_docs_context` the single high-level entry point. Narrow typed questions with complete relation-specific proof receive `docs_answer`; broader questions receive cited retrieval-only `docs_context`; coding and patch tasks receive source-bound `patch_context`; missing safe evidence returns fail-closed `insufficient_evidence`. When completeness or the requested relation is uncertain, the server chooses `docs_context`, not `docs_answer`. Delivery strategy, debug shape, and packet budget are server-owned policy.\n""",
        """This makes `get_docs_context` the single high-level entry point. Natural-language project questions retrieve bounded current repository documentation first. Narrow typed questions with complete relation-specific proof receive `docs_answer`; broader questions receive cited retrieval-only `docs_context`; coding and patch tasks receive source-bound `patch_context`; missing safe evidence returns fail-closed `insufficient_evidence`. Parser uncertainty blocks answer certification, not safe project-scoped retrieval. Retrieval-only aliases and semantic matches never authorize an answer or edit. Delivery strategy, debug shape, and packet budget are server-owned policy.\n""",
    )
    replace_once(
        "CHANGELOG.md",
        "## [Unreleased]\n",
        """## [Unreleased]\n\n### Changed\n\n- Project chat now retrieves bounded current project documentation before attempting strict answer certification. Natural Russian newcomer questions can use auditable retrieval-only aliases and fall back to non-authoritative `docs_context`; generic CLI commands are no longer confused with the Docs MCP tool inventory, and mixed-language recovery questions are not generated.\n\n### Fixed\n\n- Current-state preflight reports nearby legacy `.docmancer` derived indexes as reindex diagnostics without reading or migrating them. Explicit calibrated semantic-match provenance can qualify `docs_context` while remaining insufficient by itself for `docs_answer`.\n""",
    )

    print("context7-style project-chat patch applied")


if __name__ == "__main__":
    main()
