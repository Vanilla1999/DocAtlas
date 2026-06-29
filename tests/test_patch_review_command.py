from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.docs.application.patch_review_service import PatchReviewService
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



def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker)
    rest = text[start + len(marker):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def test_patch_review_summary_prioritizes_actionable_items_and_demotes_noise(tmp_path: Path):
    repo = _repo(tmp_path)
    _write(repo / "docs/research/normal-architecture-note.md", "NormalArchitectureService owns reviewable project architecture.\n")
    _write(repo / "docs/research/docatlas-dogfood-v2/review-value-v2.md", "DocAtlas patch-review dogfood v2 says DogfoodMemoService owns everything.\n")
    _write(repo / "docs/research/docatlas-dogfood-v2/foo/task.md", "DogfoodTaskService owns task artifacts.\n")
    _write(repo / "lib/navigation_observer.dart", "void onHide() {}\n")
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(
        repo / "lib/presentation/menu_view.dart",
        """
import 'package:app/localization.dart';
// TODO: keep this surgical
void buildMenu() {
  final text = LocaleKeys.menu.tr();
  menuNotifierController.closeMenu();
  ref.read(tabBrowserNotifierProvider.notifier).openInfo();
  barrierDismissible: false;
  onHide();
}
""",
    )
    out = tmp_path / "review"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review-only: keep patch surgical, close menu before transition actions, reuse existing openInfo path, do not edit generated files or lockfiles, keep policy logic out of UI/provider.",
            "--output-dir",
            str(out),
            "--strict",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = (out / "review_summary.md").read_text(encoding="utf-8")
    constraints = json.loads((out / "constraints.json").read_text(encoding="utf-8"))
    actionable = _section(summary, "Actionable PR checklist")
    low = _section(summary, "Low-confidence / noisy signals")
    unknown = _section(summary, "Unknown/manual review buckets")
    quality = _section(summary, "Review summary quality")

    assert "Review summary quality" in summary
    assert "Generated files" in actionable or "generated artifacts" in actionable
    assert "policy" in actionable.lower() or "provider" in actionable.lower()
    assert "DogfoodMemoService" not in summary
    assert "docs/research/docatlas-dogfood-v2/review-value-v2.md" not in actionable
    assert "DogfoodTaskService" not in summary
    assert "TODO" not in actionable
    assert "package" not in actionable
    assert "symbol `tr`" not in actionable
    assert "symbol `onHide`" not in actionable
    assert "symbol `barrierDismissible`" not in actionable
    assert "low-confidence/noisy symbols hidden from checklist" in summary
    assert "tr" in low or "barrierDismissible" in low or "onHide" in low
    assert "bucket" in quality
    assert "Source-of-truth ownership unknowns" in unknown or "Provider/UI policy ownership unknowns" in unknown
    reasons = {item["reason"] for item in constraints["excluded_source_reasons"]}
    assert "dogfood_result_memo" in reasons
    assert "dogfood_task_artifact" in reasons


def test_patch_review_summary_sections_stay_ordered_without_full_markdown_snapshot():
    summary = PatchReviewService._review_summary(
        "Review changed-file-local menu action and keep policy out of UI/provider",
        ["lib/presentation/menu_view.dart"],
        {
            "constraints": [
                {
                    "id": "generated-guardrail",
                    "type": "generated_file",
                    "instruction": "Generated files must not be edited by hand.",
                    "source": "docs/architecture.md",
                    "confidence": "high",
                    "evidence": "Generated files must not be edited by hand.",
                    "symbols": [],
                    "files": [],
                },
                {
                    "id": "menu-local",
                    "type": "source_of_truth",
                    "instruction": "Reuse the changed-file-local closeMenu action before transitions.",
                    "source": "lib/presentation/menu_view.dart",
                    "confidence": "medium",
                    "evidence": "menuNotifierController.closeMenu();",
                    "symbols": ["closeMenu"],
                    "files": ["lib/presentation/menu_view.dart"],
                },
                {
                    "id": "provider-policy",
                    "type": "architecture",
                    "instruction": "Provider/UI code must keep policy decisions out of the menu view.",
                    "source": "docs/architecture.md",
                    "confidence": "high",
                    "evidence": "Provider/UI code must delegate policy decisions.",
                    "symbols": [],
                    "files": [],
                },
            ],
            "symbol_candidates": [
                {"term": "tr", "matched_symbol": "tr", "source": "lib/presentation/menu_view.dart", "reason": "identifier match", "evidence": "LocaleKeys.menu.tr();"}
            ],
            "excluded_source_reasons": [
                {"path": "docs/research/docatlas-dogfood-v4/review-value-v4.md", "reason": "dogfood_result_memo"}
            ],
        },
        {
            "satisfied": 1,
            "violated": 0,
            "unknown": 1,
            "results": [
                {"constraint_id": "menu-local", "status": "unknown", "reason": "provider/UI policy ownership needs review", "files": []}
            ],
            "warnings": [],
        },
    )
    expected_order = [
        "## Changed files",
        "## Review summary quality",
        "## Actionable PR checklist",
        "## Manual review context",
        "## Low-confidence / noisy signals",
        "## Validation",
        "## Violations",
        "## Unknown/manual review buckets",
        "## Generated/lockfile checks",
        "## Source-of-truth / symbol notes",
        "## Excluded or ignored sources",
        "## Claims avoided",
    ]

    positions = [summary.index(section) for section in expected_order]
    assert positions == sorted(positions)
    assert "- attachable: maybe" in summary
    assert "- actionable_items_limit: 5" in summary
    assert "- unknown_bucket_count: 1" in summary
    assert "- residual_memo_source_count: 1" in summary
    assert "symbol `tr`" in _section(summary, "Low-confidence / noisy signals")
    assert "symbol `tr`" not in _section(summary, "Actionable PR checklist")


def test_patch_review_summary_quality_can_be_yes_or_no_without_raw_data_loss():
    yes_summary = PatchReviewService._review_summary(
        "Review generated-file guardrails",
        ["lib/presentation/menu_view.dart"],
        {
            "constraints": [
                {
                    "id": f"guardrail-{index}",
                    "type": "generated_file",
                    "instruction": f"Generated/lockfile guardrail {index} must hold.",
                    "source": "docs/architecture.md",
                    "confidence": "high",
                    "evidence": "Generated files must not be edited by hand.",
                    "symbols": [],
                    "files": [],
                }
                for index in range(3)
            ],
            "symbol_candidates": [],
            "excluded_source_reasons": [],
        },
        {"satisfied": 3, "violated": 0, "unknown": 0, "results": [], "warnings": []},
    )
    no_summary = PatchReviewService._review_summary(
        "Review broad context only",
        ["lib/presentation/menu_view.dart"],
        {
            "constraints": [
                {
                    "id": "broad-context",
                    "type": "architecture",
                    "instruction": "Rules that must not be violated live in broad docs.",
                    "source": "docs/architecture.md",
                    "confidence": "medium",
                    "evidence": "Rules that must not be violated.",
                    "symbols": [],
                    "files": [],
                }
            ],
            "symbol_candidates": [],
            "excluded_source_reasons": [],
        },
        {
            "satisfied": 0,
            "violated": 0,
            "unknown": 1,
            "results": [{"constraint_id": "broad-context", "status": "unknown", "reason": "manual review required", "files": []}],
            "warnings": [],
        },
    )

    assert "- attachable: yes" in yes_summary
    assert "- attachable: no" in no_summary
    assert "- unknown/manual review: 1" in no_summary
    assert "broad-context: manual review required" in no_summary


def test_patch_review_summary_max_items_limits_actionable_checklist(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
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



def test_patch_review_summary_modes_control_markdown_verbosity():
    packet = {
        "constraints": [
            {
                "id": "guardrail",
                "type": "generated_file",
                "instruction": "Generated files must not be edited by hand.",
                "source": "docs/architecture.md",
                "confidence": "high",
                "evidence": "Generated files must not be edited by hand.",
                "symbols": [],
                "files": [],
            },
            {
                "id": "manual-context",
                "type": "architecture",
                "instruction": "Broad architecture context should be manually reviewed.",
                "source": "docs/architecture.md",
                "confidence": "medium",
                "evidence": "Manual review required.",
                "symbols": [],
                "files": [],
            },
        ],
        "symbol_candidates": [
            {"term": "open", "matched_symbol": "openInfo", "source": "lib/menu.dart", "reason": "identifier match", "evidence": "openInfo();"}
        ],
        "excluded_source_reasons": [
            {"path": "docs/research/docatlas-dogfood-v4/review-value-v4.md", "reason": "dogfood_result_memo"}
        ],
    }
    validation = {
        "satisfied": 1,
        "violated": 0,
        "unknown": 1,
        "results": [{"constraint_id": "manual-context", "status": "unknown", "reason": "manual review required", "files": []}],
        "warnings": [],
    }

    compact = PatchReviewService._review_summary(
        "Review openInfo path",
        ["lib/menu.dart"],
        packet,
        validation,
        summary_mode="compact",
    )
    verbose = PatchReviewService._review_summary(
        "Review openInfo path",
        ["lib/menu.dart"],
        packet,
        validation,
        summary_mode="verbose",
    )

    assert "- summary_mode: compact" in compact
    assert "## Actionable PR checklist" in compact
    assert "## Violations" in compact
    assert "## Manual review context" not in compact
    assert "## Unknown/manual review buckets" not in compact
    assert "## Excluded or ignored sources" not in compact
    assert "## Claims avoided" in compact

    assert "- summary_mode: verbose" in verbose
    assert "## Manual review context" in verbose
    assert "## Unknown/manual review buckets" in verbose
    assert "## Excluded or ignored sources" in verbose
    assert "## Source-of-truth / symbol notes" in verbose


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
