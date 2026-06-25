from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.models import DocsChunk, DocsResult, LibraryInfo, ProjectContextResult, UnifiedDocsContextResult


@dataclass
class FakeMetadata:
    dependencies: list[Any] = field(default_factory=list)


class FakeFacade:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.library_local = True
        self.library_stale = False
        self.dependency_missing = False
        self.project_context = ProjectContextResult(
            project_path="/repo",
            question="q",
            status="success",
            mode="auto",
            context_pack=[{"doc_scope": "project", "source_class": "project_doc", "path": "README.md", "title": "README", "content": "project", "why_selected": "project docs"}],
            trust_contract={"selected": [], "rejected": [], "risky": []},
        )
        self.library_result = DocsResult(
            library_id="python:fastapi@latest:web",
            library="fastapi",
            version="latest",
            topic="Depends",
            refreshed=False,
            stale_before_refresh=False,
            warning=None,
            last_refreshed_at="now",
            source_type="web",
            results=[DocsChunk(title="Depends", content="FastAPI Depends", source="https://fastapi.tiangolo.com/tutorial/dependencies/", url="https://fastapi.tiangolo.com/tutorial/dependencies/", metadata={})],
            resolved_version="latest",
        )
        self.wrote_repo_files = False
        self.prefetched_dependency_docs = False

    def bootstrap_project_docs(self, project_path, question=None):
        self.calls.append(("bootstrap_project_docs", {"project_path": project_path, "question": question}))
        return type("Bootstrap", (), {"requires_confirmation": False, "warnings": [], "reason_code": "project_docs_ready"})()

    def get_project_context(self, project_path, question, **kwargs):
        self.calls.append(("get_project_context", {"project_path": project_path, "question": question, **kwargs}))
        return self.project_context

    def resolve_library(self, library, ecosystem=None, version=None, docs_url=None, docs_url_template=None, source_type=None):
        self.calls.append(("resolve_library", {"library": library, "ecosystem": ecosystem, "version": version, "source_type": source_type}))
        return LibraryInfo(
            library_id=f"{ecosystem or 'python'}:{library}@{version or 'latest'}:{source_type or 'web'}",
            library=library,
            ecosystem=ecosystem,
            version=version or "latest",
            source_type=source_type or "web",
            status="available",
            local=self.library_local,
            stale=self.library_stale,
            last_refreshed_at="now" if self.library_local else None,
        )

    def get_docs(self, library, **kwargs):
        self.calls.append(("get_docs", {"library": library, **kwargs}))
        return self.library_result

    def read_project_metadata(self, project_path):
        return FakeMetadata(dependencies=[type("Dep", (), {"package_name": "riverpod"})()])

    def _project_dependency_docs_state(self, metadata):
        return {"missing": ["riverpod"]} if self.dependency_missing else {"missing": [], "stale": []}

    def prefetch_project_dependency_docs(self, *args, **kwargs):
        self.prefetched_dependency_docs = True


def _service(facade: FakeFacade | None = None) -> UnifiedDocsContextService:
    return UnifiedDocsContextService(facade or FakeFacade())


def _call_names(facade: FakeFacade) -> list[str]:
    return [name for name, _ in facade.calls]


def test_auto_with_project_path_routes_to_project_context():
    facade = FakeFacade()
    result = _service(facade).get_docs_context("How docs work?", project_path="/repo", prepare_project_docs=False)
    assert result.mode_selected == "project"
    assert _call_names(facade) == ["get_project_context"]
    assert facade.calls[0][1]["mode"] == "project-only"


def test_auto_with_library_only_routes_to_library_docs():
    facade = FakeFacade()
    result = _service(facade).get_docs_context("How Depends?", library="fastapi")
    assert result.mode_selected == "library"
    assert "get_docs" in _call_names(facade)
    assert result.source_summary["library"] == 1


def test_auto_with_project_and_library_routes_to_mixed():
    facade = FakeFacade()
    result = _service(facade).get_docs_context("How project uses Depends?", project_path="/repo", library="fastapi", prepare_project_docs=False)
    assert result.mode_selected == "mixed"
    assert result.context_pack[0]["doc_scope"] == "project"
    assert {item["doc_scope"] for item in result.context_pack} == {"project", "library"}


def test_explicit_project_mode_overrides_auto():
    facade = FakeFacade()
    result = _service(facade).get_docs_context("Project?", project_path="/repo", mode="project", prepare_project_docs=False)
    assert result.mode_selected == "project"
    assert facade.calls[0][1]["mode"] == "project-only"


