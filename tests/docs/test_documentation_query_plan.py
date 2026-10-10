from docmancer.docs.domain.documentation_query_plan import (
    DocumentationLookup,
    build_documentation_query_plan,
)
from docmancer.docs.domain.context_budget import ContextBudget
from docmancer.docs.domain.evidence_qualification import (
    derived_parent_trace,
    qualify_evidence,
)
import pytest


def test_documentation_lookup_rejects_invalid_lineage():
    with pytest.raises(ValueError, match="unsupported"):
        DocumentationLookup("query-x", "x", "hint", relation="internal_hint")
    with pytest.raises(ValueError, match="public parent"):
        DocumentationLookup("query-x", "x", "canonical_intent", relation="audited_rewrite")


def test_context_budget_is_a_product_invariant():
    budget = ContextBudget()

    assert budget.max_sources == 3
    assert budget.max_tokens == 800
    assert budget.bounded_tokens(2_000) == 800


def test_evidence_qualification_fails_closed_and_owns_derived_lineage():
    rejected = qualify_evidence(
        {"qualified": True}, query_id="query-intent-1", visible_text="unrelated",
    )
    assert rejected.qualified is False
    assert rejected.reason == "missing_visible_query_terms"

    qualified = qualify_evidence(
        {
            "qualified": True,
            "query_text": "project architecture",
            "relation": "audited_rewrite",
        },
        query_id="query-intent-1",
        visible_text="Project architecture boundaries.",
    )
    parent = derived_parent_trace(
        qualified.trace,
        source_query_id="query-intent-1",
        parent_query_id="query-original",
    )
    assert qualified.qualified is True
    assert parent is not None
    assert parent["coverage_kind"] == "derived"
    assert parent["derived_from_query_ids"] == ["query-intent-1"]


def test_evidence_qualification_rejects_metadata_only_term_matches():
    qualification = qualify_evidence(
        {"qualified": True, "query_text": "project architecture"},
        query_id="query-original",
        visible_text="docs/project-architecture.md\nArchitecture\nunrelated body",
        evidence_text="unrelated body",
    )

    assert qualification.qualified is False
    assert qualification.reason == "insufficient_visible_match"


@pytest.mark.parametrize("failed_direct", [False, True])
def test_derived_merge_never_invents_successful_direct_coverage(failed_direct):
    from docmancer.docs.application.context_selection import merge_query_matches

    derived = {"query-original": {
        "qualified": True, "coverage_kind": "derived",
        "derived_from_query_ids": ["query-intent-1"],
    }}
    failed = {"query-original": {"qualified": False, "coverage_kind": "direct"}}
    for inputs in ((derived, failed), (failed, derived)) if failed_direct else ((derived,),):
        trace = merge_query_matches(*inputs)["query-original"]
        assert trace["coverage_kinds"] == ["derived"]
        assert trace["derived_from_query_ids"] == ["query-intent-1"]


@pytest.mark.parametrize("question,expected", [
    ("Где находятся модули?", set()),
    ("Какие инструменты нужны для ремонта?", set()),
])
def test_exact_project_facets_and_negative_neighbors(question, expected):
    from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
    assert {alias.intent_id for alias in build_project_retrieval_aliases(question)} == expected


def test_host_policies_follow_relevant_facets_not_compound_union():
    plan = build_documentation_query_plan(
        "Compare Docs MCP workflow and Packs MCP workflow",
        lookup_queries=("Docs MCP workflow", "Packs MCP workflow"),
    )
    original = plan.queries[0]
    assert not original.forbidden_evidence_terms
    docs, packs = [q for q in plan.queries if q.origin == "host_lookup"]
    assert "packs mcp runtime" in docs.forbidden_evidence_terms
    assert "packs mcp runtime" not in packs.forbidden_evidence_terms
    assert docs.public_parent_query_id is packs.public_parent_query_id is None


def test_unrecognized_host_inherits_only_single_facet_policy():
    plan = build_documentation_query_plan(
        "Explain Docs MCP workflow", lookup_queries=("public tool routing",),
    )
    host = next(q for q in plan.queries if q.origin == "host_lookup")
    assert host.forbidden_evidence_terms == plan.queries[0].forbidden_evidence_terms
    assert host.forbidden_evidence_terms


@pytest.mark.parametrize("suffix,equivalent", [
    (" и объяснить архитектуру?", False),
    (" и проверить неизвестный контракт?", False),
    (" с UnknownLedger?", False),
])
def test_audited_installation_equivalence_is_complete_and_bounded(suffix, equivalent):
    question = "Как установить DocAtlas локально и проверить, что он работает" + suffix
    plan = build_documentation_query_plan(question)
    audited = [q for q in plan.queries if q.relation == "audited_rewrite"]
    assert bool(audited) is equivalent
    if equivalent:
        assert len(audited) == 1
        assert "local installation setup verification" in audited[0].text
        assert audited[0].public_parent_query_id == "query-original"


def test_failed_derived_probe_does_not_contribute_successful_lineage():
    from docmancer.docs.application.context_selection import merge_query_matches
    trace = merge_query_matches(
        {"query-original": {"qualified": True, "coverage_kind": "direct"}},
        {"query-original": {"qualified": False, "coverage_kind": "derived", "derived_from_query_ids": ["query-intent-1"]}},
    )["query-original"]
    assert trace["coverage_kinds"] == ["direct"]
    assert not trace.get("derived_from_query_ids")


