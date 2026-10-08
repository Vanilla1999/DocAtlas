"""Literal-needs changes preserve indexed public context, not answer authority."""
import pytest

from scripts import run_project_docs_self_host_gate as gate
from tests._fixture_member_transaction import indexed_fixture_member_service


@pytest.mark.parametrize("question", [
    "How does the Docs MCP server start, and why is it required?",
    "If configuration changes, which command starts the Docs MCP server? What is the default?",
    "Compare the Docs MCP server command and its configuration requirements.",
    "Как запускается Docs MCP server и почему он нужен?",
])
def test_explicit_lookup_delivers_indexed_context_without_inferred_answer(tmp_path, monkeypatch, question):
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.setattr(gate, "REPO_ROOT", root)
    (root / "README.md").write_text(
        "# Docs MCP server\n\n"
        "The command that starts the Docs MCP server is `doc-atlas mcp docs-serve`.\n",
    )
    (root / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\ndocuments:\n  - path: README.md\n"
        "    role: overview\n    scope: project\n"
        "    description: Authored MCP fixture.\n"
        "    authority: supporting\n    status: active\n    impact: search_only\n",
        encoding="utf-8",
    )
    service, sync = indexed_fixture_member_service(
        tmp_path, monkeypatch, root, ("README.md",),
    )
    assert sync.status == "success"
    payload, snapshot = gate._call_with_snapshot({
        "question": question, "project_path": str(root),
        "lookup_queries": ["doc-atlas mcp docs-serve"],
    }, service)
    assert payload["sources"] and snapshot
    assert any(row["path_or_url"] == "README.md" and "doc-atlas mcp docs-serve" in row["snippet"]
               for row in payload["sources"])
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert payload["estimated_tokens"] <= 800
    assert gate._citation_integrity(payload, snapshot)


@pytest.mark.parametrize("question", [
    "If Client.send changes, how does it work and why is it required?",
    "Если Client.send изменится, как он работает и почему нужен?",
    "Compare A and B. What is the default?",
])
def test_recovery_diagnostics_do_not_split_or_inherit_clauses(monkeypatch, question):
    from types import SimpleNamespace
    from docmancer.docs.application import recovery
    from docmancer.docs.domain import question_frame_core

    def forbidden(*args, **kwargs):
        raise AssertionError("semantic clause parser called")

    monkeypatch.setattr(question_frame_core, "split_question_clause_spans", forbidden)
    requirements = SimpleNamespace(query_requirement_spans=(("old", 0, 2, "supported"),))
    assert recovery._problem_spans(question, requirements) == [question]
    assert recovery._problem_spans(" ", requirements) == []
    assert len(recovery._problem_spans(question * 30, requirements)[0]) <= 220
