"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_inspect_library_docs_reports_complete_manifest_coverage(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-health", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={"source_manifest": manifest},
    )
    _add_manifest_documents(service, record, manifest)

    result = service.inspect_library_docs(record.library_id)

    assert result.status == "indexed"
    assert result.manifest_expected == 1
    assert result.manifest_indexed == 1
    assert result.manifest_missing == 0
    assert result.manifest_stale_orphans == 0
    assert result.active_manifest_digest == manifest["digest"]


def test_inspect_library_docs_exposes_complete_manifest_and_generation_identity(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-inspection", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        docs_url_template="https://github.com/acme/sample/blob/{version}/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={
            "source_manifest": manifest,
            "active_manifest_digest": manifest["digest"],
            "last_attempt_manifest_digest": manifest["digest"],
            "last_complete_manifest_digest": manifest["digest"],
            "ingestion_policy_version": 1,
        },
    )
    _add_manifest_documents(service, record, manifest, generation=True)

    result = service.inspect_library_docs(record.library_id)

    assert result.docs_url_template == "https://github.com/acme/sample/blob/{version}/docs/guide.md"
    assert result.manifest_fetched == 1
    assert result.requested_ref == "v1"
    assert result.resolved_commit_sha == "1" * 40
    assert result.manifest_complete is True
    assert result.manifest_truncated is False
    assert result.ingestion_policy_version == 1
    assert result.active_generation_id is not None
    assert result.active_generation_id.startswith("gen-")


def test_inspect_library_docs_marks_old_manifest_policy_needs_refresh(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-old-policy", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={"source_manifest": manifest, "ingestion_policy_version": 0},
    )
    _add_manifest_documents(service, record, manifest)

    result = service.inspect_library_docs(record.library_id)

    assert result.status == "needs_refresh"
    assert result.reason_code == "needs_refresh"


def test_inspect_library_docs_marks_incomplete_manifest_unhealthy(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [
            {"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12},
            {"path": "docs/extra.md", "git_blob_sha": "3" * 40, "size": 12},
        ],
        "complete": True,
        "truncated": False,
    })
    record = service.registry.upsert(
        library="manifest-incomplete", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={"source_manifest": manifest},
    )
    _add_manifest_documents(service, record, manifest, manifest["documents"][:1])
    store = SQLiteStore(
        service._index_config_for(record).index.db_path,
        service._index_config_for(record).index.extracted_dir,
    )
    store.add_documents([Document(
        source="https://github.com/acme/sample/blob/" + "1" * 40 + "/docs/stale.md",
        content="# stale\nWrong manifest source.",
        metadata={
            "canonical_url": "https://github.com/acme/sample/blob/" + "1" * 40 + "/docs/stale.md",
            "resolved_commit_sha": "1" * 40,
            "git_blob_sha": "4" * 40,
        },
    )])

    result = service.inspect_library_docs(record.library_id)

    assert result.status == "corpus_incomplete"
    assert result.reason_code == "corpus_incomplete"
    assert result.manifest_expected == 2
    assert result.manifest_indexed == 1
    assert result.manifest_missing == 1
    assert result.manifest_stale_orphans == 1


def test_inspect_library_docs_marks_truncated_manifest_unhealthy(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory", "owner": "acme", "repository": "sample",
            "requested_ref": "v1", "resolved_commit_sha": "1" * 40, "directory": "docs",
        },
        "documents": [{"path": "docs/guide.md", "git_blob_sha": "2" * 40, "size": 12}],
        "complete": False,
        "truncated": True,
    })
    record = service.registry.upsert(
        library="manifest-truncated", ecosystem="web", version="latest", source_type="guides",
        docs_url="https://github.com/acme/sample/blob/v1/docs/guide.md",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        target_spec={"source_manifest": manifest},
    )
    _add_manifest_documents(service, record, manifest)

    result = service.inspect_library_docs(record.library_id)

    assert result.status == "corpus_incomplete"
    assert result.reason_code == "corpus_incomplete"
    assert result.manifest_expected == 1
    assert result.manifest_indexed == 1
    assert result.manifest_missing == 0


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


def test_cancel_docs_job_during_fetch_finishes_cancelled_and_removes_new_record(tmp_path, monkeypatch):
    class CooperativeAgent(FakeAgent):
        def __init__(self):
            super().__init__()
            self.entered = Event()

        def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
            self.add_calls.append(docs_url)
            self.add_kwargs.append(kwargs)
            self.entered.set()
            cancellation_callback = kwargs["cancellation_callback"]
            for _ in range(100):
                if cancellation_callback():
                    raise RuntimeError("Documentation ingestion cancelled before indexing.")
                time.sleep(0.01)
            return 1

    agent = CooperativeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    started = service.prefetch_docs_targets(
        [{
            "library": "cancelled-guides",
            "ecosystem": "web",
            "docs_url": "https://example.com/docs/",
            "allowed_domains": ["example.com"],
        }],
        async_=True,
    )
    assert agent.entered.wait(timeout=1)

    service.cancel_docs_job(started.job_id)
    for _ in range(100):
        status = service.get_docs_job_status(started.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.01)

    status = service.get_docs_job_status(started.job_id)
    assert status is not None
    assert status.status == "cancelled"
    assert status.phase == "done"
    assert service.registry.get("cancelled-guides", ecosystem="web", source_type="api") is None


