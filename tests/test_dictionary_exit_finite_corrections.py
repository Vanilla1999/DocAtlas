"""Offline regressions for the separately allocated finite-contract corrections."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import ipaddress

import httpx
import pytest

from docmancer.connectors.fetchers.github import Context7Config, GitHubFetcher
from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError
from docmancer.docs.fetch_transport import DocsHttpClient
from docmancer.docs.finite_membership import preflight_target_urls
from docmancer.docs.github_source_manifest import normalize_resolved_github_manifest
from docmancer.docs.models import DocsTarget
from tests._shared_test_docs_service import _service
from tests.test_dictionary_exit_finite_corpus import ROOT, ROBOTS, _agent, offline_http


@pytest.mark.parametrize("url", [
    ROOT + "?meaning=é", ROOT + "/é", "https://éxample.com/docs",
    ROOT + "?", ROOT + "#", "https://example.com:443/docs",
    ROOT + "/{entity}", "https://example.com\\evil.test/docs",
])
def test_actual_agent_factory_web_rejects_transport_unstable_selection_before_http(url, offline_http):
    calls, _ = offline_http
    with pytest.raises((ValueError, DocsFetchSecurityError)):
        _agent().add(url, exact_urls=[url], robots_urls=[ROBOTS], with_vectors=False)
    assert calls == []


@pytest.mark.parametrize("url", [
    ROOT + "?meaning=%C3%A9", ROOT + "/%C3%A9",
    ROOT + "/?source=v1&ref=v2&from=v3&utm_source=explicit",
])
def test_actual_serialized_request_preserves_selected_spelling(url, offline_http):
    calls, _ = offline_http
    agent = _agent()
    assert agent.add(url, exact_urls=[url], robots_urls=[ROBOTS], with_vectors=False) == 1
    assert calls == [ROBOTS, url]
    assert agent.documents[0].source == url


@pytest.mark.parametrize("mode", ["argument", "client_default"])
def test_transport_checks_effective_query_before_mock_dispatch(mode, monkeypatch):
    calls = []
    monkeypatch.setattr("docmancer.docs.fetch_policy.resolve_host", lambda host: (ipaddress.ip_address("93.184.216.34"),))
    raw = httpx.Client(
        transport=httpx.MockTransport(lambda request: calls.append(str(request.url)) or httpx.Response(200, text="exact", request=request)),
        params={"ref": "unselected"} if mode == "client_default" else None,
    )
    policy = DocsFetchPolicy(allowed_hosts=("example.com",), exact_urls=(ROOT,))
    with DocsHttpClient(raw, policy, pin_resolved_ips=False) as client:
        with pytest.raises(DocsFetchSecurityError, match="url_not_selected"):
            client.get(ROOT, **({"params": {"ref": "unselected"}} if mode == "argument" else {}))
    assert calls == []


def _manifest(path="docs/a.md", commit="1" * 40):
    raw = b"# Approved\n"
    return normalize_resolved_github_manifest({
        "schema_version": 2, "official": True, "complete": True, "truncated": False,
        "discovery": {"kind": "github_directory", "owner": "o", "repository": "r", "requested_ref": "v1", "resolved_commit_sha": commit, "directory": "docs"},
        "documents": [{"path": path, "git_blob_sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(), "size": len(raw)}],
    }), raw


@pytest.mark.parametrize("mutation", ["rows", "root", "digest", "replacement"])
def test_direct_github_constructor_snapshots_approved_root_rows_and_digest(mutation, offline_http):
    calls, responses = offline_http
    original, raw = _manifest()
    approved = deepcopy(original)
    fetcher = GitHubFetcher(source_manifest=original)
    extra, _ = _manifest("docs/ru/extra.md", "2" * 40)
    if mutation == "rows":
        original["documents"][0]["path"] = "docs/ru/extra.md"
    elif mutation == "root":
        original["discovery"]["resolved_commit_sha"] = "2" * 40
    elif mutation == "digest":
        original["digest"] = "0" * 64
    else:
        original.clear()
        original.update(extra)
    row = approved["documents"][0]
    responses[row["raw_url"]] = raw
    docs = fetcher.fetch(row["blob_url"])
    assert calls == [row["raw_url"]]
    assert docs[0].source == row["blob_url"]
    assert docs[0].metadata["resolved_commit_sha"] == "1" * 40
    assert docs[0].metadata["content_sha256"] == hashlib.sha256(raw).hexdigest()
    calls.clear()
    with pytest.raises(ValueError, match="seed_mismatch"):
        fetcher.fetch(extra["documents"][0]["blob_url"])
    assert calls == []


def test_direct_github_rejects_invalid_manifest_at_construction(offline_http):
    with pytest.raises(ValueError):
        GitHubFetcher(source_manifest={})
    assert offline_http[0] == []


@pytest.mark.parametrize("folder", ["docs", "./docs", "/docs/"])
def test_explicit_github_folder_grammar_has_no_implicit_root_extras(folder):
    assert GitHubFetcher()._select_documentation_files(
        ["README.md", "docs/a.md", "docs/ru/legacy.md", "docs-other/a.md"],
        Context7Config(folders=[folder]),
    ) == ["docs/a.md", "docs/ru/legacy.md"]


def _target(library="corrections"):
    return {"library": library, "docs_url": ROOT, "seed_urls": [ROOT + "/a?ref=v1", ROBOTS], "allowed_domains": ["example.com"], "path_prefixes": ["/"]}


@pytest.mark.parametrize("lane", ["prefetch", "refresh_core"])
@pytest.mark.parametrize("bad", ["fragment", "unicode", "binary", "path", "private_dns", "robots_missing", "malformed_hosts", "malformed_paths", "string_paths"])
def test_valid_first_invalid_later_target_never_dispatches(lane, bad, tmp_path, monkeypatch, offline_http):
    calls, _ = offline_http
    service = _service(tmp_path, monkeypatch, _agent())
    target = _target()
    if lane == "refresh_core":
        assert service.prefetch_docs_targets([target], force_refresh=True).status == "ok"
        record = service.registry.get("corrections")
        calls.clear()
    if bad == "fragment":
        target["seed_urls"][0] = ROOT + "/a#part"
    elif bad == "unicode":
        target["seed_urls"][0] = ROOT + "/a?version=é"
    elif bad == "binary":
        target["seed_urls"][0] = ROOT + "/a.pdf"
    elif bad == "path":
        target["seed_urls"][0] = "https://example.com/docs-other"
        target["path_prefixes"] = ["/docs", "/robots.txt"]
    elif bad == "private_dns":
        target["seed_urls"][0] = "https://private.example.com/docs"
        monkeypatch.setattr("docmancer.docs.fetch_policy.resolve_host", lambda host: (ipaddress.ip_address("127.0.0.1" if host.startswith("private") else "93.184.216.34"),))
    elif bad == "robots_missing":
        target["seed_urls"].remove(ROBOTS)
    elif bad == "malformed_hosts":
        target["allowed_domains"] = ["example.com", ""]
    elif bad == "malformed_paths":
        target["path_prefixes"] = ["/", ""]
    else:
        target["path_prefixes"] = "/"
    if lane == "prefetch":
        result = service.prefetch_docs_targets([target], force_refresh=True)
        assert result.results[0].status == "failed"
    else:
        # Exercise the original refresh core, independent of concurrently owned wrappers.
        spec = {**record.target_spec, **target}
        result = service._refresh_record_unlocked(replace(record, target_spec=spec), force=True)
        assert result.status == "failed"
    assert calls == []


def test_valid_whole_set_prefetch_and_refresh_core_keep_exact_sources(tmp_path, monkeypatch, offline_http):
    calls, _ = offline_http
    agent = _agent()
    service = _service(tmp_path, monkeypatch, agent)
    target = _target()
    expected = {ROOT, *target["seed_urls"]}
    assert service.prefetch_docs_targets([target], force_refresh=True).status == "ok"
    assert set(calls) == expected
    assert {doc.source for doc in agent.documents} == expected
    calls.clear()
    record = service.registry.get("corrections")
    # The indexing boundary is deliberately mocked; source fetching succeeds,
    # but this fixture cannot claim that a real index was published.
    assert service._refresh_record_unlocked(record, force=True).status == "empty_index"
    assert set(calls) == expected
    assert len(agent.documents) == 2 * len(expected)


def test_prefetch_snapshots_caller_collections_before_first_member(tmp_path, monkeypatch, offline_http):
    calls, _ = offline_http
    agent = _agent()
    service = _service(tmp_path, monkeypatch, agent)
    target = DocsTarget(**_target())
    selected = [ROOT, *target.seed_urls]
    original_ingest = agent.ingest_documents

    def ingest(documents, **kwargs):
        target.seed_urls[:] = ["https://evil.test/extra"]
        target.allowed_domains[:] = ["evil.test"]
        target.path_prefixes[:] = ["/extra"]
        return original_ingest(documents, **kwargs)

    agent.ingest_documents = ingest
    assert service.prefetch_docs_targets([target], force_refresh=True).status == "ok"
    assert set(calls) == set(selected)
    assert {doc.source for doc in agent.documents} == set(selected)


@pytest.mark.parametrize("kind", ["cancelled", "deadline"])
def test_whole_set_preflight_preserves_operation_stop_before_dispatch(kind, offline_http):
    with pytest.raises((RuntimeError, DocsFetchSecurityError)):
        preflight_target_urls(
            [ROOT, ROBOTS], max_pages=2, allowed_domains=["example.com"], path_prefixes=["/"],
            cancellation_callback=(lambda: True) if kind == "cancelled" else None,
            deadline_at=0 if kind == "deadline" else None,
        )
    assert offline_http[0] == []
