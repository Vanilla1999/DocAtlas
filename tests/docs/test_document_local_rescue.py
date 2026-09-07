"""Exercise rescue through the service, gateway, and real evidence selector."""
from dataclasses import replace
import hashlib
from types import SimpleNamespace

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application import project_context_service as service_impl
from docmancer.docs.application.project_context_service import ProjectContextService
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.docs.infrastructure.agent_index_gateway import AgentIndexGateway
from docmancer.docs.models import ProjectDocsChunk, ProjectDocsResult, ProjectMetadata
from docmancer.mcp.docs_server import call_docs_tool_payload


QUESTION = "What are the public tools of the Docs MCP server?"
OVERVIEW = "The Docs MCP server provides project documentation through a local application boundary with indexed repository sources."
TOOLS = "The three Docs MCP public tools are `get_docs_context`, `prepare_docs`, and `docs_status`."


@pytest.fixture
def rescue_case(tmp_path, monkeypatch):
    identity = ProjectDocsService._repository_identity(tmp_path)
    content_hash = hashlib.sha256((OVERVIEW + "\n" + TOOLS).encode()).hexdigest()
    observed = ProjectDocsChunk(
        title="Docs MCP", content=OVERVIEW, source=str(tmp_path / "docs/mcp.md"),
        url=None, path="docs/mcp.md", source_class="project_file",
        stable_chunk_id="overview", parent_logical_id="overview-parent",
        content_hash=content_hash, display_content_hash=hashlib.sha256(OVERVIEW.encode()).hexdigest(),
        char_start=0, char_end=len(OVERVIEW), line_start=1, line_end=1,
        project_identity=identity, lifecycle_status="active", authority="source_of_truth",
        metadata={"score": 1.0},
    )
    raw = RetrievedChunk(
        source=observed.source, chunk_index=1, text=TOOLS, score=1.0,
        metadata={
            "project_path": str(tmp_path), "project_identity": identity,
            "project_doc_path": observed.path, "project_doc_content_hash": content_hash,
            "source_class": "project_file", "doc_scope": "project",
            "project_doc_authority": "source_of_truth", "project_doc_lifecycle_status": "active",
            "stable_chunk_id": "tools", "parent_logical_id": "tools-parent",
            "char_span": [len(OVERVIEW) + 1, len(OVERVIEW) + 1 + len(TOOLS)],
            "line_span": [2, 2], "title": "Docs MCP public tools",
            "retrieval_query_ids": ["query-original"],
            "retrieval_query_matches": {"query-original": {"qualified": True}},
            "lexical_match": {"relation": "audited_rewrite", "public_parent_query_id": "query-original"},
        },
    )
    state = SimpleNamespace(rows=[raw], calls=[], observed=observed, raw=raw, root=tmp_path)

    class Dispatcher:
        def run(self, query, **kwargs):
            state.calls.append((query, kwargs))
            return SimpleNamespace(
                chunks=state.rows, mode_used="lexical", query_plan_hash="plan-hash",
                fusion_config_hash="fusion-hash",
            )

    gateway = AgentIndexGateway(
        DocmancerConfig(), default_agent=SimpleNamespace(store=SimpleNamespace(query=lambda: None)),
    )
    monkeypatch.setattr(gateway, "dispatcher_for", lambda agent, mode: Dispatcher())
    facade = SimpleNamespace(
        agent_gateway=gateway,
        read_project_metadata=lambda root: ProjectMetadata(project_path=root),
        get_project_docs=lambda root, question, **kwargs: state.docs,
    )
    state.docs = ProjectDocsResult(project_path=str(tmp_path), query=QUESTION, results=[observed])
    state.service = ProjectContextService(facade)
    state.gateway = gateway
    return state