def test_explicit_library_mode_excludes_project_evidence():
    facade = FakeFacade()
    result = _service(facade).get_docs_context("Depends?", project_path="/repo", library="fastapi", mode="library")
    assert result.mode_selected == "library"
    assert "get_project_context" not in _call_names(facade)
    assert all(item["doc_scope"] == "library" for item in result.context_pack)


def test_dependency_mode_requires_project_path():
    result = _service().get_docs_context("Riverpod?", mode="dependency", library="riverpod")
    assert result.status == "invalid_request"
    assert result.reason_code == "project_path_required"


def test_missing_all_targets_returns_invalid_request():
    result = _service().get_docs_context("What docs?")
    assert result.status == "invalid_request"
    assert result.reason_code == "docs_context_target_missing"
    assert result.next_action == {"type": "retry", "arguments_patch": {"project_path": "/path/to/repo"}}


def test_prepare_project_docs_uses_safe_bootstrap():
    facade = FakeFacade()
    _service(facade).get_docs_context("Project?", project_path="/repo")
    assert _call_names(facade)[0] == "bootstrap_project_docs"


def test_prepare_project_docs_does_not_fetch_dependency_docs():
    facade = FakeFacade()
    _service(facade).get_docs_context("Project?", project_path="/repo")
    assert facade.prefetched_dependency_docs is False


def test_prepare_project_docs_does_not_write_repo_files(tmp_path: Path):
    facade = FakeFacade()
    _service(facade).get_docs_context("Project?", project_path=str(tmp_path))
    assert facade.wrote_repo_files is False


def test_missing_library_index_requires_confirmation_when_network_disallowed():
    facade = FakeFacade()
    facade.library_local = False
    result = _service(facade).get_docs_context("Depends?", library="fastapi")
    assert result.status == "confirmation_required"
    assert result.reason_code == "library_docs_network_fetch_required"
    assert result.requires_confirmation is True


def test_allow_network_delegates_to_library_refresh():
    facade = FakeFacade()
    facade.library_local = False
    result = _service(facade).get_docs_context("Depends?", library="fastapi", allow_network=True)
    assert result.status == "success"
    assert "get_docs" in _call_names(facade)


def test_missing_dependency_docs_requires_confirmation():
    facade = FakeFacade()
    facade.dependency_missing = True
    result = _service(facade).get_docs_context("Riverpod autoDispose?", project_path="/repo", mode="dependency", prepare_project_docs=False)
    assert result.status == "confirmation_required"
    assert result.reason_code == "dependency_docs_prefetch_required"


def test_unified_tool_preserves_exact_version_unsupported():
    facade = FakeFacade()
    facade.library_local = False
    facade.library_result = DocsResult(
        library_id="",
        library="fastapi",
        version="0.115.0",
        topic="Depends",
        refreshed=False,
        stale_before_refresh=False,
        warning="unsupported",
        last_refreshed_at=None,
        status="exact_version_not_supported",
        requested_version="0.115.0",
        resolved_version=None,
        diagnostics={"exact_version": {"expected": "0.115.0", "used": None, "match": None, "fallback": False, "reason_code": "versioned_docs_unavailable"}},
    )
    result = _service(facade).get_docs_context("Depends?", library="fastapi", ecosystem="python", version="0.115.0")
    assert result.exact_version["fallback"] is False
    assert result.exact_version["used"] is None


def test_unified_tool_does_not_silently_use_latest():
    facade = FakeFacade()
    facade.library_result = DocsResult(
        library_id="python:fastapi@latest:web",
        library="fastapi",
        version="latest",
        topic="Depends",
        refreshed=False,
        stale_before_refresh=False,
        warning=None,
        last_refreshed_at="now",
        results=[DocsChunk(title="Depends", content="latest", source="https://fastapi.tiangolo.com/", url="https://fastapi.tiangolo.com/", metadata={})],
        requested_version="0.115.0",
        resolved_version="latest",
    )
    result = _service(facade).get_docs_context("Depends?", library="fastapi", ecosystem="unknown", version="0.115.0")
    assert result.exact_version["match"] is False
    assert result.exact_version["fallback"] is True


def test_unified_tool_marks_explicit_latest_fallback_not_exact():
    facade = FakeFacade()
    facade.library_result = DocsResult(
        library_id="",
        library="fastapi",
        version="0.115.0",
        topic="Depends",
        refreshed=False,
        stale_before_refresh=False,
        warning="unsupported",
        last_refreshed_at=None,
        status="exact_version_not_supported",
        requested_version="0.115.0",
        diagnostics={"exact_version": {"expected": "0.115.0", "used": None, "match": None, "fallback": False, "fallback_available": True}},
    )
    result = _service(facade).get_docs_context("Depends?", library="fastapi", ecosystem="python", version="0.115.0", allow_latest_fallback=True)
    assert result.exact_version == {"expected": "0.115.0", "used": "latest", "match": False, "fallback": True, "status": "exact_version_fallback_latest"}


