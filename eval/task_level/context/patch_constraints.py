from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from eval.task_level.context.action_checklist import build_action_checklist
from eval.task_level.schemas import TaskSpec

ConstraintType = Literal[
    "architecture",
    "forbidden_edit",
    "dependency_version",
    "source_of_truth",
    "generated_file",
    "verification",
]
Severity = Literal["must", "should", "info"]
Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class PatchConstraint:
    id: str
    type: ConstraintType
    instruction: str
    source: str
    severity: Severity
    confidence: Confidence
    symbols: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchConstraintPacket:
    task_id: str
    constraints: list[PatchConstraint]
    suggested_checks: list[str]
    warnings: list[str]
    source_summary: list[dict[str, Any]]
    token_estimate: int | None

    def to_json(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "constraints": [constraint.to_json() for constraint in self.constraints],
            "suggested_checks": self.suggested_checks,
            "warnings": self.warnings,
            "source_summary": self.source_summary,
            "token_estimate": self.token_estimate,
        }


def build_patch_constraint_packet(
    *,
    task: TaskSpec,
    workspace: Path,
    docatlas_response: dict[str, Any] | None = None,
    max_constraints: int = 12,
    max_sources: int = 8,
    max_tokens: int = 1200,
) -> PatchConstraintPacket:
    visible_files = _read_visible_files(workspace)
    context_text = _combined_text(task.issue_text, docatlas_response, visible_files)
    constraints: list[PatchConstraint] = []

    def add(constraint: PatchConstraint) -> None:
        key = (constraint.id, constraint.instruction, constraint.source)
        if key not in {(c.id, c.instruction, c.source) for c in constraints}:
            constraints.append(constraint)

    if _mentions_generated_rule(context_text, visible_files):
        source = _first_existing(visible_files, ("docs/generated-files.md", "docs/generated-source.md", "README.md")) or "visible project docs"
        add(PatchConstraint(
            id="generated-files",
            type="generated_file",
            instruction="Do not hand-edit generated files such as `*.g.dart`, `*.freezed.dart`, or generated Riverpod/provider outputs; edit the source model/policy file instead.",
            source=source,
            severity="must",
            confidence="high",
            symbols=["*.g.dart", "*.freezed.dart", "generated"],
            files=[source],
        ))

    owner_file = _architecture_owner_file(visible_files)
    if owner_file:
        add(PatchConstraint(
            id="architecture-owner",
            type="architecture",
            instruction="Keep permission/business policy in the documented service/domain layer; UI/provider layers should delegate rather than own behavior.",
            source=owner_file,
            severity="must",
            confidence="high",
            symbols=["PermissionService", "provider", "service"],
            files=[owner_file],
        ))
        add(PatchConstraint(
            id="source-of-truth-service",
            type="source_of_truth",
            instruction="Treat the documented service/source layer as the source of truth for behavior changes before editing presentation adapters.",
            source=owner_file,
            severity="must",
            confidence="high",
            symbols=["PermissionService"],
            files=[owner_file],
        ))

    for dependency in task.dependencies:
        if dependency.name and dependency.version:
            add(PatchConstraint(
                id=f"dependency-{dependency.name}",
                type="dependency_version",
                instruction=f"Use the repository-pinned `{dependency.name}` version `{dependency.version}` contract; do not assume latest API behavior.",
                source=_dependency_source(visible_files, dependency.name) or "task manifest dependency metadata",
                severity="must",
                confidence="high",
                symbols=[dependency.name, dependency.version],
                files=[f for f in ("pyproject.toml", "requirements.txt", "pubspec.lock", "pubspec.yaml") if f in visible_files],
            ))

    if "permission_handler" in context_text and "pubspec.lock" in visible_files:
        version = _extract_pubspec_lock_version(visible_files["pubspec.lock"], "permission_handler")
        if version:
            add(PatchConstraint(
                id="dependency-permission_handler",
                type="dependency_version",
                instruction=f"Use pinned `permission_handler` `{version}` behavior; do not substitute unrelated newer media/storage APIs.",
                source="pubspec.lock",
                severity="must",
                confidence="high",
                symbols=["permission_handler", version, "Permission.notification"],
                files=["pubspec.lock"],
            ))

    if _mentions_duplicate_policy(context_text):
        add(PatchConstraint(
            id="do-not-duplicate-policy",
            type="forbidden_edit",
            instruction="Do not add a second policy map or flow-specific duplicate of the shared permission/business policy; update the shared policy/source of truth instead.",
            source=_first_existing(visible_files, ("docs/permission-architecture.md", "docs/browser-flow.md", "docs/scan-flow.md", "README.md")) or "visible issue/project docs",
            severity="must",
            confidence="medium",
            symbols=["policy", "PermissionService", "duplicate"],
            files=[f for f in ("docs/permission-architecture.md", "docs/browser-flow.md", "docs/scan-flow.md") if f in visible_files],
        ))

    for item in build_action_checklist(task_id=task.task_id, issue_text=task.issue_text, docatlas_response=docatlas_response or {}, workspace=workspace):
        if item.source == "issue" and not item.symbols:
            continue
        add(PatchConstraint(
            id=f"checklist-{_slug(item.text)[:48]}",
            type="verification" if "run" in item.text.lower() or "verify" in item.text.lower() else "source_of_truth",
            instruction=item.text,
            source=item.source,
            severity="should" if item.confidence != "high" else "must",
            confidence=item.confidence,
            symbols=item.symbols,
            files=item.files,
        ))

    suggested_checks = _suggested_checks(task)
    source_summary = _source_summary(visible_files, docatlas_response)[:max_sources]
    warnings: list[str] = []
    if docatlas_response and docatlas_response.get("reason_code") == "docatlas_context_timeout_fallback":
        warnings.append("DocAtlas retrieval used visible local project-doc fallback; vector retrieval success is not implied.")

    constraints = constraints[:max_constraints]
    packet = PatchConstraintPacket(
        task_id=task.task_id,
        constraints=constraints,
        suggested_checks=suggested_checks,
        warnings=warnings,
        source_summary=source_summary,
        token_estimate=None,
    )
    estimated = estimate_packet_tokens(packet)
    if estimated > max_tokens and constraints:
        constraints = constraints[: max(1, int(len(constraints) * max_tokens / estimated))]
    packet = PatchConstraintPacket(
        task_id=task.task_id,
        constraints=constraints,
        suggested_checks=suggested_checks,
        warnings=warnings,
        source_summary=source_summary,
        token_estimate=estimate_packet_tokens(PatchConstraintPacket(task.task_id, constraints, suggested_checks, warnings, source_summary, None)),
    )
    return packet


