from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


def test_project_index_cleanup_is_preview_first_and_mcp_requires_confirmation(tmp_path):
    project = tmp_path / "project"
    storage = project / ".docmancer"
    extracted = storage / "extracted"
    extracted.mkdir(parents=True)
    database = storage / "project.db"
    database.write_text("index", encoding="utf-8")
    (extracted / "chunk.md").write_text("extract", encoding="utf-8")
    (project / "README.md").write_text("source document", encoding="utf-8")
    (project / "docmancer.yaml").write_text(
        "index:\n"
        "  db_path: .docmancer/project.db\n"
        "  extracted_dir: .docmancer/extracted\n",
        encoding="utf-8",
    )

    cli_result = CliRunner().invoke(
        cli,
        [
            "clear-index",
            "--scope",
            "project-local",
            "--project-path",
            str(project),
            "--format",
            "json",
        ],
    )

    assert cli_result.exit_code == 0, cli_result.output
    preview = json.loads(cli_result.output)
    assert preview["status"] == "preview"
    assert preview["config_source"] == "project_local"
    assert preview["db_path"] == str(database.resolve())
    assert preview["extracted_dir"] == str(extracted.resolve())
    assert preview["plan"] == [str(database.resolve()), str(extracted.resolve())]
    assert database.exists()
    assert extracted.exists()
    assert (project / "README.md").exists()
    assert (project / "docmancer.yaml").exists()

    mcp_result = call_docs_tool_payload(
        "prepare_docs",
        {"action": "clear_index", "scope": "project-local", "project_path": str(project)},
        LibraryDocsService(),
    )

    assert mcp_result["status"] == "confirmation_required"
    assert mcp_result["requires_confirmation"] is True
    assert mcp_result["arguments_patch"] == {
        "action": "clear_index",
        "scope": "project-local",
        "project_path": str(project.resolve()),
        "confirm": True,
    }
    assert database.exists()
    assert extracted.exists()

    applied = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "clear_index",
            "scope": "project-local",
            "project_path": str(project),
            "confirm": True,
        },
        LibraryDocsService(),
    )

    assert applied["status"] == "applied"
    assert applied["removed"] == [str(database.resolve()), str(extracted.resolve())]
    assert not database.exists()
    assert not extracted.exists()
    assert (project / "README.md").exists()
    assert (project / "docmancer.yaml").exists()
