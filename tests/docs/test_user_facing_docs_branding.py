from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
USER_FACING_DOCS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CONTRIBUTING.md",
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
    "pipx install docmancer",
    "pip install docmancer",
]

PRIMARY_PRODUCT_DOCS = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CONTRIBUTING.md",
    *sorted((ROOT / "docs").glob("*.md")),
    *sorted((ROOT / "wiki").glob("*.md")),
]
CANONICAL_RELEASE_DOCS = [
    ROOT / "README.md",
    ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md",
    ROOT / "docs" / "mcp-docs-server.md",
    ROOT / "docs" / "capabilities.md",
    ROOT / "docs" / "RELEASE_CHECKLIST.md",
]

def test_user_facing_docs_prefer_doc_atlas_cli():
    for path in USER_FACING_DOCS:
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_LEGACY_COMMANDS:
            assert forbidden not in text, f"{path} contains legacy user-facing command {forbidden!r}"


def test_primary_product_docs_do_not_install_legacy_distribution_extras():
    legacy_extra = re.compile(r"(?:pipx?|uv tool)\s+install\s+['\"]?docmancer\[")
    for path in PRIMARY_PRODUCT_DOCS:
        assert not legacy_extra.search(path.read_text(encoding="utf-8")), (
            f"{path} installs legacy docmancer extras instead of doc-atlas extras"
        )


def test_primary_product_docs_name_docatlas_as_the_product():
    forbidden_product_phrases = (
        "# docmancer Wiki",
        "Docmancer Docs runtime",
        "Docmancer Docs",
        "Docmancer Packs",
        "Docmancer's advanced product layer",
        "Docmancer's local",
        "Docmancer is a local-first",
        "Docmancer is a local",
        "Docmancer runs",
        "Docmancer detects",
        "Docmancer falls back",
        "Docmancer will compile",
    )
    for path in PRIMARY_PRODUCT_DOCS:
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden_product_phrases:
            assert phrase not in text, f"{path} still uses {phrase!r} as the product name"
        for line in text.splitlines():
            if "Docmancer" in line:
                allowed_compatibility_contexts = (
                    "compatibility Docmancer artifact API",
                )
                names_internal_symbol = re.search(r"\bDocmancer[A-Z][A-Za-z0-9_]*\b", line)
                assert names_internal_symbol or any(
                    context in line for context in allowed_compatibility_contexts
                ), (
                    f"{path} uses the old capitalized product name outside an explicit compatibility label: "
                    f"{line!r}"
                )


def test_patch_constraints_are_labelled_advanced_or_advisory():
    for path in PRIMARY_PRODUCT_DOCS:
        paragraphs = path.read_text(encoding="utf-8").split("\n\n")
        for paragraph in paragraphs:
            if "patch constraint" not in paragraph.lower():
                continue
            assert any(label in paragraph.lower() for label in ("advanced", "advisory", "compatibility")), (
                f"{path} presents patch constraints without an advanced/advisory label: {paragraph!r}"
            )


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
        *(path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "docs").glob("*.md"))),
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
    line_counts = {
        path.relative_to(ROOT).as_posix(): len(path.read_text(encoding="utf-8").splitlines())
        for path in CANONICAL_RELEASE_DOCS
    }
    line_count = sum(line_counts.values())
    assert line_count <= 1000, (
        f"canonical release docs use {line_count} lines ({line_counts}); see docs/RELEASE_CHECKLIST.md"
    )


def test_maturity_docs_name_the_remaining_stable_release_gates():
    brief = (ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
    assert "Task 15" in brief
    assert "Task 14" in brief
    assert "post-publish" in brief
    assert "Task 14" in checklist


def test_mcp_reference_remains_the_only_canonical_detailed_workflow():
    reference = (ROOT / "docs" / "mcp-docs-server.md").read_text(encoding="utf-8")
    assert "canonical detailed workflow reference" in reference

    expected_links = {
        ROOT / "README.md": "./docs/mcp-docs-server.md",
        ROOT / "docs" / "DOCMANCER_PRODUCT_BRIEF.md": "./mcp-docs-server.md",
        ROOT / "docs" / "capabilities.md": "./mcp-docs-server.md",
        ROOT / "docs" / "RELEASE_CHECKLIST.md": "./mcp-docs-server.md",
    }
    for path, target in expected_links.items():
        assert target in path.read_text(encoding="utf-8"), f"{path} must link to the canonical workflow"
