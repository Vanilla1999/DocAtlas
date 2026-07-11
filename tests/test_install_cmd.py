import json
import zipfile
import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from docmancer.cli.__main__ import cli


class FakeDocmancerConfig:
    def __init__(self, data=None):
        self._data = data or {
            "index": {"provider": "sqlite", "db_path": ".docmancer/docmancer.db", "extracted_dir": ".docmancer/extracted"},
            "query": {"default_budget": 1200},
            "web_fetch": {"workers": 8, "default_page_cap": 500},
        }
        self.index = type("Index", (), {})()
        self.index.db_path = self._data["index"]["db_path"]
        self.index.extracted_dir = self._data["index"].get("extracted_dir", "")
        self.query = type("Query", (), {})()
        self.query.default_budget = self._data.get("query", {}).get("default_budget", 1200)
        self.web_fetch = type("WebFetch", (), {})()
        self.web_fetch.workers = self._data.get("web_fetch", {}).get("workers", 8)

    def model_dump(self):
        return self._data

    @classmethod
    def from_yaml(cls, path):
        return cls()


def _home(tmp_dir: str) -> Path:
    home = Path(tmp_dir) / "home"
    home.mkdir(exist_ok=True)
    return home


def test_install_claude_code_creates_rebooted_skill_file():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", "claude-code"])
        assert result.exit_code == 0, result.output
        skill_file = fake_home / ".claude" / "skills" / "docmancer" / "SKILL.md"
        content = skill_file.read_text()
        assert content.startswith("---\n")
        assert content.index("<!-- docmancer:start -->") > content.index("\n---\n")
        assert "allowed-tools" in content
        assert "get_docs_context" in content
        assert "prepare_docs" in content
        assert "docs_status" in content
        assert "legacy direct documentation tools" in content


def test_install_codex_creates_native_and_shared_skills():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", "codex"])
        assert result.exit_code == 0, result.output
        assert (fake_home / ".codex" / "skills" / "docmancer" / "SKILL.md").exists()
        assert (fake_home / ".agents" / "skills" / "docmancer" / "SKILL.md").exists()


def test_install_cursor_creates_agents_md_fallback():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", "cursor"])
        assert result.exit_code == 0, result.output
        agents_md = fake_home / ".cursor" / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert "get_docs_context" in content
        assert "prepare_docs" in content
        assert "docs_status" in content


def test_install_github_copilot_project_creates_repo_instructions():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", "github-copilot", "--project"])
        assert result.exit_code == 0, result.output
        copilot_md = Path(".github") / "copilot-instructions.md"
        agents_md = Path("AGENTS.md")
        vscode_settings = Path(".vscode") / "settings.json"
        assert copilot_md.exists()
        assert agents_md.exists()
        assert vscode_settings.exists()
        copilot_content = copilot_md.read_text()
        assert "get_docs_context" in copilot_content
        assert "prepare_docs" in copilot_content
        assert "docs_status" in copilot_content
        assert len(copilot_content.split()) < 250
        assert "docmancer:start" in agents_md.read_text()
        assert "github.copilot.chat.codeGeneration.useInstructionFiles" in vscode_settings.read_text()


@pytest.mark.parametrize(
    ("agent", "instruction_path"),
    [
        ("codex", "AGENTS.md"),
        ("claude-code", "CLAUDE.md"),
        ("cursor", "AGENTS.md"),
        ("github-copilot", "AGENTS.md"),
        ("opencode", "AGENTS.md"),
        ("cline", "AGENTS.md"),
        ("gemini", "AGENTS.md"),
    ],
)
def test_project_install_writes_compact_docs_mcp_bootstrap(agent: str, instruction_path: str):
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", agent, "--project"])
        assert result.exit_code == 0, result.output
        content = Path(instruction_path).read_text(encoding="utf-8")
        assert "<!-- docmancer:start -->" in content
        assert "get_docs_context" in content
        assert "prepare_docs" in content
        assert "docs_status" in content
        assert len(content.split()) < 250


