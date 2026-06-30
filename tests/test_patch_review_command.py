from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.docs.application.patch_review_service import PATCH_REVIEW_SCHEMA_VERSIONS, PatchReviewService
from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.models import (
    PatchConstraint,
    PatchConstraintPacket,
    PatchConstraintValidationPacket,
    PatchConstraintValidationResult,
)
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


class _FakePrBotInvalidManifestContract(Exception):
    pass


class _FakePrBotInvalidBotBundleContract(Exception):
    pass


def _fake_pr_bot_contract_mapping(value: Any, error: type[Exception], field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise error(f"{field} must be an object")
    return value


def _fake_pr_bot_contract_list(value: Any, error: type[Exception], field: str) -> list[Any]:
    if not isinstance(value, list):
        raise error(f"{field} must be a list")
    return value


def _fake_pr_bot_contract_require(condition: bool, error: type[Exception], field: str) -> None:
    if not condition:
        raise error(f"{field} failed contract validation")


def _fake_pr_bot_consume_manifest(manifest_path: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    if manifest is None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = _fake_pr_bot_contract_mapping(manifest, _FakePrBotInvalidManifestContract, "manifest")
    _fake_pr_bot_contract_require(
        manifest.get("product_role") == "non_blocking_pr_review_assistant",
        _FakePrBotInvalidManifestContract,
        "manifest.product_role",
    )
    manifest_claims = _fake_pr_bot_contract_list(
        manifest.get("claims_avoided"),
        _FakePrBotInvalidManifestContract,
        "manifest.claims_avoided",
    )
    _fake_pr_bot_contract_require(
        "correctness_proof" in manifest_claims,
        _FakePrBotInvalidManifestContract,
        "manifest.claims_avoided.correctness_proof",
    )
    _fake_pr_bot_contract_require(
        "test_or_human_review_replacement" in manifest_claims,
        _FakePrBotInvalidManifestContract,
        "manifest.claims_avoided.test_or_human_review_replacement",
    )
    artifacts = _fake_pr_bot_contract_list(
        manifest.get("artifacts"),
        _FakePrBotInvalidManifestContract,
        "manifest.artifacts",
    )
    bundle_entries: list[dict[str, Any]] = []
    for item in artifacts:
        descriptor = _fake_pr_bot_contract_mapping(
            item,
            _FakePrBotInvalidManifestContract,
            "manifest.artifacts[]",
        )
        if descriptor.get("kind") == "bot_bundle" and descriptor.get("filename") == "review_summary_bot_bundle.json":
            bundle_entries.append(descriptor)
    _fake_pr_bot_contract_require(len(bundle_entries) == 1, _FakePrBotInvalidManifestContract, "manifest.bot_bundle")
    bundle_entry = bundle_entries[0]
    _fake_pr_bot_contract_require(
        bundle_entry.get("schema_version") == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        _FakePrBotInvalidManifestContract,
        "manifest.bot_bundle.schema_version",
    )
    intended_consumers = _fake_pr_bot_contract_list(
        bundle_entry.get("intended_consumers"),
        _FakePrBotInvalidManifestContract,
        "manifest.bot_bundle.intended_consumers",
    )
    _fake_pr_bot_contract_require("pr_bot" in intended_consumers, _FakePrBotInvalidManifestContract, "manifest.bot_bundle.pr_bot")
    safe_usage = bundle_entry.get("safe_usage")
    _fake_pr_bot_contract_require(isinstance(safe_usage, str), _FakePrBotInvalidManifestContract, "manifest.bot_bundle.safe_usage")
    safe_usage = cast(str, safe_usage)
    _fake_pr_bot_contract_require(
        "single-file bot integration entrypoint" in safe_usage,
        _FakePrBotInvalidManifestContract,
        "manifest.bot_bundle.safe_usage.entrypoint",
    )
    _fake_pr_bot_contract_require(
        "advisory non-blocking" in safe_usage,
        _FakePrBotInvalidManifestContract,
        "manifest.bot_bundle.safe_usage.non_blocking",
    )

    bundle = json.loads((manifest_path.parent / bundle_entry["filename"]).read_text(encoding="utf-8"))
    bundle = _fake_pr_bot_contract_mapping(bundle, _FakePrBotInvalidBotBundleContract, "bundle")
    decision = _fake_pr_bot_contract_mapping(
        bundle.get("advisory_decision"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.advisory_decision",
    )
    quality = _fake_pr_bot_contract_mapping(bundle.get("quality"), _FakePrBotInvalidBotBundleContract, "bundle.quality")
    actions = _fake_pr_bot_contract_mapping(bundle.get("actions"), _FakePrBotInvalidBotBundleContract, "bundle.actions")
    bundle_claims = _fake_pr_bot_contract_list(
        bundle.get("claims_avoided"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.claims_avoided",
    )
    decision_claims = _fake_pr_bot_contract_list(
        decision.get("claims_avoided"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.advisory_decision.claims_avoided",
    )
    _fake_pr_bot_contract_require(
        bundle.get("schema_version") == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        _FakePrBotInvalidBotBundleContract,
        "bundle.schema_version",
    )
    _fake_pr_bot_contract_require(bundle.get("manifest") == manifest, _FakePrBotInvalidBotBundleContract, "bundle.manifest")
    _fake_pr_bot_contract_require(
        decision.get("semantics") == "advisory_non_blocking_only",
        _FakePrBotInvalidBotBundleContract,
        "bundle.advisory_decision.semantics",
    )
    _fake_pr_bot_contract_require("safe_to_merge" not in bundle, _FakePrBotInvalidBotBundleContract, "bundle.safe_to_merge")
    _fake_pr_bot_contract_require("safe_to_merge" not in decision, _FakePrBotInvalidBotBundleContract, "decision.safe_to_merge")
    _fake_pr_bot_contract_require(
        "safe_to_merge" in decision_claims,
        _FakePrBotInvalidBotBundleContract,
        "bundle.advisory_decision.claims_avoided.safe_to_merge",
    )
    _fake_pr_bot_contract_require(
        "correctness_proof" in bundle_claims,
        _FakePrBotInvalidBotBundleContract,
        "bundle.claims_avoided.correctness_proof",
    )
    _fake_pr_bot_contract_require(
        "test_or_human_review_replacement" in bundle_claims,
        _FakePrBotInvalidBotBundleContract,
        "bundle.claims_avoided.test_or_human_review_replacement",
    )
    unknown_triage = _fake_pr_bot_contract_list(
        quality.get("unknown_triage", []),
        _FakePrBotInvalidBotBundleContract,
        "bundle.quality.unknown_triage",
    )
    unknown_triage_examples_by_code = {
        item["code"]: item.get("examples", [])
        for item in unknown_triage
        if isinstance(item, dict)
        if item.get("examples")
    }
    unknown_triage_counts = {
        item["code"]: item.get("count")
        for item in unknown_triage
        if isinstance(item, dict)
        if item.get("code") and item.get("count", 0) > 0
    }
    decision_unknown_triage_counts = decision.get("unknown_triage_counts")
    if decision_unknown_triage_counts is None:
        decision_unknown_triage_counts = unknown_triage_counts
    else:
        _fake_pr_bot_contract_require(
            isinstance(decision_unknown_triage_counts, dict) and decision_unknown_triage_counts == unknown_triage_counts,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.unknown_triage_counts",
        )
    reason_codes = list(
        _fake_pr_bot_contract_list(
            decision.get("reason_codes"),
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.reason_codes",
        )
    )
    unknown_triage_codes = _fake_pr_bot_contract_list(
        decision.get("unknown_triage_codes"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.advisory_decision.unknown_triage_codes",
    )
    for field in ["should_attach_comment", "show_warning_badge", "highlight_violations", "requires_manual_review"]:
        _fake_pr_bot_contract_require(isinstance(decision.get(field), bool), _FakePrBotInvalidBotBundleContract, f"bundle.advisory_decision.{field}")
    violations = _fake_pr_bot_contract_list(actions.get("violations", []), _FakePrBotInvalidBotBundleContract, "bundle.actions.violations")
    show_warning_badge = decision["show_warning_badge"]
    requires_manual_review = decision["requires_manual_review"]
    if quality.get("unknown_count", 0) > 0 and not decision_unknown_triage_counts:
        show_warning_badge = True
        requires_manual_review = True
        if "manual_review_required" not in reason_codes:
            reason_codes.append("manual_review_required")
    return {
        "attach_comment": decision["should_attach_comment"],
        "show_warning_badge": show_warning_badge,
        "highlight_violations": decision["highlight_violations"],
        "requires_manual_review": requires_manual_review,
        "reason_codes": reason_codes,
        "unknown_triage_codes": unknown_triage_codes,
        "unknown_triage_counts": decision_unknown_triage_counts,
        "unknown_triage_examples_by_code": unknown_triage_examples_by_code,
        "violation_count": len(violations),
        "unknown_count": quality.get("unknown_count", 0),
    }


def _fake_pr_bot_discover_output_dir(output_dir: Path) -> dict[str, Any]:
    manifest_path = output_dir / "review_summary_manifest.json"
    def manual_fallback(reason_code: str) -> dict[str, Any]:
        sibling_artifacts = sorted(
            path.name
            for path in output_dir.iterdir()
            if path.name.startswith("review_summary")
        ) if output_dir.exists() else []
        return {
            "status": "no_completed_patch_review_run",
            "attach_comment": False,
            "show_warning_badge": True,
            "highlight_violations": False,
            "requires_manual_review": True,
            "reason_codes": [reason_code],
            "ignored_sibling_artifacts": sibling_artifacts,
            "semantics": "manual_fallback_not_pass",
        }

    if not manifest_path.exists():
        return manual_fallback("missing_manifest_completed_run_marker")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return manual_fallback("invalid_manifest_completed_run_marker")
    if not isinstance(manifest, dict):
        return manual_fallback("invalid_manifest_completed_run_marker")
    if manifest.get("schema_version") != PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"]:
        return manual_fallback("unsupported_manifest_schema_version")
    try:
        consumer_payload = _fake_pr_bot_consume_manifest(manifest_path, manifest)
    except _FakePrBotInvalidManifestContract:
        return manual_fallback("invalid_manifest_completed_run_marker")
    except _FakePrBotInvalidBotBundleContract:
        return manual_fallback("invalid_bot_bundle_contract")
    except FileNotFoundError:
        return manual_fallback("missing_bot_bundle_artifact")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return manual_fallback("invalid_bot_bundle_artifact")
    return {
        "status": "completed_patch_review_run",
        **consumer_payload,
    }


def _assert_fake_pr_bot_manual_fallback(decision: dict[str, Any], reason_code: str) -> None:
    assert decision["status"] == "no_completed_patch_review_run"
    assert decision["attach_comment"] is False
    assert decision["show_warning_badge"] is True
    assert decision["highlight_violations"] is False
    assert decision["requires_manual_review"] is True
    assert decision["reason_codes"] == [reason_code]
    assert decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in decision


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
    for name in ["constraints.json", "constraints.md", "changed_files.json", "untracked_files.json", "ignored_runtime_artifacts.json", "patch_hygiene.json", "patch.diff", "validation.json", "review_summary_actions.json", "review_summary_quality.json", "review_summary_manifest.json", "review_summary.md"]:
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


def test_patch_review_quality_classifies_unknowns_without_treating_them_as_pass():
    constraints = {
        "constraints": [
            {
                "id": "diff-gap",
                "type": "source_of_truth",
                "instruction": "Close the menu before navigation.",
                "source": "docs/menu.md",
                "confidence": "high",
                "evidence": "Menu closes before navigation.",
                "symbols": ["closeMenu"],
                "files": [],
            },
            {
                "id": "test-gap",
                "type": "behavior",
                "instruction": "Add regression tests for closed request reopening.",
                "source": "docs/help.md",
                "confidence": "medium",
                "evidence": "Request reopening needs regression coverage.",
                "symbols": [],
                "files": [],
            },
            {
                "id": "manual-design",
                "type": "architecture",
                "instruction": "Designer must confirm the menu button style.",
                "source": "docs/menu.md",
                "confidence": "medium",
                "evidence": "Open designer question remains.",
                "symbols": [],
                "files": [],
            },
            {
                "id": "low-risk-note",
                "type": "architecture",
                "instruction": "Keep optional helper naming aligned with docs.",
                "source": "docs/menu.md",
                "confidence": "low",
                "evidence": "Optional naming note.",
                "symbols": [],
                "files": [],
            },
        ],
        "symbol_candidates": [],
        "excluded_source_reasons": [],
    }
    validation = {
        "satisfied": 0,
        "violated": 0,
        "unknown": 4,
        "results": [
            {"constraint_id": "diff-gap", "status": "unknown", "reason": "no direct diff evidence found", "files": []},
            {"constraint_id": "test-gap", "status": "unknown", "reason": "missing test evidence", "files": []},
            {"constraint_id": "manual-design", "status": "unknown", "reason": "manual review required for designer input", "files": []},
            {"constraint_id": "low-risk-note", "status": "unknown", "reason": "low confidence context only", "files": []},
        ],
        "warnings": [],
    }

    quality = PatchReviewService._review_summary_quality_payload(
        "Review menu redesign unknowns",
        ["lib/menu.dart"],
        constraints,
        validation,
    )

    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert triage["missing_diff_evidence"]["count"] == 1
    assert triage["missing_test_evidence"]["count"] == 1
    assert triage["manual_review_required"]["count"] == 1
    assert triage["low_risk_unknown"]["count"] == 1
    assert all(item["requires_manual_review"] for item in quality["unknown_triage"])
    assert "manual_review_required" in {signal["code"] for signal in quality["signals"]}
    assert quality["unknown_count"] == 4
    assert quality["attachable"] != "yes"


def test_patch_review_unknown_triage_examples_carry_source_evidence_for_bot_routing():
    constraints = {
        "constraints": [
            {
                "id": "open-designer-input",
                "type": "architecture",
                "instruction": "Получить инфо от дизайнера по новому виду кнопки вызова меню.",
                "source": "docs/menu.md",
                "confidence": "medium",
                "evidence": "Открытый вопрос по макету остается нерешенным.",
                "symbols": [],
                "files": [],
            }
        ],
        "symbol_candidates": [],
        "excluded_source_reasons": [],
    }
    validation = {
        "satisfied": 0,
        "violated": 0,
        "unknown": 1,
        "results": [
            {
                "constraint_id": "open-designer-input",
                "status": "unknown",
                "reason": "No decisive changed-file or diff evidence was found for this constraint.",
                "files": [],
            }
        ],
        "warnings": [],
    }

    quality = PatchReviewService._review_summary_quality_payload(
        "Review TSDB menu redesign",
        ["lib/presentation/menu_view.dart"],
        constraints,
        validation,
    )

    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert set(triage) == {"manual_review_required"}
    assert triage["manual_review_required"]["requires_manual_review"] is True
    assert triage["manual_review_required"]["examples"][0] == {
        "constraint_id": "open-designer-input",
        "reason": "No decisive changed-file or diff evidence was found for this constraint.",
        "source": "docs/menu.md",
        "instruction": "Получить инфо от дизайнера по новому виду кнопки вызова меню.",
        "evidence": "Открытый вопрос по макету остается нерешенным.",
        "confidence": "medium",
    }
    assert quality["unknown_count"] == 1
    assert quality["attachable"] != "yes"


def test_patch_review_unknown_triage_keeps_generic_design_and_manual_text_granular():
    constraints = {
        "constraints": [
            {
                "id": "design-doc-gap",
                "type": "source_of_truth",
                "instruction": "Follow the design system spacing rule.",
                "source": "docs/design.md",
                "confidence": "medium",
                "evidence": "Design tokens define menu spacing.",
                "symbols": [],
                "files": [],
            },
            {
                "id": "manual-retry-test-gap",
                "type": "behavior",
                "instruction": "Keep the manual retry command covered by tests.",
                "source": "docs/manual-retry.md",
                "confidence": "medium",
                "evidence": "Manual retry should remain available after service failures.",
                "symbols": [],
                "files": [],
            },
        ],
        "symbol_candidates": [],
        "excluded_source_reasons": [],
    }
    validation = {
        "satisfied": 0,
        "violated": 0,
        "unknown": 2,
        "results": [
            {"constraint_id": "design-doc-gap", "status": "unknown", "reason": "no direct diff evidence found", "files": []},
            {"constraint_id": "manual-retry-test-gap", "status": "unknown", "reason": "missing test evidence", "files": []},
        ],
        "warnings": [],
    }

    quality = PatchReviewService._review_summary_quality_payload(
        "Review generic design documentation and manual retry coverage",
        ["lib/menu.dart"],
        constraints,
        validation,
    )

    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert set(triage) == {"missing_diff_evidence", "missing_test_evidence"}
    assert triage["missing_diff_evidence"]["examples"][0] == {
        "constraint_id": "design-doc-gap",
        "reason": "no direct diff evidence found",
        "source": "docs/design.md",
        "instruction": "Follow the design system spacing rule.",
        "evidence": "Design tokens define menu spacing.",
        "confidence": "medium",
    }
    assert triage["missing_test_evidence"]["examples"][0] == {
        "constraint_id": "manual-retry-test-gap",
        "reason": "missing test evidence",
        "source": "docs/manual-retry.md",
        "instruction": "Keep the manual retry command covered by tests.",
        "evidence": "Manual retry should remain available after service failures.",
        "confidence": "medium",
    }
    assert all(item["requires_manual_review"] for item in quality["unknown_triage"])
    assert "manual_review_required" in {signal["code"] for signal in quality["signals"]}


def test_patch_review_bot_bundle_keeps_generic_unknowns_granular_for_consumers(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  renderDesignSystemSpacing();\n  runManualRetryCommand();\n}\n")
    out = tmp_path / "review-generic-unknowns"

    class FakeDocsService:
        def get_patch_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintPacket:
            return PatchConstraintPacket(
                task="Review generic design docs and manual retry coverage",
                constraints=[
                    PatchConstraint(
                        id="design-doc-gap",
                        type="source_of_truth",
                        instruction="Follow the design system spacing rule.",
                        source="docs/design.md",
                        severity="warning",
                        confidence="medium",
                        evidence="Design tokens define menu spacing.",
                    ),
                    PatchConstraint(
                        id="manual-retry-test-gap",
                        type="behavior",
                        instruction="Keep the manual retry command covered by tests.",
                        source="docs/manual-retry.md",
                        severity="warning",
                        confidence="medium",
                        evidence="Manual retry should remain available after service failures.",
                    ),
                ],
                confidence="medium",
            )

        def validate_patch_against_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintValidationPacket:
            return PatchConstraintValidationPacket(
                task="Review generic design docs and manual retry coverage",
                project_path=str(repo),
                total_constraints=2,
                unknown=2,
                results=[
                    PatchConstraintValidationResult(
                        constraint_id="design-doc-gap",
                        status="unknown",
                        reason="no direct diff evidence found",
                        files=[],
                    ),
                    PatchConstraintValidationResult(
                        constraint_id="manual-retry-test-gap",
                        status="unknown",
                        reason="missing test evidence",
                        files=[],
                    ),
                ],
                confidence="low",
            )

    PatchReviewService(cast(Any, FakeDocsService())).run(
        project_path=str(repo),
        task="Review generic design docs and manual retry coverage",
        output_dir=str(out),
    )

    quality = json.loads((out / "review_summary_quality.json").read_text(encoding="utf-8"))
    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert set(triage) == {"missing_diff_evidence", "missing_test_evidence"}
    assert triage["missing_diff_evidence"]["examples"][0] == {
        "constraint_id": "design-doc-gap",
        "reason": "no direct diff evidence found",
        "source": "docs/design.md",
        "instruction": "Follow the design system spacing rule.",
        "evidence": "Design tokens define menu spacing.",
        "confidence": "medium",
    }
    assert triage["missing_test_evidence"]["examples"][0] == {
        "constraint_id": "manual-retry-test-gap",
        "reason": "missing test evidence",
        "source": "docs/manual-retry.md",
        "instruction": "Keep the manual retry command covered by tests.",
        "evidence": "Manual retry should remain available after service failures.",
        "confidence": "medium",
    }
    assert "manual_review_required" in {signal["code"] for signal in quality["signals"]}

    consumer_decision = _fake_pr_bot_consume_manifest(out / "review_summary_manifest.json")
    assert consumer_decision["requires_manual_review"] is True
    assert "manual_review_required" in consumer_decision["reason_codes"]
    assert consumer_decision["unknown_triage_codes"] == ["missing_diff_evidence", "missing_test_evidence"]
    assert consumer_decision["unknown_triage_counts"] == {
        "missing_diff_evidence": 1,
        "missing_test_evidence": 1,
    }
    assert "manual_review_required" not in consumer_decision["unknown_triage_codes"]
    assert consumer_decision["unknown_count"] == 2
    assert consumer_decision["violation_count"] == 0


def test_patch_review_bot_bundle_routes_open_design_unknowns_to_manual_review(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  showMenuButton();\n}\n")
    out = tmp_path / "review-open-design-unknown"

    class FakeDocsService:
        def get_patch_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintPacket:
            return PatchConstraintPacket(
                task="Review TSDB menu redesign",
                constraints=[
                    PatchConstraint(
                        id="open-designer-input",
                        type="architecture",
                        instruction="Получить инфо от дизайнера по новому виду кнопки вызова меню.",
                        source="docs/menu.md",
                        severity="warning",
                        confidence="medium",
                        evidence="Открытый вопрос по макету остается нерешенным.",
                    )
                ],
                confidence="medium",
            )

        def validate_patch_against_constraints(self, *args: Any, **kwargs: Any) -> PatchConstraintValidationPacket:
            return PatchConstraintValidationPacket(
                task="Review TSDB menu redesign",
                project_path=str(repo),
                total_constraints=1,
                unknown=1,
                results=[
                    PatchConstraintValidationResult(
                        constraint_id="open-designer-input",
                        status="unknown",
                        reason="No decisive changed-file or diff evidence was found for this constraint.",
                        files=[],
                    )
                ],
                confidence="low",
            )

    PatchReviewService(cast(Any, FakeDocsService())).run(
        project_path=str(repo),
        task="Review TSDB menu redesign",
        output_dir=str(out),
    )

    quality = json.loads((out / "review_summary_quality.json").read_text(encoding="utf-8"))
    triage = {item["code"]: item for item in quality["unknown_triage"]}
    assert set(triage) == {"manual_review_required"}
    assert triage["manual_review_required"]["count"] == 1
    assert triage["manual_review_required"]["requires_manual_review"] is True

    consumer_decision = _fake_pr_bot_consume_manifest(out / "review_summary_manifest.json")
    assert consumer_decision["requires_manual_review"] is True
    assert "manual_review_required" in consumer_decision["reason_codes"]
    assert consumer_decision["unknown_triage_codes"] == ["manual_review_required"]
    assert consumer_decision["unknown_triage_counts"] == {"manual_review_required": 1}
    assert consumer_decision["unknown_triage_examples_by_code"] == {
        "manual_review_required": [
            {
                "constraint_id": "open-designer-input",
                "reason": "No decisive changed-file or diff evidence was found for this constraint.",
                "source": "docs/menu.md",
                "instruction": "Получить инфо от дизайнера по новому виду кнопки вызова меню.",
                "evidence": "Открытый вопрос по макету остается нерешенным.",
                "confidence": "medium",
            }
        ]
    }


def test_patch_review_writes_machine_readable_action_items(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    _write(repo / "docs/architecture.md", "Generated files must not be edited by hand. Checkout buttons call launchCheckoutFlow before navigation.\n")
    _write(repo / "lib/payments/checkout_button.dart", "void renderCheckout() {}\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    _write(repo / "lib/payments/checkout_button.dart", "void renderCheckout() { launchCheckoutFlow(); }\n")
    out = tmp_path / "review-actions"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review checkout launch action",
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
    actions = json.loads((out / "review_summary_actions.json").read_text(encoding="utf-8"))
    actionable_markdown = _section((out / "review_summary.md").read_text(encoding="utf-8"), "Actionable PR checklist")
    assert "review_summary_actions.json" in payload["artifacts"]
    assert payload["review_summary_actions"] == actions
    assert actions["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_actions.json"]
    assert actions["actionable_items_limit"] == 2
    assert 0 < len(actions["actionable_items"]) <= 2
    assert any(item["instruction"] in actionable_markdown for item in actions["actionable_items"])
    assert all(item["constraint_id"] for item in actions["actionable_items"])
    assert [item["rank"] for item in actions["actionable_items"]] == list(range(1, len(actions["actionable_items"]) + 1))
    assert all(item["markdown"] in actionable_markdown for item in actions["actionable_items"])
    assert any(item["evidence"] and item["evidence"] in item["evidence_markdown"] for item in actions["actionable_items"])
    assert any("launchCheckoutFlow" in item["evidence"] for item in actions["actionable_items"] if item["evidence"])
    assert actions["claims_avoided"] == [
        "correctness_proof",
        "test_or_human_review_replacement",
        "broad_docatlas_superiority",
    ]


def test_patch_review_writes_machine_readable_manifest(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  menuNotifier.closeMenu();\n}\n")
    out = tmp_path / "review-manifest"

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
    manifest = json.loads((out / "review_summary_manifest.json").read_text(encoding="utf-8"))
    manifest_artifacts = {item["filename"]: item for item in manifest["artifacts"]}
    assert "review_summary_manifest.json" in payload["artifacts"]
    assert payload["review_summary_manifest"] == manifest
    assert manifest["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"]
    assert manifest["summary_mode"] == "compact"
    assert manifest["product_role"] == "non_blocking_pr_review_assistant"
    assert [item["filename"] for item in manifest["artifacts"]] == payload["artifacts"]
    assert manifest_artifacts["review_summary.md"]["intended_consumers"] == ["human_reviewer"]
    assert manifest_artifacts["review_summary_quality.json"]["schema_version"] == payload["review_summary_quality"]["schema_version"]
    assert manifest_artifacts["review_summary_actions.json"]["schema_version"] == payload["review_summary_actions"]["schema_version"]
    assert manifest_artifacts["review_summary_pr_comment.json"]["schema_version"] == payload["review_summary_pr_comment"]["schema_version"]
    assert manifest_artifacts["review_summary_pr_comment.json"]["kind"] == "bot_pr_comment_payload"
    assert manifest_artifacts["review_summary_trace.json"]["schema_version"] == payload["review_summary_trace"]["schema_version"]
    assert manifest_artifacts["review_summary_trace.json"]["kind"] == "bot_traceability_metadata"
    assert manifest_artifacts["review_summary_bot_bundle.json"]["schema_version"] == payload["review_summary_bot_bundle"]["schema_version"]
    assert manifest_artifacts["review_summary_bot_bundle.json"]["kind"] == "bot_bundle"
    assert "without parsing markdown" in manifest_artifacts["review_summary_quality.json"]["safe_usage"]
    assert "without parsing markdown" in manifest_artifacts["review_summary_actions.json"]["safe_usage"]
    assert "correctness_proof" in manifest["claims_avoided"]


def test_patch_review_machine_readable_artifact_contracts(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/presentation/menu_view.dart", "void buildMenu() {\n  menuNotifier.closeMenu();\n}\n")
    out = tmp_path / "review-contracts"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review menu navigation",
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
    quality = payload["review_summary_quality"]
    actions = payload["review_summary_actions"]
    pr_comment = payload["review_summary_pr_comment"]
    trace = payload["review_summary_trace"]
    bot_bundle = payload["review_summary_bot_bundle"]
    manifest = payload["review_summary_manifest"]
    manifest_artifacts = {item["filename"]: item for item in manifest["artifacts"]}

    assert {
        "schema_version",
        "attachable",
        "summary_mode",
        "actionable_items_limit",
        "actionable_items_count",
        "actionable_items_total_count",
        "low_value_top_items_count",
        "unknown_bucket_count",
        "residual_memo_source_count",
        "satisfied_count",
        "violated_count",
        "unknown_count",
        "reasons",
        "signals",
        "unknown_triage",
        "unknown_buckets",
        "claims_avoided",
    } <= set(quality)
    assert quality["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_quality.json"]
    assert quality["schema_version"] == 2
    assert quality["attachable"] in {"yes", "maybe", "no"}
    for signal in quality["signals"]:
        assert {"code", "severity", "count", "message"} <= set(signal)
        assert signal["severity"] in {"info", "warning", "error"}
    for unknown_triage in quality["unknown_triage"]:
        assert {"code", "count", "requires_manual_review", "message", "examples"} <= set(unknown_triage)
        assert unknown_triage["code"] in {
            "missing_diff_evidence",
            "missing_test_evidence",
            "manual_review_required",
            "low_risk_unknown",
        }
        assert unknown_triage["requires_manual_review"] is True

    assert {
        "schema_version",
        "summary_mode",
        "actionable_items_limit",
        "actionable_items",
        "violations",
        "claims_avoided",
    } <= set(actions)
    assert actions["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_actions.json"]
    for item in actions["actionable_items"]:
        assert {
            "rank",
            "constraint_id",
            "instruction",
            "source",
            "type",
            "confidence",
            "evidence",
            "source_files",
            "symbols",
            "markdown",
            "evidence_markdown",
        } <= set(item)

    assert {"schema_version", "summary_mode", "product_role", "claims_avoided", "artifacts"} <= set(manifest)
    assert manifest["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"]
    for item in manifest["artifacts"]:
        assert {"filename", "kind", "schema_version", "intended_consumers", "safe_usage"} <= set(item)
    assert [item["filename"] for item in manifest["artifacts"]] == payload["artifacts"]
    assert PATCH_REVIEW_SCHEMA_VERSIONS == {
        "review_summary_manifest.json": manifest["schema_version"],
        "review_summary_quality.json": quality["schema_version"],
        "review_summary_actions.json": actions["schema_version"],
        "review_summary_pr_comment.json": pr_comment["schema_version"],
        "review_summary_trace.json": trace["schema_version"],
        "review_summary_bot_bundle.json": bot_bundle["schema_version"],
    }
    assert {
        "schema_version",
        "summary_mode",
        "title",
        "attachable",
        "body_markdown",
        "source_artifacts",
        "signals",
        "actionable_items",
        "violations",
        "claims_avoided",
    } <= set(pr_comment)
    assert pr_comment["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_pr_comment.json"]
    assert "DocAtlas patch review" in pr_comment["body_markdown"]
    assert "Non-blocking review context only" in pr_comment["body_markdown"]
    assert "review_summary_quality.json" in pr_comment["source_artifacts"]
    assert "review_summary_actions.json" in pr_comment["source_artifacts"]
    assert {
        "schema_version",
        "summary_mode",
        "source_artifacts",
        "counts",
        "action_traces",
        "claims_avoided",
    } <= set(trace)
    assert trace["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_trace.json"]
    assert "constraints.json" in trace["source_artifacts"]
    assert "validation.json" in trace["source_artifacts"]
    assert trace["counts"]["action_traces"] == len(trace["action_traces"])
    for item in trace["action_traces"]:
        assert {
            "rank",
            "constraint_id",
            "source",
            "evidence",
            "validation_status",
            "validation_reason",
            "raw_constraint_artifact",
            "raw_validation_artifact",
        } <= set(item)
    assert {
        "schema_version",
        "summary_mode",
        "source_artifacts",
        "manifest",
        "quality",
        "actions",
        "pr_comment",
        "trace",
        "advisory_decision",
        "claims_avoided",
    } <= set(bot_bundle)
    assert bot_bundle["schema_version"] == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"]
    assert bot_bundle["schema_version"] == 3
    assert manifest_artifacts["review_summary_quality.json"]["schema_version"] == quality["schema_version"]
    assert manifest_artifacts["review_summary_bot_bundle.json"]["schema_version"] == bot_bundle["schema_version"]
    assert bot_bundle["quality"] == quality
    assert bot_bundle["actions"] == actions
    assert bot_bundle["pr_comment"] == pr_comment
    assert bot_bundle["trace"] == trace
    assert {
        "should_attach_comment",
        "show_warning_badge",
        "highlight_violations",
        "requires_manual_review",
        "reason_codes",
        "unknown_triage_codes",
        "unknown_triage_counts",
        "semantics",
        "claims_avoided",
    } <= set(bot_bundle["advisory_decision"])
    assert bot_bundle["advisory_decision"]["semantics"] == "advisory_non_blocking_only"
    assert "safe_to_merge" not in bot_bundle["advisory_decision"]


def test_patch_review_advisory_decision_is_non_blocking_and_escalates_violations_and_unknowns():
    base_quality = {
        "signals": [],
        "violated_count": 0,
        "unknown_count": 0,
        "actionable_items_total_count": 1,
    }
    base_actions = {"actionable_items": [{"constraint_id": "action"}], "violations": []}

    clean_action = PatchReviewService._review_summary_advisory_decision_payload(base_quality, base_actions)
    assert clean_action["should_attach_comment"] is True
    assert clean_action["show_warning_badge"] is False
    assert clean_action["highlight_violations"] is False
    assert clean_action["requires_manual_review"] is False
    assert clean_action["reason_codes"] == ["actionable_items_present"]
    assert clean_action["unknown_triage_codes"] == []
    assert clean_action["unknown_triage_counts"] == {}

    violation = PatchReviewService._review_summary_advisory_decision_payload(
        {**base_quality, "violated_count": 1, "actionable_items_total_count": 0},
        {"actionable_items": [], "violations": [{"constraint_id": "policy"}]},
    )
    assert violation["should_attach_comment"] is True
    assert violation["show_warning_badge"] is True
    assert violation["highlight_violations"] is True
    assert violation["requires_manual_review"] is True
    assert violation["reason_codes"] == ["violations_present"]

    unknown = PatchReviewService._review_summary_advisory_decision_payload(
        {
            **base_quality,
            "unknown_count": 2,
            "actionable_items_total_count": 0,
            "unknown_triage": [
                {"code": "missing_test_evidence", "count": 1, "requires_manual_review": True},
                {"code": "low_risk_unknown", "count": 1, "requires_manual_review": True},
            ],
        },
        {"actionable_items": [], "violations": []},
    )
    assert unknown["should_attach_comment"] is True
    assert unknown["show_warning_badge"] is True
    assert unknown["highlight_violations"] is False
    assert unknown["requires_manual_review"] is True
    assert unknown["reason_codes"] == ["manual_review_required"]
    assert unknown["unknown_triage_codes"] == ["missing_test_evidence", "low_risk_unknown"]
    assert unknown["unknown_triage_counts"] == {"missing_test_evidence": 1, "low_risk_unknown": 1}

    violation_and_unknown = PatchReviewService._review_summary_advisory_decision_payload(
        {**base_quality, "violated_count": 1, "unknown_count": 1, "actionable_items_total_count": 0},
        {"actionable_items": [], "violations": [{"constraint_id": "policy"}]},
    )
    assert violation_and_unknown["highlight_violations"] is True
    assert violation_and_unknown["requires_manual_review"] is True
    assert violation_and_unknown["reason_codes"] == ["violations_present", "manual_review_required"]
    assert violation_and_unknown["unknown_triage_codes"] == []
    assert violation_and_unknown["unknown_triage_counts"] == {}
    assert violation_and_unknown["semantics"] == "advisory_non_blocking_only"
    assert violation_and_unknown["claims_avoided"] == [
        "safe_to_merge",
        "correctness_proof",
        "test_or_human_review_replacement",
    ]
    assert "safe_to_merge" not in violation_and_unknown


def test_patch_review_advisory_decision_exposes_unknown_triage_counts_for_bot_badges():
    decision = PatchReviewService._review_summary_advisory_decision_payload(
        {
            "signals": [],
            "violated_count": 0,
            "unknown_count": 3,
            "actionable_items_total_count": 0,
            "unknown_triage": [
                {"code": "manual_review_required", "count": 2, "requires_manual_review": True},
                {"code": "missing_test_evidence", "count": 1, "requires_manual_review": True},
            ],
        },
        {"actionable_items": [], "violations": []},
    )

    assert decision["should_attach_comment"] is True
    assert decision["show_warning_badge"] is True
    assert decision["requires_manual_review"] is True
    assert decision["reason_codes"] == ["manual_review_required"]
    assert decision["unknown_triage_codes"] == ["manual_review_required", "missing_test_evidence"]
    assert decision["unknown_triage_counts"] == {
        "manual_review_required": 2,
        "missing_test_evidence": 1,
    }
    assert decision["semantics"] == "advisory_non_blocking_only"
    assert "safe_to_merge" not in decision


def test_fake_pr_bot_consumer_reconstructs_missing_triage_counts_for_v3_bundle(tmp_path: Path):
    out = tmp_path / "review-v3-additive-field-fallback"
    out.mkdir()
    manifest = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
        "summary_mode": "standard",
        "product_role": "non_blocking_pr_review_assistant",
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
        "artifacts": [
            {
                "filename": "review_summary_bot_bundle.json",
                "kind": "bot_bundle",
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "Use as a single-file bot integration entrypoint with advisory non-blocking decisions.",
            }
        ],
    }
    bundle = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        "summary_mode": "standard",
        "manifest": manifest,
        "quality": {
            "unknown_count": 2,
            "unknown_triage": [
                {"code": "missing_diff_evidence", "count": 1, "requires_manual_review": True, "examples": []},
                {"code": "missing_test_evidence", "count": 1, "requires_manual_review": True, "examples": []},
            ],
        },
        "actions": {"violations": []},
        "advisory_decision": {
            "should_attach_comment": True,
            "show_warning_badge": True,
            "highlight_violations": False,
            "requires_manual_review": True,
            "reason_codes": ["manual_review_required"],
            "unknown_triage_codes": ["missing_diff_evidence", "missing_test_evidence"],
            "semantics": "advisory_non_blocking_only",
            "claims_avoided": [
                "safe_to_merge",
                "correctness_proof",
                "test_or_human_review_replacement",
            ],
        },
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
    }
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps(bundle))

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    assert consumer_decision["status"] == "completed_patch_review_run"
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["manual_review_required"]
    assert consumer_decision["unknown_triage_codes"] == ["missing_diff_evidence", "missing_test_evidence"]
    assert consumer_decision["unknown_triage_counts"] == {
        "missing_diff_evidence": 1,
        "missing_test_evidence": 1,
    }
    assert "safe_to_merge" not in consumer_decision


def test_fake_pr_bot_consumer_requires_manual_review_when_triage_counts_unavailable(tmp_path: Path):
    out = tmp_path / "review-v3-missing-triage-details"
    out.mkdir()
    manifest = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
        "summary_mode": "standard",
        "product_role": "non_blocking_pr_review_assistant",
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
        "artifacts": [
            {
                "filename": "review_summary_bot_bundle.json",
                "kind": "bot_bundle",
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "Use as a single-file bot integration entrypoint with advisory non-blocking decisions.",
            }
        ],
    }
    bundle = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        "summary_mode": "standard",
        "manifest": manifest,
        "quality": {
            "unknown_count": 1,
            "unknown_triage": [],
        },
        "actions": {"violations": []},
        "advisory_decision": {
            "should_attach_comment": False,
            "show_warning_badge": False,
            "highlight_violations": False,
            "requires_manual_review": False,
            "reason_codes": [],
            "unknown_triage_codes": [],
            "semantics": "advisory_non_blocking_only",
            "claims_avoided": [
                "safe_to_merge",
                "correctness_proof",
                "test_or_human_review_replacement",
            ],
        },
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
    }
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps(bundle))

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    assert consumer_decision["status"] == "completed_patch_review_run"
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["manual_review_required"]
    assert consumer_decision["unknown_triage_codes"] == []
    assert consumer_decision["unknown_triage_counts"] == {}
    assert consumer_decision["unknown_count"] == 1
    assert consumer_decision["violation_count"] == 0
    assert "safe_to_merge" not in consumer_decision


def test_fake_pr_bot_consumer_discovers_bundle_via_manifest_without_markdown_parsing(tmp_path: Path):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/menu_state.g.dart", "// manual generated edit\n")
    out = tmp_path / "review-fake-consumer"

    result = CliRunner().invoke(
        cli,
        [
            "patch-review",
            "--project-path",
            str(repo),
            "--task",
            "Review generated artifact edit",
            "--output-dir",
            str(out),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    consumer_decision = _fake_pr_bot_consume_manifest(out / "review_summary_manifest.json")
    assert consumer_decision["attach_comment"] is True
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is True
    assert consumer_decision["requires_manual_review"] is True
    assert "violations_present" in consumer_decision["reason_codes"]
    assert consumer_decision["violation_count"] > 0
    assert consumer_decision["violation_count"] + consumer_decision["unknown_count"] > 0


def test_patch_review_manifest_is_final_discovery_marker_when_bot_bundle_write_fails(tmp_path: Path, monkeypatch):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/menu_state.g.dart", "// manual generated edit\n")
    out = tmp_path / "review-partial-write"
    original_write_json = PatchReviewService._write_json

    def fail_on_bot_bundle(path: Path, payload: Any) -> None:
        if path.name == "review_summary_bot_bundle.json":
            raise RuntimeError("simulated bot bundle write failure")
        original_write_json(path, payload)

    monkeypatch.setattr(PatchReviewService, "_write_json", staticmethod(fail_on_bot_bundle))

    with pytest.raises(RuntimeError, match="simulated bot bundle write failure"):
        PatchReviewService().run(
            project_path=str(repo),
            task="Review generated artifact edit",
            output_dir=str(out),
        )

    assert not (out / "review_summary_manifest.json").exists()
    assert not (out / "review_summary_bot_bundle.json").exists()
    assert (out / "review_summary_quality.json").exists()
    assert (out / "review_summary_actions.json").exists()


def test_patch_review_reused_output_dir_clears_stale_manifest_before_failed_run(tmp_path: Path, monkeypatch):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/menu_state.g.dart", "// manual generated edit\n")
    out = tmp_path / "review-reused-output-dir"

    PatchReviewService().run(
        project_path=str(repo),
        task="Review generated artifact edit",
        output_dir=str(out),
    )
    manifest_path = out / "review_summary_manifest.json"
    assert manifest_path.exists()
    assert _fake_pr_bot_consume_manifest(manifest_path)["show_warning_badge"] is True
    original_write_json = PatchReviewService._write_json

    def fail_on_bot_bundle(path: Path, payload: Any) -> None:
        if path.name == "review_summary_bot_bundle.json":
            raise RuntimeError("simulated bot bundle write failure")
        original_write_json(path, payload)

    monkeypatch.setattr(PatchReviewService, "_write_json", staticmethod(fail_on_bot_bundle))

    with pytest.raises(RuntimeError, match="simulated bot bundle write failure"):
        PatchReviewService().run(
            project_path=str(repo),
            task="Review generated artifact edit",
            output_dir=str(out),
        )

    assert not manifest_path.exists()
    assert not list(out.glob(".review_summary_manifest.json.*.tmp"))
    assert (out / "review_summary_quality.json").exists()


def test_fake_pr_bot_consumer_treats_missing_manifest_as_no_completed_run(tmp_path: Path, monkeypatch):
    repo = _repo(tmp_path)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _write(repo / "lib/generated/menu_state.g.dart", "// manual generated edit\n")
    out = tmp_path / "review-missing-manifest-fallback"

    PatchReviewService().run(
        project_path=str(repo),
        task="Review generated artifact edit",
        output_dir=str(out),
    )
    completed_decision = _fake_pr_bot_discover_output_dir(out)
    assert completed_decision["status"] == "completed_patch_review_run"
    assert completed_decision["highlight_violations"] is True
    original_write_json = PatchReviewService._write_json

    def fail_on_bot_bundle(path: Path, payload: Any) -> None:
        if path.name == "review_summary_bot_bundle.json":
            raise RuntimeError("simulated bot bundle write failure")
        original_write_json(path, payload)

    monkeypatch.setattr(PatchReviewService, "_write_json", staticmethod(fail_on_bot_bundle))

    with pytest.raises(RuntimeError, match="simulated bot bundle write failure"):
        PatchReviewService().run(
            project_path=str(repo),
            task="Review generated artifact edit",
            output_dir=str(out),
        )

    assert not (out / "review_summary_manifest.json").exists()
    assert (out / "review_summary_bot_bundle.json").exists()
    assert (out / "review_summary.md").exists()
    original_read_text = Path.read_text

    def fail_if_direct_artifact_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"review_summary_bot_bundle.json", "review_summary.md"}:
            raise AssertionError(f"fake PR bot must ignore sibling artifact without manifest: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_direct_artifact_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)
    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["missing_manifest_completed_run_marker"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_treats_invalid_manifest_as_no_completed_run(tmp_path: Path, monkeypatch):
    out = tmp_path / "review-invalid-manifest-fallback"
    out.mkdir()
    _write(out / "review_summary_manifest.json", "{not valid json")
    _write(out / "review_summary_bot_bundle.json", json.dumps({"safe_to_merge": True}))
    _write(out / "review_summary.md", "stale human summary")
    original_read_text = Path.read_text

    def fail_if_sibling_artifact_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"review_summary_bot_bundle.json", "review_summary.md"}:
            raise AssertionError(f"fake PR bot must ignore sibling artifact with invalid manifest: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_sibling_artifact_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)
    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["invalid_manifest_completed_run_marker"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_treats_unsupported_manifest_schema_as_no_completed_run(tmp_path: Path, monkeypatch):
    out = tmp_path / "review-unsupported-manifest-fallback"
    out.mkdir()
    _write(
        out / "review_summary_manifest.json",
        json.dumps(
            {
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"] + 1,
                "product_role": "non_blocking_pr_review_assistant",
                "claims_avoided": ["safe_to_merge"],
                "artifacts": [
                    {
                        "filename": "review_summary_bot_bundle.json",
                        "kind": "bot_bundle",
                        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                        "intended_consumers": ["pr_bot", "automation"],
                        "safe_usage": "single-file bot integration entrypoint; advisory non-blocking only",
                    }
                ],
            }
        ),
    )
    _write(out / "review_summary_bot_bundle.json", json.dumps({"safe_to_merge": True}))
    _write(out / "review_summary.md", "stale human summary")
    original_read_text = Path.read_text

    def fail_if_sibling_artifact_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"review_summary_bot_bundle.json", "review_summary.md"}:
            raise AssertionError(f"fake PR bot must ignore sibling artifact with unsupported manifest: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_sibling_artifact_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)
    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["unsupported_manifest_schema_version"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_treats_missing_manifest_referenced_bundle_as_manual_review(tmp_path: Path, monkeypatch):
    out = tmp_path / "review-missing-bundle-fallback"
    out.mkdir()
    _write(
        out / "review_summary_manifest.json",
        json.dumps(
            {
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
                "summary_mode": "standard",
                "product_role": "non_blocking_pr_review_assistant",
                "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
                "artifacts": [
                    {
                        "filename": "review_summary_bot_bundle.json",
                        "kind": "bot_bundle",
                        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                        "intended_consumers": ["pr_bot", "automation"],
                        "safe_usage": "single-file bot integration entrypoint; advisory non-blocking only",
                    }
                ],
            }
        ),
    )
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_markdown_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review_summary.md":
            raise AssertionError("fake PR bot must not parse markdown when manifest-referenced bundle is missing")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_markdown_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["missing_bot_bundle_artifact"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_fake_pr_bot_consumer_treats_invalid_manifest_referenced_bundle_as_manual_review(tmp_path: Path, monkeypatch):
    out = tmp_path / "review-invalid-bundle-fallback"
    out.mkdir()
    _write(
        out / "review_summary_manifest.json",
        json.dumps(
            {
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
                "summary_mode": "standard",
                "product_role": "non_blocking_pr_review_assistant",
                "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
                "artifacts": [
                    {
                        "filename": "review_summary_bot_bundle.json",
                        "kind": "bot_bundle",
                        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                        "intended_consumers": ["pr_bot", "automation"],
                        "safe_usage": "single-file bot integration entrypoint; advisory non-blocking only",
                    }
                ],
            }
        ),
    )
    _write(out / "review_summary_bot_bundle.json", "{not valid json")
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_markdown_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review_summary.md":
            raise AssertionError("fake PR bot must not parse markdown when manifest-referenced bundle is invalid")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_markdown_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    assert consumer_decision["status"] == "no_completed_patch_review_run"
    assert consumer_decision["attach_comment"] is False
    assert consumer_decision["show_warning_badge"] is True
    assert consumer_decision["highlight_violations"] is False
    assert consumer_decision["requires_manual_review"] is True
    assert consumer_decision["reason_codes"] == ["invalid_bot_bundle_artifact"]
    assert consumer_decision["semantics"] == "manual_fallback_not_pass"
    assert "safe_to_merge" not in consumer_decision
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


@pytest.mark.parametrize(
    "manifest",
    [
        {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
            "summary_mode": "standard",
            "product_role": "non_blocking_pr_review_assistant",
            "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
        },
        {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
            "summary_mode": "standard",
            "product_role": "non_blocking_pr_review_assistant",
            "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
            "artifacts": {"filename": "review_summary_bot_bundle.json"},
        },
        {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
            "summary_mode": "standard",
            "product_role": "non_blocking_pr_review_assistant",
            "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
            "artifacts": [{"kind": "bot_bundle"}],
        },
    ],
)
def test_fake_pr_bot_consumer_treats_malformed_supported_manifest_contract_as_manual_review(
    tmp_path: Path,
    monkeypatch,
    manifest: dict[str, Any],
):
    out = tmp_path / "review-malformed-supported-manifest-fallback"
    out.mkdir()
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps({"safe_to_merge": True}))
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_sibling_artifact_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in {"review_summary_bot_bundle.json", "review_summary.md"}:
            raise AssertionError(f"fake PR bot must ignore sibling artifact with malformed manifest contract: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_sibling_artifact_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    _assert_fake_pr_bot_manual_fallback(consumer_decision, "invalid_manifest_completed_run_marker")
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


@pytest.mark.parametrize(
    "bundle_override",
    [
        {"quality": None},
        {"advisory_decision": None},
        {"advisory_decision": {"semantics": "advisory_non_blocking_only"}},
    ],
)
def test_fake_pr_bot_consumer_treats_malformed_referenced_bundle_contract_as_manual_review(
    tmp_path: Path,
    monkeypatch,
    bundle_override: dict[str, Any],
):
    out = tmp_path / "review-malformed-bundle-contract-fallback"
    out.mkdir()
    manifest = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
        "summary_mode": "standard",
        "product_role": "non_blocking_pr_review_assistant",
        "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
        "artifacts": [
            {
                "filename": "review_summary_bot_bundle.json",
                "kind": "bot_bundle",
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "single-file bot integration entrypoint; advisory non-blocking only",
            }
        ],
    }
    bundle = {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        "summary_mode": "standard",
        "manifest": manifest,
        "quality": {"unknown_count": 0, "unknown_triage": []},
        "actions": {"violations": []},
        "advisory_decision": {
            "should_attach_comment": False,
            "show_warning_badge": False,
            "highlight_violations": False,
            "requires_manual_review": False,
            "reason_codes": ["no_attachable_review_signal"],
            "unknown_triage_codes": [],
            "unknown_triage_counts": {},
            "semantics": "advisory_non_blocking_only",
            "claims_avoided": [
                "safe_to_merge",
                "correctness_proof",
                "test_or_human_review_replacement",
            ],
        },
        "claims_avoided": [
            "correctness_proof",
            "test_or_human_review_replacement",
            "broad_docatlas_superiority",
        ],
    }
    for key, value in bundle_override.items():
        if value is None:
            bundle.pop(key)
        else:
            bundle[key] = value
    _write(out / "review_summary_manifest.json", json.dumps(manifest))
    _write(out / "review_summary_bot_bundle.json", json.dumps(bundle))
    _write(out / "review_summary.md", "stale human summary that must not be parsed for automation")
    original_read_text = Path.read_text

    def fail_if_markdown_is_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "review_summary.md":
            raise AssertionError("fake PR bot must not parse markdown when manifest-referenced bundle contract is malformed")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_markdown_is_read)

    consumer_decision = _fake_pr_bot_discover_output_dir(out)

    _assert_fake_pr_bot_manual_fallback(consumer_decision, "invalid_bot_bundle_contract")
    assert "review_summary_bot_bundle.json" in consumer_decision["ignored_sibling_artifacts"]
    assert "review_summary.md" in consumer_decision["ignored_sibling_artifacts"]


def test_patch_review_summary_uses_generic_task_terms_without_project_hardcoding():
    summary = PatchReviewService._review_summary(
        "Review checkout launch action",
        ["lib/payments/checkout_button.dart"],
        {
            "constraints": [
                {
                    "id": "generic-task-local",
                    "type": "source_of_truth",
                    "instruction": "Use launchCheckoutFlow for the changed payment button action.",
                    "source": "docs/payments.md",
                    "confidence": "medium",
                    "evidence": "Checkout buttons call launchCheckoutFlow before navigation.",
                    "symbols": ["launchCheckoutFlow"],
                    "files": [],
                },
                {
                    "id": "broad-architecture",
                    "type": "architecture",
                    "instruction": "Rules that must not be violated live in broad architecture docs.",
                    "source": "docs/architecture.md",
                    "confidence": "high",
                    "evidence": "Rules that must not be violated.",
                    "symbols": [],
                    "files": [],
                },
            ],
            "symbol_candidates": [],
            "excluded_source_reasons": [],
        },
        {"satisfied": 0, "violated": 0, "unknown": 0, "results": [], "warnings": []},
    )

    actionable = _section(summary, "Actionable PR checklist")
    manual = _section(summary, "Manual review context")
    assert "launchCheckoutFlow" in actionable
    assert "broad architecture" not in actionable.lower()
    assert "broad architecture" in manual.lower()



def test_patch_review_summary_puts_violations_first_even_when_broad_context():
    summary = PatchReviewService._review_summary(
        "Review current patch",
        ["lib/widget.dart"],
        {
            "constraints": [
                {
                    "id": "broad-violated",
                    "type": "architecture",
                    "instruction": "Broad architecture rule was violated and needs reviewer action.",
                    "source": "docs/architecture.md",
                    "confidence": "medium",
                    "evidence": "Rules that must not be violated.",
                    "symbols": [],
                    "files": [],
                },
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
            ],
            "symbol_candidates": [],
            "excluded_source_reasons": [],
        },
        {
            "satisfied": 0,
            "violated": 1,
            "unknown": 0,
            "results": [
                {"constraint_id": "broad-violated", "status": "violated", "reason": "policy code changed in UI", "files": ["lib/widget.dart"]}
            ],
            "warnings": [],
        },
        summary_max_items=2,
    )

    actionable_items = [line for line in _section(summary, "Actionable PR checklist").splitlines() if line.startswith("- ")]
    assert actionable_items[0].startswith("- Broad architecture rule was violated")
    assert "Generated files must not be edited" in actionable_items[1]
    assert "broad-violated: policy code changed in UI" in _section(summary, "Violations")


def test_patch_review_quality_attachable_uses_total_actionable_not_display_cap():
    constraints = {
        "constraints": [
            {
                "id": f"actionable-{index}",
                "type": "source_of_truth",
                "instruction": f"Apply checkout rule {index}.",
                "source": "docs/checkout.md",
                "confidence": "high",
                "evidence": f"checkout rule {index}",
                "symbols": [f"checkoutRule{index}"],
                "files": [],
            }
            for index in range(3)
        ],
        "symbol_candidates": [],
        "excluded_source_reasons": [],
    }
    validation = {"satisfied": 0, "violated": 0, "unknown": 0, "results": [], "warnings": []}

    quality = PatchReviewService._review_summary_quality_payload(
        "Review checkout rules",
        ["docs/checkout.md"],
        constraints,
        validation,
        summary_max_items=1,
    )

    assert quality["actionable_items_count"] == 1
    assert quality["actionable_items_total_count"] == 3
    assert quality["attachable"] == "yes"


def test_patch_review_pr_comment_lists_violations_separately_from_capped_actions():
    actions = {
        "actionable_items": [],
        "violations": [
            {"constraint_id": "policy-violation", "reason": "Provider policy moved into UI", "files": ["lib/widget.dart"]}
        ],
    }
    quality = {
        "attachable": "maybe",
        "signals": [{"code": "violations_present", "severity": "error", "count": 1}],
        "claims_avoided": ["correctness_proof"],
    }

    comment = PatchReviewService._review_summary_pr_comment_payload(actions, quality, summary_mode="compact")

    assert comment["violations"] == actions["violations"]
    assert "Violations:" in comment["body_markdown"]
    assert "policy-violation" in comment["body_markdown"]
    assert "Provider policy moved into UI" in comment["body_markdown"]


def test_patch_review_render_ready_markdown_escapes_mentions_backticks_and_truncates():
    item = PatchReviewService._actionable_item_payload(
        {
            "id": "unsafe-markdown",
            "instruction": "Ping @team and use `danger`" + "x" * 2500,
            "source": "docs/`unsafe`.md",
            "type": "source_of_truth",
            "confidence": "high",
            "evidence": "Evidence mentions @team and `danger`",
            "symbols": [],
            "files": [],
        },
        None,
        rank=1,
    )

    assert "@team" not in item["markdown"]
    assert "@\u200bteam" in item["markdown"]
    assert "\\`danger\\`" in item["markdown"]
    assert "[truncated]" in item["markdown"]
    assert "@team" not in item["evidence_markdown"]
    assert "\\`danger\\`" in item["evidence_markdown"]

    long_body = PatchReviewService._truncate_pr_comment("x" * 70_000)
    assert len(long_body) <= 60_000
    assert "Comment truncated for provider limits" in long_body
