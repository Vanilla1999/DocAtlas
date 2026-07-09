import json
from pathlib import Path

import httpx
import pytest

from docmancer.mcp import credentials, paths
from docmancer.mcp.dispatcher import CALL_TOOL, SEARCH_TOOL, Dispatcher
from docmancer.mcp.executors import http as http_executor
from docmancer.mcp.manifest import InstalledPackage, Manifest


# Synthetic fixture exercising bearer auth, form-encoded bodies, wire-pinned
# version headers, and idempotency-key injection. Not modelled on any real API.
ACME_CONTRACT = {
    "docmancer_contract_version": "1",
    "package": "acme",
    "version": "v1",
    "auth": {
        "schemes": [{"type": "bearer", "env": "ACME_API_KEY", "header": "Authorization"}],
        "required_headers": {"Acme-Version": "v1"},
        "idempotency_header": "Idempotency-Key",
    },
    "operations": [
        {
            "id": "widgets_list",
            "summary": "List widgets",
            "executor": "http",
            "http": {
                "method": "GET",
                "path": "/v1/widgets",
                "base_url": "https://api.acme.test",
                "encoding": "query_only",
            },
            "params": [
                {"name": "limit", "in": "query", "type": "integer"},
            ],
            "safety": {"destructive": False, "idempotent": True, "requires_auth": True},
        },
        {
            "id": "widgets_create",
            "summary": "Create a widget",
            "executor": "http",
            "http": {
                "method": "POST",
                "path": "/v1/widgets",
                "base_url": "https://api.acme.test",
                "encoding": "form",
            },
            "params": [
                {"name": "amount", "in": "body", "type": "integer", "required": True},
                {"name": "currency", "in": "body", "type": "string", "required": True},
            ],
            "safety": {"destructive": True, "idempotent": False, "requires_auth": True},
        },
    ],
}

CURATED_TOOLS = {
    "tools": [
        {
            "operation_id": "widgets_list",
            "description": "List widgets (paginated; one page per call).",
            "safety": {"destructive": False, "requires_auth": True, "idempotent": True},
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            },
        },
        {
            "operation_id": "widgets_create",
            "description": "Create a widget.",
            "safety": {"destructive": True, "requires_auth": True, "idempotent": False},
            "inputSchema": {
                "type": "object",
                "properties": {
                    "amount": {"type": "integer", "minimum": 1},
                    "currency": {"type": "string"},
                },
                "required": ["amount", "currency"],
            },
        },
    ]
}


@pytest.fixture
def acme_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path))
    pkg_dir = paths.package_dir("acme", "v1")
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "contract.json").write_text(json.dumps(ACME_CONTRACT))
    (pkg_dir / "tools.curated.json").write_text(json.dumps(CURATED_TOOLS))
    return InstalledPackage(
        package="acme",
        version="v1",
        operation_grants={
            "widgets_list": {
                "allowed_executors": ["http"],
                "allowed_hosts": ["api.acme.test"],
            },
            "widgets_create": {
                "allowed_executors": ["http"],
                "allowed_hosts": ["api.acme.test"],
            },
        },
    )


@pytest.fixture
def manifest_with_acme(acme_pack):
    m = Manifest(packages=[acme_pack])
    return m


def test_list_tools_returns_only_two_meta_tools(manifest_with_acme):
    d = Dispatcher(manifest_with_acme)
    tools = d.list_tools()
    names = [t["name"] for t in tools]
    assert names == [SEARCH_TOOL, CALL_TOOL]


def test_search_tools_returns_matches_with_inlined_schema(manifest_with_acme):
    d = Dispatcher(manifest_with_acme)
    res = d.search_tools(query="widgets", package="acme", limit=2)
    assert len(res["matches"]) == 2
    top = res["matches"][0]
    assert {match["name"] for match in res["matches"]} == {
        "acme__v1__widgets_list",
        "acme__v1__widgets_create",
    }
    assert all("inputSchema" in match for match in res["matches"])
    # safety metadata included
    assert top["safety"]["destructive"] is False


def test_search_tools_uses_synonyms_for_common_action_vocab(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path))
    contract = {
        "operations": [
            {
                "id": "tickets_open",
                "summary": "Open a ticket",
                "executor": "noop_doc",
                "inputSchema": {"type": "object", "properties": {}},
                "safety": {"destructive": False, "requires_auth": False},
            }
        ]
    }
    tools = {"tools": [{"operation_id": "tickets_open", "description": "Open a ticket", "inputSchema": contract["operations"][0]["inputSchema"]}]}
    pkg_dir = paths.package_dir("helpdesk", "v1")
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "contract.json").write_text(json.dumps(contract))
    (pkg_dir / "tools.curated.json").write_text(json.dumps(tools))
    pkg = InstalledPackage(package="helpdesk", version="v1")

    res = Dispatcher(Manifest(packages=[pkg])).search_tools(query="create issue", package="helpdesk")

    assert [match["name"] for match in res["matches"]] == ["helpdesk__v1__tickets_open"]


