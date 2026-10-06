from __future__ import annotations

from dataclasses import replace
from contextlib import nullcontext
import hashlib
import ipaddress
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import httpx
import pytest

from docmancer.agent import DocmancerAgent
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.connectors.fetchers.web import WebFetcher
from docmancer.docs.models import DocsTarget, RefreshResult
from docmancer.docs.application.docs_target_service import DocsTargetService
from docmancer.docs.fetch_transport import DocsHttpClient
from docmancer.docs.github_source_manifest import normalize_resolved_github_manifest
from tests._shared_test_docs_service import _service

ROOT = "https://example.com/docs/ru/blog?source=v1&ref=explicit"
ROBOTS = "https://example.com/robots.txt"


class IndexFixtureAgent(DocmancerAgent):
    """Real caller/fetcher with offline local fixture indexing, no embeddings."""
    def __init__(self):
        self.calls = []
        self.after_index = None
        self.vector_failure = False

    @property
    def store(self):
        return SQLiteStore(self.config.index.db_path, self.config.index.extracted_dir)

    def add(self, url, recreate=False, **kwargs):
        self.calls.append((url, kwargs, self.config.index.db_path))
        return super().add(url, recreate=recreate, **kwargs)

    def ingest_documents(self, documents, recreate=False, with_vectors=True):
        result = self.store.add_documents(documents, recreate=recreate)
        if self.after_index:
            self.after_index()
        return result.sections

    def prepare_vector_generation(self):
        pass

    def sync_vectors(self):
        if self.vector_failure:
            raise RuntimeError("fixture vector failure")
        self.last_vector_sync_metrics = {"status": "success"}
        return 1

    def discard_vector_generation(self):
        pass


@pytest.fixture
def transport(monkeypatch):
    calls = []
    responses = {ROBOTS: "User-agent: *\nAllow: /\nSitemap: https://evil.test/sitemap.xml"}
    monkeypatch.setattr("docmancer.docs.fetch_policy.resolve_host", lambda host: (ipaddress.ip_address("93.184.216.34"),))

    def handler(request):
        url = f"{request.url.scheme}://{request.headers['host']}{request.url.raw_path.decode('ascii')}"
        calls.append(url)
        value = responses.get(url, "# Selected documentation\n\nExact finite fixture content without discovery.")
        if isinstance(value, tuple):
            return httpx.Response(value[0], headers={"location": value[1]}, request=request)
        return httpx.Response(200, content=value, headers={"content-type": "text/plain"}, request=request)

    def client(fetcher, policy=None):
        return DocsHttpClient(
            httpx.Client(transport=httpx.MockTransport(handler)), policy or fetcher._fetch_policy,
            pin_resolved_ips=False, max_redirects=fetcher._max_redirects,
            max_response_bytes=fetcher._max_response_bytes,
            max_decoded_text_bytes=fetcher._max_decoded_text_bytes,
            deadline_at=getattr(fetcher, "_operation_deadline_at", fetcher._deadline_at),
        )

    monkeypatch.setattr(WebFetcher, "_new_client", client)
    return calls, responses, handler


@pytest.fixture
def service(tmp_path, monkeypatch):
    agent = IndexFixtureAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.config.retrieval.default_mode = "lexical"
    return service, agent


def _target(**kwargs):
    return DocsTarget(library="finite", ecosystem="web", version="v1", docs_url=ROOT,
                      seed_urls=[ROBOTS], allowed_domains=["example.com"], path_prefixes=["/"], **kwargs)


def _sources(service, record):
    config = service._index_config_for(record)
    with sqlite3.connect(config.index.db_path) as conn:
        return {row[0] for row in conn.execute("SELECT source FROM sources")}


def _snapshot(service, record):
    config = service._index_config_for(record)
    path = Path(config.index.db_path)
    return (hashlib.sha256(path.read_bytes()).hexdigest(), service.registry.get(record.library_id))


@pytest.mark.parametrize("ecosystem", ["pub", "dart", "flutter", None])
@pytest.mark.parametrize("async_", [False, True])
def test_missing_explicit_target_never_guesses_package_roots(ecosystem, async_, service, transport):
    facade, agent = service
    result = facade.prefetch_docs("flutter" if ecosystem == "flutter" else "package", ecosystem=ecosystem,
                                   versions=["1.2.3"], query="literal", async_=async_)
    assert result.status == "needs_explicit_target"
    assert result.targets_failed == 1
    assert transport[0] == [] and agent.calls == []
    assert facade.jobs.list() == []


