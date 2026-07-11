from __future__ import annotations

from unittest.mock import MagicMock

import gzip
import httpx
import pytest

from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError
from docmancer.docs.fetch_transport import DocsHttpClient


PUBLIC = "93.184.216.34"


def _response(status: int, *, location: str | None = None, body: bytes = b"ok", content_type: str = "text/plain"):
    headers = {"content-type": content_type, "content-length": str(len(body))}
    if location:
        headers["location"] = location
    return httpx.Response(status, headers=headers, content=body)


def test_client_blocks_private_redirect_before_dispatch():
    transport = MagicMock()
    transport.get.return_value = _response(302, location="http://127.0.0.1/admin")
    policy = DocsFetchPolicy(resolver=lambda host: (__import__("ipaddress").ip_address(host if host == "127.0.0.1" else PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="private_network_blocked"):
        DocsHttpClient(transport, policy).get("https://example.com/docs")

    assert transport.get.call_count == 1


def test_client_follows_valid_redirect_manually():
    transport = MagicMock()
    transport.get.side_effect = [
        _response(302, location="/guide/start"),
        _response(200, body=b"hello"),
    ]
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    response = DocsHttpClient(transport, policy).get("https://example.com/docs")

    assert response.status_code == 200
    assert [call.args[0] for call in transport.get.call_args_list] == [
        "https://example.com/docs",
        "https://example.com/guide/start",
    ]


def test_client_rejects_redirect_loop_limit():
    transport = MagicMock()
    transport.get.return_value = _response(302, location="/again")
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="too_many_redirects"):
        DocsHttpClient(transport, policy, max_redirects=2).get("https://example.com/start")

    assert transport.get.call_count == 3


@pytest.mark.parametrize(
    ("location", "category"),
    [
        ("https://evil.test/docs", "host_not_allowed"),
        ("https://example.com/admin", "path_not_allowed"),
    ],
)
def test_client_reapplies_scope_to_redirects(location, category):
    transport = MagicMock()
    transport.get.return_value = _response(302, location=location)
    policy = DocsFetchPolicy(
        resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),),
        allowed_hosts=("example.com",),
        path_prefixes=("/docs",),
    )

    with pytest.raises(DocsFetchSecurityError, match=category):
        DocsHttpClient(transport, policy).get("https://example.com/docs")

    assert transport.get.call_count == 1


def test_transport_error_exposes_only_safe_category_and_redacted_url():
    transport = MagicMock()
    request = httpx.Request("GET", "https://example.com/docs?token=secret")
    transport.get.side_effect = httpx.ConnectError(
        "proxy http://user:password@proxy.internal failed",
        request=request,
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError) as exc:
        DocsHttpClient(transport, policy).get(str(request.url))

    assert exc.value.category == "transport_error"
    assert "secret" not in exc.value.redacted_url
    assert "password" not in str(exc.value)
    assert exc.value.__cause__ is None


def test_client_revalidates_reported_final_response_url():
    transport = MagicMock()
    transport.get.return_value = httpx.Response(
        200,
        headers={"content-type": "text/plain"},
        content=b"docs",
        request=httpx.Request("GET", "http://127.0.0.1/internal"),
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="private_network_blocked"):
        DocsHttpClient(transport, policy).get("https://example.com/docs")


def test_client_rejects_rebinding_before_dispatch():
    answers = iter([PUBLIC, "93.184.216.35"])
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(next(answers)),))
    transport = MagicMock()

    with pytest.raises(DocsFetchSecurityError, match="dns_resolution_changed"):
        DocsHttpClient(transport, policy).get("https://example.com/docs")

    transport.get.assert_not_called()


