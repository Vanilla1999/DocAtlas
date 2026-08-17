from __future__ import annotations

from pathlib import Path

from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from scripts.check_python_module_size import DEFAULT_MAX_LINES, oversized_modules


ROOT = Path(__file__).resolve().parents[2]


def test_all_repository_python_modules_stay_within_hard_line_budget():
    assert oversized_modules(ROOT, DEFAULT_MAX_LINES) == []


def test_architecture_module_docs_are_registered_as_source_of_truth():
    catalog = read_project_docs_catalog(ROOT)
    assert catalog.present is True
    assert catalog.valid is True, catalog.warnings
    expected = {
        "docs/modules/question-planning.md": "docmancer/docs/domain",
        "docs/modules/evidence-selection.md": "docmancer/docs/application",
        "docs/modules/storage-mutation-coordination.md": "docmancer/docs/infrastructure",
    }
    observed = {
        entry.path: entry.module_path
        for entry in catalog.entries
        if entry.path in expected
    }
    assert observed == expected
    for entry in catalog.entries:
        if entry.path in expected:
            assert entry.scope == "module"
            assert entry.role == "module_architecture"
            assert entry.authority == "source_of_truth"
            assert entry.status == "active"

    policy = next(
        entry for entry in catalog.entries
        if entry.path == "docs/development/python-module-size-policy.md"
    )
    assert policy.scope == "project"
    assert policy.role == "development"
    assert policy.authority == "source_of_truth"
    assert policy.status == "active"


def test_question_planning_and_evidence_selection_document_the_same_boundary():
    planning = (ROOT / "docs/modules/question-planning.md").read_text(encoding="utf-8")
    selection = (ROOT / "docs/modules/evidence-selection.md").read_text(encoding="utf-8")
    assert "project-answer requirement contract" in planning
    assert "project-answer requirement contract" in selection
    assert "evidence-selection" in planning
    assert "question planning" in selection.lower()


def test_module_docs_readme_documents_sync_and_query_workflow():
    text = Path("docs/modules/README.md").read_text(encoding="utf-8")
    assert 'action="sync_project_docs"' in text
    assert 'scope="module"' in text
    assert 'module_path="modules/orion"' in text
    assert "What is ModuleEvidenceContract?" in text
