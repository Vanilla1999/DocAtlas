from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from threading import Event, Thread
import time
from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.agent import DocmancerAgent
from docmancer.docs.models import DocsChunk, DocsResult, DocsTarget, ProjectContextResult, SOURCE_CLASS_PROJECT_FILE
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


class FakeAgent:
    def __init__(self):
        self.add_calls: list[str] = []
        self.add_kwargs: list[dict] = []
        self.query_calls: list[tuple[str, int | None]] = []
        self.config = None

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if self.config is not None:
            store = SQLiteStore(self.config.index.db_path, self.config.index.extracted_dir)
            metadata = dict(kwargs.get("metadata") or {})
            metadata.setdefault("title", "Guide")
            store.add_documents([Document(source=docs_url.rstrip("/") + "/guide", content="# Guide\nUse parametrize for generated cases.", metadata=metadata)], recreate=recreate)
        return 1

    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append((text, budget))
        metadata = dict((self.add_kwargs[-1].get("metadata") if self.add_kwargs else None) or {})
        metadata.setdefault("title", "Parametrize")
        return [
            RetrievedChunk(
                source=(self.add_calls[-1].rstrip("/") + "/guide") if self.add_calls else "https://docs.example.com/guide",
                chunk_index=0,
                text="Use parametrize for generated cases.",
                score=1.0,
                metadata=metadata,
            )
        ]


class FailingAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        if "bad-version" in docs_url:
            self.add_calls.append(docs_url)
            self.add_kwargs.append(kwargs)
            raise RuntimeError("404 docs")
        return super().add(docs_url, recreate=recreate, **kwargs)


class BlockingAgent(FakeAgent):
    def __init__(self):
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if len(self.add_calls) >= 2:
            self.entered.set()
        self.release.wait(timeout=2)
        return 1


class SlowAgent(FakeAgent):
    def __init__(self):
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        self.entered.set()
        self.release.wait(timeout=2)
        return 1


class SlowIndexingAgent(FakeAgent):
    def __init__(self):
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.entered.set()
        self.release.wait(timeout=2)
        return super().add(docs_url, recreate=recreate, **kwargs)


class PageFailingAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if "bad" in docs_url:
            raise RuntimeError("bad page")
        return 1


class ZeroPageAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        return 0


class AlwaysFailingAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        raise RuntimeError("indexer exploded")


class ProgressAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        cb = kwargs.get("progress_callback")
        if cb:
            cb({"phase": "fetching", "message": "Fetching page", "url": docs_url, "fetched_pages": 1, "total_pages": 1})
            cb({"phase": "indexing", "message": "Indexed page", "url": docs_url, "indexed_pages": 1, "total_pages": 1})
        return 1


class MixedVersionFakeAgent(FakeAgent):
    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append((text, budget))
        return [
            RetrievedChunk(
                source="https://pub.dev/documentation/go_router/14.8.1/",
                chunk_index=0,
                text="ShellRoute behavior from 14.8.1.",
                score=1.0,
                metadata={"title": "14 docs", "library_id": "go_router@14.8.1"},
            ),
            RetrievedChunk(
                source="https://pub.dev/documentation/go_router/latest/",
                chunk_index=0,
                text="ShellRoute behavior from latest.",
                score=0.9,
                metadata={"title": "latest docs", "library_id": "go_router@latest"},
            ),
        ]


class MixedRiverpodFakeAgent(FakeAgent):
    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append((text, budget))
        return [
            RetrievedChunk(
                source="https://pub.dev/documentation/riverpod/2.6.1/",
                chunk_index=0,
                text="Riverpod 2 APIs.",
                score=1.0,
                metadata={"title": "v2", "library_id": "riverpod@2.6.1"},
            ),
            RetrievedChunk(
                source="https://pub.dev/documentation/riverpod/3.0.0/",
                chunk_index=0,
                text="Riverpod 3 APIs.",
                score=0.9,
                metadata={"title": "v3", "library_id": "riverpod@3.0.0"},
            ),
        ]


class StaticChunksAgent(FakeAgent):
    def __init__(self, chunks):
        super().__init__()
        self.chunks = chunks

    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append((text, budget))
        return self.chunks


class FailingRefreshStaticChunksAgent(StaticChunksAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        raise RuntimeError("refresh failed")


def _service(tmp_path, monkeypatch, agent: FakeAgent | None = None) -> LibraryDocsService:
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    agent = agent or FakeAgent()
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    def agent_factory(**kwargs):
        agent.config = kwargs.get("config")
        return agent

    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=agent,
        agent_factory=agent_factory,
        job_tracker=DocsJobTracker(),
    )


def _service_with_real_agent(tmp_path, monkeypatch) -> LibraryDocsService:
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def _mark_library_indexed(service: LibraryDocsService, record) -> None:
    config = service._index_config_for(record)
    marker = Path(config.index.extracted_dir) / "chunk.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("indexed chunk", encoding="utf-8")


def _write_library_index(service: LibraryDocsService, record, content: str = "# Guide\nUse this documentation.") -> None:
    config = service._index_config_for(record)
    store = SQLiteStore(config.index.db_path, config.index.extracted_dir)
    store.add_documents([Document(source=record.docs_url_resolved or record.docs_url or record.library_id, content=content, metadata={"library_id": record.library_id})])


def _old_iso(days: int = 31) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def _library_chunk(record, text: str, source_suffix: str = "guide", score: float = 1.0) -> RetrievedChunk:
    root = (record.docs_url_resolved or record.docs_url or "https://docs.example.com/").rstrip("/")
    return RetrievedChunk(
        source=f"{root}/{source_suffix}",
        chunk_index=0,
        text=text,
        score=score,
        metadata={"title": source_suffix, "library_id": record.library_id, "canonical_id": record.canonical_id},
    )


def _flutter_project(tmp_path, *, fvmrc: str = "stable"):
    project = tmp_path / "app"
    project.mkdir()
    (project / ".fvmrc").write_text(fvmrc, encoding="utf-8")
    (project / "pubspec.yaml").write_text(
        """
name: app
dependencies:
  flutter:
    sdk: flutter
  go_router: ^14.0.0
  riverpod: ^2.0.0
""",
        encoding="utf-8",
    )
    (project / "pubspec.lock").write_text(
        """
packages:
  go_router:
    dependency: "direct main"
    description:
      name: go_router
      url: "https://pub.dev"
    source: hosted
    version: "14.8.1"
  riverpod:
    dependency: "direct main"
    description:
      name: riverpod
      url: "https://pub.dev"
    source: hosted
    version: "2.6.1"
sdks:
  dart: ">=3.5.0 <4.0.0"
""",
        encoding="utf-8",
    )
    return project


def _rust_project(tmp_path):
    project = tmp_path / "rust_app"
    project.mkdir()
    (project / "Cargo.toml").write_text(
        """
[package]
name = "rust_app"
version = "0.1.0"

[dependencies]
serde = "1.0"
tokio = { version = "1", features = ["rt"] }
local_crate = { path = "../local_crate" }
""",
        encoding="utf-8",
    )
    (project / "Cargo.lock").write_text(
        """
# This file is automatically @generated by Cargo.

[[package]]
name = "serde"
version = "1.0.228"
source = "registry+https://github.com/rust-lang/crates.io-index"

[[package]]
name = "tokio"
version = "1.48.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
""",
        encoding="utf-8",
    )
    return project


