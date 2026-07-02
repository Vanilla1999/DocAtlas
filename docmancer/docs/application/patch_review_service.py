from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.artifact_hygiene import apply_patch_hygiene, is_runtime_artifact, parse_status_paths

from docmancer.docs.service import LibraryDocsService

LOW_VALUE_SYMBOLS = {
    "package", "import", "export", "part", "TODO", "FIXME", "tr", "l10n",
    "localization", "onHide", "onShow", "onTap", "onPressed",
    "barrierDismissible", "context", "build", "Widget", "State",
    "StatelessWidget", "StatefulWidget", "Text", "title", "VoidCallback",
    "onRequest",
}
DOGFOOD_MEMO_REASONS = {"dogfood_result_memo", "dogfood_task_artifact"}
MAX_PR_COMMENT_CHARS = 60_000
MAX_PR_COMMENT_FIELD_CHARS = 2_000
PATCH_REVIEW_SCHEMA_VERSIONS = {
    "review_summary_manifest.json": 1,
    "review_summary_quality.json": 2,
    "review_summary_actions.json": 1,
    "review_summary_pr_comment.json": 2,
    "review_summary_trace.json": 1,
    "review_summary_bot_bundle.json": 3,
    "constraint_coverage.json": 1,
}
TASK_TOKEN_STOPWORDS = {
    "add", "and", "before", "change", "check", "current", "diff", "file",
    "for", "from", "into", "keep", "make", "must", "path", "patch", "pr",
    "review", "task", "test", "the", "this", "with", "without",
}

