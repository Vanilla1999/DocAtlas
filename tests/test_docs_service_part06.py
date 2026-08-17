"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

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
        "missing-library",
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
    assert payload["status"] in {"pending", "running"}
    assert payload["job_id"]
    assert agent.entered.wait(timeout=1)

    status_started = time.monotonic()
    status = call_docs_tool_payload("docs_status", {"action": "job", "job_id": payload["job_id"]}, service)
    assert time.monotonic() - status_started < 1
    assert status["status"] == "running"
    assert status["job_id"] == payload["job_id"]

    agent.release.set()


def test_prepare_library_docs_resolves_curated_github_manifest_before_indexing(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    commit = "62137874ff26dd74d2fea80ff528a7fd9ca7a5e7"
    commit_response = MagicMock(status_code=200, content=b"{}")
    commit_response.json.return_value = {"sha": commit}
    listing_response = MagicMock(status_code=200, content=b"[]")
    listing_response.json.return_value = [
        {"path": "docs/index.md", "type": "file", "sha": "2" * 40, "size": 12}
    ]
    client = MagicMock()
    client.get.side_effect = [commit_response, listing_response]
    service.docs_targets.github_api_client_factory = lambda: nullcontext(client)

    payload = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "prefetch_library_docs",
            "library": "mcp",
            "ecosystem": "python",
            "version": "1.27.2",
        },
        service,
    )

    status = None
    for _ in range(50):
        status = service.get_docs_job_status(payload["job_id"])
        if status and status.status in {"succeeded", "failed"}:
            break
        time.sleep(0.02)

    assert status is not None
    assert status.status == "succeeded", status.message
    assert len(client.get.call_args_list) == 2
    manifest = agent.add_kwargs[0]["source_manifest"]
    assert manifest["complete"] is True
    assert manifest["truncated"] is False
    assert manifest["discovery"]["resolved_commit_sha"] == commit
    assert status.completed_pages == 1
    assert status.failed_pages == 0


def test_library_prefetch_rejects_non_boolean_curated_manifest_completion(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch, FakeAgent())
    info = service.resolve_library("mcp", ecosystem="python", version="1.27.2")
    assert info.library_id is not None
    record = service.registry.get(info.library_id, source_type="api")
    assert record is not None
    target_spec = dict(record.target_spec or {})
    target_spec["source_manifest"] = {
        **target_spec["source_manifest"],
        "complete": "true",
    }
    service.registry.restore(replace(record, target_spec=target_spec))
    resolver_calls = []

    def resolve(target):
        resolver_calls.append(target)
        return replace(
            target,
            source_manifest=normalize_resolved_github_manifest({
                "schema_version": 2,
                "official": True,
                "discovery": {
                    "kind": "github_directory",
                    "owner": "modelcontextprotocol",
                    "repository": "python-sdk",
                    "requested_ref": "62137874ff26dd74d2fea80ff528a7fd9ca7a5e7",
                    "resolved_commit_sha": "62137874ff26dd74d2fea80ff528a7fd9ca7a5e7",
                    "directory": "docs",
                },
                "documents": [
                    {"path": "docs/index.md", "git_blob_sha": "2" * 40, "size": 12}
                ],
                "complete": True,
                "truncated": False,
            }),
        )

    monkeypatch.setattr(service.docs_targets, "resolve_github_directory_target", resolve)

    with pytest.raises(ValueError, match="complete must be a boolean"):
        service.prefetch_docs(
            "mcp",
            ecosystem="python",
            versions=["1.27.2"],
            force_refresh=True,
        )

    assert resolver_calls == []


