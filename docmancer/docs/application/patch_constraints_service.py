from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docmancer.docs.models import PatchConstraint, PatchConstraintPacket

DEFAULT_MAX_CONSTRAINTS = 12
DEFAULT_MAX_TOKENS = 1200
LOCKFILES = {"pubspec.lock", "poetry.lock", "uv.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Cargo.lock"}


class PatchConstraintsService:
    """Compile compact repository patch constraints from visible local project sources."""

    def __init__(self, facade: Any):
        self.facade = facade

    def get_patch_constraints(
        self,
        question: str,
        *,
        project_path: str | None = None,
        changed_files: list[str] | None = None,
        max_constraints: int = DEFAULT_MAX_CONSTRAINTS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        include_sources: bool = True,
    ) -> PatchConstraintPacket:
        max_constraints = max(1, int(max_constraints or DEFAULT_MAX_CONSTRAINTS))
        max_tokens = max(80, int(max_tokens or DEFAULT_MAX_TOKENS))
        changed_files = changed_files or []
        root = Path(project_path).expanduser().resolve() if project_path else None
        sources = self._visible_sources(root) if root else []
        constraints: list[PatchConstraint] = []
        constraints.extend(self._generated_file_constraints(sources))
        constraints.extend(self._source_of_truth_constraints(sources, changed_files))
        constraints.extend(self._dependency_constraints(root))
        constraints.extend(self._fallback_constraints(question, changed_files))
        constraints = self._dedupe(constraints)
        constraints = self._sort_constraints(constraints)
        selected, truncated = self._apply_budget(constraints, max_constraints=max_constraints, max_tokens=max_tokens)
        warnings: list[str] = []
        if truncated:
            warnings.append("Constraint packet was truncated to fit max_constraints/max_tokens; must/high-confidence constraints were kept first.")
        if not root:
            warnings.append("project_path was not provided; constraints are limited to task-level generic guidance.")
        if root and not sources:
            warnings.append("No visible project docs were found; constraints are limited to dependency metadata and generic checks.")
        token_estimate = self._estimate_packet_tokens(selected, warnings)
        confidence = self._packet_confidence(selected)
        return PatchConstraintPacket(
            task=question,
            constraints=selected,
            forbidden_edits=[c for c in selected if c.type in {"forbidden_edit", "generated_file"}],
            dependency_contracts=[c for c in selected if c.type == "dependency_version"],
            source_of_truth_rules=[c for c in selected if c.type == "source_of_truth"],
            suggested_checks=[c.instruction for c in selected if c.type == "verification"],
            warnings=warnings,
            sources=self._source_summary(sources, selected) if include_sources else [],
            token_estimate=token_estimate,
            confidence=confidence,
        )

    def _visible_sources(self, root: Path | None) -> list[dict[str, str]]:
        if not root or not root.exists():
            return []
        candidates: list[Path] = []
        try:
            metadata = self.facade.read_project_metadata(str(root))
            candidates.extend(root / item.path for item in metadata.docs_candidates)
        except Exception:
            candidates = []
        if not candidates:
            patterns = ["README*", "docs/**/*.md", "docs/**/*.txt", "**/ARCHITECTURE.md", "**/ADR*.md"]
            for pattern in patterns:
                candidates.extend(root.glob(pattern))
        out: list[dict[str, str]] = []
        seen: set[Path] = set()
        for path in candidates:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen or not resolved.is_file() or not self._under_root(resolved, root):
                continue
            if resolved.stat().st_size > 80_000:
                continue
            text = resolved.read_text(encoding="utf-8", errors="replace")
            rel = resolved.relative_to(root).as_posix()
            out.append({"path": rel, "text": text})
            seen.add(resolved)
        return out

    @staticmethod
    def _under_root(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _generated_file_constraints(self, sources: list[dict[str, str]]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for source in sources:
            text = source["text"]
            if re.search(r"generated|\.g\.dart|\.freezed\.dart", text, re.I):
                evidence = self._evidence(text, ["generated", ".g.dart", ".freezed.dart"])
                constraints.append(PatchConstraint(
                    id="generated-files-readonly",
                    type="generated_file",
                    instruction="Do not edit generated files such as `*.g.dart` or `*.freezed.dart` by hand.",
                    source=source["path"],
                    severity="must",
                    confidence="high",
                    evidence=evidence,
                    files=["*.g.dart", "*.freezed.dart"],
                ))
                break
        return constraints

    def _source_of_truth_constraints(self, sources: list[dict[str, str]], changed_files: list[str]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for source in sources:
            text = source["text"]
            lowered = text.lower()
            mentions_owner = "source-of-truth" in lowered or "source of truth" in lowered or "owned by" in lowered or "service" in lowered or "domain" in lowered or "application" in lowered
            if mentions_owner:
                symbol = self._first_symbol(text) or "documented service/domain/application layer"
                constraints.append(PatchConstraint(
                    id="source-of-truth-owner",
                    type="source_of_truth",
                    instruction=f"Keep behavior changes in the documented source-of-truth owner: {symbol}.",
                    source=source["path"],
                    severity="must",
                    confidence="high",
                    evidence=self._evidence(text, ["source-of-truth", "source of truth", "owned", "service", "domain", "application"]),
                    symbols=[symbol] if symbol else [],
                    files=[f for f in changed_files if any(part in f.lower() for part in ("service", "domain", "application"))],
                ))
                break
        for source in sources:
            text = source["text"]
            lowered = text.lower()
            if "provider" in lowered and ("delegate" in lowered or "do not duplicate" in lowered or "must not duplicate" in lowered):
                constraints.append(PatchConstraint(
                    id="provider-delegates-policy",
                    type="architecture",
                    instruction="Provider/UI layers should delegate policy to the service/domain/application owner; do not duplicate behavior policy there.",
                    source=source["path"],
                    severity="must",
                    confidence="high",
                    evidence=self._evidence(text, ["provider", "delegate", "duplicate policy"]),
                    files=[f for f in changed_files if any(part in f.lower() for part in ("provider", "presentation", "ui"))],
                ))
                constraints.append(PatchConstraint(
                    id="do-not-duplicate-policy",
                    type="forbidden_edit",
                    instruction="Do not add duplicate policy maps or parallel rule tables outside the documented owner.",
                    source=source["path"],
                    severity="must",
                    confidence="high",
                    evidence=self._evidence(text, ["do not duplicate", "must not duplicate", "policy"]),
                ))
                break
        return constraints

    def _dependency_constraints(self, root: Path | None) -> list[PatchConstraint]:
        if not root:
            return []
        constraints: list[PatchConstraint] = []
        try:
            metadata = self.facade.read_project_metadata(str(root))
        except Exception:
            return []
        for dep in metadata.dependencies[:6]:
            if not dep.resolved_version:
                continue
            source = self._dependency_source(dep.version_source)
            constraints.append(PatchConstraint(
                id=f"pinned-dependency-{self._slug(dep.package_name)}",
                type="dependency_version",
                instruction=f"Use pinned {dep.package_name} {dep.resolved_version}; do not assume APIs from another version.",
                source=source,
                severity="must",
                confidence="high" if dep.version_source.endswith("exact") else "medium",
                evidence=f"{dep.package_name} resolved_version={dep.resolved_version} from {dep.version_source}.",
                symbols=[dep.package_name, dep.resolved_version],
                files=[source],
            ))
        if any((root / lockfile).exists() for lockfile in LOCKFILES):
            lockfile = next(lock for lock in LOCKFILES if (root / lock).exists())
            constraints.append(PatchConstraint(
                id="do-not-change-lockfile",
                type="forbidden_edit",
                instruction="Do not change lockfiles unless the task explicitly requires dependency updates.",
                source=lockfile,
                severity="must",
                confidence="high",
                evidence=f"Lockfile `{lockfile}` is present and pins dependency resolution.",
                files=[lockfile],
            ))
        return constraints

    def _fallback_constraints(self, question: str, changed_files: list[str]) -> list[PatchConstraint]:
        checks = ["Run the relevant test command for the changed area before reporting completion."]
        if changed_files:
            checks.append(f"Review changed files for project-policy compliance: {', '.join(changed_files[:4])}.")
        return [PatchConstraint(
            id="run-relevant-tests",
            type="verification",
            instruction=check,
            source="question",
            severity="should",
            confidence="medium",
            evidence="Every coding patch should be verified with relevant checks.",
        ) for check in checks]

    @staticmethod
    def _dependency_source(version_source: str) -> str:
        for lockfile in LOCKFILES:
            if lockfile.replace(".", "_") in version_source.replace(".", "_") or lockfile in version_source:
                return lockfile
        if "pubspec" in version_source:
            return "pubspec.lock"
        if "package" in version_source:
            return "package-lock.json"
        return version_source or "manifest/lockfile"

    @staticmethod
    def _first_symbol(text: str) -> str | None:
        match = re.search(r"\b[A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy)\b", text)
        return match.group(0) if match else None

    @staticmethod
    def _evidence(text: str, needles: list[str]) -> str:
        for line in text.splitlines():
            if any(needle.lower() in line.lower() for needle in needles):
                return line.strip()[:240]
        compact = " ".join(text.split())
        return compact[:240]

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "dependency"

    @staticmethod
    def _dedupe(constraints: list[PatchConstraint]) -> list[PatchConstraint]:
        seen: set[str] = set()
        out: list[PatchConstraint] = []
        for constraint in constraints:
            if constraint.id in seen:
                continue
            seen.add(constraint.id)
            out.append(constraint)
        return out

    @staticmethod
    def _sort_constraints(constraints: list[PatchConstraint]) -> list[PatchConstraint]:
        severity_rank = {"must": 0, "should": 1, "info": 2}
        confidence_rank = {"high": 0, "medium": 1, "low": 2}
        type_rank = {"generated_file": 0, "forbidden_edit": 1, "source_of_truth": 2, "dependency_version": 3, "architecture": 4, "verification": 5}
        return sorted(constraints, key=lambda c: (severity_rank.get(c.severity, 3), confidence_rank.get(c.confidence, 3), type_rank.get(c.type, 9), c.id))

    def _apply_budget(self, constraints: list[PatchConstraint], *, max_constraints: int, max_tokens: int) -> tuple[list[PatchConstraint], bool]:
        selected: list[PatchConstraint] = []
        truncated = False
        for constraint in constraints:
            candidate = selected + [constraint]
            if len(candidate) > max_constraints or self._estimate_packet_tokens(candidate, []) > max_tokens:
                truncated = True
                continue
            selected = candidate
        return selected, truncated or len(selected) < len(constraints)

    @staticmethod
    def _estimate_packet_tokens(constraints: list[PatchConstraint], warnings: list[str]) -> int:
        text = "\n".join(
            [f"{c.type} {c.severity} {c.confidence} {c.instruction} {c.source} {c.evidence}" for c in constraints]
            + warnings
        )
        return max(1, (len(text) + 3) // 4) if text else 0

    @staticmethod
    def _packet_confidence(constraints: list[PatchConstraint]) -> str:
        if not constraints:
            return "low"
        high = sum(1 for c in constraints if c.confidence == "high")
        if high >= 3:
            return "high"
        if high:
            return "medium"
        return "low"

    @staticmethod
    def _source_summary(sources: list[dict[str, str]], constraints: list[PatchConstraint]) -> list[dict[str, Any]]:
        used = {c.source for c in constraints}
        summary: list[dict[str, Any]] = []
        for source in sources:
            if source["path"] in used:
                summary.append({"path": source["path"], "kind": "project_doc"})
        for source in sorted(used):
            if source in LOCKFILES or "lock" in source or "manifest" in source:
                summary.append({"path": source, "kind": "dependency_metadata"})
        return summary
