from __future__ import annotations

from types import SimpleNamespace

import pytest

from docmancer.docs.project import ProjectMetadataReader
from eval.live_mcp_context7_benchmark import BenchmarkCase, DocAtlasDirectProvider, SourceRef


class FakeDependencyService:
    def __init__(self):
        self.query_calls: list[dict] = []
        self.prefetch_calls: list[dict] = []

    def read_project_metadata(self, project_path: str):
        return ProjectMetadataReader().read(project_path)

    def sync_project_docs(self, project_path: str, *, with_vectors: bool = True):
        return SimpleNamespace(status="success", current_count=1, new_count=0, changed_count=0, sections_indexed=2)

    def prefetch_project_docs(self, project_path: str, **kwargs):
        self.prefetch_calls.append({"project_path": project_path, **kwargs})
        return SimpleNamespace(
            warnings=[],
            results=[SimpleNamespace(
                library_id="rust:anyhow@1.0.86:api",
                status="ready",
                docs_url="https://docs.rs/anyhow/1.0.86/",
                version="1.0.86",
                pages_indexed=3,
                chunks_indexed=7,
            )],
        )

    def get_docs_context(self, question: str, **kwargs):
        self.query_calls.append({"question": question, **kwargs})
        return SimpleNamespace(
            status="success",
            mode_selected="dependency",
            routing={"reason_code": "project_context_auto", "dependency_detected": True},
            requires_confirmation=False,
            contamination={"detected": False},
            deduplication={"dropped_count": 0},
            context_pack=[{
                "source": "https://docs.rs/anyhow/1.0.86/anyhow/trait.Context.html",
                "title": "anyhow::Context",
                "doc_scope": "dependency",
                "content": "The Context trait adds context to Rust errors.",
            }],
        )


def _provider(tmp_path, service=None):
    provider = DocAtlasDirectProvider(project_path=str(tmp_path))
    provider.runtime_dir = tmp_path / "runtime"
    provider.benchmark_mode = "preindexed"
    provider.provider_id = "docatlas_preindexed"
    provider._service = service or FakeDependencyService()
    return provider


def _case():
    return BenchmarkCase(
        id="unified_dependency_auto",
        query="How do I use anyhow Context for the dependency version in this project?",
        suite="unified-context",
        ecosystem="rust",
        mode="auto",
        expected_source_patterns=["anyhow"],
    )


def test_rust_dependency_fixture_contains_manifest_lock_and_readme(tmp_path):
    provider = _provider(tmp_path)
    project = provider._dependency_fixture_project()

    assert (tmp_path / "runtime" / "fixtures" / "unified_dependency_auto" / "Cargo.toml").exists()
    assert (tmp_path / "runtime" / "fixtures" / "unified_dependency_auto" / "Cargo.lock").exists()
    assert (tmp_path / "runtime" / "fixtures" / "unified_dependency_auto" / "README.md").exists()
    assert project.startswith(str(provider.runtime_dir))


def test_rust_dependency_fixture_metadata_detects_anyhow_exact_version(tmp_path):
    provider = _provider(tmp_path)
    project = provider._dependency_fixture_project()

    diag = provider._validate_dependency_fixture(project)

    assert diag.valid is True
    assert diag.ecosystem == "rust"
    assert diag.locked_version == "1.0.86"
    assert diag.exact is True


def test_dependency_auto_preparation_uses_project_dependency_flow(tmp_path):
    service = FakeDependencyService()
    provider = _provider(tmp_path, service)
    project = provider._dependency_fixture_project()

    preindex, dependency_preparation, project_preparation = provider._prepare_dependency_auto_fixture(project)

    assert service.prefetch_calls[0]["include_packages"] == ["anyhow"]
    assert service.prefetch_calls[0]["include_rust"] is True
    assert dependency_preparation["method"] == "prefetch_project_dependency_docs"
    assert preindex.library_id == "rust:anyhow@1.0.86:api"
    assert project_preparation["docs_indexed"] is True


@pytest.mark.asyncio
async def test_dependency_auto_query_does_not_pass_explicit_library(tmp_path):
    service = FakeDependencyService()
    provider = _provider(tmp_path, service)

    result = await provider.query(_case())

    call = service.query_calls[0]
    assert result.status == "success"
    assert call["library"] is None
    assert call["version"] is None
    assert call["mode"] == "auto"
    assert call["project_path"].startswith(str(provider.runtime_dir))


@pytest.mark.asyncio
async def test_dependency_auto_raw_diagnostics_are_available(tmp_path):
    provider = _provider(tmp_path)

    result = await provider.query(_case())

    assert result.dependency_fixture is not None
    assert result.dependency_fixture.valid is True
    assert result.dependency_preparation["canonical_id"] == "rust:anyhow@1.0.86:api"
    assert result.project_preparation["status"] == "success"
    assert result.routing_observed["dependency_detected"] is True


def test_dependency_auto_rejects_project_only_result(tmp_path):
    provider = _provider(tmp_path)
    result = SimpleNamespace(requires_confirmation=False, contamination={"detected": False})

    reason = provider._dependency_auto_failure_reason(
        result=result,
        mode_selected="project",
        sources=[SourceRef(url="README.md", doc_scope="project")],
        exact_version_used="1.0.86",
    )

    assert reason == "dependency_not_detected"


def test_dependency_auto_rejects_latest_when_lockfile_is_exact(tmp_path):
    provider = _provider(tmp_path)
    result = SimpleNamespace(requires_confirmation=False, contamination={"detected": False})

    reason = provider._dependency_auto_failure_reason(
        result=result,
        mode_selected="dependency",
        sources=[SourceRef(url="https://docs.rs/anyhow/latest/anyhow/trait.Context.html", doc_scope="dependency")],
        exact_version_used="latest",
    )

    assert reason == "dependency_version_mismatch"


def test_dependency_auto_rejects_confirmation_required(tmp_path):
    provider = _provider(tmp_path)
    result = SimpleNamespace(requires_confirmation=True, contamination={"detected": False})

    reason = provider._dependency_auto_failure_reason(
        result=result,
        mode_selected="dependency",
        sources=[SourceRef(url="https://docs.rs/anyhow/1.0.86/", doc_scope="dependency")],
        exact_version_used="1.0.86",
    )

    assert reason == "unexpected_confirmation"
