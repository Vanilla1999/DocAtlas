from __future__ import annotations

from pathlib import Path

from docmancer.docs.agent_contract import build_agent_contract
from docmancer.docs.impact import analyze_docs_impact
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.project_docs_catalog import CATALOG_FILENAME, read_project_docs_catalog


def _catalog(root: Path, documents: str) -> None:
    (root / CATALOG_FILENAME).write_text(
        "schema_version: 1\ndocuments:\n" + documents,
        encoding="utf-8",
    )


def test_catalog_selects_nonstandard_docs_and_disables_guessing(tmp_path):
    (tmp_path / "handbook").mkdir()
    (tmp_path / "handbook" / "system.md").write_text("# System\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    _catalog(tmp_path, """  - path: handbook/system.md
    role: project_architecture
    scope: project
    description: Whole-project architecture and component boundaries.
    authority: source_of_truth
    status: active
    impact: track
""")

    metadata = ProjectMetadataReader().read(tmp_path)

    assert [item.path for item in metadata.docs_candidates] == ["handbook/system.md"]
    assert metadata.docs_candidates[0].description.startswith("Whole-project")
    assert metadata.docs_candidates[0].authority == "source_of_truth"


def test_absent_catalog_keeps_cold_start_discovery(tmp_path):
    (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")

    metadata = ProjectMetadataReader().read(tmp_path)

    assert [item.path for item in metadata.docs_candidates] == ["README.md"]


def test_invalid_catalog_fails_closed_instead_of_guessing(tmp_path):
    (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    (tmp_path / CATALOG_FILENAME).write_text("schema_version: 9\n", encoding="utf-8")

    metadata = ProjectMetadataReader().read(tmp_path)

    assert metadata.docs_candidates == []
    assert any("schema_version" in warning for warning in metadata.warnings)


def test_catalog_rejects_traversal_and_symlink(tmp_path):
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    (tmp_path / "linked.md").symlink_to(outside)
    _catalog(tmp_path, """  - path: ../outside.md
    role: overview
    description: Outside file must not be indexed.
  - path: linked.md
    role: overview
    description: Symlink must not be indexed.
""")

    catalog = read_project_docs_catalog(tmp_path)

    assert catalog.entries == []
    assert len(catalog.warnings) == 2


def test_agent_contract_exposes_catalog_routing_metadata(tmp_path):
    (tmp_path / "design.md").write_text("# Design\n", encoding="utf-8")
    _catalog(tmp_path, """  - path: design.md
    role: module_architecture
    scope: module
    module_path: packages/auth
    description: Authentication module architecture.
    authority: source_of_truth
    status: active
    impact: track
""")

    project = build_agent_contract(tmp_path)["project"]
    document = project["documentation"][0]

    assert document["description"] == "Authentication module architecture."
    assert document["module_path"] == "packages/auth"
    assert document["authority"] == "source_of_truth"
    assert project["documentation_catalog"]["mode"] == "explicit"


def test_search_only_and_completed_catalog_docs_do_not_create_impact(tmp_path):
    (tmp_path / "history.md").write_text("# Old plan\n", encoding="utf-8")
    _catalog(tmp_path, """  - path: history.md
    role: roadmap
    description: Completed historical implementation plan.
    authority: historical
    status: completed
    impact: search_only
""")

    report = analyze_docs_impact(tmp_path, ["src/change.py"])

    assert report["summary"]["docs_to_review"] == 0
    assert report["impacts"] == []

    changed_history = analyze_docs_impact(tmp_path, ["history.md"])
    assert changed_history["summary"]["code_files"] == 0
    assert changed_history["summary"]["docs_updated"] == 0
    assert changed_history["impacts"] == []
