from __future__ import annotations

import json

import httpx

from docmancer.docs.application.library_source_discovery import discover_library_docs_sources


class _Client:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.requested_url = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get(self, url: str):
        self.requested_url = url
        return self.response


def _response(payload: dict, status: int = 200) -> httpx.Response:
    request = httpx.Request("GET", "https://registry.example.test/package")
    return httpx.Response(status, content=json.dumps(payload).encode(), request=request)


def test_pub_discovery_constructs_exact_confirmable_dartdoc_candidate() -> None:
    result = discover_library_docs_sources("go_router", "flutter", "14.8.1")

    assert result["status"] == "candidates_found"
    assert result["candidates"][0]["docs_url"] == "https://pub.dev/documentation/go_router/14.8.1/"
    assert result["candidates"][0]["arguments_patch"] == {
        "action": "prefetch_library_docs",
        "library": "go_router",
        "ecosystem": "pub",
        "version": "14.8.1",
        "source_type": "api",
        "docs_url": "https://pub.dev/documentation/go_router/14.8.1/",
    }
    assert result["requires_confirmation"] is True


def test_python_discovery_prefers_pypi_documentation_metadata(monkeypatch) -> None:
    client = _Client(_response({
        "info": {
            "project_urls": {
                "Source": "https://github.com/example/sample",
                "Documentation": "https://docs.example.com/sample/",
            },
            "home_page": "https://example.com/sample/",
        }
    }))
    monkeypatch.setattr("docmancer.docs.application.library_source_discovery.httpx.Client", lambda **_kwargs: client)

    result = discover_library_docs_sources("sample", "python", "1.2.3")

    assert client.requested_url == "https://pypi.org/pypi/sample/1.2.3/json"
    assert result["status"] == "candidates_found"
    assert result["candidates"][0]["docs_url"] == "https://docs.example.com/sample/"
    assert result["candidates"][0]["confidence"] == "high"


def test_registry_discovery_rejects_credentials_and_non_https_urls(monkeypatch) -> None:
    client = _Client(_response({
        "info": {
            "project_urls": {
                "Documentation": "http://docs.example.com/",
                "Source": "https://user:secret@example.com/repo",
            },
            "home_page": "",
        }
    }))
    monkeypatch.setattr("docmancer.docs.application.library_source_discovery.httpx.Client", lambda **_kwargs: client)

    result = discover_library_docs_sources("unsafe", "python")

    assert result["status"] == "needs_manual_docs_url"
    assert result["candidates"] == []


def test_unknown_ecosystem_explains_manual_source_requirement() -> None:
    result = discover_library_docs_sources("sample", "kotlin")

    assert result["status"] == "unsupported_ecosystem"
    assert "Provide docs_url manually" in result["message"]
