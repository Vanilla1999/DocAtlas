from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy

import pytest

from docmancer.docs.application.docs_target_service import DocsTargetService
from docmancer.docs.github_source_manifest import (
    GitHubSourceManifestError,
    canonical_manifest_digest,
    normalize_resolved_github_manifest,
    resolve_github_directory_manifest,
)
from docmancer.docs.models import DocsTarget


COMMIT = "1" * 40


def _render(template: str, library: str, version: str) -> str:
    return template.format(library=library, version=version)


def test_schema_v1_round_trips_and_plain_github_blob_remains_single_page():
    service = DocsTargetService(_render)
    schema_v1 = {"schema_version": 1, "version_rule": "exact", "official": True}
    target = DocsTarget(
        library="sample",
        version="1.0",
        docs_url="https://github.com/acme/sample/blob/main/docs/guide.md",
        allowed_domains=["github.com"],
        path_prefixes=["/acme/sample/blob/"],
        source_manifest=deepcopy(schema_v1),
    )

    urls, error = service.target_urls(target)
    spec = service.target_to_spec(target, urls)

    assert error is None
    assert urls == [target.docs_url]
    assert spec["source_manifest"] == schema_v1


def test_resolved_directory_manifest_is_sorted_hashed_and_uses_canonical_identity():
    manifest = {
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory",
            "owner": "Kotlin",
            "repository": "kotlinx.coroutines",
            "requested_ref": "1.8.1",
            "resolved_commit_sha": COMMIT,
            "directory": "docs/topics",
        },
        "documents": [
            {
                "path": "docs/topics/z-last.mdx",
                "git_blob_sha": "3" * 40,
                "size": 30,
                "download_url": "https://attacker.invalid/ignored",
            },
            {
                "path": "docs/topics/a-first.md",
                "git_blob_sha": "2" * 40,
                "size": 20,
                "html_url": "https://attacker.invalid/ignored",
            },
        ],
        "complete": True,
        "truncated": False,
    }

    normalized = normalize_resolved_github_manifest(manifest)

    assert [row["path"] for row in normalized["documents"]] == [
        "docs/topics/a-first.md",
        "docs/topics/z-last.mdx",
    ]
    assert all(set(row) == {"path", "git_blob_sha", "size", "blob_url", "raw_url"} for row in normalized["documents"])
    assert normalized["documents"][0]["blob_url"] == (
        f"https://github.com/Kotlin/kotlinx.coroutines/blob/{COMMIT}/docs/topics/a-first.md"
    )
    assert normalized["documents"][0]["raw_url"] == (
        f"https://raw.githubusercontent.com/Kotlin/kotlinx.coroutines/{COMMIT}/docs/topics/a-first.md"
    )
    assert normalized["digest"] == canonical_manifest_digest(normalized)


def test_target_service_binds_manifest_to_explicit_approved_blob_scope():
    service = DocsTargetService(_render)
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory",
            "owner": "Kotlin",
            "repository": "kotlinx.coroutines",
            "requested_ref": "1.8.1",
            "resolved_commit_sha": COMMIT,
            "directory": "docs/topics",
        },
        "documents": [{
            "path": "docs/topics/guide.md",
            "git_blob_sha": "2" * 40,
            "size": 20,
        }],
        "complete": True,
        "truncated": False,
    })
    target = DocsTarget(
        library="kotlinx.coroutines",
        version="1.8.1",
        docs_url="https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/docs/topics/guide.md",
        allowed_domains=["github.com"],
        path_prefixes=["/Kotlin/kotlinx.coroutines/blob/"],
        source_manifest=manifest,
    )

    urls, error = service.target_urls(target)

    assert error is None
    assert urls == [manifest["documents"][0]["blob_url"]]


