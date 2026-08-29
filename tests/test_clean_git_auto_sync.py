from __future__ import annotations

import subprocess
from pathlib import Path

from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from tests._shared_test_docs_service import _flutter_project, _service_with_real_agent


def _commit_project(project: Path) -> str:
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    subprocess.run(["git", "-C", str(project), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(project), "config", "user.name", "Tests"], check=True)
    subprocess.run(["git", "-C", str(project), "add", "."], check=True)
    subprocess.run(["git", "-C", str(project), "commit", "-qm", "accepted docs"], check=True)
    return subprocess.run(
        ["git", "-C", str(project), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_clean_git_inspection_returns_guarded_prepare_action(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nAccepted architecture docs.\n", encoding="utf-8")
    head = _commit_project(project)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_found_not_indexed"
    assert result.requires_confirmation is False
    assert result.diagnostics["preflight"]["auto_sync_eligible"] is True
    assert result.next_action["tool"] == "prepare_docs"
    assert result.arguments_patch == {
        "action": "sync_project_docs",
        "project_path": str(project.resolve()),
        "with_vectors": False,
        "plan_digest": service.project_docs._clean_git_sync_digest(head),
    }


def test_dirty_git_requires_confirmation_before_project_docs_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nAccepted architecture docs.\n", encoding="utf-8")
    _commit_project(project)
    readme.write_text("# App\n\nUncommitted architecture draft.\n", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.requires_confirmation is True
    assert result.diagnostics["preflight"]["auto_sync_eligible"] is False
    assert "git_worktree_not_clean" in {
        risk["code"] for risk in result.diagnostics["preflight"]["risks"]
    }


def test_prepare_docs_rechecks_clean_git_before_mutating_index(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nAccepted architecture docs.\n", encoding="utf-8")
    _commit_project(project)
    service = _service_with_real_agent(tmp_path, monkeypatch)
    action = service.inspect_project_docs(str(project)).arguments_patch
    (project / "draft.txt").write_text("untracked\n", encoding="utf-8")

    result = handle_prefetch_tool("prepare_docs", action, service)

    assert result is not None
    assert result["status"] == "precondition_failed"
    assert result["reason_code"] == "clean_git_auto_sync_precondition_failed"
    assert result["requires_confirmation"] is True
    assert service.inspect_project_docs(str(project)).indexed_sources == []


def test_prepare_docs_executes_when_clean_git_witness_still_matches(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nAccepted architecture docs.\n", encoding="utf-8")
    _commit_project(project)
    service = _service_with_real_agent(tmp_path, monkeypatch)
    action = service.inspect_project_docs(str(project)).arguments_patch

    result = handle_prefetch_tool("prepare_docs", action, service)

    assert result is not None
    assert result["status"] == "success"
    assert service.inspect_project_docs(str(project)).reason_code == "project_docs_ready"


def test_get_docs_context_does_not_implicitly_sync_clean_project(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nAccepted architecture docs.\n", encoding="utf-8")
    _commit_project(project)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    UnifiedDocsContextService(service).get_docs_context(
        "How is the project organized?", project_path=str(project), mode="project"
    )

    inspection = service.inspect_project_docs(str(project))
    assert inspection.indexed_sources == []
    assert inspection.arguments_patch["plan_digest"] == service.project_docs._clean_git_sync_digest(
        inspection.diagnostics["preflight"]["git"]["head"]
    )