def test_raw_urls_do_not_synthesize_ceilings_or_robots_permission(service, transport):
    facade, agent = service
    for operation in (facade.prefetch_docs, facade.refresh_docs):
        result = operation("finite", docs_url=ROOT)
        assert result.status == "needs_explicit_target"
    assert transport[0] == [] and agent.calls == []


def test_typed_target_prefetch_refresh_persists_exact_contract(service, transport):
    facade, agent = service
    target = _target()
    result = facade.prefetch_docs("finite", target=target, force_refresh=True)
    assert result.status == "updated"
    record = facade.registry.get(result.library_id)
    assert record.target_spec["docs_url"] == ROOT
    assert record.target_spec["seed_urls"] == [ROBOTS]
    assert record.target_spec["allowed_domains"] == ["example.com"]
    assert record.target_spec["path_prefixes"] == ["/"]
    assert _sources(facade, record) == {ROOT, ROBOTS}

    transport[0].clear()
    persisted = facade.refresh_docs("finite", ecosystem="web", version="v1", force=True)
    assert persisted.status in {"updated", "skipped"}
    assert set(transport[0]) == {ROOT, ROBOTS}
    assert set(transport[0]) == {ROOT, ROBOTS}
    assert all(kwargs["exact_urls"] == [url] and kwargs["robots_urls"] == [ROBOTS]
               for url, kwargs, _ in agent.calls)
    transport[0].clear()
    result = facade.refresh_docs("finite", version="v1", target=target, force=True)
    assert result.status in {"updated", "skipped"}
    assert set(transport[0]) == {ROOT, ROBOTS}
    assert _sources(facade, record) == {ROOT, ROBOTS}


@pytest.mark.parametrize("kind", ["host", "path", "missing_robots", "empty", "template_without_version", "unhashed_github"])
def test_invalid_typed_selection_rejected_before_http_and_registration(kind, service, transport):
    facade, _ = service
    target = _target()
    if kind == "host":
        target = replace(target, docs_url="https://evil.test/docs")
    elif kind == "path":
        target = replace(target, docs_url="https://example.com/docs-other", path_prefixes=["/docs"])
    elif kind == "missing_robots":
        target = replace(target, seed_urls=[])
    elif kind == "empty":
        target = replace(target, docs_url=None, seed_urls=[])
    elif kind == "template_without_version":
        target = replace(target, docs_url=None, docs_url_template="https://example.com/{version}/docs", version=None)
    else:
        target = replace(target, docs_url="https://github.com/o/r/blob/main/docs/a.md", allowed_domains=["github.com"], seed_urls=[])
    result = facade.prefetch_docs("finite", target=target)
    assert result.status == "needs_explicit_target"
    assert transport[0] == []
    assert facade.registry.get("finite", "web", target.version) is None


@pytest.mark.parametrize("kwargs", [{"library": "other"}, {"ecosystem": "pub"}, {"versions": ["v2"]}, {"docs_url": ROOT + "&source=v2"}, {"source_type": "guides"}])
def test_target_identity_mismatch_never_fetches(kwargs, service, transport):
    facade, _ = service
    arguments = {"library": "finite", "target": _target(), **kwargs}
    result = facade.prefetch_docs(**arguments)
    assert result.status == "needs_explicit_target"
    assert result.reason_codes == ["explicit_target_identity_mismatch"]
    assert transport[0] == []


def _manifest(raw=b"# Immutable selected file\n", requested_ref="v1"):
    return normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "o", "repository": "r", "requested_ref": requested_ref,
                      "resolved_commit_sha": "1" * 40, "directory": "docs"},
        "documents": [{"path": "docs/ru/legacy/CHANGELOG.md", "size": len(raw),
                       "git_blob_sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}],
        "complete": True, "truncated": False,
    })


