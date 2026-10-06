"""Literal-needs changes preserve indexed public context, not answer authority."""
import pytest

from scripts import run_project_docs_self_host_gate as gate


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
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    config = gate.DocmancerConfig()
    config.index.db_path = str(tmp_path / "index.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    service = gate.LibraryDocsService(
        config=config, config_source="explicit",
        registry=gate.LibraryRegistry(config.index.db_path),
        agent=gate.DocmancerAgent(config=config), job_tracker=gate.DocsJobTracker(),
    )
    assert service.sync_project_docs(str(root), with_vectors=False).status == "success"
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
