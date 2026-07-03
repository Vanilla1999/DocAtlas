from __future__ import annotations

import json
import fnmatch
import hashlib
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docmancer.docs.domain.source_map import build_project_repo_map, build_project_source_evidence
from docmancer.docs.models import DependencyObservation, PatchConstraint, PatchConstraintPacket

DEFAULT_MAX_CONSTRAINTS = 12
DEFAULT_MAX_TOKENS = 1200
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
MANIFESTS = {"pubspec.yaml", "pyproject.toml", "requirements.txt", "package.json", "Cargo.toml", "go.mod"}
DEPENDENCY_FILES = LOCKFILES | MANIFESTS
GENERATED_PATTERNS = (
    "*.g.dart",
    "*.freezed.dart",
    "*.pb.go",
    "*.pb.dart",
    "*.generated.*",
    "generated/",
    "dist/",
)
GENERATED_ARTIFACT_SOURCE_PATTERNS = (
    "eval/task_level/results/**",
    ".docatlas/**",
    ".docmancer/**",
)
PATCH_REVIEW_DIR_NAMES = {"patch-review", "patch_review"}
PATCH_REVIEW_ARTIFACT_NAMES = {
    "review_summary.md",
    "constraints.md",
    "constraints.json",
    "validation.json",
    "changed_files.json",
    "patch.diff",
    "patch.raw.diff",
    "git_status.txt",
    "git_status.raw.txt",
    "changed_files.raw.json",
    "patch_hygiene.json",
    "untracked_files.json",
    "ignored_runtime_artifacts.json",
    "review_notes.md",
    "checks.txt",
}
DOGFOOD_TASK_ARTIFACT_NAMES = {"task.md", "review_notes.md"}
GENERIC_CALL_SYMBOLS = {
    "read", "watch", "of", "push", "pop", "map", "where", "firstWhere",
    "maybeWhen", "when", "setState",
}
ASSET_TASK_TERMS = {
    "asset", "assets", "icon", "image", "logo", "svg", "png", "jpg",
    "resource", "generated asset", "иконка", "изображение", "логотип",
    "ресурс", "ассет", "картинка",
}
ASSET_REGISTRY_FILENAMES = {"assets.dart", "asset.dart", "assets.gen.dart", "assets.g.dart"}
PHRASE_ALIASES = {
    "закрыть меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрывать меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрытие меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрыть шторку": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрывать шторку": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрытие шторки": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрыть панель": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "закрывать панель": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "скрыть меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "скрывать меню": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "скрыть шторку": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "скрывать шторку": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "close menu": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "closing menu": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "close drawer": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "closing drawer": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "hide menu": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "hide drawer": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "dismiss menu": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "dismiss drawer": ("closeMenu", "close", "hide", "dismiss", "drawer", "menu"),
    "быстрая информация": ("openInfo", "info", "information"),
    "scan doc": ("goToScanDocInit", "scanDoc", "scan", "document"),
    "сканирование документов": ("goToScanDocInit", "scanDoc", "scan", "document"),
}
SYMBOL_SOURCE_SUFFIXES = (".py", ".dart", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".kt", ".java", ".md", ".txt")
ARCHITECTURE_DOC_RE = re.compile(
    r"(^|/)(architecture\.md|architecture/|adr/|adrs/|contributing\.md|readme[^/]*\.(md|txt)|adr[^/]*\.md)$",
    re.I,
)
KEYWORD_RE = re.compile(
    r"\b(must(?:\s+not)?|should(?:\s+not)?|belongs to|owned by|owns|source[- ]of[- ]truth|canonical|single source|do not duplicate|do not bypass|do not hardcode|layer|service layer|domain layer|application layer|presentation layer|provider delegates|repository owns|adapter owns)\b",
    re.I,
)
EXCLUDED_SOURCE_PARTS = {
    "eval",
    "fixtures",
    "results",
    "runtime",
    "workspaces",
    "hidden_tests",
    "oracles",
    ".cache",
    ".pytest_cache",
    ".uv",
    "uv-cache",
    "archive-v0",
    "materialized",
    "node_modules",
    ".venv",
    "venv",
    ".git",
    "__pycache__",
}