def test_project_install_replaces_only_its_managed_bootstrap_block():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        instruction_path = Path("AGENTS.md")
        instruction_path.write_text(
            "# Team instructions\n\n<!-- docmancer:start -->\nold bootstrap\n<!-- docmancer:end -->\n\nKeep this text.\n",
            encoding="utf-8",
        )
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            first = runner.invoke(cli, ["install", "codex", "--project"])
            assert first.exit_code == 0, first.output
            first_content = instruction_path.read_text(encoding="utf-8")
            second = runner.invoke(cli, ["install", "codex", "--project"])
        assert second.exit_code == 0, second.output
        assert instruction_path.read_text(encoding="utf-8") == first_content
        assert "# Team instructions" in first_content
        assert "Keep this text." in first_content
        assert "old bootstrap" not in first_content
        assert first_content.count("<!-- docmancer:start -->") == 1


def test_project_install_preserves_user_text_when_appending_bootstrap():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        instruction_path = Path("AGENTS.md")
        original = "# Team instructions\n\n\n"
        instruction_path.write_text(original, encoding="utf-8")
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", "codex", "--project"])
        assert result.exit_code == 0, result.output
        assert instruction_path.read_text(encoding="utf-8").startswith(original)


def test_project_uninstall_removes_only_managed_bootstrap_block():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        instruction_path = Path("AGENTS.md")
        instruction_path.write_text("# Team instructions\n", encoding="utf-8")
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            install = runner.invoke(cli, ["install", "codex", "--project"])
            uninstall = runner.invoke(cli, ["install", "codex", "--project", "--uninstall"])
        assert install.exit_code == 0, install.output
        assert uninstall.exit_code == 0, uninstall.output
        assert instruction_path.read_text(encoding="utf-8") == "# Team instructions\n"


def test_project_uninstall_keeps_shared_bootstrap_for_another_agent():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            codex = runner.invoke(cli, ["install", "codex", "--project"])
            gemini = runner.invoke(cli, ["install", "gemini", "--project"])
            remove_gemini = runner.invoke(cli, ["install", "gemini", "--project", "--uninstall"])
            retained = Path("AGENTS.md").read_text(encoding="utf-8")
            remove_codex = runner.invoke(cli, ["install", "codex", "--project", "--uninstall"])
        assert codex.exit_code == 0, codex.output
        assert gemini.exit_code == 0, gemini.output
        assert remove_gemini.exit_code == 0, remove_gemini.output
        assert "get_docs_context" in retained
        assert remove_codex.exit_code == 0, remove_codex.output
        assert not Path("AGENTS.md").exists()


@pytest.mark.parametrize(
    ("agent", "skill_path"),
    [
        ("claude-code", ".claude/skills/docmancer/SKILL.md"),
        ("cursor", ".cursor/skills/docmancer/SKILL.md"),
        ("cline", ".cline/skills/docmancer/SKILL.md"),
        ("gemini", ".gemini/skills/docmancer/SKILL.md"),
    ],
)
def test_project_uninstall_removes_managed_project_skill(agent: str, skill_path: str):
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            install = runner.invoke(cli, ["install", agent, "--project"])
            assert Path(skill_path).exists()
            uninstall = runner.invoke(cli, ["install", agent, "--project", "--uninstall"])
        assert install.exit_code == 0, install.output
        assert uninstall.exit_code == 0, uninstall.output
        assert not Path(skill_path).exists()


def test_claude_project_uninstall_preserves_global_mcp_registration():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            global_install = runner.invoke(cli, ["install", "claude-code"])
            project_install = runner.invoke(cli, ["install", "claude-code", "--project"])
            uninstall = runner.invoke(cli, ["install", "claude-code", "--project", "--uninstall"])
        assert global_install.exit_code == 0, global_install.output
        assert project_install.exit_code == 0, project_install.output
        assert uninstall.exit_code == 0, uninstall.output
        global_config = json.loads((fake_home / ".claude/settings.json").read_text())
        assert "docmancer" in global_config["mcpServers"]
        project_config = json.loads(Path(".mcp.json").read_text())
        assert "docmancer" not in project_config["mcpServers"]


