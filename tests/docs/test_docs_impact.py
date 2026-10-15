from __future__ import annotations

from pathlib import Path

from docmancer.docs import impact
from docmancer.docs.impact import analyze_docs_impact, changed_files_from_git, format_docs_impact_markdown


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "README.md", "# Project\n")
    _write(root / "ARCHITECTURE.md", "# Architecture\n")
    _write(root / "docs" / "INDEX.md", "# Docs index\n")
    _write(root / "packages" / "auth" / "README.md", "# Auth module\n")
    return root


def test_module_without_docs_is_reported_as_gap(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = analyze_docs_impact(root, ["apps/web/src/routes.ts"])

    assert report["summary"]["missing_docs"] == 1
    assert report["missing"] == [{
        "module_path": "apps/web",
        "reason": "module_code_changed_without_module_docs",
        "suggested_path": "apps/web/README.md",
    }]
    assert "Create or link the missing module documentation" in report["recommendation"]


def test_dependency_metadata_without_root_readme_is_a_gap(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "README.md").unlink()

    report = analyze_docs_impact(root, ["package-lock.json"])

    assert report["impacts"] == []
    assert report["missing"] == [{
        "module_path": ".",
        "reason": "dependency_metadata_changed_without_root_readme",
        "suggested_path": "README.md",
    }]


def test_deleted_module_docs_are_reported_as_a_gap(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "packages" / "auth" / "README.md").unlink()

    report = analyze_docs_impact(root, ["packages/auth/README.md"])

    assert report["summary"]["missing_docs"] == 1
    assert report["missing"][0]["module_path"] == "packages/auth"




def test_tests_only_change_does_not_request_docs_review(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = analyze_docs_impact(root, [
        "tests/test_auth.py",
        "packages/auth/__tests__/token.ts",
        "packages/auth/src/token.spec.tsx",
        "packages/auth/token_test.go",
    ])

    assert report["summary"]["code_files"] == 0
    assert report["impacts"] == []
    assert report["recommendation"] == "No maintained documentation changes are suggested by this diff."

