from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.interfaces.mcp.prefetch_tools import handle_prefetch_tool
from tests._shared_test_docs_service import _service_with_real_agent
from tests.test_clean_git_auto_sync import _commit_project


QUESTION = "How do I prepare local project documentation?"
README = (
    "# Local project documentation\n\n"
    'To prepare local project documentation, call prepare_docs(action="sync_project_docs"). '
    "This indexes repository docs before retrieval.\n"
)


def _project(tmp_path: Path, *, commit: bool = True) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text(README, encoding="utf-8")
    (root / "docatlas.yaml").write_text(
        "index:\n  provider: sqlite\n"
        f"  db_path: {tmp_path / 'docmancer.db'}\n"
        f"  extracted_dir: {tmp_path / 'extracted'}\n",
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(".docatlas/\n", encoding="utf-8")
    if commit:
        _commit_project(root)
    return root


def _context(service, root: Path, **arguments):
    request = {"question": QUESTION, "project_path": str(root), **arguments}
    original = deepcopy(request)
    payload = handle_context_tool("get_docs_context", request, service)
    assert request == original
    assert payload is not None
    assert payload.get("answer_supported", False) is False
    assert payload.get("edit_ready") is not True
    return payload


def test_project_docs_retains_exact_clean_preflight_action(tmp_path, monkeypatch):
    root = _project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)
    inspection = service.inspect_project_docs(str(root))

    result = service.get_project_docs(str(root), QUESTION)

    assert result.reason_code == "project_docs_found_not_indexed"
    assert result.next_action == inspection.next_action
    assert result.arguments_patch == inspection.arguments_patch
    assert result.next_actions[0]["arguments_patch"] == inspection.arguments_patch
    assert service.inspect_project_docs(str(root)).indexed_sources == []


@pytest.mark.parametrize("mode", ["auto", "project"])
@pytest.mark.parametrize("scope", [None, "project", "all"])
@pytest.mark.parametrize("question", [QUESTION, "Как подготовить локальную документацию проекта?"])
def test_public_context_retains_clean_project_sync_recovery(tmp_path, monkeypatch, mode, scope, question):
    root = _project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)
    inspection = service.inspect_project_docs(str(root))
    assert inspection.reason_code == "project_docs_found_not_indexed"
    assert inspection.requires_confirmation is False

    payload = _context(service, root, question=question, mode=mode, **({"scope": scope} if scope else {}))

    assert payload["status"] == "insufficient_evidence"
    assert payload["recovery_reason_code"] == "project_docs_found_not_indexed"
    assert payload["recovery_origin"] == "operational"
    action = payload["recommended_next_action"]
    assert action["tool"] == "prepare_docs"
    assert action["arguments_patch"] == inspection.arguments_patch
    assert action["requires_confirmation"] is False
    assert action["auto_execute"] is False
    assert service.inspect_project_docs(str(root)).indexed_sources == []


@pytest.mark.parametrize("state", ["dirty", "indeterminate"])
def test_uncertain_project_state_stays_confirmation_gated(tmp_path, monkeypatch, state):
    root = _project(tmp_path)
    if state == "dirty":
        (root / "README.md").write_text(README + "\nUncommitted draft.\n", encoding="utf-8")
    elif state == "indeterminate":
        monkeypatch.setattr(
            "docmancer.docs.application._project_docs_service_part01.git_worktree_state",
            lambda _: {"status": "indeterminate", "head": None},
        )
    service = _service_with_real_agent(tmp_path, monkeypatch)

    payload = _context(service, root)

    action = payload["recommended_next_action"]
    assert action["requires_confirmation"] is True
    assert action["confirmation_reason"] == "project_docs_preflight"
    assert action["auto_execute"] is False
    assert service.inspect_project_docs(str(root)).indexed_sources == []


def test_no_git_project_does_not_gain_clean_sync_witness(tmp_path, monkeypatch):
    root = _project(tmp_path, commit=False)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    payload = _context(service, root)

    # Legacy inspection permits explicit no-Git sync; this fix must not grant
    # the clean-Git, no-confirmation recovery permission to such a project.
    inspection = service.inspect_project_docs(str(root))
    assert inspection.diagnostics["preflight"]["auto_sync_eligible"] is False
    assert payload["recommended_next_action"]["tool"] != "prepare_docs"
    assert inspection.indexed_sources == []


