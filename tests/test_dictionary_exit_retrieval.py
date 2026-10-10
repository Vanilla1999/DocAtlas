"""New dictionary-exit contract tests; legacy recall gates remain untouched."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from types import SimpleNamespace

import pytest

from docmancer.core.config import DocmancerConfig, QueryRouter
from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application.need_query_schedule import (
    requirement_search_probes, schedule_need_queries, scheduled_plan,
)
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.lifecycle_policy import lifecycle_allows, lifecycle_intent
from docmancer.docs.domain.project_doc_ranking import (
    project_source_taxonomy, rerank_project_doc_chunks, source_lane_allowed,
    source_requirement_boost, source_weight_for_intent,
)
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
from docmancer.docs.domain.query_terms import documentation_query_terms
from docmancer.docs.domain.question_component_rewrite import rewrite_component
from docmancer.docs.domain.question_surface_normalization import normalize_question_surface
from docmancer.docs.domain.retrieval_routing import route_initial_stages
from docmancer.docs.domain.snippets import infer_snippet_query_intent, _infer_language
from docmancer.docs.domain.technical_terms import controlled_noun_forms, coerce_technical_term
from docmancer.docs.domain.tool_selection import select_public_docs_tool, normalize_public_docs_action
from docmancer.mcp.search import _tokens
from docmancer.retrieval.dispatch import HybridRetrievalError, RetrievalDispatcher
from docmancer.retrieval.query_planning import build_query_plan, metadata_matches_filters


@pytest.mark.parametrize("question", [
    "  Как настроить проектную документацию?\n",
    "How does get_docs_context accept a request and select visible sources?",
    "How should I use FastAPI Depends and TestClient examples?",
    "Explain Riverpod autoDispose and queued-work permission contracts.",
    "Describe the architecture, docs sync, testing and offline workflow.",
])
def test_plan_contains_only_exact_caller_queries(question):
    requirements = SimpleNamespace(
        retrieval_hints=("invented_hint",), concept_queries=("docs/testing.md pytest",),
        proof_obligations=(SimpleNamespace(expected_value="docs-serve"),),
        component_scope_complete=True, unresolved_parts=("unresolved",),
    )
    lookups = tuple(f"  explicit lookup {index}\n" for index in range(7))
    plan = build_documentation_query_plan(question, lookup_queries=lookups,
        explicit_path="docs/explicit.md", requirements=requirements)
    assert tuple(row.text for row in plan.queries) == (question, *lookups[:5])
    assert plan.explicit_paths == ("docs/explicit.md",)
    assert plan.component_contract == ()
    assert plan.component_scope_complete is False
    assert plan.unresolved_parts == ("unresolved",)
    assert plan.as_payload()["required_query_ids"] == ["query-original"]
    for row in plan.queries:
        assert row.public_parent_query_id is None
        assert row.preferred_catalog_roles == row.forbidden_catalog_roles == ()
        assert row.forbidden_evidence_terms == row.parent_exact_terms == ()
        assert row.component_rewrite_audit is None
        assert row.need_subject is None
    assert all(row.relation == "host_lookup" for row in plan.queries[1:])


def test_repeated_explicit_lookups_remain_independently_attributed():
    plan = build_documentation_query_plan("same", lookup_queries=("same", "same", "  ", "other"))
    assert [(row.query_id, row.text) for row in plan.queries] == [
        ("query-original", "same"), ("query-lookup-1", "same"),
        ("query-lookup-2", "same"), ("query-lookup-4", "other"),
    ]
    assert all(row.public_parent_query_id is None for row in plan.queries)


def test_scheduler_cannot_resurrect_need_or_requirement_probes():
    plan = build_documentation_query_plan("original", lookup_queries=("explicit",))
    unchanged, scheduled = scheduled_plan(plan, supplemental_queries=("invented",))
    assert unchanged is plan
    assert [row.text for row in scheduled] == ["explicit"]
    assert schedule_need_queries(plan, [object()], optional_limit=0) == ()
    assert requirement_search_probes([object()]) == ()
    with pytest.raises(ValueError):
        schedule_need_queries(plan, (), optional_limit=13)


def test_backend_plan_uses_literal_syntax_and_preserves_hash_bindings():
    class Requirements:
        requirements_hash = "source-bound-hash"

        def __iter__(self):
            return iter([SimpleNamespace(kind="entity", value="inventedAPI")])

    query = "  Use `Client.call` only if CONFIG_KEY is not set.  "
    requirements = Requirements()
    filters = {"project_identity": "repo", "resolved_version": "2.1",
        "exact_snapshot_required": True, "forbidden_sources": ["mirror"]}
    first = build_query_plan(query, filters=filters, requirements=requirements)
    assert first.concept_queries == ()
    assert "inventedAPI" not in {term.value for term in first.exact_terms}
    assert "Client.call" in {term.value for term in first.exact_terms}
    assert first.original_query_hash == sha256(query.encode()).hexdigest()
    assert first.requirements is requirements
    assert first.requirements_hash == "source-bound-hash"
    assert first == build_query_plan(query, filters=filters, requirements=requirements)
    assert first.plan_hash != build_query_plan(query, filters={**filters, "resolved_version": "2.2"}, requirements=requirements).plan_hash


def test_scope_version_snapshot_freshness_and_forbidden_source_guards():
    filters = {"project_identity": "repo", "resolved_version": "2.1",
        "exact_snapshot_required": True, "index_freshness": "synchronized",
        "forbidden_sources": ["mirror"]}
    metadata = {"project_identity": "repo", "resolved_version": "2.1",
        "docs_snapshot_exact": True, "index_freshness": "synchronized"}
    assert metadata_matches_filters(metadata, filters, source="official")
    for key, value in [("project_identity", "other"), ("resolved_version", "2.2"),
                       ("docs_snapshot_exact", False), ("index_freshness", "stale")]:
        assert not metadata_matches_filters({**metadata, key: value}, filters, source="official")
    assert not metadata_matches_filters(metadata, filters, source="mirror")


def test_dispatch_executes_original_once_and_ignores_config_topic_router():
    calls = []

    class Store:
        def query(self, text, **kwargs):
            calls.append((text, kwargs))
            return []

    config = DocmancerConfig()
    config.retrieval.routers = [QueryRouter(match=".*", filters={"library_id": "guessed"})]
    dispatcher = RetrievalDispatcher(store=Store(), config=config)
    question = "  Test `Client.call` --dry-run CONFIG_KEY in docs/explicit.md  "
    filters = {"project_identity": "repo"}
    result = dispatcher.run(question, filters=filters, limit=2, budget=128)
    assert len(calls) == 1
    assert calls[0][0] == question
    assert calls[0][1]["filters"] == filters
    assert calls[0][1]["budget"] == 128
    assert result.query_plan_hash and result.fusion_config_hash
    with pytest.raises(HybridRetrievalError):
        dispatcher.run(question, mode="hybrid")
    assert len(calls) == 1


@pytest.mark.parametrize("question", [
    "Как запустить проект и проверить документацию?",
    "Explain architecture and testing before contributing.",
    "Riverpod autoDispose", "Click command group", "FastAPI Depends example",
])
def test_no_semantic_alias_rewrite_intent_or_language_invention(question):
    assert build_project_retrieval_aliases(question) == ()
    assert normalize_question_surface(question) is None
    assert rewrite_component(question) is None
    assert classify_project_query_intent(question).name == "general"
    intent = infer_snippet_query_intent(question)
    assert intent.expected_languages == []
    assert not {"keepAlive", "ref.watch", "@click.group"} & set(intent.symbols)
    assert _infer_language("opaque snippet", {"library_id": "fastapi", "source": "docs.rs"}) is None


def test_literal_identifiers_connectors_and_protocol_actions_are_retained():
    assert _tokens("create issue", expand=True) == ["create", "issue"]
    assert controlled_noun_forms("indices") == ("indices",)
    assert coerce_technical_term("Client.call").aliases == ("Client.call",)
    from docmancer.docs.domain.technical_terms import technical_term_present
    assert coerce_technical_term("--dry_run").raw == "--dry_run"
    assert not technical_term_present(coerce_technical_term("--dry-run"), "dry_run")
    assert not technical_term_present(coerce_technical_term("foo_bar"), "foo-bar")
    assert {"not", "if", "and", "не", "если"} <= set(documentation_query_terms("not if and не если"))
    assert infer_snippet_query_intent("Client.call").symbols == ["Client.call"]
    assert select_public_docs_tool("delete documentation and refresh the index").tool == "get_docs_context"
    assert select_public_docs_tool("ignored", next_action_tool="prepare_docs").tool == "prepare_docs"
    assert normalize_public_docs_action({"tool": "sync_project_docs", "requires_confirmation": True}) == {
        "tool": "prepare_docs", "type": "prepare_docs", "requires_confirmation": True,
        "arguments_patch": {"action": "sync_project_docs"},
    }


def test_prose_does_not_authorize_source_stages_or_historical_exemption():
    route = route_initial_stages(question="Find WidgetService imports across modules and fix it",
        mode="project-only", dependency_requested=False, project_doc_items=[{"content": "src/widget.py"}])
    assert route.project_mode
    assert not route.use_source_evidence
    assert route.intent == "docs"
    assert lifecycle_intent("Historical previous version") == "current"
    assert not lifecycle_allows({"lifecycle_status": "superseded"}, "current")
    assert lifecycle_allows({"lifecycle_status": "superseded"}, "historical")
    assert not source_lane_allowed("eval/results.md", "show evaluation metrics")
    assert project_source_taxonomy("ARCHITECTURE.md")["authority"] == "unknown"
    assert "research_artifact" in project_source_taxonomy("docs/research/report.md")["risk_flags"]
    assert source_weight_for_intent("docs/testing.md", "pytest", object()) == 1.0
    assert source_requirement_boost("CONTRIBUTING.md", "testing", object()) == 1.0


def test_ranker_retains_stale_failed_qualification_and_source_quota_guards():
    @dataclass
    class Chunk:
        path: str
        score: float
        stale: bool = False
        lifecycle_status: str = "active"
        metadata: dict = field(default_factory=dict)

    chunks = [Chunk("a.md", 1), Chunk("a.md", .9), Chunk("a.md", .8),
        Chunk("stale.md", 9, stale=True), Chunk("old.md", 8, lifecycle_status="superseded"),
        Chunk("failed.md", 7, metadata={"retrieval_query_matches": {"query-original": {"qualified": False}}}),
        Chunk("b.md", .7)]
    ranked = rerank_project_doc_chunks(chunks, question="architecture testing",
        intent=classify_project_query_intent("architecture testing"), limit=4, narrow_max_per_source=2)
    assert [chunk.path for chunk in ranked] == ["a.md", "a.md", "b.md"]
    assert all(chunk.metadata["project_ranking"]["base_score"] ==
        chunk.metadata["project_ranking"]["final_score"] for chunk in ranked)


def test_sqlite_removes_topic_features_but_keeps_identity_filters(tmp_path):
    store = SQLiteStore(tmp_path / "index.db", tmp_path / "extracted")
    store.add_documents([
        Document(source="docs/a.md", content="# Configure widget\n\nconfigure widget",
            metadata={"project_identity": "repo", "title": "Configure widget"}),
        Document(source="docs/b.md", content="# Terms and Conditions\n\nconfigure widget",
            metadata={"project_identity": "other", "title": "Terms and Conditions"}),
    ], recreate=True)
    results = store.query("configure widget", filters={"project_identity": "repo"}, limit=5, budget=128)
    assert results
    assert {chunk.source for chunk in results} == {"docs/a.md"}
    removed = {"task_action_title_boost", "boilerplate_title_penalty", "project_rule_authority_boost",
        "non_legal_query_legal_source_penalty"}
    assert all(not removed & set(chunk.metadata["ranking"]["feature_contributions"]) for chunk in results)


def test_missing_literal_named_subject_is_not_lost_with_framing_tables():
    trace = SQLiteStore._lexical_match_trace(
        "Telegram notifications after indexing DocAtlas", title="Workflow",
        body="DocAtlas indexing workflow", mode="or_fallback", bm25_cost=-1.0,
    )
    assert "telegram" in trace["missing_exact_terms"]
    # Without a framing dictionary even a capitalized request word remains a
    # conservative exact constraint; it cannot exempt a missing named subject.
    from docmancer.docs.domain.query_terms import is_exact_technical_token
    assert is_exact_technical_token("Please")


def test_public_context_imports_keep_helper_bridge_interfaces():
    from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
    from docmancer.docs.application.context_candidate_ranking import technical_anchors
    assert callable(handle_context_tool)
    assert "CONFIG_KEY" in technical_anchors("CONFIG_KEY")


def test_project_read_boundary_discards_generated_plan_and_preserves_scope_budget(tmp_path):
    from docmancer.docs.application._project_docs_service_part03 import _ProjectDocsServicePart03
    from docmancer.docs.domain.documentation_query_plan import DocumentationLookup, DocumentationQueryPlan
    calls = []

    class Agent:
        config = DocmancerConfig()

        def query(self, text, **kwargs):
            calls.append((text, kwargs))
            return []

    class Service(_ProjectDocsServicePart03):
        facade = SimpleNamespace()

        def _agent_instance(self):
            return Agent()

        def _repository_identity(self, root):
            return "repo"

    question = "  architecture and testing CONFIG_KEY  "
    polluted = DocumentationQueryPlan(question, (
        DocumentationLookup("query-invented", "inventedAPI", "canonical_intent", False),
    ))
    diagnostics = {}
    assert Service().query_project_docs(str(tmp_path), question, tokens=128, limit=2,
        scope="module", module_path="packages/exact", evidence_path="docs/explicit.md",
        lookup_queries=("  explicit lookup  ",), documentation_query_plan=polluted,
        internal_diagnostics=diagnostics) == []
    assert [text for text, _ in calls] == [question, question, "  explicit lookup  "]
    assert diagnostics["planned_query_ids"] == ["query-original", "query-lookup-1"]
    for _, kwargs in calls:
        assert kwargs["budget"] <= 128
        assert kwargs["filters"]["project_identity"] == "repo"
        assert kwargs["filters"]["project_doc_path"] == "docs/explicit.md"
        assert kwargs["filters"]["module_path"] == "packages/exact"
        assert kwargs["filters"]["doc_scope"] == "module"
