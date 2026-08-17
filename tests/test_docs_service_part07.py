"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_service_restart_automatically_resumes_authorized_library_prefetch(tmp_path, monkeypatch):
    first = _service(tmp_path, monkeypatch, FakeAgent(), durable_jobs=True)
    request_identity = json.dumps({
        "library": "example-docs",
        "ecosystem": "web",
        "docs_url": "https://example.com/docs/",
        "docs_url_template": None,
        "versions": [],
    }, sort_keys=True)
    interrupted = first.jobs.create(
        "prefetch_library_docs",
        request_identity=request_identity,
        request_payload={
            "library": "example-docs",
            "ecosystem": "web",
            "versions": [],
            "docs_url": "https://example.com/docs/",
            "docs_url_template": None,
            "source_type": None,
            "force_refresh": False,
            "continue_on_error": True,
            "target_plan": [],
        },
    )
    first.jobs.update(interrupted.job_id, status="running")

    restarted_tracker = DocsJobTracker(
        db_path=first.config.index.db_path,
        lease_id="simulated-restarted-worker",
    )
    restarted = LibraryDocsService(
        config=first.config,
        registry=first.registry,
        agent=FakeAgent(),
        job_tracker=restarted_tracker,
    )

    recovered = restarted.get_docs_job_status(interrupted.job_id)
    assert recovered is not None
    assert recovered.reason_code == "job_resumed"
    assert recovered.resumed_by_job_id in restarted.resumed_docs_job_ids
    successor = restarted.get_docs_job_status(recovered.resumed_by_job_id)
    assert successor is not None
    assert successor.predecessor_job_id == interrupted.job_id


def test_cancel_between_staging_fetch_and_commit_never_publishes_index(tmp_path, monkeypatch):
    agent = SlowIndexingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )
    assert agent.entered.wait(timeout=1)
    publication = service.library_docs.refresh_ops.publication
    original_count = publication.count_index_config
    cancelled = False

    def cancel_before_commit(config):
        nonlocal cancelled
        if not cancelled:
            cancelled = True
            service.cancel_docs_job(result.job_id)
        return original_count(config)

    monkeypatch.setattr(publication, "count_index_config", cancel_before_commit)
    agent.release.set()
    for _ in range(30):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.02)

    record = service.registry.get("example-docs", "web", "latest")
    assert record is not None
    assert service.library_docs.registry_ops.count_index_entries(record) == (0, 0)


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
    record = service.registry.get("example-docs", "web", "latest")
    assert record is not None
    index_parent = Path(service._index_config_for(record).index.db_path).parent
    for _ in range(50):
        if not list(index_parent.glob(".docatlas-staging-*")):
            break
        time.sleep(0.02)
    assert list(index_parent.glob(".docatlas-staging-*")) == []
    assert service.library_docs.registry_ops.count_index_entries(record) == (0, 0)


def test_library_prefetch_rejects_overload_before_staging(tmp_path, monkeypatch):
    agent = SlowAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.library_docs.job_executor = LibraryJobExecutor(max_workers=1, max_queued=0)

    first = service.prefetch_docs(
        "first-docs",
        ecosystem="web",
        docs_url="https://example.com/first/",
        async_=True,
    )
    assert first.status in {"pending", "running"}
    assert agent.entered.wait(timeout=1)

    rejected = service.prefetch_docs(
        "second-docs",
        ecosystem="web",
        docs_url="https://example.com/second/",
        async_=True,
    )
    assert rejected.status == "busy"
    status = service.get_docs_job_status(rejected.job_id)
    assert status is not None
    assert status.reason_code == "busy"
    assert status.retryable is True
    assert status.generation_id is None
    assert status.running_jobs == 1
    assert status.max_running_jobs == 1
    assert status.max_queued_jobs == 0
    public_status = call_docs_tool_payload(
        "docs_status", {"action": "job", "job_id": rejected.job_id}, service
    )
    assert public_status["running_jobs"] == 1
    assert public_status["max_running_jobs"] == 1
    assert public_status["max_queued_jobs"] == 0
    assert len(agent.add_calls) == 1
    assert not list((tmp_path / "home" / "docs-indexes").glob(".docatlas-staging-*second*"))
    status_latencies = []
    for _ in range(100):
        started = time.monotonic()
        assert service.get_docs_job_status(first.job_id) is not None
        status_latencies.append(time.monotonic() - started)
    assert sorted(status_latencies)[98] < 1.0
    agent.release.set()


