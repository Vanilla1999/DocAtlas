from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

LegacyCandidateStatus = Literal["accepted", "rejected_too_easy", "rejected_unfair", "needs_redesign"]
CandidateStatus = Literal[
    "candidate",
    "accepted_differentiating",
    "rejected_too_easy",
    "rejected_too_hard",
    "rejected_invalid",
    "rejected_hidden_only",
    "rejected_insufficient_visible_source",
    "rejected_no_constraint_angle",
    "needs_manual_review",
]
TaskClass = Literal[
    "generated_file_trap",
    "lockfile_dependency_trap",
    "provider_ui_policy_leakage",
    "source_of_truth_ownership",
    "architecture_layer_boundary",
    "verification_required",
    "cross_module_policy",
    "dependency_version_contract",
    "benchmark_accounting",
    "other",
]
KNOWN_TASK_CLASSES: set[str] = {
    "generated_file_trap",
    "lockfile_dependency_trap",
    "provider_ui_policy_leakage",
    "source_of_truth_ownership",
    "architecture_layer_boundary",
    "verification_required",
    "cross_module_policy",
    "dependency_version_contract",
    "benchmark_accounting",
    "other",
}


@dataclass(frozen=True)
class ScreeningResult:
    task_id: str
    status: CandidateStatus
    task_class: str
    reason: str
    visible_source_coverage: bool
    hidden_oracle_only: bool
    fairness_clean: bool
    constraint_angle: str
    repo_only_repeats: int
    repo_only_resolved: int
    repo_only_public_passed: int
    repo_only_hidden_passed: int
    policy_clean: bool
    selected_for_targeted_pilot: bool
    requires_manual_review: bool

    def to_json_dict(self) -> dict[str, object]:
        return asdict(self)


def decide_candidate_status(*, repo_only_repeats: int, repo_only_resolved: int, fairness_clean: bool, hidden_oracle_only: bool) -> LegacyCandidateStatus:
    """Backward-compatible pre-pilot screening rule for legacy manifests."""
    result = decide_screening_result(
        task_id="legacy_candidate",
        repo_only_repeats=repo_only_repeats,
        repo_only_resolved=repo_only_resolved,
        repo_only_public_passed=0,
        repo_only_hidden_passed=0,
        policy_clean=fairness_clean,
        visible_source_coverage=True,
        hidden_oracle_only=hidden_oracle_only,
        fairness_clean=fairness_clean,
        constraint_angle="legacy constraint angle",
        task_class="other",
        stable_public_hidden_separation=True,
        valid_fixture=True,
        allow_partial_as_legacy_accepted=True,
    )
    if result.status == "accepted_differentiating":
        return "accepted"
    if result.status in {"rejected_hidden_only", "rejected_invalid", "rejected_insufficient_visible_source"}:
        return "rejected_unfair"
    if result.status == "rejected_too_easy":
        return "rejected_too_easy"
    return "needs_redesign"