class PatchConstraintsService:
    """Compile compact repository patch constraints from visible local project sources."""

    def __init__(self, facade: Any):
        self.facade = facade
        self._question = ""
        self._changed_files: list[str] = []
        self._ignored_generated_artifact_sources: list[str] = []
        self._excluded_source_reasons: list[dict[str, str]] = []
        self._project_root: Path | None = None

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
        self._question = question or ""
        self._changed_files = changed_files
        self._ignored_generated_artifact_sources = []
        self._excluded_source_reasons = []
        root = Path(project_path).expanduser().resolve() if project_path else None
        self._project_root = root
        sources = self._visible_sources(root) if root else []
        constraints: list[PatchConstraint] = []
        constraints.extend(self._architecture_constraints(sources))
        constraints.extend(self._generated_file_constraints(sources, changed_files))
        constraints.extend(self._dependency_constraints(root))
        repo_map, source_evidence = self._code_evidence(root, question, changed_files)
        constraints.extend(self._source_evidence_constraints(source_evidence))
        symbol_candidates = self._symbol_candidates(question, root, changed_files)
        constraints.extend(self._symbol_candidate_constraints(symbol_candidates))
        constraints.extend(self._fallback_constraints(question, changed_files, root))
        constraints = self._dedupe(constraints)
        constraints = self._sort_constraints(constraints)
        selected, truncated = self._apply_budget(constraints, max_constraints=max_constraints, max_tokens=max_tokens)
        warnings: list[str] = []
        if truncated:
            warnings.append("constraints truncated by budget: must/high-confidence direct-source constraints were kept before lower-confidence guidance.")
        if any(c.confidence == "low" for c in selected):
            warnings.append("Low-confidence inferred constraints are based only on filenames/task context; verify against project docs before treating them as hard requirements.")
        if not root:
            warnings.append("project_path was not provided; constraints are limited to task-level generic guidance.")
        if root and not sources:
            warnings.append("No visible project docs were found; constraints are limited to dependency metadata and generic checks.")
        if self._ignored_generated_artifact_sources:
            warnings.append(f"ignored_generated_artifact_sources: excluded {len(self._ignored_generated_artifact_sources)} generated dogfood/eval artifact source(s) from patch-constraint extraction.")
        selected, final_truncated = self._final_token_clamp(
            selected, warnings, max_constraints=max_constraints, max_tokens=max_tokens
        )
        if final_truncated:
            warnings.append("constraints omitted by final token budget clamp after warnings were added.")
            selected, _ = self._final_token_clamp(
                selected, warnings, max_constraints=max_constraints, max_tokens=max_tokens
            )
        token_estimate = self._estimate_packet_tokens(selected, warnings)
        confidence = self._packet_confidence(selected)
        return PatchConstraintPacket(
            task=question,
            constraints=selected,
            contract_id=self._contract_id(root, question, selected),
            project_path=str(root) if root else None,
            generated_at=datetime.now(UTC).isoformat(),
            index_state=self._index_state(root, sources),
            token_budget={
                "max_tokens": max_tokens,
                "max_constraints": max_constraints,
                "token_estimate": token_estimate,
                "truncated": truncated,
            },
            next_actions=self._next_actions(selected, truncated),
            forbidden_edits=[c for c in selected if c.type in {"forbidden_edit", "generated_file"}],
            dependency_contracts=[c for c in selected if c.type == "dependency_version"],
            source_of_truth_rules=[c for c in selected if c.type == "source_of_truth"],
            suggested_checks=[c.instruction for c in selected if c.type == "verification"],
            warnings=warnings,
            sources=self._source_summary(sources, selected) if include_sources else [],
            repo_map=repo_map,
            source_evidence=source_evidence,
            symbol_candidates=symbol_candidates,
            ignored_generated_artifact_sources=self._ignored_generated_artifact_sources[:20],
            excluded_source_reasons=self._excluded_source_reasons[:50],
            excluded_source_count=len(self._ignored_generated_artifact_sources),
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
        patterns = [
            "README*",
            "CONTRIBUTING*",
            "ARCHITECTURE.md",
            "docs/architecture.md",
            "docs/**/*.md",
            "docs/**/*.txt",
            "ADR*",
            "adr/**/*.md",
            "ADR/**/*.md",
            ".docatlas/**/*.md",
            ".docmancer/**/*.md",
            "**/README.md",
            "**/ARCHITECTURE.md",
        ]
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
            rel = resolved.relative_to(root).as_posix()
            excluded_reason = self._excluded_source_reason(rel)
            if excluded_reason:
                if excluded_reason in {
                    "patch_review_output",
                    "dogfood_generated_artifact",
                    "dogfood_result_memo",
                    "dogfood_task_artifact",
                    "eval_result_artifact",
                    "docatlas_internal_output",
                }:
                    self._ignored_generated_artifact_sources.append(rel)
                    self._excluded_source_reasons.append({"path": rel, "reason": excluded_reason})
                continue
            if not (ARCHITECTURE_DOC_RE.search(rel) or "/docs/" in f"/{rel}" or rel.lower().startswith("docs/")):
                continue
            if resolved.stat().st_size > 80_000:
                continue
            text = resolved.read_text(encoding="utf-8", errors="replace")
            out.append({"path": rel, "text": text})
            seen.add(resolved)
        return out

    def _code_evidence(self, root: Path | None, question: str, changed_files: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not root or not root.exists():
            return [], []
        requirements = self._task_terms(question)
        for changed in changed_files:
            stem = Path(changed).stem.replace("_", " ").replace("-", " ")
            if len(stem) >= 3:
                requirements.append(stem)
        try:
            repo_map = build_project_repo_map(root, question=question, max_files=6, token_budget=650)
            source_evidence = build_project_source_evidence(
                root,
                question=question,
                requirements=requirements or None,
                max_items=8,
                token_budget=500,
            )
        except Exception:
            return [], []
        return repo_map, source_evidence

    def _source_evidence_constraints(self, items: list[dict[str, Any]]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for item in items:
            if item.get("evidence_class") != "source_snippet":
                continue
            path = str(item.get("path") or "")
            if not path:
                continue
            snippet = str(item.get("snippet") or "")
            terms = [str(term) for term in item.get("matched_terms") or [] if str(term).strip()]
            term = terms[0] if terms else Path(path).stem
            line_start = item.get("line_start")
            constraints.append(self._constraint(
                id=f"source-evidence-{self._slug(path)}-{self._slug(term)}-{line_start or 0}",
                type="project_convention",
                instruction=f"Task term `{term}` has concrete source evidence in `{path}`; inspect or reuse that path before inventing a new implementation.",
                source=path,
                severity="should",
                confidence="medium",
                evidence=snippet,
                symbols=terms,
                files=[path],
                source_kind="source_evidence",
                line_start=line_start,
                line_end=item.get("line_end") or line_start,
            ))
        return constraints

    @staticmethod
    def _under_root(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _excluded_source_reason(rel: str) -> str | None:
        normalized = rel.replace("\\", "/")
        parts_list = [part.lower() for part in Path(normalized).parts]
        parts = set(parts_list)
        name = parts_list[-1] if parts_list else ""
        if bool(parts & PATCH_REVIEW_DIR_NAMES):
            return "patch_review_output"
        if parts_list[:2] in ([".docatlas", "patch-review"], [".docmancer", "patch-review"]):
            return "patch_review_output"
        in_dogfood_research = (
            "docs" in parts
            and "research" in parts
            and any(part.startswith("docatlas-dogfood") for part in parts_list)
        )
        if in_dogfood_research and (fnmatch.fnmatch(name, "review-value*.md") or name == "baseline.md"):
            return "dogfood_result_memo"
        if in_dogfood_research and name in DOGFOOD_TASK_ARTIFACT_NAMES:
            return "dogfood_task_artifact"
        if name in PATCH_REVIEW_ARTIFACT_NAMES and in_dogfood_research:
            return "dogfood_generated_artifact"
        if normalized.startswith("docs/research/docatlas-dogfood") and name in PATCH_REVIEW_ARTIFACT_NAMES:
            return "dogfood_generated_artifact"
        if normalized.startswith("eval/task_level/results/"):
            return "eval_result_artifact"
        if normalized.startswith((".docatlas/", ".docmancer/")):
            return "docatlas_internal_output"
        if any(fnmatch.fnmatch(normalized, pattern) for pattern in GENERATED_ARTIFACT_SOURCE_PATTERNS):
            return "dogfood_generated_artifact"
        if bool(parts & EXCLUDED_SOURCE_PARTS) or any("oracle" in part or "hidden" in part for part in parts_list):
            return "runtime_or_hidden"
        return None

    @classmethod
    def _excluded_source(cls, rel: str) -> bool:
        return cls._excluded_source_reason(rel) is not None


    # Patch Contract Safety Gate helpers.
    # These helpers deliberately keep the safety policy local to the constraint compiler:
    # public/runtime surfaces may stay stable while extraction becomes more conservative.

    @staticmethod
    def _source_authority(path: str) -> str:
        """Return an authority class for extracting agent-obeyable patch rules."""
        normalized = (path or "").replace("\\", "/").lower().strip("/")
        name = Path(normalized).name
        if not normalized:
            return "low"
        if any(part in normalized for part in (
            "/eval/", "eval/", "/results/", "results/", "/dogfood/", "dogfood/",
            "/patch-review/", "/patch_review/", ".docatlas/", ".docmancer/",
        )):
            return "risky"
        if normalized.startswith("docs/research/") or "/docs/research/" in f"/{normalized}":
            return "low"
        if any(token in name for token in (
            "comparison", "benchmark", "pilot", "experiment", "research", "roadmap", "prompt", "brief",
        )):
            return "low"
        if name in {"agents.md", "contributing.md", "architecture.md", "project_map.md"}:
            return "high"
        if name.startswith("adr") or normalized.startswith("adr/") or normalized.startswith("adrs/"):
            return "high"
        if normalized == "readme.md" or name == "readme.md":
            return "high"
        if normalized.startswith("docs/") and any(token in normalized for token in (
            "architecture", "index", "development", "contributing", "runbook", "operations", "policy",
        )):
            return "medium"
        if normalized.startswith("docs/") or name.endswith(".md") or name.endswith(".txt"):
            return "medium"
        return "low"

    @staticmethod
    def _is_markdown_table_row(raw: str) -> bool:
        stripped = (raw or "").strip()
        if not stripped.startswith("|"):
            return False
        if stripped.count("|") < 2:
            return False
        # Header separator or ordinary table row.
        compact = stripped.replace("|", "").replace("-", "").replace(":", "").strip()
        return not compact or stripped.count("|") >= 2

    @staticmethod
    def _example_marker_re() -> re.Pattern[str]:
        return re.compile(
            r"\b(statements?\s+like|for\s+example|e\.g\.|i\.e\.|example(?:s)?|sample|hypothetical|such\s+as|например)\b",
            re.I,
        )

    @classmethod
    def _is_example_line(cls, line: str) -> bool:
        stripped = (line or "").strip()
        if not stripped:
            return False
        if cls._example_marker_re().search(stripped):
            return True
        # Treat quoted symbol-only owners in explanatory prose as examples unless other evidence grounds them.
        if re.search(r"[\"'“”«»][A-Z][A-Za-z0-9_]*(?:Service|Manager|Repository|Controller|Policy|Layer|Adapter)[\"'“”«»]", stripped):
            if re.search(r"\b(can|could|may|would|like|example|extract|detect|recognize|распозна)\b", stripped, re.I):
                return True
        return False

    @staticmethod
    def _is_example_heading(heading: str) -> bool:
        lowered = (heading or "").lower()
        return any(token in lowered for token in (
            "example", "examples", "sample", "tutorial", "hypothesis", "research", "benchmark",
            "comparison", "experiment", "prompt", "roadmap", "appendix", "пример",
        ))

    @staticmethod
    def _has_normative_language(line: str) -> bool:
        return bool(re.search(
            r"\b(must(?:\s+not)?|should(?:\s+not)?|do\s+not|don't|required|requires|forbidden|never|"
            r"source[- ]of[- ]truth|single\s+source|canonical|owned\s+by|owns|belongs\s+in|"
            r"delegate(?:s)?\s+to|do\s+not\s+duplicate|do\s+not\s+bypass|do\s+not\s+hardcode)\b",
            line or "",
            re.I,
        ))

    @staticmethod
    def _line_metadata_suffix(*, authority: str, block: str, heading: str, downgrade_reason: str | None = None) -> str:
        parts = [f"authority={authority}", f"block={block}"]
        if heading:
            parts.append(f"heading={heading[:60]}")
        if downgrade_reason:
            parts.append(f"downgrade={downgrade_reason}")
        return " [" + "; ".join(parts) + "]"

    def _iter_constraint_lines(self, text: str, source_path: str) -> list[dict[str, str]]:
        """Return non-table, non-code constraint candidates with coarse markdown context."""
        candidates: list[dict[str, str]] = []
        in_code = False
        heading = ""
        authority = self._source_authority(source_path)
        for raw in (text or "").splitlines():
            stripped = raw.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if not stripped:
                continue
            if stripped.startswith("#"):
                heading = re.sub(r"^#+\s*", "", stripped).strip()[:120]
                continue
            if self._is_markdown_table_row(stripped):
                continue
            if stripped.startswith(">"):
                # Blockquotes are frequently copied examples or historical quotes, not project policy.
                continue
            block = "list" if re.match(r"^\s*[-*+\d.)]+\s+", raw) else "paragraph"
            line = re.sub(r"^\s*[-*+\d.)]+\s*", "", raw).strip()
            if not line:
                continue
            is_example = self._is_example_line(line) or self._is_example_heading(heading)
            candidates.append({
                "line": line[:300],
                "heading": heading,
                "authority": authority,
                "block": block,
                "is_example": "true" if is_example else "false",
            })
        return candidates

    @staticmethod
    def _path_looks_forbidden_artifact(path: str) -> bool:
        normalized = (path or "").replace("\\", "/").lower()
        if not normalized:
            return False
        artifact_parts = (
            "/generated/", "generated/", "/dist/", "dist/", "/build/", "build/", "/coverage/", "coverage/",
            "eval/task_level/results/", ".docatlas/", ".docmancer/", "/patch-review/", "/patch_review/",
            "/dogfood/", "dogfood/", "/node_modules/", "node_modules/", "/vendor/", "vendor/",
        )
        artifact_suffixes = (
            ".g.dart", ".freezed.dart", ".pb.go", ".pb.dart", ".generated", ".generated.py", "_generated.py",
        )
        return any(part in normalized for part in artifact_parts) or any(normalized.endswith(suffix) for suffix in artifact_suffixes)

    def _repo_artifact_examples(self, root: Path | None, limit: int = 8) -> list[str]:
        if not root or not root.exists():
            return []
        examples: list[str] = []
        patterns = (
            "eval/task_level/results/**", ".docatlas/**", ".docmancer/**", "**/patch-review/**", "**/patch_review/**",
            "**/generated/**", "**/dist/**", "**/coverage/**", "**/*.g.dart", "**/*.freezed.dart", "**/*.pb.go",
            "**/*.pb.dart", "**/*.generated.*", "**/*_generated.py",
        )
        seen: set[str] = set()
        for pattern in patterns:
            try:
                paths = root.glob(pattern)
            except Exception:
                continue
            for path in paths:
                try:
                    if not path.is_file():
                        continue
                    rel = path.relative_to(root).as_posix()
                except Exception:
                    continue
                if rel in seen:
                    continue
                seen.add(rel)
                examples.append(rel)
                if len(examples) >= limit:
                    return examples
        return examples

    def _owner_is_repo_grounded(self, owner: str | None) -> bool:
        if not owner:
            return False
        root = getattr(self, "_project_root", None)
        if not isinstance(root, Path) or not root.exists():
            return False
        needle = owner.lower()
        # Fast path: path/file names.
        try:
            for path in root.rglob("*"):
                if len(path.parts) > 20:
                    continue
                try:
                    rel = path.relative_to(root).as_posix()
                except Exception:
                    continue
                lowered = rel.lower()
                if self._excluded_source(rel):
                    continue
                if needle in lowered:
                    return True
        except Exception:
            pass
        # Bounded content scan to avoid expensive repo-wide reads.
        scanned = 0
        for glob in ("**/*.py", "**/*.dart", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.go", "**/*.rs", "**/*.md"):
            try:
                files = root.glob(glob)
            except Exception:
                continue
            for path in files:
                if scanned >= 250:
                    return False
                try:
                    rel = path.relative_to(root).as_posix()
                    if self._excluded_source(rel) or path.stat().st_size > 120_000:
                        continue
                    scanned += 1
                    if owner in path.read_text(encoding="utf-8", errors="replace"):
                        return True
                except Exception:
                    continue
        return False

    def _safe_constraint_profile(self, *, source_path: str, line: str, owner: str | None, candidate: dict[str, str]) -> tuple[str, str, str | None]:
        """Return severity, confidence, downgrade_reason after applying the safety gate."""
        authority = candidate.get("authority") or self._source_authority(source_path)
        if candidate.get("is_example") == "true":
            return "should", "low", "example_context"
        if candidate.get("block") == "table":
            return "should", "low", "table_row"
        if authority in {"low", "risky"}:
            return "should", "medium" if authority == "low" else "low", "low_authority_source"
        if not self._has_normative_language(line):
            return "should", "medium", "non_normative_language"
        if owner and not self._owner_is_repo_grounded(owner):
            return "should", "medium", "ungrounded_owner"
        severity = "must" if re.search(r"\b(must|must not|do not|source[- ]of[- ]truth|owned by|owns|single source|never|required)\b", line, re.I) else "should"
        confidence = "high" if severity == "must" and authority in {"high", "medium"} else "medium"
        return severity, confidence, None

    def _final_token_clamp(self, constraints: list[PatchConstraint], warnings: list[str], *, max_constraints: int, max_tokens: int) -> tuple[list[PatchConstraint], bool]:
        """Apply the token budget after warnings have been assembled."""
        selected = constraints[:max_constraints]
        if self._estimate_packet_tokens(selected, warnings) <= max_tokens:
            return selected, False
        # Drop lowest-value constraints first: low confidence, verification, then long instructions.
        type_rank = {"source_of_truth": 0, "generated_file": 1, "forbidden_edit": 1, "dependency_version": 2, "architecture": 3, "project_convention": 4, "verification": 8}
        confidence_rank = {"high": 0, "medium": 1, "low": 2}
        severity_rank = {"must": 0, "should": 1, "may": 2}
        ordered = sorted(
            selected,
            key=lambda c: (
                0 if c.type == "generated_file" and c.source == "changed_files" else 1,
                type_rank.get(c.type, 9),
                severity_rank.get(c.severity, 9),
                confidence_rank.get(c.confidence, 9),
                len(c.instruction) + len(c.evidence),
            ),
        )
        while ordered and self._estimate_packet_tokens(ordered, warnings) > max_tokens:
            ordered.pop()
        return ordered, True

    def _architecture_constraints(self, sources: list[dict[str, str]]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []

        for source in sources:
            source_path = source["path"]
            for candidate in self._iter_constraint_lines(source["text"], source_path):
                line = candidate["line"]
                lowered = line.lower()

                # Never turn examples/tutorial text into agent-obeyable patch rules.
                if candidate.get("is_example") == "true":
                    continue
                if not (KEYWORD_RE.search(line) or self._owner_from_line(line)):
                    continue

                owner = self._owner_from_line(line)
                ctype = "architecture"
                if "source of truth" in lowered or "source-of-truth" in lowered or owner:
                    ctype = "source_of_truth"
                if "do not" in lowered or "must not" in lowered:
                    ctype = "forbidden_edit" if "duplicate" in lowered or "bypass" in lowered or "hardcode" in lowered else ctype

                severity, confidence, downgrade_reason = self._safe_constraint_profile(
                    source_path=source_path,
                    line=line,
                    owner=owner,
                    candidate=candidate,
                )
                evidence = line + self._line_metadata_suffix(
                    authority=candidate.get("authority", "low"),
                    block=candidate.get("block", "paragraph"),
                    heading=candidate.get("heading", ""),
                    downgrade_reason=downgrade_reason,
                )

                if "duplicate" in lowered and "policy" in lowered:
                    constraints.append(self._constraint(
                        id="do-not-duplicate-policy",
                        type="forbidden_edit",
                        instruction="Do not duplicate policy outside the documented owner/source of truth.",
                        source=source_path,
                        severity=severity,
                        confidence=confidence,
                        evidence=evidence,
                        symbols=[owner] if owner else [],
                    ))

                if "provider" in lowered and "delegat" in lowered:
                    target = owner or self._delegate_target(line) or "the documented service/domain/application owner"
                    target_grounded = owner is None or self._owner_is_repo_grounded(owner)
                    target_confidence = confidence if target_grounded else "medium"
                    target_severity = severity if target_grounded else "should"
                    constraints.append(self._constraint(
                        id=f"provider-delegates-{self._slug(target)}",
                        type="architecture",
                        instruction=f"Provider/presentation code must delegate policy decisions to {target}; do not implement policy in provider/UI code.",
                        source=source_path,
                        severity=target_severity,
                        confidence=target_confidence,
                        evidence=evidence if target_grounded else evidence + " [downgrade=ungrounded_delegate_target]",
                        symbols=[target],
                        files=self._matching_changed_files(("provider", "presentation", "ui")),
                    ))

                if owner:
                    constraints.append(self._constraint(
                        id=f"source-of-truth-{self._slug(owner)}",
                        type="source_of_truth",
                        instruction=f"Keep behavior/policy changes in the documented source of truth: {owner}.",
                        source=source_path,
                        severity=severity,
                        confidence=confidence,
                        evidence=evidence,
                        symbols=[owner],
                        files=self._matching_changed_files(("service", "domain", "application", "provider", "presentation")),
                    ))
                    continue

                if KEYWORD_RE.search(line):
                    constraints.append(self._constraint(
                        id=f"{ctype}-{self._slug(line[:50])}",
                        type=ctype if ctype != "forbidden_edit" or ("do not" in lowered or "must not" in lowered) else "project_convention",
                        instruction=self._instruction_from_line(line),
                        source=source_path,
                        severity=severity,
                        confidence=confidence,
                        evidence=evidence,
                    ))

        return constraints

    def _generated_file_constraints(self, sources: list[dict[str, str]], changed_files: list[str]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []

        for source in sources:
            source_path = source["path"]
            for candidate in self._iter_constraint_lines(source["text"], source_path):
                line = candidate["line"]
                generated_normative = bool(
                    re.search(r"generated|\.g\.dart|\.freezed\.dart|\.pb\.go|\.pb\.dart|build_runner|regenerate|dist/", line, re.I)
                    and self._has_normative_language(line)
                )
                if candidate.get("is_example") == "true" and not generated_normative:
                    continue
                if not re.search(r"generated|\.g\.dart|\.freezed\.dart|\.pb\.go|\.pb\.dart|build_runner|regenerate|dist/", line, re.I):
                    continue
                severity = "must" if candidate.get("authority") in {"high", "medium"} and self._has_normative_language(line) else "should"
                confidence = "high" if severity == "must" else "medium"
                evidence = line + self._line_metadata_suffix(
                    authority=candidate.get("authority", "low"),
                    block=candidate.get("block", "paragraph"),
                    heading=candidate.get("heading", ""),
                    downgrade_reason=None if confidence == "high" else "non_normative_or_low_authority",
                )
                constraints.append(self._constraint(
                    id="generated-files-readonly",
                    type="generated_file",
                    instruction="Do not edit generated artifacts by hand; update the source model/input and regenerate instead.",
                    source=source_path,
                    severity=severity,
                    confidence=confidence,
                    evidence=evidence,
                    files=list(GENERATED_PATTERNS),
                ))
                if "source" in line.lower() or "regenerate" in line.lower() or "build_runner" in line.lower():
                    constraints.append(self._constraint(
                        id="generated-source-of-truth",
                        type="source_of_truth",
                        instruction="For generated artifacts, change the documented source model/input and run the documented generator.",
                        source=source_path,
                        severity=severity,
                        confidence=confidence,
                        evidence=evidence,
                        files=list(GENERATED_PATTERNS),
                    ))

        generated_changed = [f for f in changed_files if self._is_generated_path(f) or self._path_looks_forbidden_artifact(f)]
        if generated_changed:
            constraints.append(self._constraint(
                id="generated-files-inferred",
                type="generated_file",
                instruction="Changed file path looks generated or artifact-like; verify whether it should be regenerated from a source file instead of edited directly.",
                source="changed_files",
                severity="should",
                confidence="medium",
                evidence=", ".join(generated_changed[:4]) + " [authority=changed_files; block=path_heuristic]",
                files=generated_changed,
            ))

        root = getattr(self, "_project_root", None)
        artifact_examples = self._repo_artifact_examples(root)
        if artifact_examples and not any(c.id == "generated-files-inferred" for c in constraints):
            constraints.append(self._constraint(
                id="artifact-paths-not-touch",
                type="generated_file",
                instruction="Do not edit generated, eval, dogfood, patch-review, build, coverage, vendor, or runtime artifact paths unless the task explicitly targets artifact maintenance.",
                source="repo_path_heuristics",
                severity="should",
                confidence="medium",
                evidence=", ".join(artifact_examples[:4]) + " [authority=path_heuristic; block=repo_scan]",
                files=artifact_examples[:8],
            ))

        return constraints

    def _dependency_constraints(self, root: Path | None) -> list[PatchConstraint]:
        if not root:
            return []
        constraints: list[PatchConstraint] = []
        observations = self._dependency_observations(root)
        ranked = sorted(observations, key=lambda dep: self._dependency_relevance(dep), reverse=True)
        for dep in ranked[:12]:
            version = dep.resolved_version or (dep.specifier_raw if dep.specifier_kind == "exact" else None)
            if not version:
                continue
            source = self._dependency_source(dep.version_source, dep.ecosystem, root)
            confidence = "high" if dep.resolved_version and ("lock" in dep.version_source or dep.version_source.endswith("exact")) else "medium"
            constraints.append(self._constraint(
                id=f"pinned-dependency-{self._slug(dep.package_name)}",
                type="dependency_version",
                instruction=f"Use pinned/locked {dep.package_name} {version}; do not assume APIs from another version or latest-only docs.",
                source=source,
                severity="must",
                confidence=confidence,
                evidence=f"{dep.package_name} version {version} from {dep.version_source}.",
                symbols=[dep.package_name, version],
                files=[source],
            ))
        lockfiles = [name for name in sorted(LOCKFILES) if (root / name).exists()]
        if lockfiles:
            lockfile = self._most_relevant_lockfile(lockfiles)
            constraints.append(self._constraint(
                id="do-not-change-lockfile",
                type="forbidden_edit",
                instruction="Do not change lockfiles unless the task explicitly requires dependency updates.",
                source=lockfile,
                severity="must",
                confidence="high",
                evidence=f"Lockfile `{lockfile}` is present and pins dependency resolution.",
                files=lockfiles,
            ))
        return constraints

    def _dependency_observations(self, root: Path) -> list[DependencyObservation]:
        observations: list[DependencyObservation] = []
        try:
            metadata = self.facade.read_project_metadata(str(root))
            observations.extend(metadata.dependencies)
        except Exception:
            pass
        observations.extend(self._read_python_dependencies(root))
        observations.extend(self._read_node_dependencies(root))
        observations.extend(self._read_go_dependencies(root))
        return self._dedupe_dependencies(observations)

    def _read_python_dependencies(self, root: Path) -> list[DependencyObservation]:
        observations: list[DependencyObservation] = []
        req = root / "requirements.txt"
        if req.exists():
            for raw in req.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.split("#", 1)[0].strip()
                match = re.match(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.!+\-]+)", line)
                if match:
                    observations.append(DependencyObservation("python", match.group(1), resolved_version=match.group(2), specifier_kind="exact", specifier_raw=match.group(2), version_source="requirements.txt_exact"))
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            deps = data.get("project", {}).get("dependencies", []) if isinstance(data, dict) else []
            if isinstance(deps, list):
                for spec in deps:
                    if isinstance(spec, str):
                        match = re.match(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.!+\-]+)", spec)
                        if match:
                            observations.append(DependencyObservation("python", match.group(1), resolved_version=match.group(2), specifier_kind="exact", specifier_raw=match.group(2), version_source="pyproject.toml_exact"))
        return observations

    def _read_node_dependencies(self, root: Path) -> list[DependencyObservation]:
        observations: list[DependencyObservation] = []
        lock = root / "package-lock.json"
        if lock.exists():
            try:
                data = json.loads(lock.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            packages = data.get("packages") if isinstance(data, dict) else None
            if isinstance(packages, dict):
                for path, entry in packages.items():
                    if not path.startswith("node_modules/") or not isinstance(entry, dict):
                        continue
                    version = entry.get("version")
                    if isinstance(version, str):
                        observations.append(DependencyObservation("npm", path.split("node_modules/", 1)[1], resolved_version=version, specifier_kind="exact", specifier_raw=version, version_source="package-lock.json_exact"))
            deps = data.get("dependencies") if isinstance(data, dict) else None
            if isinstance(deps, dict):
                for name, entry in deps.items():
                    if isinstance(entry, dict) and isinstance(entry.get("version"), str):
                        observations.append(DependencyObservation("npm", name, resolved_version=entry["version"], specifier_kind="exact", specifier_raw=entry["version"], version_source="package-lock.json_exact"))
        package = root / "package.json"
        if package.exists():
            try:
                data = json.loads(package.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            for section in ("dependencies", "devDependencies"):
                deps = data.get(section) if isinstance(data, dict) else None
                if isinstance(deps, dict):
                    for name, spec in deps.items():
                        if isinstance(spec, str) and re.match(r"^\d+(?:\.\d+){0,2}$", spec):
                            observations.append(DependencyObservation("npm", name, resolved_version=spec, specifier_kind="exact", specifier_raw=spec, version_source="package.json_exact"))
        return observations

    def _read_go_dependencies(self, root: Path) -> list[DependencyObservation]:
        observations: list[DependencyObservation] = []
        gomod = root / "go.mod"
        if gomod.exists():
            text = gomod.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"^\s*([A-Za-z0-9_./-]+)\s+(v\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?)", text, re.M):
                if match.group(1) == "module":
                    continue
                observations.append(DependencyObservation("go", match.group(1), resolved_version=match.group(2), specifier_kind="exact", specifier_raw=match.group(2), version_source="go.mod_exact"))
        return observations

    def _symbol_candidates(self, question: str, root: Path | None, changed_files: list[str]) -> list[dict[str, Any]]:
        if not root or not root.exists():
            return []
        terms = self._task_terms(question)
        if not terms:
            return []
        asset_related_task = self._is_asset_related_task(question)
        source_files = self._symbol_source_files(root, changed_files)
        candidates: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for term in terms:
            variants = self._term_variants(term)
            for path in source_files:
                rel = path.relative_to(root).as_posix()
                if self._excluded_source(rel):
                    continue
                generated_asset_source = self._is_generated_asset_path(rel)
                if generated_asset_source and not asset_related_task:
                    continue
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                for line_number, line in enumerate(lines, start=1):
                    lowered = line.lower()
                    if not any(variant and variant.lower() in lowered for variant in variants):
                        continue
                    symbol = self._symbol_from_line(line, variants)
                    if not symbol:
                        continue
                    if symbol in GENERIC_CALL_SYMBOLS and not self._term_explicitly_mentions_symbol(term, symbol):
                        continue
                    key = (term.lower(), rel, symbol)
                    if key in seen:
                        continue
                    seen.add(key)
                    confidence = self._symbol_confidence(line, symbol, generated_asset_source)
                    reason = "task term matched an existing source/docs symbol; prefer reusing source-attributed project behavior before inventing a new path."
                    if generated_asset_source:
                        reason = "generated_asset_demoted: task explicitly mentions assets/resources, so generated asset registry evidence is kept at low confidence."
                    elif self._is_broad_acronym_symbol_candidate(term, symbol):
                        confidence = "low"
                        reason = "broad_acronym_demoted: short project/product acronyms are too broad for the top PR-bot checklist unless tied to a more specific task symbol."
                    candidates.append({
                        "term": term,
                        "matched_symbol": symbol,
                        "source": rel,
                        "line": line_number,
                        "evidence": line.strip()[:240],
                        "confidence": confidence,
                        "reason": reason,
                    })
                    break
                if any(candidate["term"].lower() == term.lower() for candidate in candidates):
                    break
        return candidates[:12]

    @staticmethod
    def _task_terms(question: str) -> list[str]:
        terms: list[str] = []
        for match in re.finditer(r"[\"'“”«»](.*?)[\"'“”«»]", question):
            value = match.group(1).strip()
            if 2 <= len(value) <= 60:
                terms.append(value)
        terms.extend(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", question))
        terms.extend(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:[A-Z][A-Za-z0-9_]*)+\b", question))
        terms.extend(re.findall(r"\b[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9]*(?:\s+[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9]*){1,2}\b", question))
        for match in re.finditer(r"\b(open|close|show|hide|toggle|navigate|route|save|load)\s+([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9]*)\b", question, re.I):
            terms.append(f"{match.group(1)} {match.group(2)}")
        lowered_question = question.lower()
        for phrase, aliases in PHRASE_ALIASES.items():
            if phrase in lowered_question:
                terms.append(phrase)
                terms.extend(aliases)
        out: list[str] = []
        seen: set[str] = set()
        stop = {"should", "existing", "button", "action", "menu", "project", "current", "текущая", "кнопка", "меню", "экран"}
        for term in terms:
            cleaned = term.strip(" .,:;()[]{}\n\t")
            if len(cleaned) < 3 or len(cleaned) > 60 or cleaned.lower() in stop or PatchConstraintsService._is_noisy_task_term(cleaned):
                continue
            key = cleaned.lower()
            if key not in seen:
                seen.add(key)
                out.append(cleaned)
        return out[:32]

    @staticmethod
    def _is_noisy_task_term(term: str) -> bool:
        words = re.findall(r"[A-Za-zА-Яа-яЁё0-9_]+", term)
        if not words:
            return True
        connector_words = {"and", "or", "и", "или"}
        if words[0].lower() in connector_words or words[-1].lower() in connector_words:
            return True
        return False

    @staticmethod
    def _term_variants(term: str) -> list[str]:
        variants = {term, term.replace("_", " "), term.replace(" ", "_"), term.replace(" ", "")}
        if term.isupper() and "_" in term:
            variants.add(term.lower())
        words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", term)
        if words:
            variants.add("".join(word[:1].upper() + word[1:] for word in words))
            variants.add("".join([words[0].lower(), *[word[:1].upper() + word[1:] for word in words[1:]]]))
            for left, right in zip(words, words[1:]):
                variants.add(f"{left} {right}")
                variants.add(f"{left.lower()}{right[:1].upper() + right[1:]}")
        if term in PHRASE_ALIASES:
            variants.update(PHRASE_ALIASES[term])
        return [variant for variant in variants if len(variant) >= 3]

    def _symbol_source_files(self, root: Path, changed_files: list[str]) -> list[Path]:
        files: list[Path] = []
        for changed in changed_files:
            path = (root / changed).resolve()
            if path.is_file() and self._under_root(path, root):
                files.append(path)
            parent = path.parent if path.suffix else path
            if parent.exists() and self._under_root(parent, root):
                files.extend(p for p in parent.glob("**/*") if p.is_file() and p.suffix in SYMBOL_SOURCE_SUFFIXES and p.stat().st_size <= 80_000)
        for base in (root / "lib", root / "src", root / "app", root / "docs"):
            if base.exists():
                files.extend(p for p in base.rglob("*") if p.is_file() and p.suffix in SYMBOL_SOURCE_SUFFIXES and p.stat().st_size <= 80_000)
        out: list[Path] = []
        seen: set[Path] = set()
        for path in files:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen or not self._under_root(resolved, root):
                continue
            seen.add(resolved)
            out.append(resolved)
            if len(out) >= 300:
                break
        return out

    @staticmethod
    def extract_method_call_symbols(line: str) -> list[str]:
        symbols: list[str] = []
        for match in re.finditer(r"\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", line):
            symbol = match.group(1)
            if symbol not in symbols:
                symbols.append(symbol)
        return symbols

    @classmethod
    def _symbol_from_line(cls, line: str, variants: list[str] | None = None) -> str | None:
        call_symbols = cls.extract_method_call_symbols(line)
        variants_lower = {variant.lower() for variant in variants or []}
        non_generic_calls = [symbol for symbol in call_symbols if symbol not in GENERIC_CALL_SYMBOLS]
        for symbol in reversed(non_generic_calls):
            if symbol.lower() in variants_lower:
                return symbol
        if non_generic_calls:
            return non_generic_calls[-1]
        if call_symbols:
            explicit = [symbol for symbol in reversed(call_symbols) if symbol.lower() in variants_lower]
            if explicit:
                return explicit[0]
        patterns = [
            r"\b(?:class|enum|mixin|extension|typedef|const|final|var|void|Future<[^>]+>|Future|Widget)\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[:=]",
        ]
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                symbol = match.group(1)
                if symbol not in {"if", "for", "while", "switch", "return"}:
                    return symbol
        return None

    @staticmethod
    def _symbol_confidence(line: str, symbol: str, generated_asset_source: bool) -> str:
        if generated_asset_source:
            return "low"
        if re.search(rf"\b(?:class|enum|mixin|extension|typedef|const|final|var|void|Future<[^>]+>|Future|Widget)\s+{re.escape(symbol)}\b", line):
            return "high"
        return "medium"

    @staticmethod
    def _is_broad_acronym_symbol_candidate(term: str, symbol: str) -> bool:
        compact_term = re.sub(r"[^A-Z0-9]+", "", term)
        if not (term == compact_term and 3 <= len(compact_term) <= 5):
            return False
        return symbol.lower() != compact_term.lower()

    @staticmethod
    def _term_explicitly_mentions_symbol(term: str, symbol: str) -> bool:
        return term.lower() == symbol.lower()

    @staticmethod
    def _is_asset_related_task(question: str) -> bool:
        lowered = question.lower()
        return any(term in lowered for term in ASSET_TASK_TERMS)

    @classmethod
    def _is_generated_asset_path(cls, rel: str) -> bool:
        lower = rel.lower()
        name = Path(lower).name
        return cls._is_generated_path(rel) or name in ASSET_REGISTRY_FILENAMES or lower.startswith("lib/generated/") or "/lib/generated/" in f"/{lower}"

    def _symbol_candidate_constraints(self, candidates: list[dict[str, Any]]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for candidate in candidates[:6]:
            symbol = str(candidate.get("matched_symbol") or candidate.get("term") or "symbol")
            constraints.append(self._constraint(
                id=f"symbol-candidate-{self._slug(str(candidate.get('term') or symbol))}-{self._slug(symbol)}",
                type="source_of_truth" if candidate.get("confidence") == "medium" else "project_convention",
                instruction=f"Task term `{candidate.get('term')}` matches existing project symbol `{symbol}`; prefer reusing that source-attributed path before adding a new implementation.",
                source=str(candidate.get("source") or "project_source"),
                severity="should",
                confidence=str(candidate.get("confidence") or "low"),
                evidence=str(candidate.get("evidence") or ""),
                symbols=[str(candidate.get("term") or ""), symbol],
                files=[str(candidate.get("source") or "")],
            ))
        return constraints

    @staticmethod
    def _dedupe_dependencies(observations: list[DependencyObservation]) -> list[DependencyObservation]:
        best: dict[tuple[str, str], DependencyObservation] = {}
        for dep in observations:
            key = (dep.ecosystem, dep.package_name)
            old = best.get(key)
            if old is None or (dep.resolved_version and not old.resolved_version) or ("lock" in dep.version_source and "lock" not in old.version_source):
                best[key] = dep
        return list(best.values())

    def _fallback_constraints(self, question: str, changed_files: list[str], root: Path | None) -> list[PatchConstraint]:
        checks = ["Run the relevant test command for the changed area before reporting completion."]
        if any(self._is_generated_path(f) for f in changed_files):
            checks.append("Run the documented code generator/build step and verify generated artifacts are up to date.")
        if any(Path(f).name in DEPENDENCY_FILES for f in changed_files):
            checks.append("Run dependency/lockfile consistency checks after manifest or lockfile changes.")
        if changed_files:
            checks.append(f"Review changed files for project-policy compliance: {', '.join(changed_files[:4])}.")
        source = "question" if not root else "changed_files" if changed_files else "question"
        return [self._constraint(
            id=f"run-check-{idx}",
            type="verification",
            instruction=check,
            source=source,
            severity="should",
            confidence="medium",
            evidence="Coding patches should be verified with relevant checks; changed_files/task context selected this check.",
        ) for idx, check in enumerate(checks)]

    def _constraint(self, **kwargs: Any) -> PatchConstraint:
        evidence = str(kwargs.get("evidence") or "").strip()[:240]
        source = str(kwargs.get("source") or "").strip()
        confidence = kwargs.get("confidence") or "low"
        if confidence == "high" and (not source or not evidence):
            confidence = "medium" if source or evidence else "low"
        return PatchConstraint(
            id=kwargs["id"],
            type=kwargs["type"],
            instruction=str(kwargs["instruction"]).strip(),
            source=source or "inferred",
            severity=kwargs.get("severity", "should"),
            confidence=confidence,
            evidence=evidence or "Inferred from task context; no direct source evidence was available.",
            symbols=list(kwargs.get("symbols") or []),
            files=list(kwargs.get("files") or []),
            source_refs=self._source_refs(source or "inferred", kind=kwargs.get("source_kind"), line_start=kwargs.get("line_start"), line_end=kwargs.get("line_end")),
            evidence_snippets=self._evidence_snippets(source or "inferred", evidence, line_start=kwargs.get("line_start"), line_end=kwargs.get("line_end")),
        )

    @staticmethod
    def _source_refs(source: str, *, kind: str | None = None, line_start: Any = None, line_end: Any = None) -> list[dict[str, Any]]:
        if not source:
            return []
        kind = kind or ("task_context" if source in {"changed_files", "question", "inferred"} else "source")
        if source in DEPENDENCY_FILES or "lock" in source or "manifest" in source:
            kind = "dependency_metadata"
        ref: dict[str, Any] = {"path": source, "kind": kind}
        if line_start:
            ref["line_start"] = line_start
            ref["line_end"] = line_end or line_start
        return [ref]

    @staticmethod
    def _evidence_snippets(source: str, evidence: str, *, line_start: Any = None, line_end: Any = None) -> list[dict[str, Any]]:
        if not evidence:
            return []
        snippet: dict[str, Any] = {"path": source, "text": evidence[:240]}
        if line_start:
            snippet["line_start"] = line_start
            snippet["line_end"] = line_end or line_start
        return [snippet]

    @staticmethod
    def _contract_id(root: Path | None, question: str, constraints: list[PatchConstraint]) -> str:
        payload = json.dumps(
            {
                "project_path": str(root) if root else None,
                "task": question,
                "constraints": [c.id for c in constraints],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return "patch-contract-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _index_state(root: Path | None, sources: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "project_path": str(root) if root else None,
            "visible_source_count": len(sources),
            "source_paths": [source["path"] for source in sources[:20]],
            "source_paths_truncated": len(sources) > 20,
        }

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
            actions.append({"type": "rerun_with_larger_budget", "description": "Contract was budget-truncated; rerun with larger max_tokens/max_constraints if lower-priority guidance is needed."})
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
        score = 0
        if dep.package_name.lower() in haystack:
            score += 10
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
