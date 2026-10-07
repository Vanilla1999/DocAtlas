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