@pytest.mark.parametrize("approved", [
    "https://github.com/Kotlin/kotlinx.coroutines/blob/feature%2Fdocs/docs/topics/guide.md?x=1",
    "https://github.com/Kotlin/kotlinx.coroutines/blob/feature%2Fdocs/docs/topics/guide.md#x",
    "https://github.com/Kotlin/kotlinx.coroutines/blob/feature%2Fdocs/docs/topics/",
    "https://github.com/Kotlin/kotlinx.coroutines/blob/feature%2Fdocs/docs/topics",
    "https://github.com/Kotlin/kotlinx.coroutines/blob/feature%2Fdocs/docs/topics-evil/guide.md",
    "https://github.com/Kotlin/kotlinx.coroutines.evil/blob/feature%2Fdocs/docs/topics/guide.md",
    "https://github.com.evil/Kotlin/kotlinx.coroutines/blob/feature%2Fdocs/docs/topics/guide.md",
    "https://github.com/Kotlin/kotlinx.coroutines/blob/feature/docs/docs/topics/guide.md",
], ids=("query", "fragment", "directory-slash", "directory", "directory-prefix", "repo-prefix", "host-prefix", "noncanonical-ref"))
def test_target_service_rejects_noncanonical_or_prefix_confused_approved_blob(approved):
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "Kotlin", "repository": "kotlinx.coroutines",
                      "requested_ref": "feature/docs", "resolved_commit_sha": COMMIT, "directory": "docs/topics"},
        "documents": [], "complete": True, "truncated": False,
    })
    target = DocsTarget(library="x", docs_url=approved, source_manifest=manifest,
                        allowed_domains=["github.com"], path_prefixes=["/Kotlin/kotlinx.coroutines/blob/"])
    urls, error = DocsTargetService(_render).target_urls(target)
    assert urls == []
    assert error == "github directory manifest scope does not match approved blob target"


def test_target_service_accepts_canonical_encoded_ref_and_path_for_empty_manifest_seed():
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "Kotlin", "repository": "kotlinx.coroutines",
                      "requested_ref": "feature/docs", "resolved_commit_sha": COMMIT, "directory": "docs/topics"},
        "documents": [], "complete": True, "truncated": False,
    })
    approved = "https://github.com/Kotlin/kotlinx.coroutines/blob/feature%2Fdocs/docs/topics/my%20guide.md"
    target = DocsTarget(library="x", docs_url=approved, source_manifest=manifest,
                        allowed_domains=["github.com"], path_prefixes=["/Kotlin/kotlinx.coroutines/blob/"])
    urls, error = DocsTargetService(_render).target_urls(target)
    assert error is None
    assert urls == [approved]


@pytest.mark.parametrize(("changes", "message"), [
    ({"type": "symlink"}, "regular file"),
    ({"type": "submodule"}, "regular file"),
    ({"path": "docs/topics/../escape.md"}, "document path"),
    ({"path": "docs/topics/readme.txt"}, "markdown"),
    ({"git_blob_sha": "not-a-sha"}, "git_blob_sha"),
    ({"owner": "Attacker"}, "owner"),
    ({"repository": "replacement"}, "repository"),
    ({"resolved_commit_sha": "a" * 40}, "resolved_commit_sha"),
], ids=("symlink", "submodule", "path-escape", "non-doc", "bad-sha", "wrong-owner", "wrong-repository", "wrong-ref"))
def test_resolved_manifest_rejects_untrusted_or_out_of_scope_document_fields(
    changes: dict[str, object], message: str,
):
    document = {
        "path": "docs/topics/guide.md",
        "git_blob_sha": "2" * 40,
        "size": 20,
        **changes,
    }
    manifest = {
        "schema_version": 2,
        "official": True,
        "discovery": {
            "kind": "github_directory",
            "owner": "Kotlin",
            "repository": "kotlinx.coroutines",
            "requested_ref": "1.8.1",
            "resolved_commit_sha": COMMIT,
            "directory": "docs/topics",
        },
        "documents": [document],
        "complete": True,
        "truncated": False,
    }

    with pytest.raises(GitHubSourceManifestError, match=message):
        normalize_resolved_github_manifest(manifest)