def decide_screening_result(
    *,
    task_id: str,
    repo_only_repeats: int,
    repo_only_resolved: int,
    repo_only_public_passed: int,
    repo_only_hidden_passed: int,
    policy_clean: bool,
    visible_source_coverage: bool,
    hidden_oracle_only: bool,
    fairness_clean: bool,
    constraint_angle: str,
    task_class: str,
    stable_public_hidden_separation: bool,
    valid_fixture: bool,
    smoke_or_prototype: bool = False,
    expected_differentiator_stated: bool = True,
    allow_partial_as_legacy_accepted: bool = False,
) -> ScreeningResult:
    status: CandidateStatus
    reason: str
    requires_manual_review = False
    normalized_angle = constraint_angle.strip()
    normalized_class = task_class if task_class in KNOWN_TASK_CLASSES else "other"

    if not valid_fixture or not fairness_clean or not policy_clean or not stable_public_hidden_separation:
        status = "rejected_invalid"
        reason = "fixture, fairness, policy, or public/hidden separation validation is not clean"
    elif hidden_oracle_only:
        status = "rejected_hidden_only"
        reason = "success depends on hidden/oracle-only information"
    elif not visible_source_coverage:
        status = "rejected_insufficient_visible_source"
        reason = "visible docs/source do not cover the contract needed to solve the task"
    elif not normalized_angle:
        status = "rejected_no_constraint_angle"
        reason = "task has no explicit visible constraint angle"
    elif smoke_or_prototype:
        status = "rejected_too_easy"
        reason = "task is marked smoke/prototype and is not a proof-of-value candidate"
    elif not expected_differentiator_stated:
        status = "needs_manual_review"
        reason = "expected differentiator was not stated before DocAtlas outcome"
        requires_manual_review = True
    elif repo_only_repeats <= 0:
        status = "candidate"
        reason = "candidate has not been screened with repo-only baseline yet"
        requires_manual_review = True
    elif repo_only_resolved >= repo_only_repeats:
        status = "rejected_too_easy"
        reason = "repo_only_strict_offline resolved all screening repeats"
    elif repo_only_resolved == 0:
        status = "accepted_differentiating"
        reason = "repo_only_strict_offline did not resolve any repeats and visible constraint evidence is available"
    elif allow_partial_as_legacy_accepted:
        status = "accepted_differentiating"
        reason = "legacy rule accepts partial repo-only failures for screening compatibility"
    else:
        status = "needs_manual_review"
        reason = "repo_only_strict_offline had mixed results; automatic promotion would be ambiguous"
        requires_manual_review = True

    return ScreeningResult(
        task_id=task_id,
        status=status,
        task_class=normalized_class,
        reason=reason,
        visible_source_coverage=visible_source_coverage,
        hidden_oracle_only=hidden_oracle_only,
        fairness_clean=fairness_clean,
        constraint_angle=normalized_angle,
        repo_only_repeats=repo_only_repeats,
        repo_only_resolved=repo_only_resolved,
        repo_only_public_passed=repo_only_public_passed,
        repo_only_hidden_passed=repo_only_hidden_passed,
        policy_clean=policy_clean,
        selected_for_targeted_pilot=status == "accepted_differentiating",
        requires_manual_review=requires_manual_review,
    )


def write_screening_artifacts(run_dir: Path, results: list[ScreeningResult]) -> dict[str, object]:
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [result.to_json_dict() for result in results]
    accepted = [row for row in rows if row["status"] == "accepted_differentiating"]
    rejected = [row for row in rows if row["status"] != "accepted_differentiating"]
    counts = dict(sorted(Counter(str(row["status"]) for row in rows).items()))
    payload: dict[str, object] = {
        "candidate_count": len(rows),
        "accepted_differentiating_count": len(accepted),
        "rejected_counts": {status: count for status, count in counts.items() if status != "accepted_differentiating"},
        "status_counts": counts,
        "results": rows,
        "discipline": {
            "no_docatlas_outcome_promotion": True,
            "hidden_oracle_only_not_promoted": True,
            "rejected_too_easy_not_promoted": True,
        },
    }
    (run_dir / "screening_results.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "accepted_pool.json").write_text(json.dumps(accepted, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "rejected_pool.json").write_text(json.dumps(rejected, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "screening_report.md").write_text(format_screening_report(payload), encoding="utf-8")
    return payload


def format_screening_report(payload: dict[str, object]) -> str:
    rows = payload.get("results", [])
    assert isinstance(rows, list)
    lines = [
        "# Patch constraints fair screening report",
        "",
        f"Candidate count: {payload['candidate_count']}",
        f"Accepted/differentiating count: {payload['accepted_differentiating_count']}",
        "",
        "Rejected counts by status:",
    ]
    rejected_counts = payload.get("rejected_counts", {})
    if isinstance(rejected_counts, dict) and rejected_counts:
        lines.extend(f"- {status}: {count}" for status, count in rejected_counts.items())
    else:
        lines.append("- none")
    lines.extend([
        "",
        "Notes:",
        "- rejected-too-easy tasks are not promoted.",
        "- hidden/oracle-only tasks are not promoted.",
        "- screening is pre-pilot and must not use DocAtlas outcome to promote tasks.",
        "",
        "| task_id | status | task_class | reason |",
        "| --- | --- | --- | --- |",
    ])
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(f"| {row.get('task_id')} | {row.get('status')} | {row.get('task_class')} | {str(row.get('reason')).replace('|', '/')} |")
    return "\n".join(lines) + "\n"
