"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

@pytest.mark.parametrize("document_count", [0])
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


