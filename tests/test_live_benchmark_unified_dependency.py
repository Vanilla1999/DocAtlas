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

    def prefetch_project_dependency_docs(self, project_path: str, **kwargs):
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
        mode_selected = "dependency" if kwargs.get("mode") == "dependency" else "dependency"
        status = "partial_success" if kwargs.get("mode") == "dependency" else "success"
        return SimpleNamespace(
            status=status,
            mode_selected=mode_selected,
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


def _explicit_dependency_case():
    return BenchmarkCase(
        id="unified_dependency",
        query="How do I use anyhow Context with an explicit dependency request?",
        suite="unified-context",
        library="anyhow",
        ecosystem="rust",
        version="1.0.86",
        mode="dependency",
        expected_source_patterns=["anyhow"],
    )