def test_global_uninstall_preserves_unmanaged_skill_text():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        skill = fake_home / ".codex" / "skills" / "docmancer" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# User notes\n", encoding="utf-8")
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            install = runner.invoke(cli, ["install", "codex"])
            uninstall = runner.invoke(cli, ["install", "codex", "--uninstall"])
        assert install.exit_code == 0, install.output
        assert uninstall.exit_code == 0, uninstall.output
        assert skill.read_text(encoding="utf-8") == "# User notes\n"


def test_project_uninstall_removes_codex_mcp_registration():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            install = runner.invoke(cli, ["install", "codex", "--project"])
            uninstall = runner.invoke(cli, ["install", "codex", "--project", "--uninstall"])
        assert install.exit_code == 0, install.output
        assert uninstall.exit_code == 0, uninstall.output
        config = Path(".codex/config.toml").read_text(encoding="utf-8")
        assert "[mcp_servers.docmancer]" not in config
        assert "Removed DocAtlas MCP registration." in uninstall.output


def test_gemini_uninstall_does_not_remove_codex_shared_skill():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            codex = runner.invoke(cli, ["install", "codex"])
            gemini = runner.invoke(cli, ["install", "gemini"])
            uninstall = runner.invoke(cli, ["install", "gemini", "--uninstall"])
        assert codex.exit_code == 0, codex.output
        assert gemini.exit_code == 0, gemini.output
        assert uninstall.exit_code == 0, uninstall.output
        assert (fake_home / ".agents/skills/docmancer/SKILL.md").exists()


def test_reinstall_migrates_marker_before_front_matter():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        skill = fake_home / ".claude/skills/docmancer/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("<!-- docmancer:start -->\n---\nname: old\n---\nold\n<!-- docmancer:end -->\n")
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", "claude-code"])
        assert result.exit_code == 0, result.output
        content = skill.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert content.count("<!-- docmancer:start -->") == 1


def test_global_uninstall_removes_fully_managed_skill_file():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        skill = fake_home / ".claude/skills/docmancer/SKILL.md"
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            install = runner.invoke(cli, ["install", "claude-code"])
            uninstall = runner.invoke(cli, ["install", "claude-code", "--uninstall"])
        assert install.exit_code == 0, install.output
        assert uninstall.exit_code == 0, uninstall.output
        assert not skill.exists()


def test_global_uninstall_preserves_user_skill_front_matter():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        skill = fake_home / ".claude/skills/docmancer/SKILL.md"
        skill.parent.mkdir(parents=True)
        user_front_matter = "---\nname: user-skill\n---\n"
        skill.write_text(user_front_matter, encoding="utf-8")
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            install = runner.invoke(cli, ["install", "claude-code"])
            uninstall = runner.invoke(cli, ["install", "claude-code", "--uninstall"])
        assert install.exit_code == 0, install.output
        assert uninstall.exit_code == 0, uninstall.output
        assert skill.read_text(encoding="utf-8") == user_front_matter


def test_reinstall_updates_owned_skill_front_matter():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        skill = fake_home / ".claude/skills/docmancer/SKILL.md"
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            first = runner.invoke(cli, ["install", "claude-code"])
            content = skill.read_text(encoding="utf-8").replace(
                "description: Source-grounded documentation workflow for coding agents.",
                "description: stale metadata",
            )
            skill.write_text(content, encoding="utf-8")
            second = runner.invoke(cli, ["install", "claude-code"])
        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        assert "description: Source-grounded documentation workflow for coding agents." in skill.read_text(encoding="utf-8")


def test_copilot_project_uninstall_removes_both_managed_instruction_blocks():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            install = runner.invoke(cli, ["install", "github-copilot", "--project"])
            uninstall = runner.invoke(cli, ["install", "github-copilot", "--project", "--uninstall"])
        assert install.exit_code == 0, install.output
        assert uninstall.exit_code == 0, uninstall.output
        assert not Path("AGENTS.md").exists()
        assert not (Path(".github") / "copilot-instructions.md").exists()