class PatchReviewService:
    """Generate read-only patch review artifacts for a local project."""

    def __init__(self, docs_service: LibraryDocsService | None = None):
        self.docs_service = docs_service or LibraryDocsService()

    def run(
        self,
        *,
        project_path: str,
        task: str,
        base_ref: str = "HEAD",
        output_dir: str | None = None,
        changed_files: list[str] | None = None,
        strict: bool = False,
        max_constraints: int = 12,
        max_tokens: int = 1200,
        summary_max_items: int = 5,
        summary_mode: str = "standard",
    ) -> dict[str, Any]:
        root = Path(project_path).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"project_path does not exist: {root}")
        raw_changed_files = self._git_changed_files(root, base_ref)
        raw_status = self._git_status_porcelain(root)
        raw_patch_diff = self._git_diff(root, base_ref)
        hygiene = apply_patch_hygiene(
            raw_status_lines=raw_status.splitlines(),
            raw_changed_files=raw_changed_files,
            raw_patch_diff=raw_patch_diff,
        )
        changed = changed_files or hygiene.filtered_changed_files
        patch_diff = raw_patch_diff if changed_files else hygiene.filtered_patch_diff
        untracked_files = self._meaningful_untracked_files(raw_status)
        ignored_runtime_artifacts = hygiene.ignored_runtime_artifacts
        warnings: list[str] = []
        if untracked_files and not changed_files:
            warnings.append("untracked files are included in changed_files; patch.diff may not include their content")
        out = Path(output_dir).expanduser() if output_dir else root / ".docatlas" / "patch-review" / self._run_id()
        if not out.is_absolute():
            out = root / out
        out.mkdir(parents=True, exist_ok=True)
        self._clear_stale_manifest_marker(out)

        constraints = self.docs_service.get_patch_constraints(
            task,
            project_path=str(root),
            changed_files=changed,
            max_constraints=max_constraints,
            max_tokens=max_tokens,
            include_sources=True,
        )
        validation = self.docs_service.validate_patch_against_constraints(
            constraints,
            project_path=str(root),
            changed_files=changed,
            patch_diff=patch_diff,
            strict=strict,
        )

        constraints_dict = asdict(constraints)
        validation_dict = asdict(validation)
        quality_payload = self._review_summary_quality_payload(
            task,
            changed,
            constraints_dict,
            validation_dict,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        actions_payload = self._review_summary_actions_payload(
            task,
            changed,
            constraints_dict,
            validation_dict,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        coverage_payload = self._constraint_coverage_payload(constraints_dict, validation_dict)
        artifact_names = [
            "review_summary_manifest.json",
            "review_summary.md",
            "review_summary_quality.json",
            "review_summary_actions.json",
            "review_summary_pr_comment.json",
            "review_summary_trace.json",
            "review_summary_bot_bundle.json",
            "constraint_coverage.json",
            "constraints.json",
            "constraints.md",
            "changed_files.json",
            "untracked_files.json",
            "ignored_runtime_artifacts.json",
            "patch_hygiene.json",
            "patch.diff",
            "validation.json",
        ]
        self._write_json(out / "constraints.json", constraints_dict)
        (out / "constraints.md").write_text(self._constraints_markdown(constraints_dict), encoding="utf-8")
        self._write_json(out / "changed_files.json", changed)
        self._write_json(out / "untracked_files.json", untracked_files)
        self._write_json(out / "ignored_runtime_artifacts.json", ignored_runtime_artifacts)
        self._write_json(out / "patch_hygiene.json", hygiene.to_json_dict())
        (out / "patch.diff").write_text(patch_diff, encoding="utf-8")
        self._write_json(out / "validation.json", validation_dict)
        self._write_json(out / "constraint_coverage.json", coverage_payload)
        self._write_json(out / "review_summary_actions.json", actions_payload)
        self._write_json(out / "review_summary_quality.json", quality_payload)
        pr_comment_payload = self._review_summary_pr_comment_payload(
            actions_payload,
            quality_payload,
            summary_mode=summary_mode,
        )
        trace_payload = self._review_summary_trace_payload(
            constraints_dict,
            validation_dict,
            actions_payload,
            quality_payload,
            coverage_payload,
            summary_mode=summary_mode,
        )
        self._write_json(out / "review_summary_pr_comment.json", pr_comment_payload)
        self._write_json(out / "review_summary_trace.json", trace_payload)
        summary = self._review_summary(
            task,
            changed,
            constraints_dict,
            validation_dict,
            warnings=warnings,
            untracked_files=untracked_files,
            ignored_runtime_artifacts=ignored_runtime_artifacts,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        (out / "review_summary.md").write_text(summary, encoding="utf-8")
        manifest_payload = self._review_summary_manifest_payload(
            artifact_names,
            summary_mode=summary_mode,
            quality_schema_version=quality_payload["schema_version"],
            actions_schema_version=actions_payload["schema_version"],
            pr_comment_schema_version=pr_comment_payload["schema_version"],
            trace_schema_version=trace_payload["schema_version"],
            bot_bundle_schema_version=PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
        )
        bot_bundle_payload = self._review_summary_bot_bundle_payload(
            manifest_payload,
            quality_payload,
            actions_payload,
            pr_comment_payload,
            trace_payload,
            summary_mode=summary_mode,
        )
        self._write_json(out / "review_summary_bot_bundle.json", bot_bundle_payload)
        self._write_json(out / "review_summary_manifest.json", manifest_payload)
        return {
            "output_dir": str(out),
            "changed_files": changed,
            "untracked_files": untracked_files,
            "ignored_runtime_artifacts": ignored_runtime_artifacts,
            "warnings": warnings,
            "summary_max_items": summary_max_items,
            "summary_mode": summary_mode,
            "review_summary_manifest": manifest_payload,
            "review_summary_actions": actions_payload,
            "review_summary_quality": quality_payload,
            "review_summary_pr_comment": pr_comment_payload,
            "review_summary_trace": trace_payload,
            "review_summary_bot_bundle": bot_bundle_payload,
            "constraint_coverage": coverage_payload,
            "constraints": constraints_dict,
            "validation": validation_dict,
            "artifacts": artifact_names,
        }

    @staticmethod
    def _run_id() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _git_changed_files(root: Path, base_ref: str) -> list[str]:
        output = subprocess.check_output(["git", "diff", "--name-only", base_ref, "--"], cwd=root, text=True)
        return [line.strip() for line in output.splitlines() if line.strip()]

    @staticmethod
    def _git_status_porcelain(root: Path) -> str:
        return subprocess.check_output(["git", "status", "--porcelain", "-uall"], cwd=root, text=True)

    @staticmethod
    def _git_diff(root: Path, base_ref: str) -> str:
        return subprocess.check_output(["git", "diff", base_ref, "--"], cwd=root, text=True)

    @staticmethod
    def _meaningful_untracked_files(raw_status: str) -> list[str]:
        return [path for status, path in parse_status_paths(raw_status.splitlines()) if status == "??" and not is_runtime_artifact(path)]

    @staticmethod
    def _clear_stale_manifest_marker(output_dir: Path) -> None:
        (output_dir / "review_summary_manifest.json").unlink(missing_ok=True)
        for temp_manifest in output_dir.glob(".review_summary_manifest.json.*.tmp"):
            temp_manifest.unlink(missing_ok=True)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        tmp_path = Path(tmp)
        try:
            with open(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            tmp_path.replace(path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _review_summary_manifest_payload(
        artifact_names: list[str],
        *,
        summary_mode: str,
        quality_schema_version: int,
        actions_schema_version: int,
        pr_comment_schema_version: int,
        trace_schema_version: int,
        bot_bundle_schema_version: int,
    ) -> dict[str, Any]:
        artifact_contract = {
            "review_summary.md": {
                "kind": "human_review_summary",
                "schema_version": None,
                "intended_consumers": ["human_reviewer"],
                "safe_usage": "Attach to PRs as non-blocking review context; do not treat as correctness proof.",
            },
            "review_summary_quality.json": {
                "kind": "bot_quality_metadata",
                "schema_version": quality_schema_version,
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "Use for attachability and summary-health decisions without parsing markdown; do not gate correctness by this alone.",
            },
            "review_summary_actions.json": {
                "kind": "bot_action_metadata",
                "schema_version": actions_schema_version,
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "Render ranked checklist suggestions without parsing markdown; keep comments non-blocking unless a separate policy says otherwise.",
            },
            "review_summary_pr_comment.json": {
                "kind": "bot_pr_comment_payload",
                "schema_version": pr_comment_schema_version,
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "Render a ready non-blocking PR comment without parsing markdown; do not treat it as a merge gate by itself.",
            },
            "review_summary_trace.json": {
                "kind": "bot_traceability_metadata",
                "schema_version": trace_schema_version,
                "intended_consumers": ["pr_bot", "automation", "debugger"],
                "safe_usage": "Trace rendered recommendations back to raw constraints and validation results; use for audit/debug, not as a correctness proof.",
            },
            "constraint_coverage.json": {
                "kind": "constraint_coverage_metadata",
                "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["constraint_coverage.json"],
                "intended_consumers": ["pr_bot", "automation", "debugger"],
                "safe_usage": "Inspect deterministic coverage versus unknown/manual categories; unknown/manual coverage remains review context, not pass.",
            },
            "review_summary_bot_bundle.json": {
                "kind": "bot_bundle",
                "schema_version": bot_bundle_schema_version,
                "intended_consumers": ["pr_bot", "automation"],
                "safe_usage": "Use as a single-file bot integration entrypoint containing manifest, quality, actions, PR comment, trace metadata, and advisory non-blocking integration decisions.",
            },
            "constraints.json": {
                "kind": "raw_constraints",
                "schema_version": None,
                "intended_consumers": ["debugger", "automation"],
                "safe_usage": "Inspect full extracted constraints and sources; this is raw evidence, not a verdict.",
            },
            "validation.json": {
                "kind": "raw_validation",
                "schema_version": None,
                "intended_consumers": ["debugger", "automation"],
                "safe_usage": "Inspect satisfied, violated, and unknown validation results; unknown means manual review, not pass.",
            },
            "patch.diff": {
                "kind": "raw_patch_diff",
                "schema_version": None,
                "intended_consumers": ["debugger", "automation"],
                "safe_usage": "Use as source patch evidence; may omit untracked file content.",
            },
        }
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_manifest.json"],
            "summary_mode": summary_mode,
            "product_role": "non_blocking_pr_review_assistant",
            "claims_avoided": [
                "correctness_proof",
                "test_or_human_review_replacement",
                "broad_docatlas_superiority",
            ],
            "artifacts": [
                {
                    "filename": name,
                    **artifact_contract.get(
                        name,
                        {
                            "kind": "supporting_artifact",
                            "schema_version": None,
                            "intended_consumers": ["debugger"],
                            "safe_usage": "Use as supporting review/debug context; do not treat as correctness proof.",
                        },
                    ),
                }
                for name in artifact_names
            ],
        }

    @staticmethod
    def _review_summary_pr_comment_payload(
        actions_payload: dict[str, Any],
        quality_payload: dict[str, Any],
        *,
        summary_mode: str,
    ) -> dict[str, Any]:
        actionable_items = actions_payload.get("actionable_items", [])
        violations = actions_payload.get("violations", [])
        signals = quality_payload.get("signals", [])
        body_lines = [
            "### DocAtlas patch review",
            "",
            f"Attachability: `{quality_payload.get('attachable')}`",
            f"Summary mode: `{summary_mode}`",
        ]
        if violations:
            body_lines.extend(["", "Violations:"])
            body_lines.extend(
                f"- `{PatchReviewService._markdown_text(item.get('constraint_id'))}`: "
                f"{PatchReviewService._markdown_text(item.get('reason'))}"
                for item in violations
            )
        if signals:
            body_lines.extend(["", "Signals:"])
            body_lines.extend(
                f"- `{item.get('code')}` ({item.get('severity')}, count={item.get('count')})"
                for item in signals
            )
        if actionable_items:
            body_lines.extend(["", "Actionable checklist:"])
            body_lines.extend(item.get("markdown", "") for item in actionable_items if item.get("markdown"))
        body_lines.extend([
            "",
            "Non-blocking review context only; not a correctness proof or test replacement.",
        ])
        body_markdown = PatchReviewService._truncate_pr_comment("\n".join(body_lines) + "\n")
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_pr_comment.json"],
            "summary_mode": summary_mode,
            "title": "DocAtlas patch review",
            "attachable": quality_payload.get("attachable"),
            "body": body_markdown,
            "body_markdown": body_markdown,
            "source_artifacts": [
                "review_summary_quality.json",
                "review_summary_actions.json",
            ],
            "signals": signals,
            "actionable_items": actionable_items,
            "violations": violations,
            "claims_avoided": quality_payload.get("claims_avoided", []),
        }

    @staticmethod
    def _review_summary_trace_payload(
        constraints: dict[str, Any],
        validation: dict[str, Any],
        actions_payload: dict[str, Any],
        quality_payload: dict[str, Any],
        coverage_payload: dict[str, Any],
        *,
        summary_mode: str,
    ) -> dict[str, Any]:
        constraints_by_id = {str(item.get("id") or ""): item for item in constraints.get("constraints", [])}
        validation_by_id = {str(item.get("constraint_id") or ""): item for item in validation.get("results", [])}
        action_traces = []
        for item in actions_payload.get("actionable_items", []):
            constraint_id = str(item.get("constraint_id") or "")
            raw_constraint = constraints_by_id.get(constraint_id, {})
            raw_validation = validation_by_id.get(constraint_id, {})
            action_traces.append(
                {
                    "rank": item.get("rank"),
                    "constraint_id": constraint_id,
                    "source": raw_constraint.get("source") or item.get("source"),
                    "evidence": raw_constraint.get("evidence") or item.get("evidence"),
                    "validation_status": raw_validation.get("status"),
                    "validation_reason": raw_validation.get("reason"),
                    "raw_constraint_artifact": "constraints.json",
                    "raw_validation_artifact": "validation.json",
                }
            )
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_trace.json"],
            "summary_mode": summary_mode,
            "source_artifacts": [
                "constraints.json",
                "validation.json",
                "constraint_coverage.json",
                "review_summary_quality.json",
                "review_summary_actions.json",
            ],
            "counts": {
                "constraints": len(constraints.get("constraints", [])),
                "validation_results": len(validation.get("results", [])),
                "action_traces": len(action_traces),
                "quality_signals": len(quality_payload.get("signals", [])),
                "coverage_categories": len(coverage_payload.get("categories", [])),
            },
            "action_traces": action_traces,
            "coverage_status_counts": coverage_payload.get("validation_status_counts", {}),
            "claims_avoided": quality_payload.get("claims_avoided", []),
        }

    @staticmethod
    def _constraint_coverage_payload(constraints: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        constraint_items = list(constraints.get("constraints") or [])
        results = list(validation.get("results") or [])
        results_by_id = {str(item.get("constraint_id") or ""): item for item in results}
        categories: dict[str, dict[str, Any]] = {
            "generated_files": PatchReviewService._empty_coverage_category("generated_files", "Generated/protected artifact edits"),
            "source_of_truth_owner_layer": PatchReviewService._empty_coverage_category("source_of_truth_owner_layer", "Source-of-truth, owner, or layer rules"),
            "required_checks_tests": PatchReviewService._empty_coverage_category("required_checks_tests", "Required checks and test evidence"),
            "dependency_versions": PatchReviewService._empty_coverage_category("dependency_versions", "Dependency versions and lockfiles"),
            "docs_update_requirements": PatchReviewService._empty_coverage_category("docs_update_requirements", "Documentation update requirements"),
            "unknown_manual": PatchReviewService._empty_coverage_category("unknown_manual", "Constraints requiring unknown/manual review handling"),
        }
        uncategorized = PatchReviewService._empty_coverage_category("uncategorized", "Other constraints")
        for constraint in constraint_items:
            result = results_by_id.get(str(constraint.get("id") or ""))
            names = PatchReviewService._coverage_categories_for_constraint(constraint, result) or ["uncategorized"]
            for name in names:
                category = categories.get(name) or uncategorized
                PatchReviewService._add_constraint_to_coverage_category(category, constraint, result)
        status_counts = {
            "satisfied": int(validation.get("satisfied") or 0),
            "violated": int(validation.get("violated") or 0),
            "unknown": int(validation.get("unknown") or 0),
            "manual_review": int(validation.get("manual_review") or 0),
        }
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["constraint_coverage.json"],
            "source_artifacts": ["constraints.json", "validation.json"],
            "total_constraints": int(validation.get("total_constraints") or len(constraint_items)),
            "validation_status_counts": status_counts,
            "covered_count": status_counts["satisfied"] + status_counts["violated"],
            "unknown_manual_count": status_counts["unknown"] + status_counts["manual_review"],
            "categories": [category for category in [*categories.values(), uncategorized] if category["total_constraints"] > 0],
            "claims_avoided": [
                "correctness_proof",
                "test_or_human_review_replacement",
                "unknown_manual_as_pass",
            ],
        }

    @staticmethod
    def _empty_coverage_category(name: str, description: str) -> dict[str, Any]:
        return {
            "name": name,
            "description": description,
            "total_constraints": 0,
            "status_counts": {"satisfied": 0, "violated": 0, "unknown": 0, "manual_review": 0, "unvalidated": 0},
            "constraint_ids": [],
            "examples": [],
        }

    @staticmethod
    def _coverage_categories_for_constraint(constraint: dict[str, Any], result: dict[str, Any] | None) -> list[str]:
        ctype = str(constraint.get("type") or "").lower()
        text = " ".join(
            str(value or "")
            for value in (
                ctype,
                constraint.get("instruction"),
                constraint.get("source"),
                constraint.get("evidence"),
                " ".join(constraint.get("files") or []),
            )
        ).lower()
        names: list[str] = []
        if ctype in {"generated_file", "forbidden_edit"} or "generated" in text or "protected" in text:
            names.append("generated_files")
        if ctype == "source_of_truth" or any(token in text for token in ("source-of-truth", "source of truth", "owner", "owns", "layer", "delegate")):
            names.append("source_of_truth_owner_layer")
        if ctype == "verification" or any(token in text for token in ("test", "check", "regression", "coverage")):
            names.append("required_checks_tests")
        if ctype == "dependency_version" or "lockfile" in text or "dependency" in text or "version" in text:
            names.append("dependency_versions")
        if "doc" in text or "readme" in text or "changelog" in text:
            names.append("docs_update_requirements")
        if result and result.get("status") in {"unknown", "manual_review"}:
            names.append("unknown_manual")
        return list(dict.fromkeys(names))

    @staticmethod
    def _add_constraint_to_coverage_category(category: dict[str, Any], constraint: dict[str, Any], result: dict[str, Any] | None) -> None:
        constraint_id = str(constraint.get("id") or "")
        status = str((result or {}).get("status") or "unvalidated")
        if status not in category["status_counts"]:
            status = "unvalidated"
        category["total_constraints"] += 1
        category["status_counts"][status] += 1
        if constraint_id:
            category["constraint_ids"].append(constraint_id)
        if len(category["examples"]) < 3:
            category["examples"].append(
                {
                    "constraint_id": constraint_id,
                    "status": status,
                    "type": constraint.get("type"),
                    "source": constraint.get("source"),
                    "reason": (result or {}).get("reason"),
                }
            )

    @staticmethod
    def _review_summary_bot_bundle_payload(
        manifest_payload: dict[str, Any],
        quality_payload: dict[str, Any],
        actions_payload: dict[str, Any],
        pr_comment_payload: dict[str, Any],
        trace_payload: dict[str, Any],
        *,
        summary_mode: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_bot_bundle.json"],
            "summary_mode": summary_mode,
            "source_artifacts": [
                "review_summary_manifest.json",
                "review_summary_quality.json",
                "review_summary_actions.json",
                "review_summary_pr_comment.json",
                "review_summary_trace.json",
                "constraint_coverage.json",
            ],
            "manifest": manifest_payload,
            "quality": quality_payload,
            "actions": actions_payload,
            "pr_comment": pr_comment_payload,
            "trace": trace_payload,
            "advisory_decision": PatchReviewService._review_summary_advisory_decision_payload(
                quality_payload,
                actions_payload,
            ),
            "claims_avoided": quality_payload.get("claims_avoided", []),
        }

    @staticmethod
    def _review_summary_advisory_decision_payload(
        quality_payload: dict[str, Any],
        actions_payload: dict[str, Any],
    ) -> dict[str, Any]:
        signals = {str(item.get("code") or "") for item in quality_payload.get("signals", [])}
        unknown_triage_counts: dict[str, int] = {}
        for item in quality_payload.get("unknown_triage", []):
            code = str(item.get("code") or "")
            count = int(item.get("count") or 0)
            if code and count > 0:
                unknown_triage_counts[code] = count
        unknown_triage_codes = list(unknown_triage_counts)
        violations = list(actions_payload.get("violations") or [])
        actionable_items = list(actions_payload.get("actionable_items") or [])
        has_violations = bool(violations) or quality_payload.get("violated_count", 0) > 0 or "violations_present" in signals
        has_manual_review = (
            quality_payload.get("unknown_count", 0) > 0
            or quality_payload.get("manual_review_count", 0) > 0
            or "manual_review_required" in signals
            or bool(unknown_triage_codes)
        )
        has_actionable_items = bool(actionable_items) or quality_payload.get("actionable_items_total_count", 0) > 0
        reason_codes = []
        if has_violations:
            reason_codes.append("violations_present")
        if has_manual_review:
            reason_codes.append("manual_review_required")
        if has_actionable_items:
            reason_codes.append("actionable_items_present")
        should_attach_comment = has_violations or has_manual_review or has_actionable_items
        if not should_attach_comment:
            reason_codes.append("no_attachable_review_signal")
        return {
            "should_attach_comment": should_attach_comment,
            "show_warning_badge": has_violations or has_manual_review,
            "highlight_violations": has_violations,
            "requires_manual_review": has_violations or has_manual_review,
            "reason_codes": reason_codes,
            "unknown_triage_codes": unknown_triage_codes,
            "unknown_triage_counts": unknown_triage_counts,
            "semantics": "advisory_non_blocking_only",
            "claims_avoided": [
                "safe_to_merge",
                "correctness_proof",
                "test_or_human_review_replacement",
            ],
        }

    @staticmethod
    def _review_summary_model(
        task: str,
        changed_files: list[str],
        constraints: dict[str, Any],
        validation: dict[str, Any],
        *,
        summary_max_items: int = 5,
        summary_mode: str = "standard",
    ) -> dict[str, Any]:
        summary_mode = summary_mode.lower()
        if summary_mode not in {"compact", "standard", "verbose"}:
            raise ValueError(f"unsupported summary_mode: {summary_mode}")
        constraint_items = list(constraints.get("constraints", []))
        results = list(validation.get("results", []))
        violations = [result for result in results if result.get("status") == "violated"]
        unknowns = [result for result in results if result.get("status") in {"unknown", "manual_review"}]
        generated_or_lock = [
            result for result in results
            if "generated" in str(result.get("reason", "")).lower() or "lockfile" in str(result.get("reason", "")).lower()
        ]
        ranked_constraints = sorted(
            constraint_items,
            key=lambda item: PatchReviewService._summary_constraint_rank(item, changed_files, task),
        )
        constraints_by_id = {str(item.get("id") or ""): item for item in constraint_items}
        violation_constraints = [
            constraints_by_id[str(item.get("constraint_id") or "")]
            for item in violations
            if str(item.get("constraint_id") or "") in constraints_by_id
        ]
        actionable_candidates = [item for item in ranked_constraints if PatchReviewService._summary_bucket(item, changed_files, task) == "actionable"]
        all_actionable = PatchReviewService._dedupe_constraints([*violation_constraints, *actionable_candidates])
        actionable = all_actionable[:summary_max_items]
        manual_limit = 12 if summary_mode == "verbose" else 6
        low_limit = 12 if summary_mode == "verbose" else 6
        symbol_limit = 16 if summary_mode == "verbose" else 8
        excluded_limit = 24 if summary_mode == "verbose" else 12
        manual_context = [item for item in ranked_constraints if PatchReviewService._summary_bucket(item, changed_files, task) == "manual"][:manual_limit]
        low_context = [item for item in ranked_constraints if PatchReviewService._summary_bucket(item, changed_files, task) == "low"][:low_limit]
        symbol_candidates = list(constraints.get("symbol_candidates") or [])
        useful_symbols = [item for item in symbol_candidates if not PatchReviewService._is_low_value_symbol_candidate(item, task)]
        low_symbols = [item for item in symbol_candidates if PatchReviewService._is_low_value_symbol_candidate(item, task)]
        unknown_buckets = PatchReviewService._unknown_buckets(unknowns, constraint_items)
        unknown_triage = PatchReviewService._unknown_triage(unknowns, constraint_items)
        excluded_sources = list(constraints.get("excluded_source_reasons") or [])
        residual_memos = [item for item in excluded_sources if item.get("reason") in DOGFOOD_MEMO_REASONS]
        quality = PatchReviewService._summary_quality(
            actionable=actionable,
            actionable_total_count=len(all_actionable),
            low_context=low_context,
            low_symbols=low_symbols,
            unknown_buckets=unknown_buckets,
            residual_memos=residual_memos,
        )
        return {
            "summary_mode": summary_mode,
            "all_actionable": all_actionable,
            "actionable": actionable,
            "manual_context": manual_context,
            "low_context": low_context,
            "useful_symbols": useful_symbols,
            "low_symbols": low_symbols,
            "unknown_buckets": unknown_buckets,
            "unknown_triage": unknown_triage,
            "excluded_sources": excluded_sources,
            "residual_memos": residual_memos,
            "violations": violations,
            "generated_or_lock": generated_or_lock,
            "results_by_id": {str(item.get("constraint_id") or ""): item for item in results},
            "quality": quality,
            "symbol_limit": symbol_limit,
            "low_limit": low_limit,
            "excluded_limit": excluded_limit,
        }

    @staticmethod
    def _review_summary_quality_payload(
        task: str,
        changed_files: list[str],
        constraints: dict[str, Any],
        validation: dict[str, Any],
        *,
        summary_max_items: int = 5,
        summary_mode: str = "standard",
    ) -> dict[str, Any]:
        model = PatchReviewService._review_summary_model(
            task,
            changed_files,
            constraints,
            validation,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        summary_mode = model["summary_mode"]
        actionable = model["actionable"]
        all_actionable = model["all_actionable"]
        low_context = model["low_context"]
        low_symbols = model["low_symbols"]
        unknown_buckets = model["unknown_buckets"]
        unknown_triage = model["unknown_triage"]
        residual_memos = model["residual_memos"]
        quality = model["quality"]
        signals = PatchReviewService._review_summary_quality_signals(
            actionable=actionable,
            low_context=low_context,
            low_symbols=low_symbols,
            unknown_buckets=unknown_buckets,
            unknown_triage=unknown_triage,
            residual_memos=residual_memos,
            validation=validation,
        )
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_quality.json"],
            "attachable": quality["attachable"],
            "summary_mode": summary_mode,
            "actionable_items_limit": summary_max_items,
            "actionable_items_count": len(actionable),
            "actionable_items_total_count": len(all_actionable),
            "low_value_top_items_count": len(low_context) + len(low_symbols),
            "unknown_bucket_count": len(unknown_buckets),
            "residual_memo_source_count": len(residual_memos),
            "satisfied_count": validation.get("satisfied", 0),
            "violated_count": validation.get("violated", 0),
            "unknown_count": validation.get("unknown", 0),
            "manual_review_count": validation.get("manual_review", 0),
            "reasons": quality["reasons"],
            "signals": signals,
            "unknown_triage": unknown_triage,
            "unknown_buckets": [
                {
                    "name": name,
                    "count": len(items),
                    "examples": [
                        {"constraint_id": item.get("constraint_id"), "reason": item.get("reason")}
                        for item in items[:2]
                    ],
                }
                for name, items in unknown_buckets.items()
            ],
            "claims_avoided": [
                "correctness_proof",
                "test_or_human_review_replacement",
                "broad_docatlas_superiority",
            ],
        }

    @staticmethod
    def _review_summary_quality_signals(
        *,
        actionable: list[dict[str, Any]],
        low_context: list[dict[str, Any]],
        low_symbols: list[dict[str, Any]],
        unknown_buckets: dict[str, list[dict[str, Any]]],
        unknown_triage: list[dict[str, Any]],
        residual_memos: list[dict[str, Any]],
        validation: dict[str, Any],
    ) -> list[dict[str, Any]]:
        signals = [
            {
                "code": "actionable_items_present" if actionable else "no_actionable_items",
                "severity": "info" if actionable else "warning",
                "count": len(actionable),
                "message": "Actionable checklist items are available." if actionable else "No actionable checklist items were selected.",
            },
            {
                "code": "violations_present" if validation.get("violated", 0) else "no_violations",
                "severity": "error" if validation.get("violated", 0) else "info",
                "count": validation.get("violated", 0),
                "message": "Validation found violated constraints." if validation.get("violated", 0) else "Validation found no violated constraints.",
            },
        ]
        if unknown_buckets:
            signals.append(
                {
                    "code": "unknown_buckets_present",
                    "severity": "warning",
                    "count": len(unknown_buckets),
                    "message": "Manual-review buckets remain.",
                }
            )
        manual_review_count = sum(item["count"] for item in unknown_triage if item.get("requires_manual_review"))
        if manual_review_count:
            signals.append(
                {
                    "code": "manual_review_required",
                    "severity": "warning",
                    "count": manual_review_count,
                    "message": "Unknown validation results require manual review; do not treat them as pass.",
                }
            )
        if low_context or low_symbols:
            signals.append(
                {
                    "code": "low_value_signals_present",
                    "severity": "warning",
                    "count": len(low_context) + len(low_symbols),
                    "message": "Low-confidence or noisy signals were kept out of the top checklist.",
                }
            )
        if residual_memos:
            signals.append(
                {
                    "code": "residual_memo_sources_present",
                    "severity": "warning",
                    "count": len(residual_memos),
                    "message": "Prior dogfood memo/task artifacts were excluded from top-level recommendations.",
                }
            )
        return signals

    @staticmethod
    def _review_summary_actions_payload(
        task: str,
        changed_files: list[str],
        constraints: dict[str, Any],
        validation: dict[str, Any],
        *,
        summary_max_items: int = 5,
        summary_mode: str = "standard",
    ) -> dict[str, Any]:
        model = PatchReviewService._review_summary_model(
            task,
            changed_files,
            constraints,
            validation,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        summary_mode = model["summary_mode"]
        actionable = model["actionable"]
        violations = model["violations"]
        results_by_id = model["results_by_id"]
        return {
            "schema_version": PATCH_REVIEW_SCHEMA_VERSIONS["review_summary_actions.json"],
            "summary_mode": summary_mode,
            "actionable_items_limit": summary_max_items,
            "actionable_items": [
                PatchReviewService._actionable_item_payload(
                    item,
                    results_by_id.get(str(item.get("id") or "")),
                    rank=index,
                )
                for index, item in enumerate(actionable, start=1)
            ],
            "violations": [
                {
                    "constraint_id": item.get("constraint_id"),
                    "reason": item.get("reason"),
                    "files": item.get("files", []),
                }
                for item in violations
            ],
            "claims_avoided": [
                "correctness_proof",
                "test_or_human_review_replacement",
                "broad_docatlas_superiority",
            ],
        }

    @staticmethod
    def _actionable_item_payload(item: dict[str, Any], result: dict[str, Any] | None, *, rank: int) -> dict[str, Any]:
        source = item.get("source")
        instruction = item.get("instruction")
        evidence = item.get("evidence")
        files = item.get("files") or []
        symbols = item.get("symbols") or []
        payload = {
            "rank": rank,
            "constraint_id": item.get("id"),
            "instruction": instruction,
            "source": source,
            "type": item.get("type"),
            "confidence": item.get("confidence"),
            "evidence": evidence,
            "source_files": files,
            "symbols": symbols,
            "files": files,
            "markdown": (
                f"- {PatchReviewService._markdown_text(instruction)} "
                f"(source: `{PatchReviewService._markdown_text(source)}`)"
            ),
            "evidence_markdown": f"  - evidence: {PatchReviewService._markdown_text(evidence)}" if evidence else None,
        }
        if result:
            payload["validation_status"] = result.get("status")
            payload["validation_reason"] = result.get("reason")
            payload["files"] = result.get("files", [])
        return payload

    @staticmethod
    def _markdown_text(value: Any, *, limit: int = MAX_PR_COMMENT_FIELD_CHARS) -> str:
        text = str(value or "")
        text = text.replace("`", "\\`").replace("@", "@\u200b")
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 16)].rstrip() + " … [truncated]"

    @staticmethod
    def _truncate_pr_comment(body: str) -> str:
        if len(body) <= MAX_PR_COMMENT_CHARS:
            return body
        return body[: MAX_PR_COMMENT_CHARS - 64].rstrip() + "\n\n_Comment truncated for provider limits._\n"

    @staticmethod
    def _constraints_markdown(packet: dict[str, Any]) -> str:
        lines = ["# Patch constraints", "", f"Task: {packet.get('task')}", "", "## Constraints"]
        for constraint in packet.get("constraints", []):
            lines.append(
                f"- [{constraint.get('type')}/{constraint.get('severity')}/{constraint.get('confidence')}] "
                f"{constraint.get('instruction')} (source: `{constraint.get('source')}`)"
            )
        if packet.get("symbol_candidates"):
            lines.extend(["", "## Symbol candidates"])
            for candidate in packet["symbol_candidates"]:
                lines.append(f"- `{candidate.get('term')}` -> `{candidate.get('matched_symbol')}` in `{candidate.get('source')}`: {candidate.get('evidence')}")
        if packet.get("warnings"):
            lines.extend(["", "## Warnings"])
            lines.extend(f"- {warning}" for warning in packet["warnings"])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _review_summary(
        task: str,
        changed_files: list[str],
        constraints: dict[str, Any],
        validation: dict[str, Any],
        *,
        warnings: list[str] | None = None,
        untracked_files: list[str] | None = None,
        ignored_runtime_artifacts: list[str] | None = None,
        summary_max_items: int = 5,
        summary_mode: str = "standard",
    ) -> str:
        model = PatchReviewService._review_summary_model(
            task,
            changed_files,
            constraints,
            validation,
            summary_max_items=summary_max_items,
            summary_mode=summary_mode,
        )
        summary_mode = model["summary_mode"]
        warnings = warnings or []
        untracked_files = untracked_files or []
        ignored_runtime_artifacts = ignored_runtime_artifacts or []
        violations = model["violations"]
        generated_or_lock = model["generated_or_lock"]
        actionable = model["actionable"]
        manual_context = model["manual_context"]
        low_context = model["low_context"]
        symbol_limit = model["symbol_limit"]
        low_limit = model["low_limit"]
        excluded_limit = model["excluded_limit"]
        useful_symbols = model["useful_symbols"]
        low_symbols = model["low_symbols"]
        unknown_buckets = model["unknown_buckets"]
        excluded_sources = model["excluded_sources"]
        residual_memos = model["residual_memos"]
        quality = model["quality"]

        lines = [
            "# Patch review summary",
            "",
            "Status: review/audit artifact, not correctness proof.",
            "",
            f"Task: {task}",
            "",
            "## Changed files",
            *[f"- {path}" for path in changed_files],
            "",
            "## Review summary quality",
            f"- attachable: {quality['attachable']}",
            f"- summary_mode: {summary_mode}",
            f"- actionable_items_limit: {summary_max_items}",
            f"- actionable_items_count: {len(actionable)}",
            f"- low_value_top_items_count: {len(low_context) + len(low_symbols)}",
            f"- unknown_bucket_count: {len(unknown_buckets)}",
            f"- residual_memo_source_count: {len(residual_memos)}",
        ]
        if quality["reasons"]:
            lines.append("- reasons:")
            lines.extend(f"  - {reason}" for reason in quality["reasons"])
        lines.extend(["", "## Actionable PR checklist"])
        lines.extend(
            [f"- {item.get('instruction')} (source: `{item.get('source')}`)" for item in actionable]
            or ["- none"]
        )
        if summary_mode == "compact":
            lines.extend(["", "## Violations"])
            lines.extend([f"- {item.get('constraint_id')}: {item.get('reason')}" for item in violations] or ["- none"])
            lines.extend([
                "",
                "## Claims avoided",
                "- This artifact does not prove correctness.",
                "- This artifact does not replace tests or human review.",
                "- This artifact does not claim broad DocAtlas superiority.",
            ])
            return "\n".join(lines) + "\n"
        lines.extend(["", "## Manual review context"])
        lines.extend(
            [f"- {item.get('instruction')} (source: `{item.get('source')}`)" for item in manual_context]
            or ["- none"]
        )
        lines.extend(["", "## Low-confidence / noisy signals"])
        lines.extend([f"- {item.get('instruction')} (source: `{item.get('source')}`)" for item in low_context] or [])
        lines.extend(
            [
                f"- symbol `{item.get('matched_symbol')}` from `{item.get('source')}`: {item.get('reason')}"
                for item in low_symbols[:6]
            ]
            or ["- none"]
        )
        lines.extend([
            "",
            "## Validation",
            f"- satisfied: {validation.get('satisfied', 0)}",
            f"- violated: {validation.get('violated', 0)}",
            f"- unknown/manual review: {validation.get('unknown', 0) + validation.get('manual_review', 0)}",
            f"- unknown: {validation.get('unknown', 0)}",
            f"- manual_review: {validation.get('manual_review', 0)}",
            "",
            "## Violations",
        ])
        lines.extend([f"- {item.get('constraint_id')}: {item.get('reason')}" for item in violations] or ["- none"])
        lines.extend(["", "## Unknown/manual review buckets"])
        if unknown_buckets:
            for name, items in unknown_buckets.items():
                lines.append(f"- {name}: {len(items)}")
                for item in items[:2]:
                    lines.append(f"  - {item.get('constraint_id')}: {item.get('reason')}")
        else:
            lines.append("- none")
        lines.extend(["", "## Generated/lockfile checks"])
        lines.extend([f"- {item.get('constraint_id')}: {item.get('status')} — {item.get('reason')}" for item in generated_or_lock] or ["- none"])
        if constraints.get("symbol_candidates"):
            lines.extend(["", "## Source-of-truth / symbol notes"])
            if useful_symbols:
                for candidate in useful_symbols[:symbol_limit]:
                    lines.append(f"- `{candidate.get('term')}` -> `{candidate.get('matched_symbol')}` (`{candidate.get('source')}`)")
            if low_symbols:
                lines.append("- low-confidence/noisy symbols hidden from checklist:")
                lines.extend(f"  - `{candidate.get('matched_symbol')}` (`{candidate.get('source')}`)" for candidate in low_symbols[:low_limit])
        if excluded_sources:
            lines.extend(["", "## Excluded or ignored sources"])
            for item in excluded_sources[:excluded_limit]:
                lines.append(f"- {item.get('reason')}: `{item.get('path')}`")
            if len(excluded_sources) > excluded_limit:
                lines.append(f"- ... {len(excluded_sources) - excluded_limit} more excluded source(s)")
        if untracked_files:
            lines.extend(["", "## Untracked files"])
            lines.extend(f"- {path}" for path in untracked_files)
        if ignored_runtime_artifacts:
            lines.extend(["", "## Ignored runtime/cache artifacts"])
            lines.extend(f"- {path}" for path in ignored_runtime_artifacts[:20])
        if constraints.get("warnings") or validation.get("warnings") or warnings:
            lines.extend(["", "## Warnings"])
            lines.extend(f"- {warning}" for warning in warnings)
            lines.extend(f"- {warning}" for warning in constraints.get("warnings", []))
            lines.extend(f"- {warning}" for warning in validation.get("warnings", []))
        lines.extend([
            "",
            "## Claims avoided",
            "- This artifact does not prove correctness.",
            "- This artifact does not replace tests or human review.",
            "- This artifact does not claim broad DocAtlas superiority.",
        ])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _summary_constraint_rank(item: dict[str, Any], changed_files: list[str], task: str) -> tuple[int, int, str]:
        source = str(item.get("source") or "")
        instruction = str(item.get("instruction") or "")
        evidence = str(item.get("evidence") or "")
        ctype = str(item.get("type") or "")
        confidence = str(item.get("confidence") or "low")
        haystack = f"{instruction} {evidence} {' '.join(item.get('symbols') or [])}".lower()
        haystack_compact = re.sub(r"[^a-z0-9]+", "", haystack)
        changed = " ".join(changed_files).lower()
        task_lower = task.lower()
        priority = 50
        if ctype in {"generated_file", "forbidden_edit"} or "generated" in haystack or "lockfile" in haystack:
            priority = min(priority, 10)
        if any(path and path.lower() in source.lower() for path in changed_files):
            priority = min(priority, 15)
        if any(token in haystack or token in haystack_compact for token in PatchReviewService._task_symbol_tokens(task_lower)):
            priority = min(priority, 20)
        if "policy" in task_lower and ("provider" in haystack or "policy" in haystack or "ui" in haystack):
            priority = min(priority, 22)
        if source.startswith("docs/research/docatlas-dogfood"):
            priority = max(priority, 80)
        if PatchReviewService._is_broad_context_source(source, instruction):
            priority = max(priority, 60)
        if PatchReviewService._has_only_low_value_symbols(item) or PatchReviewService._has_low_value_matched_symbol(item):
            priority = max(priority, 60)
        confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(confidence, 3)
        if source and source.lower() in changed:
            priority -= 3
        return (priority, confidence_rank, str(item.get("id") or ""))

    @staticmethod
    def _summary_bucket(item: dict[str, Any], changed_files: list[str], task: str) -> str:
        rank = PatchReviewService._summary_constraint_rank(item, changed_files, task)[0]
        source = str(item.get("source") or "")
        confidence = str(item.get("confidence") or "low")
        if source.startswith("docs/research/docatlas-dogfood") or rank >= 75 or confidence == "low":
            return "low"
        if rank <= 25:
            return "actionable"
        return "manual"

    @staticmethod
    def _dedupe_constraints(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in items:
            key = str(item.get("id") or item.get("instruction") or "")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _task_symbol_tokens(task_lower: str) -> set[str]:
        tokens = {
            token
            for token in re.findall(r"[a-zа-я0-9_]{3,}", task_lower, flags=re.IGNORECASE)
            if token not in TASK_TOKEN_STOPWORDS
            and token not in {value.lower() for value in LOW_VALUE_SYMBOLS}
        }
        compact_task = re.sub(r"[^a-zа-я0-9]+", "", task_lower, flags=re.IGNORECASE)
        for token in ("openinfo", "closemenu", "gotoscandocinit", "generated", "lockfile", "provider", "policy"):
            if token.lower() in task_lower:
                tokens.add(token.lower())
        for phrase in re.findall(r"[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)+", task_lower):
            compact_phrase = re.sub(r"[^a-z0-9]+", "", phrase)
            if len(compact_phrase) >= 6:
                tokens.add(compact_phrase)
        if compact_task and len(compact_task) <= 48:
            tokens.add(compact_task)
        if "быстрая информация" in task_lower or "quick-info" in task_lower or "quick info" in task_lower:
            tokens.add("openinfo")
        if "закры" in task_lower or "close menu" in task_lower or "штор" in task_lower:
            tokens.add("closemenu")
        if "scan" in task_lower or "скан" in task_lower:
            tokens.add("gotoscandocinit")
        return tokens

    @staticmethod
    def _is_low_value_symbol_candidate(item: dict[str, Any], task: str) -> bool:
        symbol = str(item.get("matched_symbol") or "")
        task_lower = task.lower()
        if symbol in LOW_VALUE_SYMBOLS or symbol.lower() in {value.lower() for value in LOW_VALUE_SYMBOLS}:
            explicit = symbol.lower() in task_lower
            return not explicit
        evidence = str(item.get("evidence") or "").strip()
        if evidence.startswith(("import ", "export ", "part ")):
            return True
        return False

    @staticmethod
    def _has_only_low_value_symbols(item: dict[str, Any]) -> bool:
        symbols = [str(symbol or "") for symbol in item.get("symbols") or []]
        if not symbols:
            return False
        low_value = {value.lower() for value in LOW_VALUE_SYMBOLS}
        return all(symbol in LOW_VALUE_SYMBOLS or symbol.lower() in low_value for symbol in symbols)

    @staticmethod
    def _has_low_value_matched_symbol(item: dict[str, Any]) -> bool:
        symbols = [str(symbol or "") for symbol in item.get("symbols") or []]
        if len(symbols) < 2:
            return False
        low_value = {value.lower() for value in LOW_VALUE_SYMBOLS}
        matched_symbol = symbols[-1]
        if matched_symbol not in LOW_VALUE_SYMBOLS and matched_symbol.lower() not in low_value:
            return False
        evidence = str(item.get("evidence") or "").strip()
        if evidence.startswith(("import ", "export ", "part ")):
            return True
        instruction = str(item.get("instruction") or "")
        return "matches existing project symbol" in instruction

    @staticmethod
    def _is_broad_context_source(source: str, instruction: str) -> bool:
        lowered = f"{source} {instruction}".lower()
        return (
            "external_oidc" in lowered
            or "rules that must not be violated" in lowered
            or "mainscreen owns global runtime" in lowered
        )

    @staticmethod
    def _unknown_buckets(unknowns: list[dict[str, Any]], constraints: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        by_id = {item.get("id"): item for item in constraints}
        buckets: dict[str, list[dict[str, Any]]] = {}
        for item in unknowns:
            constraint = by_id.get(item.get("constraint_id"), {})
            source = str(constraint.get("source") or "")
            reason = str(item.get("reason") or "")
            text = f"{item.get('constraint_id')} {reason} {source}".lower()
            if source.startswith("docs/research/docatlas-dogfood"):
                bucket = "Residual dogfood/research memo context"
            elif "source-of-truth" in text or "source_of_truth" in text or "ownership" in text or "owns" in text:
                bucket = "Source-of-truth ownership unknowns"
            elif "provider" in text or "ui" in text or "policy" in text or "presentation" in text:
                bucket = "Provider/UI policy ownership unknowns"
            elif "generated" in text or "lockfile" in text or "protected" in text:
                bucket = "Generated/lockfile/protected-file unknowns"
            elif "module" in text or "boundary" in text or "route" in text or "scan_doc" in text or "architecture" in text:
                bucket = "Module-boundary context unknowns"
            else:
                bucket = "Other low-confidence context"
            buckets.setdefault(bucket, []).append(item)
        return dict(sorted(buckets.items()))

    @staticmethod
    def _unknown_triage(unknowns: list[dict[str, Any]], constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id = {item.get("id"): item for item in constraints}
        buckets: dict[str, list[dict[str, Any]]] = {
            "missing_diff_evidence": [],
            "missing_test_evidence": [],
            "manual_review_required": [],
            "low_risk_unknown": [],
        }
        messages = {
            "missing_diff_evidence": "No decisive changed-file or diff evidence was found for this constraint.",
            "missing_test_evidence": "The unknown result depends on missing or inconclusive test evidence.",
            "manual_review_required": "A human reviewer must resolve an open product, ownership, or policy question.",
            "low_risk_unknown": "Low-confidence context remains unresolved; keep it visible for manual review.",
        }
        for item in unknowns:
            constraint = by_id.get(item.get("constraint_id"), {})
            manual_text = " ".join(
                str(value or "")
                for value in (
                    item.get("reason"),
                    constraint.get("instruction"),
                    constraint.get("evidence"),
                    constraint.get("source"),
                )
            ).lower()
            evidence_text = " ".join(
                str(value or "")
                for value in (
                    item.get("constraint_id"),
                    item.get("reason"),
                    constraint.get("instruction"),
                    constraint.get("evidence"),
                    constraint.get("source"),
                    constraint.get("type"),
                )
            ).lower()
            if PatchReviewService._has_manual_unknown_signal(manual_text):
                code = "manual_review_required"
            elif "test" in evidence_text or "coverage" in evidence_text or "regression" in evidence_text:
                code = "missing_test_evidence"
            elif PatchReviewService._has_missing_diff_unknown_signal(evidence_text):
                code = "missing_diff_evidence"
            else:
                code = "low_risk_unknown"
            buckets[code].append(item)
        return [
            {
                "code": code,
                "count": len(items),
                "requires_manual_review": True,
                "message": messages[code],
                "examples": [
                    PatchReviewService._unknown_triage_example(item, by_id.get(item.get("constraint_id"), {}))
                    for item in items[:2]
                ],
            }
            for code, items in buckets.items()
            if items
        ]

    @staticmethod
    def _unknown_triage_example(item: dict[str, Any], constraint: dict[str, Any]) -> dict[str, Any]:
        example = {
            "constraint_id": item.get("constraint_id"),
            "reason": item.get("reason"),
        }
        for field in ("source", "instruction", "evidence", "confidence"):
            value = constraint.get(field)
            if value:
                example[field] = value
        return example

    @staticmethod
    def _has_manual_unknown_signal(text: str) -> bool:
        manual_tokens = (
            "manual review",
            "manual reviewer",
            "manual approval",
            "manual decision",
            "manual triage",
            "human review",
            "human reviewer",
            "designer",
            "open question",
            "ownership",
            "source-of-truth",
            "source of truth",
            "policy",
            "дизайнер",
            "дизайнера",
            "дизайнером",
            "открытый вопрос",
            "открыт вопрос",
            "владель",
            "ответствен",
            "согласовать",
            "уточнить",
            "политик",
        )
        if any(token in text for token in manual_tokens):
            return True
        return bool(re.search(r"\bdesign\s+(?:input|question|approval|review|owner|dependency)\b", text))

    @staticmethod
    def _has_missing_diff_unknown_signal(text: str) -> bool:
        if any(
            token in text
            for token in (
                "diff",
                "changed-file",
                "changed file",
                "patch",
                "direct evidence",
                "not found",
                "missing evidence",
                "changed files unavailable",
                "changed files or diff unavailable",
                "not deterministically checkable from changed files",
                "not deterministic for this patch",
            )
        ):
            return True
        return any(token in text for token in ("source question", "source changed_files", "source changed files"))

    @staticmethod
    def _summary_quality(
        *,
        actionable: list[dict[str, Any]],
        actionable_total_count: int,
        low_context: list[dict[str, Any]],
        low_symbols: list[dict[str, Any]],
        unknown_buckets: dict[str, list[dict[str, Any]]],
        residual_memos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        reasons: list[str] = []
        if len(actionable) < 3:
            reasons.append(f"only {len(actionable)} actionable checklist item(s)")
        if low_context or low_symbols:
            reasons.append(f"{len(low_context) + len(low_symbols)} low-confidence/noisy signal(s) kept outside checklist")
        if unknown_buckets:
            reasons.append(f"unknowns collapsed into {len(unknown_buckets)} bucket(s)")
        if residual_memos:
            reasons.append(f"{len(residual_memos)} residual dogfood memo source(s) excluded/demoted")
        attachable = "yes"
        if actionable_total_count < 3 or len(unknown_buckets) > 5:
            attachable = "no"
        elif low_context or low_symbols or residual_memos or unknown_buckets:
            attachable = "maybe"
        return {"attachable": attachable, "reasons": reasons}