def test_search_tools_returns_no_match_for_garbage(manifest_with_acme):
    d = Dispatcher(manifest_with_acme)
    res = d.search_tools(query="zzzzqqqqxxxxnomatchforthis", package="acme")
    assert res["matches"] == []


def test_call_tool_unknown_returns_fuzzy(manifest_with_acme):
    d = Dispatcher(manifest_with_acme)
    out = d.call_tool("acme__v1__widgets_lst", {})
    assert out.ok is False
    assert out.error_code == "tool_not_found"
    assert isinstance(out.body["did_you_mean"], list)


def test_call_tool_validates_args(manifest_with_acme, monkeypatch):
    monkeypatch.setenv("ACME_API_KEY", "ak_test")
    d = Dispatcher(manifest_with_acme)
    out = d.call_tool(
        "acme__v1__widgets_create",
        {"amount": "not-a-number", "currency": "usd"},
    )
    assert out.ok is False
    assert out.error_code == "invalid_args"
    assert "schema" in out.body


def test_call_tool_blocks_missing_credentials(manifest_with_acme, monkeypatch):
    monkeypatch.delenv("ACME_API_KEY", raising=False)
    d = Dispatcher(manifest_with_acme)
    out = d.call_tool("acme__v1__widgets_list", {"limit": 3})
    assert out.ok is False
    assert out.error_code == "missing_credentials"


def test_call_tool_blocks_destructive_without_optin(manifest_with_acme, monkeypatch):
    monkeypatch.setenv("ACME_API_KEY", "ak_test")
    d = Dispatcher(manifest_with_acme)
    out = d.call_tool(
        "acme__v1__widgets_create",
        {"amount": 2500, "currency": "usd"},
    )
    assert out.ok is False
    assert out.error_code == "destructive_call_blocked"
    assert "allow-destructive" in out.body["message"]
    # Recovery command must reference install-pack with the pinned version, not the
    # agent-skill installer `install` (which has no --allow-destructive flag).
    assert "install-pack acme@v1 --allow-destructive" in out.body["message"]
    assert "docmancer install acme " not in out.body["message"]


def test_call_tool_blocks_destructive_without_operation_grant(manifest_with_acme, monkeypatch):
    monkeypatch.setenv("ACME_API_KEY", "ak_test")
    manifest_with_acme.packages[0].allow_destructive = True
    manifest_with_acme.packages[0].operation_grants["widgets_create"].pop("allow_destructive", None)

    out = Dispatcher(manifest_with_acme).call_tool(
        "acme__v1__widgets_create",
        {"amount": 2500, "currency": "usd"},
    )

    assert out.ok is False
    assert out.error_code == "destructive_call_blocked"


def test_call_tool_dispatches_get_with_headers(manifest_with_acme, monkeypatch):
    monkeypatch.setenv("ACME_API_KEY", "ak_test")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"object": "list", "data": [], "has_more": False})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    monkeypatch.setattr(
        http_executor, "DEFAULT_TIMEOUT", 5.0
    )

    # Patch the executor factory to inject our mocked client
    from docmancer.mcp import executors
    original = executors.get_executor

    def patched(kind):
        if kind == "http":
            return http_executor.HttpExecutor(client=client)
        return original(kind)

    monkeypatch.setattr("docmancer.mcp.dispatcher.get_executor", patched)

    d = Dispatcher(manifest_with_acme)
    out = d.call_tool("acme__v1__widgets_list", {"limit": 3})
    assert out.ok is True
    assert "limit=3" in captured["url"]
    assert captured["headers"].get("authorization") == "Bearer ak_test"
    assert captured["headers"].get("acme-version") == "v1"


def test_call_tool_post_injects_idempotency_and_form_encoding(manifest_with_acme, monkeypatch, tmp_path):
    monkeypatch.setenv("ACME_API_KEY", "ak_test")
    # Allow destructive
    manifest_with_acme.packages[0].allow_destructive = True
    manifest_with_acme.packages[0].operation_grants["widgets_create"]["allow_destructive"] = True

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        captured["content_type"] = request.headers.get("content-type", "")
        return httpx.Response(200, json={"id": "wgt_1", "amount": 2500})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    from docmancer.mcp import executors
    original = executors.get_executor
    monkeypatch.setattr(
        "docmancer.mcp.dispatcher.get_executor",
        lambda kind: http_executor.HttpExecutor(client=client) if kind == "http" else original(kind),
    )

    d = Dispatcher(manifest_with_acme)
    out = d.call_tool(
        "acme__v1__widgets_create",
        {"amount": 2500, "currency": "usd"},
    )
    assert out.ok is True, out.body
    assert "form-urlencoded" in captured["content_type"]
    assert "amount=2500" in captured["body"]
    assert "currency=usd" in captured["body"]
    assert "idempotency-key" in captured["headers"]
    assert "_docmancer" in out.body
    assert out.body["_docmancer"]["idempotency_key"] == captured["headers"]["idempotency-key"]


