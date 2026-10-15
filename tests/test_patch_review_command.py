"""Split test module; helpers live in _shared_test_patch_review_command.py."""
from tests import _shared_test_patch_review_command as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

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
    for name in ["constraints.json", "constraints.md", "changed_files.json", "untracked_files.json", "ignored_runtime_artifacts.json", "patch_hygiene.json", "patch.diff", "validation.json", "constraint_coverage.json", "review_summary_actions.json", "review_summary_quality.json", "review_summary_manifest.json", "review_summary.md"]:
        assert (out / name).exists()
    validation = json.loads((out / "validation.json").read_text(encoding="utf-8"))
    assert "violated" in validation
    assert "unknown" in validation
    assert "Warnings" in (out / "review_summary.md").read_text(encoding="utf-8")


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




def test_patch_review_summary_max_items_limits_actionable_checklist(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    _write(
        repo / "docs/architecture.md",
        "\n".join(
            f"Generated files must not be edited by hand. Guardrail {index}."
            for index in range(6)
        ),
    )
    _write(repo / "lib/menu.dart", "void openInfo() {}\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    _write(repo / "lib/menu.dart", "void openInfo() {}\nvoid closeMenu() {}\n")
    out = tmp_path / "review"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review generated guardrails and menu action",
            "--summary-max-items",
            "2",
            "--output-dir",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    actionable = _section((out / "review_summary.md").read_text(), "Actionable PR checklist")
    quality = _section((out / "review_summary.md").read_text(), "Review summary quality")
    items = [line for line in actionable.splitlines() if line.startswith("- ") and line != "- none"]
    assert len(items) <= 2
    assert "- actionable_items_limit: 2" in quality

    json_result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review generated guardrails and menu action",
            "--summary-max-items",
            "2",
            "--output-dir",
            str(tmp_path / "review-json"),
            "--format",
            "json",
        ],
    )
    assert json_result.exit_code == 0, json_result.output
    assert json.loads(json_result.output)["summary_max_items"] == 2


def test_patch_review_summary_max_items_is_validated_by_cli():
    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            ".",
            "--task",
            "Review patch",
            "--summary-max-items",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert "--summary-max-items" in result.output




def test_patch_review_summary_mode_is_exposed_in_json(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  menuNotifier.closeMenu();\n}\n")
    out = tmp_path / "review-compact"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review menu navigation",
            "--summary-mode",
            "compact",
            "--output-dir",
            str(out),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary_mode"] == "compact"
    summary = (out / "review_summary.md").read_text()
    assert "- summary_mode: compact" in summary
    assert "## Manual review context" not in summary


def test_patch_review_writes_machine_readable_summary_quality(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  menuNotifier.closeMenu();\n}\n")
    out = tmp_path / "review-quality"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review menu navigation",
            "--summary-mode",
            "compact",
            "--summary-max-items",
            "2",
            "--output-dir",
            str(out),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    quality = json.loads((out / "review_summary_quality.json").read_text(encoding="utf-8"))
    summary_quality = _section((out / "review_summary.md").read_text(encoding="utf-8"), "Review summary quality")
    assert "review_summary_quality.json" in payload["artifacts"]
    assert payload["review_summary_quality"] == quality
    assert quality["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_quality.json"]
    assert quality["summary_mode"] == "compact"
    assert quality["actionable_items_limit"] == 2
    assert quality["attachable"] in {"yes", "maybe", "no"}
    assert quality["claims_avoided"] == [
        "correctness_proof",
        "test_or_human_review_replacement",
        "broad_docatlas_superiority",
    ]
    signal_codes = {item["code"] for item in quality["signals"]}
    assert "actionable_items_present" in signal_codes
    assert "no_violations" in signal_codes
    assert f"- attachable: {quality['attachable']}" in summary_quality
    assert f"- actionable_items_count: {quality['actionable_items_count']}" in summary_quality