def test_real_client_connects_to_the_validated_ip_with_original_host_and_sni():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["host"] = request.headers["host"]
        observed["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"docs")

    raw_client = httpx.Client(transport=httpx.MockTransport(handler))
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with DocsHttpClient(raw_client, policy) as client:
        response = client.get("https://example.com/docs")

    assert observed == {
        "url": f"https://{PUBLIC}/docs",
        "host": "example.com",
        "sni": "example.com",
    }
    assert str(response.url) == "https://example.com/docs"


def test_real_client_falls_back_only_to_other_prevalidated_ips():
    first = "2001:4860:4860::8888"
    second = PUBLIC
    observed = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.host)
        if request.url.host == first:
            raise httpx.ConnectError("unreachable", request=request)
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"ok")

    raw_client = httpx.Client(transport=httpx.MockTransport(handler))
    policy = DocsFetchPolicy(
        resolver=lambda _host: (
            __import__("ipaddress").ip_address(first),
            __import__("ipaddress").ip_address(second),
        )
    )

    with DocsHttpClient(raw_client, policy) as client:
        response = client.get("https://example.com/docs")

    assert response.status_code == 200
    assert observed == [first, second]


def test_client_rejects_content_length_before_reading_body():
    transport = MagicMock()
    transport.get.return_value = httpx.Response(
        200,
        headers={"content-type": "text/html", "content-length": "100"},
        content=b"",
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="response_too_large"):
        DocsHttpClient(transport, policy, max_response_bytes=10).get("https://example.com/docs")


def test_client_rejects_binary_content_type():
    transport = MagicMock()
    transport.get.return_value = _response(200, body=b"binary", content_type="application/zip")
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="content_type_blocked") as exc:
        DocsHttpClient(transport, policy).get("https://example.com/archive.zip?token=secret")

    assert "secret" not in exc.value.redacted_url


def test_real_client_stops_stream_when_decoded_body_exceeds_limit():
    class CountingStream(httpx.SyncByteStream):
        def __init__(self):
            self.yielded = 0

        def __iter__(self):
            for chunk in (b"abcd", b"efgh", b"ijkl"):
                self.yielded += 1
                yield chunk

    stream = CountingStream()
    raw_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                stream=stream,
            )
        )
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="response_too_large"):
        DocsHttpClient(
            raw_client,
            policy,
            max_response_bytes=100,
            max_decoded_text_bytes=5,
        ).get("https://example.com/docs")

    assert stream.yielded == 2


def test_injected_clock_enforces_total_request_budget_before_dispatch():
    ticks = iter([0.0, 11.0])
    transport = MagicMock()
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="request_timeout"):
        DocsHttpClient(
            transport,
            policy,
            clock=lambda: next(ticks),
            max_total_seconds=10.0,
        ).get("https://example.com/docs")

    transport.get.assert_not_called()


def test_injected_transfer_counter_enforces_budget():
    raw_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                content=b"ok",
            )
        )
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="response_too_large"):
        with DocsHttpClient(
            raw_client,
            policy,
            max_response_bytes=10,
            transfer_counter=lambda _response: 11,
        ) as client:
            client.get("https://example.com/docs")


def test_real_client_rejects_missing_content_type():
    raw_client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=b"docs"))
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with pytest.raises(DocsFetchSecurityError, match="content_type_blocked"):
        with DocsHttpClient(raw_client, policy) as client:
            client.get("https://example.com/docs")


@pytest.mark.parametrize("content_type", ["application/gzip", "application/x-gzip"])
def test_real_client_accepts_gzip_sitemap_media_types(content_type):
    raw_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": content_type},
                content=b"compressed",
            )
        )
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with DocsHttpClient(raw_client, policy) as client:
        response = client.get("https://example.com/sitemap.xml.gz")

    assert response.content == b"compressed"


def test_real_client_does_not_decode_content_encoding_twice():
    body = gzip.compress(b"docs")
    raw_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={
                    "content-type": "text/plain",
                    "content-encoding": "gzip",
                    "content-length": str(len(body)),
                },
                content=body,
            )
        )
    )
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with DocsHttpClient(raw_client, policy) as client:
        response = client.get("https://example.com/docs")

    assert response.content == b"docs"