@pytest.mark.parametrize("path", ["docs/mcp.md", "docs/MCP.md", "README.md"])
def test_missing_semantic_component_rescues_despite_lookup_coverage(rescue_case, path):
    case = rescue_case
    source = str(case.root / path)
    case.docs = replace(case.docs, results=[replace(case.observed, path=path, source=source, metadata={
        "score": 1.0, "retrieval_query_matches": {"query-lookup-1": {"qualified": True}},
    })])
    case.rows = [case.raw.model_copy(update={"source": source, "metadata": {
        **case.raw.metadata, "project_doc_path": path,
    }})]
    result = case.service.get_project_context(str(case.root), QUESTION, lookup_queries=("Docs MCP",))

    assert len(case.calls) == 1
    assert case.calls[0][1]["filters"]["project_doc_path"] == {"in": [path]}
    assert [chunk.stable_chunk_id for chunk in result.project_docs.results] == ["overview", "tools"]
    assert result.support_decision.answer_supported
    rescued = next(item for item in result.context_pack if item["stable_chunk_id"] == "tools")
    assert "query-original" not in rescued["retrieval_query_matches"]
    provenance = rescued["document_local_rescue"]
    assert provenance["component_id"] == result.requirements.requirements[0].requirement_id
    assert provenance["qualified_component_ids"] == [provenance["component_id"]]
    assert provenance["stable_chunk_id"] == "tools"
    assert provenance["parent_logical_id"] == "tools-parent"
    assert provenance["char_span"] == case.raw.metadata["char_span"]
    assert provenance["line_span"] == [2, 2]
    assert provenance["project_doc_content_hash"] == case.observed.content_hash
    assert provenance["display_content_hash"] == hashlib.sha256(TOOLS.encode()).hexdigest()
    assert provenance["query_plan_hash"] == "plan-hash"


@pytest.mark.parametrize("question,content", [
    (QUESTION, TOOLS),
    ("How do I install Docmancer locally and verify it works?", OVERVIEW),
])
def test_covered_or_unrecognized_components_do_not_trigger_rescue(rescue_case, question, content):
    case = rescue_case
    case.docs = replace(case.docs, results=[replace(
        case.observed, content=content, char_end=len(content),
        display_content_hash=hashlib.sha256(content.encode()).hexdigest(),
    )])
    case.service.get_project_context(str(case.root), question, lookup_queries=("uncovered lookup",))
    assert case.calls == []


@pytest.mark.parametrize("changes", [
    {"content_hash": None}, {"content_hash": ""}, {"content_hash": " "},
    {"stale": True}, {"project_identity": "other-project"},
    {"source_class": "dependency_doc"}, {"lifecycle_status": "superseded"},
    {"metadata": {"stale": True}}, {"metadata": {"risk_flags": ["unsafe"]}},
])
def test_inadmissible_observed_documents_cannot_seed_rescue(rescue_case, changes):
    case = rescue_case
    case.docs = replace(case.docs, results=[replace(case.observed, **changes)])
    case.service.get_project_context(str(case.root), QUESTION)
    assert case.calls == []


@pytest.mark.parametrize("changes", [
    {"project_identity": "other-project"}, {"project_path": "/other-root"},
    {"project_doc_content_hash": None}, {"project_doc_content_hash": ""},
    {"project_doc_content_hash": "old-hash"}, {"source_class": "dependency_doc"},
    {"doc_scope": "module"}, {"module_path": "other-module"}, {"module_id": "other-module"},
    {"project_doc_lifecycle_status": "superseded"}, {"project_doc_authority": "overview"},
    {"stale": True}, {"freshness": "stale"}, {"index_freshness": "stale"},
    {"risk_flags": ["unsafe"]}, {"stable_chunk_id": None}, {"parent_logical_id": None},
    {"instruction_risk_flags": ["unsafe"]}, {"stable_chunk_id": " "}, {"parent_logical_id": " "},
    {"char_span": [0]}, {"char_span": [0, 1]}, {"line_span": [0, 2]},
])
def test_each_candidate_must_preserve_source_and_current_provenance(rescue_case, changes):
    case = rescue_case
    case.rows = [case.raw.model_copy(update={"metadata": {**case.raw.metadata, **changes}})]
    result = case.service.get_project_context(str(case.root), QUESTION)
    assert len(case.calls) == 1
    assert [chunk.stable_chunk_id for chunk in result.project_docs.results] == ["overview"]
    assert not result.support_decision.answer_supported