def format_patch_constraint_packet(packet: PatchConstraintPacket) -> str:
    must = [c for c in packet.constraints if c.severity == "must"]
    forbidden = [c for c in packet.constraints if c.type in {"forbidden_edit", "generated_file"}]
    dependencies = [c for c in packet.constraints if c.type == "dependency_version"]
    lines = [
        "## DocAtlas patch constraints",
        "",
        "These constraints were derived from visible project docs/source/lockfiles.",
        "They may be incomplete, but they are source-attributed.",
        "",
        "Must obey:",
    ]
    lines.extend(_constraint_lines(must) or ["- No must constraints were derived."])
    lines.extend(["", "Forbidden edits:"])
    lines.extend(_constraint_lines(forbidden) or ["- No forbidden-edit constraints were derived."])
    lines.extend(["", "Dependency/version contracts:"])
    lines.extend(_constraint_lines(dependencies) or ["- No dependency/version contracts were derived."])
    lines.extend(["", "Suggested checks:"])
    lines.extend([f"- {check}" for check in packet.suggested_checks] or ["- Run the relevant public tests."])
    lines.extend(["", "Sources:"])
    for source in packet.source_summary:
        lines.append(f"- {source.get('path') or source.get('title') or 'unknown'} ({source.get('kind', 'source')})")
    if packet.warnings:
        lines.extend(["", "Warnings:", *[f"- {warning}" for warning in packet.warnings]])
    return "\n".join(lines)


