"""PatchConstraintsService implementation shard 1."""
from __future__ import annotations

from ._patch_constraints_service_shared import *  # noqa: F401,F403


class _PatchConstraintsServicePart01:
    def __init__(self, facade: Any):
        self.facade = facade
        self._question = ""
        self._changed_files: list[str] = []
        self._ignored_generated_artifact_sources: list[str] = []
        self._excluded_source_reasons: list[dict[str, str]] = []
        self._project_root: Path | None = None
        self._dropped_non_actionable_constraints: list[str] = []

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
        self._dropped_non_actionable_constraints = []
        root = Path(project_path).expanduser().resolve() if project_path else None
        self._project_root = root
        sources = self._visible_sources(root) if root else []
        constraints: list[PatchConstraint] = []
        constraints.extend(self._architecture_constraints(sources))
        constraints.extend(self._generated_file_constraints(sources, changed_files))
        constraints.extend(self._dependency_constraints(root))
        requirements = self._task_terms(question)
        for changed in changed_files:
            stem = Path(changed).stem
            if len(stem) >= 3:
                requirements.append(stem)
        repo_map, source_evidence = self._code_evidence(root, question, requirements, changed_files)
        _code_graph, code_graph_items = self._code_graph_evidence(root, question, requirements, changed_files)
        constraints.extend(self._repo_map_constraints(repo_map))
        constraints.extend(self._source_evidence_constraints(source_evidence))
        constraints.extend(self._code_graph_constraints(code_graph_items))
        symbol_candidates = self._symbol_candidates(question, root, changed_files)
        constraints.extend(self._symbol_candidate_constraints(symbol_candidates))
        constraints.extend(self._fallback_constraints(question, changed_files, root))
        constraints = self._dedupe(constraints)
        constraints = self._drop_non_actionable_constraints(constraints)
        constraints = self._sort_constraints(constraints)
        selected, truncated = self._apply_budget(constraints, max_constraints=max_constraints, max_tokens=max_tokens)
        warnings: list[str] = []
        warnings.append("Policy coverage unresolved: prose is not compiled into patch rules; this packet does not authorize edits.")
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
        if self._dropped_non_actionable_constraints:
            warnings.append(
                "dropped_non_actionable_constraints: excluded "
                f"{len(self._dropped_non_actionable_constraints)} heading/tree/ungrounded-owner candidate(s)."
            )
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
        from docmancer.docs.project import ProjectMetadataReader
        metadata = ProjectMetadataReader(max_docs_hash_bytes=80_000).read(root)
        out: list[dict[str, str]] = []
        for candidate in metadata.docs_candidates:
            path = root / candidate.path
            try:
                if candidate.size_bytes > 80_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeError):
                continue
            out.append({"path": candidate.path, "text": text})
        return out

    def _code_evidence(self, root: Path | None, question: str, requirements: list[str], changed_files: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not root or not root.exists():
            return [], []
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
        if changed_files:
            source_evidence = self._prefer_changed_file_evidence(source_evidence, changed_files)
        return repo_map, source_evidence

    def _code_graph_evidence(
        self,
        root: Path | None,
        question: str,
        requirements: list[str],
        changed_files: list[str],
    ) -> tuple[Any | None, list[dict[str, Any]]]:
        if not root or not root.exists():
            return None, []
        try:
            graph = build_project_code_graph(
                root,
                question=question,
                requirements=requirements,
                max_files=24,
                token_budget=3500,
            )
            graph_items = build_code_graph_context_items(
                graph,
                question=question,
                max_items=6,
                token_budget=800,
            )
        except Exception:
            return None, []
        if changed_files:
            graph_items = self._prefer_changed_file_evidence(graph_items, changed_files)
        return graph, graph_items

    @staticmethod
    def _prefer_changed_file_evidence(items: list[dict[str, Any]], changed_files: list[str]) -> list[dict[str, Any]]:
        changed = {file.replace("\\", "/").strip("/") for file in changed_files if file.strip()}
        if not changed:
            return items
        in_scope = [item for item in items if str(item.get("path") or "").replace("\\", "/").strip("/") in changed]
        if in_scope:
            return in_scope
        return items

    def _repo_map_constraints(self, items: list[dict[str, Any]]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for item in items:
            path = str(item.get("path") or "")
            if not path or self._example_source_noise(path):
                continue
            terms = [str(term) for term in item.get("matched_terms") or [] if str(term).strip()]
            term = terms[0] if terms else Path(path).stem
            constraints.append(self._constraint(
                id=f"repo-map-{self._slug(path)}-{self._slug(term)}",
                type="project_convention",
                instruction=f"Task term `{term}` maps to `{path}`; inspect or update that project source before using example or unrelated paths.",
                source=path,
                severity="should",
                confidence="medium",
                evidence=str(item.get("content") or item.get("title") or path)[:500],
                symbols=terms,
                files=[path],
                source_kind="repo_map",
                line_start=item.get("line_start"),
                line_end=item.get("line_end") or item.get("line_start"),
            ))
        return constraints

    def _source_evidence_constraints(self, items: list[dict[str, Any]]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for item in items:
            if item.get("evidence_class") != "source_snippet":
                continue
            path = str(item.get("path") or "")
            if not path:
                continue
            if self._example_source_noise(path):
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

    def _code_graph_constraints(self, items: list[dict[str, Any]]) -> list[PatchConstraint]:
        constraints: list[PatchConstraint] = []
        for item in items:
            path = str(item.get("path") or "")
            if not path or self._example_source_noise(path):
                continue
            metadata = item.get("metadata") or {}
            edge_kinds = [str(kind) for kind in metadata.get("edge_kinds") or []]
            confidence_summary = metadata.get("confidence_summary") or {}
            linked_paths = [str(value) for value in metadata.get("linked_paths") or [] if str(value).strip()]
            symbols = [str(value) for value in metadata.get("symbols") or [] if str(value).strip()]
            files = list(dict.fromkeys([path, *linked_paths]))
            unresolved_only = bool(edge_kinds) and all(str(kind).startswith("unresolved_") for kind in edge_kinds)
            confidence = self._code_graph_constraint_confidence(confidence_summary, unresolved_only=unresolved_only)
            instruction = self._code_graph_constraint_instruction(path, edge_kinds, unresolved_only=unresolved_only)
            constraints.append(self._constraint(
                id=f"code-graph-{self._slug(path)}",
                type="project_convention",
                instruction=instruction,
                source=path,
                severity="should",
                confidence=confidence,
                evidence=str(item.get("content") or "")[:500],
                symbols=symbols,
                files=files,
                source_kind="code_graph",
                source_ref_metadata={"diagnostics": self._code_graph_constraint_diagnostics(item)},
                line_start=item.get("line_start"),
                line_end=item.get("line_end") or item.get("line_start"),
            ))
        return constraints

    @staticmethod
    def _code_graph_constraint_diagnostics(item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata") or {}
        confidence_summary = metadata.get("confidence_summary") or {}
        edge_kinds = [str(kind) for kind in metadata.get("edge_kinds") or []][:20]
        return {
            "path": item.get("path"),
            "edge_kinds": edge_kinds,
            "confidence_summary": dict(sorted(confidence_summary.items())) if isinstance(confidence_summary, dict) else {},
            "score_reasons": [str(reason) for reason in metadata.get("score_reasons") or []][:8],
            "unresolved_count": sum(1 for kind in edge_kinds if kind.startswith("unresolved_")),
            "token_estimate": int(item.get("token_estimate") or 0),
        }

    @staticmethod
    def _code_graph_constraint_confidence(confidence_summary: dict[str, Any], *, unresolved_only: bool) -> str:
        if unresolved_only:
            return "low"
        strong = int(confidence_summary.get("exact") or 0) + int(confidence_summary.get("parser") or 0)
        weak = int(confidence_summary.get("heuristic") or 0) + int(confidence_summary.get("unresolved") or 0) + int(confidence_summary.get("regex") or 0)
        return "medium" if strong > weak else "low"

    @staticmethod
    def _code_graph_constraint_instruction(path: str, edge_kinds: list[str], *, unresolved_only: bool) -> str:
        if unresolved_only:
            return f"`{path}` contains unresolved task-relevant references/imports. Treat this as a search hint, not proof of dependency; inspect linked files or search results before patching."
        if "references" in edge_kinds:
            return f"Task-relevant symbol references appear in `{path}`; inspect this file together with linked definitions before patching."
        if "imports" in edge_kinds or "exports" in edge_kinds:
            return f"`{path}` has local import links to task-relevant files; inspect linked files on both sides of the import before changing behavior."
        return f"Code graph links `{path}` to task-relevant symbols/imports/references. Inspect this file and its linked local files before inventing a new implementation."

    def _example_source_noise(self, path: str) -> bool:
        # Candidate reads have already passed literal membership and boundaries.
        return False

    @staticmethod
    def _under_root(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _excluded_source_reason(rel: str) -> str | None:
        # Compatibility-only negative guard for unbound direct callers. The
        # finite _visible_sources lane does not apply this guessed taxonomy.
        normalized = rel.replace("\\", "/")
        parts_list = [part.lower() for part in Path(normalized).parts]
        parts = set(parts_list)
        name = parts_list[-1] if parts_list else ""
        if bool(parts & PATCH_REVIEW_DIR_NAMES):
            return "patch_review_output"
        if parts_list[:2] == [".docatlas", "patch-review"]:
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
        if normalized.startswith(".docatlas/"):
            return "docatlas_internal_output"
        if any(fnmatch.fnmatch(normalized, pattern) for pattern in GENERATED_ARTIFACT_SOURCE_PATTERNS):
            return "dogfood_generated_artifact"
        if bool(parts & EXCLUDED_SOURCE_PARTS) or any("oracle" in part or "hidden" in part for part in parts_list):
            return "runtime_or_hidden"
        return None

    @classmethod
    def _excluded_source(cls, rel: str) -> bool:
        return cls._excluded_source_reason(rel) is not None

    @staticmethod
    def _source_authority(path: str) -> str:
        """A filename does not establish normative authority."""
        return "risky" if PatchConstraintsService._excluded_source(path) else "low"

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
        return re.compile(r"(?!)")

    @classmethod
    def _is_example_line(cls, line: str) -> bool:
        # No semantic classification; all prose remains non-authoritative.
        return False

    @staticmethod
    def _is_example_heading(heading: str) -> bool:
        return False

    @staticmethod
    def _has_normative_language(line: str) -> bool:
        return False

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
        for line_index, raw in enumerate((text or "").splitlines()):
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
            "eval/task_level/results/", ".docatlas/", "/patch-review/", "/patch_review/",
            "/dogfood/", "dogfood/", "/node_modules/", "node_modules/", "/vendor/", "vendor/", ".dart_tool/", "/.dart_tool/",
        )
        artifact_suffixes = (
            ".g.dart", ".freezed.dart", ".pb.go", ".pb.dart", ".generated", ".generated.py", "_generated.py",
            "generatedpluginregistrant.java", "generatedpluginregistrant.kt",
        )
        return any(part in normalized for part in artifact_parts) or any(normalized.endswith(suffix) for suffix in artifact_suffixes)

    def _repo_artifact_examples(self, root: Path | None, limit: int = 8) -> list[str]:
        # Artifact examples are not a grant to enumerate the repository.
        return []

    def _owner_is_repo_grounded(self, owner: str | None) -> bool:
        # Prose owners are unresolved; never run a hidden repository scan.
        return False

    def _safe_constraint_profile(self, *, source_path: str, line: str, owner: str | None, candidate: dict[str, str]) -> tuple[str, str, str | None]:
        return "should", "low", "unresolved_policy_authority"

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