def test_lexical_and_parent_claims_do_not_substitute_for_local_semantic_proof(rescue_case):
    case = rescue_case
    bad_text = "Docs MCP public_tools public_tool are vocabulary labels rather than an inventory of available tools."
    bad = case.raw.model_copy(update={"text": bad_text, "metadata": {
        **case.raw.metadata, "stable_chunk_id": "bad", "char_span": [0, len(bad_text)],
    }})
    case.rows = [bad, case.raw]
    result = case.service.get_project_context(str(case.root), QUESTION)
    assert [chunk.stable_chunk_id for chunk in result.project_docs.results] == ["overview", "tools"]
    assert result.support_decision.answer_supported


def test_rescue_preserves_existing_source_context(rescue_case, monkeypatch):
    case = rescue_case
    route = service_impl.route_initial_stages
    monkeypatch.setattr(service_impl, "route_initial_stages", lambda **kwargs: replace(
        route(**kwargs), use_source_evidence=True,
    ))
    source_item = {
        "source_class": "project_source", "evidence_class": "source_snippet",
        "path": "src/server.py", "content": "def handle_docs(): return local_documents()",
        "token_estimate": 20, "title": "Source boundary", "origin_lane": "source_evidence",
    }
    monkeypatch.setattr(service_impl, "build_project_source_evidence", lambda *args, **kwargs: [source_item])
    repo_item = {**source_item, "path": "src/map.py", "origin_lane": "repo_map"}
    graph_item = {**source_item, "path": "src/graph.py", "origin_lane": "code_graph"}
    monkeypatch.setattr(service_impl, "should_run_repo_map", lambda *args: (True, "test source context"))
    monkeypatch.setattr(service_impl, "build_project_repo_map", lambda *args, **kwargs: [repo_item])
    monkeypatch.setattr(service_impl, "should_run_code_graph", lambda *args, **kwargs: (True, "test code context"))
    monkeypatch.setattr(service_impl, "build_project_code_graph", lambda *args, **kwargs: None)
    monkeypatch.setattr(service_impl, "build_code_graph_context_items", lambda *args, **kwargs: [graph_item])
    result = case.service.get_project_context(str(case.root), QUESTION)
    assert len(case.calls) == 1
    assert any(item.get("stable_chunk_id") == "tools" for item in result.context_pack)
    preserved = next(item for item in result.context_pack if item.get("path") == "src/server.py")
    assert preserved["content"] == source_item["content"]
    assert preserved["content_boundary"]["role"] == "cited_document_data"
    assert {"src/map.py", "src/graph.py"} <= {item.get("path") for item in result.context_pack}


def test_gateway_bounds_documents_and_candidates_and_preserves_lifecycle(rescue_case):
    case = rescue_case
    case.rows = [case.raw.model_copy(update={"metadata": {
        **case.raw.metadata, "stable_chunk_id": f"tools-{index}",
    }}) for index in range(9)]
    result = case.gateway.search_document_components(
        case.observed.project_identity, case.root, ["docs/mcp.md", "README.md"],
        [("tools", "public tools"), ("storage", "persistence")], lifecycle_intent="historical",
    )
    assert len(result.candidates) == 4
    assert result.queried_component_ids == ("tools",)
    assert len(case.calls) == 1
    assert case.calls[0][1]["filters"]["lifecycle_status"] == {"in": ["completed", "historical", "superseded"]}
    overflow = case.gateway.search_document_components(
        case.observed.project_identity, case.root, ["one.md", "two.md", "three.md"], [("tools", "public tools")],
    )
    assert overflow.status == "invalid_request"
    assert len(case.calls) == 1
    context = case.service.get_project_context(str(case.root), QUESTION)
    assert len(context.project_docs.results) == 5
    assert sum("document_local_rescue" in item for item in context.context_pack) == 4
    case.rows = [case.raw, case.raw.model_copy(update={"metadata": {
        **case.raw.metadata, "project_doc_path": "README.md",
    }})]
    distinct_documents = case.gateway.search_document_components(
        case.observed.project_identity, case.root, ["docs/mcp.md", "README.md"], [("tools", "public tools")],
    )
    assert {candidate.project_doc_path for candidate in distinct_documents.candidates} == {
        "docs/mcp.md", "README.md",
    }