def test_cancel_terminalizes_without_waiting_for_library_worker(tmp_path, monkeypatch):
    agent = SlowAgent()
    service = _service(tmp_path, monkeypatch, agent)
    result = service.prefetch_docs(
        "cancelled-docs",
        ecosystem="web",
        docs_url="https://example.com/cancelled/",
        async_=True,
    )
    assert agent.entered.wait(timeout=1)

    service.cancel_docs_job(result.job_id)
    for _ in range(50):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.01)

    assert status is not None
    assert status.status == "cancelled"
    record = service.registry.get("cancelled-docs", "web", "latest")
    assert record is not None
    assert service.library_docs.registry_ops.count_index_entries(record) == (0, 0)
    agent.release.set()


def test_cancellation_during_registry_commit_rolls_back_late_publication(tmp_path, monkeypatch):
    agent = SlowIndexingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(service.library_docs, "_library_job_timeout_seconds", lambda: 5.0)
    original_upsert = service.registry.upsert
    commit_entered = Event()
    commit_release = Event()

    result = service.prefetch_docs(
        "commit-docs",
        ecosystem="web",
        docs_url="https://example.com/commit/",
        async_=True,
    )
    assert agent.entered.wait(timeout=1)

    def blocking_upsert(**values):
        if values.get("status") in {"available", "empty_index"}:
            commit_entered.set()
            commit_release.wait(timeout=1)
        return original_upsert(**values)

    monkeypatch.setattr(service.registry, "upsert", blocking_upsert)
    agent.release.set()
    assert commit_entered.wait(timeout=1)
    service.cancel_docs_job(result.job_id)
    for _ in range(80):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.01)
    assert status is not None
    assert status.reason_code == "cancelled"
    commit_release.set()
    for _ in range(80):
        record = service.registry.get("commit-docs", "web", "latest")
        if (
            record
            and record.last_refreshed_at is None
            and service.library_docs.registry_ops.count_index_entries(record) == (0, 0)
        ):
            break
        time.sleep(0.01)
    assert record is not None
    assert record.last_refreshed_at is None
    assert service.library_docs.registry_ops.count_index_entries(record) == (0, 0)


def test_registry_commit_failure_rolls_back_published_staging_index(tmp_path, monkeypatch):
    agent = SlowIndexingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )
    assert agent.entered.wait(timeout=1)

    monkeypatch.setattr(
        service.registry,
        "upsert",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("registry commit failed")),
    )
    agent.release.set()
    for _ in range(100):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "failed":
            break
        time.sleep(0.02)

    record = service.registry.get("example-docs", "web", "latest")
    assert record is not None
    assert status is not None
    assert status.status == "failed"
    assert service.library_docs.registry_ops.count_index_entries(record) == (0, 0)


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

    for _ in range(100):
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