class _Response:
    def __init__(self, payload, status_code=200):
        import json
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode()

    def json(self):
        return self._payload


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []
        self.timeouts = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        self.timeouts.append(kwargs.get("timeout"))
        return self.responses.pop(0)


def test_target_service_resolves_approved_directory_declaration_before_ingest():
    client = _Client([
        _Response({"sha": COMMIT}),
        _Response([{"path": "docs/topics/a.md", "type": "file", "sha": "2" * 40, "size": 1}]),
    ])
    service = DocsTargetService(_render, github_api_client_factory=lambda: nullcontext(client))
    target = DocsTarget(
        library="sample",
        docs_url="https://github.com/Kotlin/repo/blob/v1/docs/topics/a.md",
        allowed_domains=["github.com"],
        path_prefixes=["/Kotlin/repo/blob/"],
        source_manifest={
            "schema_version": 2,
            "official": True,
            "discovery": {
                "kind": "github_directory", "owner": "Kotlin", "repository": "repo",
                "requested_ref": "v1", "directory": "docs/topics",
            },
        },
    )

    resolved = service.resolve_github_directory_target(target)

    assert resolved.source_manifest["complete"] is True
    assert resolved.source_manifest["truncated"] is False
    assert resolved.source_manifest["discovery"]["resolved_commit_sha"] == COMMIT
    assert [document["path"] for document in resolved.source_manifest["documents"]] == ["docs/topics/a.md"]
    assert client.urls[0].endswith("/repos/Kotlin/repo/commits/v1")
    assert client.urls[1].endswith(f"/contents/docs/topics?ref={COMMIT}")


def test_resolver_pins_ref_before_bounded_recursive_listing_and_ignores_urls():
    client = _Client([
        _Response({"sha": COMMIT}),
        _Response([
            {"path": "docs/topics/deep", "type": "dir", "sha": "3" * 40, "size": 0, "url": "https://attacker.invalid"},
            {"path": "docs/topics/b.md", "type": "file", "sha": "2" * 40, "size": 2, "download_url": "https://attacker.invalid"},
        ]),
        _Response([{"path": "docs/topics/deep/a.mdx", "type": "file", "sha": "4" * 40, "size": 3}]),
    ])
    result = resolve_github_directory_manifest(client, owner="Kotlin", repository="kotlinx.coroutines", requested_ref="1.8.1", directory="docs/topics", max_api_requests=3)
    assert result["complete"] is True
    assert [d["path"] for d in result["documents"]] == ["docs/topics/b.md", "docs/topics/deep/a.mdx"]
    assert client.urls[0].endswith("/repos/Kotlin/kotlinx.coroutines/commits/1.8.1")
    assert client.urls[1].endswith(f"/contents/docs/topics?ref={COMMIT}")
    assert client.urls[2].endswith(f"/contents/docs/topics/deep?ref={COMMIT}")
    assert not any("attacker" in url for url in client.urls)
    assert all(timeout is not None and timeout > 0 for timeout in client.timeouts)


@pytest.mark.parametrize(("kwargs", "reason"), [
    ({"max_api_requests": 1}, "max_api_requests"),
    ({"max_entries_seen": 1}, "max_entries_seen"),
    ({"max_accepted_documents": 0}, "max_accepted_documents"),
    ({"max_api_response_bytes": 1}, "max_api_response_bytes"),
])
def test_resolver_fails_closed_for_independent_budgets(kwargs, reason):
    client = _Client([_Response({"sha": COMMIT}), _Response([
        {"path": "docs/topics/a.md", "type": "file", "sha": "2" * 40, "size": 1},
        {"path": "docs/topics/b.md", "type": "file", "sha": "3" * 40, "size": 1},
    ])])
    result = resolve_github_directory_manifest(client, owner="o", repository="r", requested_ref="v1", directory="docs/topics", **kwargs)
    assert result["complete"] is False
    assert result["reason_code"] == reason


