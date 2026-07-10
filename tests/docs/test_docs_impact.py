from __future__ import annotations

from pathlib import Path

from docmancer.docs.impact import analyze_docs_impact, format_docs_impact_markdown


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


def test_code_change_marks_matching_module_docs_for_review(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = analyze_docs_impact(root, ["packages/auth/src/token_service.ts"])

    assert report["summary"] == {
        "changed_files": 1,
        "code_files": 1,
        "docs_updated": 0,
        "docs_to_review": 1,
        "missing_docs": 0,
    }
    assert report["impacts"] == [{
        "path": "packages/auth/README.md",
        "status": "review_required",
        "reasons": ["module_code_changed"],
        "changed_files": ["packages/auth/src/token_service.ts"],
        "module_path": "packages/auth",
    }]


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


def test_docs_and_dependency_metadata_changes_are_explicit(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = analyze_docs_impact(root, ["docs/INDEX.md", "package-lock.json"])

    by_path = {item["path"]: item for item in report["impacts"]}
    assert by_path["docs/INDEX.md"]["status"] == "updated"
    assert by_path["docs/INDEX.md"]["reasons"] == ["documentation_changed"]
    assert by_path["README.md"]["reasons"] == ["dependency_metadata_changed"]


def test_tests_only_change_does_not_request_docs_review(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = analyze_docs_impact(root, ["tests/test_auth.py"])

    assert report["summary"]["code_files"] == 0
    assert report["impacts"] == []
    assert report["recommendation"] == "No maintained documentation changes are suggested by this diff."


def test_markdown_report_is_ready_for_github_step_summary(tmp_path: Path) -> None:
    root = _project(tmp_path)
    report = analyze_docs_impact(root, ["packages/auth/src/token_service.ts"])

    rendered = format_docs_impact_markdown(report)

    assert rendered.startswith("## DocAtlas documentation impact")
    assert "`packages/auth/README.md`" in rendered
    assert "Review the listed docs" in rendered