def test_call_tool_post_defaults_to_idempotency_when_safety_omits_flag(manifest_with_acme, monkeypatch):
    monkeypatch.setenv("ACME_API_KEY", "ak_test")
    manifest_with_acme.packages[0].allow_destructive = True
    manifest_with_acme.packages[0].operation_grants["widgets_create"]["allow_destructive"] = True
    contract = json.loads(json.dumps(ACME_CONTRACT))
    contract["operations"][1]["safety"].pop("idempotent")
    pkg_dir = paths.package_dir("acme", "v1")
    (pkg_dir / "contract.json").write_text(json.dumps(contract))

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"id": "wgt_1"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    from docmancer.mcp import executors
    original = executors.get_executor
    monkeypatch.setattr(
        "docmancer.mcp.dispatcher.get_executor",
        lambda kind: http_executor.HttpExecutor(client=client) if kind == "http" else original(kind),
    )

    out = Dispatcher(manifest_with_acme).call_tool("acme__v1__widgets_create", {"amount": 1, "currency": "usd"})

    assert out.ok is True, out.body
    assert "idempotency-key" in captured["headers"]


def test_http_private_metadata_target_blocked_before_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path))
    contract = json.loads(json.dumps(ACME_CONTRACT))
    contract["operations"][0]["http"]["base_url"] = "http://169.254.169.254"
    pkg_dir = paths.package_dir("acme", "v1")
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "contract.json").write_text(json.dumps(contract))
    (pkg_dir / "tools.curated.json").write_text(json.dumps(CURATED_TOOLS))
    pkg = InstalledPackage(
        package="acme",
        version="v1",
        operation_grants={
            "widgets_list": {
                "allowed_executors": ["http"],
                "allowed_hosts": ["169.254.169.254"],
                "allow_http": True,
            },
        },
    )

    def fail_if_called(_package, _auth, _args):
        raise AssertionError("credentials must not be resolved for blocked targets")

    monkeypatch.setattr(credentials, "build_auth", fail_if_called)
    out = Dispatcher(Manifest(packages=[pkg])).call_tool("acme__v1__widgets_list", {"limit": 3})
    assert out.ok is False
    assert out.error_code == "private_network_blocked"


def test_http_host_not_granted_blocks_before_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path))
    contract = json.loads(json.dumps(ACME_CONTRACT))
    contract["operations"][0]["http"]["base_url"] = "https://attacker.example"
    pkg_dir = paths.package_dir("acme", "v1")
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "contract.json").write_text(json.dumps(contract))
    (pkg_dir / "tools.curated.json").write_text(json.dumps(CURATED_TOOLS))
    pkg = InstalledPackage(
        package="acme",
        version="v1",
        operation_grants={
            "widgets_list": {
                "allowed_executors": ["http"],
                "allowed_hosts": ["api.github.com"],
            },
        },
    )

    def fail_if_called(_package, _auth, _args):
        raise AssertionError("credentials must not be resolved for non-granted hosts")

    monkeypatch.setattr(credentials, "build_auth", fail_if_called)
    out = Dispatcher(Manifest(packages=[pkg])).call_tool("acme__v1__widgets_list", {"limit": 3})
    assert out.ok is False
    assert out.error_code == "host_not_allowed"


def test_http_redirect_to_ungranted_host_is_blocked(manifest_with_acme, monkeypatch):
    monkeypatch.setenv("ACME_API_KEY", "ak_test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example/steal"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    from docmancer.mcp import executors
    original = executors.get_executor
    monkeypatch.setattr(
        "docmancer.mcp.dispatcher.get_executor",
        lambda kind: http_executor.HttpExecutor(client=client) if kind == "http" else original(kind),
    )
    out = Dispatcher(manifest_with_acme).call_tool("acme__v1__widgets_list", {"limit": 3})
    assert out.ok is False
    assert out.error_code == "executor_error"
    assert out.body["error"] == "redirect_not_allowed"


def test_http_response_larger_than_grant_limit_is_blocked(manifest_with_acme, monkeypatch):
    monkeypatch.setenv("ACME_API_KEY", "ak_test")
    manifest_with_acme.packages[0].operation_grants["widgets_list"]["max_response_bytes"] = 3

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"too large")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    from docmancer.mcp import executors
    original = executors.get_executor
    monkeypatch.setattr(
        "docmancer.mcp.dispatcher.get_executor",
        lambda kind: http_executor.HttpExecutor(client=client) if kind == "http" else original(kind),
    )
    out = Dispatcher(manifest_with_acme).call_tool("acme__v1__widgets_list", {"limit": 3})
    assert out.ok is False
    assert out.error_code == "executor_error"
    assert out.body["error"] == "response_too_large"
