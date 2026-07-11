import json
import tomllib
from pathlib import Path

import pytest

from docmancer.mcp import agent_config


def test_register_writes_entry(tmp_path):
    cfg = tmp_path / "settings.json"
    target = agent_config.AgentTarget("test", cfg, "json_mcpServers")
    changed, _ = agent_config.register_server(target)
    assert changed is True
    payload = json.loads(cfg.read_text())
    assert payload["mcpServers"]["docmancer"]["command"] == "doc-atlas"
    assert payload["mcpServers"]["docmancer"]["args"] == ["mcp", "docs-serve"]


def test_register_is_idempotent(tmp_path):
    cfg = tmp_path / "settings.json"
    target = agent_config.AgentTarget("test", cfg, "json_mcpServers")
    agent_config.register_server(target)
    changed, _ = agent_config.register_server(target)
    assert changed is False


def test_register_preserves_other_servers(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    target = agent_config.AgentTarget("test", cfg, "json_mcpServers")
    agent_config.register_server(target)
    payload = json.loads(cfg.read_text())
    assert payload["mcpServers"]["other"] == {"command": "x"}
    assert "docmancer" in payload["mcpServers"]


def test_register_preserves_existing_env(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({
        "mcpServers": {
            "docmancer": {
                "command": "docmancer",
                "args": ["mcp", "serve"],
                "env": {"DOCMANCER_HOME": "/custom/home"},
            }
        }
    }))
    target = agent_config.AgentTarget("test", cfg, "json_mcpServers")

    changed, _ = agent_config.register_server(target)

    assert changed is True
    payload = json.loads(cfg.read_text())
    assert payload["mcpServers"]["docmancer"] == {
        "command": "doc-atlas",
        "args": ["mcp", "docs-serve"],
        "env": {"DOCMANCER_HOME": "/custom/home"},
    }


def test_register_refuses_to_overwrite_unrelated_docmancer_entry(tmp_path):
    cfg = tmp_path / "settings.json"
    original = {"mcpServers": {"docmancer": {"command": "custom-docs", "args": ["serve"]}}}
    cfg.write_text(json.dumps(original))
    target = agent_config.AgentTarget("test", cfg, "json_mcpServers")

    with pytest.raises(ValueError, match="refusing to overwrite"):
        agent_config.register_server(target)

    assert json.loads(cfg.read_text()) == original


def test_claude_code_project_target_is_project_local(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = agent_config.find_agent("claude-code", project=True)
    assert target is not None
    assert target.config_path == Path(".mcp.json")


def test_unregister_removes(tmp_path):
    cfg = tmp_path / "settings.json"
    target = agent_config.AgentTarget("test", cfg, "json_mcpServers")
    agent_config.register_server(target)
    assert agent_config.unregister_server(target) is True
    payload = json.loads(cfg.read_text())
    assert "docmancer" not in payload["mcpServers"]


def test_unregister_preserves_a_user_modified_docmancer_entry(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"mcpServers": {"docmancer": {"command": "custom-docs"}}}))
    target = agent_config.AgentTarget("test", cfg, "json_mcpServers")

    assert agent_config.unregister_server(target) is False
    assert json.loads(cfg.read_text())["mcpServers"]["docmancer"] == {"command": "custom-docs"}


def test_unregister_preserves_a_user_modified_codex_entry(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[mcp_servers.docmancer]\ncommand = "custom-docs"\nargs = []\n')
    target = agent_config.AgentTarget("codex", cfg, "toml_mcp_servers")

    assert agent_config.unregister_server(target) is False
    assert "custom-docs" in cfg.read_text()


def test_unregister_removes_codex_nested_server_tables(tmp_path):
    cfg = tmp_path / "config.toml"
    target = agent_config.AgentTarget("codex", cfg, "toml_mcp_servers")
    agent_config.register_server(target)
    cfg.write_text(
        cfg.read_text()
        + '\n[mcp_servers.docmancer.env]\nTOKEN = "secret"\n\n[other]\nvalue = 1\n'
    )

    assert agent_config.unregister_server(target) is True
    payload = tomllib.loads(cfg.read_text())
    assert "docmancer" not in payload.get("mcp_servers", {})
    assert payload["other"]["value"] == 1


def test_register_writes_codex_toml_entry(tmp_path):
    cfg = tmp_path / "config.toml"
    target = agent_config.AgentTarget("codex", cfg, "toml_mcp_servers")

    changed, _ = agent_config.register_server(target)

    assert changed is True
    payload = tomllib.loads(cfg.read_text())
    assert payload["mcp_servers"]["docmancer"] == {"command": "doc-atlas", "args": ["mcp", "docs-serve"]}


def test_register_writes_opencode_and_vscode_project_entries(tmp_path):
    opencode = agent_config.AgentTarget("opencode", tmp_path / "opencode.json", "json_opencode_mcp")
    vscode = agent_config.AgentTarget("github-copilot", tmp_path / "mcp.json", "json_vscode_servers")

    agent_config.register_server(opencode)
    agent_config.register_server(vscode)

    assert json.loads(opencode.config_path.read_text())["mcp"]["docmancer"] == {
        "type": "local", "command": ["doc-atlas", "mcp", "docs-serve"], "enabled": True,
    }
    assert json.loads(vscode.config_path.read_text())["servers"]["docmancer"] == {
        "type": "stdio", "command": "doc-atlas", "args": ["mcp", "docs-serve"],
    }
