"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

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

    result = service.get_docs("riverpod", ecosystem="pub", version="2.6.1", topic="Riverpod")

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
    action = result.next_actions[0]
    assert action["arguments_patch"]["action"] == "prefetch_library_docs"
    assert action["security_scope"]["scope_expansion_allowed"] is False


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


def test_prefetch_project_docs_counts_partial_target_as_completed(tmp_path, monkeypatch):
    class PartialAgent(FakeAgent):
        def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
            pages = super().add(docs_url, recreate=recreate, **kwargs)
            self.last_discovery_diagnostics = {"complete": False, "reason_code": "page_budget_exhausted"}
            return pages

    project = _flutter_project(tmp_path)
    service = _service(tmp_path, monkeypatch, PartialAgent())
    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)

    result = service.prefetch_project_docs(
        str(project),
        include_flutter=False,
        include_packages=["go_router"],
    )

    assert result.results[0].status == "partial"
    assert result.results[0].targets_completed == 1
    assert result.results[0].targets_failed == 0

    default_agent = FakeAgent()
    default_service = _service(tmp_path / "default", monkeypatch, default_agent)
    monkeypatch.setattr(default_service, "_discover_pub_dartdoc_target", lambda target, warnings, job_id=None, canonical_id=None: target)
    default_result = default_service.prefetch_project_docs(
        str(project), include_flutter=False, include_packages=[],
    )
    assert {item.library_id for item in default_result.results} == {
        "pub:go_router@14.8.1:api", "pub:riverpod@2.6.1:api",
    }


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
    action = result.next_actions[0]
    assert action["arguments_patch"] == {
        "action": "prefetch_library_docs",
        "library": "flutter_bloc",
        "ecosystem": "pub",
        "version": "9.1.1",
    }
    assert action["security_scope"]["scope_expansion_allowed"] is False
    assert action["requires_confirmation"] is True


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
