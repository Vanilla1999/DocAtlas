"""R1: endpoint prose cannot exempt HTTP writes from the Packs safety gate."""
from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
from types import SimpleNamespace

import pytest

from docmancer.mcp import dispatcher, network_policy, paths, safety
from docmancer.mcp.installer import install_package
from docmancer.mcp.manifest import Manifest
from docmancer.mcp.registry import LocalRegistry, _derive_safety, build_openapi_pack


@pytest.mark.parametrize("method", ["DELETE", "POST", "PUT", "PATCH"])
@pytest.mark.parametrize("path", ["/search/all", "/query/all", "/list/all", "/find/all", "/records/all"])
def test_endpoint_name_cannot_remove_destructive_gate(method, path):
    meta = {"method": method, "path": path}
    original = copy.deepcopy(meta)
    derived = _derive_safety(meta)
    gate = safety.check(
        package="p", operation={"id": "write", "safety": derived},
        allow_destructive=False, has_credentials=False,
    )
    assert derived["destructive"] is True
    assert gate.allowed is False
    assert gate.error_code == "destructive_call_blocked"
    assert meta == original


@pytest.mark.parametrize("method,idempotent", [
    ("GET", True), ("HEAD", True), ("OPTIONS", False), ("POST", False),
    ("PUT", True), ("PATCH", False), ("DELETE", True),
])
def test_http_method_auth_rate_and_idempotence_dto_are_preserved(method, idempotent):
    rate = {"requests": 5, "period": "second"}
    meta = {"method": method.lower(), "path": "/search/all",
            "security": [{"token": []}], "rate_limit": rate}
    assert _derive_safety(meta) == {
        "destructive": method in {"POST", "PUT", "PATCH", "DELETE"},
        "idempotent": idempotent, "requires_auth": True, "rate_limit": rate,
    }
    meta["x_idempotent"] = True
    assert _derive_safety(meta)["idempotent"] is True
    # Idempotence is not permission to call a destructive operation.
    assert _derive_safety(meta)["destructive"] is (method in {"POST", "PUT", "PATCH", "DELETE"})


@pytest.mark.parametrize("path", ["/search/all", "/records/all"])
def test_safe_get_positive_and_original_auth_guard(path):
    meta = {"method": "GET", "path": path}
    operation = {"id": "read", "safety": _derive_safety(meta)}
    assert safety.check(package="p", operation=operation,
                        allow_destructive=False, has_credentials=False).allowed
    meta["security"] = [{"token": []}]
    operation["safety"] = _derive_safety(meta)
    blocked = safety.check(package="p", operation=operation,
                           allow_destructive=False, has_credentials=False)
    assert not blocked.allowed
    assert blocked.error_code == "missing_credentials"
    assert safety.check(package="p", operation=operation,
                        allow_destructive=False, has_credentials=True).allowed


@pytest.fixture
def compiled_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("R1_TEST_TOKEN", raising=False)
    monkeypatch.setattr(network_policy, "resolve_host",
                        lambda host: [ipaddress.ip_address("93.184.216.34")])
    spec = {
        "openapi": "3.0.0", "servers": [{"url": "https://packs.example.test"}],
        "components": {"securitySchemes": {
            "R1_TEST_TOKEN": {"type": "http", "scheme": "bearer"},
        }},
        "paths": {
            "/search/all": {
                "delete": {"operationId": "delete_search", "description": "Safe read-only search"},
                "post": {"operationId": "post_search", "x-idempotent": True},
                "get": {"operationId": "read"},
            },
            "/records/all": {"delete": {"operationId": "delete_records"}},
            "/private": {"get": {"operationId": "private_read", "security": [{"R1_TEST_TOKEN": []}]}},
        },
    }
    original = copy.deepcopy(spec)
    source_sha = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    root = tmp_path / "registry"
    build_openapi_pack(package="r1", version="v1", spec=spec,
                       output_dir=root / "r1@v1", source_url="file:///fixture/openapi.json",
                       source_sha256=source_sha, overrides={}, curated_ids=None)
    assert spec == original
    executor_calls = []

    class OfflineExecutor:
        def call(self, **kwargs):
            executor_calls.append(kwargs)
            return SimpleNamespace(ok=True, body={"offline": True}, status=200)

    # Replace only the final executor: real compilation, installer, network
    # policy (with deterministic DNS), credentials and safety still execute.
    monkeypatch.setattr(dispatcher, "get_executor", lambda kind: OfflineExecutor())

    def install(allow_destructive=False, plain_http=False):
        expected_source_sha = source_sha
        if plain_http:
            http_spec = copy.deepcopy(spec)
            http_spec["servers"] = [{"url": "http://packs.example.test"}]
            expected_source_sha = hashlib.sha256(json.dumps(http_spec, sort_keys=True).encode()).hexdigest()
            build_openapi_pack(package="r1", version="v1", spec=http_spec,
                               output_dir=root / "r1@v1", source_url="file:///fixture/openapi.json",
                               source_sha256=expected_source_sha, overrides={}, curated_ids=None)
        result = install_package("r1", "v1", registry=LocalRegistry(root),
                                 allow_destructive=allow_destructive)
        assert result.destructive_count == 3
        assert result.curated_count == result.full_count == 5
        contract = result.package.contract()
        assert contract["source"]["sha256"] == expected_source_sha
        assert contract["source"]["url"] == "file:///fixture/openapi.json"
        for artifact, digest in result.package.artifact_sha256.items():
            assert hashlib.sha256((paths.package_dir("r1", "v1") / artifact).read_bytes()).hexdigest() == digest
        for operation in contract["operations"]:
            assert set(operation["safety"]) == {"destructive", "idempotent", "requires_auth", "rate_limit"}
        manifest = Manifest.load()
        return result, manifest, dispatcher.Dispatcher(manifest)

    return install, executor_calls


