"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

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

    assert agent.add_kwargs[0]["max_pages"] == 12
    assert agent.add_kwargs[0]["browser"] is False
    assert agent.add_kwargs[0]["metadata"]["canonical_source_identity"].startswith("source:")
    assert agent.add_kwargs[0]["metadata"]["version"] == "latest"


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


def test_remove_library_docs_preserves_other_project_library_index(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    services: list[LibraryDocsService] = []
    records = []
    for name in ("project-a", "project-b"):
        project = tmp_path / name
        project.mkdir()
        (project / "docmancer.yaml").write_text(
            "index:\n  db_path: .docmancer/project.db\n",
            encoding="utf-8",
        )
        topology = StorageTopologyResolver().resolve(project)
        service = LibraryDocsService(
            config=topology.config,
            library_index_root=topology.library_index_root,
        )
        record = service.registry.upsert(
            library="go_router",
            ecosystem="pub",
            version="14.8.1",
            source_type="api",
            docs_url="https://pub.dev/documentation/go_router/14.8.1/",
            now=now,
            status="available",
        )
        index_path = Path(service._index_config_for(record).index.db_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(name, encoding="utf-8")
        services.append(service)
        records.append(record)

    result = services[0].remove_library_docs(records[0].library_id)

    other_index = Path(services[1]._index_config_for(records[1]).index.db_path)
    assert result.removed is True
    assert not Path(services[0]._index_config_for(records[0]).index.db_path).exists()
    assert other_index.exists()
    assert other_index.read_text(encoding="utf-8") == "project-b"


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


def test_service_startup_removes_only_old_owned_staging_directories(tmp_path, monkeypatch):
    old_owned = tmp_path / ".docatlas-staging-old"
    fresh_owned = tmp_path / ".docatlas-staging-fresh"
    old_unowned = tmp_path / ".docatlas-staging-unowned"
    for root in (old_owned, fresh_owned, old_unowned):
        root.mkdir()
    old_marker = old_owned / ".docatlas-staging-owner.json"
    fresh_marker = fresh_owned / ".docatlas-staging-owner.json"
    owner = '{"job_id":"orphan-job","generation_id":"revoked-generation"}'
    old_marker.write_text(owner, encoding="utf-8")
    fresh_marker.write_text(owner, encoding="utf-8")
    old_time = time.time() - (25 * 60 * 60)
    os.utime(old_marker, (old_time, old_time))

    _service(tmp_path, monkeypatch)

    assert not old_owned.exists()
    assert fresh_owned.exists()
    assert old_unowned.exists()


def test_mcp_docs_status_uses_project_local_storage_topology(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Project\n", encoding="utf-8")
    (project / "docmancer.yaml").write_text(
        "index:\n  db_path: .docmancer/project.db\n",
        encoding="utf-8",
    )
    fallback_config = DocmancerConfig()
    fallback_config.index.db_path = str(tmp_path / "fallback.db")
    service = LibraryDocsService(config=fallback_config, job_tracker=DocsJobTracker())

    result = call_docs_tool_payload(
        "docs_status",
        {"action": "project", "project_path": str(project)},
        service,
    )

    assert result["project"]["diagnostics"]["active_index"]["db_path"] == str(
        (project / ".docmancer" / "project.db").resolve()
    )
    active = result["project"]["diagnostics"]["active_index"]
    assert active["config_source"] == "project_local"
    assert active["config_path"] == str((project / "docmancer.yaml").resolve())
    assert active["retrieval_mode"] == "lexical"


def test_project_service_cache_reuses_directory_config_and_invalidates_on_change(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config_path = project / "docmancer.yaml"
    config_path.write_text("index:\n  db_path: .docmancer/one.db\n", encoding="utf-8")
    fallback = LibraryDocsService(config=DocmancerConfig(), job_tracker=DocsJobTracker())
    from docmancer.mcp.docs_server import _service_for_project_path

    first = _service_for_project_path(fallback, {"project_path": str(project)})
    second = _service_for_project_path(fallback, {"project_path": str(project / ".")})
    config_path.write_text("index:\n  db_path: .docmancer/two.db\n", encoding="utf-8")
    third = _service_for_project_path(fallback, {"project_path": str(project)})

    assert first is second
    assert Path(first.config_path) == config_path.resolve()
    assert Path(first.config.index.db_path) == (project / ".docmancer/one.db").resolve()
    assert third is not first
    assert Path(third.config.index.db_path) == (project / ".docmancer/two.db").resolve()
    assert len(fallback._project_service_cache) == 1


def test_project_service_cache_concurrent_first_use_and_config_replacement(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from docmancer.mcp.docs_server import _service_for_project_path

    project = tmp_path / "project"
    project.mkdir()
    config_path = project / "docmancer.yaml"
    config_path.write_text("index:\n  db_path: .docmancer/one.db\n", encoding="utf-8")
    fallback = LibraryDocsService(config=DocmancerConfig(), job_tracker=DocsJobTracker())

    def resolve():
        return _service_for_project_path(fallback, {"project_path": str(project)})

    with ThreadPoolExecutor(max_workers=8) as executor:
        first_wave = list(executor.map(lambda _: resolve(), range(24)))
    config_path.write_text("index:\n  db_path: .docmancer/two.db\n", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=8) as executor:
        second_wave = list(executor.map(lambda _: resolve(), range(24)))

    assert len({id(item) for item in first_wave}) == 1
    assert len({id(item) for item in second_wave}) == 1
    assert first_wave[0] is not second_wave[0]
    assert len(fallback._project_service_cache) == 1


def test_prepare_docs_removes_project_local_library_target(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "docmancer.yaml").write_text(
        "index:\n  db_path: .docmancer/project.db\n",
        encoding="utf-8",
    )
    fallback_config = DocmancerConfig()
    fallback_config.index.db_path = str(tmp_path / "fallback.db")
    fallback_service = LibraryDocsService(config=fallback_config, job_tracker=DocsJobTracker())
    topology = StorageTopologyResolver().resolve(project)
    project_service = LibraryDocsService(
        config=topology.config,
        library_index_root=topology.library_index_root,
    )
    record = project_service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="available",
    )

    result = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "remove_library_docs",
            "canonical_id": record.canonical_id,
            "project_path": str(project),
        },
        fallback_service,
    )

    assert result["removed"] is True
    assert project_service.registry.get(record.canonical_id) is None


@pytest.mark.parametrize("scope_kind", ["configless", "nonexistent"])
def test_prepare_docs_removal_rejects_scope_without_project_owned_topology(tmp_path, scope_kind):
    project_path = tmp_path / scope_kind
    if scope_kind == "configless":
        project_path.mkdir()
    fallback_config = DocmancerConfig()
    fallback_config.index.db_path = str(tmp_path / "fallback.db")
    fallback_service = LibraryDocsService(config=fallback_config, job_tracker=DocsJobTracker())
    record = fallback_service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="available",
    )

    result = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "remove_library_docs",
            "canonical_id": record.canonical_id,
            "project_path": str(project_path),
        },
        fallback_service,
    )

    assert result["reason_code"] == "validation_error"
    assert fallback_service.registry.get(record.canonical_id) is not None