def test_prepare_library_docs_rejects_resolved_manifest_missing_documents(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch, FakeAgent())
    info = service.resolve_library("mcp", ecosystem="python", version="1.27.2")
    assert info.library_id is not None
    record = service.registry.get(info.library_id, source_type="api")
    assert record is not None
    target_spec = dict(record.target_spec or {})
    source_manifest = dict(target_spec["source_manifest"])
    source_manifest["discovery"] = {
        **source_manifest["discovery"],
        "resolved_commit_sha": "62137874ff26dd74d2fea80ff528a7fd9ca7a5e7",
    }
    source_manifest["complete"] = True
    source_manifest["truncated"] = False
    target_spec["source_manifest"] = source_manifest
    service.registry.restore(replace(record, target_spec=target_spec))
    resolver_calls = []

    def resolve(target):
        resolver_calls.append(target)
        return replace(
            target,
            source_manifest=normalize_resolved_github_manifest({
                **source_manifest,
                "documents": [
                    {"path": "docs/index.md", "git_blob_sha": "2" * 40, "size": 12}
                ],
            }),
        )

    monkeypatch.setattr(service.docs_targets, "resolve_github_directory_target", resolve)

    payload = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "prefetch_library_docs",
            "library": "mcp",
            "ecosystem": "python",
            "version": "1.27.2",
        },
        service,
    )

    status = None
    for _ in range(50):
        status = service.get_docs_job_status(payload["job_id"])
        if status and status.status in {"succeeded", "failed"}:
            break
        time.sleep(0.02)

    assert status is not None
    assert status.status == "failed"
    assert status.message == "documents must be a list"
    assert resolver_calls == []


def test_successful_library_prefetch_atomically_publishes_staged_index(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch, FakeAgent())
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )

    for _ in range(100):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "succeeded":
            break
        time.sleep(0.02)

    record = service.registry.get("example-docs", "web", "latest")
    assert record is not None
    assert status is not None
    assert status.status == "succeeded"
    assert service.library_docs.registry_ops.count_index_entries(record) == (1, 1)


@pytest.mark.parametrize(
    ("retrieval_mode", "expected_sync_calls"),
    [("lexical", 0), ("hybrid", 1)],
)
def test_staged_prefetch_syncs_vectors_only_from_production_index(
    tmp_path, monkeypatch, retrieval_mode, expected_sync_calls
):
    agent = VectorTrackingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.config.retrieval.default_mode = retrieval_mode
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )

    for _ in range(100):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "succeeded":
            break
        time.sleep(0.02)

    assert status is not None
    assert status.status == "succeeded"
    assert agent.add_kwargs[0]["with_vectors"] is False
    assert agent.sync_calls == expected_sync_calls
    assert agent.prepare_calls == expected_sync_calls
    if expected_sync_calls:
        assert Path(agent.sync_db_paths[0]).parent.name.startswith(".docatlas-staging-")


def test_unchanged_forced_prefetch_skips_second_vector_sync(tmp_path, monkeypatch):
    agent = VectorTrackingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.config.retrieval.default_mode = "hybrid"

    first = service.prefetch_docs(
        "example-docs", ecosystem="web", docs_url="https://example.com/docs/", async_=True,
    )
    for _ in range(100):
        first_status = service.get_docs_job_status(first.job_id)
        if first_status and first_status.status == "succeeded":
            break
        time.sleep(0.02)

    second = service.prefetch_docs(
        "example-docs", ecosystem="web", docs_url="https://example.com/docs/",
        force_refresh=True, async_=True,
    )
    for _ in range(100):
        second_status = service.get_docs_job_status(second.job_id)
        if second_status and second_status.status == "succeeded":
            break
        time.sleep(0.02)

    assert first_status is not None and first_status.status == "succeeded"
    assert second_status is not None and second_status.status == "succeeded"
    assert "corpus_unchanged" in second_status.message
    assert agent.sync_calls == 1


def test_cancelled_staged_prefetch_never_syncs_vectors(tmp_path, monkeypatch):
    agent = SlowVectorTrackingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.config.retrieval.default_mode = "hybrid"
    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )

    assert agent.entered.wait(timeout=1)
    service.cancel_docs_job(result.job_id)
    agent.release.set()
    for _ in range(30):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.02)

    assert agent.sync_calls == 0


