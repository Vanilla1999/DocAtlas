from __future__ import annotations

import hashlib
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from threading import Event, Thread
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.core.config import DocmancerConfig
from docmancer.core.storage_topology import StorageTopologyResolver
from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.agent import DocmancerAgent
from docmancer.docs.github_source_manifest import normalize_resolved_github_manifest
from docmancer.docs.models import DocsChunk, DocsResult, ProjectContextResult, SOURCE_CLASS_PROJECT_FILE
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.docs.application.library_job_executor import LibraryJobExecutor
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


class FakeAgent:
    def __init__(self):
        self.add_calls: list[str] = []
        self.add_kwargs: list[dict] = []
        self.query_calls: list[tuple[str, int | None]] = []
        self.config = None
        self.document_content = "# Guide\nUse parametrize for generated cases."

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if self.config is not None:
            store = SQLiteStore(self.config.index.db_path, self.config.index.extracted_dir)
            metadata = dict(kwargs.get("metadata") or {})
            metadata.setdefault("title", "Guide")
            manifest = kwargs.get("source_manifest") or {}
            if manifest.get("schema_version") == 2:
                commit = manifest["discovery"]["resolved_commit_sha"]
                documents = []
                for document in manifest["documents"]:
                    document_metadata = {
                        **metadata,
                        "canonical_url": document["blob_url"],
                        "resolved_commit_sha": commit,
                        "git_blob_sha": document["git_blob_sha"],
                        "content_sha256": hashlib.sha256(
                            f"# {document['path']}\nManifest fixture content.".encode("utf-8")
                        ).hexdigest(),
                    }
                    documents.append(Document(
                        source=document["blob_url"],
                        content=f"# {document['path']}\nManifest fixture content.",
                        metadata=document_metadata,
                    ))
                store.add_documents(documents, recreate=recreate)
                return len(documents)
            store.add_documents([Document(source=docs_url.rstrip("/") + "/guide", content=self.document_content, metadata=metadata)], recreate=recreate)
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


def _add_manifest_documents(service, record, manifest, documents=None, *, generation=False) -> None:
    """Populate a fixture index with the exact source identities in a manifest."""
    selected = documents if documents is not None else manifest["documents"]
    commit = manifest["discovery"]["resolved_commit_sha"]
    store = SQLiteStore(
        service._index_config_for(record).index.db_path,
        service._index_config_for(record).index.extracted_dir,
    )
    store.add_documents([
        Document(
            source=document["blob_url"],
            content=f"# {document['path']}\nExact manifest fixture.",
            metadata={
                "canonical_url": document["blob_url"],
                "resolved_commit_sha": commit,
                "git_blob_sha": document["git_blob_sha"],
                "content_sha256": hashlib.sha256(
                    f"# {document['path']}\nExact manifest fixture.".encode("utf-8")
                ).hexdigest(),
                **({"chunking_schema": "parent-child-v1"} if generation else {}),
            },
        )
        for document in selected
    ], recreate=True)


class FailingAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        if "bad-version" in docs_url:
            self.add_calls.append(docs_url)
            self.add_kwargs.append(kwargs)
            raise RuntimeError("404 docs")
        return super().add(docs_url, recreate=recreate, **kwargs)


class FailingManifestAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        if kwargs.get("source_manifest"):
            raise RuntimeError("manifest fetch failed")
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


VectorSyncFailure = type("aws_secret_access_key_leaked_value", (RuntimeError,), {})


class VectorTrackingAgent(FakeAgent):
    def __init__(self, *, fail_sync: bool = False, skip_sync: bool = False):
        super().__init__()
        self.fail_sync = fail_sync
        self.skip_sync = skip_sync
        self.sync_calls = 0
        self.prepare_calls = 0
        self.sync_db_paths: list[str] = []

    def prepare_vector_generation(self):
        self.prepare_calls += 1
        return "staging-vector-collection"

    def sync_vectors(self):
        self.sync_calls += 1
        self.sync_db_paths.append(self.config.index.db_path)
        if self.fail_sync:
            raise VectorSyncFailure(
                '{"api_key": "vector-sync-secret", "password": "other-secret", '
                '"AWS_SECRET_ACCESS_KEY": "aws-env-secret", '
                '"Authorization": "Bearer authorization-secret"}'
            )
        if self.skip_sync:
            self.last_vector_sync_metrics = {
                "status": "skipped",
                "reason": "missing_vector_extra",
            }
            return None
        self.last_vector_sync_metrics = {
            "status": "success",
            "vector_backend": "sqlite-vec",
        }
        return SimpleNamespace(upserted=1)


class SlowVectorTrackingAgent(SlowIndexingAgent):
    def __init__(self):
        super().__init__()
        self.sync_calls = 0

    def sync_vectors(self):
        self.sync_calls += 1


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


class ZeroManifestAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        if kwargs.get("source_manifest"):
            super().add(docs_url, recreate=recreate, **kwargs)
            return 0
        return super().add(docs_url, recreate=recreate, **kwargs)


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


def _service(
    tmp_path,
    monkeypatch,
    agent: FakeAgent | None = None,
    *,
    durable_jobs: bool = False,
) -> LibraryDocsService:
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
        job_tracker=DocsJobTracker(db_path=config.index.db_path) if durable_jobs else DocsJobTracker(),
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



































































































































































































































































































































































































































def _write_manifest(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path