@pytest.mark.parametrize("document_count", [0, 2])
def test_github_manifest_prefetch_and_refresh_use_one_canonical_operation(
    tmp_path, monkeypatch, document_count,
):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    commit = "1" * 40
    documents = [
        {
            "path": f"docs/guide-{index}.md",
            "git_blob_sha": str(index + 2) * 40,
            "size": index + 10,
        }
        for index in reversed(range(document_count))
    ]
    raw_manifest = {
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory",
            "owner": "acme",
            "repository": "sample",
            "requested_ref": "v1",
            "resolved_commit_sha": commit,
            "directory": "docs",
        },
        "documents": documents,
        "complete": True,
        "truncated": False,
        "ignored_untrusted_field": "not persisted or forwarded",
    }
    canonical_manifest = normalize_resolved_github_manifest(raw_manifest)
    approved = "https://github.com/acme/sample/blob/v1/docs/approved.md"
    target = {
        "library": "sample",
        "ecosystem": "web",
        "version": "v1",
        "source_type": "guides",
        "docs_url": approved,
        "allowed_domains": ["github.com"],
        "path_prefixes": ["/acme/sample/blob/"],
        "source_manifest": raw_manifest,
    }

    prefetch = service.prefetch_docs_targets([target], force_refresh=True)

    if document_count == 0:
        assert prefetch.status == "failed"
        assert prefetch.results[0].status == "failed"  # type: ignore[index]
        return

    assert prefetch.status == "ok"
    assert agent.add_calls == [canonical_manifest["documents"][0]["blob_url"]]
    assert agent.add_kwargs[0]["source_manifest"] == canonical_manifest

    agent.add_calls.clear()
    agent.add_kwargs.clear()
    refreshed = service.refresh_docs(
        "sample",
        ecosystem="web",
        version="v1",
        source_type="guides",
        force=True,
    )

    assert refreshed.status == "skipped"
    assert refreshed.preindex["reason_code"] == "corpus_unchanged"
    assert refreshed.preindex["sync_efficiency"] == {
        "corpus_changed": False,
        "pages_changed": 0,
        "chunks_changed": 0,
        "embedding_work": "avoided",
        "publication_work": "avoided",
    }
    assert agent.add_calls == [canonical_manifest["documents"][0]["blob_url"]]
    assert agent.add_kwargs[0]["source_manifest"] == canonical_manifest
    persisted = service.registry.get("sample", "web", "v1", "guides")
    assert persisted is not None
    assert persisted.target_spec is not None
    assert persisted.target_spec["active_manifest_digest"] == canonical_manifest["digest"]
    assert persisted.target_spec["last_attempt_manifest_digest"] == canonical_manifest["digest"]
    assert persisted.target_spec["last_complete_manifest_digest"] == canonical_manifest["digest"]


