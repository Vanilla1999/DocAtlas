from __future__ import annotations

import json
import fnmatch
import re
import tomllib
from pathlib import Path
from typing import Any

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
        sources = self._visible_sources(root) if root else []
        constraints: list[PatchConstraint] = []
        constraints.extend(self._architecture_constraints(sources))
        constraints.extend(self._generated_file_constraints(sources, changed_files))
        constraints.extend(self._dependency_constraints(root))
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

    def _architecture_constraints(self, sources: list[dict[str, str]]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for source in sources:
            for line in self._interesting_lines(source["text"]):
                lowered = line.lower()
                owner = self._owner_from_line(line)
                ctype = "architecture"
                severity = "must" if re.search(r"\b(must|must not|do not|source[- ]of[- ]truth|owned by|owns|single source)\b", line, re.I) else "should"
                if "source of truth" in lowered or "source-of-truth" in lowered or owner:
                    ctype = "source_of_truth"
                if "do not" in lowered or "must not" in lowered:
                    ctype = "forbidden_edit" if "duplicate" in lowered or "bypass" in lowered or "hardcode" in lowered else ctype
                if "duplicate" in lowered and "policy" in lowered:
                    constraints.append(self._constraint(
                        id="do-not-duplicate-policy",
                        type="forbidden_edit",
                        instruction="Do not duplicate policy outside the documented owner/source of truth.",
                        source=source["path"],
                        severity="must",
                        confidence="high",
                        evidence=line,
                        symbols=[owner] if owner else [],
                    ))
                if "provider" in lowered and "delegat" in lowered:
                    target = owner or self._delegate_target(line) or "the documented service/domain/application owner"
                    constraints.append(self._constraint(
                        id=f"provider-delegates-{self._slug(target)}",
                        type="architecture",
                        instruction=f"Provider/presentation code must delegate policy decisions to {target}; do not implement policy in provider/UI code.",
                        source=source["path"],
                        severity="must",
                        confidence="high",
                        evidence=line,
                        symbols=[target],
                        files=self._matching_changed_files(("provider", "presentation", "ui")),
                    ))
                if owner:
                    constraints.append(self._constraint(
                        id=f"source-of-truth-{self._slug(owner)}",
                        type="source_of_truth",
                        instruction=f"Keep behavior/policy changes in the documented source of truth: {owner}.",
                        source=source["path"],
                        severity="must",
                        confidence="high",
                        evidence=line,
                        symbols=[owner],
                        files=self._matching_changed_files(("service", "domain", "application", "provider", "presentation")),
                    ))
                elif KEYWORD_RE.search(line):
                    constraints.append(self._constraint(
                        id=f"{ctype}-{self._slug(line[:50])}",
                        type=ctype if ctype != "forbidden_edit" or ("do not" in lowered or "must not" in lowered) else "project_convention",
                        instruction=self._instruction_from_line(line),
                        source=source["path"],
                        severity=severity,
                        confidence="high",
                        evidence=line,
                    ))
        return constraints

    def _generated_file_constraints(self, sources: list[dict[str, str]], changed_files: list[str]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for source in sources:
            for line in self._interesting_lines(source["text"]):
                if re.search(r"generated|\.g\.dart|\.freezed\.dart|\.pb\.go|\.pb\.dart|build_runner|regenerate|source model|source[- ]of[- ]truth|dist/", line, re.I):
                    if not re.search(r"generated|\.g\.dart|\.freezed\.dart|\.pb\.go|\.pb\.dart|build_runner|regenerate|dist/", line, re.I):
                        continue
                    constraints.append(self._constraint(
                        id="generated-files-readonly",
                        type="generated_file",
                        instruction="Do not edit generated artifacts by hand; update the source model/input and regenerate instead.",
                        source=source["path"],
                        severity="must",
                        confidence="high",
                        evidence=line,
                        files=list(GENERATED_PATTERNS),
                    ))
                    if "source" in line.lower() or "regenerate" in line.lower() or "build_runner" in line.lower():
                        constraints.append(self._constraint(
                            id="generated-source-of-truth",
                            type="source_of_truth",
                            instruction="For generated artifacts, change the documented source model/input and run the documented generator.",
                            source=source["path"],
                            severity="must",
                            confidence="high",
                            evidence=line,
                            files=list(GENERATED_PATTERNS),
                        ))
                    return constraints
        generated_changed = [f for f in changed_files if self._is_generated_path(f)]
        if generated_changed:
            constraints.append(self._constraint(
                id="generated-files-inferred",
                type="generated_file",
                instruction="Changed file path looks generated; verify whether it should be regenerated from a source file instead of edited directly.",
                source="changed_files",
                severity="should",
                confidence="low",
                evidence=", ".join(generated_changed[:4]),
                files=generated_changed,
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
                    symbol = self._symbol_from_line(line, variants) or term
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
            if len(cleaned) < 3 or len(cleaned) > 60 or cleaned.lower() in stop:
                continue
            key = cleaned.lower()
            if key not in seen:
                seen.add(key)
                out.append(cleaned)
        return out[:32]

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
        )

    @staticmethod
    def _interesting_lines(text: str) -> list[str]:
        lines = []
        for raw in text.splitlines():
            line = re.sub(r"^\s*[-*#>\d.()]+\s*", "", raw).strip()
            if line:
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
