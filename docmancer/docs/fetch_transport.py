"""Policy-aware HTTP transport for documentation ingestion."""
from __future__ import annotations

import socket
import ssl
from time import monotonic
from typing import Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError, ValidatedDocsTarget

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_HTTPX_CLIENT_TYPE = httpx.Client
_ALLOWED_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "application/rss+xml",
    "application/atom+xml",
    "application/gzip",
    "application/x-gzip",
)


class DocsHttpClient:
    """Validate DNS and every redirect target before forwarding GET requests."""

    def __init__(
        self,
        client,
        policy: DocsFetchPolicy,
        *,
        max_redirects: int = 5,
        max_response_bytes: int = 8 * 1024 * 1024,
        max_decoded_text_bytes: int = 16 * 1024 * 1024,
        clock: Callable[[], float] = monotonic,
        max_total_seconds: float | None = None,
        transfer_counter: Callable[[httpx.Response], int] | None = None,
    ) -> None:
        self._client = client
        self._policy = policy
        self._max_redirects = max_redirects
        self._max_response_bytes = max_response_bytes
        self._max_decoded_text_bytes = max_decoded_text_bytes
        self._clock = clock
        self._max_total_seconds = max_total_seconds
        self._transfer_counter = transfer_counter or (lambda response: response.num_bytes_downloaded)

    def __enter__(self):
        return self

    def __exit__(self, exc_type=None, exc=None, traceback=None) -> None:
        self.close()

    def get(self, url: httpx.URL | str, **kwargs) -> httpx.Response:
        current = str(url)
        started_at = self._clock()
        for redirects in range(self._max_redirects + 1):
            first = self._policy.validate_url(current)
            second = self._policy.validate_url(current)
            self._validate_stable_resolution(first, second)
            if self._max_total_seconds is not None and self._clock() - started_at > self._max_total_seconds:
                raise DocsFetchSecurityError("request_timeout", first.redacted_url)
            try:
                response = self._request_once(current, first, **kwargs)
            except httpx.RequestError as exc:
                raise DocsFetchSecurityError(
                    _network_failure_category(exc),
                    first.redacted_url,
                    phase="fetching",
                    retryable=True,
                ) from None
            try:
                reported_url = response.url
            except (AttributeError, RuntimeError):
                reported_url = None
            if isinstance(reported_url, httpx.URL):
                self._policy.validate_url(str(reported_url))
            if response.status_code not in _REDIRECT_STATUSES:
                if not isinstance(self._client, _HTTPX_CLIENT_TYPE):
                    self._validate_response(response, first)
                return response
            location = getattr(response, "headers", {}).get("location")
            if not location:
                self._validate_response(response, first)
                return response
            if redirects == self._max_redirects:
                raise DocsFetchSecurityError("too_many_redirects", first.redacted_url)
            current = urljoin(current, location)
        raise DocsFetchSecurityError("too_many_redirects", current)

    def _request_once(self, url: str, target: ValidatedDocsTarget, **kwargs) -> httpx.Response:
        if not isinstance(self._client, _HTTPX_CLIENT_TYPE):
            return self._client.get(url, **kwargs)
        last_connect_error: httpx.RequestError | None = None
        for address in target.resolved_ips:
            try:
                return self._request_pinned(url, target, address, **kwargs)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_connect_error = exc
        assert last_connect_error is not None
        raise last_connect_error

    def _request_pinned(
        self,
        url: str,
        target: ValidatedDocsTarget,
        address: str,
        **kwargs,
    ) -> httpx.Response:
        pinned_url = _pinned_url(url, address)
        headers = dict(kwargs.pop("headers", {}) or {})
        default_port = 443 if target.scheme == "https" else 80
        headers["Host"] = target.host if target.port == default_port else f"{target.host}:{target.port}"
        extensions = dict(kwargs.pop("extensions", {}) or {})
        extensions["sni_hostname"] = target.host
        original_request = httpx.Request("GET", url)
        with self._client.stream(
            "GET",
            pinned_url,
            headers=headers,
            extensions=extensions,
            follow_redirects=False,
            **kwargs,
        ) as response:
            self._validate_headers(response, target)
            if response.status_code in _REDIRECT_STATUSES:
                return httpx.Response(
                    response.status_code,
                    headers=response.headers,
                    request=original_request,
                )
            chunks: list[bytes] = []
            decoded_size = 0
            for chunk in response.iter_bytes():
                decoded_size += len(chunk)
                if (
                    decoded_size > self._max_decoded_text_bytes
                    or self._transfer_counter(response) > self._max_response_bytes
                ):
                    raise DocsFetchSecurityError("response_too_large", target.redacted_url)
                chunks.append(chunk)
            response_headers = response.headers.copy()
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)
            return httpx.Response(
                response.status_code,
                headers=response_headers,
                content=b"".join(chunks),
                request=original_request,
            )

    @staticmethod
    def _validate_stable_resolution(first: ValidatedDocsTarget, second: ValidatedDocsTarget) -> None:
        if first.resolved_ips != second.resolved_ips:
            raise DocsFetchSecurityError("dns_resolution_changed", first.redacted_url)

    def _validate_response(self, response, target: ValidatedDocsTarget) -> None:
        self._validate_headers(response, target)
        content = getattr(response, "content", None)
        if isinstance(content, bytes) and len(content) > self._max_response_bytes:
            raise DocsFetchSecurityError("response_too_large", target.redacted_url)

    def _validate_headers(self, response, target: ValidatedDocsTarget) -> None:
        headers = getattr(response, "headers", {})
        raw_length = headers.get("content-length")
        if raw_length:
            try:
                content_length = int(raw_length)
            except (TypeError, ValueError):
                raise DocsFetchSecurityError("invalid_content_length", target.redacted_url) from None
            if content_length > self._max_response_bytes:
                raise DocsFetchSecurityError("response_too_large", target.redacted_url)
        if getattr(response, "status_code", None) in _REDIRECT_STATUSES:
            return
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if not any(
            content_type == allowed or content_type.startswith(allowed)
            for allowed in _ALLOWED_CONTENT_TYPES
        ):
            raise DocsFetchSecurityError("content_type_blocked", target.redacted_url)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close:
            close()


def _pinned_url(url: str, address: str) -> str:
    parsed = urlsplit(url)
    host = f"[{address}]" if ":" in address else address
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def _network_failure_category(exc: httpx.RequestError) -> str:
    """Map httpx's transport hierarchy to the public Docs-job vocabulary."""
    if isinstance(exc, httpx.ConnectTimeout):
        return "connect_timeout"
    if isinstance(exc, httpx.ReadTimeout):
        return "read_timeout"
    if isinstance(exc, httpx.TimeoutException):
        return "connect_timeout"
    cause: BaseException | None = exc
    seen: set[int] = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if isinstance(cause, (socket.gaierror, UnicodeError)):
            return "dns_failure"
        if isinstance(cause, ssl.SSLError):
            return "tls_failure"
        cause = cause.__cause__ or cause.__context__
    return "network_unreachable"
