"""Section 29: python_import executor (opt-in)."""
import json
import sys

import pytest

from docmancer.mcp import paths
from docmancer.mcp.dispatcher import Dispatcher
from docmancer.mcp.executors.python_import import PythonImportExecutor, detect_python
from docmancer.mcp.installer import install_package
from docmancer.mcp.manifest import Manifest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    paths.ensure_dirs()


def _seed_python_pack(registry_root, *, via_kwargs=False):
    contract = {
        "operations": [
            {
                "id": "json_loads",
                "summary": "Parse a JSON string",
                "executor": "python_import",
                "python_import": {"module": "json", "callable": "loads", "via_kwargs": via_kwargs},
                "params": [{"name": "s", "in": "body", "type": "string", "required": True}],
                "inputSchema": {
                    "type": "object",
                    "properties": {"s": {"type": "string"}},
                    "required": ["s"],
                },
                "safety": {"destructive": False, "idempotent": True, "requires_auth": False},
            },
        ],
    }
    pkg = registry_root / "demo@1"
    pkg.mkdir(parents=True)
    (pkg / "contract.json").write_text(json.dumps(contract))
    (pkg / "tools.curated.json").write_text(json.dumps({"tools": [{
        "operation_id": "json_loads",
        "description": "Parse a JSON string",
        "safety": {"destructive": False, "idempotent": True, "requires_auth": False},
        "inputSchema": contract["operations"][0]["inputSchema"],
    }]}))


def test_executor_blocked_without_allow_execute(tmp_path, monkeypatch):
    registry = tmp_path / "reg"
    _seed_python_pack(registry)
    monkeypatch.setenv("DOCMANCER_REGISTRY_DIR", str(registry))
    install_package("demo", "1")
    d = Dispatcher(Manifest.load())
    out = d.call_tool("demo__1__json_loads", {"s": "{}"})
    assert out.ok is False
    assert out.error_code == "execution_not_allowed"
    assert "--allow-execute" in out.body["message"]


def test_executor_runs_when_opted_in(tmp_path, monkeypatch):
    registry = tmp_path / "reg"
    _seed_python_pack(registry, via_kwargs=True)
    monkeypatch.setenv("DOCMANCER_REGISTRY_DIR", str(registry))
    install_package("demo", "1", allow_execute=True)
    d = Dispatcher(Manifest.load())
    out = d.call_tool("demo__1__json_loads", {"s": '{"x": 1}'})
    assert out.ok is True, out.body
    assert out.body == {"x": 1}


def test_detect_python_finds_local_venv(tmp_path):
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    python = venv / "python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    found = detect_python(start=tmp_path)
    assert found == str(python)


def test_executor_returns_structured_error_for_missing_module():
    op = {
        "executor": "python_import",
        "python_import": {"module": "nonexistent_module_xyz_12345", "callable": "anything"},
    }
    exec_ = PythonImportExecutor(python=sys.executable)
    result = exec_.call(
        operation=op, args={},
        auth_headers={}, required_headers={},
        idempotency_key=None, idempotency_header=None,
    )
    assert result.ok is False
    assert "ModuleNotFoundError" in (result.error or "") or "nonexistent" in (result.error or "")
