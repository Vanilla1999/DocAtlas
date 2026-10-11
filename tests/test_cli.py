import json
import os
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from docmancer._version import __version__
from docmancer.cli.__main__ import cli
from docmancer.cli.ui import display_path


def _declare_docs(root, *paths):
    """Fixtures use literal membership, never implicit README discovery."""
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "code_files": [],
        "documents": [{"path": path,
            "role": "module_architecture" if path.startswith("packages/") else "overview",
            "scope": "module" if path.startswith("packages/") else "project",
            "module_path": "packages/auth" if path.startswith("packages/auth/") else None,
            "description": "Explicit fixture documentation membership.",
            "authority": "source_of_truth", "status": "active", "impact": "track"}
            for path in paths],
    }), encoding="utf-8")


class FakeDocmancerConfig:
    def __init__(self, data=None):
        defaults = {
            "index": {"provider": "sqlite", "db_path": str(Path.home() / ".docatlas" / "docatlas.db"), "extracted_dir": ""},
            "query": {"default_budget": 1200, "default_limit": 8, "default_expand": "adjacent"},
            "web_fetch": {"workers": 8, "default_page_cap": 500, "browser_fallback": False},
        }
        data = data or {}
        self._data = {
            **defaults,
            **data,
            "index": {**defaults["index"], **data.get("index", {})},
            "query": {**defaults["query"], **data.get("query", {})},
            "web_fetch": {**defaults["web_fetch"], **data.get("web_fetch", {})},
        }
        self.index = type("Index", (), {})()
        self.index.provider = self._data["index"]["provider"]
        self.index.db_path = self._data["index"]["db_path"]
        self.index.extracted_dir = self._data["index"].get("extracted_dir", "")
        self.query = type("Query", (), {})()
        self.query.default_budget = self._data["query"]["default_budget"]
        self.web_fetch = type("WebFetch", (), {})()
        self.web_fetch.workers = self._data["web_fetch"]["workers"]

    def model_dump(self):
        self._data["index"]["db_path"] = self.index.db_path
        self._data["index"]["extracted_dir"] = self.index.extracted_dir
        self._data["query"]["default_budget"] = self.query.default_budget
        self._data["web_fetch"]["workers"] = self.web_fetch.workers
        return self._data

    @classmethod
    def from_yaml(cls, path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        db_path = data.get("index", {}).get("db_path", ".docatlas/docatlas.db")
        if not Path(db_path).is_absolute():
            data.setdefault("index", {})["db_path"] = str((Path(path).parent / db_path).resolve())
        return cls(data)


PUBLIC_COMMAND_HELP_CASES = [
    ("setup", ["doc-atlas setup --all"]),
    ("add", ["doc-atlas add https://docs.example.com"]),
    ("ingest", ["doc-atlas ingest ./docs", "--format"]),
    ("query", ["doc-atlas query", "--expand", "--format json"]),
    ("list", ["doc-atlas list"]),
    ("install", ["doc-atlas install claude-code", "--project"]),
    ("inspect", ["doc-atlas inspect --config ./docatlas.yaml"]),
    ("doctor", ["doc-atlas doctor --config ./docatlas.yaml"]),
    ("docs-impact", ["doc-atlas docs-impact --base origin/main", "--changed-file"]),
    ("agent-contract", ["doc-atlas agent-contract --project-path .", "--format json"]),
    ("remove", ["doc-atlas remove"]),
    ("mcp", ["docs-serve", "packs-serve"]),
    ("qdrant", ["status", "upgrade"]),
]


def test_cli_help():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Compress documentation context" in result.output
    assert "add" in result.output
    assert "setup" in result.output
    assert "mcp" in result.output

    with patch("docmancer.cli.help._unicode_help_supported", return_value=False):
        ascii_result = CliRunner().invoke(cli, ["--help"])
    assert ascii_result.exit_code == 0
    assert "DOCATLAS" in ascii_result.output
    assert "█" not in ascii_result.output




def test_docs_impact_cli_returns_machine_readable_report(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    module = tmp_path / "packages" / "auth"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Auth\n", encoding="utf-8")
    _declare_docs(tmp_path, "README.md", "packages/auth/README.md")

    result = CliRunner().invoke(
        cli,
        [
            "docs-impact",
            "--project-path", str(tmp_path),
            "--changed-file", "packages/auth/src/token_service.ts",
            "--format", "json",
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["summary"]["docs_to_review"] == 1
    assert report["impacts"][0]["path"] == "packages/auth/README.md"


def test_docs_impact_cli_can_fail_for_missing_module_docs(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "docs-impact",
            "--project-path", str(tmp_path),
            "--changed-file", "apps/web/src/routes.ts",
            "--fail-on-missing",
        ],
    )

    assert result.exit_code == 2
    assert "Documentation gaps" in result.output


def test_docs_impact_cli_accepts_changed_symbols_for_section_hints(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Project\n\n## Authentication\nUse `issue_token`.\n", encoding="utf-8"
    )
    _declare_docs(tmp_path, "README.md")

    result = CliRunner().invoke(
        cli,
        [
            "docs-impact",
            "--project-path", str(tmp_path),
            "--changed-file", "src/auth.py",
            "--changed-symbol", "issue_token",
            "--format", "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["impacts"][0]["sections"][0]["evidence"] == ["issue_token"]


def test_docs_impact_cli_requires_exact_git_evidence_before_sync(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "docs-impact",
            "--project-path", str(tmp_path),
            "--changed-file", "README.md",
            "--sync-saved-docs",
        ],
    )

    assert result.exit_code == 2
    assert "requires --base/--head" in result.output


def test_docs_impact_cli_incrementally_syncs_exact_committed_doc_diff(tmp_path):
    project = tmp_path / "repo"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("# Project\n\nOld accepted docs.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(project), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(project), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(project), "config", "user.name", "Tests"], check=True)
    subprocess.run(["git", "-C", str(project), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(project), "commit", "-m", "base"], check=True, capture_output=True)
    base = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    readme.write_text("# Project\n\nNew accepted docs.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(project), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(project), "commit", "-m", "docs"], check=True, capture_output=True)
    config = tmp_path / "docatlas.yaml"
    config.write_text(
        "index:\n"
        "  provider: sqlite\n"
        f"  db_path: {tmp_path / 'index.db'}\n"
        f"  extracted_dir: {tmp_path / 'extracted'}\n",
        encoding="utf-8",
    )
    arguments = [
        "docs-impact",
        "--project-path", str(project),
        "--base", base,
        "--sync-saved-docs",
        "--format", "json",
        "--config", str(config),
    ]

    first = CliRunner().invoke(cli, arguments)
    second = CliRunner().invoke(cli, arguments)

    # Exact committed changes describe the diff, not an explicit member grant.
    # The legacy CLI flag cannot bypass the authorized prepare_docs lane.
    for result in (first, second):
        assert result.exit_code != 0
        assert isinstance(result.exception, PermissionError)
    assert not (tmp_path / "index.db").exists()
    assert not (tmp_path / "extracted").exists()
    assert readme.read_text(encoding="utf-8") == "# Project\n\nNew accepted docs.\n"


def test_agent_contract_cli_describes_project_sources_and_tool_selection(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    module = tmp_path / "packages" / "auth"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Auth\n", encoding="utf-8")
    _declare_docs(tmp_path, "README.md", "packages/auth/README.md")
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "18.3.1"}}', encoding="utf-8")

    result = CliRunner().invoke(cli, ["agent-contract", "--project-path", str(tmp_path), "--format", "json"])

    assert result.exit_code == 0, result.output
    contract = json.loads(result.output)
    assert contract["schema_version"] == "agent-contract-1"
    assert contract["tool_selection"]["default_tool"] == "get_docs_context"
    assert "docs_status for an explicit health" in contract["tool_selection"]["decision_rule"]
    assert {item["path"] for item in contract["project"]["documentation"]} == {"README.md", "packages/auth/README.md"}
    assert contract["project"]["dependencies"] == []
    assert any("Dependency/source metadata unresolved" in warning
        for warning in contract["warnings"])
    assert 'context_format="patch_context"' in contract["tool_selection"]["decision_rule"]


def test_agent_contract_cli_can_render_markdown(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    _declare_docs(tmp_path, "README.md")

    result = CliRunner().invoke(cli, ["agent-contract", "--project-path", str(tmp_path), "--format", "markdown"])

    assert result.exit_code == 0, result.output
    assert "# DocAtlas agent contract" in result.output
    assert "`README.md`" in result.output


def test_version_flag_outputs_compact_version():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"doc-atlas {__version__}"


def test_public_commands_have_examples_in_help():
    runner = CliRunner()
    for command, expected_fragments in PUBLIC_COMMAND_HELP_CASES:
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0, result.output
        for fragment in expected_fragments:
            assert fragment in result.output


def test_ingest_url_points_to_add():
    result = CliRunner().invoke(cli, ["ingest", "https://docs.example.com"])
    assert result.exit_code != 0
    assert "Use `doc-atlas add` for URLs." in result.output


def test_cli_init_creates_project_sqlite_config(tmp_path):
    result = CliRunner().invoke(cli, ["init", "--dir", str(tmp_path)])
    assert result.exit_code == 0
    config_file = tmp_path / "docatlas.yaml"
    data = yaml.safe_load(config_file.read_text())
    assert data["index"]["db_path"] == ".docatlas/docatlas.db"
    assert "SQLite FTS5" in result.output