def test_approved_manifest_positive_validates_without_discovery_and_ingests_exact_rows(service, transport):
    facade, _ = service
    manifest = _manifest()
    row = manifest["documents"][0]
    transport[1][row["raw_url"]] = b"# Immutable selected file\n"
    target = DocsTarget(library="finite", ecosystem="web", version="v1", docs_url=row["blob_url"].replace("1" * 40, "v1"),
                        allowed_domains=["github.com"], path_prefixes=["/o/r/blob/"], source_manifest=manifest)
    facade.docs_targets.github_api_client_factory = lambda: pytest.fail("directory resolution")
    resolved = facade.docs_targets.resolve_github_directory_target(target)
    assert resolved.source_manifest == manifest and transport[0] == []
    result = facade.prefetch_docs("finite", target=target, force_refresh=True)
    assert result.status == "updated"
    record = facade.registry.get(result.library_id)
    assert _sources(facade, record) == {row["blob_url"]}
    assert record.target_spec["active_manifest_digest"] == manifest["digest"]
    assert record.target_spec["source_manifest"] == manifest
    assert transport[0] == [row["raw_url"]]
    refreshed = facade.refresh_docs("finite", target=target, force=True)
    assert refreshed.status in {"updated", "skipped"}
    assert transport[0] == [row["raw_url"], row["raw_url"]]


@pytest.mark.parametrize("kind", ["absent", "directory", "wrong_ref", "wrong_host", "wrong_path", "incomplete"])
def test_callable_github_resolution_never_expands_unapproved_files(kind, service, transport):
    facade, _ = service
    manifest = _manifest()
    target = DocsTarget(library="finite", docs_url=manifest["documents"][0]["blob_url"].replace("1" * 40, "v1"), allowed_domains=["github.com"], path_prefixes=["/o/r/blob/"], source_manifest=manifest)
    if kind == "absent":
        target = replace(target, source_manifest={})
    elif kind == "directory":
        target = replace(target, source_manifest={"schema_version": 2, "official": True, "discovery": manifest["discovery"]})
    elif kind == "wrong_ref":
        target = replace(target, docs_url="https://github.com/o/r/blob/v2/docs/a.md")
    elif kind == "wrong_host":
        target = replace(target, allowed_domains=["evil.test"])
    elif kind == "wrong_path":
        target = replace(target, path_prefixes=["/o/r/blob/v2/"])
    else:
        target = replace(target, source_manifest={**manifest, "complete": False, "digest": None})
    facade.docs_targets.github_api_client_factory = lambda: pytest.fail("directory resolution")
    with pytest.raises(ValueError):
        facade.docs_targets.resolve_github_directory_target(target)
    assert transport[0] == []


def test_callable_package_discovery_is_metadata_only_no_normalization_or_network(service, transport):
    facade, _ = service
    target = DocsTarget(library="p", ecosystem="pub", version="1.0", docs_url="https://pub.dev/packages/p?ref=chosen", allowed_domains=["pub.dev"])
    assert facade.docs_targets.discover_pub_dartdoc_target(target, []) == target
    with pytest.raises(ValueError):
        facade.docs_targets.discover_pub_dartdoc_target(replace(target, docs_url=None), [])
    assert transport[0] == []


def test_transport_failure_retains_prior_index_and_exact_registry_snapshot(service, transport):
    facade, agent = service
    target = _target()
    initial = facade.prefetch_docs("finite", target=target, force_refresh=True)
    record = facade.registry.get(initial.library_id)
    before = _snapshot(facade, record)
    transport[1][ROOT] = (302, ROOT + "&ref=other")
    result = facade.refresh_docs("finite", target=target, force=True)
    assert result.status == "failed"
    assert _snapshot(facade, record) == before
    assert ROOT + "&ref=other" not in transport[0]


def test_incomplete_staging_cannot_publish_even_when_old_rows_cover_missing_member(service, transport):
    facade, _ = service
    target = _target()
    initial = facade.prefetch_docs("finite", target=target, force_refresh=True)
    record = facade.registry.get(initial.library_id)
    before = _snapshot(facade, record)
    transport[1][ROBOTS] = "User-agent: *\nDisallow: /docs"
    result = facade.refresh_docs("finite", target=target, force=True)
    assert result.status == "needs_explicit_target"
    assert result.reason_codes == ["finite_staging_incomplete"]
    assert _snapshot(facade, record) == before


