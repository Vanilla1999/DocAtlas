from __future__ import annotations

import socket

import pytest


def test_default_suite_blocks_unregistered_outbound_dns():
    with pytest.raises(RuntimeError, match="unregistered outbound DNS blocked"):
        socket.getaddrinfo("example.com", 443)


def test_default_suite_blocks_unregistered_outbound_socket():
    with socket.socket() as client:
        with pytest.raises(RuntimeError, match="unregistered outbound socket blocked"):
            client.connect(("203.0.113.1", 443))


def test_default_suite_blocks_unregistered_udp_send():
    with socket.socket(type=socket.SOCK_DGRAM) as client:
        with pytest.raises(RuntimeError, match="unregistered outbound socket blocked"):
            client.sendto(b"probe", ("203.0.113.1", 53))