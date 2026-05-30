from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread
import time

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.mcp.docs_server import TOOLS


class FakeAgent:
    def __init__(self):
        self.add_calls: list[str] = []
        self.add_kwargs: list[dict] = []
        self.query_calls: list[tuple[str, int | None]] = []

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        return 1

    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append((text, budget))
        return [
            RetrievedChunk(
                source="https://docs.example.com/guide",
                chunk_index=0,
                text="Use parametrize for generated cases.",
                score=1.0,
                metadata={"title": "Parametrize"},
            )
        ]


class FailingAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if "bad-version" in docs_url:
            raise RuntimeError("404 docs")
        return 1


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


class PageFailingAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if "bad" in docs_url:
            raise RuntimeError("bad page")
        return 1


class AlwaysFailingAgent(FakeAgent):
    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        raise RuntimeError("indexer exploded")


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


def _service(tmp_path, monkeypatch, agent: FakeAgent | None = None) -> LibraryDocsService:
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=agent or FakeAgent(),
        job_tracker=DocsJobTracker(),
    )


def _old_iso(days: int = 31) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


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


def test_mcp_exposes_prefetch_library_docs():
    assert "prefetch_library_docs" in {tool["name"] for tool in TOOLS}


def test_mcp_exposes_prefetch_project_docs():
    assert "prefetch_project_docs" in {tool["name"] for tool in TOOLS}


def test_mcp_exposes_prefetch_docs_targets():
    assert "prefetch_docs_targets" in {tool["name"] for tool in TOOLS}


def test_mcp_exposes_docs_job_tools():
    names = {tool["name"] for tool in TOOLS}
    assert "get_docs_job_status" in names
    assert "list_docs_jobs" in names
    assert "cancel_docs_job" in names


def test_mcp_exposes_manifest_tools():
    names = {tool["name"] for tool in TOOLS}
    assert "validate_docs_manifest" in names
    assert "prefetch_docs_manifest" in names


def test_mcp_exposes_lifecycle_tools():
    names = {tool["name"] for tool in TOOLS}
    assert "inspect_library_docs" in names
    assert "remove_library_docs" in names
    assert "prune_library_docs" in names


def test_project_reader_reads_pubspec_lock_versions(tmp_path):
    project = _flutter_project(tmp_path)

    metadata = ProjectMetadataReader().read(project)

    assert metadata.packages["go_router"] == "14.8.1"
    assert metadata.packages["riverpod"] == "2.6.1"


def test_project_reader_preserves_go_router_underscore(tmp_path):
    project = _flutter_project(tmp_path)

    metadata = ProjectMetadataReader().read(project)

    assert "go_router" in metadata.packages
    assert "go-router" not in metadata.packages


def test_project_reader_reads_fvmrc(tmp_path):
    project = _flutter_project(tmp_path, fvmrc='{"flutter": "3.24.5", "channel": "stable"}')

    metadata = ProjectMetadataReader().read(project)

    assert metadata.flutter_version == "3.24.5"
    assert metadata.flutter_channel == "stable"


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

    assert result.library_id == "pub:go_router@14.8.1:api"
    assert result.version == "14.8.1"


def test_hyphen_alias_resolves_to_underscore_package_record(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="14.8.1",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
    )

    result = service.resolve_library("go-router", ecosystem="pub", version="14.8.1")

    assert result.library_id == "pub:go_router@14.8.1:api"
    assert result.library == "go_router"


def test_docs_url_template_registers_version_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="16.2.0",
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.library_id == "pub:go_router@16.2.0:api"
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
    assert service.registry.get("go_router", "pub", "15.0.0").library_id == "pub:go_router@15.0.0:api"


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


def test_missing_version_falls_back_to_latest_with_warning(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

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


def test_get_docs_uses_project_package_version_when_omitted(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("go_router", ecosystem="pub", topic="ShellRoute", project_path=str(project))

    assert result.library_id == "pub:go_router@14.8.1:api"
    assert result.version == "14.8.1"
    assert result.docs_snapshot_exact is True
    assert result.requested_version == "14.8.1"
    assert result.version_source == "project"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/14.8.1/"]


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

    assert result.library_id == "pub:go_router@16.2.0:api"
    assert result.version == "16.2.0"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/16.2.0/"]


def test_flutter_fvmrc_version_uses_stable_channel_id_not_exact_version(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path, fvmrc='{"flutter": "3.24.5", "channel": "stable"}')
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("flutter-api", topic="Navigator", project_path=str(project))

    assert result.library_id == "flutter:flutter-api@stable:api"
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

    assert result.library_id == "flutter:flutter-api@main:api"
    assert result.version == "main"
    assert result.docs_snapshot_exact is False
    assert agent.add_calls == ["https://main-api.flutter.dev/"]


def test_query_isolation_returns_only_requested_go_router_version(tmp_path, monkeypatch):
    agent = MixedVersionFakeAgent()
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
        version="latest",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.get_docs("go_router", ecosystem="pub", version="14.8.1", topic="ShellRoute")

    assert [chunk.content for chunk in result.results] == ["ShellRoute behavior from 14.8.1."]


def test_query_isolation_returns_only_latest_go_router_version(tmp_path, monkeypatch):
    agent = MixedVersionFakeAgent()
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
        version="latest",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.get_docs("go_router", ecosystem="pub", version="latest", topic="ShellRoute")

    assert [chunk.content for chunk in result.results] == ["ShellRoute behavior from latest."]


def test_query_isolation_between_two_riverpod_versions(tmp_path, monkeypatch):
    agent = MixedRiverpodFakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="riverpod",
        ecosystem="pub",
        version="2.6.1",
        docs_url="https://pub.dev/documentation/riverpod/2.6.1/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
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


def test_prefetch_project_docs_prefetches_only_selected_packages(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["go_router"],
    )

    assert len(result.results) == 1
    assert result.results[0].library_id == "pub:go_router@14.8.1:api"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/14.8.1/"]


def test_prefetch_project_docs_missing_package_returns_warning(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["missing_pkg"],
    )

    assert result.results[0].status == "needs_docs_url"
    assert "Package was not found in pubspec.lock." in result.results[0].message
    assert "missing_pkg: Package was not found in pubspec.lock." in result.warnings
    assert agent.add_calls == []


def test_fresh_library_does_not_refresh(tmp_path, monkeypatch):
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
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    result = service.refresh_docs("pytest", force=False)

    assert result.status == "skipped"
    assert agent.add_calls == []


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

    assert api.library_id == "pub:riverpod@latest:api"
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
                "library": "go_router",
                "ecosystem": "pub",
                "version": "latest",
                "docs_url_template": "https://pub.dev/documentation/{library}/{version}/",
                "allowed_domains": ["pub.dev"],
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


def test_prefetch_docs_manifest_resolves_project_version_from_pubspec_lock(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
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
    assert result.status == "available"
    assert result.library == "go_router"
    assert result.stale is False


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
    assert agent.add_kwargs == [
        {"max_pages": 1, "browser": False},
        {"max_pages": 1, "browser": False},
    ]


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

    assert result.library_id == "pub:go_router@14.8.1:api"
    assert service.registry.get("pub:go_router@14.8.1:api") is not None
    assert service.registry.get("go_router@14.8.1") is None


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

    assert [item.library_id for item in result.results] == ["missing_pkg"]
    assert agent.add_calls == []
