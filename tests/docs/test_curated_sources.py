from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from dataclasses import replace
import hashlib
import ipaddress
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
import pytest

from docmancer.connectors.fetchers.web import WebFetcher
from docmancer.core.config import DocmancerConfig
from docmancer.docs.curated_sources import (
    canonical_source_identity,
    curated_source_for,
    curated_sources,
    curated_target_spec,
    validate_curated_sources,
)
from docmancer.docs.application.docs_target_service import DocsTargetService
from docmancer.docs.fetch_policy import DocsFetchPolicy
from docmancer.docs.github_source_manifest import GitHubApiClient
from docmancer.docs.service import LibraryDocsService


MCP_COMMIT = "62137874ff26dd74d2fea80ff528a7fd9ca7a5e7"
PUBLIC_TEST_IP = ipaddress.ip_address("93.184.216.34")


def _service(tmp_path: Path) -> LibraryDocsService:
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return LibraryDocsService(config=config)


def test_curated_manifest_covers_the_parity_libraries_with_bounded_official_sources() -> None:
    sources = curated_sources()

    assert len(sources) >= 30
    assert curated_source_for("fastapi", "python", None) is not None
    assert curated_source_for("mcp", "python", "1.27.2") is not None
    assert curated_source_for("python", "python", "3.13") is not None
    assert curated_source_for("mcp", "python", "definitely-not-a-release") is None
    assert curated_source_for("python", "python", "999.999") is None
    assert curated_source_for("react", "typescript", None) is not None
    assert curated_source_for("go_router", "flutter", "14.8.1") is not None
    assert all(source.allowed_domains and source.max_pages <= 24 for source in sources)


def test_curated_target_has_explicit_allowlist_and_never_invents_version_binding() -> None:
    source = curated_source_for("fastapi", "python", None)
    assert source is not None

    target = curated_target_spec(source, version=None)

    assert target["docs_url"] == "https://fastapi.tiangolo.com/"
    assert target["allowed_domains"] == ["fastapi.tiangolo.com"]
    assert target["source_manifest"]["official"] is True
    assert target["source_manifest"]["version_rule"] == "unversioned"
    assert canonical_source_identity("https://fastapi.tiangolo.com/") == canonical_source_identity("https://FASTAPI.tiangolo.com")


def test_curated_target_preserves_path_prefix_policy() -> None:
    source = curated_source_for("fastapi", "python", None)
    assert source is not None

    target = curated_target_spec(replace(source, path_prefixes=("/docs/",)), version=None)
    assert target is not None
    runtime_target = DocsTargetService.target_from_dict(target)

    assert runtime_target.path_prefixes == ["/docs/"]
    service = DocsTargetService(
        lambda template, library, version: template.format(library=library, version=version)
    )
    urls, error = service.target_urls(runtime_target)
    assert urls == []
    assert error == "URL path is outside path_prefixes: https://fastapi.tiangolo.com/"


def test_exact_request_does_not_register_unversioned_curated_docs(tmp_path: Path) -> None:
    info = _service(tmp_path).resolve_library("fastapi", ecosystem="python", version="0.115.6", source_type="api")

    assert info.library_id is None
    assert info.status == "needs_docs_url"