def test_resolver_rejects_ambiguous_listing_and_cancellation():
    entries = [{"path": f"docs/topics/{i}.md", "type": "file", "sha": "2" * 40, "size": 1} for i in range(1000)]
    ambiguous = resolve_github_directory_manifest(_Client([_Response({"sha": COMMIT}), _Response(entries)]), owner="o", repository="r", requested_ref="v1", directory="docs/topics", max_entries_seen=2000, max_accepted_documents=2000)
    cancelled_client = _Client([])
    cancelled = resolve_github_directory_manifest(cancelled_client, owner="o", repository="r", requested_ref="v1", directory="docs/topics", cancellation_callback=lambda: True)
    assert ambiguous["reason_code"] == "ambiguous_listing"
    assert cancelled["reason_code"] == "cancelled"
    assert cancelled_client.urls == []


def test_manifest_rejects_digest_mismatch_strict_booleans_and_binds_empty_identity():
    base = {
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "o", "repository": "r",
                      "requested_ref": "v1", "resolved_commit_sha": COMMIT, "directory": "docs"},
        "documents": [], "complete": True, "truncated": False,
    }
    with pytest.raises(GitHubSourceManifestError, match="digest mismatch"):
        normalize_resolved_github_manifest({**base, "digest": "0" * 64})
    for field, value in (("official", 1), ("complete", 1), ("truncated", 0)):
        with pytest.raises(GitHubSourceManifestError, match=field):
            normalize_resolved_github_manifest({**base, field: value})
    digests = set()
    for owner, repository, directory in (("o", "r", "docs"), ("x", "r", "docs"), ("o", "x", "docs"), ("o", "r", "other")):
        candidate = deepcopy(base)
        candidate["discovery"].update(owner=owner, repository=repository, directory=directory)
        digests.add(normalize_resolved_github_manifest(candidate)["digest"])
    assert len(digests) == 4


def test_target_service_rejects_unapproved_or_security_bypassing_manifest_scope():
    manifest = normalize_resolved_github_manifest({
        "schema_version": 2, "official": True,
        "discovery": {"kind": "github_directory", "owner": "Kotlin", "repository": "repo",
                      "requested_ref": "v1", "resolved_commit_sha": COMMIT, "directory": "docs"},
        "documents": [{"path": "docs/a.md", "git_blob_sha": "2" * 40, "size": 1}],
        "complete": True, "truncated": False,
    })
    service = DocsTargetService(_render)
    targets = [
        DocsTarget(library="x", source_manifest=manifest, allowed_domains=["github.com"], path_prefixes=["/Kotlin/repo/blob/"]),
        DocsTarget(library="x", docs_url="https://github.com/Other/repo/blob/v1/docs/a.md", source_manifest=manifest,
                   allowed_domains=["github.com"], path_prefixes=["/Kotlin/repo/blob/"]),
        DocsTarget(library="x", docs_url="https://github.com/Kotlin/repo/blob/v1/docs/a.md", source_manifest=manifest,
                   allowed_domains=["example.com"], path_prefixes=["/Kotlin/repo/blob/"]),
    ]
    for target in targets:
        urls, error = service.target_urls(target)
        assert urls == []
        assert error


def test_resolver_rechecks_deadline_after_request_and_rejects_duplicate_listing():
    ticks = iter([0.0, 0.0, 2.0])
    deadline = resolve_github_directory_manifest(
        _Client([_Response({"sha": COMMIT})]), owner="o", repository="r", requested_ref="v1",
        directory="docs", max_total_seconds=1.0, monotonic=lambda: next(ticks),
    )
    duplicate = resolve_github_directory_manifest(_Client([
        _Response({"sha": COMMIT}),
        _Response([{"path": "docs/a.md", "type": "file", "sha": "2" * 40, "size": 1},
                   {"path": "docs/a.md", "type": "file", "sha": "2" * 40, "size": 1}]),
    ]), owner="o", repository="r", requested_ref="v1", directory="docs")
    assert deadline["complete"] is False and deadline["reason_code"] == "deadline_exceeded"
    assert duplicate["complete"] is False and duplicate["reason_code"] == "duplicate_entry"