@pytest.mark.parametrize(
    ("agent", "config_path", "container_key"),
    [
        ("codex", ".codex/config.toml", "mcp_servers"),
        ("opencode", "opencode.json", "mcp"),
        ("github-copilot", ".vscode/mcp.json", "servers"),
    ],
)
def test_project_install_registers_docs_mcp_without_global_skill(agent: str, config_path: str, container_key: str):
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.mcp.agent_config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", agent, "--project"])
        assert result.exit_code == 0, result.output
        config = Path(config_path)
        if config.suffix == ".toml":
            payload = tomllib.loads(config.read_text(encoding="utf-8"))
        else:
            payload = json.loads(config.read_text(encoding="utf-8"))
        assert "docmancer" in payload[container_key]
        if agent == "codex":
            assert not (fake_home / ".codex" / "skills" / "docmancer" / "SKILL.md").exists()
        if agent == "opencode":
            assert not (fake_home / ".config" / "opencode" / "skills" / "docmancer" / "SKILL.md").exists()


def test_setup_detects_vscode_and_installs_github_copilot_project_files():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        (fake_home / "Library" / "Application Support" / "Code").mkdir(parents=True)
        fake_agent = MagicMock()
        fake_agent.collection_stats.return_value = {"sources_count": 0, "sections_count": 0}
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.core.config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_agent_class", return_value=lambda config: fake_agent):
            result = runner.invoke(cli, ["setup"])
        assert result.exit_code == 0, result.output
        assert (Path(".github") / "copilot-instructions.md").exists()
        assert (Path(".vscode") / "settings.json").exists()


def test_install_claude_desktop_creates_zip():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_config_class", return_value=FakeDocmancerConfig):
            result = runner.invoke(cli, ["install", "claude-desktop"])
        assert result.exit_code == 0, result.output
        zip_path = fake_home / ".docmancer" / "exports" / "claude-desktop" / "docmancer.zip"
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path) as zf:
                assert "docmancer/Skill.md" in zf.namelist()
                content = zf.read("docmancer/Skill.md").decode()
                assert "get_docs_context" in content
                assert "prepare_docs" in content
                assert "docs_status" in content


def test_setup_all_creates_config_db_and_installs_skills():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        fake_agent = MagicMock()
        fake_agent.collection_stats.return_value = {"sources_count": 0, "sections_count": 0}
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.core.config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_agent_class", return_value=lambda config: fake_agent):
            result = runner.invoke(cli, ["setup", "--all"])
        assert result.exit_code == 0, result.output
        assert (fake_home / ".docmancer" / "docmancer.yaml").exists()
        assert (fake_home / ".codex" / "skills" / "docmancer" / "SKILL.md").exists()
        assert (fake_home / ".docmancer" / "exports" / "claude-desktop" / "docmancer.zip").exists()


def test_setup_yes_offline_project_local_prints_readiness_summary():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        fake_agent = MagicMock()
        fake_agent.collection_stats.return_value = {"sources_count": 0, "sections_count": 0}
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.core.config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_agent_class", return_value=lambda config: fake_agent):
            result = runner.invoke(cli, ["setup", "--yes", "--offline", "--vectors", "off", "--project-local"])

        assert result.exit_code == 0, result.output
        assert Path("docmancer.yaml").exists()
        assert "Ready now" in result.output
        assert "Next best command" in result.output
        assert "doc-atlas ingest ./docs" in result.output


def test_setup_mcp_docs_prints_docs_server_command():
    runner = CliRunner()
    with runner.isolated_filesystem() as tmp_dir:
        fake_home = _home(tmp_dir)
        fake_agent = MagicMock()
        fake_agent.collection_stats.return_value = {"sources_count": 0, "sections_count": 0}
        with patch("docmancer.cli.commands.Path.home", return_value=fake_home), \
             patch("docmancer.core.config.Path.home", return_value=fake_home), \
             patch("docmancer.cli.commands._get_agent_class", return_value=lambda config: fake_agent):
            result = runner.invoke(cli, ["setup", "--profile", "mcp-docs", "--yes"])

        assert result.exit_code == 0, result.output
        assert "doc-atlas mcp docs-serve" in result.output
