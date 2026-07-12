"""Test-wide defaults.

Vector retrieval is on by default for user installs, but the test suite
should never spawn the managed Qdrant binary or download FastEmbed models
into the developer's real ``~/.docmancer`` while running locally. Tests
that exercise the vector path opt in explicitly.
"""
from __future__ import annotations

import ipaddress
import os
import socket

import pytest

os.environ.setdefault("DOCMANCER_AUTO_VECTORS", "0")

# Unit tests must never reach the real hosted registry (docmancer.dev).
# Point the hosted fallback at an unroutable local port so an accidental
# network fetch fails fast instead of hanging on restricted networks.
# Tests that exercise the hosted path mock transports or delete this var.
os.environ.setdefault("DOCMANCER_REGISTRY_API_URL", "http://127.0.0.1:1")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_network: allows real network access; skipped unless DOCMANCER_RUN_LIVE_TESTS=1",
    )
    config.addinivalue_line(
        "markers",
        "mock_network_dns: replaces public DNS with a deterministic documentation address",
    )


def pytest_collection_modifyitems(config, items):
    if os.getenv("DOCMANCER_RUN_LIVE_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="live network tests require DOCMANCER_RUN_LIVE_TESTS=1")
    for item in items:
        if item.get_closest_marker("live_network"):
            item.add_marker(skip)


def _loopback_host(host: object) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    value = str(host).strip("[]").rstrip(".").lower()
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def block_unregistered_outbound_network(monkeypatch, request):
    """Fail the default suite before it can perform external DNS/socket I/O."""
    if request.node.get_closest_marker("live_network"):
        return

    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    real_sendmsg = getattr(socket.socket, "sendmsg", None)
    mock_public_dns = request.node.get_closest_marker("mock_network_dns") is not None

    def guarded_getaddrinfo(host, *args, **kwargs):
        if mock_public_dns and not _loopback_host(host):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 0))
            ]
        if not _loopback_host(host):
            raise RuntimeError(f"unregistered outbound DNS blocked: {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(sock, address):
        if isinstance(address, tuple) and not _loopback_host(address[0]):
            raise RuntimeError(f"unregistered outbound socket blocked: {address[0]!r}")
        return real_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if isinstance(address, tuple) and not _loopback_host(address[0]):
            raise RuntimeError(f"unregistered outbound socket blocked: {address[0]!r}")
        return real_connect_ex(sock, address)

    def guarded_sendto(sock, data, *args):
        address = args[-1] if args else None
        if isinstance(address, tuple) and not _loopback_host(address[0]):
            raise RuntimeError(f"unregistered outbound socket blocked: {address[0]!r}")
        return real_sendto(sock, data, *args)

    def guarded_sendmsg(sock, buffers, *args):
        address = args[-1] if args and isinstance(args[-1], tuple) else None
        if address is not None and not _loopback_host(address[0]):
            raise RuntimeError(f"unregistered outbound socket blocked: {address[0]!r}")
        assert real_sendmsg is not None
        return real_sendmsg(sock, buffers, *args)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    if real_sendmsg is not None:
        monkeypatch.setattr(socket.socket, "sendmsg", guarded_sendmsg)
