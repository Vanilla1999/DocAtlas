from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.task_level.artifact_hygiene import apply_patch_hygiene, is_runtime_artifact, parse_status_paths

from docmancer.docs.service import LibraryDocsService


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
        self._write_json(out / "constraints.json", constraints_dict)
        (out / "constraints.md").write_text(self._constraints_markdown(constraints_dict), encoding="utf-8")
        self._write_json(out / "changed_files.json", changed)
        self._write_json(out / "untracked_files.json", untracked_files)
        self._write_json(out / "ignored_runtime_artifacts.json", ignored_runtime_artifacts)
        self._write_json(out / "patch_hygiene.json", hygiene.to_json_dict())
        (out / "patch.diff").write_text(patch_diff, encoding="utf-8")
        self._write_json(out / "validation.json", validation_dict)
        summary = self._review_summary(task, changed, constraints_dict, validation_dict, warnings=warnings, untracked_files=untracked_files, ignored_runtime_artifacts=ignored_runtime_artifacts)
        (out / "review_summary.md").write_text(summary, encoding="utf-8")
        return {
            "output_dir": str(out),
            "changed_files": changed,
            "untracked_files": untracked_files,
            "ignored_runtime_artifacts": ignored_runtime_artifacts,
            "warnings": warnings,
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
    ) -> str:
        warnings = warnings or []
        untracked_files = untracked_files or []
        ignored_runtime_artifacts = ignored_runtime_artifacts or []
        violations = [result for result in validation.get("results", []) if result.get("status") == "violated"]
        unknowns = [result for result in validation.get("results", []) if result.get("status") == "unknown"]
        generated_or_lock = [
            result for result in validation.get("results", [])
            if "generated" in str(result.get("reason", "")).lower() or "lockfile" in str(result.get("reason", "")).lower()
        ]
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
            "## Top constraints",
        ]
        for constraint in constraints.get("constraints", [])[:6]:
            lines.append(f"- {constraint.get('instruction')} (source: `{constraint.get('source')}`)")
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
        lines.extend(["", "## Unknown/manual review"])
        lines.extend([f"- {item.get('constraint_id')}: {item.get('reason')}" for item in unknowns[:8]] or ["- none"])
        lines.extend(["", "## Generated/lockfile checks"])
        lines.extend([f"- {item.get('constraint_id')}: {item.get('status')} — {item.get('reason')}" for item in generated_or_lock] or ["- none"])
        if untracked_files:
            lines.extend(["", "## Untracked files"])
            lines.extend(f"- {path}" for path in untracked_files)
        if ignored_runtime_artifacts:
            lines.extend(["", "## Ignored runtime/cache artifacts"])
            lines.extend(f"- {path}" for path in ignored_runtime_artifacts[:20])
        if constraints.get("symbol_candidates"):
            lines.extend(["", "## Source-of-truth / symbol notes"])
            for candidate in constraints["symbol_candidates"][:8]:
                lines.append(f"- `{candidate.get('term')}` -> `{candidate.get('matched_symbol')}` (`{candidate.get('source')}`)")
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