def test_vector_sync_failure_redacts_valid_identifier_secret_from_durable_status(tmp_path, monkeypatch):
    agent = VectorTrackingAgent(fail_sync=True)
    service = _service(tmp_path, monkeypatch, agent)
    service.config.retrieval.default_mode = "hybrid"
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

    record = service.registry.get("example-docs", "web", "latest")
    assert record is not None
    assert status is not None
    assert status.status == "failed"
    assert status.reason_code == "vector_indexing_failed"
    assert "vector_indexing_failed" in status.message
    assert "vector-sync-secret" not in status.message
    assert status.failure_phase == "staging"
    assert status.failure_operation == "sync_vectors"
    assert status.exception_type == "<redacted exception type>"
    assert status.exception_message == "<redacted diagnostic text>"
    assert status.exception_traceback == "<redacted traceback>"
    assert "type-secret" not in status.exception_type
    assert "aws_secret_access_key_leaked_value" not in status.exception_type
    assert "other-secret" not in status.exception_traceback
    assert "vector-sync-secret" not in status.exception_traceback
    assert "aws-env-secret" not in status.exception_message
    assert "aws-env-secret" not in status.exception_traceback
    assert "authorization-secret" not in status.exception_message
    assert "authorization-secret" not in status.exception_traceback
    assert len(status.exception_traceback) <= 4000
    assert service.library_docs.registry_ops.count_index_entries(record) == (0, 0)


def test_vector_sync_failure_retains_existing_active_corpus(tmp_path, monkeypatch):
    agent = VectorTrackingAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.config.retrieval.default_mode = "hybrid"

    initial = service.prefetch_docs(
        "example-docs", ecosystem="web", docs_url="https://example.com/docs/", async_=True,
    )
    for _ in range(30):
        initial_status = service.get_docs_job_status(initial.job_id)
        if initial_status and initial_status.status == "succeeded":
            break
        time.sleep(0.02)
    record_before = service.registry.get("example-docs", "web", "latest")
    assert record_before is not None
    assert service.library_docs.registry_ops.count_index_entries(record_before) == (1, 1)
    refreshed_before = record_before.last_refreshed_at

    agent.fail_sync = True
    agent.document_content = "# Guide\nChanged content that requires a new vector generation."
    failed = service.prefetch_docs(
        "example-docs", ecosystem="web", docs_url="https://example.com/docs/",
        force_refresh=True, async_=True,
    )
    for _ in range(30):
        failed_status = service.get_docs_job_status(failed.job_id)
        if failed_status and failed_status.status == "failed":
            break
        time.sleep(0.02)

    record_after = service.registry.get("example-docs", "web", "latest")
    assert failed_status is not None
    assert failed_status.status == "failed"
    assert record_after is not None
    assert record_after.status == record_before.status
    assert record_after.target_spec == record_before.target_spec
    assert record_after.last_refreshed_at == refreshed_before
    assert service.library_docs.registry_ops.count_index_entries(record_after) == (1, 1)


def test_skipped_vector_sync_never_publishes_hybrid_library_index(tmp_path, monkeypatch):
    agent = VectorTrackingAgent(skip_sync=True)
    service = _service(tmp_path, monkeypatch, agent)
    service.config.retrieval.default_mode = "hybrid"

    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )
    for _ in range(50):
        status = service.get_docs_job_status(result.job_id)
        if status and status.status == "failed":
            break
        time.sleep(0.02)

    record = service.registry.get("example-docs", "web", "latest")
    assert status is not None
    assert status.status == "failed"
    assert status.reason_code == "vector_indexing_failed"
    assert record is not None
    assert service.library_docs.registry_ops.count_index_entries(record) == (0, 0)


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
    status = service.get_docs_job_status(result.job_id)
    assert status is not None
    assert status.status == "cancelling"
    agent.release.set()
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


def test_cross_service_durable_cancellation_stops_active_library_prefetch(tmp_path, monkeypatch):
    agent = SlowIndexingAgent()
    active_service = _service(tmp_path, monkeypatch, agent, durable_jobs=True)
    cancelling_service = LibraryDocsService(
        config=active_service.config,
        registry=active_service.registry,
        agent=agent,
        agent_factory=active_service.agent_gateway._agent_factory,
    )
    result = active_service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
        async_=True,
    )

    assert agent.entered.wait(timeout=1)
    cancelling_service.cancel_docs_job(result.job_id)
    try:
        assert active_service.jobs.cancellation_requested(result.job_id)
    finally:
        agent.release.set()

    status = None
    for _ in range(30):
        status = active_service.get_docs_job_status(result.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.02)
    assert status is not None
    assert status.status == "cancelled"
    record = active_service.registry.get("example-docs", "web", "latest")
    assert record is not None
    assert active_service.library_docs.registry_ops.count_index_entries(record) == (0, 0)