@pytest.mark.parametrize(
    "refresh_direct_text",
    [False, True],
    ids=["resolution", "refresh-dispatch"],
)
def test_exact_curated_source_renders_the_requested_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    refresh_direct_text: bool,
) -> None:
    source = curated_source_for("go_router", "flutter", "16.2.0")
    assert source is not None
    assert source.exact_snapshot is True
    assert source.render("16.2.0") == "https://pub.dev/documentation/go_router/16.2.0/"
    assert curated_target_spec(source, version="16.2.0")["seed_urls"] == []

    service = _service(tmp_path)
    expected_urls = {
        ("mcp", "1.27.2"): f"https://github.com/modelcontextprotocol/python-sdk/blob/{MCP_COMMIT}/docs/index.md",
        ("python", "3.13"): "https://docs.python.org/3.13/_sources/library/base64.rst.txt",
    }
    for (library, version), expected_url in expected_urls.items():
        resolved = service.resolve_library(
            library,
            ecosystem="python",
            version=version,
            source_type="api",
        )
        assert resolved.status == "available"
        assert resolved.library_id == f"python:{library}@{version}:api"
        assert resolved.docs_url == expected_url
        assert resolved.docs_snapshot_exact is True
        record = service.registry.get(
            library,
            ecosystem="python",
            version=version,
            source_type="api",
        )
        assert record is not None
        assert record.target_spec is not None
        assert record.target_spec["docs_url"] == expected_url

    if not refresh_direct_text:
        return

    calls: list[tuple[str, list[str] | None]] = []

    class FakeAgent:
        def add(self, url: str, **kwargs: object) -> int:
            calls.append((url, cast(list[str] | None, kwargs["seed_urls"])))
            return 0

    agent = FakeAgent()
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    service = LibraryDocsService(config=config, agent_factory=lambda **_kwargs: agent)

    resolved = service.resolve_library(
        "python", ecosystem="python", version="3.13", source_type="api"
    )
    result = service.refresh_docs(resolved.library_id, source_type="api", force=True)

    assert result.status == "empty_index"
    assert calls == [
        ("https://docs.python.org/3.13/_sources/library/base64.rst.txt", []),
        ("https://docs.python.org/3.13/_sources/library/zlib.rst.txt", []),
    ]


def test_full_curated_manifest_passes_offline_target_validation() -> None:
    validate_curated_sources()

    expected_targets = {
        ("mcp", "1.27.2"): (
            f"https://github.com/modelcontextprotocol/python-sdk/blob/{MCP_COMMIT}/docs/index.md",
            "github.com",
        ),
        ("python", "3.13"): (
            "https://docs.python.org/3.13/_sources/library/base64.rst.txt",
            "docs.python.org",
        ),
    }
    for (library, version), (expected_url, expected_domain) in expected_targets.items():
        source = curated_source_for(library, "python", version)
        assert source is not None
        assert source.exact_snapshot is True
        target_spec = curated_target_spec(source, version=version)
        assert target_spec is not None
        assert target_spec["docs_url"] == expected_url
        assert target_spec["allowed_domains"] == [expected_domain]
        if library == "mcp":
            assert target_spec["path_prefixes"] == [
                f"/modelcontextprotocol/python-sdk/blob/{MCP_COMMIT}/docs/"
            ]
            assert target_spec["source_manifest"] == {
                "schema_version": 2,
                "official": True,
                "discovery": {
                    "kind": "github_directory",
                    "owner": "modelcontextprotocol",
                    "repository": "python-sdk",
                    "requested_ref": MCP_COMMIT,
                    "directory": "docs",
                },
            }
        else:
            assert target_spec["seed_urls"] == [
                "https://docs.python.org/3.13/_sources/library/zlib.rst.txt"
            ]
            assert target_spec["path_prefixes"] == ["/3.13/_sources/library/"]
            assert target_spec["doc_format"] == "direct-text"
            assert target_spec["source_manifest"] == {
                "schema_version": 1,
                "version_rule": "exact",
                "official": True,
            }

    _assert_locked_targets_cross_the_real_fetch_boundary()


class _GitHubResponse:
    def __init__(self, payload: object):
        import json

        self._payload = payload
        self.status_code = 200
        self.content = json.dumps(payload).encode()

    def json(self) -> object:
        return self._payload


class _GitHubClient:
    def __init__(self, responses: list[_GitHubResponse]):
        self.responses = responses

    def get(self, _url: str, **_kwargs: object) -> _GitHubResponse:
        return self.responses.pop(0)


