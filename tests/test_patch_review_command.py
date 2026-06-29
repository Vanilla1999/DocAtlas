from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.service import LibraryDocsService


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _write(root / "docs/architecture.md", "Generated files *.g.dart must not be edited. Provider/UI must not duplicate policy; delegate to PermissionService.\n")
    _write(root / "lib/presentation/menu_view.dart", "void buildMenu() {\n}\n")
    return root


def _git(repo: Path, *args: str) -> None:
    import subprocess

    subprocess.check_call(["git", *args], cwd=repo)


def test_patch_review_command_writes_expected_artifacts(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  menuNotifier.closeMenu();\n}\n")
    out = tmp_path / "review"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Close menu before action",
            "--output-dir",
            str(out),
            "--strict",
        ],
    )

    assert result.exit_code == 0, result.output
    for name in ["constraints.json", "constraints.md", "changed_files.json", "untracked_files.json", "ignored_runtime_artifacts.json", "patch_hygiene.json", "patch.diff", "validation.json", "review_summary.md"]:
        assert (out / name).exists()
    validation = json.loads((out / "validation.json").read_text(encoding="utf-8"))
    assert "violated" in validation
    assert "unknown" in validation
    assert "Warnings" in (out / "review_summary.md").read_text(encoding="utf-8")


def test_patch_review_output_dir_is_excluded_from_future_extraction(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo / ".docatlas/patch-review/run/constraints.md", "FakeReviewService owns everything.\n")

    packet = PatchConstraintsService(LibraryDocsService()).get_patch_constraints(
        "Review patch",
        project_path=str(repo),
        max_constraints=20,
        max_tokens=4000,
    )
    payload = json.dumps(packet.__dict__, default=str)

    assert "FakeReviewService" not in payload
    assert packet.excluded_source_count >= 1


def test_patch_review_command_json_output_preserves_sources(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  context.push(MenuRoute.route);\n}\n")

    result = CliRunner().invoke(
        cli,
        ["patch-review", "--project-path", str(repo), "--task", "Navigate from menu", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["constraints"]["constraints"]
    assert any(item["source"] for item in payload["constraints"]["constraints"])
    assert payload["validation"]["violated"] == 0


def test_patch_review_includes_meaningful_untracked_files_and_warns(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/new_policy.dart", "class NewPolicy {}\n")
    out = tmp_path / "review"

    result = CliRunner().invoke(cli, ["patch-review", "--project-path", str(repo), "--task", "Review untracked source", "--output-dir", str(out)])

    assert result.exit_code == 0, result.output
    changed = json.loads((out / "changed_files.json").read_text(encoding="utf-8"))
    untracked = json.loads((out / "untracked_files.json").read_text(encoding="utf-8"))
    summary = (out / "review_summary.md").read_text(encoding="utf-8")
    assert "lib/new_policy.dart" in changed
    assert "lib/new_policy.dart" in untracked
    assert "untracked files are included in changed_files; patch.diff may not include their content" in summary


def test_patch_review_ignores_untracked_runtime_cache_artifacts(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "__pycache__/module.pyc", "cache")
    _write(repo / ".pytest_cache/v/cache/nodeids", "[]")
    out = tmp_path / "review"

    result = CliRunner().invoke(cli, ["patch-review", "--project-path", str(repo), "--task", "Review runtime files", "--output-dir", str(out)])

    assert result.exit_code == 0, result.output
    changed = json.loads((out / "changed_files.json").read_text(encoding="utf-8"))
    ignored = json.loads((out / "ignored_runtime_artifacts.json").read_text(encoding="utf-8"))
    assert "__pycache__/module.pyc" not in changed
    assert ".pytest_cache/v/cache/nodeids" not in changed
    assert "__pycache__/module.pyc" in ignored
    assert ".pytest_cache/v/cache/nodeids" in ignored


def test_patch_review_preserves_untracked_generated_and_lockfiles_for_validation(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/client.pb.go", "package generated\n")
    _write(repo / "pubspec.lock", "packages: {}\n")
    out = tmp_path / "review"

    result = CliRunner().invoke(cli, ["patch-review", "--project-path", str(repo), "--task", "Review untracked protected files", "--output-dir", str(out)])

    assert result.exit_code == 0, result.output
    changed = json.loads((out / "changed_files.json").read_text(encoding="utf-8"))
    validation = json.loads((out / "validation.json").read_text(encoding="utf-8"))
    assert "lib/generated/client.pb.go" in changed
    assert "pubspec.lock" in changed
    assert validation["violated"] >= 1
    assert any("lib/generated/client.pb.go" in result.get("files", []) or "pubspec.lock" in result.get("files", []) for result in validation["results"])
