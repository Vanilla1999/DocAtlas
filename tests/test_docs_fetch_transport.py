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


def test_real_client_preserves_hostname_for_proxy_transport():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["host"] = request.headers["host"]
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"docs")

    raw_client = httpx.Client(transport=httpx.MockTransport(handler))
    policy = DocsFetchPolicy(resolver=lambda _host: (__import__("ipaddress").ip_address(PUBLIC),))

    with DocsHttpClient(raw_client, policy, pin_resolved_ips=False) as client:
        response = client.get("https://example.com/docs")

    assert observed == {
        "url": "https://example.com/docs",
        "host": "example.com",
    }
    assert response.status_code == 200


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