def test_stale_extra_source_requires_separate_first_slice_fix_not_implicit_deletion(service, transport):
    facade, agent = service
    target = _target()
    initial = facade.prefetch_docs("finite", target=target, force_refresh=True)
    record = facade.registry.get(initial.library_id)
    from docmancer.core.models import Document
    config = facade._index_config_for(record)
    SQLiteStore(config.index.db_path, config.index.extracted_dir).add_documents([Document(source="https://example.com/undeclared", content="# Old fixture\n", metadata={})])
    before = _snapshot(facade, record)
    result = facade.refresh_docs("finite", target=target, force=True)
    assert result.reason_codes == ["finite_staging_incomplete"]
    assert _snapshot(facade, record) == before
    cached = facade.prefetch_docs("finite", target=target, force_refresh=False)
    assert cached.reason_codes == ["finite_staging_incomplete"]
    assert _snapshot(facade, record) == before


def test_cancel_after_staged_fetch_cannot_publish(service, transport):
    facade, agent = service
    target = _target()
    initial = facade.prefetch_docs("finite", target=target, force_refresh=True)
    record = facade.registry.get(initial.library_id)
    before = _snapshot(facade, record)
    cancelled = [False]
    agent.after_index = lambda: cancelled.__setitem__(0, True)
    result = facade.library_docs._prefetch_explicit_targets([target], force_refresh=True, should_cancel=lambda: cancelled[0])
    assert result.status == "cancelled"
    assert _snapshot(facade, record) == before


def test_registry_commit_failure_rolls_back_active_index_and_selection(service, transport, monkeypatch):
    facade, _ = service
    target = _target()
    initial = facade.prefetch_docs("finite", target=target, force_refresh=True)
    record = facade.registry.get(initial.library_id)
    before = _snapshot(facade, record)
    transport[1][ROOT] = "# Changed selected documentation\n\nNew fixture content."
    upsert = facade.registry.upsert

    def fail_commit(**kwargs):
        if kwargs.get("status") == "available" and kwargs.get("last_refreshed_at"):
            raise RuntimeError("fixture registry commit failure")
        return upsert(**kwargs)

    monkeypatch.setattr(facade.registry, "upsert", fail_commit)
    with pytest.raises(RuntimeError, match="fixture registry commit failure"):
        facade.refresh_docs("finite", target=target, force=True)
    assert _snapshot(facade, record) == before


class DeferredExecutor:
    def __init__(self, available=True):
        self.available = available
        self.work = []
        self.capacity_result = SimpleNamespace(queue_position=1, running=0, queued=1, max_running=1, max_queued=2)

    def try_reserve(self):
        return self.available

    def capacity(self):
        return self.capacity_result

    def release_reservation(self):
        pass

    def submit_reserved(self, work, **kwargs):
        self.work.append((work, kwargs))
        return self.capacity_result


def test_queue_capacity_rejects_before_registration_or_http(service, transport):
    facade, _ = service
    executor = DeferredExecutor(available=False)
    facade.library_docs.job_executor = executor
    result = facade.prefetch_docs("finite", target=_target(), async_=True)
    assert result.status == "busy"
    assert facade.jobs.get(result.job_id).reason_code == "busy"
    assert facade.registry.get("finite", "web", "v1") is None
    assert transport[0] == []


def test_async_explicit_target_keeps_snapshot_commit_guards_and_query_identity(service, transport):
    facade, _ = service
    executor = DeferredExecutor()
    facade.library_docs.job_executor = executor
    target = _target()
    first = facade.prefetch_docs("finite", target=target, force_refresh=True, async_=True)
    second = facade.prefetch_docs("finite", target=replace(target, docs_url=ROOT + "&source=v2"), async_=True)
    assert facade.jobs.get(first.job_id).request_identity != facade.jobs.get(second.job_id).request_identity
    target.seed_urls.append("https://evil.test/extra")
    executor.work[0][0]()
    job = facade.jobs.get(first.job_id)
    assert job.status == "succeeded" and job.reason_code == "healthy"
    assert set(transport[0]) == {ROOT, ROBOTS}
    assert facade.registry.get("finite", "web", "v1").target_spec["seed_urls"] == [ROBOTS]