def test_cancel_docs_job_during_discovery_finishes_cancelled(tmp_path, monkeypatch):
    entered = Event()
    release = Event()
    service = _service(tmp_path, monkeypatch)

    def discover(target, warnings, job_id=None, canonical_id=None):
        entered.set()
        release.wait(timeout=1)
        raise RuntimeError("discovery cancelled")

    monkeypatch.setattr(service, "_discover_pub_dartdoc_target", discover)
    started = service.prefetch_docs_targets(
        [{
            "library": "cancelled-discovery",
            "ecosystem": "pub",
            "version": "1.0.0",
            "docs_url": "https://pub.dev/documentation/cancelled-discovery/1.0.0/",
            "allowed_domains": ["pub.dev"],
        }],
        async_=True,
    )
    assert entered.wait(timeout=1)

    service.cancel_docs_job(started.job_id)
    release.set()
    for _ in range(100):
        status = service.get_docs_job_status(started.job_id)
        if status and status.status == "cancelled":
            break
        time.sleep(0.01)

    status = service.get_docs_job_status(started.job_id)
    assert status is not None
    assert status.status == "cancelled"
    assert status.phase == "done"


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


def test_prefetch_docs_targets_rejects_empty_index(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch, ZeroPageAgent())

    result = service.prefetch_docs_targets([
        {
            "library": "empty-guides",
            "docs_url": "https://example.com/docs/",
            "allowed_domains": ["example.com"],
        }
    ])

    assert result.status == "failed"
    assert result.results[0].status == "failed"
    assert result.results[0].message == "empty_index: target produced no indexable documentation"


def test_prefetch_docs_targets_reports_degraded_discovery_as_partial(tmp_path, monkeypatch):
    class PartialAgent(FakeAgent):
        def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
            pages = super().add(docs_url, recreate=recreate, **kwargs)
            self.last_fetch_failure = None
            self.last_discovery_diagnostics = {
                "complete": False,
                "reason_code": "discovery_manifest_too_large",
            }
            return pages

    service = _service(tmp_path, monkeypatch, PartialAgent())

    result = service.prefetch_docs_targets([
        {
            "library": "flutter-api",
            "ecosystem": "flutter",
            "version": "stable",
            "docs_url": "https://api.flutter.dev/",
            "allowed_domains": ["api.flutter.dev"],
            "doc_format": "dartdoc",
        }
    ])

    assert result.status == "partial"
    assert result.results[0].status == "partial"
    assert result.results[0].pages_indexed == 1
    assert result.results[0].message == "partial ingestion: discovery_manifest_too_large, checkpoint_pending"


def test_prefetch_docs_targets_uses_page_ledger_for_partial_and_counters(tmp_path, monkeypatch):
    class LedgerAgent(FakeAgent):
        def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
            super().add(docs_url, recreate=recreate, **kwargs)
            self.last_fetch_failure = None
            self.last_discovery_diagnostics = {
                "complete": True,
                "reason_code": "ok",
                "page_failure_count": 1,
                "page_ledger": [
                    {"outcome": "usable"},
                    {"outcome": "usable"},
                    {"outcome": "failed", "reason_code": "http_failure"},
                ],
            }
            return 4

    service = _service(tmp_path, monkeypatch, LedgerAgent())

    result = service.prefetch_docs_targets([
        {
            "library": "partial-guides",
            "docs_url": "https://example.com/docs/",
            "allowed_domains": ["example.com"],
        }
    ])

    assert result.status == "partial"
    assert result.results[0].status == "partial"
    assert result.pages_indexed == 2
    assert result.pages_failed == 1
    assert result.chunks_indexed == 4


def test_prefetch_docs_targets_reports_zero_seed_as_partial(tmp_path, monkeypatch):
    class MixedSeedAgent(FakeAgent):
        empty_attempts = 0

        def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
            self.add_calls.append(docs_url)
            self.add_kwargs.append(kwargs)
            if docs_url.endswith("empty"):
                self.empty_attempts += 1
                return 0 if self.empty_attempts == 1 else 1
            return 1

    agent = MixedSeedAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs_targets([
        {
            "library": "mixed-guides",
            "seed_urls": ["https://example.com/docs/empty", "https://example.com/docs/ready"],
            "allowed_domains": ["example.com"],
            "path_prefixes": ["/docs/"],
        }
    ])

    assert result.status == "partial"
    assert result.results[0].status == "partial"
    assert result.results[0].message == "partial ingestion: empty_seed, checkpoint_pending"

    resumed = service.prefetch_docs_targets([{
        "library": "mixed-guides",
        "seed_urls": ["https://example.com/docs/empty", "https://example.com/docs/ready"],
        "allowed_domains": ["example.com"],
        "path_prefixes": ["/docs/"],
    }])

    assert resumed.status == "ok"
    assert agent.add_calls == [
        "https://example.com/docs/empty",
        "https://example.com/docs/ready",
        "https://example.com/docs/empty",
    ]