def test_exact_path_and_module_scope_survive_rescue(rescue_case, monkeypatch):
    case = rescue_case
    monkeypatch.setattr(service_impl, "extract_document_locator", lambda question: "docs/mcp.md")
    build_requirements = service_impl.build_requirements
    # Supply a semantic contract at the planner boundary; the current explicit-
    # document profile emits path requirements only for this inventory question.
    monkeypatch.setattr(service_impl, "build_requirements", lambda question, **kwargs: build_requirements(
        question, **{**kwargs, "profile": "project_docs_answer"},
    ))
    observed = replace(case.observed, doc_scope="module", module_path="docmancer/docs", module_id="docs")
    case.docs = replace(case.docs, results=[observed, replace(
        case.observed, path="docs/other.md", source=str(case.root / "docs/other.md"),
    )])
    case.rows = [case.raw.model_copy(update={"metadata": {
        **case.raw.metadata, "doc_scope": "module", "module_path": "docmancer/docs", "module_id": "docs",
    }})]
    result = case.service.get_project_context(
        str(case.root), QUESTION, scope="module", module_path="docmancer/docs",
    )
    assert len(case.calls) == 1
    assert case.calls[0][1]["filters"]["project_doc_path"] == {"in": ["docs/mcp.md"]}
    assert {item["path"] for item in result.context_pack} == {"docs/mcp.md"}
    rescued = next(item for item in result.context_pack if item["stable_chunk_id"] == "tools")
    assert rescued["doc_scope"] == "module"
    assert rescued["module_path"] == "docmancer/docs"
    assert rescued["module_id"] == "docs"


def test_only_two_admissible_documents_are_observed(rescue_case):
    case = rescue_case
    case.docs = replace(case.docs, results=[
        replace(case.observed, path="docs/stale.md", stale=True),
        *[replace(case.observed, path=f"docs/doc{index}.md") for index in range(4)],
    ])
    case.rows = []
    case.service.get_project_context(str(case.root), QUESTION, limit=12)
    assert len(case.calls) == 1
    paths = case.calls[0][1]["filters"]["project_doc_path"]["in"]
    assert len(paths) == 2
    assert "docs/stale.md" not in paths


