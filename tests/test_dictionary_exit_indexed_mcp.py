"""Exercise real indexing and the public MCP handler without retrieval mocks."""
import pytest

from scripts import run_project_docs_self_host_gate as gate


@pytest.mark.parametrize("lookup_queries", [(), ("doc-atlas mcp docs-serve",)])
def test_indexed_repo_quote_without_answer_authority_survives_public_mcp(tmp_path, monkeypatch, lookup_queries):
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
        "question": "Which command starts the Docs MCP server?",
        "project_path": str(root), "lookup_queries": list(lookup_queries),
    }, service)
    assert payload["sources"] and snapshot
    assert any(row["path_or_url"] == "README.md" and "doc-atlas mcp docs-serve" in row["snippet"]
               for row in payload["sources"])
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert payload["estimated_tokens"] <= 800
    assert gate._citation_integrity(payload, snapshot)
    assert payload["diagnostics"]["qualification_rejections"] == []
