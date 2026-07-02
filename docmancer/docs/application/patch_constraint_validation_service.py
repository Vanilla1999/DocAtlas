from __future__ import annotations

import fnmatch
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from docmancer.docs.models import (
    PatchConstraint,
    PatchConstraintPacket,
    PatchConstraintValidationPacket,
    PatchConstraintValidationResult,
)

GENERATED_PATTERNS = (
    "*.g.dart",
    "*.freezed.dart",
    "*.pb.go",
    "*.pb.dart",
    "*.generated.*",
    "generated/*",
    "dist/*",
)
LOCKFILES = {
    "pubspec.lock",
    "poetry.lock",
    "uv.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "go.sum",
}
PROVIDER_PATH_PARTS = ("provider", "presentation", "ui", "component", "view")
SOURCE_OF_TRUTH_PATH_PARTS = ("service", "domain", "application", "repository", "adapter")
POLICY_KEYWORDS = (
    "switch",
    "map",
    "permission",
    "policy",
    "status",
    "authorization",
    "role",
    "admin",
    "canproceed",
    "isallowed",
)
POLICY_DECISION_KEYWORDS = (
    "permission",
    "policy",
    "status",
    "authorization",
    "role",
    "admin",
    "canproceed",
    "isallowed",
    "access",
    "allowed",
    "denied",
    "entitlement",
)
SAFE_UI_WIRING_PATTERNS = (
    r"\bcloseMenu\s*\(",
    r"\bcontext\.push\s*\(",
    r"\bcontext\.go\s*\(",
    r"\bNavigator\.",
    r"\bref\.read\([^\n]+\.notifier\)\.[A-Za-z_][A-Za-z0-9_]*\s*\(",
    r"\b[a-zA-Z_][A-Za-z0-9_]*(Notifier|Controller)\.[A-Za-z_][A-Za-z0-9_]*\s*\(",
)


