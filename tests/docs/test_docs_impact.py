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


def test_module_dependency_metadata_maps_to_module_docs(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = analyze_docs_impact(root, ["packages/auth/package.json"])

    assert report["impacts"] == [{
        "path": "packages/auth/README.md",
        "status": "review_required",
        "reasons": ["module_dependency_metadata_changed"],
        "changed_files": ["packages/auth/package.json"],
        "module_path": "packages/auth",
    }]


def test_dependency_metadata_uses_discovered_root_readme(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "README.md").unlink()
    _write(root / "README.rst", "Project\n=======\n")

    report = analyze_docs_impact(root, ["package-lock.json"])

    assert report["impacts"][0]["path"] == "README.rst"
    assert report["missing"] == []


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


def test_git_diff_includes_deleted_paths(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = "packages/auth/README.md\n"
        stderr = ""

    def fake_run(command, **_kwargs):
        calls.append(command)
        return Completed()

    monkeypatch.setattr(impact.subprocess, "run", fake_run)

    assert changed_files_from_git(tmp_path, "base") == ["packages/auth/README.md"]
    assert "--diff-filter=ACDMR" in calls[0]


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


def test_markdown_report_is_ready_for_github_step_summary(tmp_path: Path) -> None:
    root = _project(tmp_path)
    report = analyze_docs_impact(root, ["packages/auth/src/token_service.ts"])

    rendered = format_docs_impact_markdown(report)

    assert rendered.startswith("## DocAtlas documentation impact")
    assert "`packages/auth/README.md`" in rendered
    assert "Review the listed docs" in rendered


def test_explicit_changed_path_returns_only_the_referenced_section(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write(
        root / "ARCHITECTURE.md",
        """# Architecture

## Authentication
The token service lives at `packages/auth/src/token_service.ts`.

## Payments
The payment gateway lives at `packages/payments/src/gateway.ts`.
""",
    )

    report = analyze_docs_impact(root, ["packages/auth/src/token_service.ts"])

    architecture = next(item for item in report["impacts"] if item["path"] == "ARCHITECTURE.md")
    assert architecture["sections"] == [{
        "heading_path": ["Architecture", "Authentication"],
        "reason": "references_changed_path",
        "evidence": ["packages/auth/src/token_service.ts"],
    }]


def test_explicit_changed_symbol_returns_only_matching_python_typescript_and_dart_sections(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write(
        root / "ARCHITECTURE.md",
        """# API contracts

## Python
Use `issue_token` for the Python service.

## TypeScript
Use `createSession` in the web client.

## Dart
Use `AuthNotifier` in Flutter.

## Unrelated
Use `PaymentNotifier` for payments.
""",
    )

    report = analyze_docs_impact(
        root,
        ["src/contracts.py", "web/session.ts", "lib/auth_notifier.dart"],
        changed_symbols=["issue_token", "createSession", "AuthNotifier"],
    )

    architecture = next(item for item in report["impacts"] if item["path"] == "ARCHITECTURE.md")
    assert architecture["sections"] == [
        {"heading_path": ["API contracts", "Python"], "reason": "references_changed_symbol", "evidence": ["issue_token"]},
        {"heading_path": ["API contracts", "TypeScript"], "reason": "references_changed_symbol", "evidence": ["createSession"]},
        {"heading_path": ["API contracts", "Dart"], "reason": "references_changed_symbol", "evidence": ["AuthNotifier"]},
    ]


def test_unmatched_sections_leave_file_level_recommendation_intact(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write(root / "packages" / "auth" / "README.md", "# Auth\n\n## API\nUse `issue_token`.\n")

    report = analyze_docs_impact(root, ["packages/auth/src/token_service.ts"])

    item = report["impacts"][0]
    assert item["path"] == "packages/auth/README.md"
    assert "sections" not in item


def test_symbol_evidence_does_not_pollute_changed_files(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write(root / "README.md", "# Project\n\n## Auth\nUse `issue_token`.\n")

    report = analyze_docs_impact(root, ["src/auth.py"], changed_symbols=["issue_token"])

    item = next(impact for impact in report["impacts"] if impact["path"] == "README.md")
    assert item["changed_files"] == ["src/auth.py"]
    assert item["sections"][0]["evidence"] == ["issue_token"]


def test_all_matching_paths_are_kept_as_changed_files(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write(
        root / "docs" / "auth.md",
        "# Auth\nReview `src/auth.py` together with `web/auth.ts`.\n",
    )

    report = analyze_docs_impact(root, ["src/auth.py", "web/auth.ts"])

    item = next(impact for impact in report["impacts"] if impact["path"] == "docs/auth.md")
    assert item["changed_files"] == ["src/auth.py", "web/auth.ts"]
    assert item["sections"][0]["evidence"] == ["src/auth.py", "web/auth.ts"]
