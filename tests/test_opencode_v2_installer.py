"""Run the actual embedded shell writer, never the live installer."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from docmancer.mcp.agent_config import AgentTarget, register_server

COMMAND = ["doc-atlas", "mcp", "docs-serve"]


def shell_writer(path):
    source = (Path(__file__).resolve().parents[1] / "scripts/install.sh").read_text()
    program = source.split("if OPENCODE_CFG=", 1)[1].split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    return subprocess.run([sys.executable, "-c", program], capture_output=True, text=True,
                          env={**os.environ, "OPENCODE_CFG": str(path), "SERVER_NAME": "docatlas"})


@pytest.mark.parametrize("writer", [shell_writer, "python"])
@pytest.mark.parametrize("legacy", [False, True])
def test_unique_owned_name_and_state_preserved(tmp_path, writer, legacy):
    path = tmp_path / "opencode.json"
    entry = {"type": "local", "command": COMMAND, "disabled": True,
             "environment": {"CUSTOM": "keep"}, "timeout": {"startup": 42000}}
    config = {"model": "unchanged", "mcp": {"timeout": {"catalog": 1234},
              "servers": {"other": {"type": "remote", "url": "https://example.test"}}}}
    (config["mcp"] if legacy else config["mcp"]["servers"])["my-docs"] = entry
    path.write_text(json.dumps(config))
    if writer == "python":
        target = AgentTarget("opencode", path, "json_opencode_mcp")
        assert register_server(target)[0]
    else:
        assert shell_writer(path).returncode == 0
    updated = json.loads(path.read_text())
    assert updated["model"] == config["model"]
    assert updated["mcp"]["timeout"] == config["mcp"]["timeout"]
    servers = updated["mcp"]["servers"]
    assert set(servers) == {"other", "my-docs"}
    assert servers["my-docs"] == {**entry, "environment": {"CUSTOM": "keep", "DOCATLAS_MCP_TEXT_FALLBACK": "1"}}
    original = path.read_bytes()
    if writer == "python":
        assert register_server(target)[0] is False
    else:
        assert shell_writer(path).returncode == 0
    assert path.read_bytes() == original


def run_stubbed_installer(tmp_path, **overrides):
    """Execute the installer with fake tools; no downloads or live registration."""
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "uv-args"
    (tools / "uv").write_text(
        '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "uv fixture"; exit 0; fi\n'
        'printf "%s\\n" "$@" > "$UV_ARGS_LOG"\nexit "${UV_STUB_EXIT:-0}"\n'
    )
    (tools / "doc-atlas").write_text('#!/bin/sh\necho "doc-atlas fixture"\n')
    (tools / "curl").write_text('#!/bin/sh\nexit 99\n')
    for tool in tools.iterdir():
        tool.chmod(0o755)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("DOCATLAS_")}
    env.update(HOME=str(tmp_path), PATH=f"{tools}:/usr/bin:/bin", UV_ARGS_LOG=str(log))
    env.update(overrides)
    script = Path(__file__).resolve().parents[1] / "scripts/install.sh"
    result = subprocess.run(["/bin/sh", str(script), "none"], env=env,
                            text=True, capture_output=True, timeout=15)
    return result, log


@pytest.mark.parametrize("runtime", [None, "3.11", "3.12", "3.13"])
def test_installer_uses_managed_supported_python_and_wheels(tmp_path, runtime):
    overrides = {"DOCATLAS_INSTALL_SOURCE": "/fixture/doc_atlas.whl"}
    if runtime is not None:
        overrides["DOCATLAS_INSTALL_PYTHON"] = runtime
    result, log = run_stubbed_installer(tmp_path, **overrides)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        "tool", "install", "--upgrade", "--managed-python", "--python",
        runtime or "3.13", "--no-build", "/fixture/doc_atlas.whl",
    ]
    assert not (tmp_path / ".config").exists()


def test_installer_rejects_unsupported_python_before_tool_install(tmp_path):
    result, log = run_stubbed_installer(tmp_path, DOCATLAS_INSTALL_PYTHON="3.14")
    assert result.returncode != 0
    assert "Unsupported DOCATLAS_INSTALL_PYTHON" in result.stderr
    assert not log.exists()


def test_installer_does_not_fallback_after_wheel_install_failure(tmp_path):
    result, log = run_stubbed_installer(tmp_path, UV_STUB_EXIT="8")
    assert result.returncode == 8
    assert "--no-build" in log.read_text().splitlines()
    assert "DocAtlas is ready" not in result.stdout
    assert not (tmp_path / ".config").exists()


@pytest.mark.parametrize("writer", [shell_writer, "python"])
@pytest.mark.parametrize("entries", [
    {"docatlas": {"command": ["foreign"]}},
    {"one": {"command": COMMAND}, "two": {"command": COMMAND}},
])
def test_collision_refuses_without_writes(tmp_path, writer, entries):
    path = tmp_path / "opencode.json"
    path.write_text(json.dumps({"mcp": {"servers": entries}}))
    original = path.read_bytes()
    if writer == "python":
        with pytest.raises(ValueError):
            register_server(AgentTarget("opencode", path, "json_opencode_mcp"))
    else:
        assert shell_writer(path).returncode != 0
    assert path.read_bytes() == original
    assert not path.with_suffix(".json.bak").exists()


def test_shell_jsonc_noop_preserves_comments_and_update_refuses(tmp_path):
    path = tmp_path / "opencode.jsonc"
    path.write_text('// keep comment\n' + json.dumps({"mcp": {"servers": {"custom": {
        "type": "local", "command": COMMAND,
        "environment": {"DOCATLAS_MCP_TEXT_FALLBACK": "1"}}}}}))
    original = path.read_bytes()
    assert shell_writer(path).returncode == 0
    assert path.read_bytes() == original
    path.write_text('// keep comment\n{"model":"keep"}')
    original = path.read_bytes()
    result = shell_writer(path)
    assert result.returncode != 0 and "refusing to drop comments" in result.stderr
    assert path.read_bytes() == original


def test_python_jsonc_refuses_without_writes(tmp_path):
    path = tmp_path / "opencode.jsonc"
    path.write_text('// keep\n{}')
    with pytest.raises(ValueError, match="not valid JSON"):
        register_server(AgentTarget("opencode", path, "json_opencode_mcp"))
    assert path.read_text() == '// keep\n{}'


@pytest.mark.parametrize("writer", [shell_writer, "python"])
@pytest.mark.parametrize("state", [{"disabled": True}, {"disabled": False}, {"enabled": False}, {"enabled": True}])
def test_owned_nested_server_named_servers_preserves_identity_and_state(tmp_path, writer, state):
    path = tmp_path / "opencode.json"
    entry = {"type": "local", "command": COMMAND, **state}
    path.write_text(json.dumps({"mcp": {"servers": {"servers": entry}}}))
    if writer == "python":
        register_server(AgentTarget("opencode", path, "json_opencode_mcp"))
    else:
        assert shell_writer(path).returncode == 0
    servers = json.loads(path.read_text())["mcp"]["servers"]
    assert set(servers) == {"servers"}
    assert "enabled" not in servers["servers"]
    assert servers["servers"]["disabled"] is state.get("disabled", not state.get("enabled", True))
    original = path.read_bytes()
    if writer == "python":
        assert register_server(AgentTarget("opencode", path, "json_opencode_mcp"))[0] is False
    else:
        assert shell_writer(path).returncode == 0
    assert path.read_bytes() == original