def test_queued_cancellation_has_no_fetch_or_registration(service, transport):
    facade, _ = service
    executor = DeferredExecutor()
    facade.library_docs.job_executor = executor
    result = facade.prefetch_docs("finite", target=_target(), async_=True)
    facade.jobs.cancel(result.job_id)
    executor.work[0][0]()
    assert facade.jobs.get(result.job_id).status == "cancelled"
    assert facade.registry.get("finite", "web", "v1") is None
    assert transport[0] == []


def test_inspection_only_fetches_selected_urls_and_never_follows_navigation(service, transport, monkeypatch):
    facade, _ = service
    transport[1][ROOT] = '<html><body><a href="/docs/extra">Extra</a></body></html>'
    real_client = httpx.Client
    monkeypatch.setattr("docmancer.docs.application.docs_target_service.httpx.Client", lambda **kwargs: real_client(transport=httpx.MockTransport(transport[2])))
    target = replace(_target(), seed_urls=[])
    result = facade.docs_targets.inspect_docs_target(target)
    assert result.observations["indexed"] is False
    assert result.observations["scope_expanded"] is False
    assert transport[0] == [ROOT]
    assert facade.registry.get("finite", "web", "v1") is None


def test_queued_deadline_terminalizes_without_fetch_or_registration(service, transport):
    facade, _ = service
    executor = DeferredExecutor()
    facade.library_docs.job_executor = executor
    result = facade.prefetch_docs("finite", target=_target(), async_=True)
    executor.work[0][1]["terminalize"]("deadline")
    executor.work[0][0]()
    job = facade.jobs.get(result.job_id)
    assert job.status == "failed" and job.reason_code == "job_deadline_exceeded"
    assert job.retryable is True
    assert facade.registry.get("finite", "web", "v1") is None
    assert transport[0] == []


def test_async_cancel_after_staging_preserves_active_index_and_registry(service, transport):
    facade, agent = service
    target = _target()
    initial = facade.prefetch_docs("finite", target=target, force_refresh=True)
    record = facade.registry.get(initial.library_id)
    before = _snapshot(facade, record)
    executor = DeferredExecutor()
    facade.library_docs.job_executor = executor
    job = facade.prefetch_docs("finite", target=target, force_refresh=True, async_=True)
    agent.after_index = lambda: facade.jobs.cancel(job.job_id)
    executor.work[0][0]()
    assert facade.jobs.get(job.job_id).status == "cancelled"
    assert _snapshot(facade, record) == before


def test_vector_failure_never_publishes_candidate(service, transport):
    facade, agent = service
    target = _target()
    initial = facade.prefetch_docs("finite", target=target, force_refresh=True)
    record = facade.registry.get(initial.library_id)
    before = _snapshot(facade, record)
    transport[1][ROOT] = "# Changed documentation\n\nDistinct staging candidate."
    facade.config.retrieval.default_mode = "hybrid"
    agent.vector_failure = True
    result = facade.refresh_docs("finite", target=target, force=True)
    assert result.status == "failed"
    assert result.reason_codes == ["vector_indexing_failed"]
    assert _snapshot(facade, record) == before


def test_unknown_target_port_result_cannot_claim_healthy(service, transport):
    from docmancer.docs.application.library_ingest_orchestrator import LibraryIngestOrchestrator

    facade, _ = service
    ports = replace(facade.library_docs.ingest_orchestrator.ports,
                    prefetch_targets=lambda *a, **k: RefreshResult(library_id=None, status="invented", docs_url=ROOT, last_refreshed_at=None))
    orchestrator = LibraryIngestOrchestrator(ports)
    result = orchestrator.prefetch_docs("finite", target_plan=[_target()])
    assert result.status == "needs_explicit_target"
    assert result.reason_codes == ["unknown_target_result"]
    assert transport[0] == []


def test_inspection_redirect_cannot_dispatch_to_unselected_query(service, transport, monkeypatch):
    facade, _ = service
    transport[1][ROOT] = (302, ROOT + "&ref=other")
    real_client = httpx.Client
    monkeypatch.setattr("docmancer.docs.application.docs_target_service.httpx.Client", lambda **kwargs: real_client(transport=httpx.MockTransport(transport[2])))
    result = facade.docs_targets.inspect_docs_target(replace(_target(), seed_urls=[]))
    assert result.status == "failed"
    assert result.pages[0]["reason_code"] == "url_not_selected"
    assert transport[0] == [ROOT]
