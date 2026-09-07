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


def test_documentation_query_plan_owns_public_retrieval_query_ids():
    plan = build_documentation_query_plan(
        "Please explain DocAtlas architecture and testing.",
        lookup_queries=(
            "project purpose",
            "project architecture",
            "project data flow",
            "local development",
            "test commands",
        ),
    ).as_payload()

    assert plan["public_query_ids"] == [
        "query-original",
        "query-lookup-1",
        "query-lookup-2",
        "query-lookup-3",
        "query-lookup-4",
        "query-lookup-5",
    ]
    assert plan["required_query_ids"] == []
    assert any(item["origin"] == "canonical_intent" for item in plan["queries"])
    assert not any(
        query_id.startswith("query-intent-") for query_id in plan["public_query_ids"]
    )


def test_documentation_query_plan_owns_retrieval_only_alias_lineage():
    plan = build_documentation_query_plan(
        "Как устроен полный процесс работы Docs MCP?",
        lookup_queries=("MCP public tools",),
    ).as_payload()
    by_origin = {
        origin: [item for item in plan["queries"] if item["origin"] == origin]
        for origin in {item["origin"] for item in plan["queries"]}
    }

    assert by_origin["original"][0]["relation"] == "direct"
    assert by_origin["original"][0]["public_parent_query_id"] is None
    assert by_origin["host_lookup"][0]["relation"] == "host_lookup"
    assert by_origin["host_lookup"][0]["public_parent_query_id"] is None
    assert all(
        item["relation"] == "host_lookup"
        and item["public_parent_query_id"] is None
        and item["preferred_catalog_roles"]
        for item in by_origin["canonical_intent"]
    )


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


def test_same_text_lookups_retain_independent_public_and_canonical_ids():
    plan = build_documentation_query_plan(
        "Explain get_docs_context project architecture",
        lookup_queries=("get_docs_context", "project architecture overview components indexing retrieval storage",
                        "get_docs_context"),
    )
    assert {q.query_id for q in plan.queries if q.origin == "host_lookup"} == {
        "query-lookup-1", "query-lookup-2", "query-lookup-3",
    }
    assert any(q.origin == "exact_anchor" and q.text == "get_docs_context" for q in plan.queries)
    assert any(
        q.origin == "canonical_intent"
        and q.text == "project architecture overview components indexing retrieval storage"
        for q in plan.queries
    )


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
    ("Что это за проект и какую проблему он решает?", {"product_overview"}),
    ("Как устроена архитектура проекта и где проходят основные границы модулей?", {"project_architecture"}),
    ("Как проходит запрос get_docs_context от MCP-входа до выбора источников?", {"retrieval_pipeline"}),
    ("Какие публичные инструменты предоставляет Docs MCP?", {"docs_mcp_public_tools"}),
    ("Как система выбирает доказательства?", {"evidence_selection"}),
    ("Почему проект не работает и как диагностировать проблему?", {"troubleshooting"}),
    ("Где находятся модули?", set()),
    ("Где начать читать код проекта?", {"contributor_start"}),
    ("Какие инструменты нужны для ремонта?", set()),
    ("Как система хранит доказательства?", {"project_storage"}),
])
def test_exact_project_facets_and_negative_neighbors(question, expected):
    from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
    assert {alias.intent_id for alias in build_project_retrieval_aliases(question)} == expected


def test_alias_budget_is_fair_across_requested_facets():
    from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
    aliases = build_project_retrieval_aliases("Explain project purpose, architecture, offline mode and context token budget")
    assert len(aliases) == 4
    assert {alias.intent_id for alias in aliases} == {
        "product_overview", "project_architecture", "offline_usage", "context_budget",
    }
    assert not any(alias.intent_id == "context_budget" for alias in build_project_retrieval_aliases("Explain project architecture"))


@pytest.mark.parametrize("question", [
    "Explain project architecture and testing",
    "Explain UnknownLedger project architecture",
    "Explain project architecture and the imaginary orbital subsystem",
])
def test_partial_canonical_facets_cannot_cover_original(question):
    plan = build_documentation_query_plan(question)
    aliases = [q for q in plan.queries if q.origin == "canonical_intent"]
    assert aliases
    assert all(q.relation == "host_lookup" and q.public_parent_query_id is None for q in aliases)


def test_only_audited_complete_equivalence_derives_original():
    question = "project architecture overview components indexing retrieval storage"
    plan = build_documentation_query_plan(question)
    alias = next(q for q in plan.queries if q.origin == "canonical_intent" and q.text == question)
    assert alias.text == question
    assert alias.relation == "audited_rewrite"
    assert alias.public_parent_query_id == "query-original"


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


@pytest.mark.parametrize("question", ["clear local index", "troubleshoot stale docs", "offline mode", "context token budget"])
def test_operational_facets_have_role_policies(question):
    from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
    aliases = build_project_retrieval_aliases(question)
    assert aliases
    assert all(alias.preferred_catalog_roles and "roadmap" in alias.forbidden_catalog_roles for alias in aliases)


@pytest.mark.parametrize("question", [
    "What output budgets apply to Docs MCP responses?",
    "Какой лимит источников в ответе Docs MCP?",
])
def test_output_budget_wording_gets_requested_facet(question):
    from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
    assert "context_budget" in {a.intent_id for a in build_project_retrieval_aliases(question)}


@pytest.mark.parametrize("suffix,equivalent", [
    ("?", True),
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


@pytest.mark.parametrize("question", [
    "Which pytest markers are available?",
    "Where is project docs configuration?",
    "Which environment variable controls the state root?",
])
def test_narrow_operational_probes_have_policies(question):
    from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
    aliases = build_project_retrieval_aliases(question)
    assert aliases
    assert all(a.preferred_catalog_roles and "roadmap" in a.forbidden_catalog_roles for a in aliases)


@pytest.mark.parametrize("question,expected", [
    ("Что это за проект и какую проблему он решает?", "architecture"),
    ("What problem does this project solve?", "architecture"),
    ("What problem is causing the project to fail?", "troubleshooting"),
])
def test_project_query_routing_distinguishes_purpose_from_failure(question, expected):
    from docmancer.docs.domain.project_query_intent import classify_project_query_intent
    assert classify_project_query_intent(question).name == expected


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
    "What problem is causing this project to fail?",
    "How do I solve a problem in this project?",
])
def test_failure_neighbors_do_not_become_product_purpose(question):
    from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
    from docmancer.docs.domain.project_query_intent import classify_project_query_intent
    assert {a.intent_id for a in build_project_retrieval_aliases(question)} == {"troubleshooting"}
    assert classify_project_query_intent(question).name == "troubleshooting"


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
