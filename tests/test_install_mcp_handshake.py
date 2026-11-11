"""Section 13: agent install also registers the DocAtlas MCP entry."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from tests.test_install_cmd import FakeDocmancerConfig, _home


def _run_install(tmp_dir, agent):
    fake_home = _home(tmp_dir)
    runner = CliRunner()
    with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
         patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig), \
         patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home):
        result = runner.invoke(cli, ["install", agent])
    return fake_home, result


def test_install_claude_code_registers_mcp_entry():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home, result = _run_install(tmp_dir, "claude-code")
        assert result.exit_code == 0, result.output
        cfg = fake_home / ".claude" / "settings.json"
        assert cfg.exists()
        payload = json.loads(cfg.read_text())
        assert payload["mcpServers"]["docatlas"]["command"] == "doc-atlas"
        assert payload["mcpServers"]["docatlas"]["args"] == ["mcp", "docs-serve"]
        assert "docmancer" not in payload["mcpServers"]


def test_install_cursor_registers_mcp_entry():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home, result = _run_install(tmp_dir, "cursor")
        assert result.exit_code == 0, result.output
        cfg = fake_home / ".cursor" / "mcp.json"
        assert cfg.exists()
        payload = json.loads(cfg.read_text())
        assert "docatlas" in payload["mcpServers"]


def test_install_unknown_to_mcp_agent_does_not_break_install(tmp_path):
    """Five CLI installs and one uninstall; no MCP calls or model inference.

    Exercise fresh registration, repeat, uninstall, legacy migration, explicit
    opt-in and repeat without replacing configuration or writers.
    """
    from scripts.docs_mcp_stdio_smoke import isolated_environment

    project = tmp_path / "project"
    project.mkdir(mode=0o700)
    model = tmp_path / "local-model-assets"
    model.mkdir(mode=0o700)
    repo = Path(__file__).resolve().parents[1]
    environment = isolated_environment(tmp_path)
    environment.update({
        "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1",
        "DOCATLAS_OFFLINE": "1", "DOCATLAS_MINILM_MODEL_DIR": str(model),
        # An installer's ambient setting is not an explicit server preference.
        "DOCATLAS_CONTEXT_COMPRESSION": "minilm-sections-v1",
    })
    config_path = project / "opencode.json"

    def install(*options):
        result = subprocess.run(
            [sys.executable, "-m", "docmancer.cli.__main__", "install", "opencode", "--project", *options],
            cwd=project, env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(config_path.read_text(encoding="utf-8"))

    fresh = install()
    server = fresh["mcp"]["servers"]["docatlas"]
    assert server["type"] == "local"
    assert server["command"] == ["doc-atlas", "mcp", "docs-serve"]
    registered = server["environment"]
    assert registered["DOCATLAS_MCP_TEXT_FALLBACK"] == "1"
    assert registered["DOCATLAS_MCP_COMPACT_TEXT"] == "1"
    assert registered["DOCATLAS_CONTEXT_COMPRESSION"] == "off"
    assert registered["DOCATLAS_MINILM_MODEL_DIR"] == str(model.resolve())
    assert "DOCATLAS_CONTEXT_ASSEMBLY" not in registered
    assert "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT" not in registered
    assert "DOCATLAS_EXPERIMENT_POOL_PRUNE" not in registered
    binding = json.loads(registered["DOCATLAS_PROJECT_BINDING"])
    assert binding["project_path"] == binding["workspace_path"] == str(project.resolve())
    assert (project / "AGENTS.md").is_file()
    before = config_path.read_bytes()
    install()
    assert config_path.read_bytes() == before
    removed = install("--uninstall")
    assert "docatlas" not in removed["mcp"]["servers"]

    # Existing model assets alone must not opt a legacy registration into a model.
    legacy = json.loads(before)
    owned = legacy["mcp"]["servers"].pop("docatlas")
    owned["environment"].pop("DOCATLAS_CONTEXT_COMPRESSION")
    owned["environment"]["CUSTOM"] = "preserve-user-value"
    owned.update(disabled=True, timeout={"startup": 42000})
    legacy["model"] = "preserve-host-model"
    other = {"type": "remote", "url": "https://example.test/mcp"}
    legacy["mcp"]["servers"]["other"] = other
    legacy["mcp"]["my-docs"] = owned
    config_path.write_text(json.dumps(legacy), encoding="utf-8")
    migrated = install()
    assert migrated["model"] == "preserve-host-model"
    assert set(migrated["mcp"]["servers"]) == {"my-docs", "other"}
    assert "my-docs" not in migrated["mcp"]
    assert migrated["mcp"]["servers"]["other"] == other
    assert migrated["mcp"]["servers"]["my-docs"] == {
        **owned,
        "environment": {**owned["environment"], "DOCATLAS_CONTEXT_COMPRESSION": "off"},
    }

    # A preference written in the server entry remains an explicit user opt-in.
    explicit = migrated["mcp"]["servers"]["my-docs"]["environment"]
    explicit["DOCATLAS_CONTEXT_COMPRESSION"] = "minilm-sections-v1"
    explicit["DOCATLAS_CONTEXT_ASSEMBLY"] = "literal"
    config_path.write_text(json.dumps(migrated), encoding="utf-8")
    assert install() == migrated
    before = config_path.read_bytes()
    assert install() == migrated
    assert config_path.read_bytes() == before
    assert not list(model.iterdir())
    assert not list(tmp_path.rglob("*.db"))


def test_project_install_cline_and_gemini_register_docs_mcp():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        for agent, path in (("cline", ".cline/mcp.json"), ("gemini", ".gemini/mcp.json")):
            with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
                 patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig), \
                 patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home):
                result = runner.invoke(cli, ["install", agent, "--project"])
            assert result.exit_code == 0, result.output
            payload = json.loads(Path(path).read_text())
            assert "docatlas" in payload["mcpServers"]