def save_patch_constraint_packet(packet: PatchConstraintPacket, output_dir: Path) -> None:
    output_dir.joinpath("patch_constraints.json").write_text(json.dumps(packet.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    output_dir.joinpath("patch_constraints.md").write_text(format_patch_constraint_packet(packet), encoding="utf-8")


def estimate_packet_tokens(packet: PatchConstraintPacket) -> int:
    return max(1, len(json.dumps(packet.to_json(), ensure_ascii=False, sort_keys=True)) // 4)


def packet_from_json(data: dict[str, Any]) -> PatchConstraintPacket:
    return PatchConstraintPacket(
        task_id=str(data.get("task_id", "")),
        constraints=[PatchConstraint(**item) for item in data.get("constraints", []) if isinstance(item, dict)],
        suggested_checks=[str(item) for item in data.get("suggested_checks", [])],
        warnings=[str(item) for item in data.get("warnings", [])],
        source_summary=[item for item in data.get("source_summary", []) if isinstance(item, dict)],
        token_estimate=data.get("token_estimate"),
    )


def _constraint_lines(constraints: list[PatchConstraint]) -> list[str]:
    return [f"- {c.instruction} (source: `{c.source}`; id: `{c.id}`; confidence: {c.confidence})" for c in constraints]


def _combined_text(issue_text: str, docatlas_response: dict[str, Any] | None, visible_files: dict[str, str]) -> str:
    parts = [issue_text]
    if docatlas_response:
        parts.append(json.dumps(docatlas_response, ensure_ascii=False, sort_keys=True))
    parts.extend(visible_files.values())
    return "\n".join(parts)


def _read_visible_files(workspace: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for pattern in ("README.md", "docs/*.md", "src/**/*.py", "tests/*.py", "lib/**/*.dart", "pyproject.toml", "requirements.txt", "pubspec.yaml", "pubspec.lock"):
        for path in workspace.glob(pattern):
            if path.is_file() and "hidden" not in path.parts:
                try:
                    files[path.relative_to(workspace).as_posix()] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
    return files


def _mentions_generated_rule(context_text: str, visible_files: dict[str, str]) -> bool:
    haystack = context_text.lower()
    return any(token in haystack for token in ("generated", ".g.dart", ".freezed.dart", "must not be edited by hand")) or any(path in visible_files for path in ("docs/generated-files.md", "docs/generated-source.md"))


def _architecture_owner_file(visible_files: dict[str, str]) -> str | None:
    for path, content in visible_files.items():
        lower = content.lower()
        if ("architecture" in path.lower() or "architecture" in lower) and ("service" in lower or "source of truth" in lower):
            return path
    for path, content in visible_files.items():
        if "PermissionService" in content:
            return path
    return None


def _dependency_source(visible_files: dict[str, str], dependency_name: str) -> str | None:
    for path in ("pubspec.lock", "requirements.txt", "pyproject.toml", "pubspec.yaml"):
        if dependency_name in visible_files.get(path, ""):
            return path
    return None


def _extract_pubspec_lock_version(lock_text: str, package: str) -> str | None:
    lines = lock_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == f"{package}:":
            for follow in lines[index : index + 8]:
                if "version:" in follow:
                    return follow.split("version:", 1)[1].strip().strip('"')
    return None


def _mentions_duplicate_policy(context_text: str) -> bool:
    lower = context_text.lower()
    return "duplicate" in lower or "same shared" in lower or "shared permission contract" in lower or "source of truth" in lower


def _suggested_checks(task: TaskSpec) -> list[str]:
    checks = [task.test_command] if task.test_command else []
    checks.append("Inspect changed files against generated-file and source-of-truth constraints before accepting the patch.")
    return checks


def _source_summary(visible_files: dict[str, str], docatlas_response: dict[str, Any] | None) -> list[dict[str, Any]]:
    sources = [{"path": path, "kind": "visible_file"} for path in sorted(visible_files)]
    if docatlas_response:
        trust = docatlas_response.get("trust_contract", {}) if isinstance(docatlas_response.get("trust_contract"), dict) else {}
        selected = trust.get("selected") or trust.get("selected_sources") or []
        for item in selected:
            if isinstance(item, dict):
                source = item.get("source") if isinstance(item.get("source"), dict) else item
                sources.append({"path": source.get("path") or source.get("title"), "kind": source.get("kind") or "docatlas_selected"})
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for source in sources:
        key = (source.get("path"), source.get("kind"))
        if key not in seen:
            seen.add(key)
            deduped.append(source)
    return deduped


def _first_existing(visible_files: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    return next((candidate for candidate in candidates if candidate in visible_files), None)


def _slug(text: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())
