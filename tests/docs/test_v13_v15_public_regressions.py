"""End-to-end public regressions for the V13/V15 failure classes."""
from __future__ import annotations

from pathlib import Path

from docmancer.core.config import DocmancerConfig
from docmancer.docs.service import LibraryDocsService
from eval.project_context_quality.capture_public_context import capture_public_call


ROOT = Path(__file__).resolve().parents[2]
V13 = "How does DocAtlas report omitted material when a bounded documentation response cannot include everything?"
V15 = "How should current documentation answers treat CHANGELOG.md compared with current source-of-truth documentation?"


def _public_service(tmp_path):
    project = tmp_path / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[project]\nname="v13-v15-public-regression"\nversion="0.1"\n',
        encoding="utf-8",
    )
    for name in ("mcp-response-contract.md", "project-docs-mcp-workflow.md"):
        (docs / name).write_text(
            (ROOT / "docs" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (docs / "topical-noise.md").write_text(
        "# Bounded documentation diagnostics\n\n"
        "DocAtlas handles bounded documentation response validation and reports "
        "invalid project roots as warnings when a configuration cannot include "
        "every requested path. This section does not define omission semantics "
        "or source authority.\n",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: docs/mcp-response-contract.md\n"
        "    role: runbook\n"
        "    scope: project\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    description: Public bounded response contract\n"
        "  - path: docs/project-docs-mcp-workflow.md\n"
        "    role: runbook\n"
        "    scope: project\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    description: Project documentation workflow and source authority\n"
        "  - path: docs/topical-noise.md\n"
        "    role: runbook\n"
        "    scope: project\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    description: Bounded documentation diagnostics\n",
        encoding="utf-8",
    )
    config = DocmancerConfig()
    config.index.provider = "sqlite"
    config.index.db_path = str(tmp_path / "state" / "index.db")
    config.index.extracted_dir = str(tmp_path / "state" / "extracted")
    service = LibraryDocsService(config=config, config_source="explicit")
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"
    return service, project


def _capture(service, project, question):
    return capture_public_call(service, {
        "question": question,
        "project_path": str(project),
        "scope": "project",
    })["public_payload"]


def _assert_retrieval_only(payload):
    assert payload["kind"] == "docs_context"
    assert payload["answer_supported"] is False
    assert payload["answer_available"] is False
    assert payload["edit_ready"] is False
    assert payload["sources"]
    assert all(row.get("evidence_id") for row in payload["sources"])


def _visible_text(payload):
    return "\n".join(str(row.get("snippet") or "") for row in payload["sources"])


def test_v13_public_projection_keeps_general_omission_contract(tmp_path):
    service, project = _public_service(tmp_path)
    payload = _capture(service, project, V13)
    _assert_retrieval_only(payload)
    text = _visible_text(payload)
    assert "`omitted_counts`" in text
    assert "non-critical material" in text
    assert "honor that field" in text
    assert "reported as warnings" not in payload["sources"][0]["snippet"]


def test_v15_public_projection_keeps_current_vs_history_authority(tmp_path):
    service, project = _public_service(tmp_path)
    payload = _capture(service, project, V15)
    _assert_retrieval_only(payload)
    text = _visible_text(payload)
    assert "current documentation answers should use maintained source-of-truth" in text
    assert "`CHANGELOG.md` is release-history/change" in text
    assert "treat it as primary when the question asks about releases" in text