class PatchConstraintValidationService:
    """Deterministic best-effort validator for patch constraints.

    This service does not call an LLM, web, retrieval, or git. It only compares
    caller-supplied constraints with caller-supplied changed_files / patch_diff.
    """

    def validate_patch_against_constraints(
        self,
        constraints: PatchConstraintPacket | list[PatchConstraint] | dict[str, Any] | list[dict[str, Any]],
        *,
        project_path: str | None = None,
        changed_files: list[str] | None = None,
        patch_diff: str | None = None,
        strict: bool = False,
    ) -> PatchConstraintValidationPacket:
        task, normalized = self._normalize_constraints(constraints)
        files = self._normalize_changed_files(changed_files, patch_diff)
        warnings: list[str] = []
        if not files and not patch_diff:
            warnings.append("Validation is limited: provide changed_files or patch_diff for deterministic checks.")

        results = [self._validate_constraint(constraint, files, patch_diff, task) for constraint in normalized]
        satisfied = sum(1 for result in results if result.status == "satisfied")
        violated = sum(1 for result in results if result.status == "violated")
        unknown = sum(1 for result in results if result.status == "unknown")
        if strict and unknown:
            warnings.append("strict mode: unresolved unknown constraints require manual review")

        confidence = self._packet_confidence(total=len(normalized), satisfied=satisfied, violated=violated, unknown=unknown)
        return PatchConstraintValidationPacket(
            task=task,
            project_path=project_path,
            total_constraints=len(normalized),
            satisfied=satisfied,
            violated=violated,
            unknown=unknown,
            results=results,
            warnings=warnings,
            confidence=confidence,
        )

    def _validate_constraint(self, constraint: PatchConstraint, changed_files: list[str], patch_diff: str | None, task: str | None = None) -> PatchConstraintValidationResult:
        text = self._constraint_text(constraint)
        generated_matches = self._changed_generated_files(changed_files)
        if self._is_generated_constraint(constraint, text):
            if generated_matches:
                return self._result(constraint, "violated", "generated file edit detected", generated_matches, evidence=constraint.evidence)
            if changed_files:
                return self._result(constraint, "satisfied", "no generated files changed", [], evidence=constraint.evidence)
            return self._result(constraint, "unknown", "changed files unavailable for generated-file constraint", [], evidence=constraint.evidence)

        lockfile_matches = self._changed_lockfiles(changed_files)
        if self._is_lockfile_constraint(constraint, text):
            if lockfile_matches:
                if self._lockfile_change_allowed(text, task):
                    return self._result(
                        constraint,
                        "unknown",
                        "lockfile changed under explicit dependency-upgrade allowance; review dependency intent manually",
                        lockfile_matches,
                        evidence=constraint.evidence,
                    )
                return self._result(constraint, "violated", "lockfile edit detected", lockfile_matches, evidence=constraint.evidence)
            if changed_files:
                return self._result(constraint, "satisfied", "no lockfiles changed", [], evidence=constraint.evidence)
            return self._result(constraint, "unknown", "changed files unavailable for lockfile constraint", [], evidence=constraint.evidence)

        provider_matches = [file for file in changed_files if self._is_provider_or_ui_path(file)]
        if self._is_provider_policy_constraint(text):
            if provider_matches and self._diff_adds_policy_logic(patch_diff):
                return self._result(constraint, "violated", "provider/UI file adds policy-like logic forbidden by constraint", provider_matches, evidence=self._policy_diff_evidence(patch_diff))
            if provider_matches and not patch_diff:
                return self._result(constraint, "unknown", "provider/UI file changed but diff unavailable", provider_matches, evidence=constraint.evidence)
            if changed_files:
                return self._result(constraint, "satisfied", "no provider/UI policy edit detected", [], evidence=constraint.evidence)
            return self._result(constraint, "unknown", "changed files unavailable for provider/UI policy constraint", [], evidence=constraint.evidence)

        if constraint.type == "source_of_truth" or "source of truth" in text or "belongs in" in text or "owns" in text:
            source_matches = [file for file in changed_files if self._is_source_of_truth_path(file)]
            provider_matches = [file for file in changed_files if self._is_provider_or_ui_path(file)]
            if source_matches:
                return self._result(constraint, "satisfied", "source-of-truth layer file changed", source_matches, evidence=constraint.evidence)
            if provider_matches and self._diff_adds_policy_logic(patch_diff):
                return self._result(constraint, "violated", "policy-like logic changed outside source-of-truth layer", provider_matches, evidence=self._policy_diff_evidence(patch_diff))
            if provider_matches and not patch_diff:
                return self._result(constraint, "unknown", "provider/UI file changed but diff unavailable", provider_matches, evidence=constraint.evidence)
            return self._result(constraint, "unknown", "source-of-truth constraint is not deterministic for this patch", [], evidence=constraint.evidence)

        if constraint.type == "verification":
            return self._result(constraint, "unknown", "verification constraint requires explicit test evidence", [], evidence=constraint.evidence)

        if changed_files:
            return self._result(constraint, "unknown", "constraint not deterministically checkable from changed files", [], evidence=constraint.evidence)
        return self._result(constraint, "unknown", "changed files or diff unavailable", [], evidence=constraint.evidence)

    def _normalize_constraints(self, constraints: PatchConstraintPacket | list[PatchConstraint] | dict[str, Any] | list[dict[str, Any]]) -> tuple[str | None, list[PatchConstraint]]:
        task: str | None = None
        raw_constraints: Any
        if isinstance(constraints, PatchConstraintPacket):
            task = constraints.task
            raw_constraints = constraints.constraints
        elif isinstance(constraints, dict):
            task = constraints.get("task")
            raw_constraints = constraints.get("constraints") or []
        else:
            raw_constraints = constraints

        normalized: list[PatchConstraint] = []
        for index, raw in enumerate(raw_constraints or []):
            if isinstance(raw, PatchConstraint):
                normalized.append(raw)
            elif isinstance(raw, dict):
                normalized.append(self._constraint_from_dict(raw, index))
        return task, normalized

    @staticmethod
    def _constraint_from_dict(raw: dict[str, Any], index: int) -> PatchConstraint:
        return PatchConstraint(
            id=str(raw.get("id") or f"constraint-{index + 1}"),
            type=str(raw.get("type") or "unknown"),
            instruction=str(raw.get("instruction") or ""),
            source=str(raw.get("source") or ""),
            severity=str(raw.get("severity") or "info"),
            confidence=str(raw.get("confidence") or "low"),
            evidence=str(raw.get("evidence") or ""),
            symbols=list(raw.get("symbols") or []),
            files=list(raw.get("files") or []),
            source_refs=list(raw.get("source_refs") or []),
            evidence_snippets=list(raw.get("evidence_snippets") or []),
        )

    def _normalize_changed_files(self, changed_files: list[str] | None, patch_diff: str | None) -> list[str]:
        files = list(changed_files or [])
        files.extend(self._files_from_diff(patch_diff))
        deduped: list[str] = []
        seen: set[str] = set()
        for file in files:
            normalized = file.strip().replace("\\", "/")
            if normalized.startswith("a/") or normalized.startswith("b/"):
                normalized = normalized[2:]
            if normalized and normalized not in seen:
                deduped.append(normalized)
                seen.add(normalized)
        return deduped

    @staticmethod
    def _files_from_diff(patch_diff: str | None) -> list[str]:
        if not patch_diff:
            return []
        files: list[str] = []
        for line in patch_diff.splitlines():
            if line.startswith("+++ b/"):
                files.append(line.removeprefix("+++ b/"))
            elif line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    files.append(parts[3].removeprefix("b/"))
        return files

    @staticmethod
    def _constraint_text(constraint: PatchConstraint) -> str:
        return " ".join([constraint.type, constraint.instruction, constraint.source, constraint.evidence, " ".join(constraint.files), " ".join(constraint.symbols)]).lower()

    @staticmethod
    def _is_generated_path(path: str) -> bool:
        normalized = path.replace("\\", "/")
        name = Path(normalized).name
        return any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(normalized, pattern) or f"/{pattern.rstrip('/*')}/" in f"/{normalized}/" for pattern in GENERATED_PATTERNS)

    def _changed_generated_files(self, changed_files: list[str]) -> list[str]:
        return [file for file in changed_files if self._is_generated_path(file)]

    @staticmethod
    def _changed_lockfiles(changed_files: list[str]) -> list[str]:
        return [file for file in changed_files if Path(file).name in LOCKFILES]

    @staticmethod
    def _is_generated_constraint(constraint: PatchConstraint, text: str) -> bool:
        return constraint.type == "generated_file" or "generated" in text or "build_runner" in text or "regenerate" in text

    @staticmethod
    def _is_lockfile_constraint(constraint: PatchConstraint, text: str) -> bool:
        return "lockfile" in text or any(lock.lower() in text for lock in LOCKFILES) or (constraint.type == "dependency_version" and "do not change" in text)

    @staticmethod
    def _lockfile_change_allowed(text: str, task: str | None) -> bool:
        task_text = (task or "").lower()
        allows_dependency_upgrade = (
            "unless" in text
            or "explicitly" in text
            or "allow" in text
            or "requires dependency" in text
            or "dependency update" in text
            or "dependency upgrade" in text
        )
        task_is_dependency_change = (
            "upgrade" in task_text
            or "update dependency" in task_text
            or "dependency update" in task_text
            or "dependency upgrade" in task_text
            or "bump" in task_text
        ) and ("depend" in task_text or "package" in task_text or "lockfile" in task_text)
        return allows_dependency_upgrade and task_is_dependency_change

    @staticmethod
    def _is_provider_or_ui_path(path: str) -> bool:
        lowered = path.lower().replace("\\", "/")
        return any(part in lowered for part in PROVIDER_PATH_PARTS)

    @staticmethod
    def _is_source_of_truth_path(path: str) -> bool:
        lowered = path.lower().replace("\\", "/")
        return any(part in lowered for part in SOURCE_OF_TRUTH_PATH_PARTS)

    @staticmethod
    def _is_provider_policy_constraint(text: str) -> bool:
        return ("provider" in text or "ui" in text or "presentation" in text) and (
            "policy" in text or "duplicate" in text or "delegate" in text or "must not" in text or "should not" in text
        )

    @staticmethod
    def _diff_adds_policy_logic(patch_diff: str | None) -> bool:
        if not patch_diff:
            return False
        added = [line[1:].strip() for line in patch_diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
        policy_context = "\n".join(added).lower()
        for line in added:
            lowered = line.lower()
            if not lowered:
                continue
            if PatchConstraintValidationService._is_safe_ui_wiring_line(line):
                continue
            if PatchConstraintValidationService._line_adds_policy_decision(lowered, policy_context):
                return True
        return False

    @staticmethod
    def _is_safe_ui_wiring_line(line: str) -> bool:
        stripped = line.strip()
        lowered = stripped.lower()
        if PatchConstraintValidationService._line_has_decision_shape(lowered):
            return False
        if re.match(r"^(onPressed|onTap|onChanged)\s*:\s*(\(.*\)\s*)?(async\s*)?\{?\s*$", stripped):
            return True
        if stripped in {"},", "}", "{", "});", ");"}:
            return True
        return any(re.search(pattern, stripped) for pattern in SAFE_UI_WIRING_PATTERNS)

    @staticmethod
    def _line_has_decision_shape(lowered_line: str) -> bool:
        if re.search(r"\b(return|if|else\s+if|switch|case)\b", lowered_line):
            return True
        if "&&" in lowered_line or "||" in lowered_line:
            return True
        if re.search(r"(?<![=!<>])=(?!=|>)", lowered_line):
            return True
        if re.search(r"[?:]", lowered_line) and not re.match(r"^(onpressed|ontap|onchanged)\s*:", lowered_line):
            return True
        if re.search(r"(==|!=|>=|<=|>|<)", lowered_line):
            return True
        if any(keyword in lowered_line for keyword in POLICY_DECISION_KEYWORDS):
            return True
        return False

    @staticmethod
    def _line_adds_policy_decision(lowered_line: str, lowered_patch: str) -> bool:
        has_decision_keyword = any(keyword in lowered_line for keyword in POLICY_DECISION_KEYWORDS)
        patch_has_decision_keyword = any(keyword in lowered_patch for keyword in POLICY_DECISION_KEYWORDS)
        adds_branch = re.search(r"\b(if|switch)\s*\(", lowered_line) is not None
        adds_policy_map = ("map" in lowered_line or "{" in lowered_line or "[" in lowered_line) and patch_has_decision_keyword
        adds_assignment = re.search(r"\b(canproceed|isallowed|allowed|denied|status|role|permission|authorization)\b.*(=|=>|:)", lowered_line) is not None
        compares_policy_state = re.search(r"\b(user\.|role|status|permission|authorization|access)\b.*(==|!=|>|<|&&|\|\|)", lowered_line) is not None
        returns_policy_decision = lowered_line.startswith("return ") and has_decision_keyword
        return bool((adds_branch and patch_has_decision_keyword) or adds_policy_map or adds_assignment or compares_policy_state or returns_policy_decision or (has_decision_keyword and "policy" in lowered_line))

    @staticmethod
    def _policy_diff_evidence(patch_diff: str | None) -> str | None:
        if not patch_diff:
            return None
        lines = []
        lowered_patch = patch_diff.lower()
        for line in patch_diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                stripped = line[1:].strip()
                if PatchConstraintValidationService._line_adds_policy_decision(stripped.lower(), lowered_patch):
                    lines.append(line.strip())
        return "\n".join(lines[:3]) or None

    @staticmethod
    def _result(constraint: PatchConstraint, status: str, reason: str, files: list[str], *, evidence: str | None) -> PatchConstraintValidationResult:
        return PatchConstraintValidationResult(
            constraint_id=constraint.id,
            status=status,
            reason=reason,
            files=files,
            evidence=evidence,
        )

    @staticmethod
    def _packet_confidence(*, total: int, satisfied: int, violated: int, unknown: int) -> str:
        if total == 0:
            return "low"
        if unknown == 0:
            return "high"
        if satisfied or violated:
            return "medium"
        return "low"

    @staticmethod
    def to_dict(packet: PatchConstraintValidationPacket) -> dict[str, Any]:
        return asdict(packet)