def test_prefetch_resolves_approved_github_directory_before_indexing(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    commit = "1" * 40
    commit_response = MagicMock(status_code=200, content=b'{}')
    commit_response.json.return_value = {"sha": commit}
    listing_response = MagicMock(status_code=200, content=b'[]')
    listing_response.json.return_value = [
        {"path": "docs/a.md", "type": "file", "sha": "2" * 40, "size": 1}
    ]
    client = MagicMock()
    client.get.side_effect = [commit_response, listing_response]
    service.docs_targets.github_api_client_factory = lambda: nullcontext(client)

    result = service.prefetch_docs_targets(
        [{
            "library": "sample",
            "ecosystem": "web",
            "version": "v1",
            "source_type": "guides",
            "docs_url": "https://github.com/acme/sample/blob/v1/docs/a.md",
            "allowed_domains": ["github.com"],
            "path_prefixes": ["/acme/sample/blob/"],
            "source_manifest": {
                "schema_version": 2,
                "official": True,
                "discovery": {
                    "kind": "github_directory", "owner": "acme", "repository": "sample",
                    "requested_ref": "v1", "directory": "docs",
                },
            },
        }],
        force_refresh=True,
    )

    assert result.status == "ok"
    assert len(client.get.call_args_list) == 2
    manifest = agent.add_kwargs[0]["source_manifest"]
    assert manifest["complete"] is True
    assert manifest["discovery"]["resolved_commit_sha"] == commit
    assert agent.add_calls == [manifest["documents"][0]["blob_url"]]
    record = service.registry.get("sample", "web", "v1", "guides")
    assert record is not None
    assert record.target_spec is not None
    assert record.target_spec["active_manifest_digest"] == manifest["digest"]
    assert record.target_spec["last_attempt_manifest_digest"] == manifest["digest"]
    assert record.target_spec["last_complete_manifest_digest"] == manifest["digest"]
    assert record.target_spec["ingestion_policy_version"] == 1
    inspection = service.inspect_library_docs(record.library_id)
    assert inspection.active_manifest_digest == manifest["digest"]
    assert inspection.last_attempt_manifest_digest == manifest["digest"]
    assert inspection.last_complete_manifest_digest == manifest["digest"]


def test_manifest_prefetch_replaces_prior_library_corpus(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    before = service.registry.upsert(
        library="manifest-library",
        ecosystem="web",
        version="latest",
        source_type="guides",
        docs_url="https://docs.example.com/old/",
        now=service._now(),
        status="available",
    )
    service._agent_instance(before).add("https://docs.example.com/old/")
    assert service.library_docs.registry_ops.count_index_entries(before) == (1, 1)

    raw_manifest = {
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory",
            "owner": "acme",
            "repository": "sample",
            "requested_ref": "v1",
            "resolved_commit_sha": "1" * 40,
            "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    }
    result = service.prefetch_docs_targets(
        [{
            "library": "manifest-library",
            "ecosystem": "web",
            "version": "latest",
            "source_type": "guides",
            "docs_url": "https://github.com/acme/sample/blob/v1/docs/guide.md",
            "allowed_domains": ["github.com"],
            "path_prefixes": ["/acme/sample/blob/"],
            "source_manifest": normalize_resolved_github_manifest(raw_manifest),
        }],
        force_refresh=True,
        async_=False,
    )

    record = service.registry.get("manifest-library", "web", "latest", "guides")
    assert result.status == "ok", result.results[0].message  # type: ignore[union-attr]
    assert record is not None
    assert service.library_docs.registry_ops.count_index_entries(record) == (1, 1)


def test_failed_manifest_prefetch_keeps_active_library_corpus(tmp_path, monkeypatch):
    agent = FailingManifestAgent()
    service = _service(tmp_path, monkeypatch, agent)
    previous_manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v0", "resolved_commit_sha": "0" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/old.md", "git_blob_sha": "1" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-rollback",
        ecosystem="web",
        version="latest",
        source_type="guides",
        docs_url="https://docs.example.com/old/",
        now=service._now(),
        status="available",
        target_spec={
            "source_manifest": previous_manifest,
            "active_manifest_digest": previous_manifest["digest"],
            "last_attempt_manifest_digest": previous_manifest["digest"],
            "last_complete_manifest_digest": previous_manifest["digest"],
        },
    )
    service._agent_instance(record).add("https://docs.example.com/old/")
    assert service.library_docs.registry_ops.count_index_entries(record) == (1, 1)
    attempted_manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "2" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "3" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    })

    result = service.prefetch_docs_targets(
        [{
            "library": "manifest-rollback",
            "ecosystem": "web",
            "version": "latest",
            "source_type": "guides",
            "docs_url": "https://github.com/acme/sample/blob/v1/docs/guide.md",
            "allowed_domains": ["github.com"],
            "path_prefixes": ["/acme/sample/blob/"],
            "source_manifest": attempted_manifest,
        }],
        force_refresh=True,
        async_=False,
    )

    active = service.registry.get("manifest-rollback", "web", "latest", "guides")
    assert result.status == "failed"
    assert active is not None
    assert active.status == "available"
    assert service.library_docs.registry_ops.count_index_entries(active) == (1, 1)
    assert active.target_spec is not None
    assert active.target_spec["active_manifest_digest"] == previous_manifest["digest"]
    assert active.target_spec["last_complete_manifest_digest"] == previous_manifest["digest"]
    assert active.target_spec["last_attempt_manifest_digest"] == attempted_manifest["digest"]
    assert active.target_spec["last_attempt_manifest_diagnostics"] == {
        "attempted_manifest_digest": attempted_manifest["digest"],
        "reason_code": "indexing_failed",
    }


