from __future__ import annotations

import json

import docmancer.docs.application.project_context_service as project_context_module
from docmancer.docs.application.project_context_service import ProjectContextService
from docmancer.docs.domain.retrieval_routing import (
    new_routing_record,
    record_stage,
    route_initial_stages,
    should_run_code_graph,
    should_run_repo_map,
    validate_routing_record,
)
from docmancer.docs.models import DocsChunk, DocsResult, ProjectDocsChunk, ProjectDocsResult, ProjectMetadata


class RoutingFacade:
    def __init__(self, root, *, doc_content="Architecture conventions are documented here."):
        self.root = root
        self.project_calls = 0
        self.project_docs = ProjectDocsResult(
            project_path=str(root),
            query="q",
            results=[ProjectDocsChunk(
                title="Architecture", content=doc_content,
                source=str(root / "ARCHITECTURE.md"), url=None, path="ARCHITECTURE.md",
            )],
        )

    def read_project_metadata(self, project_path):
        return ProjectMetadata(project_path=project_path)

    def get_project_docs(self, project_path, question, **kwargs):
        self.project_calls += 1
        return self.project_docs

    def get_docs(self, library, **kwargs):
        return DocsResult(
            library_id=f"test/{library}/1/api", library=library, version="1", topic=kwargs.get("topic"),
            refreshed=False, stale_before_refresh=False, warning=None, last_refreshed_at=None,
            results=[DocsChunk(title="API", content="Use the exact version API.", source="https://example.test", url="https://example.test")],
        )


def _fail_expensive(*args, **kwargs):
    raise AssertionError("expensive retrieval stage must be skipped")


def test_docs_only_does_not_invoke_source_map_or_code_graph(tmp_path, monkeypatch):
    facade = RoutingFacade(tmp_path)
    monkeypatch.setattr(project_context_module, "build_project_source_evidence", _fail_expensive)
    monkeypatch.setattr(project_context_module, "build_project_repo_map", _fail_expensive)
    monkeypatch.setattr(project_context_module, "build_project_code_graph", _fail_expensive)

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path), "Explain the architecture conventions", mode="project-only",
    )

    routing = result.diagnostics["retrieval_routing"]
    assert facade.project_calls == 1
    assert routing["intent"] == "docs"
    assert routing["stages"]["source_evidence"]["status"] == "skipped"
    assert routing["stages"]["repo_map"]["status"] == "skipped"
    assert routing["stages"]["code_graph"]["status"] == "skipped"
    assert validate_routing_record(routing) == []
    assert "Architecture conventions are documented here" not in json.dumps(routing)


def test_library_only_does_not_invoke_project_cartography(tmp_path, monkeypatch):
    facade = RoutingFacade(tmp_path)
    monkeypatch.setattr(project_context_module, "build_project_source_evidence", _fail_expensive)
    monkeypatch.setattr(project_context_module, "build_project_repo_map", _fail_expensive)
    monkeypatch.setattr(project_context_module, "build_project_code_graph", _fail_expensive)

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path), "How do I call the API?", library="demo", mode="deps-only", allow_network=True,
    )

    routing = result.diagnostics["retrieval_routing"]
    assert routing["intent"] == "api"
    assert facade.project_calls == 0
    assert all(routing["stages"][name]["status"] == "skipped" for name in ("source_evidence", "repo_map", "code_graph"))


def test_single_file_patch_skips_repo_map_and_code_graph_when_source_is_proven(tmp_path, monkeypatch):
    source = tmp_path / "lib" / "foo_service.py"
    source.parent.mkdir()
    source.write_text("class FooService:\n    pass\n", encoding="utf-8")
    facade = RoutingFacade(tmp_path, doc_content="The implementation target is lib/foo_service.py and FooService.")
    monkeypatch.setattr(project_context_module, "build_project_code_graph", _fail_expensive)

    result = ProjectContextService(facade).get_project_context(
        str(tmp_path), "Implement FooService", mode="project-only",
    )

    routing = result.diagnostics["retrieval_routing"]
    assert routing["stages"]["source_evidence"]["status"] == "used"
    assert routing["stages"]["repo_map"]["status"] == "skipped"
    assert routing["stages"]["code_graph"]["status"] == "skipped"


def test_cross_module_signal_runs_code_graph_at_most_once(tmp_path, monkeypatch):
    first = tmp_path / "lib" / "ui" / "foo_screen.py"
    second = tmp_path / "lib" / "services" / "foo_service.py"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("from lib.services.foo_service import FooService\nclass FooScreen: pass\n", encoding="utf-8")
    second.write_text("class FooService: pass\n", encoding="utf-8")
    facade = RoutingFacade(tmp_path, doc_content="FooScreen calls FooService across modules.")
    original = project_context_module.build_project_code_graph
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(project_context_module, "build_project_code_graph", counted)
    result = ProjectContextService(facade).get_project_context(
        str(tmp_path), "Update cross-module references from FooScreen to FooService", mode="project-only",
    )

    assert calls == 1
    assert result.diagnostics["retrieval_routing"]["stages"]["code_graph"]["status"] in {"used", "insufficient"}


def test_router_requires_repo_map_for_unresolved_terms_and_graph_for_cross_module():
    route = route_initial_stages(
        question="Implement FooService", mode="project-only", dependency_requested=False,
        project_doc_items=[{"content": "FooService is the target."}],
    )
    unresolved = [{"evidence_class": "absent_in_source", "path": None, "missing_terms": ["FooService"]}]

    assert should_run_repo_map(route, unresolved)[0] is True
    assert should_run_code_graph(
        route, question="Update cross-module references", source_items=unresolved, repo_map_items=[],
    )[0] is True


def test_create_intent_routes_as_patch_and_stage_overflow_is_visible():
    route = route_initial_stages(
        question="Create FooService", mode="project-only", dependency_requested=False,
        project_doc_items=[{"content": "Architecture conventions."}],
    )
    record = new_routing_record(route, project_docs_used=True, dependency_docs_used=False)
    record_stage(
        record, "repo_map", status="used", reason="fixture",
        items=[{"path": str(index), "blob": "x" * 10_000} for index in range(100)],
    )

    assert route.intent == "patch"
    assert record["stages"]["repo_map"]["budget_exceeded"] is True
    assert record["stages"]["repo_map"]["status"] == "insufficient"
    assert record["stages"]["repo_map"]["observed_item_count"] == 100
    assert validate_routing_record(record) == []
