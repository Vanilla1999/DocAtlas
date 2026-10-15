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




def test_exact_request_does_not_register_unversioned_curated_docs(tmp_path: Path) -> None:
    info = _service(tmp_path).resolve_library("fastapi", ecosystem="python", version="0.115.6", source_type="api")

    assert info.library_id is None
    assert info.status == "needs_docs_url"


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

