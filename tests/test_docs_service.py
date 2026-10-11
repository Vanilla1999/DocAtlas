"""Split test module; helpers live in _shared_test_docs_service.py."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})



def test_inspect_project_docs_reports_indexed_and_stale_sources(tmp_path, monkeypatch):
    from tests._fixture_member_transaction import indexed_fixture_member_service

    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOriginal project docs.", encoding="utf-8")
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored project overview fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "roots: []\n"
        "code_files: []\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(
        tmp_path, monkeypatch, project, ("README.md",),
    )

    indexed = service.inspect_project_docs(str(project))

    assert indexed.reason_code == "project_docs_ready"
    assert indexed.next_action is None
    assert indexed.requires_confirmation is False
    assert indexed.project_docs["indexed"][0]["path"] == "README.md"
    assert indexed.project_docs["stale"] == []
    assert indexed.indexed_sources[0]["source_class"] == SOURCE_CLASS_PROJECT_FILE

    readme.write_text("# App\n\nUpdated project docs.", encoding="utf-8")
    stale = service.inspect_project_docs(str(project))

    assert stale.project_docs["stale"][0]["path"] == "README.md"
    assert stale.reason_code == "project_docs_preflight_confirmation_required"
    assert stale.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert stale.requires_confirmation is True
    assert stale.confirmation_reason == "project_docs_preflight"
    assert stale.arguments_patch == {"project_path": str(project.resolve())}
    assert "content_hash_changed" in stale.project_docs["stale"][0]["stale_reasons"]
    assert stale.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert stale.diagnostics["preflight"]["base_reason_code"] == "project_docs_stale"
    assert {risk["code"] for risk in stale.diagnostics["preflight"]["risks"]} == {"stale_project_doc_sources"}


def test_inspect_project_docs_does_not_mark_mtime_only_change_stale(tmp_path, monkeypatch):
    from tests._fixture_member_transaction import (
        fixture_member_state, indexed_fixture_member_service,
    )
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nStable project docs.", encoding="utf-8")
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored project overview fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(tmp_path, monkeypatch, project, ("README.md",))

    original = readme.stat().st_mtime_ns
    before = service.inspect_project_docs(str(project))
    assert before.reason_code == "project_docs_ready"
    assert before.project_docs["stale"] == []
    assert before.project_docs["indexed"][0]["mtime_ns"] == original
    assert before.project_docs["indexed"][0].get("metadata_drift_reasons", []) == []
    original_hash = before.project_docs["indexed"][0]["content_hash"]
    original_state = fixture_member_state(service)
    os.utime(readme, ns=(original + 10_000_000, original + 10_000_000))

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_ready"
    assert result.project_docs["stale"] == []
    assert result.project_docs["indexed"][0]["metadata_drift_reasons"] == ["mtime_changed"]
    assert result.project_docs["indexed"][0]["content_hash"] == original_hash
    assert result.project_docs["indexed"][0]["mtime_ns"] == original
    assert result.project_docs["indexed"][0]["current_mtime_ns"] == original + 10_000_000
    assert fixture_member_state(service) == original_state


def test_active_index_diagnostics_skips_vector_initialization_in_lexical_mode(
    tmp_path, monkeypatch
):
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.config.retrieval.default_mode = "lexical"
    monkeypatch.setattr(
        service.agent_gateway,
        "dispatcher_for",
        lambda *_args, **_kwargs: pytest.fail("lexical diagnostics initialized vectors"),
    )

    diagnostics = service.active_index_diagnostics()

    assert diagnostics["vector_readiness"] == {
        "status": "not_required",
        "mode": "lexical",
    }


def test_get_project_docs_never_returns_hash_mismatched_stale_content(tmp_path, monkeypatch):
    from tests._fixture_member_transaction import indexed_fixture_member_service

    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOriginalNeedle should not be returned after edits.", encoding="utf-8")
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored project overview fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "roots: []\n"
        "code_files: []\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(
        tmp_path, monkeypatch, project, ("README.md",),
    )

    before = service.get_project_docs(str(project), "OriginalNeedle", tokens=1200, limit=5)
    assert before.results
    assert {chunk.path for chunk in before.results} == {"README.md"}
    assert {chunk.source for chunk in before.results} == {str(readme)}
    assert {chunk.content_hash for chunk in before.results} == {
        "sha256:" + hashlib.sha256(readme.read_bytes()).hexdigest(),
    }
    assert any("OriginalNeedle" in chunk.content for chunk in before.results)
    readme.write_text("# App\n\nCurrent docs without the old needle.", encoding="utf-8")

    result = service.get_project_docs(str(project), "OriginalNeedle", tokens=1200, limit=5)

    assert result.answer_available is False
    assert result.results == []
    assert result.stale_sources[0]["path"] == "README.md"
    assert result.stale_sources[0]["stale_reasons"] == ["content_hash_changed"]