@pytest.mark.parametrize(
    ("agent", "failure", "expected_reason"),
    [
        (ZeroManifestAgent(), "no_chunks", "no_extractable_content"),
        (FakeAgent(), "source_set", "manifest_source_set_mismatch"),
        (VectorTrackingAgent(fail_sync=True), "vector", "vector_indexing_failed"),
    ],
)
def test_failed_manifest_candidates_retain_active_metadata_and_diagnostics(
    tmp_path, monkeypatch, agent, failure, expected_reason,
):
    service = _service(tmp_path, monkeypatch, agent)
    if failure == "vector":
        service.config.retrieval.default_mode = "hybrid"
    active_docs_url_template = "https://docs.example.com/active/{version}/"
    attempted_docs_url_template = "https://docs.example.com/attempted/{version}/"
    previous_manifest = normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "acme", "repository": "sample", "requested_ref": "v0", "resolved_commit_sha": "0" * 40, "directory": "docs"},
        "documents": [{"path": "docs/old.md", "git_blob_sha": "1" * 40, "size": 12}],
        "complete": True, "truncated": False,
    })
    active = service.registry.upsert(
        library="manifest-candidate-rollback", ecosystem="web", version="latest",
        source_type="guides", docs_url="https://docs.example.com/old/", now=service._now(),
        docs_url_template=active_docs_url_template,
        status="available", target_spec={
            "source_manifest": previous_manifest,
            "active_manifest_digest": previous_manifest["digest"],
            "last_complete_manifest_digest": previous_manifest["digest"],
        },
    )
    _add_manifest_documents(service, active, previous_manifest, generation=True)
    active_inspection = service.inspect_library_docs(active.library_id)
    assert active_inspection.active_generation_id is not None
    attempted_manifest = normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "acme", "repository": "sample", "requested_ref": "v1", "resolved_commit_sha": "2" * 40, "directory": "docs"},
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "3" * 40, "size": 12}],
        "complete": True, "truncated": False,
    })
    candidate = replace(
        active,
        docs_url=attempted_manifest["documents"][0]["blob_url"],
        docs_url_template=attempted_docs_url_template,
        target_spec={
            "source_manifest": attempted_manifest,
            "active_source_manifest": previous_manifest,
            "active_manifest_digest": previous_manifest["digest"],
            "last_complete_manifest_digest": previous_manifest["digest"],
        },
    )
    if failure == "source_set":
        monkeypatch.setattr(
            service.library_docs.registry_ops, "manifest_coverage",
            lambda *args, **kwargs: (1, 0, 1, 0, attempted_manifest["digest"]),
        )

    result = service._refresh_record_unlocked(candidate, force=True)

    restored = service.registry.get(active.library_id, source_type=active.source_type)
    assert result.status in {"failed", "empty_index"}
    assert restored is not None
    assert restored.status == active.status
    assert restored.docs_url == active.docs_url
    assert restored.docs_url_template == active_docs_url_template
    assert restored.docs_url_template != candidate.docs_url_template
    assert restored.last_refreshed_at == active.last_refreshed_at
    assert restored.target_spec is not None
    assert restored.target_spec["active_manifest_digest"] == previous_manifest["digest"]
    assert restored.target_spec["last_complete_manifest_digest"] == previous_manifest["digest"]
    assert restored.target_spec["last_attempt_manifest_diagnostics"] == {
        "attempted_manifest_digest": attempted_manifest["digest"],
        "reason_code": expected_reason,
    }
    inspection = service.inspect_library_docs(restored.library_id)
    assert inspection.docs_url == active.docs_url
    assert inspection.docs_url_template == active_docs_url_template
    assert inspection.docs_url_template != candidate.docs_url_template
    assert inspection.active_manifest_digest == previous_manifest["digest"]
    assert inspection.last_complete_manifest_digest == previous_manifest["digest"]
    assert inspection.active_generation_id == active_inspection.active_generation_id
    assert inspection.requested_ref == "v0"
    assert inspection.resolved_commit_sha == "0" * 40
    assert inspection.manifest_complete is True
    assert inspection.manifest_truncated is False
    assert inspection.last_attempt_manifest_digest == attempted_manifest["digest"]
    assert inspection.last_attempt_manifest_diagnostics == {
        "attempted_manifest_digest": attempted_manifest["digest"],
        "reason_code": expected_reason,
    }