@pytest.mark.parametrize("state", ["no_docs", "invalid_catalog", "module_not_found", "stale", "ready"])
def test_other_project_states_do_not_become_empty_index_recovery(tmp_path, monkeypatch, state):
    root = _project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)
    arguments = {}
    if state in {"stale", "ready"}:
        assert service.sync_project_docs(str(root), with_vectors=False).status == "success"
    if state == "no_docs":
        (root / "README.md").unlink()
        _commit_project(root)
    elif state == "invalid_catalog":
        (root / "docatlas.project-docs.yaml").write_text("documents: [\n", encoding="utf-8")
        _commit_project(root)
    elif state == "module_not_found":
        arguments = {"scope": "module", "module_path": "missing/module"}
    elif state == "stale":
        (root / "README.md").write_text(README + "\nA new committed documentation rule.\n", encoding="utf-8")
        _commit_project(root)
    elif state == "ready":
        arguments = {"question": "What is the undocumented private password?"}

    payload = _context(service, root, **arguments)

    assert payload.get("recovery_reason_code") != "project_docs_found_not_indexed"
    action = payload.get("recommended_next_action") or {}
    if state in {"no_docs", "invalid_catalog", "module_not_found", "ready"}:
        assert (action.get("arguments_patch") or {}).get("action") != "sync_project_docs"


def test_edit_request_does_not_gain_permission_from_clean_sync_recovery(tmp_path, monkeypatch):
    root = _project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    payload = _context(service, root, question="Fix src/server.py to validate project paths.")

    assert payload["kind"] == "patch_context"
    assert payload.get("edit_ready") is not True
    assert service.inspect_project_docs(str(root)).indexed_sources == []


@pytest.mark.parametrize("change", ["dirty", "head", "digest", "no_git", "indeterminate", "preflight"])
def test_public_recovery_action_rechecks_witness_before_sync(tmp_path, monkeypatch, change):
    root = _project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)
    payload = _context(service, root)
    action = deepcopy(payload["recommended_next_action"])
    assert action["tool"] == "prepare_docs"
    if change == "dirty":
        (root / "draft.txt").write_text("untracked draft\n", encoding="utf-8")
    elif change == "head":
        (root / "README.md").write_text(README + "\nA changed committed rule.\n", encoding="utf-8")
        _commit_project(root)
    elif change == "no_git":
        (root / ".git").rename(root / ".git.saved")
    elif change == "indeterminate":
        for module in (
            "docmancer.docs.application._project_docs_service_part01",
            "docmancer.docs.interfaces.mcp.prefetch_tools",
        ):
            monkeypatch.setattr(f"{module}.git_worktree_state", lambda _: {"status": "indeterminate"})
    elif change == "preflight":
        inspection = service.inspect_project_docs(str(root))
        preflight = {**inspection.diagnostics["preflight"], "auto_sync_eligible": False}
        monkeypatch.setattr(
            service.project_docs, "inspect_project_docs",
            lambda _: replace(
                inspection, requires_confirmation=True,
                diagnostics={**inspection.diagnostics, "preflight": preflight},
            ),
        )
    else:
        action["arguments_patch"]["plan_digest"] = "0" * 64

    result = handle_prefetch_tool(action["tool"], action["arguments_patch"], service)

    assert result is not None
    assert result["status"] == "precondition_failed"
    assert result["requires_confirmation"] is True
    assert service.inspect_project_docs(str(root)).indexed_sources == []


def test_public_recovery_sync_then_retry_returns_current_quote(tmp_path, monkeypatch):
    root = _project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)
    payload = _context(service, root, scope="all")
    action = payload["recommended_next_action"]
    assert action["tool"] == "prepare_docs"

    prepared = handle_prefetch_tool(action["tool"], action["arguments_patch"], service)
    assert prepared is not None and prepared["status"] == "success"
    retried = _context(service, root, scope="all")

    assert retried["status"] == "ok"
    assert retried["context_available"] is True
    assert any(
        source["path_or_url"] == "README.md"
        and source["snippet"] in README
        and 'sync_project_docs' in source["snippet"]
        for source in retried["sources"]
    )
