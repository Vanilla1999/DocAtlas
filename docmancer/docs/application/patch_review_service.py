from __future__ import annotations

import json
import re
import subprocess
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
    "StatelessWidget", "StatefulWidget",
}
DOGFOOD_MEMO_REASONS = {"dogfood_result_memo", "dogfood_task_artifact"}
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
        self._write_json(out / "constraints.json", constraints_dict)
        (out / "constraints.md").write_text(self._constraints_markdown(constraints_dict), encoding="utf-8")
        self._write_json(out / "changed_files.json", changed)
        self._write_json(out / "untracked_files.json", untracked_files)
        self._write_json(out / "ignored_runtime_artifacts.json", ignored_runtime_artifacts)
        self._write_json(out / "patch_hygiene.json", hygiene.to_json_dict())
        (out / "patch.diff").write_text(patch_diff, encoding="utf-8")
        self._write_json(out / "validation.json", validation_dict)
        self._write_json(out / "review_summary_actions.json", actions_payload)
        self._write_json(out / "review_summary_quality.json", quality_payload)
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
        return {
            "output_dir": str(out),
            "changed_files": changed,
            "untracked_files": untracked_files,
            "ignored_runtime_artifacts": ignored_runtime_artifacts,
            "warnings": warnings,
            "summary_max_items": summary_max_items,
            "summary_mode": summary_mode,
            "review_summary_actions": actions_payload,
            "review_summary_quality": quality_payload,
            "constraints": constraints_dict,
            "validation": validation_dict,
            "artifacts": [
                "constraints.json",
                "constraints.md",
                "changed_files.json",
                "untracked_files.json",
                "ignored_runtime_artifacts.json",
                "patch_hygiene.json",
                "patch.diff",
                "validation.json",
                "review_summary_actions.json",
                "review_summary_quality.json",
                "review_summary.md",
            ],
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
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

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
        summary_mode = summary_mode.lower()
        if summary_mode not in {"compact", "standard", "verbose"}:
            raise ValueError(f"unsupported summary_mode: {summary_mode}")
        constraint_items = list(constraints.get("constraints", []))
        results = list(validation.get("results", []))
        violations = [result for result in results if result.get("status") == "violated"]
        unknowns = [result for result in results if result.get("status") == "unknown"]
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
        actionable = PatchReviewService._dedupe_constraints([*violation_constraints, *actionable_candidates])[:summary_max_items]
        manual_limit = 12 if summary_mode == "verbose" else 6
        low_limit = 12 if summary_mode == "verbose" else 6
        manual_context = [item for item in ranked_constraints if PatchReviewService._summary_bucket(item, changed_files, task) == "manual"][:manual_limit]
        low_context = [item for item in ranked_constraints if PatchReviewService._summary_bucket(item, changed_files, task) == "low"][:low_limit]
        symbol_candidates = list(constraints.get("symbol_candidates") or [])
        low_symbols = [item for item in symbol_candidates if PatchReviewService._is_low_value_symbol_candidate(item, task)]
        unknown_buckets = PatchReviewService._unknown_buckets(unknowns, constraint_items)
        excluded_sources = list(constraints.get("excluded_source_reasons") or [])
        residual_memos = [item for item in excluded_sources if item.get("reason") in DOGFOOD_MEMO_REASONS]
        quality = PatchReviewService._summary_quality(
            actionable=actionable,
            low_context=low_context,
            low_symbols=low_symbols,
            unknown_buckets=unknown_buckets,
            residual_memos=residual_memos,
        )
        return {
            "schema_version": 1,
            "attachable": quality["attachable"],
            "summary_mode": summary_mode,
            "actionable_items_limit": summary_max_items,
            "actionable_items_count": len(actionable),
            "low_value_top_items_count": len(low_context) + len(low_symbols),
            "unknown_bucket_count": len(unknown_buckets),
            "residual_memo_source_count": len(residual_memos),
            "satisfied_count": validation.get("satisfied", 0),
            "violated_count": validation.get("violated", 0),
            "unknown_count": validation.get("unknown", 0),
            "reasons": quality["reasons"],
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
    def _review_summary_actions_payload(
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
        results_by_id = {str(item.get("constraint_id") or ""): item for item in results}
        violations = [result for result in results if result.get("status") == "violated"]
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
        actionable = PatchReviewService._dedupe_constraints([*violation_constraints, *actionable_candidates])[:summary_max_items]
        return {
            "schema_version": 1,
            "summary_mode": summary_mode,
            "actionable_items_limit": summary_max_items,
            "actionable_items": [
                PatchReviewService._actionable_item_payload(item, results_by_id.get(str(item.get("id") or "")))
                for item in actionable
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
    def _actionable_item_payload(item: dict[str, Any], result: dict[str, Any] | None) -> dict[str, Any]:
        payload = {
            "constraint_id": item.get("id"),
            "instruction": item.get("instruction"),
            "source": item.get("source"),
            "type": item.get("type"),
            "confidence": item.get("confidence"),
        }
        if result:
            payload["validation_status"] = result.get("status")
            payload["validation_reason"] = result.get("reason")
            payload["files"] = result.get("files", [])
        return payload

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
        summary_mode = summary_mode.lower()
        if summary_mode not in {"compact", "standard", "verbose"}:
            raise ValueError(f"unsupported summary_mode: {summary_mode}")
        warnings = warnings or []
        untracked_files = untracked_files or []
        ignored_runtime_artifacts = ignored_runtime_artifacts or []
        constraint_items = list(constraints.get("constraints", []))
        results = list(validation.get("results", []))
        violations = [result for result in results if result.get("status") == "violated"]
        unknowns = [result for result in results if result.get("status") == "unknown"]
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
        actionable = PatchReviewService._dedupe_constraints([*violation_constraints, *actionable_candidates])[:summary_max_items]
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
        excluded_sources = list(constraints.get("excluded_source_reasons") or [])
        residual_memos = [item for item in excluded_sources if item.get("reason") in DOGFOOD_MEMO_REASONS]
        quality = PatchReviewService._summary_quality(
            actionable=actionable,
            low_context=low_context,
            low_symbols=low_symbols,
            unknown_buckets=unknown_buckets,
            residual_memos=residual_memos,
        )

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
            f"- unknown/manual review: {validation.get('unknown', 0)}",
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
        term = str(item.get("term") or "")
        task_lower = task.lower()
        if symbol in LOW_VALUE_SYMBOLS or symbol.lower() in {value.lower() for value in LOW_VALUE_SYMBOLS}:
            explicit = symbol.lower() in task_lower or term.lower() in task_lower
            return not explicit
        evidence = str(item.get("evidence") or "").strip()
        if evidence.startswith(("import ", "export ", "part ")):
            return True
        return False

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
    def _summary_quality(
        *,
        actionable: list[dict[str, Any]],
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
        if len(actionable) < 3 or len(unknown_buckets) > 5:
            attachable = "no"
        elif low_context or low_symbols or residual_memos or unknown_buckets:
            attachable = "maybe"
        return {"attachable": attachable, "reasons": reasons}
