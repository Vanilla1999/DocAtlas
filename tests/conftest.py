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
from pathlib import Path

import pytest

from tests.diagnostic_labels import (
    apply_diagnostic_label,
    load_diagnostic_manifest,
    validate_diagnostic_inventory,
)

os.environ.setdefault("DOCMANCER_AUTO_VECTORS", "0")

# Unit tests must never reach the real hosted registry (docmancer.dev).
# Point the hosted fallback at an unroutable local port so an accidental
# network fetch fails fast instead of hanging on restricted networks.
# Tests that exercise the hosted path mock transports or delete this var.
os.environ.setdefault("DOCMANCER_REGISTRY_API_URL", "http://127.0.0.1:1")


def pytest_configure(config):
    config.addinivalue_line("markers", "advanced: optional advanced/maintenance surface contract test")
    config.addinivalue_line("markers", "live: optional live provider test; never part of core CI")
    config.addinivalue_line(
        "markers",
        "live_network: allows real network access; skipped unless DOCMANCER_RUN_LIVE_TESTS=1",
    )
    config.addinivalue_line(
        "markers",
        "mock_network_dns: replaces public DNS with a deterministic documentation address",
    )
    for name, description in {
        "behavioral": "executes production behavior and checks a semantic outcome",
        "schema": "checks a static or wire-format shape without proving producer behavior",
        "artifact": "checks a committed artifact without executing its producer",
        "serialization": "checks encoding or decoding compatibility only",
        "compatibility": "checks a deliberately supported backward-compatible surface",
        "diagnostic_unclassified": "temporary fail-closed diagnostic inventory marker",
    }.items():
        config.addinivalue_line("markers", f"{name}: {description}")


def pytest_collection_modifyitems(config, items):
    manifest = load_diagnostic_manifest(Path(__file__).with_name("diagnostic_labels.json"))
    complete_modules: set[str] = set()
    for selection in config.args:
        if "::" in selection:
            continue
        selected_path = Path(selection).resolve()
        if selected_path.is_file() and selected_path.suffix == ".py":
            complete_modules.add(selected_path.relative_to(Path.cwd()).as_posix())
        elif selected_path.is_dir():
            complete_modules.update(
                module
                for module in manifest["module_labels"]
                if (Path.cwd() / module).resolve().is_relative_to(selected_path)
            )
    validate_diagnostic_inventory(items, manifest, complete_modules)
    advanced_modules = {
        "test_context7_parity_eval.py",
        "test_eval.py",
        "test_mcp_cli.py",
        "test_mcp_dispatcher.py",
        "test_mcp_executor_extras.py",
        "test_mcp_python_executor.py",
        "test_openai_embeddings.py",
        "test_patch_review_command.py",
        "test_qdrant_manager.py",
        "test_uspto_tm.py",
    }
    advanced_prefixes = (
        "test_mcp_patch_",
        "test_patch_constraint_",
        "test_patch_constraints_",
    )
    for item in items:
        apply_diagnostic_label(item, manifest)
        if item.get_closest_marker("live_network"):
            item.add_marker(pytest.mark.live)
        if (
            item.path.name in advanced_modules
            or item.path.name.startswith(advanced_prefixes)
            or "task_level" in item.path.parts
        ):
            item.add_marker(pytest.mark.advanced)
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