def test_requirement_hints_inherit_applicable_host_policies():
    from types import SimpleNamespace
    plan = build_documentation_query_plan(
        "Explain Docs MCP workflow",
        requirements=SimpleNamespace(retrieval_hints=("public tool routing",), concept_queries=()),
    )
    hint = next(q for q in plan.queries if q.origin == "retrieval_hint")
    assert hint.forbidden_evidence_terms == plan.queries[0].forbidden_evidence_terms
    assert hint.forbidden_evidence_terms
    assert hint.relation == "host_lookup"
    assert hint.public_parent_query_id is None


@pytest.mark.parametrize("question", [
    "Какой срок хранения документации предписывает лунный квантовый регламент DocAtlas?",
    "Какой срок хранения документации устанавливает янтарный речной регламент проекта?",
    "Как хранение документации проекта регулируется сапфировым соглашением?",
    "Как хранить документацию проекта, как предписывает медный прилив?",
    "What documentation retention period does the silver estuary policy prescribe?",
    "How does the silver estuary govern project documentation storage?",
    "What project documentation storage duration does the amber delta prescribe?",
    "Which project documentation storage regulations does the violet orchard impose?",
    "Which command starts Docs MCP as prescribed by the amber delta?",
    "Какая команда запускает Docs MCP согласно янтарному регламенту?",
])
def test_novel_normative_premises_are_not_replaced_by_topic_aliases(question):
    from docmancer.docs.domain.project_retrieval_intent import (
        build_project_retrieval_aliases, project_retrieval_disposition,
    )
    assert build_project_retrieval_aliases(question) == ()
    assert project_retrieval_disposition(question) == "fail_closed"
    plan = build_documentation_query_plan(question)
    assert plan.original_question == question
    assert not any(q.origin == "canonical_intent" for q in plan.queries)


@pytest.mark.parametrize("question", [
    "How does the amber delta store project documentation?",
    "Как проект хранит документацию для янтарной дельты?",
    "Explain project architecture and the violet orchard subsystem",
    "Как устроена архитектура проекта для сапфирового сада?",
])
def test_novel_topics_without_normative_premises_still_search(question):
    from docmancer.docs.domain.project_retrieval_intent import project_retrieval_disposition
    plan = build_documentation_query_plan(question)
    aliases = [q for q in plan.queries if q.origin == "canonical_intent"]
    assert project_retrieval_disposition(question) == "broad_context"
    assert plan.queries[0].text == question
    assert all(q.relation == "host_lookup" and q.public_parent_query_id is None for q in aliases)


@pytest.mark.parametrize("question", [
    "Какой срок хранения документации предписывает лунный квантовый регламент DocAtlas?",
    "How does the silver estuary govern project documentation storage?",
])
def test_live_normative_premise_cannot_use_generic_storage_evidence(tmp_path, monkeypatch, question):
    from tests.test_named_document_context_integration import _named_document_service
    from docmancer.mcp.docs_server import call_docs_tool_payload

    service, project = _named_document_service(
        tmp_path, monkeypatch, ["ARCHITECTURE.md"], {"ARCHITECTURE.md": (
            "# Project documentation storage and isolation\n\n"
            "Project documentation storage uses a per-project SQLite index.\n"
        )},
    )
    result = call_docs_tool_payload(
        "get_docs_context", {"question": question, "project_path": project}, service,
    )
    assert result["status"] == "insufficient_evidence"
    assert result["answer_supported"] is False
    assert result["context_available"] is False
    assert not result.get("sources")


@pytest.mark.parametrize("body,covered", [
    (
        "| Command | Description |\n|---------|-------------|\n"
        "| `doc-atlas setup` | Create config and SQLite database, auto-detect installed agents, "
        "and install skill files. Use `--all` for non-interactive installation. |\n"
        "| `doc-atlas ingest <path>` | Index local files or directories.",
        False,
    ),
    (
        "## One-line install\n\nInstall `uv`, the `doc-atlas` CLI, and register the docs MCP server "
        "into your agent in a single command:\n\n```bash\n"
        "curl -LsSf https://raw.githubusercontent.com/Vanilla1999/DocAtlas/main/scripts/install.sh | sh\n```",
        False,
    ),
    (
        "# Local installation setup verification\n\n"
        "Install DocAtlas locally and run command-line help to verify the setup.\n",
        True,
    ),
])
def test_audited_installation_needs_qualified_evidence_not_just_a_plan_alias(body, covered):
    from docmancer.docs.domain.query_terms import documentation_query_terms

    plan = build_documentation_query_plan(
        "Как установить DocAtlas локально и проверить, что он работает?",
    )
    alias = next(q for q in plan.queries if q.relation == "audited_rewrite")
    qualification = qualify_evidence(
        {
            "query_text": alias.text,
            "query_terms": documentation_query_terms(alias.text),
            "relation": alias.relation,
            "parent_exact_terms": alias.parent_exact_terms,
        },
        query_id=alias.query_id, visible_text=body, evidence_text=body,
    )
    parent = derived_parent_trace(
        qualification.trace, source_query_id=alias.query_id,
        parent_query_id=alias.public_parent_query_id,
    )
    assert qualification.qualified is covered
    assert (parent is not None) is covered
    if not covered:
        assert qualification.reason == "insufficient_visible_match"


@pytest.mark.parametrize("lookup", [
    "coding agents documentation",
    "local-first documentation context for deployment agents",
    "documentation context for coding agents without project overview",
])
def test_product_definition_neighbors_do_not_derive_original(lookup):
    plan = build_documentation_query_plan(
        "Что такое DocAtlas и зачем он нужен разработчику?",
        lookup_queries=(lookup,),
    )
    host = next(q for q in plan.queries if q.query_id == "query-lookup-1")
    assert host.relation == "host_lookup"
    assert host.public_parent_query_id is None


