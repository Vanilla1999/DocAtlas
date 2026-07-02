from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
USER_FACING_DOCS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "SKILL.md",
    ROOT / ".github" / "copilot-instructions.md",
    *sorted((ROOT / "docs").glob("*.md")),
    *sorted((ROOT / "wiki").glob("*.md")),
    *sorted((ROOT / "docmancer" / "templates").glob("*.md")),
]
FORBIDDEN_LEGACY_COMMANDS = [
    "docmancer ingest",
    "docmancer query",
    "docmancer add",
    "docmancer mcp",
    "docmancer install-pack",
    "docmancer uninstall",
    "docmancer list",
    "docmancer doctor",
    "docmancer setup",
    "docmancer qdrant",
]


def test_user_facing_docs_prefer_doc_atlas_cli():
    for path in USER_FACING_DOCS:
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_LEGACY_COMMANDS:
            assert forbidden not in text, f"{path} contains legacy user-facing command {forbidden!r}"


def test_readme_documents_naming_compatibility():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "The product name is **DocAtlas**" in text
    assert "doc-atlas --help" in text
    assert "legacy name `docmancer`" in text


def test_readme_leads_with_patch_contract_runtime_happy_path():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Project Patch Contract Runtime" in text
    assert "get_docs_context → get_patch_constraints → edit → validate_patch_against_constraints → advisory PR artifacts" in text
    assert "advisory and non-blocking" in text
    assert "does not prove a patch is safe to merge" in text


def test_readme_keeps_mcp_packs_out_of_hero_path():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    hero = text.split("## Naming and compatibility", maxsplit=1)[0]
    assert "MCP Packs" not in hero
    assert "MCP Packs are an advanced layer" in text


def test_product_brief_positions_patch_contract_runtime_before_docs_rag():
    text = (ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md").read_text(encoding="utf-8")
    assert "Project Patch Contract Runtime" in text
    assert "docs-RAG" in text
    assert text.index("Project Patch Contract Runtime") < text.index("docs-RAG")
    assert "advisory/non-blocking" in text
