from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_current_source_authority_is_documented_in_searchable_project_docs():
    workflow = (ROOT / "docs/project-docs-mcp-workflow.md").read_text(encoding="utf-8")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "CHANGELOG.md" in skill
    assert "release-history" in skill

    normalized = workflow.casefold()
    assert "changelog.md" in normalized
    assert "current" in normalized
    assert "source-of-truth" in normalized
    assert "release-history" in normalized
