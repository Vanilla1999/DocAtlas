"""PatchConstraintsService implementation shard 3."""
from __future__ import annotations

from ._patch_constraints_service_shared import *  # noqa: F401,F403


class _PatchConstraintsServicePart03:
    @staticmethod
    def _next_actions(constraints: list[PatchConstraint], truncated: bool) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = [
            {
                "type": "edit_with_constraints",
                "description": "Apply the patch while treating high-confidence must constraints as advisory guardrails.",
            },
            {
                "type": "validate_patch_against_constraints",
                "tool": "validate_patch_against_constraints",
                "description": "After editing, validate changed files or a patch diff against this contract; unknown/manual results are not passes.",
            },
        ]
        if any(c.type == "verification" for c in constraints):
            actions.append({"type": "run_tests", "description": "Run the relevant project tests/checks and report real output."})
        if truncated:
            actions.append({
                "type": "rerun_with_larger_budget",
                "tool": "get_patch_constraints",
                "description": "Contract was budget-truncated; rerun with the maximum MCP budget and pass changed_files when known to make the contract more task-specific.",
                "arguments_patch": {"max_tokens": 8000, "max_constraints": 40, "changed_files": ["path/to/changed_file"]},
            })
        return actions

    @staticmethod
    @staticmethod
    def _interesting_lines(text: str) -> list[str]:
        lines = []
        in_code = False
        heading = ""
        for raw in text.splitlines():
            stripped = raw.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_code = not in_code
                continue
            if in_code or not stripped:
                continue
            if stripped.startswith("#"):
                heading = re.sub(r"^#+\s*", "", stripped).strip()
                continue
            if PatchConstraintsService._is_markdown_table_row(stripped):
                continue
            if stripped.startswith(">"):
                continue
            line = re.sub(r"^\s*[-*+\d.)]+\s*", "", raw).strip()
            if not line:
                continue
            if PatchConstraintsService._is_example_line(line) or PatchConstraintsService._is_example_heading(heading):
                continue
            lines.append(line[:300])
        return lines

    @staticmethod
    def _owner_from_line(line: str) -> str | None:
        patterns = [
            r"\b([A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter))\s+owns\s+([^.;]+)",
            r"\b([A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter))\s+is\s+(?:the\s+)?(?:canonical\s+|single\s+)?source[- ]of[- ]truth\b",
            r"\b([A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter))\s+is\s+(?:the\s+)?source of truth\s+for\s+([^.;]+)",
            r"\b([^.;]+?)\s+belongs\s+in\s+(?:the\s+)?([A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter))\b",
            r"\bDo not implement\s+([^.;]+?)\s+in\s+([^.;]+?);?\s*(?:use|delegate to)\s+(?:the\s+)?([A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter))\b",
            r"\bdelegates?\s+to\s+(?:the\s+)?([A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter))\b",
            r"\bowned by\s+(?:the\s+)?([A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter))\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, line, re.I)
            if match:
                for group in reversed(match.groups()):
                    if group and re.search(r"[A-Z][A-Za-z0-9_]*(Service|Manager|Repository|Controller|Policy|Layer|Adapter)$", group.strip()):
                        return group.strip()
        service_layer = re.search(r"\b(service layer|domain layer|application layer)\b", line, re.I)
        if service_layer and re.search(r"source[- ]of[- ]truth|owns|belongs|policy", line, re.I):
            return service_layer.group(1).lower()
        return None

    @staticmethod
    def _delegate_target(line: str) -> str | None:
        match = re.search(r"delegates?\s+to\s+(?:the\s+)?([A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter))", line, re.I)
        return match.group(1) if match else None

    @staticmethod
    def _instruction_from_line(line: str) -> str:
        cleaned = line.strip().rstrip(".")
        if re.search(r"\b(must|should|do not)\b", cleaned, re.I):
            return cleaned + "."
        return f"Follow documented project convention: {cleaned}."

    @staticmethod
    def _is_generated_path(path: str) -> bool:
        lower = path.lower()
        return any(
            lower.endswith(suffix) for suffix in (".g.dart", ".freezed.dart", ".pb.go", ".pb.dart")
        ) or ".generated." in lower or "/generated/" in f"/{lower}" or lower.startswith("generated/") or lower.startswith("dist/") or "/dist/" in f"/{lower}"

    def _matching_changed_files(self, needles: tuple[str, ...]) -> list[str]:
        return [f for f in self._changed_files if any(needle in f.lower() for needle in needles)]

    def _dependency_relevance(self, dep: DependencyObservation) -> int:
        haystack = f"{self._question} {' '.join(self._changed_files)}".lower()
        haystack_tokens = set(re.findall(r"[a-z0-9_]+", haystack))
        score = 0
        package = dep.package_name.lower()
        package_words = package.replace("_", " ").replace("-", " ")
        if (len(package) >= 3 and re.search(rf"(?<![a-z0-9_]){re.escape(package)}(?![a-z0-9_])", haystack)) or package in haystack_tokens:
            score += 10
        elif package_words != package and package_words in haystack:
            score += 10
        elif any(part and len(part) >= 5 and part in haystack for part in re.split(r"[_\-]+", package)):
            score += 6
        if any(Path(f).name in DEPENDENCY_FILES for f in self._changed_files):
            score += 4
        if "dependency" in haystack or "version" in haystack or "upgrade" in haystack:
            score += 3
        if dep.resolved_version:
            score += 1
        return score

    def _most_relevant_lockfile(self, lockfiles: list[str]) -> str:
        changed_names = {Path(f).name for f in self._changed_files}
        for lock in lockfiles:
            if lock in changed_names:
                return lock
        order = ["pubspec.lock", "package-lock.json", "uv.lock", "poetry.lock", "Cargo.lock", "go.sum", "pnpm-lock.yaml", "yarn.lock"]
        return next((lock for lock in order if lock in lockfiles), lockfiles[0])

    @staticmethod
    def _dependency_source(version_source: str, ecosystem: str = "", root: Path | None = None) -> str:
        source_lower = (version_source or "").lower()
        for name in DEPENDENCY_FILES:
            if name.lower() in source_lower or name.lower().replace(".", "_") in source_lower.replace(".", "_"):
                return name
        if "pubspec" in source_lower or ecosystem == "pub":
            return "pubspec.lock" if root and (root / "pubspec.lock").exists() else "pubspec.yaml"
        if "package" in source_lower or ecosystem == "npm":
            return "package-lock.json" if root and (root / "package-lock.json").exists() else "package.json"
        if "requirements" in source_lower:
            return "requirements.txt"
        if "pyproject" in source_lower or ecosystem == "python":
            return "pyproject.toml"
        if ecosystem == "rust":
            return "Cargo.lock" if root and (root / "Cargo.lock").exists() else "Cargo.toml"
        if ecosystem == "go":
            return "go.mod"
        return version_source or "manifest/lockfile"

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "constraint"

    @staticmethod
    def _dedupe(constraints: list[PatchConstraint]) -> list[PatchConstraint]:
        seen: set[str] = set()
        out: list[PatchConstraint] = []
        for constraint in constraints:
            key = constraint.id
            if key in seen:
                continue
            seen.add(key)
            out.append(constraint)
        return out

    def _sort_constraints(self, constraints: list[PatchConstraint]) -> list[PatchConstraint]:
        severity_rank = {"must": 0, "should": 1, "info": 2}
        confidence_rank = {"high": 0, "medium": 1, "low": 2}
        type_rank = {"source_of_truth": 0, "architecture": 1, "generated_file": 2, "forbidden_edit": 3, "dependency_version": 4, "project_convention": 5, "verification": 6}

        def relevance(c: PatchConstraint) -> int:
            score = 0
            lower_q = self._question.lower()
            changed = " ".join(self._changed_files).lower()
            text = f"{c.instruction} {' '.join(c.symbols)} {' '.join(c.files)}".lower()
            if any(f and (Path(f).name.lower() in changed or f.lower() in changed) for f in c.files):
                score += 8
            if c.type == "generated_file" and any(self._is_generated_path(f) for f in self._changed_files):
                score += 8
            if c.type in {"architecture", "source_of_truth"} and any(part in changed for part in ("provider", "presentation", "service", "domain", "application")):
                score += 5
            if c.type == "dependency_version" and any(word in lower_q for word in ("dependency", "version", "upgrade", "package")):
                score += 5
            for token in set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", lower_q)):
                if token in text:
                    score += 1
            if c.source.lower().startswith(("docs/", "architecture", "readme", "contributing", "adr")):
                score += 1
            return score

        return sorted(
            constraints,
            key=lambda c: (
                0 if c.type == "generated_file" and c.source == "changed_files" else 1,
                0 if any(ref.get("kind") == "source_evidence" for ref in c.source_refs) else 1,
                severity_rank.get(c.severity, 3),
                confidence_rank.get(c.confidence, 3),
                -relevance(c),
                type_rank.get(c.type, 9),
                len(c.instruction),
                c.id,
            ),
        )

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
            if source in DEPENDENCY_FILES or "lock" in source or "manifest" in source or source in {"changed_files", "question"}:
                summary.append({"path": source, "kind": "dependency_metadata" if source in DEPENDENCY_FILES else "task_context"})
        return summary
