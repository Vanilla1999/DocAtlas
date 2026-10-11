"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

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
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    services: list[LibraryDocsService] = []
    records = []
    for name in ("project-a", "project-b"):
        project = tmp_path / name
        project.mkdir()
        (project / "docatlas.yaml").write_text(
            "index:\n  db_path: .docatlas/project.db\n",
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


def test_resolve_library_reuses_current_canonical_record(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="go_router",
        ecosystem="dart",
        version="14.8.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
        now=now,
        status="available",
    )
    assert service.registry.get("dart:go_router@14.8.1:api") is not None

    result = service.resolve_library("go_router", ecosystem="pub", version="14.8.1")

    assert result.library_id == "dart:go_router@14.8.1:api"
    assert service.registry.get("dart:go_router@14.8.1:api") is not None
    assert len(service.registry.list()) == 1




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
    (project / "docatlas.yaml").write_text(
        "index:\n  db_path: .docatlas/project.db\n",
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
        (project / ".docatlas" / "project.db").resolve()
    )
    active = result["project"]["diagnostics"]["active_index"]
    assert active["config_source"] == "project_local"
    assert active["config_path"] == str((project / "docatlas.yaml").resolve())
    assert active["retrieval_mode"] == "lexical"




def test_project_service_cache_reuses_directory_config_and_invalidates_on_change(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    config_path = project / "docatlas.yaml"
    config_path.write_text("index:\n  db_path: .docatlas/one.db\n", encoding="utf-8")
    fallback = LibraryDocsService(config=DocmancerConfig(), job_tracker=DocsJobTracker())
    from docmancer.mcp.docs_server import _service_for_project_path

    first = _service_for_project_path(fallback, {"project_path": str(project)})
    second = _service_for_project_path(fallback, {"project_path": str(project / ".")})
    config_path.write_text("index:\n  db_path: .docatlas/two.db\n", encoding="utf-8")
    third = _service_for_project_path(fallback, {"project_path": str(project)})

    assert first is second
    assert Path(first.config_path) == config_path.resolve()
    assert Path(first.config.index.db_path) == (project / ".docatlas/one.db").resolve()
    assert third is not first
    assert Path(third.config.index.db_path) == (project / ".docatlas/two.db").resolve()
    assert len(fallback._project_service_cache) == 1


def test_project_service_cache_concurrent_first_use_and_config_replacement(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from docmancer.mcp.docs_server import _service_for_project_path

    project = tmp_path / "project"
    project.mkdir()
    config_path = project / "docatlas.yaml"
    config_path.write_text("index:\n  db_path: .docatlas/one.db\n", encoding="utf-8")
    fallback = LibraryDocsService(config=DocmancerConfig(), job_tracker=DocsJobTracker())

    def resolve():
        return _service_for_project_path(fallback, {"project_path": str(project)})

    with ThreadPoolExecutor(max_workers=8) as executor:
        first_wave = list(executor.map(lambda _: resolve(), range(24)))
    config_path.write_text("index:\n  db_path: .docatlas/two.db\n", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=8) as executor:
        second_wave = list(executor.map(lambda _: resolve(), range(24)))

    assert len({id(item) for item in first_wave}) == 1
    assert len({id(item) for item in second_wave}) == 1
    assert first_wave[0] is not second_wave[0]
    assert len(fallback._project_service_cache) == 1


def test_prepare_docs_removes_project_local_library_target(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    (project / "docatlas.yaml").write_text(
        "index:\n  db_path: .docatlas/project.db\n",
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

    assert result["error"]["reason_code"] == "validation_error"
    assert fallback_service.registry.get(record.canonical_id) is not None


def test_prepare_docs_cancels_project_local_job_using_project_topology(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "docatlas.yaml").write_text(
        "index:\n  db_path: .docatlas/project.db\n",
        encoding="utf-8",
    )
    fallback_service = _service(tmp_path, monkeypatch)
    project_service = LibraryDocsService(config=DocmancerConfig.from_yaml(project / "docatlas.yaml"))
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

