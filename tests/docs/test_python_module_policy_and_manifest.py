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
        "docs/modules/project-context-retrieval.md": "docmancer/docs",
        "docs/modules/evidence-selection.md": "docmancer/docs",
    }
    observed = {
        entry.path: entry.module_path
        for entry in catalog.entries
        if entry.scope == "module"
    }
    assert observed == expected
    for entry in catalog.entries:
        if entry.path in expected:
            assert entry.scope == "module"
            assert entry.role == "module_architecture"
            assert entry.authority == "source_of_truth"
            assert entry.status == "active"

    # Maintained reference files are not implicit read membership. The reviewed
    # finite catalog, rather than a link or conventional location, owns access.
    unselected = {
        "docs/modules/question-planning.md",
        "docs/modules/storage-mutation-coordination.md",
        "docs/development/python-module-size-policy.md",
    }
    assert unselected.isdisjoint(entry.path for entry in catalog.entries)
    assert all((ROOT / path).is_file() for path in unselected)


def test_question_planning_and_evidence_selection_document_the_same_boundary():
    planning = (ROOT / "docs/modules/question-planning.md").read_text(encoding="utf-8")
    selection = (ROOT / "docs/modules/evidence-selection.md").read_text(encoding="utf-8")
    for document in (planning, selection):
        normalized = " ".join(document.split())
        assert "ProjectAnswerContract" in normalized
        assert "does not compile a free-form documentation question into inferred proof obligations" in normalized
        assert "original-query credit cannot be borrowed from host lookups" in normalized
        assert "cannot authorize an edit" in normalized
    assert "evidence-selection" in planning
    assert "question planning" in selection.lower()


def test_module_docs_readme_documents_sync_and_query_workflow():
    text = Path("docs/modules/README.md").read_text(encoding="utf-8")
    assert 'action="sync_project_docs"' in text
    assert 'scope="module"' in text
    assert 'module_path="modules/orion"' in text
    assert "What is ModuleEvidenceContract?" in text