def test_sqlite_dispatcher_rescue_uses_real_chunk_identity_and_filters(rescue_case):
    case = rescue_case
    store = SQLiteStore(case.root / "rescue.db", case.root / "extracted")
    document = f"# Overview\n\n{OVERVIEW}\n\n# Public Tools\n\n{TOOLS}"
    metadata = {
        key: value for key, value in case.raw.metadata.items()
        if key not in {"stable_chunk_id", "parent_logical_id", "char_span", "line_span"}
    }
    metadata.update(
        format="markdown", chunking_schema="parent-child-v1",
        repository_identity=case.observed.project_identity,
        project_doc_content_hash=hashlib.sha256(document.encode()).hexdigest(),
    )
    case.docs = replace(case.docs, results=[replace(
        case.observed, content_hash=metadata["project_doc_content_hash"],
    )])
    store.add_documents([
        Document(source=case.observed.source, content=document, metadata=metadata),
        Document(source="other-project.md", content=TOOLS, metadata={
            **metadata, "project_identity": "other-project", "repository_identity": "other-project",
        }),
        Document(source="superseded.md", content=TOOLS, metadata={
            **metadata, "project_doc_path": "docs/superseded.md",
            "project_doc_lifecycle_status": "superseded", "lifecycle_status": "superseded",
        }),
    ], recreate=True)
    indexed_overview = store.query("local application boundary", limit=1, budget=480, filters={
        "project_identity": case.observed.project_identity,
    })[0]
    case.docs = replace(case.docs, results=[replace(
        case.docs.results[0], content=indexed_overview.text,
        stable_chunk_id=indexed_overview.metadata["stable_chunk_id"],
        parent_logical_id=indexed_overview.metadata["parent_logical_id"],
        display_content_hash=hashlib.sha256(indexed_overview.text.encode()).hexdigest(),
        char_start=indexed_overview.metadata["char_span"][0],
        char_end=indexed_overview.metadata["char_span"][1],
        line_start=indexed_overview.metadata["line_span"][0],
        line_end=indexed_overview.metadata["line_span"][1],
    )])
    config = DocmancerConfig()
    agent = SimpleNamespace(store=store, config=config)
    case.service.facade.agent_gateway = AgentIndexGateway(config, default_agent=agent)
    probe = case.service.facade.agent_gateway.search_document_components(
        case.observed.project_identity, case.root, [case.observed.path],
        [("tools", "Docs MCP public_tools public_tool")], budget=480,
    )
    assert {candidate.chunk.source for candidate in probe.candidates} == {case.observed.source}
    result = case.service.get_project_context(str(case.root), QUESTION)

    assert len(result.project_docs.results) == 2
    rescued = result.project_docs.results[-1]
    assert rescued.source == case.observed.source
    assert rescued.stable_chunk_id not in {None, "overview", "tools"}
    assert rescued.parent_logical_id
    assert rescued.char_end - rescued.char_start == len(rescued.content)
    assert rescued.metadata["document_local_rescue"]["query_plan_hash"]
    assert result.support_decision.answer_supported
    facade = SimpleNamespace(unified_context=UnifiedDocsContextService(SimpleNamespace(
        get_project_context=case.service.get_project_context,
    )))
    payload = call_docs_tool_payload("get_docs_context", {
        "question": QUESTION, "project_path": str(case.root),
    }, facade)
    assert any(TOOLS in source["snippet"] for source in payload["sources"])
    assert "query-original" in payload["missing_query_ids"]
    assert "query-original" not in payload["covered_query_ids"]
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert "document_local_rescue" not in str(payload)


def test_deduplicated_hit_can_prove_another_missing_component(rescue_case, monkeypatch):
    case = rescue_case
    tools_contract = service_impl.build_requirements(QUESTION, profile="project_docs_answer")
    command_question = "Which command starts the Docs MCP server?"
    command_contract = service_impl.build_requirements(command_question, profile="project_docs_answer")
    contract = replace(tools_contract, requirements=(*command_contract, *tools_contract))
    monkeypatch.setattr(service_impl, "build_requirements", lambda *args, **kwargs: contract)

    result = case.service.get_project_context(str(case.root), f"{QUESTION} {command_question}")

    assert len(case.calls) == 2
    assert [chunk.stable_chunk_id for chunk in result.project_docs.results] == ["overview", "tools"]
    provenance = result.project_docs.results[-1].metadata["document_local_rescue"]
    assert provenance["component_id"] == command_contract[0].requirement_id
    assert provenance["qualified_component_ids"] == [tools_contract[0].requirement_id]
    assert {assignment.requirement_id for assignment in result.selection_decision.assignments} == {
        tools_contract[0].requirement_id,
    }
    assert not result.support_decision.answer_supported


