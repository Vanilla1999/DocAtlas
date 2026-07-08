"""Section 29: python_import executor (opt-in)."""
import json
import shutil
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


def _seed_python_pack(
    registry_root,
    *,
    module="json",
    callable_name="loads",
    via_kwargs=False,
    args_schema=None,
):
    args_schema = args_schema or {
        "type": "object",
        "properties": {"s": {"type": "string"}},
        "required": ["s"],
    }
    contract = {
        "operations": [
            {
                "id": "json_loads",
                "summary": "Parse a JSON string",
                "executor": "python_import",
                "python_import": {"module": module, "callable": callable_name, "via_kwargs": via_kwargs},
                "params": [
                    {"name": name, "in": "body", **schema}
                    for name, schema in args_schema.get("properties", {}).items()
                ],
                "inputSchema": args_schema,
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


def test_python_import_blocks_module_not_in_operation_grant(tmp_path, monkeypatch):
    registry = tmp_path / "reg"
    _seed_python_pack(registry, via_kwargs=True)
    monkeypatch.setenv("DOCMANCER_REGISTRY_DIR", str(registry))
    install_package("demo", "1", allow_execute=True)
    manifest = Manifest.load()
    manifest.packages[0].operation_grants["json_loads"]["allowed_modules"] = ["math"]

    out = Dispatcher(manifest).call_tool("demo__1__json_loads", {"s": "{}"})
    assert out.ok is False
    assert out.body["error"] == "module_not_allowed"


def test_python_import_blocks_dunder_callable(tmp_path, monkeypatch):
    registry = tmp_path / "reg"
    _seed_python_pack(registry, callable_name="__dict__", args_schema={"type": "object", "properties": {}})
    monkeypatch.setenv("DOCMANCER_REGISTRY_DIR", str(registry))
    install_package("demo", "1", allow_execute=True)

    out = Dispatcher(Manifest.load()).call_tool("demo__1__json_loads", {})
    assert out.ok is False
    assert out.body["error"] == "dunder_callable_blocked"


def test_python_import_uses_minimal_env_unless_allowed(tmp_path, monkeypatch):
    registry = tmp_path / "reg"
    _seed_python_pack(
        registry,
        module="os",
        callable_name="getenv",
        via_kwargs=True,
        args_schema={
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    )
    monkeypatch.setenv("DOCMANCER_REGISTRY_DIR", str(registry))
    monkeypatch.setenv("DOCMANCER_TEST_SECRET", "leaked")
    install_package("demo", "1", allow_execute=True)

    out = Dispatcher(Manifest.load()).call_tool("demo__1__json_loads", {"key": "DOCMANCER_TEST_SECRET"})
    assert out.ok is True
    assert out.body is None


def test_detect_python_ignores_project_venv_by_default(tmp_path):
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    python = venv / "python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    found = detect_python(start=tmp_path)
    assert found != str(python)
    assert found in {sys.executable, shutil.which("python3"), shutil.which("python")}


def test_detect_python_uses_project_venv_when_granted(tmp_path):
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    python = venv / "python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    found = detect_python(start=tmp_path, use_project_venv=True)
    assert found == str(python)


def test_executor_returns_structured_error_for_missing_module():
    op = {
        "executor": "python_import",
        "python_import": {"module": "nonexistent_module_xyz_12345", "callable": "anything"},
        "_docmancer_operation_grant": {"allowed_modules": ["nonexistent_module_xyz_12345"]},
    }
    exec_ = PythonImportExecutor(python=sys.executable)
    result = exec_.call(
        operation=op, args={},
        auth_headers={}, required_headers={},
        idempotency_key=None, idempotency_header=None,
    )
    assert result.ok is False
    assert "ModuleNotFoundError" in (result.error or "") or "nonexistent" in (result.error or "")