def test_mixed_mode_places_project_evidence_first():
    result = _service(FakeFacade()).get_docs_context("Mixed?", project_path="/repo", library="fastapi", prepare_project_docs=False)
    assert result.context_pack[0]["doc_scope"] == "project"


def test_mixed_mode_preserves_doc_scope():
    result = _service(FakeFacade()).get_docs_context("Mixed?", project_path="/repo", library="fastapi", prepare_project_docs=False)
    assert [item["origin_lane"] for item in result.context_pack] == ["project", "library"]


def test_mixed_mode_deduplicates_sources():
    facade = FakeFacade()
    facade.project_context.context_pack.append({"doc_scope": "project", "source_class": "project_doc", "path": "README.md", "title": "README", "content": "dup"})
    result = _service(facade).get_docs_context("Mixed?", project_path="/repo", library="fastapi", prepare_project_docs=False)
    assert result.contamination["dropped_count"] == 1
    assert "duplicate_source" in result.contamination["reason_codes"]


def test_mixed_mode_keeps_library_chunks_out_of_project_scope():
    result = _service(FakeFacade()).get_docs_context("Mixed?", project_path="/repo", library="fastapi", prepare_project_docs=False)
    library_items = [item for item in result.context_pack if item["origin_lane"] == "library"]
    assert library_items and all(item["doc_scope"] == "library" for item in library_items)


def test_partial_success_when_project_succeeds_and_library_missing():
    facade = FakeFacade()
    facade.library_local = False
    result = _service(facade).get_docs_context("Mixed?", project_path="/repo", library="fastapi", prepare_project_docs=False)
    assert result.status == "partial_success"
    assert result.answer_available is True
    assert result.lanes["library"]["status"] == "confirmation_required"


def test_unified_context_rejects_foreign_project_docs():
    facade = FakeFacade()
    facade.project_context = replace(facade.project_context, context_pack=[{"doc_scope": "foreign", "path": "/other/README.md"}])
    result = _service(facade).get_docs_context("Project?", project_path="/repo", prepare_project_docs=False)
    assert result.status == "not_found"
    assert result.contamination["detected"] is True


def test_unified_context_rejects_wrong_library_id():
    facade = FakeFacade()
    facade.library_result = DocsResult(
        library_id="python:click@latest:web",
        library="click",
        version="latest",
        topic="Depends",
        refreshed=False,
        stale_before_refresh=False,
        warning=None,
        last_refreshed_at="now",
        results=[DocsChunk(title="Click", content="click", source="https://click.palletsprojects.com/", url="https://click.palletsprojects.com/", metadata={})],
    )
    result = _service(facade).get_docs_context("Depends?", library="fastapi")
    assert result.contamination["detected"] is True
    assert "wrong_library_id" in result.contamination["reason_codes"]


def test_empty_library_lane_does_not_fallback_to_project_index():
    facade = FakeFacade()
    facade.library_result = DocsResult(library_id="python:fastapi@latest:web", library="fastapi", version="latest", topic="Depends", refreshed=False, stale_before_refresh=False, warning=None, last_refreshed_at="now", results=[])
    result = _service(facade).get_docs_context("Depends?", library="fastapi")
    assert result.status == "not_found"
    assert "get_project_context" not in _call_names(facade)


def test_compact_response_omits_lane_details():
    result = _service(FakeFacade()).get_docs_context("Depends?", library="fastapi", details=False)
    assert result.lane_details == {}


def test_details_response_includes_lane_details():
    result = _service(FakeFacade()).get_docs_context("Depends?", library="fastapi", details=True)
    assert "library" in result.lane_details


def test_result_contains_mode_selected_and_routing_reason():
    result = _service(FakeFacade()).get_docs_context("Depends?", library="fastapi")
    assert result.mode_selected == "library"
    assert result.routing["reason_code"] == "explicit_library_only"


def test_result_contains_trust_contract_and_next_actions():
    result = _service(FakeFacade()).get_docs_context("Depends?", library="fastapi")
    assert "selected" in result.trust_contract
    assert isinstance(result.next_actions, list)


def test_project_mode_with_library_is_invalid_combination():
    result = _service().get_docs_context("Project?", project_path="/repo", library="fastapi", mode="project")
    assert result.status == "invalid_request"
    assert result.reason_code == "project_mode_cannot_include_library"


def test_result_type_is_typed_model():
    result = _service(FakeFacade()).get_docs_context("Depends?", library="fastapi")
    assert isinstance(result, UnifiedDocsContextResult)