@pytest.mark.parametrize("loss", [None, "drop", "clip", "stale", "foreign", "metadata_only", "unsafe", "parent_claim"])
def test_read_and_test_rescue_survives_final_public_projection(rescue_case, monkeypatch, loss):
    case = rescue_case
    question = "What should I read in OrionRepo and what should I test?"
    reading = "For OrionRepo, first read README.md, then read docs/architecture.md."
    testing = "For OrionRepo, run pytest tests/docs before opening a pull request."
    content_hash = hashlib.sha256((reading + "\n" + testing).encode()).hexdigest()
    case.docs = replace(case.docs, query=question, results=[replace(
        case.observed, title="Contributor guide", content=reading,
        content_hash=content_hash, char_end=len(reading),
        display_content_hash=hashlib.sha256(reading.encode()).hexdigest(),
    )])
    case.rows = [case.raw.model_copy(update={"text": testing, "metadata": {
        **case.raw.metadata, "title": "Contributor checks", "stable_chunk_id": "testing",
        "project_doc_content_hash": content_hash,
        "char_span": [len(reading) + 1, len(reading) + 1 + len(testing)],
    }})]
    captured = {}
    project = context_tools.project_docs_context

    def capture_projection(**kwargs):
        projected = project(**kwargs)
        captured.update(projection=projected[0], snapshot=projected[1],
                        diagnostics=kwargs["selection_diagnostics"])
        return projected

    def get_project_context(*args, **kwargs):
        result = case.service.get_project_context(*args, **kwargs)
        rescued = next(item for item in result.context_pack if item.get("stable_chunk_id") == "testing")
        captured["component_id"] = rescued["document_local_rescue"]["qualified_component_ids"][0]
        assert "query-original" not in rescued["retrieval_query_matches"]
        assert result.support_decision.answer_supported
        if loss == "drop":
            result.context_pack.remove(rescued)
        elif loss in {"clip", "metadata_only"}:
            rescued["content"] = "For OrionRepo, run" if loss == "clip" else "# OrionRepo testing pytest"
        elif loss == "stale":
            rescued["freshness"] = "stale"
        elif loss == "foreign":
            rescued["project_identity"] = "other-project"
        elif loss == "unsafe":
            rescued["risk_flags"] = ["unsafe"]
        elif loss == "parent_claim":
            for trace in rescued["retrieval_query_matches"].values():
                trace.update(relation="audited_rewrite", public_parent_query_id="query-original")
        return result

    monkeypatch.setattr(context_tools, "project_docs_context", capture_projection)
    facade = SimpleNamespace(unified_context=UnifiedDocsContextService(SimpleNamespace(
        get_project_context=get_project_context,
    )))
    payload = call_docs_tool_payload("get_docs_context", {
        "question": question, "project_path": str(case.root),
    }, facade)

    assert case.calls, payload
    assert payload["kind"] == "docs_context"
    assert 1 <= len(payload.get("sources", [])) <= 3, (payload, captured)
    assert payload["estimated_tokens"] <= 800
    assert payload["answer_supported"] is False
    assert payload["answer_available"] is False
    assert payload["edit_ready"] is False
    assert "query-original" not in payload["covered_query_ids"]
    assert "query-original" in payload["missing_query_ids"]
    coverage = captured["diagnostics"]["component_coverage"]
    visible = "\n".join(source["snippet"] for source in payload["sources"])
    if loss in {None, "parent_claim"}:
        assert testing in visible
        assert captured["component_id"] in coverage["covered_component_ids"]
        assert coverage["status"] == "full"
    else:
        assert testing not in visible
        assert captured["component_id"] in coverage["missing_component_ids"]
        assert coverage["status"] != "full"
    for private in ("document_local_rescue", "qualified_component_ids", "_component_contract",
                    "retrieval_query_matches", "query_plan_hash", "project_answer:"):
        assert private not in str(payload)
    assert validate_model_visible_projection(
        captured["projection"], snapshot=captured["snapshot"], max_tokens=800,
    ) == []
