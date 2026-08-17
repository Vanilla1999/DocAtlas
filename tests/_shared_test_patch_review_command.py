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


def _fake_pr_bot_contract_non_negative_int(value: Any, error: type[Exception], field: str) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise error(f"{field} must be a non-negative integer")
    return value


def _fake_pr_bot_pr_comment_payload() -> dict[str, Any]:
    return {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_pr_comment.json"],
        "body": "DocAtlas patch review\n",
        "body_markdown": "DocAtlas patch review\n",
        "source_artifacts": ["review_summary_quality.json", "review_summary_actions.json"],
        "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
    }


def _fake_pr_bot_trace_payload() -> dict[str, Any]:
    return {
        "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_trace.json"],
        "source_artifacts": [
            "constraints.json",
            "validation.json",
            "review_summary_quality.json",
            "review_summary_actions.json",
        ],
        "claims_avoided": ["correctness_proof", "test_or_human_review_replacement"],
    }


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
    coverage = bundle.get("coverage")
    if coverage is not None:
        coverage = _fake_pr_bot_contract_mapping(coverage, _FakePrBotInvalidBotBundleContract, "bundle.coverage")
    pr_comment = _fake_pr_bot_contract_mapping(
        bundle.get("pr_comment"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.pr_comment",
    )
    trace = _fake_pr_bot_contract_mapping(bundle.get("trace"), _FakePrBotInvalidBotBundleContract, "bundle.trace")
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
    pr_comment_claims = _fake_pr_bot_contract_list(
        pr_comment.get("claims_avoided"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.pr_comment.claims_avoided",
    )
    trace_claims = _fake_pr_bot_contract_list(
        trace.get("claims_avoided"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.trace.claims_avoided",
    )
    _fake_pr_bot_contract_require(
        bundle.get("schema_version") == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        _FakePrBotInvalidBotBundleContract,
        "bundle.schema_version",
    )
    _fake_pr_bot_contract_require(bundle.get("manifest") == manifest, _FakePrBotInvalidBotBundleContract, "bundle.manifest")
    _fake_pr_bot_contract_require(
        pr_comment.get("schema_version") == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_pr_comment.json"],
        _FakePrBotInvalidBotBundleContract,
        "bundle.pr_comment.schema_version",
    )
    pr_comment_sources = _fake_pr_bot_contract_list(
        pr_comment.get("source_artifacts"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.pr_comment.source_artifacts",
    )
    _fake_pr_bot_contract_require(
        {"review_summary_quality.json", "review_summary_actions.json"} <= set(pr_comment_sources),
        _FakePrBotInvalidBotBundleContract,
        "bundle.pr_comment.source_artifacts",
    )
    if coverage is not None:
        _fake_pr_bot_contract_require(
            "constraint_coverage.json" in pr_comment_sources,
            _FakePrBotInvalidBotBundleContract,
            "bundle.pr_comment.source_artifacts.constraint_coverage",
        )
        _fake_pr_bot_contract_require(
            coverage.get("validation_status_counts") == trace.get("coverage_status_counts"),
            _FakePrBotInvalidBotBundleContract,
            "bundle.coverage.trace_status_counts",
        )
    body = pr_comment.get("body")
    body_markdown = pr_comment.get("body_markdown")
    _fake_pr_bot_contract_require(isinstance(body, str), _FakePrBotInvalidBotBundleContract, "bundle.pr_comment.body")
    body_text = cast(str, body)
    _fake_pr_bot_contract_require(
        body_text == body_markdown,
        _FakePrBotInvalidBotBundleContract,
        "bundle.pr_comment.body_markdown_alias",
    )
    _fake_pr_bot_contract_require(
        "correctness_proof" in pr_comment_claims,
        _FakePrBotInvalidBotBundleContract,
        "bundle.pr_comment.claims_avoided.correctness_proof",
    )
    _fake_pr_bot_contract_require(
        "test_or_human_review_replacement" in pr_comment_claims,
        _FakePrBotInvalidBotBundleContract,
        "bundle.pr_comment.claims_avoided.test_or_human_review_replacement",
    )
    _fake_pr_bot_contract_require(
        trace.get("schema_version") == PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_trace.json"],
        _FakePrBotInvalidBotBundleContract,
        "bundle.trace.schema_version",
    )
    trace_sources = _fake_pr_bot_contract_list(
        trace.get("source_artifacts"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.trace.source_artifacts",
    )
    _fake_pr_bot_contract_require(
        {"constraints.json", "validation.json", "review_summary_quality.json", "review_summary_actions.json"}
        <= set(trace_sources),
        _FakePrBotInvalidBotBundleContract,
        "bundle.trace.source_artifacts",
    )
    _fake_pr_bot_contract_require(
        "correctness_proof" in trace_claims,
        _FakePrBotInvalidBotBundleContract,
        "bundle.trace.claims_avoided.correctness_proof",
    )
    _fake_pr_bot_contract_require(
        "test_or_human_review_replacement" in trace_claims,
        _FakePrBotInvalidBotBundleContract,
        "bundle.trace.claims_avoided.test_or_human_review_replacement",
    )
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
    unknown_triage_counts: dict[str, int] = {}
    for index, item in enumerate(unknown_triage):
        if not isinstance(item, dict):
            continue
        count = _fake_pr_bot_contract_non_negative_int(
            item.get("count"),
            _FakePrBotInvalidBotBundleContract,
            f"bundle.quality.unknown_triage[{index}].count",
        )
        if item.get("code") and count > 0:
            unknown_triage_counts[str(item["code"])] = count
    decision_unknown_triage_counts = decision.get("unknown_triage_counts")
    if decision_unknown_triage_counts is None:
        decision_unknown_triage_counts = unknown_triage_counts
    else:
        decision_unknown_triage_counts = _fake_pr_bot_contract_mapping(
            decision_unknown_triage_counts,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.unknown_triage_counts",
        )
        normalized_decision_unknown_triage_counts: dict[str, int] = {}
        for code, count_value in decision_unknown_triage_counts.items():
            _fake_pr_bot_contract_require(
                isinstance(code, str),
                _FakePrBotInvalidBotBundleContract,
                "bundle.advisory_decision.unknown_triage_counts.code",
            )
            normalized_decision_unknown_triage_counts[code] = _fake_pr_bot_contract_non_negative_int(
                count_value,
                _FakePrBotInvalidBotBundleContract,
                f"bundle.advisory_decision.unknown_triage_counts.{code}",
            )
        _fake_pr_bot_contract_require(
            normalized_decision_unknown_triage_counts == unknown_triage_counts,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.unknown_triage_counts",
        )
        decision_unknown_triage_counts = normalized_decision_unknown_triage_counts
    quality_signals = {
        str(item.get("code") or "")
        for item in _fake_pr_bot_contract_list(
            quality.get("signals", []),
            _FakePrBotInvalidBotBundleContract,
            "bundle.quality.signals",
        )
        if isinstance(item, dict)
    }
    violated_count = _fake_pr_bot_contract_non_negative_int(
        quality.get("violated_count"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.quality.violated_count",
    )
    unknown_count = _fake_pr_bot_contract_non_negative_int(
        quality.get("unknown_count"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.quality.unknown_count",
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
    violations = _fake_pr_bot_contract_list(
        actions.get("violations"),
        _FakePrBotInvalidBotBundleContract,
        "bundle.actions.violations",
    )
    has_quality_violation_signal = violated_count > 0 or "violations_present" in quality_signals
    has_violation_payload = bool(violations)
    if has_quality_violation_signal or has_violation_payload:
        _fake_pr_bot_contract_require(
            has_quality_violation_signal and has_violation_payload,
            _FakePrBotInvalidBotBundleContract,
            "bundle.quality.actions.violations_consistency",
        )
        _fake_pr_bot_contract_require(
            decision["show_warning_badge"] is True,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.show_warning_badge.violations",
        )
        _fake_pr_bot_contract_require(
            decision["highlight_violations"] is True,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.highlight_violations.violations",
        )
        _fake_pr_bot_contract_require(
            decision["requires_manual_review"] is True,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.requires_manual_review.violations",
        )
        _fake_pr_bot_contract_require(
            "violations_present" in reason_codes,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.reason_codes.violations_present",
        )
    if unknown_count > 0 or unknown_triage_counts or "manual_review_required" in quality_signals:
        _fake_pr_bot_contract_require(
            decision["show_warning_badge"] is True,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.show_warning_badge.unknowns",
        )
        _fake_pr_bot_contract_require(
            decision["requires_manual_review"] is True,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.requires_manual_review.unknowns",
        )
        _fake_pr_bot_contract_require(
            "manual_review_required" in reason_codes,
            _FakePrBotInvalidBotBundleContract,
            "bundle.advisory_decision.reason_codes.manual_review_required",
        )
    if decision["should_attach_comment"]:
        _fake_pr_bot_contract_require(
            bool(body_text.strip()),
            _FakePrBotInvalidBotBundleContract,
            "bundle.pr_comment.body.non_empty_when_attachable",
        )
    return {
        "attach_comment": decision["should_attach_comment"],
        "show_warning_badge": decision["show_warning_badge"],
        "highlight_violations": decision["highlight_violations"],
        "requires_manual_review": decision["requires_manual_review"],
        "reason_codes": reason_codes,
        "unknown_triage_codes": unknown_triage_codes,
        "unknown_triage_counts": decision_unknown_triage_counts,
        "coverage_counts": decision.get("coverage_counts", {}),
        "unknown_triage_examples_by_code": unknown_triage_examples_by_code,
        "violation_count": len(violations),
        "unknown_count": unknown_count,
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















def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker)
    rest = text[start + len(marker):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]
