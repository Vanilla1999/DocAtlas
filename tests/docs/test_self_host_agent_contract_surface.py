from pathlib import Path

from docmancer.docs.project import ProjectMetadataReader

REPO = Path(__file__).resolve().parents[2]


def test_canonical_agent_workflow_is_in_self_host_corpus():
    metadata = ProjectMetadataReader().read(REPO)
    assert metadata.docs_catalog_valid
    candidate = next((row for row in metadata.docs_candidates if row.path == "SKILL.md"), None)
    assert candidate is not None
    assert candidate.doc_scope == "project"
    assert candidate.authority == "source_of_truth"


def test_canonical_agent_workflow_is_retrievable_through_public_handler(tmp_path):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
    from docmancer.docs.service import LibraryDocsService
    from docmancer.mcp.docs_server import call_docs_tool_payload

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="agent-workflow-smoke"\nversion="0.1"\n', encoding="utf-8",
    )
    (tmp_path / "SKILL.md").write_text((REPO / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
    catalog = (REPO / "docatlas.project-docs.yaml").read_text(encoding="utf-8")
    start = catalog.index("  - path: SKILL.md\n")
    end = catalog.find("\n  - path:", start + 1)
    block = catalog[start:] if end < 0 else catalog[start:end]
    (tmp_path / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\ndocuments:\n" + block + "\n", encoding="utf-8",
    )

    config = DocmancerConfig()
    config.index.provider = "sqlite"
    config.index.db_path = str(tmp_path / "state/index.db")
    config.index.extracted_dir = str(tmp_path / "state/extracted")
    service = LibraryDocsService(config=config, config_source="explicit")
    assert service.sync_project_docs(str(tmp_path), with_vectors=False).status == "success"

    payload = call_docs_tool_payload("get_docs_context", {
        "question": (
            "What is the agent workflow when a documentation target has "
            "uncertain authority, version binding or scope?"
        ),
        "project_path": str(tmp_path),
    }, service)
    text = "\n".join(source["snippet"] for source in payload.get("sources", []))
    assert any(source["path_or_url"] == "SKILL.md" for source in payload["sources"])
    assert "inspect_docs_target" in text
    assert "manifest" in text.casefold()
    assert "confirmation" in text.casefold()
    assert "validate" in text.casefold()
    assert "prefetch_docs_manifest" in text
    assert payload["edit_ready"] is False
    assert docs_context_budget_tokens(payload) <= 800
