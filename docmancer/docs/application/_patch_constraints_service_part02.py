"""PatchConstraintsService implementation shard 2."""
from __future__ import annotations

from ._patch_constraints_service_shared import *  # noqa: F401,F403


class _PatchConstraintsServicePart02:
    def _architecture_constraints(self, sources: list[dict[str, str]]) -> list[PatchConstraint]:
        # Prose is not an explicit policy schema or mutation authorization.
        return []

    def _source_relevant_to_task(self, source_path: str, text: str) -> bool:
        """Bounded literal relevance only; an empty request is not a match."""
        haystack = f"{source_path}\n{text[:3000]}"
        terms = self._source_relevance_terms(self._question)
        if not terms:
            return False
        for term in terms:
            if term and term in haystack:
                return True
        return False

    @staticmethod
    def _source_relevance_terms(question: str) -> list[str]:
        return PatchConstraintsService._task_terms(question)

    def _drop_non_actionable_constraints(self, constraints: list[PatchConstraint]) -> list[PatchConstraint]:
        kept: list[PatchConstraint] = []
        for constraint in constraints:
            if self._constraint_is_actionable(constraint):
                kept.append(constraint)
                continue
            self._dropped_non_actionable_constraints.append(f"{constraint.id}:{constraint.source}")
        return kept

    def _constraint_is_actionable(self, constraint: PatchConstraint) -> bool:
        instruction = (constraint.instruction or "").strip()
        evidence_line = (constraint.evidence or "").split("[", 1)[0].strip()
        if self._line_is_non_actionable_constraint(instruction):
            return False
        if evidence_line and self._line_is_non_actionable_constraint(evidence_line):
            return False
        if constraint.type == "source_of_truth" and constraint.symbols:
            return any(self._owner_looks_like_code_owner(str(symbol)) for symbol in constraint.symbols)
        return True

    def _line_is_non_actionable_constraint(self, line: str) -> bool:
        stripped = (line or "").strip()
        if not stripped:
            return True
        if TREE_GLYPH_RE.search(stripped):
            return True
        if stripped.endswith(":") and len(stripped.split()) <= 8:
            return True
        return False

    @staticmethod
    def _owner_looks_like_code_owner(owner: str | None) -> bool:
        value = (owner or "").strip().strip("`'\"“”«»")
        if not value or len(value) > 80:
            return False
        if re.search(r"\s|[:;?]|[│├└┬┴┼─]", value):
            return False
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value))

    def _generated_file_constraints(self, sources: list[dict[str, str]], changed_files: list[str]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []

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
        dependency_intent = self._has_dependency_intent()
        for dep in ranked[:12]:
            if not dependency_intent and self._dependency_relevance(dep) <= 1:
                continue
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

    def _has_dependency_intent(self) -> bool:
        return any(Path(path).name in DEPENDENCY_FILES for path in self._changed_files)

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
                if generated_asset_source and rel not in changed_files:
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    code_lines = self._symbol_code_text(content).splitlines()
                except OSError:
                    continue
                for line_number, line in enumerate(lines, start=1):
                    if not any(re.search(rf"(?<![\w]){re.escape(variant)}(?![\w])", line) for variant in variants):
                        continue
                    symbol = self._symbol_from_line(code_lines[line_number - 1], variants)
                    if not symbol:
                        continue
                    key = (term, rel, symbol)
                    if key in seen:
                        continue
                    seen.add(key)
                    confidence = self._symbol_confidence(code_lines[line_number - 1], symbol, generated_asset_source)
                    reason = "task term matched an existing source/docs symbol; prefer reusing source-attributed project behavior before inventing a new path."
                    if generated_asset_source:
                        reason = "Explicit changed path contains a generated registry; kept at low confidence."
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
                if any(candidate["term"] == term for candidate in candidates):
                    break
        return candidates[:12]

    @staticmethod
    def _task_terms(question: str) -> list[str]:
        question = question or ""
        terms: list[str] = []
        for match in re.finditer(r"`([^`\n]+)`|[\"'“”«»]([^\"'“”«»\n]+)[\"'“”«»]", question or ""):
            value = (match.group(1) or match.group(2)).strip()
            if 2 <= len(value) <= 60:
                terms.append(value)
        terms.extend(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", question))
        terms.extend(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:[A-Z][A-Za-z0-9_]*)+\b", question))
        out: list[str] = []
        seen: set[str] = set()
        for term in terms:
            cleaned = term.strip(" .,:;()[]{}\n\t")
            if len(cleaned) < 2 or len(cleaned) > 60:
                continue
            key = cleaned
            if key not in seen:
                seen.add(key)
                out.append(cleaned)
        return out[:32]

    @staticmethod
    def _is_noisy_task_term(term: str) -> bool:
        return not bool((term or "").strip())

    @staticmethod
    def _term_variants(term: str) -> list[str]:
        return [term] if term else []

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
    def _symbol_code_text(text: str) -> str:
        """Mask quoted text/comments without changing source line coordinates.

        Conservative lexical filtering, not a language parser or policy proof.
        Unterminated strings/block comments consume the remaining input.
        """
        pattern = r'''(?s)"""(?:\\.|(?!""").)*(?:"""|\Z)|\x27\x27\x27(?:\\.|(?!\x27\x27\x27).)*(?:\x27\x27\x27|\Z)|"(?:\\.|[^"\\])*(?:"|\Z)|\x27(?:\\.|[^\x27\\])*(?:\x27|\Z)|`(?:\\.|[^`\\])*(?:`|\Z)|/\*.*?(?:\*/|\Z)|//[^\r\n]*|\#[^\r\n]*'''
        return re.sub(pattern, lambda match: re.sub(r"[^\r\n]", " ", match[0]), text)

    @staticmethod
    def extract_method_call_symbols(line: str) -> list[str]:
        symbols: list[str] = []
        code = _PatchConstraintsServicePart02._symbol_code_text(line)
        for match in re.finditer(r"\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", code):
            symbol = match.group(1)
            if symbol not in symbols:
                symbols.append(symbol)
        return symbols

    @classmethod
    def _symbol_from_line(cls, line: str, variants: list[str] | None = None) -> str | None:
        line = cls._symbol_code_text(line)
        if line.lstrip().startswith(("#", "//", "/*", "*", "<!--")):
            return None
        call_symbols = cls.extract_method_call_symbols(line)
        requested = set(variants or [])
        for symbol in reversed(call_symbols):
            if symbol in requested:
                return symbol
        patterns = [
            r"\b(?:class|enum|mixin|extension|typedef|const|final|var|void)\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[:=]",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, line):
                symbol = match.group(1)
                if symbol in requested and symbol not in {"if", "for", "while", "switch", "return"}:
                    return symbol
        return None

    @staticmethod
    def _symbol_confidence(line: str, symbol: str, generated_asset_source: bool) -> str:
        if generated_asset_source:
            return "low"
        if re.search(rf"\b(?:class|enum|mixin|extension|typedef|const|final|var|void)\s+{re.escape(symbol)}\b", line):
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
        # Generated registries are scoped by explicit changed paths, not topic words.
        return False

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
                type="project_convention",
                instruction=f"Task term `{candidate.get('term')}` matches existing project symbol `{symbol}`; prefer reusing that source-attributed path before adding a new implementation.",
                source=str(candidate.get("source") or "project_source"),
                severity="should",
                confidence=str(candidate.get("confidence") or "low"),
                evidence=str(candidate.get("evidence") or ""),
                symbols=[str(candidate.get("term") or ""), symbol],
                files=[str(candidate.get("source") or "")],
                line_start=candidate.get("line"),
                line_end=candidate.get("line"),
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
            changed_label = "changed files"
            if any(self._is_generated_path(f) for f in changed_files) and any(Path(f).name in DEPENDENCY_FILES for f in changed_files):
                changed_label = "changed generated/lockfile files"
            elif any(self._is_generated_path(f) for f in changed_files):
                changed_label = "changed generated files"
            elif any(Path(f).name in DEPENDENCY_FILES for f in changed_files):
                changed_label = "changed lockfile/dependency files"
            checks.append(f"Review {changed_label} for project-policy compliance: {', '.join(changed_files[:4])}.")
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
            source_refs=self._source_refs(source or "inferred", kind=kwargs.get("source_kind"), line_start=kwargs.get("line_start"), line_end=kwargs.get("line_end"), extra=kwargs.get("source_ref_metadata")),
            evidence_snippets=self._evidence_snippets(source or "inferred", evidence, line_start=kwargs.get("line_start"), line_end=kwargs.get("line_end")),
        )

    @staticmethod
    def _source_refs(source: str, *, kind: str | None = None, line_start: Any = None, line_end: Any = None, extra: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not source:
            return []
        kind = kind or ("task_context" if source in {"changed_files", "question", "inferred"} else "source")
        if source in DEPENDENCY_FILES or "lock" in source or "manifest" in source:
            kind = "dependency_metadata"
        ref: dict[str, Any] = {"path": source, "kind": kind}
        if line_start:
            ref["line_start"] = line_start
            ref["line_end"] = line_end or line_start
        if extra:
            ref.update(extra)
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