@pytest.mark.parametrize("operation", ["delete_search", "delete_records", "post_search"])
def test_actual_compile_install_dispatch_blocks_ungranted_writes(compiled_pack, operation):
    install, calls = compiled_pack
    result, _, runtime = install()
    assert result.package.grant_for(operation) == {
        "allowed_executors": ["http"], "allowed_hosts": ["packs.example.test"],
    }
    outcome = runtime.call_tool(f"r1__v1__{operation}", {})
    assert not outcome.ok
    assert outcome.error_code == "destructive_call_blocked"
    assert calls == []


@pytest.mark.parametrize("missing", ["none", "package", "operation"])
def test_actual_dispatch_requires_both_destructive_grants(compiled_pack, missing):
    install, calls = compiled_pack
    _, manifest, _ = install(True)
    pkg = manifest.find("r1", "v1")
    assert pkg.allow_destructive is True
    assert pkg.grant_for("delete_search")["allow_destructive"] is True
    assert "allow_destructive" not in pkg.grant_for("read")
    if missing == "package":
        pkg.allow_destructive = False
    elif missing == "operation":
        pkg.operation_grants["delete_search"].pop("allow_destructive")
    outcome = dispatcher.Dispatcher(manifest).call_tool("r1__v1__delete_search", {})
    assert outcome.ok is (missing == "none")
    if missing == "none":
        assert len(calls) == 1
        assert calls[0]["operation"]["http"]["method"] == "DELETE"
        assert calls[0]["operation"]["_docatlas_http_grant"]["allow_destructive"] is True
    else:
        assert outcome.error_code == "destructive_call_blocked"
        assert calls == []


def test_actual_dispatch_get_positive_and_credentials_guard(compiled_pack, monkeypatch):
    install, calls = compiled_pack
    _, _, runtime = install()
    assert runtime.call_tool("r1__v1__read", {}).ok
    assert len(calls) == 1
    blocked = runtime.call_tool("r1__v1__private_read", {})
    assert not blocked.ok
    assert blocked.error_code == "missing_credentials"
    assert len(calls) == 1
    monkeypatch.setenv("R1_TEST_TOKEN", "offline-fixture")
    assert runtime.call_tool("r1__v1__private_read", {}).ok
    assert len(calls) == 2
    assert calls[-1]["auth_headers"] == {"Authorization": "Bearer offline-fixture"}


@pytest.mark.parametrize("restriction,error", [
    ("host", "host_not_allowed"), ("private", "private_network_blocked"),
    ("http", "plain_http_blocked"),
])
def test_actual_dispatch_network_guard_not_relaxed(compiled_pack, monkeypatch, restriction, error):
    install, calls = compiled_pack
    _, manifest, _ = install(True, plain_http=restriction == "http")
    pkg = manifest.find("r1", "v1")
    if restriction == "host":
        pkg.operation_grants["delete_search"]["allowed_hosts"] = []
    elif restriction == "private":
        monkeypatch.setattr(network_policy, "resolve_host",
                            lambda host: [ipaddress.ip_address("127.0.0.1")])
    blocked = dispatcher.Dispatcher(manifest).call_tool("r1__v1__delete_search", {})
    assert not blocked.ok
    assert blocked.error_code == error
    assert calls == []
