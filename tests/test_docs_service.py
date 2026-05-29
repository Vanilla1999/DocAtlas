from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Thread

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import TOOLS


class FakeAgent:
    def __init__(self):
        self.add_calls: list[str] = []
        self.query_calls: list[tuple[str, int | None]] = []

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
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

    assert result.library_id == "go_router@14.8.1"
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

    assert result.library_id == "go_router@14.8.1"
    assert result.library == "go_router"


def test_docs_url_template_registers_version_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="16.2.0",
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.library_id == "go_router@16.2.0"
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
    assert service.registry.get("go_router", "pub", "15.0.0").library_id == "go_router@15.0.0"


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

    assert result.library_id == "go_router@latest"
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

    assert result.library_id == "go_router@14.8.1"
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

    assert result.library_id == "go_router@16.2.0"
    assert result.version == "16.2.0"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/16.2.0/"]


def test_flutter_fvmrc_version_uses_stable_channel_id_not_exact_version(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path, fvmrc='{"flutter": "3.24.5", "channel": "stable"}')
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("flutter-api", topic="Navigator", project_path=str(project))

    assert result.library_id == "flutter-api@stable"
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

    assert result.library_id == "flutter-api@main"
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
    assert result.results[0].library_id == "go_router@14.8.1"
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
