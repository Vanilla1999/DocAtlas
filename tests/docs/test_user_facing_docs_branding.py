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
