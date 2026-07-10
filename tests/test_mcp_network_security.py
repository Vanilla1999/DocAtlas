from __future__ import annotations

import ipaddress

import httpx
import pytest

from docmancer.mcp.executors.http import HttpExecutor
from docmancer.mcp.network_policy import (
    HttpGrant,
    SecurityError,
    grant_from_mapping,
    validate_http_target,
    validate_resolution_stability,
)


class CountingStream(httpx.SyncByteStream):
    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks
        self.yielded = 0

    def __iter__(self):
        for chunk in self.chunks:
            self.yielded += 1
            yield chunk


def _operation(*, max_response_bytes: int = 2_000_000) -> dict:
    return {
        "executor": "http",
        "http": {
            "method": "GET",
            "path": "/v1/items",
            "base_url": "https://example.com",
            "encoding": "query_only",
        },
        "params": [],
        "safety": {
            "destructive": False,
            "idempotent": True,
            "requires_auth": False,
        },
        "_docmancer_http_grant": {
            "allowed_hosts": ["example.com"],
            "max_response_bytes": max_response_bytes,
        },
    }


def _call(executor: HttpExecutor, operation: dict):
    return executor.call(
        operation=operation,
        args={},
        auth_headers={},
        required_headers={},
        idempotency_key=None,
        idempotency_header=None,
    )


def test_http_target_rejects_url_userinfo(monkeypatch):
    monkeypatch.setattr(
        "docmancer.mcp.network_policy.resolve_host",
        lambda host: [ipaddress.ip_address("93.184.216.34")],
    )

    with pytest.raises(SecurityError) as exc:
        validate_http_target(
            "https://user:secret@example.com/v1",
            HttpGrant(allowed_hosts=("example.com",)),
        )

    assert exc.value.code == "userinfo_not_allowed"


def test_http_grant_rejects_non_positive_response_limit():
    with pytest.raises(SecurityError) as exc:
        grant_from_mapping({
            "allowed_hosts": ["example.com"],
            "max_response_bytes": 0,
        })

    assert exc.value.code == "invalid_max_response_bytes"


def test_dns_resolution_change_is_blocked_before_request(monkeypatch):
    monkeypatch.setattr(
        "docmancer.mcp.network_policy.resolve_host",
        lambda host: [ipaddress.ip_address("93.184.216.35")],
    )
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"ok": True})

    operation = _operation()
    operation["_docmancer_http_resolved_ips"] = ["93.184.216.34"]
    executor = HttpExecutor(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = _call(executor, operation)

    assert result.ok is False
    assert result.error == "dns_resolution_changed"
    assert called is False


def test_resolution_stability_ignores_dns_answer_order():
    target = validate_http_target.__annotations__["return"](
        url="https://example.com/v1",
        scheme="https",
        host="example.com",
        port=None,
        resolved_ips=("93.184.216.35", "93.184.216.34"),
    )

    validate_resolution_stability(
        ["93.184.216.34", "93.184.216.35"],
        target,
    )


def test_response_limit_stops_stream_before_full_body(monkeypatch):
    monkeypatch.setattr(
        "docmancer.mcp.network_policy.resolve_host",
        lambda host: [ipaddress.ip_address("93.184.216.34")],
    )
    stream = CountingStream([b"abcd", b"efgh", b"ijkl"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream)

    executor = HttpExecutor(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = _call(executor, _operation(max_response_bytes=5))

    assert result.ok is False
    assert result.error == "response_too_large"
    assert stream.yielded == 2


def test_content_length_limit_blocks_before_stream_read(monkeypatch):
    monkeypatch.setattr(
        "docmancer.mcp.network_policy.resolve_host",
        lambda host: [ipaddress.ip_address("93.184.216.34")],
    )
    stream = CountingStream([b"body-was-not-read"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Length": "100"},
            stream=stream,
        )

    executor = HttpExecutor(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = _call(executor, _operation(max_response_bytes=5))

    assert result.ok is False
    assert result.error == "response_too_large"
    assert stream.yielded == 0