def test_prepare_docs_cancels_project_local_job_using_project_topology(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "docmancer.yaml").write_text(
        "index:\n  db_path: .docmancer/project.db\n",
        encoding="utf-8",
    )
    fallback_service = _service(tmp_path, monkeypatch)
    project_service = LibraryDocsService(config=DocmancerConfig.from_yaml(project / "docmancer.yaml"))
    job = project_service.jobs.create("prefetch_project_dependency_docs")

    result = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "cancel_docs_job",
            "job_id": job.job_id,
            "project_path": str(project),
        },
        fallback_service,
    )

    assert result["status"] == "cancelling"
    project_job = project_service.get_docs_job_status(job.job_id)
    assert project_job is not None
    assert project_job.status == "cancelling"


def test_inflight_library_refresh_registers_storage_writer_lease_and_blocks_remove(tmp_path, monkeypatch):
    from docmancer.docs.infrastructure.storage_mutation_lock import (
        StorageMutationBusy,
        active_storage_writer_leases,
    )

    agent = SlowIndexingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    result = service.prefetch_docs(
        "lease-docs",
        ecosystem="web",
        docs_url="https://example.com/lease/",
        async_=True,
    )
    assert agent.entered.wait(timeout=1)
    try:
        leases = active_storage_writer_leases(service.config.index.db_path)
        assert any("library docs refresh" in item for item in leases)
        record = service.registry.get("lease-docs", "web", "latest")
        assert record is not None
        with pytest.raises(StorageMutationBusy, match="active index writer lease"):
            service.remove_library_docs(record.library_id)
    finally:
        service.cancel_docs_job(result.job_id)
        agent.release.set()