def test_inspect_project_docs_returns_candidates_dependency_sources_and_next_actions(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.project_detected is True
    assert result.project_path == str(project.resolve())
    assert "flutter" in result.project_type
    assert result.project_docs["found"][0]["path"] == "README.md"
    assert result.reason_code == "project_docs_found_not_indexed"
    assert result.next_action == {"type": "sync_project_docs", "tool": "sync_project_docs"}
    assert result.requires_confirmation is False
    assert result.confirmation_reason is None
    assert result.arguments_patch["project_path"] == str(project.resolve())
    assert result.arguments_patch["with_vectors"] is True
    assert "not indexed" in (result.agent_message or "")
    assert result.user_message is None
    assert result.candidate_sources == result.project_docs["found"]
    assert result.project_docs["indexed"] == []
    assert result.project_docs["stale"] == []
    assert result.dependency_sources["manifests_found"] == ["pubspec.yaml"]
    assert result.dependency_sources["lockfiles_found"] == ["pubspec.lock"]
    assert result.dependency_sources["exact_versions_available"] is True
    assert result.dependency_sources["network_fetch_required"] is True
    assert result.dependency_sources["dependency_docs_available"] is True
    assert result.dependency_sources["dependency_docs_prefetched"] is False
    assert result.dependency_sources["dependency_docs_missing_count"] >= 2
    dependency_action = result.dependency_sources["dependency_next_action"]
    assert dependency_action["type"] == "ask_user_to_prefetch_dependency_docs"
    assert dependency_action["tool_after_confirmation"] == "prepare_docs"
    assert dependency_action["alias_tool_after_confirmation"] == "prefetch_project_dependency_docs"
    assert dependency_action["requires_confirmation"] is True
    assert dependency_action["confirmation_reason"] == "network_fetch"
    assert dependency_action["arguments_patch"] == {
        "action": "prefetch_project_dependency_docs",
        "project_path": str(project.resolve()),
        "include_packages": ["go_router", "riverpod"],
    }
    action_tools = [action["tool"] for action in result.recommended_next_actions]
    assert action_tools == ["sync_project_docs", "prefetch_project_docs"]
    assert result.recommended_next_actions[0]["requires_confirmation"] is False
    assert result.recommended_next_actions[1]["requires_confirmation"] is True
    assert "sync_project_docs" in (result.agent_guidance or "")


def test_inspect_project_docs_reports_node_manifest_and_selected_lockfile(tmp_path, monkeypatch):
    project = tmp_path / "node_app"
    project.mkdir()
    (project / "README.md").write_text("# Node app\n\nArchitecture overview.", encoding="utf-8")
    (project / "package.json").write_text(
        '{"packageManager":"pnpm@9.0.0","dependencies":{"react":"^18.0.0"}}',
        encoding="utf-8",
    )
    (project / "pnpm-lock.yaml").write_text(
        "lockfileVersion: '9.0'\nimporters:\n  .:\n    dependencies:\n      react:\n        specifier: ^18.0.0\n        version: 18.3.1\n",
        encoding="utf-8",
    )
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.dependency_sources["manifests_found"] == ["package.json"]
    assert result.dependency_sources["lockfiles_found"] == ["pnpm-lock.yaml"]
    assert result.dependency_sources["exact_versions_available"] is True
    assert result.project_type == ["npm"]
    assert result.dependency_sources["dependency_next_action"]["arguments_patch"] == {
        "action": "prefetch_project_dependency_docs",
        "project_path": str(project.resolve()),
        "include_packages": ["react"],
    }


def test_inspect_project_docs_requires_preflight_for_placeholder_readme_before_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# TODO\n\nPlaceholder docs coming soon.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_action["tool_after_confirmation"] == "sync_project_docs"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.recommended_next_actions[0]["requires_confirmation"] is True
    assert result.recommended_next_actions[0]["after_confirmation"]["tool"] == "sync_project_docs"
    preflight = result.diagnostics["preflight"]
    assert preflight["base_reason_code"] == "project_docs_found_not_indexed"
    assert preflight["requires_confirmation"] is True
    assert {risk["code"] for risk in preflight["risks"]} == {"placeholder_project_doc"}


def test_inspect_project_docs_requires_preflight_for_unsupported_root_doc_before_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    (project / "ARCHITECTURE.docx").write_text("Binary-ish architecture placeholder", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.requires_confirmation is True
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    preflight = result.diagnostics["preflight"]
    assert preflight["base_reason_code"] == "project_docs_found_not_indexed"
    assert preflight["safe_to_sync_without_confirmation"] is False
    assert {risk["code"] for risk in preflight["risks"]} == {"unsupported_project_doc_candidate"}
    assert preflight["risks"][0]["path"] == "ARCHITECTURE.docx"


def test_inspect_project_docs_reports_indexed_and_stale_sources(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOriginal project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    indexed = service.inspect_project_docs(str(project))

    assert indexed.reason_code == "project_docs_ready"
    assert indexed.next_action == {"type": "get_project_context", "tool": "get_project_context"}
    assert indexed.requires_confirmation is False
    assert indexed.project_docs["indexed"][0]["path"] == "README.md"
    assert indexed.project_docs["stale"] == []
    assert indexed.indexed_sources[0]["source_class"] == SOURCE_CLASS_PROJECT_FILE

    readme.write_text("# App\n\nUpdated project docs.", encoding="utf-8")
    stale = service.inspect_project_docs(str(project))

    assert stale.project_docs["stale"][0]["path"] == "README.md"
    assert stale.reason_code == "project_docs_preflight_confirmation_required"
    assert stale.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert stale.requires_confirmation is True
    assert stale.confirmation_reason == "project_docs_preflight"
    assert stale.arguments_patch == {"project_path": str(project.resolve())}
    assert "content_hash_changed" in stale.project_docs["stale"][0]["stale_reasons"]
    assert stale.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert stale.diagnostics["preflight"]["base_reason_code"] == "project_docs_stale"
    assert {risk["code"] for risk in stale.diagnostics["preflight"]["risks"]} == {"stale_project_doc_sources"}


def test_inspect_project_docs_does_not_mark_mtime_only_change_stale(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nStable project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    original = readme.stat().st_mtime_ns
    os.utime(readme, ns=(original + 10_000_000, original + 10_000_000))

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_ready"
    assert result.project_docs["stale"] == []
    assert result.project_docs["indexed"][0]["metadata_drift_reasons"] == ["mtime_changed"]


def test_ingest_project_docs_indexes_only_discovered_candidates_with_metadata(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nIntro", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "testing.md").write_text("# Testing\n\nRun tests.", encoding="utf-8")
    (project / "lib").mkdir()
    (project / "lib" / "main.md").write_text("# Source docs should be ignored", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.ingest_project_docs(str(project), with_vectors=False)

    assert result.status == "success"
    assert result.candidate_count == 2
    assert result.sections_indexed == 2
    assert {item["path"] for item in result.indexed_sources} == {"README.md", "docs/testing.md"}
    assert result.skipped_sources == []
    assert "Indexed 2 project docs" in (result.message or "")

    with service._agent_instance().store._connect() as conn:
        rows = conn.execute("SELECT source, metadata_json FROM sources ORDER BY source").fetchall()
    sources = {Path(row["source"]).relative_to(project).as_posix(): row for row in rows}
    assert set(sources) == {"README.md", "docs/testing.md"}
    metadata = json.loads(sources["README.md"]["metadata_json"])
    assert metadata["source_class"] == "project_file"
    assert metadata["project_docs"] is True
    assert metadata["project_path"] == str(project.resolve())
    assert metadata["project_doc_path"] == "README.md"
    assert metadata["project_doc_reason"] == "root_readme"


def test_ingest_project_docs_reports_missing_candidates_after_verification(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nIntro", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "bad.md").write_bytes(b"# Bad\n\xff")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.ingest_project_docs(str(project), with_vectors=False)

    assert result.status == "partial"
    assert {item["path"] for item in result.indexed_sources} == {"README.md"}
    assert result.missing_sources[0]["path"] == "docs/bad.md"
    assert "Missing 1 project docs" in (result.message or "")


def test_ingest_project_docs_is_idempotent_with_skip_known(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    first = service.ingest_project_docs(str(project), with_vectors=False)
    second = service.ingest_project_docs(str(project), with_vectors=False)

    assert first.status == "success"
    assert first.sections_indexed == 1
    assert second.status == "success"
    assert second.sections_indexed == 0
    assert {item["path"] for item in second.indexed_sources} == {"README.md"}
    assert len(second.skipped_sources) == 1
    assert second.skipped_sources[0]["exception_type"] == "SkippedKnownFile"
    with service._agent_instance().store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == 1


def test_sync_project_docs_backfills_known_file_missing_project_doc_metadata(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nBackfillKnownNeedle project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    agent = service._agent_instance()
    agent.ingest(project, include_exact=("README.md",), with_vectors=False)

    before = service.inspect_project_docs(str(project))
    result = service.sync_project_docs(str(project), with_vectors=False)
    after = service.inspect_project_docs(str(project))

    assert before.reason_code == "project_docs_found_not_indexed"
    assert result.status == "success"
    assert result.current_count == 1
    assert result.missing_sources == []
    assert {item["path"] for item in result.indexed_sources} == {"README.md"}
    assert after.reason_code == "project_docs_ready"

    with agent.store._connect() as conn:
        row = conn.execute("SELECT metadata_json FROM sources WHERE source = ?", (str(project / "README.md"),)).fetchone()
    metadata = json.loads(row["metadata_json"] or "{}")
    assert metadata["project_docs"] is True
    assert metadata["project_doc_path"] == "README.md"


def test_get_project_docs_never_returns_deleted_orphaned_file_content(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCurrent docs.", encoding="utf-8")
    (project / "docs").mkdir()
    deleted = project / "docs" / "old.md"
    deleted.write_text("# Old\n\nOldNeedle should not be returned.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    deleted.unlink()

    result = service.get_project_docs(str(project), "OldNeedle", tokens=1200, limit=5)

    assert result.answer_available is False
    assert result.results == []
    assert result.ignored_sources[0]["path"] == "docs/old.md"
    assert "OldNeedle" not in json.dumps([item.content for item in result.results])


def test_get_project_docs_never_returns_hash_mismatched_stale_content(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOriginalNeedle should not be returned after edits.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.write_text("# App\n\nCurrent docs without the old needle.", encoding="utf-8")

    result = service.get_project_docs(str(project), "OriginalNeedle", tokens=1200, limit=5)

    assert result.answer_available is False
    assert result.results == []
    assert result.stale_sources[0]["path"] == "README.md"
    assert result.stale_sources[0]["stale_reasons"] == ["content_hash_changed"]


def test_get_project_context_never_returns_deleted_orphaned_file_content(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCurrent docs.", encoding="utf-8")
    (project / "docs").mkdir()
    deleted = project / "docs" / "old.md"
    deleted.write_text("# Old\n\nOldContextNeedle should not be returned.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    deleted.unlink()

    result = service.get_project_context(str(project), "OldContextNeedle", tokens=1200, limit=5)

    assert result.answer_available is False
    assert result.context_pack == []
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert "OldContextNeedle" not in json.dumps(result.trust_contract)


def test_get_project_context_requires_preflight_for_placeholder_readme_before_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# TODO\n\nPlaceholder docs coming soon.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_context(str(project), "What is the architecture?", tokens=1200, limit=3)

    assert result.status == "confirmation_required"
    assert result.answer_available is False
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_action["tool_after_confirmation"] == "sync_project_docs"
    assert result.project_docs is not None
    assert result.project_docs.requires_confirmation is True
    assert result.project_docs.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert not any(
        action.get("tool") == "sync_project_docs" and action.get("requires_confirmation") is False
        for action in result.next_actions
    )


def test_get_project_context_requires_preflight_for_unsupported_root_doc(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    (project / "ARCHITECTURE.docx").write_text("Binary-ish architecture placeholder", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_context(str(project), "What is the architecture?", tokens=1200, limit=3)

    assert result.status == "confirmation_required"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.project_docs is not None
    assert result.project_docs.next_actions[0]["risk_codes"] == ["unsupported_project_doc_candidate"]


def test_sync_project_docs_prunes_orphaned_sources_and_indexes_new_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCurrent docs.", encoding="utf-8")
    (project / "docs").mkdir()
    old = project / "docs" / "old.md"
    old.write_text("# Old\n\nOldSyncNeedle should be pruned.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    old.unlink()
    (project / "docs" / "new.md").write_text("# New\n\nNewSyncNeedle should be indexed.", encoding="utf-8")

    result = service.sync_project_docs(str(project), with_vectors=False)

    assert result.status == "success"
    assert result.new_count == 1
    assert result.orphaned_count == 1
    assert result.orphaned_removed == 1
    assert {item["path"] for item in result.indexed_sources} == {"README.md", "docs/new.md"}
    assert result.missing_sources == []
    assert {item["path"] for item in result.removed_sources} == {"docs/old.md"}

    old_query = service.get_project_docs(str(project), "OldSyncNeedle", tokens=1200, limit=5)
    new_query = service.get_project_docs(str(project), "NewSyncNeedle", tokens=1200, limit=5)

    assert old_query.results == []
    assert new_query.answer_available is True
    assert "NewSyncNeedle" in new_query.results[0].content


def test_sync_project_docs_ingests_only_exact_discovered_candidates(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nRoot project overview.", encoding="utf-8")
    eval_readme = project / "eval" / "task_level" / "fixtures" / "README.md"
    eval_readme.parent.mkdir(parents=True)
    eval_readme.write_text("# Eval fixture\n\nShould not be indexed as project docs.", encoding="utf-8")
    example_readme = project / "example" / "README.md"
    example_readme.parent.mkdir()
    example_readme.write_text("# Example\n\nShould not be indexed as project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.sync_project_docs(str(project), with_vectors=False)
    inspect = service.inspect_project_docs(str(project))

    assert result.status == "success"
    assert result.candidate_count == 1
    assert result.current_count == 1
    assert result.sections_indexed == 1
    assert result.missing_sources == []
    assert inspect.reason_code == "project_docs_ready"
    assert inspect.ignored_sources == []
    assert {item["path"] for item in inspect.indexed_sources} == {"README.md"}

    with service._agent_instance().store._connect() as conn:
        rows = conn.execute("SELECT source, metadata_json FROM sources ORDER BY source").fetchall()
    sources = {
        Path(row["source"]).relative_to(project).as_posix(): json.loads(row["metadata_json"] or "{}")
        for row in rows
    }
    assert set(sources) == {"README.md"}
    assert sources["README.md"]["project_doc_path"] == "README.md"


def test_sync_project_docs_converges_on_extensionless_license_candidate(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nRoot project overview.", encoding="utf-8")
    (project / "ARCHITECTURE.md").write_text("# Architecture\n\nSystem overview.", encoding="utf-8")
    (project / "CHANGELOG.md").write_text("# Changelog\n\nInitial release.", encoding="utf-8")
    (project / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    first = service.sync_project_docs(str(project), with_vectors=False)
    second = service.sync_project_docs(str(project), with_vectors=False)
    inspect = service.inspect_project_docs(str(project))

    assert first.status == "success"
    assert first.candidate_count == 4
    assert first.current_count == 4
    assert first.missing_sources == []
    assert second.status == "success"
    assert second.current_count == 4
    assert second.new_count == 0
    assert second.changed_count == 0
    assert second.missing_sources == []
    assert second.orphaned_removed == 0
    assert inspect.reason_code == "project_docs_ready"
    assert {item["path"] for item in inspect.indexed_sources} == {
        "ARCHITECTURE.md",
        "CHANGELOG.md",
        "LICENSE",
        "README.md",
    }


def test_sync_project_docs_reindexes_changed_sources_and_removes_stale_index(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOldChangedNeedle should disappear.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.write_text("# App\n\nNewChangedNeedle should appear.", encoding="utf-8")

    result = service.sync_project_docs(str(project), with_vectors=False)

    assert result.status == "success"
    assert result.changed_count == 1
    assert result.stale_removed == 1
    assert result.orphaned_removed == 0
    assert result.stale_sources == []

    old_query = service.get_project_docs(str(project), "OldChangedNeedle", tokens=1200, limit=5)
    new_query = service.get_project_docs(str(project), "NewChangedNeedle", tokens=1200, limit=5)

    assert old_query.results == []
    assert new_query.answer_available is True
    assert "NewChangedNeedle" in new_query.results[0].content


def test_sync_project_docs_prunes_orphaned_sources_when_all_docs_removed(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nRemoveAllNeedle should be pruned.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.unlink()

    result = service.sync_project_docs(str(project), with_vectors=False)

    assert result.status == "success"
    assert result.candidate_count == 0
    assert result.orphaned_count == 1
    assert result.orphaned_removed == 1
    assert result.current_count == 0
    assert result.indexed_sources == []
    assert {item["path"] for item in result.removed_sources} == {"README.md"}
    with service._agent_instance().store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == 0


def test_inspect_project_docs_reports_needs_sync_for_orphaned_sources(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOrphaned inspect source.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.unlink()

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.ignored_sources[0]["path"] == "README.md"
    assert result.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.diagnostics["preflight"]["base_reason_code"] == "project_docs_stale"
    assert {risk["code"] for risk in result.diagnostics["preflight"]["risks"]} == {"orphaned_project_doc_sources"}


def test_mcp_get_project_docs_returns_compact_response_unless_details_requested(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCompactNeedle project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    compact = handle_project_tool(
        "get_project_docs",
        {"project_path": str(project), "query": "CompactNeedle", "tokens": 1200, "limit": 5},
        service,
    )
    detailed = handle_project_tool(
        "get_project_docs",
        {"project_path": str(project), "query": "CompactNeedle", "tokens": 1200, "limit": 5, "details": True},
        service,
    )

    assert compact is not None
    assert detailed is not None
    assert compact["answer_available"] is True
    assert compact["source_summary"] == {"candidates": 1, "indexed": 1, "stale": 0, "ignored": 0}
    assert "CompactNeedle project docs." in compact["results"][0]["content"]
    assert "candidate_sources" not in compact
    assert "source_state_guidance" not in compact
    assert "candidate_sources" in detailed
    assert "source_state_guidance" in detailed


def test_mcp_project_lifecycle_tools_return_compact_response_unless_details_requested(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nLifecycle compact docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    inspect_compact = handle_project_tool("inspect_project_docs", {"project_path": str(project)}, service)
    inspect_detailed = handle_project_tool("inspect_project_docs", {"project_path": str(project), "details": True}, service)
    sync_compact = handle_project_tool("sync_project_docs", {"project_path": str(project), "with_vectors": False}, service)
    sync_detailed = handle_project_tool("sync_project_docs", {"project_path": str(project), "with_vectors": False, "details": True}, service)
    ingest_compact = handle_project_tool("ingest_project_docs", {"project_path": str(project), "with_vectors": False}, service)
    ingest_detailed = handle_project_tool("ingest_project_docs", {"project_path": str(project), "with_vectors": False, "details": True}, service)
    bootstrap_compact = handle_project_tool("bootstrap_project_docs", {"project_path": str(project), "question": "Lifecycle"}, service)
    bootstrap_detailed = handle_project_tool("bootstrap_project_docs", {"project_path": str(project), "question": "Lifecycle", "details": True}, service)

    assert inspect_compact is not None
    assert inspect_detailed is not None
    assert inspect_compact["source_summary"] == {"candidates": 1, "indexed": 0, "stale": 0, "ignored": 0}
    assert "candidate_sources" not in inspect_compact
    assert "candidate_sources" in inspect_detailed

    assert sync_compact is not None
    assert sync_detailed is not None
    assert sync_compact["summary"]["current"] == 1
    assert "indexed_sources" not in sync_compact
    assert "indexed_sources" in sync_detailed

    assert ingest_compact is not None
    assert ingest_detailed is not None
    assert ingest_compact["source_summary"]["indexed"] == 1
    assert "indexed_sources" not in ingest_compact
    assert "indexed_sources" in ingest_detailed

    assert bootstrap_compact is not None
    assert bootstrap_detailed is not None
    assert bootstrap_compact["status"] == "ready"
    assert "inspect_result" not in bootstrap_compact
    assert "inspect_result" in bootstrap_detailed


def test_project_docs_lifecycle_diagnostics_expose_active_index_and_shadowed_project_config(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nDiagnostics compact docs.", encoding="utf-8")
    (project / "docmancer.yaml").write_text(
        """
index:
  db_path: .docmancer/project-local.db
vector_store:
  api_key_env: SUPER_SECRET_DOCMANCER_TOKEN
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("SUPER_SECRET_DOCMANCER_TOKEN", "super-secret-token-value")
    monkeypatch.setenv("HOME", str(tmp_path / "user-home"))
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "docmancer-home"))
    service = LibraryDocsService(job_tracker=DocsJobTracker())

    inspect = service.inspect_project_docs(str(project))
    inspect_compact = handle_project_tool("inspect_project_docs", {"project_path": str(project)}, service)
    sync = service.sync_project_docs(str(project), with_vectors=False)
    sync_compact = handle_project_tool("sync_project_docs", {"project_path": str(project), "with_vectors": False}, service)

    expected_active_db = str((tmp_path / "user-home" / ".docmancer" / "docmancer.db").resolve())
    expected_project_db = str((project / ".docmancer" / "project-local.db").resolve())
    assert inspect.diagnostics["active_index"]["db_path"] == expected_active_db
    assert inspect.diagnostics["active_index"]["project_path"] == str(project.resolve())
    assert inspect.diagnostics["active_index"]["config_source"] == "default"
    assert inspect.diagnostics["active_index"]["project_local_config"] == {
        "present": True,
        "path": str((project / "docmancer.yaml").resolve()),
        "db_path": expected_project_db,
    }
    assert any(
        warning["code"] == "project_local_config_shadowed"
        for warning in inspect.diagnostics["active_index"]["warnings"]
    )
    assert sync.diagnostics["active_index"]["index_counts"]["sources"] == 1
    assert sync.diagnostics["active_index"]["index_counts"]["sections"] >= 1
    assert inspect_compact["diagnostics"]["active_index"]["db_path"] == expected_active_db
    assert sync_compact["diagnostics"]["active_index"]["db_path"] == expected_active_db
    assert "super-secret-token-value" not in json.dumps(inspect_compact)
    assert "SUPER_SECRET_DOCMANCER_TOKEN" not in json.dumps(inspect_compact)


def test_get_project_context_diagnostics_preserve_query_intent_and_active_index(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nContextDiagnosticsNeedle project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(
        str(project),
        "Where is ContextDiagnosticsNeedle documented?",
        tokens=1200,
        limit=5,
    )
    compact = handle_project_tool(
        "get_project_context",
        {"project_path": str(project), "question": "Where is ContextDiagnosticsNeedle documented?", "tokens": 1200, "limit": 5},
        service,
    )

    assert result.answer_available is True
    assert result.diagnostics["query_intent"]
    assert result.diagnostics["active_index"]["project_path"] == str(project.resolve())
    assert result.diagnostics["active_index"]["db_path"] == str((tmp_path / "docmancer.db").resolve())
    assert compact is not None
    assert compact["diagnostics"]["query_intent"] == result.diagnostics["query_intent"]
    assert compact["diagnostics"]["active_index"]["db_path"] == str((tmp_path / "docmancer.db").resolve())


def test_get_project_context_answers_dart_symbol_docs_with_snippet_evidence(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "lib" / "src").mkdir(parents=True)
    (project / "lib" / "src" / "help_request_module.dart").write_text(
        """
class HelpRequestModule {
  void init(Object config, String mode) {}
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    (project / "ARCHITECTURE.md").write_text(
        """
# Architecture

## Integration

File: `lib/src/help_request_module.dart`.

```text
Host Flutter App
  -> HelpRequestModule.init(config, mode)
  -> HelpRequestNavigator / exported screens
```

Main class: `HelpRequestModule`.
""".strip(),
        encoding="utf-8",
    )
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(
        str(project),
        "HelpRequestModule init",
        tokens=1200,
        limit=5,
        response_style="snippet-first",
    )

    assert result.answer_available is True
    assert result.reason == "trusted_context_available"
    assert result.primary_snippet is not None
    assert "HelpRequestModule.init" in result.primary_snippet["code"]
    assert any(item.get("source_class") == "source_evidence" and item.get("path") == "lib/src/help_request_module.dart" for item in result.context_pack)
    assert not any(action.get("tool") == "code_search" for action in result.next_actions)


def test_ingest_project_docs_no_candidates_returns_no_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service(tmp_path, monkeypatch)

    result = service.ingest_project_docs(str(project), with_vectors=False)

    assert result.status == "no_project_docs"
    assert result.candidate_count == 0
    assert result.sections_indexed == 0
    assert "No project-owned docs candidates" in (result.message or "")


def test_inspect_project_docs_recommends_architecture_bootstrap_when_no_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "no_project_docs"
    assert result.next_action["action"] == "create_reviewable_project_doc"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.next_action["suggested_file"] == "ARCHITECTURE.md"
    assert result.next_action["handled_by"] == "coding_agent"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert "No reviewable project docs" in (result.agent_message or "")
    assert "ARCHITECTURE.md" in (result.user_message or "")
    action = result.recommended_next_actions[-1]
    assert action["action"] == "create_reviewable_project_doc"
    assert action["requires_confirmation"] is True
    assert action["preferred_path"] == "ARCHITECTURE.md"
    assert "ARCHITECTURE.md" in action["suggested_paths"]
    assert [item["tool"] for item in action["after"]] == ["prepare_docs", "get_docs_context"]
    assert "reviewable ARCHITECTURE.md" in (result.agent_guidance or "")


def test_inspect_project_docs_recommends_architecture_when_docs_lack_overview(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "runbooks").mkdir()
    (project / "runbooks" / "deploy.md").write_text("# Deploy\n\nDeployment steps only.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "architecture_doc_creation_recommended"
    assert result.project_docs["high_level_overview_found"] is False
    assert result.next_action["action"] == "create_reviewable_project_doc"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.next_action["suggested_file"] == "ARCHITECTURE.md"
    assert result.next_action["handled_by"] == "coding_agent"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert "high-level project architecture document" in (result.user_message or "")
    action = result.recommended_next_actions[-1]
    assert action["action"] == "create_reviewable_project_doc"
    assert action["preferred_path"] == "ARCHITECTURE.md"
    assert "no high-level architecture or overview" in action["reason"]


def test_project_context_returns_source_grounded_public_docs_handoff(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "runbooks").mkdir()
    (project / "runbooks" / "deploy.md").write_text("# Deploy\n\nDeployment steps only.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(str(project), "Explain the architecture", mode="project-only")

    action = next(item for item in result.next_actions if item.get("action") == "create_reviewable_project_doc")
    assert result.next_action is action
    assert result.requires_confirmation is True
    assert action["documentation_gap"]["evidence_complete"] is True
    assert any("pubspec.yaml" in item["paths"] for item in action["documentation_gap"]["evidence_to_collect"])
    assert [item["tool"] for item in action["after"]] == ["prepare_docs", "get_docs_context"]

    public = service.get_docs_context(
        "Explain the architecture",
        project_path=str(project),
        mode="project",
    )
    assert public.next_action["action"] == "create_reviewable_project_doc"
    assert public.next_action["documentation_gap"]["evidence_complete"] is True
    assert [item["tool"] for item in public.next_action["after"]] == ["prepare_docs", "get_docs_context"]


def test_inspect_project_docs_treats_readme_as_high_level_overview(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_ready"
    assert result.project_docs["high_level_overview_found"] is True


def test_inspect_project_docs_reports_prefetched_dependency_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    now = service._now()
    for package in ("go_router", "riverpod"):
        version = "14.8.1" if package == "go_router" else "2.6.1"
        service.registry.upsert(
            library=package,
            ecosystem="pub",
            version=version,
            source_type="api",
            docs_url=f"https://pub.dev/documentation/{package}/{version}/",
            now=now,
            status="available",
            last_refreshed_at=now,
        )

    result = service.inspect_project_docs(str(project))

    assert result.dependency_sources["dependency_docs_available"] is True
    assert result.dependency_sources["dependency_docs_prefetched"] is True
    assert result.dependency_sources["dependency_docs_prefetched_count"] == 2
    assert result.dependency_sources["dependency_docs_missing_count"] == 0
    assert result.dependency_sources["dependency_next_action"] == {}


def test_bootstrap_project_docs_ingests_existing_docs_and_returns_ready(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nBootstrap ready overview.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.bootstrap_project_docs(str(project), question="How is the app organized?")

    assert result.status == "ready"
    assert result.reason_code == "project_docs_ready"
    assert [action["tool"] for action in result.actions_taken] == [
        "inspect_project_docs",
        "sync_project_docs",
        "inspect_project_docs",
    ]
    assert result.ingest_result is None
    assert result.sync_result is not None
    assert result.sync_result.status == "success"
    assert result.next_action == {"type": "get_project_context", "tool": "get_project_context"}
    assert result.requires_confirmation is False
    assert result.arguments_patch == {"project_path": str(project.resolve()), "question": "How is the app organized?"}


def test_bootstrap_project_docs_stops_before_placeholder_preflight_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# TODO\n\nPlaceholder docs coming soon.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.bootstrap_project_docs(str(project), question="How is the app organized?")

    assert result.status == "confirmation_required"
    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.sync_result is None
    assert [action["tool"] for action in result.actions_taken] == ["inspect_project_docs"]


def test_bootstrap_project_docs_stops_before_repo_write(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.bootstrap_project_docs(str(project), question="Explain the architecture")

    assert result.status == "confirmation_required"
    assert result.reason_code == "no_project_docs"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert [action["tool"] for action in result.actions_taken] == ["inspect_project_docs"]


def test_bootstrap_project_docs_stops_before_dependency_network_fetch(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nBootstrap ready overview.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.bootstrap_project_docs(str(project), question="How should we use go_router?")

    assert result.status == "confirmation_required"
    assert result.reason_code == "dependency_docs_prefetch_confirmation_required"
    assert result.next_action["type"] == "ask_user_to_prefetch_dependency_docs"
    assert result.next_action["tool_after_confirmation"] == "prepare_docs"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "network_fetch"


def test_query_project_docs_filters_by_project_path_and_source_class(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    project_a = _flutter_project(tmp_path / "a")
    project_b = _flutter_project(tmp_path / "b")
    (project_a / "README.md").write_text("# Runbook\n\nSharedTopic alpha migration uses blue toggles.", encoding="utf-8")
    (project_b / "README.md").write_text("# Runbook\n\nSharedTopic beta migration uses red toggles.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project_a), with_vectors=False)
    service.ingest_project_docs(str(project_b), with_vectors=False)

    chunks = service.query_project_docs(str(project_a), "SharedTopic migration toggles", tokens=1200, limit=5)

    assert chunks
    assert all(chunk.metadata["project_path"] == str(project_a.resolve()) for chunk in chunks)
    assert all(chunk.metadata["source_class"] == SOURCE_CLASS_PROJECT_FILE for chunk in chunks)
    assert all(chunk.metadata["project_docs"] is True for chunk in chunks)
    assert any("alpha migration" in chunk.text for chunk in chunks)
    assert not any("beta migration" in chunk.text for chunk in chunks)


def test_project_query_does_not_return_non_project_docs_with_same_terms(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nNeedleTerm project answer lives here.", encoding="utf-8")
    unrelated = tmp_path / "unrelated.md"
    unrelated.write_text("# Architecture\n\nNeedleTerm public docs answer should not leak.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service._agent_instance().ingest(unrelated, with_vectors=False)
    service.ingest_project_docs(str(project), with_vectors=False)

    chunks = service.query_project_docs(str(project), "NeedleTerm Architecture", tokens=1200, limit=5)

    assert chunks
    assert all(chunk.metadata.get("project_path") == str(project.resolve()) for chunk in chunks)
    assert any("project answer" in chunk.text for chunk in chunks)
    assert not any("public docs answer" in chunk.text for chunk in chunks)


def test_get_project_docs_returns_scoped_docs_result(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProjectAnswer uses the local ADR flow.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "ProjectAnswer ADR", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.tool == "get_project_docs"
    assert result.project_path == str(project.resolve())
    assert result.results
    assert result.results[0].source is not None
    assert result.results[0].source_class == SOURCE_CLASS_PROJECT_FILE
    assert result.results[0].path == "README.md"
    assert result.results[0].heading_path == "Architecture"
    assert result.results[0].content_hash is not None
    assert result.results[0].mtime_ns is not None
    assert "ProjectAnswer" in result.results[0].content
    assert result.indexed_sources[0]["path"] == "README.md"
    assert result.next_actions == []


def test_inspect_project_docs_lists_discovered_modules(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App", encoding="utf-8")
    module_docs = project / "packages" / "backend" / "docs"
    module_docs.mkdir(parents=True)
    (project / "packages" / "backend" / "README.md").write_text("# Backend", encoding="utf-8")
    (module_docs / "architecture.md").write_text("# Backend architecture", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    modules = result.project_docs["modules"]
    assert modules == [{
        "module_id": "packages/backend",
        "module_name": "backend",
        "module_path": "packages/backend",
        "module_type": "package",
        "doc_count": 2,
        "docs": ["packages/backend/README.md", "packages/backend/docs/architecture.md"],
    }]


def test_get_project_docs_can_filter_by_module_path(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    backend = project / "packages" / "backend"
    frontend = project / "packages" / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    (backend / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    (frontend / "README.md").write_text("# Frontend\n\nSharedNeedle FrontendOnlyAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "SharedNeedle", module_path="packages/backend", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.results
    assert all(item.module_path == "packages/backend" for item in result.results)
    assert all(item.doc_scope == "module" for item in result.results)
    assert any("BackendOnlyAnswer" in item.content for item in result.results)
    assert not any("FrontendOnlyAnswer" in item.content for item in result.results)


def test_ingested_module_metadata_roundtrips_to_inspect_and_results(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    module = project / "services" / "auth"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Auth service\n\nAuthRoundtripNeedle module docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    ingest = service.ingest_project_docs(str(project), with_vectors=False)
    inspect = service.inspect_project_docs(str(project))
    result = service.get_project_docs(str(project), "AuthRoundtripNeedle", module="auth", tokens=1200, limit=3)

    assert ingest.status == "success"
    assert inspect.project_docs["indexed_modules"] == [{
        "module_id": "services/auth",
        "module_name": "auth",
        "module_path": "services/auth",
        "module_type": "service",
        "doc_count": 1,
        "docs": ["services/auth/README.md"],
    }]
    assert result.status == "success"
    assert result.results
    assert result.results[0].module_id == "services/auth"
    assert result.results[0].module_name == "auth"
    assert result.results[0].module_path == "services/auth"
    assert result.results[0].module_type == "service"
    assert result.indexed_sources[0]["doc_scope"] == "module"
    assert result.indexed_sources[0]["module_path"] == "services/auth"


def test_get_project_docs_can_filter_by_module_name_exact_match(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    backend = project / "packages" / "backend"
    frontend = project / "packages" / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    (backend / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    (frontend / "README.md").write_text("# Frontend\n\nSharedNeedle FrontendOnlyAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "SharedNeedle", module="backend", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.results
    assert all(item.module_path == "packages/backend" for item in result.results)
    assert any("BackendOnlyAnswer" in item.content for item in result.results)
    assert not any("FrontendOnlyAnswer" in item.content for item in result.results)


def test_get_project_docs_returns_structured_module_ambiguity(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    for parent in ("packages", "services"):
        module = project / parent / "auth"
        module.mkdir(parents=True)
        (module / "README.md").write_text(f"# {parent} auth", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_docs(str(project), "auth", module="auth", tokens=1200, limit=3)

    assert result.status == "module_ambiguous"
    assert result.reason_code == "module_ambiguous"
    assert result.answer_available is False
    assert result.next_actions[0]["arguments_patch"] == {"project_path": str(project.resolve())}


def test_get_project_docs_returns_structured_module_not_found(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App", encoding="utf-8")
    module = project / "packages" / "backend"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Backend", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_docs(str(project), "auth", module_path="services/auth", tokens=1200, limit=3)

    assert result.status == "module_not_found"
    assert result.reason_code == "module_not_found"
    assert result.answer_available is False
    assert result.next_action == {"type": "inspect_project_docs", "tool": "inspect_project_docs"}
    assert result.arguments_patch == {"project_path": str(project.resolve())}


def test_get_project_docs_reports_stale_module_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    module = project / "packages" / "backend"
    module.mkdir(parents=True)
    doc = module / "README.md"
    doc.write_text("# Backend\n\nStaleNeedle first version.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    time.sleep(0.01)
    doc.write_text("# Backend\n\nStaleNeedle changed version.", encoding="utf-8")

    result = service.get_project_docs(str(project), "StaleNeedle", module_path="packages/backend", tokens=1200, limit=3)

    assert result.status == "stale"
    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.stale_sources
    assert result.stale_sources[0]["candidate"]["module_path"] == "packages/backend"
    assert result.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"


def test_get_project_docs_project_scope_preserves_backward_compatibility(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nSharedNeedle RootProjectAnswer.", encoding="utf-8")
    module = project / "packages" / "backend"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "SharedNeedle", scope="project", tokens=1200, limit=5)

    assert result.status == "success"
    assert result.results
    assert all(item.doc_scope == "project" for item in result.results)
    assert any("RootProjectAnswer" in item.content for item in result.results)
    assert not any("BackendOnlyAnswer" in item.content for item in result.results)


def test_get_project_context_returns_trust_contract_for_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProjectContextAnswer uses local ADRs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(str(project), "ProjectContextAnswer ADR", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.tool == "get_project_context"
    assert result.project_docs is not None
    assert result.project_docs.results
    assert result.context_pack[0]["source_class"] == "project_doc"
    assert result.context_pack[0]["token_estimate"] > 0
    assert result.metrics["project_result_count"] == 1
    selected = result.trust_contract["sources"]["selected"]
    assert selected[0]["source_class"] == "project_file"
    assert selected[0]["trust_level"] == "trusted"
    assert "trusted_sources" not in result.trust_contract
    assert result.trust_contract["policy"]["direct_webfetch"] == "forbidden"


def test_get_project_context_low_signal_single_token_query_returns_no_results(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProjectContextAnswer uses local ADRs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(str(project), "test", tokens=1200, limit=3)

    assert result.status == "no_results"
    assert result.answer_available is False
    assert result.reason == "no_reliable_context"


def test_get_project_context_preserves_module_metadata_in_pack_and_trust_contract(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    module = project / "services" / "auth"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Auth\n\nContextModuleNeedle AuthContextAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(str(project), "ContextModuleNeedle", module_path="services/auth", scope="module", mode="project-only", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.project_docs is not None
    assert result.project_docs.results[0].module_path == "services/auth"
    assert result.context_pack[0]["doc_scope"] == "module"
    assert result.context_pack[0]["module_id"] == "services/auth"
    assert result.context_pack[0]["module_name"] == "auth"
    assert result.context_pack[0]["module_path"] == "services/auth"
    assert result.context_pack[0]["module_type"] == "service"
    selected = result.trust_contract["sources"]["selected"]
    assert selected[0]["doc_scope"] == "module"
    assert selected[0]["module_path"] == "services/auth"


def test_get_project_context_before_ingest_returns_actionable_remediation(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProject docs exist but are not indexed.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_context(str(project), "Architecture", tokens=1200, limit=3)

    assert result.status == "not_indexed"
    assert result.answer_available is False
    assert result.project_docs is not None
    assert result.project_docs.reason_code == "project_docs_found_not_indexed"
    assert result.next_actions[0]["tool"] == "sync_project_docs"
    assert result.next_actions[0]["arguments_patch"] == {"project_path": str(project.resolve()), "with_vectors": True}
    assert result.trust_contract["next_actions"][0]["tool"] == "sync_project_docs"
    assert "not indexed" in (result.message or "")


def test_bootstrap_project_docs_requires_confirmation_before_refreshing_stale_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# Architecture\n\nOriginal stale acceptance text.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.write_text("# Architecture\n\nFreshAcceptanceNeedle text.", encoding="utf-8")

    bootstrap = service.bootstrap_project_docs(str(project), question="FreshAcceptanceNeedle")

    assert bootstrap.status == "confirmation_required"
    assert bootstrap.reason_code == "project_docs_preflight_confirmation_required"
    assert bootstrap.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert bootstrap.sync_result is None
    assert [action["tool"] for action in bootstrap.actions_taken] == ["inspect_project_docs"]

    sync = service.sync_project_docs(str(project), with_vectors=False)
    context = service.get_project_context(str(project), "FreshAcceptanceNeedle", tokens=1200, limit=3)

    assert sync.status == "success"
    assert context.answer_available is True
    assert context.project_docs is not None
    assert context.project_docs.results
    assert "FreshAcceptanceNeedle" in context.project_docs.results[0].content


def test_get_project_context_can_return_project_and_dependency_context(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Routing\n\nUse AppRouter wrappers with GoRouter.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    monkeypatch.setattr(
        service,
        "get_docs",
        lambda *args, **kwargs: DocsResult(
            library_id="pub:go_router@14.8.1:api",
            library="go_router",
            version="14.8.1",
            topic=kwargs.get("topic"),
            refreshed=False,
            stale_before_refresh=False,
            warning=None,
            last_refreshed_at=None,
            results=[DocsChunk(title="GoRouter", content="Use GoRouter ShellRoute APIs.", source="https://pub.dev/documentation/go_router/14.8.1/", url="https://pub.dev/documentation/go_router/14.8.1/")],
            requested_version="project-version",
            resolved_version="14.8.1",
            version_source="lockfile_exact",
            docs_exactness="exact_version_url",
            docs_binding_source="pub_dartdoc_template",
            confidence="very_high",
        ),
    )

    result = service.get_project_context(str(project), "How should AppRouter use go_router?", tokens=1200, limit=3, allow_network=True)

    assert result.answer_available is True
    assert result.project_docs is not None
    assert result.dependency_docs is not None
    context_source_classes = {item["source_class"] for item in result.context_pack}
    assert {"project_doc", "dependency_doc"}.issubset(context_source_classes)
    assert any(item.get("source_class") == "source_evidence" and item.get("evidence_class") == "absent_in_source" for item in result.context_pack)
    assert result.metrics["project_result_count"] >= 1
    assert result.metrics["dependency_result_count"] >= 1
    selected_classes = {item["source_class"] for item in result.trust_contract["sources"]["selected"]}
    assert selected_classes == {"project_file", "dependency_docs"}


def test_get_project_context_includes_snippet_object_when_metadata_has_code(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Routing\n\nUse AppRouter wrappers.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    monkeypatch.setattr(
        service,
        "get_docs",
        lambda *args, **kwargs: DocsResult(
            library_id="pub:go_router@14.8.1:api",
            library="go_router",
            version="14.8.1",
            topic=kwargs.get("topic"),
            refreshed=False,
            stale_before_refresh=False,
            warning=None,
            last_refreshed_at=None,
            results=[
                DocsChunk(
                    title="GoRouter example",
                    content="Example prose plus code.",
                    source="https://pub.dev/documentation/go_router/14.8.1/",
                    url="https://pub.dev/documentation/go_router/14.8.1/",
                    metadata={"code_snippets": [{"language": "dart", "code": "final router = GoRouter(routes: []);"}]},
                )
            ],
            requested_version="project-version",
            resolved_version="14.8.1",
            version_source="lockfile_exact",
            docs_exactness="exact_version_url",
            docs_binding_source="pub_dartdoc_template",
            confidence="very_high",
        ),
    )

    result = service.get_project_context(str(project), "GoRouter example", library="go_router", allow_network=True)

    dependency_item = next(item for item in result.context_pack if item["source_class"] == "dependency_doc")
    assert dependency_item["snippet"] == {
        "language": "dart",
        "code": "final router = GoRouter(routes: []);",
        "why_relevant": "code example extracted from matching GoRouter example section",
    }
    assert dependency_item["surrounding_context"] == "Example prose plus code."


def test_get_project_context_deps_only_skips_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service(tmp_path, monkeypatch)

    result = service.get_project_context(str(project), "go_router APIs", library="go_router", mode="deps-only")

    assert result.mode == "deps-only"
    assert result.project_docs is None
    assert any(item["reason_code"] == "project_docs_skipped" for item in result.trust_contract["sources"]["risky"])


def test_context_cli_outputs_json_and_explain(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    fake_config = DocmancerConfig()
    fake_result = ProjectContextResult(
        project_path=str(project),
        question="How?",
        trust_contract={"sources": {"selected": [], "rejected": [], "risky": []}, "warnings": [], "next_actions": []},
    )

    with patch("docmancer.cli.commands._load_config", return_value=fake_config), \
         patch("docmancer.docs.service.LibraryDocsService") as service_cls:
        service_cls.return_value.get_project_context.return_value = fake_result
        result = CliRunner().invoke(cli, ["context", str(project), "How?", "--format", "json", "--mode", "project-only"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["trust_contract"]["sources"]["selected"] == []
    service_cls.return_value.get_project_context.assert_called_once()
    assert service_cls.return_value.get_project_context.call_args.kwargs["mode"] == "project-only"


def test_context_cli_explain_outputs_human_readable_trust_contract(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    fake_config = DocmancerConfig()
    fake_result = ProjectContextResult(
        project_path=str(project),
        question="How?",
        trust_contract={
            "selected_sources": [{"source_class": "project_file", "path": "docs/architecture.md", "why_selected": "matched local rule", "freshness": "current"}],
            "rejected_sources": [{"source_class": "dependency_doc", "library": "go_router latest", "reason": "wrong_version_risk"}],
            "risky_sources": [],
            "warnings": [],
            "next_actions": [],
        },
    )

    with patch("docmancer.cli.commands._load_config", return_value=fake_config), \
         patch("docmancer.docs.service.LibraryDocsService") as service_cls:
        service_cls.return_value.get_project_context.return_value = fake_result
        result = CliRunner().invoke(cli, ["context", str(project), "How?", "--explain"])

    assert result.exit_code == 0, result.output
    assert "Trusted context for: How?" in result.output
    assert "[project_file] docs/architecture.md" in result.output
    assert "Rejected / risky:" in result.output
    assert "wrong_version_risk" in result.output


def test_get_project_docs_returns_sync_next_action_when_candidates_not_indexed(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProject docs exist but are not indexed.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_docs(str(project), "Architecture", tokens=1200, limit=3)

    assert result.status == "not_indexed"
    assert result.answer_available is False
    assert result.reason == "project_docs_not_indexed"
    assert result.reason_code == "project_docs_found_not_indexed"
    assert result.next_action == {"type": "sync_project_docs", "tool": "sync_project_docs"}
    assert result.requires_confirmation is False
    assert result.arguments_patch == {"project_path": str(project.resolve()), "with_vectors": True}
    assert result.results == []
    assert result.candidate_sources[0]["path"] == "README.md"
    assert result.next_actions[0]["tool"] == "sync_project_docs"
    assert result.next_actions[0]["arguments_patch"] == {"project_path": str(project.resolve()), "with_vectors": True}


def test_get_project_docs_distinguishes_indexed_no_results_from_not_indexed(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nKnown project docs topic.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "UnrelatedNeedleThatDoesNotExist", tokens=1200, limit=3)

    assert result.status == "no_results"
    assert result.answer_available is False
    assert result.reason == "no_project_docs_results"
    assert result.reason_code == "no_project_docs_results"
    assert result.next_action == {"type": "inspect_project_docs", "tool": "inspect_project_docs"}
    assert result.requires_confirmation is False
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.indexed_sources[0]["path"] == "README.md"
    assert result.next_actions[0]["tool"] == "inspect_project_docs"


def test_get_project_docs_drops_placeholder_license_search_results(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nKnown project docs topic.", encoding="utf-8")
    (project / "LICENSE").write_text("TODO: Put a short description of the license here.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "TODO license", tokens=1200, limit=3)

    assert result.status == "no_results"
    assert result.answer_available is False
    assert result.results == []
    assert not any("TODO: Put a short description" in chunk.content for chunk in result.results)


def test_get_project_docs_reports_stale_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# Architecture\n\nOriginal ProjectStaleAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    readme.write_text("# Architecture\n\nUpdated ProjectStaleAnswer.", encoding="utf-8")
    result = service.get_project_docs(str(project), "ProjectStaleAnswer", tokens=1200, limit=3)

    assert result.status == "stale"
    assert result.reason == "project_docs_stale"
    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_action["tool_after_confirmation"] == "sync_project_docs"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.stale_sources[0]["path"] == "README.md"
    assert result.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_actions[0]["requires_confirmation"] is True


def test_get_project_context_requires_preflight_for_stale_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# Architecture\n\nOriginal ProjectStaleContextAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    readme.write_text("# Architecture\n\nUpdated ProjectStaleContextAnswer.", encoding="utf-8")
    result = service.get_project_context(str(project), "ProjectStaleContextAnswer", tokens=1200, limit=3)

    assert result.status == "stale"
    assert result.answer_available is False
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"


def test_get_project_docs_returns_no_project_docs_next_action(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_docs(str(project), "Architecture", tokens=1200, limit=3)

    assert result.status == "no_project_docs"
    assert result.answer_available is False
    assert result.reason == "no_project_docs"
    assert result.reason_code == "no_project_docs"
    assert result.next_action["action"] == "create_reviewable_project_doc"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.next_action["suggested_file"] == "ARCHITECTURE.md"
    assert result.next_action["handled_by"] == "coding_agent"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.results == []
    assert result.candidate_sources == []
    assert result.next_actions[0]["action"] == "create_reviewable_project_doc"
    assert result.next_actions[0]["preferred_path"] == "ARCHITECTURE.md"
    assert result.next_actions[0]["requires_confirmation"] is True
    assert [item["tool"] for item in result.next_actions[0]["after"]] == ["prepare_docs", "get_docs_context"]
    assert "ARCHITECTURE.md" in (result.message or "")


def test_architecture_bootstrap_file_is_discovered_indexed_and_queryable(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    empty = service.inspect_project_docs(str(project))
    assert empty.candidate_sources == []
    assert empty.recommended_next_actions[-1]["preferred_path"] == "ARCHITECTURE.md"

    (project / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nBootstrapArchitectureAnswer uses repository-local reviewable docs.",
        encoding="utf-8",
    )
    discovered = service.inspect_project_docs(str(project))
    assert discovered.candidate_sources[0]["path"] == "ARCHITECTURE.md"
    assert discovered.candidate_sources[0]["reason"] == "architecture"

    ingest = service.ingest_project_docs(str(project), with_vectors=False)
    assert ingest.status == "success"
    assert ingest.indexed_sources[0]["path"] == "ARCHITECTURE.md"

    answer = service.get_project_docs(str(project), "BootstrapArchitectureAnswer", tokens=1200, limit=3)
    assert answer.status == "success"
    assert answer.results[0].path == "ARCHITECTURE.md"
    assert "BootstrapArchitectureAnswer" in answer.results[0].content


def test_resolve_unknown_without_url_needs_docs_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library("missing-lib")

    assert result.status == "needs_docs_url"
    assert result.library_id is None
    assert result.local is False


def test_unknown_with_url_creates_metadata(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    assert result.library_id == "pytest"
    assert result.docs_url == "https://docs.pytest.org/"
    assert result.status == "available"


def test_versioned_library_uses_canonical_id(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="14.8.1",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
    )

    assert result.library_id == "dart:go_router@14.8.1:api"
    assert result.source_id == "dart:go_router:api"
    assert result.canonical_id == "dart:go_router@14.8.1:api"
    assert result.version == "14.8.1"
    assert result.requested_version == "14.8.1"
    assert result.resolved_version == "14.8.1"
    assert result.version_source == "explicit"
    assert result.version_confidence == "high"
    assert result.version_inferred is False
    assert result.docs_url_resolved == "https://pub.dev/documentation/go_router/14.8.1/"
    assert result.docs_snapshot_exact is True


def test_registry_backfills_identity_for_existing_rows(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
    )

    record = service.registry.get("pub:go_router@latest:api")

    assert record is not None
    assert record.source_id == "pub:go_router:api"
    assert record.canonical_id == "pub:go_router@latest:api"
    assert record.requested_version == "latest"
    assert record.resolved_version == "latest"
    assert record.docs_url_resolved == "https://pub.dev/documentation/go_router/latest/"
    assert record.docs_snapshot_exact is False


def test_hyphen_alias_resolves_to_underscore_package_record(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="14.8.1",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
    )

    result = service.resolve_library("go-router", ecosystem="pub", version="14.8.1")

    assert result.library_id == "dart:go_router@14.8.1:api"
    assert result.library == "go_router"


def test_docs_url_template_registers_version_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="16.2.0",
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.library_id == "dart:go_router@16.2.0:api"
    assert result.docs_url == "https://pub.dev/documentation/go_router/16.2.0/"


def test_refresh_multiple_versions_from_template(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.refresh_docs(
        "go_router",
        ecosystem="pub",
        versions=["14.8.1", "15.0.0", "latest"],
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.status == "updated"
    assert agent.add_calls == [
        "https://pub.dev/documentation/go_router/14.8.1/",
        "https://pub.dev/documentation/go_router/15.0.0/",
        "https://pub.dev/documentation/go_router/latest/",
    ]
    assert service.registry.get("go_router", "pub", "15.0.0").library_id == "dart:go_router@15.0.0:api"


def test_prefetch_docs_delegates_to_batch_refresh(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs(
        "go_router",
        ecosystem="pub",
        versions=["14.8.1", "latest"],
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.status == "updated"
    assert agent.add_calls == [
        "https://pub.dev/documentation/go_router/14.8.1/",
        "https://pub.dev/documentation/go_router/latest/",
    ]


def test_prefetch_docs_defaults_missing_versions_to_latest_with_warning(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs(
        "go_router",
        ecosystem="pub",
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.status == "updated"
    assert "defaulted to latest" in result.message
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/latest/"]


def test_library_prefetch_reports_retryable_network_failure_category(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(agent, "add", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("network unavailable")))

    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
    )

    assert result.status == "failed"
    assert "reason_code=network_unreachable" in result.message
    assert result.preindex["reason_code"] == "network_unreachable"


def test_missing_version_falls_back_to_latest_with_warning(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("go_router", ecosystem="pub", topic="ShellRoute")

    assert result.library_id == "pub:go_router@latest:api"
    assert result.version == "latest"
    assert result.warning == "No version was provided; using latest/default docs."


def test_get_docs_ingests_missing_library_with_url(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("pytest", topic="parametrize", docs_url="https://docs.pytest.org/")

    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert result.refreshed is True
    assert result.results[0].title == "Parametrize"


def test_get_docs_unknown_without_url_asks_for_library_docs_source(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("missing-lib", topic="usage")

    assert result.library_id == ""
    assert result.results == []
    assert result.warning == "library_docs_source_required"
    assert result.warnings == ["library_docs_source_required"]
    assert result.status == "needs_input"
    assert result.decision == "retry_same_tool"
    assert result.reason_code == "library_docs_source_required"
    assert result.diagnostics["legacy_reason_code"] == "needs_docs_url"
    assert "needs_docs_url" in result.diagnostics["reason_aliases"]
    assert result.requires_confirmation is True
    assert result.message
    assert result.next_actions[0]["type"] == "ask_user_for_library_docs_source"
    assert any(option["id"] == "manual_docs_url" for option in result.diagnostics["source_options"])
    assert any(option["id"] == "best_effort_web_discovery" and option["quality_guarantee"] is False for option in result.diagnostics["source_options"])
    assert result.policy["direct_webfetch"] == "discovery_only"
    assert result.next_actions
    assert agent.add_calls == []


def test_get_docs_source_required_returns_retry_contract_with_discovery_candidate(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("mcp", ecosystem="python", topic="tools")

    assert result.status == "needs_input"
    assert result.reason_code == "library_docs_source_required"
    assert result.diagnostics["legacy_reason_code"] == "needs_docs_url"
    assert result.arguments_patch == {
        "docs_url": "https://github.com/modelcontextprotocol/python-sdk",
        "ecosystem": "python",
    }
    assert result.discovery_candidates == result.candidates
    assert result.diagnostics["discovery_candidates"] == result.candidates
    assert result.requires_confirmation is True
    assert result.next_actions[0]["type"] == "ask_user_for_library_docs_source"
    assert result.next_actions[1]["requires_confirmation"] is True
    assert agent.add_calls == []


def test_get_docs_uses_registered_docs_url_without_argument(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="parametrize")

    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert result.library_id == "pytest"
    assert result.warning is None
    assert "needs_docs_url" not in result.warnings


def test_registered_web_docs_without_docs_url_returns_success(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("flutter-adaptive-responsive", docs_url="https://pub.dev/documentation/flutter_adaptive_responsive/latest/")

    result = service.get_docs("flutter-adaptive-responsive", topic="breakpoints")

    assert result.status == "success"
    assert result.tool == "get_library_docs"
    assert result.schema_version == "2.0-mvp"
    assert result.decision == "answer_returned"
    assert result.result is None
    assert result.library_id == "flutter-adaptive-responsive"
    assert result.identity["docs_url"] == "https://pub.dev/documentation/flutter_adaptive_responsive/latest/"
    assert result.identity["docs_url_source"] == "registry"
    assert result.policy["direct_webfetch"] == "forbidden"
    assert result.policy["reason_code"] == "registered_source_exists"


def test_registered_web_docs_does_not_emit_needs_docs_url(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures")

    warning_codes = [item["code"] for item in result.diagnostics["warnings"]]

    assert "needs_docs_url" not in result.warnings
    assert "needs_docs_url" not in warning_codes


def test_registered_web_docs_uses_registry_docs_url(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures")

    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert result.request["effective"]["docs_url"] == "https://docs.pytest.org/"
    assert result.identity["docs_url_source"] == "registry"


def test_registered_web_docs_reports_resolver_diagnostics(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures")

    assert result.diagnostics["resolver"] == {
        "status": "available",
        "selected_by": "registry",
        "stored_locator": "https://docs.pytest.org/",
        "candidate_count": 0,
    }


def test_code_example_blocks_detected_and_ranked_first(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="fastapi",
        ecosystem="python",
        docs_url="https://fastapi.tiangolo.com/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)
    chunks = [
        _library_chunk(record, "Dependency injection overview.", "concepts", 0.9),
        _library_chunk(record, "Use Depends.\n```python\ndef get_db():\n    return Depends(callable)\n```", "depends", 0.8),
    ]
    service.agent_gateway.drop_library_agent(record)
    service.agent_gateway._agents[record.canonical_id] = StaticChunksAgent(chunks)

    result = service.get_docs("fastapi", ecosystem="python", topic="Depends callable injection")

    assert result.results[0].source.endswith("/depends")
    assert result.results[0].metadata["code_snippets"] == 1
    assert result.diagnostics["code_snippets"] == 1


def test_noise_cleaned_from_output_and_anchor_links_stripped(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        docs_url="https://click.palletsprojects.com/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)
    chunks = [_library_chunk(record, "Options [¶]\nCopy code\nUse @click.option() ", "options")]
    service.agent_gateway.drop_library_agent(record)
    service.agent_gateway._agents[record.canonical_id] = StaticChunksAgent(chunks)

    result = service.get_docs("click", ecosystem="python", topic="option")

    assert "[¶]" not in result.results[0].content
    assert "Copy code" not in result.results[0].content
    assert "@click.option()" in result.results[0].content


def test_max_chunks_per_source_enforced_and_unique_sources_reported(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="riverpod",
        ecosystem="pub",
        version="3.0.0",
        docs_url="https://pub.dev/documentation/riverpod/3.0.0/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)
    root = record.docs_url.rstrip("/")
    chunks = [
        RetrievedChunk(source=f"{root}/provider", chunk_index=i, text=f"ref.watch example {i}", score=1.0 - i * 0.01, metadata={"title": f"provider {i}", "library_id": record.library_id, "canonical_id": record.canonical_id})
        for i in range(4)
    ] + [
        _library_chunk(record, "ref.listen example", "listener", 0.7),
        _library_chunk(record, "AsyncValue example", "async-value", 0.6),
    ]
    service.agent_gateway.drop_library_agent(record)
    service.agent_gateway._agents[record.canonical_id] = StaticChunksAgent(chunks)

    result = service.get_docs("riverpod", ecosystem="pub", version="3.0.0", topic="ref watch listen")

    assert sum(1 for item in result.results if item.source == f"{root}/provider") == 2
    assert result.diagnostics["chunks_dropped_for_diversity"] == 2
    assert result.diagnostics["unique_sources@5"] == 3


def test_stale_docs_include_freshness_warning_and_chunk_metadata(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old = _old_iso(45)
    service = _service(tmp_path, monkeypatch)
    record = service.registry.upsert(
        library="pytest",
        ecosystem="python",
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=old,
    )
    _write_library_index(service, record)
    chunks = [_library_chunk(record, "Use fixtures.", "fixtures")]
    service.agent_gateway.drop_library_agent(record)
    service.agent_gateway._agents[record.canonical_id] = FailingRefreshStaticChunksAgent(chunks)

    result = service.get_docs("pytest", ecosystem="python", topic="fixtures")

    assert result.status == "success"
    assert any("stale after" in warning for warning in result.warnings)
    assert result.diagnostics["freshness"]["stale"] is True
    assert result.diagnostics["freshness"]["age_days"] >= 45
    assert result.results[0].metadata["stale"] is True


def test_registered_web_docs_conflicting_input_url_blocks_without_mutation(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures", docs_url="https://example.com/pytest/")

    assert result.status == "needs_input"
    assert result.decision == "retry_same_tool"
    assert result.warning == "docs_url_conflict"
    assert {"code": "docs_url_conflict", "blocking": True} in result.diagnostics["warnings"]
    assert result.policy["direct_webfetch"] == "forbidden"
    assert result.identity["docs_url"] == "https://docs.pytest.org/"
    assert agent.add_calls == []
    assert service.registry.get("pytest").docs_url == "https://docs.pytest.org/"


def test_registered_docs_without_locator_can_accept_input_url(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url=None,
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="available",
    )

    result = service.get_docs("pytest", topic="fixtures", docs_url="https://docs.pytest.org/")

    assert result.status == "success"
    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert service.registry.get("pytest").docs_url == "https://docs.pytest.org/"


def test_success_response_includes_effective_identity(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", version="8.3.4", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", version="8.3.4", topic="fixtures")

    assert result.request["input"]["library"] == "pytest"
    assert result.request["effective"]["version"] == "8.3.4"
    assert result.identity["canonical_id"] == "pytest@8.3.4"
    assert result.identity["library"] == "pytest"
    assert result.identity["version"] == "8.3.4"


def test_success_with_registry_docs_url_has_non_blocking_warning(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures")

    assert {"code": "used_registry_docs_url", "blocking": False} in result.diagnostics["warnings"]


def test_ambiguous_versions_return_candidates(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("go_router", ecosystem="pub", version="14.8.1", docs_url="https://pub.dev/documentation/go_router/14.8.1/")
    service.resolve_library("go_router", ecosystem="pub", version="16.2.0", docs_url="https://pub.dev/documentation/go_router/16.2.0/")

    result = service.get_docs("go-router", ecosystem="pub", topic="ShellRoute")

    assert result.status == "ambiguous"
    assert result.decision == "choose_candidate"
    assert len(result.candidates) == 2
    assert {candidate["canonical_id"] for candidate in result.candidates} == {
        "dart:go_router@14.8.1:api",
        "dart:go_router@16.2.0:api",
    }
    assert result.policy["direct_webfetch"] == "forbidden"
    assert result.diagnostics["resolver"]["candidate_count"] == 2
    assert agent.add_calls == []


def test_ambiguous_versions_include_retry_patches(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("go_router", ecosystem="pub", version="14.8.1", docs_url="https://pub.dev/documentation/go_router/14.8.1/")
    service.resolve_library("go_router", ecosystem="pub", version="16.2.0", docs_url="https://pub.dev/documentation/go_router/16.2.0/")

    result = service.get_docs("go-router", ecosystem="pub", topic="ShellRoute")

    assert all(candidate["arguments_patch"] for candidate in result.candidates)
    assert result.candidates[0]["arguments_patch"]["library"].startswith("dart:go_router@")


def test_exact_version_with_unversioned_url_is_not_exact(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library("pytest", version="8.3.4", docs_url="https://docs.pytest.org/")

    assert result.library_id == "pytest@8.3.4"
    assert result.docs_snapshot_exact is False


def test_get_docs_uses_registry_snapshot_metadata(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", version="8.3.4", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", version="8.3.4", topic="parametrize")

    assert result.library_id == "pytest@8.3.4"
    assert result.requested_version == "8.3.4"
    assert result.resolved_version == "8.3.4"
    assert result.version_source == "explicit"
    assert result.docs_snapshot_exact is False


def test_get_docs_uses_project_package_version_when_omitted(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("go_router", ecosystem="pub", topic="ShellRoute", project_path=str(project))

    assert result.library_id == "dart:go_router@14.8.1:api"
    assert result.version == "14.8.1"
    assert result.docs_snapshot_exact is True
    assert result.requested_version == "14.8.1"
    assert result.version_source == "lockfile_exact"
    assert result.docs_exactness == "exact_snapshot"
    assert result.docs_binding_source == "pub_dartdoc"
    assert result.confidence == "high"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/14.8.1/"]
    record = service.registry.get("dart:go_router@14.8.1:api")
    assert record is not None
    assert record.requested_version == "14.8.1"
    assert record.resolved_version == "14.8.1"
    assert record.version_source == "lockfile_exact"
    assert record.version_inferred is True


def test_get_docs_uses_rust_project_lockfile_and_docs_rs(tmp_path, monkeypatch):
    project = _rust_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("serde", ecosystem="rust", topic="Serialize", project_path=str(project))

    assert result.library_id == "rust:serde@1.0.228:api"
    assert result.version == "1.0.228"
    assert result.requested_version == "1.0"
    assert result.resolved_version == "1.0.228"
    assert result.version_source == "lockfile_exact"
    assert result.docs_snapshot_exact is True
    assert result.docs_exactness == "exact_snapshot"
    assert result.docs_binding_source == "docs_rs"
    assert result.confidence == "high"
    assert agent.add_calls == ["https://docs.rs/serde/1.0.228/"]


def test_get_docs_explicit_version_overrides_project_version(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs(
        "go_router",
        ecosystem="pub",
        version="16.2.0",
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
        topic="ShellRoute",
        project_path=str(project),
    )

    assert result.library_id == "dart:go_router@16.2.0:api"
    assert result.version == "16.2.0"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/16.2.0/"]


def test_flutter_fvmrc_version_uses_stable_channel_id_not_exact_version(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path, fvmrc='{"flutter": "3.24.5", "channel": "stable"}')
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("flutter-api", topic="Navigator", project_path=str(project))

    assert result.library_id == "dart:flutter-api@stable:api"
    assert result.version == "stable"
    assert result.requested_version == "3.24.5"
    assert result.docs_snapshot_exact is False
    assert "not an exact archived snapshot" in result.warning
    assert agent.add_calls == ["https://api.flutter.dev/"]


def test_flutter_main_channel_uses_main_id_and_non_exact_snapshot(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path, fvmrc="main")
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("flutter-api", topic="Navigator", project_path=str(project))

    assert result.library_id == "dart:flutter-api@main:api"
    assert result.version == "main"
    assert result.docs_snapshot_exact is False
    assert agent.add_calls == ["https://main-api.flutter.dev/"]


def test_query_isolation_returns_only_requested_go_router_version(tmp_path, monkeypatch):
    agent = MixedVersionFakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("go_router", ecosystem="pub", version="14.8.1", topic="ShellRoute")

    assert [chunk.content for chunk in result.results] == ["ShellRoute behavior from 14.8.1."]


def test_query_isolation_returns_only_latest_go_router_version(tmp_path, monkeypatch):
    agent = MixedVersionFakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("go_router", ecosystem="pub", version="latest", topic="ShellRoute")

    assert [chunk.content for chunk in result.results] == ["ShellRoute behavior from latest."]


def test_query_isolation_between_two_riverpod_versions(tmp_path, monkeypatch):
    agent = MixedRiverpodFakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="riverpod",
        ecosystem="pub",
        version="2.6.1",
        docs_url="https://pub.dev/documentation/riverpod/2.6.1/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)
    service.registry.upsert(
        library="riverpod",
        ecosystem="pub",
        version="3.0.0",
        docs_url="https://pub.dev/documentation/riverpod/3.0.0/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.get_docs("riverpod", ecosystem="pub", version="2.6.1", topic="Provider")

    assert [chunk.content for chunk in result.results] == ["Riverpod 2 APIs."]


def test_library_id_filter_is_unconditional(tmp_path, monkeypatch):
    service = _service(
        tmp_path,
        monkeypatch,
        StaticChunksAgent(
            [
                RetrievedChunk(
                    source="https://docs.pytest.org/guide",
                    chunk_index=0,
                    text="Unlabeled project/global chunk.",
                    score=1.0,
                    metadata={"title": "Guide"},
                )
            ]
        ),
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("pytest", topic="fixtures")

    assert result.status == "empty_library_index"
    assert result.results == []


def test_post_retrieval_guard_drops_wrong_ecosystem(tmp_path, monkeypatch):
    service = _service(
        tmp_path,
        monkeypatch,
        StaticChunksAgent(
            [
                RetrievedChunk(
                    source="https://docs.python.org/click/guide",
                    chunk_index=0,
                    text="FastAPI chunk in Click query.",
                    score=1.0,
                    metadata={
                        "title": "Wrong ecosystem",
                        "library_id": "python:click@8.1.7:api",
                        "canonical_id": "python:click@8.1.7:api",
                        "ecosystem": "fastapi",
                        "version": "8.1.7",
                    },
                )
            ]
        ),
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        version="8.1.7",
        docs_url="https://docs.python.org/click/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("click", ecosystem="python", version="8.1.7", topic="commands")

    assert result.status == "empty_library_index"
    assert result.results == []


def test_post_retrieval_guard_drops_project_docs(tmp_path, monkeypatch):
    service = _service(
        tmp_path,
        monkeypatch,
        StaticChunksAgent(
            [
                RetrievedChunk(
                    source="/repo/ARCHITECTURE.md",
                    chunk_index=0,
                    text="Project architecture chunk.",
                    score=1.0,
                    metadata={
                        "title": "Architecture",
                        "library_id": "pytest",
                        "canonical_id": "pytest",
                        "project_path": "/repo",
                    },
                )
            ]
        ),
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("pytest", topic="fixtures")

    assert result.status == "empty_library_index"
    assert result.results == []


def test_post_retrieval_guard_empty_result_returns_controlled_error(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch, StaticChunksAgent([]))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.get_docs("pytest", topic="fixtures")

    assert result.status == "empty_library_index"
    assert result.decision == "stop"
    assert result.next_actions == ["Call refresh_library_docs to ingest this library's docs."]


def test_diagnostic_on_filtered_chunks(tmp_path, monkeypatch):
    service = _service(
        tmp_path,
        monkeypatch,
        StaticChunksAgent(
            [
                RetrievedChunk(
                    source="https://docs.pytest.org/good",
                    chunk_index=0,
                    text="Correct pytest chunk.",
                    score=1.0,
                    metadata={"title": "Good", "library_id": "pytest", "canonical_id": "pytest"},
                ),
                RetrievedChunk(
                    source="https://docs.pytest.org/bad",
                    chunk_index=1,
                    text="Unlabeled contaminant.",
                    score=0.9,
                    metadata={"title": "Bad"},
                ),
            ]
        ),
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("pytest", topic="fixtures")

    assert [chunk.content for chunk in result.results] == ["Correct pytest chunk."]
    assert {"code": "cross_source_contamination_filtered", "blocking": False, "dropped": 1} in result.diagnostics["warnings"]


def test_prefetch_project_docs_prefetches_only_selected_packages(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["go_router"],
    )

    assert len(result.results) == 1
    assert result.results[0].library_id == "pub:go_router@14.8.1:api"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/14.8.1/"]
    assert agent.add_kwargs[0]["doc_format"] == "dartdoc"
    assert result.detected_ecosystems == ["flutter", "pub"]
    assert result.resolution_summary["dependencies_seen"] >= 2
    assert result.resolution_summary["exact_versions"] >= 2


def test_prefetch_project_docs_prefetches_rust_docs_rs(tmp_path, monkeypatch):
    project = _rust_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["serde"],
    )

    assert len(result.results) == 1
    assert result.results[0].library_id == "rust:serde@1.0.228:api"
    assert result.results[0].docs_url == "https://docs.rs/serde/1.0.228/"
    assert agent.add_calls == ["https://docs.rs/serde/1.0.228/"]
    assert result.detected_ecosystems == ["rust"]
    assert result.resolution_summary["exact_versions"] == 2


def test_prefetch_project_docs_does_not_treat_unregistered_npm_package_as_pub(tmp_path, monkeypatch):
    project = tmp_path / "node_prefetch"
    project.mkdir()
    (project / "package.json").write_text('{"dependencies":{"react":"^18.0.0"}}', encoding="utf-8")
    (project / "package-lock.json").write_text(
        '{"packages":{"":{"dependencies":{"react":"^18.0.0"}},"node_modules/react":{"version":"18.3.1"}}}',
        encoding="utf-8",
    )
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["react"],
    )

    assert result.results == []
    assert "react: Exact npm version 18.3.1 was found, but no npm documentation source is registered." in result.warnings
    assert agent.add_calls == []


def test_prefetch_project_docs_reuses_registered_exact_npm_target_policy(tmp_path, monkeypatch):
    project = tmp_path / "registered_node_prefetch"
    project.mkdir()
    (project / "package.json").write_text('{"dependencies":{"react":"^18.0.0"}}', encoding="utf-8")
    (project / "package-lock.json").write_text(
        '{"packages":{"":{"dependencies":{"react":"^18.0.0"}},"node_modules/react":{"version":"18.3.1"}}}',
        encoding="utf-8",
    )
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="react",
        ecosystem="npm",
        version="18.3.1",
        docs_url=None,
        docs_url_template="https://docs.example.com/react/{version}/",
        source_type="api",
        now=now,
        status="available",
        target_spec={
            "library": "react",
            "ecosystem": "npm",
            "version": "18.3.1",
            "docs_url_template": "https://docs.example.com/react/{version}/",
            "allowed_domains": ["docs.example.com"],
            "path_prefixes": ["/react/18.3.1/"],
        },
    )

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["react"],
    )

    assert len(result.results) == 1
    assert result.results[0].status == "ready"
    assert result.results[0].library_id == "npm:react@18.3.1:api"
    assert agent.add_calls == ["https://docs.example.com/react/18.3.1/"]


def test_prefetch_project_docs_missing_package_returns_warning(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["missing_pkg"],
    )

    assert result.results == []
    assert "missing_pkg: Package was not found in project lockfiles." in result.warnings
    assert agent.add_calls == []


def test_prefetch_project_docs_async_returns_job_id(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = SlowAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)

    result = service.prefetch_project_docs(str(project), include_flutter=False, include_packages=["go_router"], async_=True)

    assert result.job_id
    assert result.status == "running"
    assert agent.entered.wait(timeout=1)
    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.kind == "prefetch_project_docs"
    agent.release.set()


def test_fresh_library_does_not_refresh(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("pytest", topic="fixtures")

    assert agent.add_calls == []
    assert result.refreshed is False


def test_stale_library_refreshes_automatically(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=_old_iso(),
        status="available",
        last_refreshed_at=_old_iso(),
    )

    result = service.get_docs("pytest", topic="fixtures")

    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert result.stale_before_refresh is True


def test_force_refresh_refreshes_fresh_library(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.get_docs("pytest", topic="fixtures", force_refresh=True)

    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert result.refreshed is True


def test_refresh_force_false_skips_fresh_library(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)

    result = service.refresh_docs("pytest", force=False)

    assert result.status == "skipped"
    assert agent.add_calls == []


def test_refresh_force_false_reingests_fresh_but_empty_library(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.refresh_docs("pytest", force=False)

    assert result.status == "updated"
    assert agent.add_calls == ["https://docs.pytest.org/"]


def test_refresh_zero_pages_returns_empty_index_not_updated(tmp_path, monkeypatch):
    agent = ZeroPageAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=_old_iso(),
    )

    result = service.refresh_docs("pytest", force=False)

    assert result.status == "empty_index"
    assert result.pages_indexed == 0
    assert result.targets_failed == 1
    assert "no_extractable_content" in (result.message or "")
    assert service.inspect_library_docs("pytest").status == "empty_index"


def test_dartdoc_zero_chunk_refresh_fails_safely_without_unrelated_docs(tmp_path, monkeypatch):
    agent = ZeroPageAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="flutter_bloc",
        ecosystem="pub",
        version="9.1.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/flutter_bloc/9.1.1/",
        now=now,
        status="available",
        last_refreshed_at=_old_iso(),
        target_spec={"doc_format": "dartdoc", "max_pages": 500},
    )

    refresh = service.refresh_docs("flutter_bloc", ecosystem="pub", version="9.1.1", source_type="api", force=False)
    result = service.get_docs("flutter_bloc", ecosystem="pub", version="9.1.1", source_type="api", topic="BlocBuilder")

    assert refresh.status == "empty_index"
    assert result.status == "empty_library_index"
    assert result.results == []


def test_force_refresh_is_per_version(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="16.2.0",
        docs_url="https://pub.dev/documentation/go_router/16.2.0/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.refresh_docs("go_router", ecosystem="pub", version="14.8.1", force=True)

    assert result.status == "updated"
    assert result.version == "14.8.1"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/14.8.1/"]


def test_list_marks_stale_libraries(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.registry.upsert(
        library="old",
        ecosystem=None,
        docs_url="https://old.example.com",
        now=_old_iso(),
        status="available",
        last_refreshed_at=_old_iso(),
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="fresh",
        ecosystem=None,
        docs_url="https://fresh.example.com",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    stale = service.list_libraries(stale_only=True)

    assert [item.library_id for item in stale] == ["old"]
    assert stale[0].stale is True


def test_concurrent_get_docs_does_not_duplicate_refresh(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=_old_iso(),
        status="available",
        last_refreshed_at=_old_iso(),
    )

    threads = [
        Thread(target=lambda: service.get_docs("pytest", topic="fixtures"))
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert agent.add_calls == ["https://docs.pytest.org/"]


def test_prefetch_docs_batch_partial_failure_continue_true(tmp_path, monkeypatch):
    agent = FailingAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs(
        "go_router",
        ecosystem="pub",
        versions=["14.8.1", "bad-version", "16.2.0"],
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
        continue_on_error=True,
    )

    assert result.status == "failed"
    assert "updated=2" in result.message
    assert "failed=1" in result.message
    assert agent.add_calls == [
        "https://pub.dev/documentation/go_router/14.8.1/",
        "https://pub.dev/documentation/go_router/bad-version/",
        "https://pub.dev/documentation/go_router/16.2.0/",
    ]


def test_prefetch_docs_batch_aborts_when_continue_false(tmp_path, monkeypatch):
    agent = FailingAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs(
        "go_router",
        ecosystem="pub",
        versions=["14.8.1", "bad-version", "16.2.0"],
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
        continue_on_error=False,
    )

    assert result.status == "aborted"
    assert "updated=1" in result.message
    assert "failed=1" in result.message
    assert agent.add_calls == [
        "https://pub.dev/documentation/go_router/14.8.1/",
        "https://pub.dev/documentation/go_router/bad-version/",
    ]


def test_prefetch_docs_needs_docs_url_aborts_when_continue_false(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs(
        "go_router",
        ecosystem="pub",
        versions=["14.8.1", "16.2.0"],
        continue_on_error=False,
    )

    assert result.status == "aborted"
    assert "needs_docs_url=1" in result.message
    assert agent.add_calls == []


def test_source_type_is_part_of_canonical_target_identity(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    api = service.resolve_library(
        "riverpod",
        ecosystem="pub",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/riverpod/latest/",
    )
    guides = service.resolve_library(
        "riverpod-guides",
        ecosystem="web",
        version="latest",
        source_type="guides",
        docs_url="https://riverpod.dev/docs/",
    )

    assert api.library_id == "dart:riverpod@latest:api"
    assert guides.library_id == "web:riverpod-guides@latest:guides"
    assert api.library_id != guides.library_id


def test_same_library_version_can_have_api_and_guides_targets(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    api = service.resolve_library(
        "riverpod",
        ecosystem="web",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/riverpod/latest/",
    )
    guides = service.resolve_library(
        "riverpod",
        ecosystem="web",
        version="latest",
        source_type="guides",
        docs_url="https://riverpod.dev/docs/",
    )

    assert api.library_id == "web:riverpod@latest:api"
    assert guides.library_id == "web:riverpod@latest:guides"
    assert service.registry.get("riverpod", "web", "latest", "api").docs_url == "https://pub.dev/documentation/riverpod/latest/"
    assert service.registry.get("riverpod", "web", "latest", "guides").docs_url == "https://riverpod.dev/docs/"


def test_concurrent_refresh_different_versions_run_independently(tmp_path, monkeypatch):
    agent = BlockingAgent()
    service = _service(tmp_path, monkeypatch, agent)

    def refresh(version: str) -> None:
        service.refresh_docs(
            "go_router",
            ecosystem="pub",
            version=version,
            docs_url_template="https://pub.dev/documentation/{library}/{version}/",
        )

    threads = [Thread(target=refresh, args=(version,)) for version in ("14.8.1", "16.2.0")]
    for thread in threads:
        thread.start()

    assert agent.entered.wait(timeout=1)
    agent.release.set()
    for thread in threads:
        thread.join()

    assert sorted(agent.add_calls) == [
        "https://pub.dev/documentation/go_router/14.8.1/",
        "https://pub.dev/documentation/go_router/16.2.0/",
    ]


def test_existing_stale_lock_file_does_not_block_refresh(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    info = service.resolve_library("pytest", docs_url="https://docs.pytest.org/")
    lock = service._lock_for(info.library_id)
    Path(lock.lock_file).touch()

    result = service.refresh_docs("pytest")

    assert result.status == "updated"
    assert agent.add_calls == ["https://docs.pytest.org/"]


def test_prefetch_docs_targets_mixed_targets(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "flutter-api",
                "ecosystem": "flutter",
                "version": "stable",
                "source_type": "api",
                "docs_url": "https://api.flutter.dev/",
                "allowed_domains": ["api.flutter.dev"],
            },
            {
                "library": "riverpod-guides",
                "ecosystem": "web",
                "version": "latest",
                "source_type": "guides",
                "seed_urls": [
                    "https://riverpod.dev/docs/introduction/getting_started",
                    "https://riverpod.dev/docs/whats_new",
                ],
                "allowed_domains": ["riverpod.dev"],
                "path_prefixes": ["/docs/"],
                "warnings": ["Rolling guide docs, not an exact package snapshot."],
            },
            {
                "library": "go_router",
                "ecosystem": "pub",
                "version": "latest",
                "source_type": "api",
                "docs_url_template": "https://pub.dev/documentation/{library}/{version}/",
                "allowed_domains": ["pub.dev"],
            },
        ],
        continue_on_error=False,
    )

    assert result.status == "ok"
    assert [item.canonical_id for item in result.results] == [
        "flutter:flutter-api@stable:api",
        "web:riverpod-guides@latest:guides",
        "pub:go_router@latest:api",
    ]
    assert result.results[1].pages_indexed == 2
    assert result.results[1].warnings == ["Rolling guide docs, not an exact package snapshot."]
    assert agent.add_calls == [
        "https://api.flutter.dev/",
        "https://riverpod.dev/docs/introduction/getting_started",
        "https://riverpod.dev/docs/whats_new",
        "https://pub.dev/documentation/go_router/latest/",
    ]
    assert result.pages_indexed == 4
    assert result.pages_failed == 0
    assert result.chunks_indexed == 4
    assert result.targets_completed == 3
    assert result.targets_failed == 0
    assert result.duration_ms >= 0


def test_prefetch_docs_targets_async_returns_job_id_immediately(tmp_path, monkeypatch):
    agent = SlowAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "example-docs",
                "ecosystem": "web",
                "version": "latest",
                "docs_url": "https://example.com/docs/",
                "allowed_domains": ["example.com"],
            }
        ],
        async_=True,
    )

    assert result.job_id
    assert result.status == "running"
    assert result.message == "Started docs prefetch job."
    assert agent.entered.wait(timeout=1)
    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "running"
    agent.release.set()


def test_prepare_library_docs_queues_network_ingest_and_keeps_status_responsive(tmp_path, monkeypatch):
    agent = SlowAgent()
    service = _service(tmp_path, monkeypatch, agent)

    started = time.monotonic()
    payload = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "prefetch_library_docs",
            "library": "example-docs",
            "ecosystem": "web",
            "docs_url": "https://example.com/docs/",
        },
        service,
    )

    assert time.monotonic() - started < 1
    assert payload["status"] == "running"
    assert payload["job_id"]
    assert agent.entered.wait(timeout=1)

    status_started = time.monotonic()
    status = call_docs_tool_payload("docs_status", {"action": "job", "job_id": payload["job_id"]}, service)
    assert time.monotonic() - status_started < 1
    assert status["status"] == "running"
    assert status["job_id"] == payload["job_id"]

    agent.release.set()


def test_library_prefetch_job_cancellation_reaches_terminal_cancelled_state(tmp_path, monkeypatch):
    agent = SlowAgent()
    service = _service(tmp_path, monkeypatch, agent)
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )

    assert agent.entered.wait(timeout=1)
    assert service.cancel_docs_job(result.job_id).status == "cancelling"
    for _ in range(30):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.02)

    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "cancelled"
    assert status.reason_code == "cancelled"
    assert status.retryable is True
    agent.release.set()


def test_cancelled_library_prefetch_restores_index_state_after_inflight_fetch(tmp_path, monkeypatch):
    agent = SlowIndexingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )

    assert agent.entered.wait(timeout=1)
    service.cancel_docs_job(result.job_id)
    for _ in range(30):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.02)
    before = service.registry.get("example-docs", "web", "latest")
    assert before is not None
    assert before.status == "available"

    agent.release.set()
    time.sleep(0.2)
    after = service.registry.get("example-docs", "web", "latest")
    assert after is not None
    assert after.status == "available"
    assert service.library_docs.registry_ops.count_index_entries(after) == (0, 0)


def test_library_prefetch_job_deadline_is_terminal_and_retryable(tmp_path, monkeypatch):
    agent = SlowAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service.library_docs, "_library_job_timeout_seconds", lambda: 0.05)
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )

    assert agent.entered.wait(timeout=1)
    for _ in range(30):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "failed":
            break
        time.sleep(0.02)

    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "failed"
    assert status.reason_code == "job_deadline_exceeded"
    assert status.retryable is True
    agent.release.set()


def test_library_prefetch_job_exposes_structured_retryable_network_error(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(agent, "add", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("network unavailable")))
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )

    for _ in range(30):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "failed":
            break
        time.sleep(0.02)

    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.reason_code == "network_unreachable"
    assert status.retryable is True


def test_partial_library_prefetch_job_never_reports_healthy_reason(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch, FailingAgent())
    result = service.prefetch_docs(
        "go_router",
        ecosystem="pub",
        versions=["bad-version", "16.2.0"],
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
        async_=True,
    )

    for _ in range(30):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status in {"partial", "failed", "succeeded"}:
            break
        time.sleep(0.02)

    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "partial"
    assert status.reason_code == "partial_failure"
    assert status.retryable is False


def test_prefetch_docs_targets_passes_doc_format_to_agent(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "go_router-api",
                "ecosystem": "pub",
                "version": "17.2.3",
                "source_type": "api",
                "doc_format": "dartdoc",
                "seed_urls": [
                    "https://pub.dev/documentation/go_router/17.2.3/go_router/ShellRoute-class.html"
                ],
                "allowed_domains": ["pub.dev"],
                "path_prefixes": ["/documentation/go_router/17.2.3/"],
            }
        ],
    )

    assert result.status == "ok"
    assert agent.add_kwargs[0]["doc_format"] == "dartdoc"
    assert agent.add_kwargs[0]["browser"] is False


def test_docs_job_status_changes_to_succeeded_and_tracks_counts(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "riverpod-guides",
                "ecosystem": "web",
                "version": "latest",
                "source_type": "guides",
                "seed_urls": [
                    "https://riverpod.dev/docs/intro",
                    "https://riverpod.dev/docs/advanced",
                ],
                "allowed_domains": ["riverpod.dev"],
                "path_prefixes": ["/docs/"],
            }
        ],
        async_=True,
    )

    for _ in range(50):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "succeeded":
            break
        time.sleep(0.02)

    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "succeeded"
    assert status.phase == "done"
    assert status.total_targets == 1
    assert status.completed_targets == 1
    assert status.failed_targets == 0
    assert status.current_target == "web:riverpod-guides@latest:guides"
    assert status.total_pages == 2
    assert status.completed_pages == 2
    assert status.failed_pages == 0
    assert status.completed_chunks == 2
    assert status.target_results == [
        {
            "canonical_id": "web:riverpod-guides@latest:guides",
            "status": "ready",
            "pages_indexed": 2,
            "message": None,
        }
    ]


def test_progress_callback_updates_current_url_and_events(tmp_path, monkeypatch):
    agent = ProgressAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "riverpod-guides",
                "ecosystem": "web",
                "version": "latest",
                "source_type": "guides",
                "seed_urls": ["https://riverpod.dev/docs/intro"],
                "allowed_domains": ["riverpod.dev"],
                "path_prefixes": ["/docs/"],
            }
        ],
        async_=True,
    )

    for _ in range(50):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "succeeded":
            break
        time.sleep(0.02)
    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.current_url == "https://riverpod.dev/docs/intro"
    assert status.fetched_pages == 1
    assert status.indexed_pages == 1
    assert any(event.get("phase") == "fetching" for event in status.events)


def test_job_events_are_capped_to_last_50(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    job = service.jobs.create("prefetch_docs_targets")
    for index in range(60):
        service.jobs.append_event(job.job_id, {"phase": "fetching", "message": f"event {index}"})
    status = service.get_docs_job_status(job.job_id)
    assert status is not None
    assert len(status.events) == 50
    assert status.events[0]["message"] == "event 10"


def test_docs_job_failed_page_increments_errors_and_failed_pages(tmp_path, monkeypatch):
    agent = PageFailingAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "bad-guides",
                "ecosystem": "web",
                "source_type": "guides",
                "seed_urls": ["https://example.com/docs/bad"],
                "allowed_domains": ["example.com"],
                "path_prefixes": ["/docs/"],
            }
        ],
        async_=True,
    )

    for _ in range(50):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "failed":
            break
        time.sleep(0.02)

    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "failed"
    assert status.failed_targets == 1
    assert status.failed_pages == 1
    assert status.finished_at is not None
    assert any("bad page" in error for error in status.errors)


def test_background_indexer_exception_marks_job_failed(tmp_path, monkeypatch):
    agent = AlwaysFailingAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "explode",
                "docs_url": "https://example.com/docs/",
                "allowed_domains": ["example.com"],
            }
        ],
        async_=True,
    )

    for _ in range(50):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "failed":
            break
        time.sleep(0.02)

    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "failed"
    assert status.finished_at is not None
    assert status.phase == "done"
    assert any("indexer exploded" in error for error in status.errors)


def test_cancel_docs_job_cancels_between_targets(tmp_path, monkeypatch):
    agent = SlowAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "one",
                "docs_url": "https://example.com/one/",
                "allowed_domains": ["example.com"],
            },
            {
                "library": "two",
                "docs_url": "https://example.com/two/",
                "allowed_domains": ["example.com"],
            },
        ],
        async_=True,
    )

    assert agent.entered.wait(timeout=1)
    cancel = service.cancel_docs_job(result.job_id)
    assert cancel.status == "cancelling"
    agent.release.set()
    for _ in range(50):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.02)

    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "cancelled"
    assert status.finished_at is not None
    assert any("Cancellation requested" in warning for warning in status.warnings)
    assert agent.add_calls == ["https://example.com/one/"]


def test_cancel_docs_job_before_first_target_starts(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    job = service.jobs.create("prefetch_docs_targets")

    cancel = service.cancel_docs_job(job.job_id)
    assert cancel.status == "cancelling"
    result = service._prefetch_docs_targets_sync(
        [
            {
                "library": "one",
                "docs_url": "https://example.com/one/",
                "allowed_domains": ["example.com"],
            }
        ],
        job_id=job.job_id,
    )

    status = service.get_docs_job_status(job.job_id)
    assert result.status == "aborted"
    assert status is not None
    assert status.status == "cancelled"
    assert status.completed_targets == 0
    assert status.finished_at is not None
    assert agent.add_calls == []


def test_list_docs_jobs_filters_by_status(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    running = service.jobs.create("prefetch_docs_targets")
    failed = service.jobs.create("prefetch_docs_targets")
    service.jobs.update(running.job_id, status="running")
    service.jobs.update(failed.job_id, status="failed")

    jobs = service.list_docs_jobs(status="running", limit=10)

    assert running.job_id in {job.job_id for job in jobs}
    assert failed.job_id not in {job.job_id for job in jobs}


def test_list_docs_jobs_limit_returns_newest_first(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    first = service.jobs.create("prefetch_docs_targets")
    time.sleep(0.01)
    second = service.jobs.create("prefetch_docs_targets")
    time.sleep(0.01)
    third = service.jobs.create("prefetch_docs_targets")

    jobs = service.list_docs_jobs(limit=2)

    assert [job.job_id for job in jobs] == [third.job_id, second.job_id]
    assert first.job_id not in {job.job_id for job in jobs}


def test_invalid_job_id_returns_not_found(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    assert service.get_docs_job_status("missing") is None
    cancel = service.cancel_docs_job("missing")
    assert cancel.status == "not_found"


def test_prefetch_docs_targets_docs_url_template_target(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "go_router",
                "ecosystem": "pub",
                "version": "14.8.1",
                "docs_url_template": "https://pub.dev/documentation/{library}/{version}/",
                "allowed_domains": ["pub.dev"],
            }
        ]
    )

    assert result.status == "ok"
    assert result.results[0].canonical_id == "pub:go_router@14.8.1:api"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/14.8.1/"]


def test_prefetch_docs_targets_duplicate_canonical_id(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "go_router",
                "ecosystem": "pub",
                "version": "latest",
                "docs_url": "https://pub.dev/documentation/go_router/latest/",
                "allowed_domains": ["pub.dev"],
            },
            {
                "library": "go_router",
                "ecosystem": "pub",
                "version": "latest",
                "docs_url": "https://pub.dev/documentation/go_router/latest/",
                "allowed_domains": ["pub.dev"],
            },
        ]
    )

    assert result.status == "partial"
    assert result.results[1].status == "failed"
    assert result.results[1].message == "duplicate canonical target id"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/latest/"]


def test_prefetch_docs_targets_invalid_without_url_seed_or_template(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets([{"library": "missing", "ecosystem": "web"}])

    assert result.status == "failed"
    assert result.results[0].message == "target must provide docs_url, docs_url_template, or seed_urls"


def test_prefetch_docs_targets_requires_allowed_domains_for_remote(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets([{"library": "flutter-api", "docs_url": "https://api.flutter.dev/"}])

    assert result.status == "failed"
    assert result.results[0].message == "allowed_domains is required for remote docs targets"


def test_prefetch_docs_targets_rejects_domain_not_allowed(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "flutter-api",
                "docs_url": "https://api.flutter.dev/",
                "allowed_domains": ["docs.flutter.dev"],
            }
        ]
    )

    assert result.status == "failed"
    assert "not in allowed_domains" in result.results[0].message


def test_prefetch_docs_targets_rejects_path_outside_prefix(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "riverpod-guides",
                "ecosystem": "web",
                "source_type": "guides",
                "seed_urls": ["https://riverpod.dev/blog/release"],
                "allowed_domains": ["riverpod.dev"],
                "path_prefixes": ["/docs/"],
            }
        ]
    )

    assert result.status == "failed"
    assert "outside path_prefixes" in result.results[0].message


def test_prefetch_docs_targets_continue_false_aborts(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets(
        [
            {
                "library": "bad",
                "docs_url": "https://bad.example.com/",
                "allowed_domains": ["other.example.com"],
            },
            {
                "library": "go_router",
                "ecosystem": "pub",
                "version": "latest",
                "docs_url_template": "https://pub.dev/documentation/{library}/{version}/",
                "allowed_domains": ["pub.dev"],
            },
        ],
        continue_on_error=False,
    )

    assert result.status == "aborted"
    assert len(result.results) == 1
    assert agent.add_calls == []


def _write_manifest(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_validate_docs_manifest_valid_manifest(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: flutter-api-stable
    library: flutter-api
    ecosystem: flutter
    version: stable
    source_type: api
    docs_url: https://api.flutter.dev/
    allowed_domains:
      - api.flutter.dev
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is True
    assert len(result.targets) == 1
    assert result.targets[0].library == "flutter-api"


def test_validate_docs_manifest_invalid_yaml(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(tmp_path / "docmancer.docs.yaml", "version: [")

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "invalid YAML" in result.errors[0]


def test_validate_docs_manifest_requires_allowed_domains(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: flutter-api-stable
    library: flutter-api
    docs_url: https://api.flutter.dev/
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "allowed_domains is required" in result.errors[0]


def test_validate_docs_manifest_warns_for_pub_package_landing_page(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: go-router-package
    library: go_router
    ecosystem: pub
    version: 14.8.1
    docs_url: https://pub.dev/packages/go_router
    allowed_domains:
      - pub.dev
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is True
    assert result.warnings == [
        "go_router: Prefer exact pub.dev API docs such as https://pub.dev/documentation/go_router/14.8.1/ over package landing pages."
    ]


def test_prefetch_docs_manifest_resolves_project_version_from_pubspec_lock(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)
    manifest = _write_manifest(
        project / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: go-router-project
    library: go_router
    ecosystem: pub
    version: project-version
    source_type: api
    project_version:
      from: pubspec.lock
      package: go_router
      fallback: latest
    docs_url_template: https://pub.dev/documentation/{library}/{version}/
    allowed_domains:
      - pub.dev
""",
    )

    result = service.prefetch_docs_manifest(str(manifest), project_path=str(project))

    assert result.status == "ok"
    assert result.results[0].canonical_id == "pub:go_router@14.8.1:api"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/14.8.1/"]


def test_prefetch_docs_manifest_project_version_falls_back_latest(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = _write_manifest(
        project / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: missing-project
    library: missing_pkg
    ecosystem: pub
    version: project-version
    source_type: api
    project_version:
      from: pubspec.lock
      package: missing_pkg
      fallback: latest
    docs_url_template: https://pub.dev/documentation/{library}/{version}/
    allowed_domains:
      - pub.dev
""",
    )

    result = service.prefetch_docs_manifest(str(manifest), project_path=str(project))

    assert result.status == "ok"
    assert result.results[0].canonical_id == "pub:missing_pkg@latest:api"
    assert "missing_pkg: Package was not found" in result.warnings[0]


def test_prefetch_docs_manifest_target_selection_by_id(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)
    manifest = _write_manifest(
        tmp_path / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: flutter-api-stable
    library: flutter-api
    ecosystem: flutter
    version: stable
    docs_url: https://api.flutter.dev/
    allowed_domains: [api.flutter.dev]
  - id: go-router-latest
    library: go_router
    ecosystem: pub
    version: latest
    docs_url_template: https://pub.dev/documentation/{library}/{version}/
    allowed_domains: [pub.dev]
""",
    )

    result = service.prefetch_docs_manifest(str(manifest), targets=["go-router-latest"])

    assert result.status == "ok"
    assert [item.canonical_id for item in result.results] == ["pub:go_router@latest:api"]
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/latest/"]


def test_validate_docs_manifest_duplicate_target_ids(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: duplicate
    library: one
    docs_url: https://one.example.com/
    allowed_domains: [one.example.com]
  - id: duplicate
    library: two
    docs_url: https://two.example.com/
    allowed_domains: [two.example.com]
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "duplicate target id: duplicate" in result.errors


def test_validate_docs_manifest_invalid_source_type(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: bad-source
    library: flutter-api
    source_type: blog
    docs_url: https://api.flutter.dev/
    allowed_domains: [api.flutter.dev]
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "invalid source_type" in result.errors[0]


def test_validate_docs_manifest_rejects_path_prefix_escape(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = _write_manifest(
        tmp_path / "docmancer.docs.yaml",
        """
version: 1
targets:
  - id: riverpod-guides
    library: riverpod-guides
    ecosystem: web
    version: latest
    source_type: guides
    seed_urls:
      - https://riverpod.dev/blog/release
    allowed_domains:
      - riverpod.dev
    path_prefixes:
      - /docs/
""",
    )

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert "outside path_prefixes" in result.errors[0]


def test_inspect_library_docs_ready_target(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.inspect_library_docs("pub:go_router@14.8.1:api")

    assert result.canonical_id == "pub:go_router@14.8.1:api"
    assert result.source_id == "pub:go_router:api"
    assert result.status == "empty_index"
    assert result.library == "go_router"
    assert result.docs_url_resolved == "https://pub.dev/documentation/go_router/14.8.1/"
    assert result.docs_snapshot_exact is True
    assert result.requested_version == "14.8.1"
    assert result.resolved_version == "14.8.1"
    assert result.version_source == "explicit"
    assert result.version_confidence == "high"
    assert result.version_inferred is False
    assert result.stale is False
    assert result.reason_code == "empty_index"
    assert result.pages == 0
    assert result.chunks == 0


def test_inspect_on_empty_index_reports_empty_index_state(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        version="8.1.7",
        source_type="api",
        docs_url="https://click.palletsprojects.com/en/8.1.x/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    config = service._index_config_for(record)
    SQLiteStore(config.index.db_path, config.index.extracted_dir)

    result = service.inspect_library_docs("python:click@8.1.7:api")

    assert result.status == "empty_index"
    assert result.reason_code == "empty_index"
    assert result.pages == 0
    assert result.chunks == 0


def test_list_libraries_shows_pages_and_chunks(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        version="8.1.7",
        source_type="api",
        docs_url="https://click.palletsprojects.com/en/8.1.x/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)

    result = service.list_libraries()

    assert result[0].status == "indexed"
    assert result[0].reason_code == "healthy"
    assert result[0].pages == 1
    assert result[0].chunks == 1


def test_list_libraries_exposes_removable_canonical_id(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
    )

    result = service.list_libraries()

    assert result[0].library_id == "pub:go_router@14.8.1:api"
    assert result[0].canonical_id == "pub:go_router@14.8.1:api"
    assert result[0].source_id == "pub:go_router:api"


def test_stale_index_triggers_warning_not_empty_state(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        version="8.1.7",
        source_type="api",
        docs_url="https://click.palletsprojects.com/en/8.1.x/",
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="available",
        last_refreshed_at=_old_iso(),
    )
    _write_library_index(service, record)

    result = service.inspect_library_docs("python:click@8.1.7:api")

    assert result.status == "stale"
    assert result.reason_code == "stale"
    assert result.stale is True
    assert result.pages == 1
    assert result.chunks == 1


def test_remove_library_docs_exact_canonical_id_only(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
    )
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
    )

    result = service.remove_library_docs("pub:go_router@14.8.1:api")

    assert result.removed is True
    assert service.registry.get("pub:go_router@14.8.1:api") is None
    assert service.registry.get("pub:go_router@latest:api") is not None


def test_remove_api_does_not_remove_guides(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="riverpod",
        ecosystem="web",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/riverpod/latest/",
        now=now,
        status="available",
    )
    service.registry.upsert(
        library="riverpod",
        ecosystem="web",
        version="latest",
        source_type="guides",
        docs_url="https://riverpod.dev/docs/",
        now=now,
        status="available",
    )

    service.remove_library_docs("web:riverpod@latest:api")

    assert service.registry.get("web:riverpod@latest:api") is None
    assert service.registry.get("web:riverpod@latest:guides") is not None


def test_prune_library_docs_dry_run_removes_nothing(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=_old_iso(120),
        status="available",
        last_refreshed_at=_old_iso(120),
    )

    result = service.prune_library_docs(library="go_router", older_than_days=90, dry_run=True)

    assert result.would_remove == ["pub:go_router@14.8.1:api"]
    assert service.registry.get("pub:go_router@14.8.1:api") is not None


def test_prune_library_docs_keep_versions_respected(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    for version in ["14.8.1", "17.2.3"]:
        service.registry.upsert(
            library="go_router",
            ecosystem="pub",
            version=version,
            source_type="api",
            docs_url=f"https://pub.dev/documentation/go_router/{version}/",
            now=_old_iso(120),
            status="available",
            last_refreshed_at=_old_iso(120),
        )

    result = service.prune_library_docs(
        library="go_router",
        keep_versions=["17.2.3"],
        older_than_days=90,
        dry_run=True,
    )

    assert result.would_remove == ["pub:go_router@14.8.1:api"]


def test_prune_library_docs_removes_failed_stale_records(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="15.0.0",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/15.0.0/",
        now=_old_iso(120),
        status="failed",
        last_error="404",
    )

    result = service.prune_library_docs(library="go_router", older_than_days=90, dry_run=False)

    assert result.removed == ["pub:go_router@15.0.0:api"]
    assert service.registry.get("pub:go_router@15.0.0:api") is None


def test_prune_library_docs_dry_run_includes_failed_records_even_when_not_old(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="15.0.0",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/15.0.0/",
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="failed",
        last_error="404",
    )

    result = service.prune_library_docs(library="go_router", older_than_days=90, dry_run=True)

    assert result.would_remove == ["pub:go_router@15.0.0:api"]
    assert service.registry.get("pub:go_router@15.0.0:api") is not None


def test_prefetch_docs_targets_rejects_localhost_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [{"library": "local", "docs_url": "http://localhost:8000", "allowed_domains": ["localhost"]}]
    )

    assert result.status == "failed"
    assert result.results[0].message == "localhost URLs are not allowed"


def test_prefetch_docs_targets_rejects_private_ip_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [{"library": "router", "docs_url": "http://192.168.1.1", "allowed_domains": ["192.168.1.1"]}]
    )

    assert result.status == "failed"
    assert result.results[0].message == "private network URLs are not allowed"


def test_prefetch_docs_targets_rejects_file_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets(
        [{"library": "passwd", "docs_url": "file:///etc/passwd", "allowed_domains": ["etc"]}]
    )

    assert result.status == "failed"
    assert result.results[0].message == "unsupported URL scheme: file"


def test_prefetch_docs_targets_passes_max_pages_and_browser_false_by_default(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    service.prefetch_docs_targets(
        [
            {
                "library": "flutter-api",
                "docs_url": "https://api.flutter.dev/",
                "allowed_domains": ["api.flutter.dev"],
                "max_pages": 12,
            }
        ]
    )

    assert agent.add_kwargs == [{"max_pages": 12, "browser": False}]


def test_refresh_record_reuses_all_persisted_seed_urls(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    service.prefetch_docs_targets(
        [
            {
                "library": "riverpod-guides",
                "ecosystem": "web",
                "version": "latest",
                "source_type": "guides",
                "seed_urls": [
                    "https://riverpod.dev/docs/one",
                    "https://riverpod.dev/docs/two",
                ],
                "allowed_domains": ["riverpod.dev"],
                "path_prefixes": ["/docs/"],
            }
        ]
    )
    agent.add_calls.clear()
    agent.add_kwargs.clear()
    service.registry.upsert(
        library="riverpod-guides",
        ecosystem="web",
        version="latest",
        source_type="guides",
        docs_url="https://riverpod.dev/docs/one",
        now=_old_iso(),
        status="available",
        last_refreshed_at=_old_iso(),
    )

    result = service.refresh_docs("riverpod-guides", ecosystem="web", version="latest", source_type="guides", force=False)

    assert result.status == "updated"
    assert agent.add_calls == [
        "https://riverpod.dev/docs/one",
        "https://riverpod.dev/docs/two",
    ]
    assert [kwargs["max_pages"] for kwargs in agent.add_kwargs] == [1, 1]
    assert [kwargs["browser"] for kwargs in agent.add_kwargs] == [False, False]
    assert [kwargs["metadata"]["library_id"] for kwargs in agent.add_kwargs] == [
        "web:riverpod-guides@latest:guides",
        "web:riverpod-guides@latest:guides",
    ]


def test_refresh_record_keeps_dartdoc_seed_urls_at_target_page_cap(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    service.prefetch_docs_targets(
        [
            {
                "library": "flutter-bloc-api",
                "ecosystem": "pub",
                "version": "8.1.6",
                "source_type": "api",
                "seed_urls": [
                    "https://pub.dev/documentation/flutter_bloc/latest/flutter_bloc/BlocProvider-class.html",
                    "https://pub.dev/documentation/flutter_bloc/latest/flutter_bloc/BlocBuilder-class.html",
                ],
                "doc_format": "dartdoc",
                "max_pages": 500,
                "allowed_domains": ["pub.dev"],
                "path_prefixes": ["/documentation/flutter_bloc/"],
            }
        ]
    )
    agent.add_calls.clear()
    agent.add_kwargs.clear()
    service.registry.upsert(
        library="flutter-bloc-api",
        ecosystem="pub",
        version="8.1.6",
        source_type="api",
        docs_url="https://pub.dev/documentation/flutter_bloc/latest/flutter_bloc/BlocProvider-class.html",
        now=_old_iso(),
        status="available",
        last_refreshed_at=_old_iso(),
    )

    result = service.refresh_docs("flutter-bloc-api", ecosystem="pub", version="8.1.6", source_type="api", force=False)

    assert result.status == "updated"
    assert agent.add_calls == [
        "https://pub.dev/documentation/flutter_bloc/latest/flutter_bloc/BlocProvider-class.html",
        "https://pub.dev/documentation/flutter_bloc/latest/flutter_bloc/BlocBuilder-class.html",
    ]
    assert [kwargs["max_pages"] for kwargs in agent.add_kwargs] == [500, 500]


def test_remove_library_docs_deletes_physical_index_files(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="available",
    )
    config = service._index_config_for(record)
    db_path = Path(config.index.db_path)
    extracted = Path(config.index.extracted_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("old index", encoding="utf-8")
    extracted.mkdir(parents=True, exist_ok=True)
    (extracted / "chunk.md").write_text("old chunk", encoding="utf-8")

    result = service.remove_library_docs(record.library_id)

    assert result.removed is True
    assert result.chunks_removed > 0
    assert not db_path.exists()
    assert not extracted.exists()


def test_legacy_record_migrates_to_new_canonical_id(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem=None,
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
    )
    assert service.registry.get("go_router@14.8.1") is not None

    result = service.resolve_library("go_router", ecosystem="pub", version="14.8.1")

    assert result.library_id == "dart:go_router@14.8.1:api"
    assert service.registry.get("dart:go_router@14.8.1:api") is not None
    legacy = service.registry.get("go_router@14.8.1")
    assert legacy is not None
    assert legacy.library_id == "dart:go_router@14.8.1:api"
    assert legacy.source_id == "dart:go_router:api"
    assert "go_router@14.8.1" in legacy.legacy_ids


def test_prefetch_project_docs_continue_false_aborts_on_missing_package(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["missing_pkg", "go_router"],
        continue_on_error=False,
    )

    assert result.results == []
    assert agent.add_calls == []


def test_sync_project_docs_dedup_duplicate_indexed_sources(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nDedupDuplicateNeedle", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    agent = service._agent_instance()
    row = None
    with agent.store._connect() as conn:
        row = conn.execute(
            "SELECT source, metadata_json, ingested_at FROM sources WHERE json_extract(metadata_json, '$.project_docs') = 1"
        ).fetchone()
    assert row is not None
    dup_source = f"{row['source']}_dup"
    dup_meta = json.loads(row["metadata_json"])
    dup_meta["project_doc_path"] = dup_meta.get("project_doc_path")
    with agent.store._connect() as conn:
        conn.execute(
            "INSERT INTO sources (source, docset_root, content, metadata_json, ingested_at) VALUES (?, '', '', ?, ?)",
            (dup_source, json.dumps(dup_meta), row["ingested_at"]),
        )

    result = service.sync_project_docs(str(project), with_vectors=False)

    assert result.dedup_removed == 1
    assert result.status == "success"
    assert result.current_count == 1
    with agent.store._connect() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE json_extract(metadata_json, '$.project_docs') = 1"
        ).fetchone()[0]
        assert remaining == 1

    query_result = service.get_project_docs(str(project), "DedupDuplicateNeedle", tokens=1200, limit=5)
    assert query_result.answer_available is True
    assert "DedupDuplicateNeedle" in query_result.results[0].content
