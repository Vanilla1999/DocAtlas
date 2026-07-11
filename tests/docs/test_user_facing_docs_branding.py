from __future__ import annotations

from pathlib import Path
import subprocess


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


def test_readme_leads_with_three_tool_docs_runtime_happy_path():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Local-first documentation context" in text
    assert "get_docs_context → follow a returned prepare_docs action when needed → retry get_docs_context" in text
    assert "exactly three mutually exclusive tools" in text
    assert "DOCMANCER_MCP_ADVANCED_TOOLS=1" in text


def test_readme_keeps_mcp_packs_out_of_hero_path():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    hero = text.split("## Naming and compatibility", maxsplit=1)[0]
    assert "MCP Packs" not in hero
    assert "MCP Packs are an advanced layer" in text


def test_product_brief_positions_docs_mcp_before_advanced_patch_constraints():
    text = (ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md").read_text(encoding="utf-8")
    assert "local-first documentation context" in text
    assert "get_docs_context" in text
    assert "Patch constraints" in text
    assert "advanced compatibility" in text
    assert "Project Patch Contract Runtime" not in text


def test_active_docs_are_not_silently_ignored_by_gitignore():
    active_docs = [
        "docs/DOCMANCER_PRODUCT_BRIEF.md",
        "docs/RELEASE_CHECKLIST.md",
        "docs/capabilities.md",
        "docs/mcp-docs-server.md",
        "docs/FUTURE_ACTIVE_DOC.md",
    ]
    for relative_path in active_docs:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", relative_path],
            cwd=ROOT,
            check=False,
        )
        assert result.returncode == 1, f"{relative_path} is ignored by .gitignore"


def test_active_docs_stay_within_the_documentation_size_budget():
    active_docs = [
        ROOT / "README.md",
        ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md",
        ROOT / "docs" / "mcp-docs-server.md",
        ROOT / "docs" / "capabilities.md",
        ROOT / "docs" / "RELEASE_CHECKLIST.md",
    ]
    line_count = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in active_docs)
    assert line_count <= 1000, f"canonical release docs use {line_count} lines; see docs/RELEASE_CHECKLIST.md"
