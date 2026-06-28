from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from eval.task_level.context.patch_constraints import PatchConstraint, PatchConstraintPacket

LOCKFILES = {"pubspec.lock", "poetry.lock", "uv.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
GENERATED_SUFFIXES = (".g.dart", ".freezed.dart")
PROVIDER_HINTS = ("provider", "ui", "presentation", "widget")
SERVICE_HINTS = ("service", "domain", "application")


def validate_patch_against_constraints(
    *,
    packet: PatchConstraintPacket,
    changed_files: list[str],
    diff_text: str = "",
    checks_run: list[str] | None = None,
) -> dict[str, Any]:
    checks_run = checks_run or []
    violations: list[dict[str, Any]] = []
    satisfied = 0
    unknown = 0

    for constraint in packet.constraints:
        result, reason, files = _evaluate_constraint(constraint, changed_files, diff_text, checks_run)
        if result == "violated":
            violations.append({"constraint_id": constraint.id, "reason": reason, "files": files})
        elif result == "satisfied":
            satisfied += 1
        else:
            unknown += 1

    return {
        "constraint_validation": {
            "total_constraints": len(packet.constraints),
            "satisfied": satisfied,
            "violated": len(violations),
            "unknown": unknown,
            "violations": violations,
        }
    }


def _evaluate_constraint(constraint: PatchConstraint, changed_files: list[str], diff_text: str, checks_run: list[str]) -> tuple[str, str, list[str]]:
    touched = [file for file in changed_files if _matches_any(file, constraint.files)]
    generated_touched = [file for file in changed_files if file.endswith(GENERATED_SUFFIXES)]
    lockfile_touched = [file for file in changed_files if Path(file).name in LOCKFILES]
    instruction = constraint.instruction.lower()

    if constraint.type == "generated_file" or "generated" in instruction:
        if generated_touched:
            return "violated", "generated files were edited", generated_touched
        return "satisfied", "no generated files were edited", []

    if constraint.type == "dependency_version":
        if lockfile_touched:
            return "violated", "lockfile changed under a pinned dependency/version contract", lockfile_touched
        return "satisfied", "pinned dependency contract preserved", []

    if constraint.type == "forbidden_edit":
        forbidden = touched or _provider_policy_files(changed_files, instruction)
        if forbidden:
            return "violated", "forbidden file/layer was edited", forbidden
        if "duplicate" in instruction and _adds_duplicate_policy(diff_text):
            return "violated", "diff appears to add a duplicate policy map", []
        return "unknown", "forbidden edit constraint is not deterministically provable from changed files", []

    if constraint.type in {"source_of_truth", "architecture"}:
        if touched or _service_files(changed_files):
            return "satisfied", "source-of-truth/service layer was touched", touched or _service_files(changed_files)
        provider_files = _provider_policy_files(changed_files, instruction)
        if provider_files and ("service" in instruction or "source of truth" in instruction):
            return "violated", "provider/UI layer changed while policy says service/source-of-truth owns behavior", provider_files
        return "unknown", "source-of-truth edit could not be determined", []

    if constraint.type == "verification":
        if any(check and any(check in run or run in check for run in checks_run) for check in constraint.symbols + [constraint.instruction]):
            return "satisfied", "suggested check appears to have run", []
        return "unknown", "suggested check not observed", []

    return "unknown", "constraint type not deterministically evaluated", []


def _matches_any(path: str, candidates: list[str]) -> bool:
    return any(candidate and (path == candidate or path.endswith(candidate) or candidate.endswith(path)) for candidate in candidates)


def _provider_policy_files(changed_files: list[str], instruction: str) -> list[str]:
    if not any(word in instruction for word in ("provider", "ui", "presentation", "service", "source of truth")):
        return []
    return [file for file in changed_files if any(hint in file.lower() for hint in PROVIDER_HINTS)]


def _service_files(changed_files: list[str]) -> list[str]:
    return [file for file in changed_files if any(hint in file.lower() for hint in SERVICE_HINTS)]


def _adds_duplicate_policy(diff_text: str) -> bool:
    added = "\n".join(line[1:] for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
    return bool(re.search(r"(policy|permission).*(map|table)|Map<|const\s+.*Policy", added, flags=re.IGNORECASE))