def _assert_locked_targets_cross_the_real_fetch_boundary() -> None:
    mcp_source = curated_source_for("mcp", "python", "1.27.2")
    assert mcp_source is not None
    mcp_spec = curated_target_spec(mcp_source, version="1.27.2")
    assert mcp_spec is not None
    mcp_content = b"# MCP result contracts\n\nReturn structuredContent and set isError for tool failures.\n"
    mcp_blob = hashlib.sha1(
        b"blob " + str(len(mcp_content)).encode("ascii") + b"\0" + mcp_content
    ).hexdigest()
    github = _GitHubClient([
        _GitHubResponse({"sha": MCP_COMMIT}),
        _GitHubResponse([
            {"path": "docs/index.md", "type": "file", "sha": mcp_blob, "size": len(mcp_content)}
        ]),
    ])
    target_service = DocsTargetService(
        lambda template, name, version: template.format(library=name, version=version),
        github_api_client_factory=lambda: cast(
            AbstractContextManager[GitHubApiClient], nullcontext(github)
        ),
    )
    resolved_mcp = target_service.resolve_github_directory_target(
        target_service.target_from_dict(mcp_spec)
    )
    mcp_urls, error = target_service.target_urls(resolved_mcp)
    assert error is None
    assert resolved_mcp.source_manifest["discovery"]["resolved_commit_sha"] == MCP_COMMIT
    assert [row["path"] for row in resolved_mcp.source_manifest["documents"]] == ["docs/index.md"]
    assert all(f"/blob/{MCP_COMMIT}/docs/" in url for url in mcp_urls)

    python_source = curated_source_for("python", "python", "3.13")
    assert python_source is not None
    python_spec = curated_target_spec(python_source, version="3.13")
    assert python_spec is not None
    python_target = target_service.target_from_dict(python_spec)
    python_urls, error = target_service.target_urls(python_target)
    assert error is None
    assert python_urls == [
        "https://docs.python.org/3.13/_sources/library/base64.rst.txt",
        "https://docs.python.org/3.13/_sources/library/zlib.rst.txt",
    ]

    evidence = {
        python_urls[0]: "base64 — Base16, Base32, Base64, Base85 Data Encodings\n.. function:: b64decode(s)",
        python_urls[1]: "zlib — Compression compatible with gzip\n.. method:: Decompress.decompress(data, max_length=0)",
    }
    real_client = httpx.Client

    def client_factory(**_kwargs: object) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            canonical_url = f"https://{request.headers['host']}{request.url.path}"
            return httpx.Response(200, text=evidence[canonical_url])

        return real_client(transport=httpx.MockTransport(handler))

    fetch_policy = DocsFetchPolicy(
        resolver=lambda _host: (PUBLIC_TEST_IP,),
        allowed_hosts=("docs.python.org",),
        path_prefixes=("/3.13/_sources/library/",),
    )
    with patch("docmancer.connectors.fetchers.web.httpx.Client", side_effect=client_factory):
        documents = [
            WebFetcher(max_pages=python_target.max_pages, fetch_policy=fetch_policy).fetch(url)[0]
            for url in python_urls
        ]

    assert [document.source for document in documents] == python_urls
    assert "b64decode" in documents[0].content
    assert "max_length" in documents[1].content


def test_flutter_bloc_exact_target_is_allowed() -> None:
    source = curated_source_for("flutter_bloc", "flutter", "8.1.6")
    assert source is not None

    target = curated_target_spec(source, version="8.1.6")
    urls, error = DocsTargetService(lambda template, library, version: template.format(library=library, version=version)).target_urls(
        DocsTargetService.target_from_dict(target)
    )

    assert error is None
    assert urls == ["https://pub.dev/documentation/flutter_bloc/8.1.6/"]


def test_curated_manifest_validator_reports_library_and_invalid_field() -> None:
    source = curated_source_for("flutter_bloc", "dart", "8.1.6")
    assert source is not None

    invalid = replace(source, allowed_domains=("bloclibrary.dev",))

    with pytest.raises(ValueError, match="invalid curated source flutter_bloc field docs_url: URL host is not in allowed_domains"):
        validate_curated_sources([invalid])


def test_curated_manifest_validator_rejects_seed_userinfo() -> None:
    source = curated_source_for("flutter_bloc", "dart", "8.1.6")
    assert source is not None

    invalid = replace(source, preferred_seeds=("https://user:secret@pub.dev/seed",))

    with pytest.raises(ValueError, match="invalid curated source flutter_bloc field preferred_seeds\\[0\\]: URL userinfo is not allowed"):
        validate_curated_sources([invalid])
