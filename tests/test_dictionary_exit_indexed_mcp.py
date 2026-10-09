"""Exercise real indexing and the public MCP handler without retrieval mocks."""
import pytest

from scripts import run_project_docs_self_host_gate as gate
from tests._fixture_member_transaction import indexed_fixture_member_service


@pytest.mark.parametrize("lookup_queries", [(), ("doc-atlas mcp docs-serve",)])
def test_indexed_repo_quote_without_answer_authority_survives_public_mcp(tmp_path, monkeypatch, lookup_queries):
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
        "question": "Which command starts the Docs MCP server?",
        "project_path": str(root), "lookup_queries": list(lookup_queries),
    }, service)
    assert payload["sources"] and snapshot
    assert any(row["path_or_url"] == "README.md" and "doc-atlas mcp docs-serve" in row["snippet"]
               for row in payload["sources"])
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert gate._citation_integrity(payload, snapshot)
    assert payload["diagnostics"]["qualification_rejections"] == []
