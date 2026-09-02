"""ProjectDocsService implementation shard 3."""
from __future__ import annotations

from ._project_docs_service_shared import *  # noqa: F401,F403
from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.context_selection import select_context_candidates
from docmancer.docs.domain.documentation_query_plan import DocumentationQueryPlan


_EXACT_DOCUMENT_FALLBACK_LIMIT = 12


def _exact_document_index_chunks(
    agent: Any,
    *,
    root: Path,
    evidence_path: str,
    indexed_source: str,
    requirements: Any | None,
) -> list[RetrievedChunk]:
    """Return bounded canonical stored sections for one resolved indexed document.

    This fallback is used only after the normal retrieval lane returned no
    candidates. It reads the active generation's already-indexed display text,
    never reparses the working-tree file, and therefore cannot create a second
    source of truth. Canonical evidence selection still decides support.
    """

    try:
        rows = list(
            agent.store.list_sections_for_source(indexed_source, limit=64)
        )
    except (AttributeError, OSError, RuntimeError):
        return []

    normalized_path = normalize_doc_path(evidence_path)
    probes = tuple(dict.fromkeys(
        probe
        for requirement in requirements or ()
        if getattr(requirement, "mandatory", False)
        and (probe := requirement_probe_query(requirement))
    ))[:8]
    terms = tuple(dict.fromkeys(
        token.casefold()
        for probe in probes
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/=+-]{3,}", probe)
    ))[:24]

    metadata_cache: dict[str, dict[str, Any]] = {}
    candidates: list[RetrievedChunk] = []
    for row in rows:
        source = str(row.get("source") or "")
        if not source:
            continue
        if source not in metadata_cache:
            try:
                metadata_cache[source] = dict(agent.store.source_metadata(source) or {})
            except (AttributeError, OSError, RuntimeError):
                metadata_cache[source] = {}
        source_metadata = metadata_cache[source]
        row_path = normalize_doc_path(
            source_metadata.get("project_doc_path") or row.get("source_path")
        )
        if row_path != normalized_path:
            continue
        indexed_project_path = str(
            source_metadata.get("project_path") or row.get("project_path") or ""
        )
        if indexed_project_path != str(root):
            continue
        source_class = str(
            source_metadata.get("source_class") or row.get("source_class") or ""
        )
        if source_class != "project_file":
            continue
        display_text = str(row.get("display_text") or row.get("text") or "").strip()
        if not display_text:
            continue

        searchable = " ".join((
            str(row.get("title") or ""),
            str(row.get("anchor") or ""),
            str(row.get("text") or ""),
            display_text,
        )).casefold()
        hit_count = sum(term in searchable for term in terms)
        if terms and hit_count == 0:
            continue
        metadata = {**source_metadata}
        metadata.update({
            "project_doc_path": row_path,
            "source_path": row_path,
            "source_class": source_class,
            "project_path": indexed_project_path,
            "project_identity": (
                source_metadata.get("project_identity")
                or row.get("project_identity")
            ),
            "doc_scope": source_metadata.get("doc_scope") or row.get("doc_scope") or "project",
            "module_id": source_metadata.get("module_id") or row.get("module_id"),
            "project_doc_authority": (
                source_metadata.get("project_doc_authority")
                or row.get("authority")
            ),
            "project_doc_lifecycle_status": (
                source_metadata.get("project_doc_lifecycle_status")
                or row.get("lifecycle_status")
                or "active"
            ),
            "title": row.get("title"),
            "anchor": row.get("anchor"),
            "line_start": row.get("line_start"),
            "line_end": row.get("line_end"),
            "token_estimate": int(row.get("token_estimate") or 0),
            "stable_chunk_id": row.get("stable_chunk_id"),
            "parent_logical_id": row.get("parent_logical_id"),
            "exact_path_match": True,
        })
        start, end = row.get("char_start"), row.get("char_end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end:
            metadata["char_span"] = [start, end]
        candidates.append(RetrievedChunk(
            source=source,
            chunk_index=int(row.get("chunk_index") or 0),
            text=display_text,
            score=float(1000 + hit_count),
            metadata=metadata,
        ))

    candidates.sort(key=lambda item: (-item.score, item.chunk_index, item.source))
    return candidates[:_EXACT_DOCUMENT_FALLBACK_LIMIT]


def _tag_retrieval_query(
    chunks: Any, query_id: str | None, query_text: str | None = None,
) -> list[Any]:
    if not query_id:
        return list(chunks)
    tagged = []
    for chunk in chunks:
        metadata = dict(chunk.metadata or {})
        trace = dict(metadata.get("lexical_match") or {})
        exact_path_match = bool(metadata.get("exact_path_match"))
        if query_id.startswith("query-path-") and query_text:
            candidate_path = str(
                metadata.get("project_doc_path")
                or metadata.get("path")
                or chunk.source
            )
            exact_path_match = (
                normalize_doc_path(candidate_path) == normalize_doc_path(query_text)
            )
        # Retrieval is candidate generation. Only a lexical relevance trace or
        # an explicitly resolved exact path may qualify model-visible context.
        # A future dense qualification path must carry calibrated provenance
        # from the dispatcher; this layer must not infer it from rank alone.
        trace["qualified"] = bool(trace.get("qualified") or exact_path_match)
        trace.setdefault("lexical_score", float(chunk.score))
        if query_text:
            trace.setdefault("query_text", query_text)
        matches = dict(metadata.get("retrieval_query_matches") or {})
        matches[query_id] = trace
        qualified_ids = tuple(key for key, value in matches.items() if value.get("qualified") is True)
        metadata.update({
            "retrieval_query_matches": matches,
            "retrieval_query_ids": qualified_ids,
        })
        tagged.append(chunk.model_copy(update={"metadata": metadata}))
    return tagged


class _ProjectDocsServicePart03:
    def query_project_docs(
        self,
        project_path: str,
        query: str,
        *,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
        source_class: str = "project_file",
        scope: str | None = None,
        module_path: str | None = None,
        evidence_path: str | None = None,
        requirements: Any | None = None,
        lookup_queries: tuple[str, ...] = (),
        documentation_query_plan: DocumentationQueryPlan | None = None,
    ):
        root = validate_project_path(project_path).path
        answer_lifecycle_intent = str(
            getattr(requirements, "lifecycle_intent", "") or lifecycle_intent(query)
        )
        filters: dict[str, Any] = {
            "project_path": str(root),
            "project_identity": self._repository_identity(root),
            "source_class": source_class,
            **lifecycle_filters_for_intent(answer_lifecycle_intent),
        }
        if scope:
            filters["doc_scope"] = scope
        if module_path:
            filters["module_path"] = module_path
        if evidence_path:
            filters["project_doc_path"] = evidence_path
        agent = self._agent_instance()
        effective_limit = limit or agent.config.query.default_limit
        if requirements is not None:
            # Candidate generation needs enough diversity for deterministic
            # lane/facet selection; the model-visible projection remains capped
            # at three sources and owns the final token ceiling.
            effective_limit = max(effective_limit, 20)
        budget = tokens or DEFAULT_DOC_TOKENS
        effective_expand = (expand or "none") if requirements is not None else expand
        documentation_query_plan = documentation_query_plan or build_documentation_query_plan(
            query, lookup_queries=lookup_queries, explicit_path=evidence_path,
            requirements=requirements,
        )
        lookup_query_ids = {
            item.text: item.query_id
            for item in documentation_query_plan.queries
            if item.origin in {"exact_anchor", "exact_path", "host_lookup", "canonical_intent", "concept_alias", "retrieval_hint"}
        }
        exact_path_query_id = next((
            item.query_id for item in documentation_query_plan.queries
            if item.origin == "exact_path"
        ), None)
        retrieval = getattr(agent.config, "retrieval", None)
        mode = str(getattr(retrieval, "default_mode", "lexical") or "lexical").lower()

        mandatory_requirements = tuple(
            requirement
            for requirement in requirements or ()
            if getattr(requirement, "mandatory", False)
        )
        probe_queries = tuple(dict.fromkeys(
            probe
            for requirement in mandatory_requirements
            if (probe := requirement_probe_query(requirement))
        ))[:8]
        retrieval_hints = tuple(dict.fromkeys(
            str(value).strip()
            for value in getattr(requirements, "retrieval_hints", ())
            if str(value).strip()
        ))[:4]
        contract_concepts = tuple(dict.fromkeys(
            str(value).strip()
            for value in getattr(requirements, "concept_queries", ())
            if str(value).strip()
        ))[:4]
        planned_lookup_queries = tuple(
            item.text for item in documentation_query_plan.queries
            if item.origin in {"exact_anchor", "exact_path", "host_lookup", "canonical_intent", "concept_alias", "retrieval_hint"}
        )
        supplemental_queries = tuple(dict.fromkeys((
            *planned_lookup_queries,
            *probe_queries,
            *contract_concepts,
            *retrieval_hints,
        )))[:12]
        next_supplemental_id = 1
        for supplemental_query in supplemental_queries:
            if supplemental_query in lookup_query_ids:
                continue
            lookup_query_ids[supplemental_query] = (
                f"query-supplemental-{next_supplemental_id}"
            )
            next_supplemental_id += 1
        supplemental_budget = min(budget, max(128, budget // 4))

        gateway = getattr(self.facade, "agent_gateway", None)
        if gateway is not None:
            dispatcher = gateway.dispatcher_for(agent, mode=mode)

            def _run(
                text: str,
                *,
                query_limit: int,
                query_budget: int,
                query_expand: str | None,
                query_filters: dict[str, Any],
            ):
                return dispatcher.run(
                    text,
                    mode=mode,
                    limit=query_limit,
                    budget=query_budget,
                    expand=query_expand,
                    filters=query_filters,
                    requirements=requirements,
                ).chunks

        else:
            # Lightweight facades used by embedders retain the legacy agent
            # contract.  The production service always owns an agent gateway.
            def _run(
                text: str,
                *,
                query_limit: int,
                query_budget: int,
                query_expand: str | None,
                query_filters: dict[str, Any],
            ):
                return agent.query(
                    text,
                    limit=query_limit,
                    budget=query_budget,
                    expand=query_expand,
                    filters=query_filters,
                )

        chunks = _run(
            query,
            query_limit=effective_limit,
            query_budget=budget,
            query_expand=effective_expand,
            query_filters=filters,
        )
        chunks = _tag_retrieval_query(chunks, "query-original", query)
        chunks = _tag_retrieval_query(chunks, exact_path_query_id, evidence_path)
        authoritative_chunks = _run(
            query,
            query_limit=max(effective_limit, 20),
            query_budget=budget,
            query_expand=effective_expand or "page",
            query_filters={**filters, "authority": "source_of_truth"},
        )
        authoritative_chunks = _tag_retrieval_query(
            authoritative_chunks, "query-original", query,
        )
        authoritative_chunks = _tag_retrieval_query(
            authoritative_chunks, exact_path_query_id, evidence_path,
        )
        supplemental_chunks_by_query = {
            supplemental_query: _tag_retrieval_query(
                _run(
                    supplemental_query,
                    query_limit=4,
                    query_budget=supplemental_budget,
                    query_expand="none",
                    query_filters=filters,
                ),
                lookup_query_ids.get(supplemental_query),
                supplemental_query,
            )
            for supplemental_query in supplemental_queries
        }
        queries_by_origin: dict[str, list[list[Any]]] = {}
        for item in documentation_query_plan.queries:
            lane = supplemental_chunks_by_query.get(item.text)
            if lane:
                queries_by_origin.setdefault(item.origin, []).append(lane)
        candidates = select_context_candidates([
            [
                *queries_by_origin.get("exact_path", []),
                *queries_by_origin.get("exact_anchor", []),
            ],
            [[*authoritative_chunks, *chunks]],
            queries_by_origin.get("host_lookup", []),
            [
                *queries_by_origin.get("canonical_intent", []),
                *queries_by_origin.get("concept_alias", []),
                *queries_by_origin.get("retrieval_hint", []),
            ],
        ])
        selected = []
        seen: set[tuple[str, int]] = set()
        token_total = 0
        for chunk in candidates:
            if not lifecycle_allows(chunk.metadata or {}, answer_lifecycle_intent):
                continue
            key = (chunk.source, chunk.chunk_index)
            if key in seen:
                existing_index = next(
                    index for index, item in enumerate(selected)
                    if (item.source, item.chunk_index) == key
                )
                from docmancer.docs.application.context_selection import merge_query_matches
                merged_matches = merge_query_matches(
                    (selected[existing_index].metadata or {}).get("retrieval_query_matches"),
                    (chunk.metadata or {}).get("retrieval_query_matches"),
                )
                merged_ids = tuple(
                    key for key, value in merged_matches.items() if value.get("qualified") is True
                )
                existing = selected[existing_index]
                preferred = chunk if chunk.score > existing.score else existing
                selected[existing_index] = preferred.model_copy(update={
                    "metadata": {
                        **(preferred.metadata or {}),
                        "retrieval_query_matches": merged_matches,
                        "retrieval_query_ids": merged_ids,
                    },
                })
                continue
            if len(selected) >= effective_limit:
                anchor = selected[0]
                same_authoritative_source = (
                    chunk.source == anchor.source
                    and len(selected) < max(effective_limit, 4)
                )
                if not same_authoritative_source:
                    continue
            chunk_tokens = int((chunk.metadata or {}).get("token_estimate") or 0)
            if token_total + chunk_tokens > budget:
                continue
            selected.append(chunk)
            seen.add(key)
            token_total += chunk_tokens
        return selected

    def get_project_docs(
        self,
        project_path: str,
        query: str,
        *,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
        module: str | None = None,
        module_path: str | None = None,
        scope: str | None = None,
        evidence_path: str | None = None,
        requirements: Any | None = None,
        lookup_queries: tuple[str, ...] = (),
        documentation_query_plan: DocumentationQueryPlan | None = None,
    ) -> ProjectDocsResult:
        root = validate_project_path(project_path).path
        if hasattr(self.facade, "_project_get_project_docs_impl"):
            kwargs = {
                "tokens": tokens, "limit": limit, "expand": expand, "module": module,
                "module_path": module_path, "scope": scope,
            }
            if requirements is not None:
                kwargs["requirements"] = requirements
            if lookup_queries:
                kwargs["lookup_queries"] = lookup_queries
            if documentation_query_plan is not None:
                kwargs["documentation_query_plan"] = documentation_query_plan
            if evidence_path:
                kwargs["evidence_path"] = evidence_path
            return self.facade._project_get_project_docs_impl(str(root), query, **kwargs)
        if scope and scope not in {"project", "module", "all"}:
            raise ValueError("scope must be one of: project, module, all")
        metadata = self.read_project_metadata(str(root))
        if metadata.docs_catalog_present and not metadata.docs_catalog_valid:
            next_action = self._invalid_project_docs_catalog_action(root, metadata.warnings)
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="invalid_project_docs_catalog",
                reason_code="invalid_project_docs_catalog",
                next_action=next_action,
                arguments_patch={"project_path": str(root)},
                answer_available=False,
                reason="invalid_project_docs_catalog",
                warnings=metadata.warnings,
                next_actions=[next_action],
                message="docatlas.project-docs.yaml is invalid; fix the catalog before retrieving project documentation.",
            )
        candidate_sources = [asdict(item) for item in metadata.docs_candidates]
        module_summaries = self._module_summaries(candidate_sources)
        resolved_module_path, module_error = self._resolve_module_filter(module_summaries, module=module, module_path=module_path)
        if module_error:
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status=module_error["reason_code"],
                reason_code=module_error["reason_code"],
                next_action={"type": "inspect_project_docs", "tool": "inspect_project_docs"},
                arguments_patch={"project_path": str(root)},
                reason=module_error["reason_code"],
                answer_available=False,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                source_state_guidance=self._source_state_guidance(),
                next_actions=[{
                    "tool": "inspect_project_docs",
                    "requires_confirmation": False,
                    "arguments_patch": {"project_path": str(root)},
                    "reason": "Inspect available modules, then retry with an exact module_path.",
                }],
                message=module_error["message"],
            )
        query_scope = scope if scope != "all" else None
        if resolved_module_path:
            query_scope = "module"
        indexed_sources_all = self._indexed_project_doc_sources(str(root))
        indexed_sources, stale_sources, ignored_sources = self._partition_project_doc_state(candidate_sources, indexed_sources_all)
        if evidence_path:
            requested_path = normalize_doc_path(evidence_path)
            exact_paths = {
                str(item.get("path"))
                for item in indexed_sources
                if normalize_doc_path(item.get("path")) == requested_path
            }
            matching_paths = exact_paths or {
                str(item.get("path"))
                for item in indexed_sources
                if Path(normalize_doc_path(item.get("path"))).name == Path(requested_path).name
            }
            if len(matching_paths) != 1:
                reason_code = (
                    "ambiguous_document_locator" if matching_paths else "document_not_indexed"
                )
                return ProjectDocsResult(
                    project_path=str(root), query=query, status=reason_code,
                    reason_code=reason_code, answer_available=False,
                    reason=reason_code, warnings=metadata.warnings,
                    candidate_sources=candidate_sources,
                    indexed_sources=indexed_sources,
                    source_state_guidance=self._source_state_guidance(),
                    message=(
                        f"Document locator {evidence_path!r} matches multiple indexed project documents."
                        if matching_paths else
                        f"Document locator {evidence_path!r} is not indexed for this project."
                    ),
                )
            evidence_path = next(iter(matching_paths))
        if query_scope:
            candidate_sources = [item for item in candidate_sources if item.get("doc_scope") == query_scope]
            indexed_sources = [item for item in indexed_sources if item.get("doc_scope") == query_scope]
            stale_sources = [item for item in stale_sources if (item.get("candidate") or item).get("doc_scope") == query_scope]
            ignored_sources = [item for item in ignored_sources if item.get("doc_scope") == query_scope]
        if resolved_module_path:
            candidate_sources = [item for item in candidate_sources if item.get("module_path") == resolved_module_path]
            indexed_sources = [item for item in indexed_sources if item.get("module_path") == resolved_module_path]
            stale_sources = [item for item in stale_sources if (item.get("candidate") or item).get("module_path") == resolved_module_path]
            ignored_sources = [item for item in ignored_sources if item.get("module_path") == resolved_module_path]
            if not candidate_sources:
                return ProjectDocsResult(
                    project_path=str(root),
                    query=query,
                    status="no_module_docs",
                    reason_code="no_module_docs",
                    next_action={"type": "inspect_project_docs", "tool": "inspect_project_docs"},
                    arguments_patch={"project_path": str(root)},
                    reason="no_module_docs",
                    answer_available=False,
                    warnings=metadata.warnings,
                    candidate_sources=[asdict(item) for item in metadata.docs_candidates],
                    source_state_guidance=self._source_state_guidance(),
                    message=f"Module {resolved_module_path!r} exists, but no module docs were discovered for this scope.",
                )

        preflight_inspect: ProjectDocsInspectResult | None = None
        if not indexed_sources_all or stale_sources or ignored_sources:
            inspect_result = self.inspect_project_docs(str(root))
            if inspect_result.requires_confirmation and inspect_result.confirmation_reason == "project_docs_preflight":
                preflight_inspect = inspect_result

        def _confirmation_required_result(*, status: str, reason: str) -> ProjectDocsResult:
            assert preflight_inspect is not None
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                resolved_evidence_path=evidence_path,
                status=status,
                reason_code=preflight_inspect.reason_code,
                next_action=preflight_inspect.next_action,
                requires_confirmation=True,
                confirmation_reason=preflight_inspect.confirmation_reason,
                arguments_patch=preflight_inspect.arguments_patch,
                reason=reason,
                answer_available=False,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                indexed_sources=indexed_sources,
                stale_sources=stale_sources,
                ignored_sources=ignored_sources,
                source_state_guidance=self._source_state_guidance(),
                diagnostics=preflight_inspect.diagnostics,
                next_actions=preflight_inspect.recommended_next_actions,
                message=preflight_inspect.user_message or preflight_inspect.agent_message,
            )

        if not candidate_sources:
            if preflight_inspect:
                return _confirmation_required_result(
                    status="confirmation_required",
                    reason="project_docs_preflight_confirmation_required",
                )
            next_action, requires_confirmation, confirmation_reason, arguments_patch, _, user_message = self._project_docs_structured_next_action(
                reason_code="no_project_docs",
                root=root,
                query=query,
            )
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="no_project_docs",
                reason_code="no_project_docs",
                next_action=next_action,
                requires_confirmation=requires_confirmation,
                confirmation_reason=confirmation_reason,
                arguments_patch=arguments_patch,
                reason="no_project_docs",
                answer_available=False,
                warnings=metadata.warnings,
                next_actions=[{
                    **self._create_project_docs_next_action(root, query),
                    "reason": "No project-owned docs candidates were discovered for this repository. Create a reviewable architecture doc before indexing.",
                }],
                message=user_message or "No project-owned docs were found. Ask before creating a reviewable ARCHITECTURE.md, then run inspect_project_docs and sync_project_docs.",
            )

        if not indexed_sources_all:
            if preflight_inspect:
                return _confirmation_required_result(
                    status="confirmation_required",
                    reason="project_docs_preflight_confirmation_required",
                )
            next_action, requires_confirmation, confirmation_reason, arguments_patch, _, _ = self._project_docs_structured_next_action(
                reason_code="project_docs_found_not_indexed",
                root=root,
                query=query,
            )
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                status="not_indexed",
                reason_code="project_docs_found_not_indexed",
                next_action=next_action,
                requires_confirmation=requires_confirmation,
                confirmation_reason=confirmation_reason,
                arguments_patch=arguments_patch,
                reason="project_docs_not_indexed",
                answer_available=False,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                next_actions=[{
                    "tool": "prepare_docs",
                    "requires_confirmation": False,
                    "arguments_patch": {
                        "action": "sync_project_docs",
                        **self._project_sync_arguments(root),
                    },
                    "reason": "Project docs candidates were discovered but have not been indexed; reconcile the index.",
                }],
                message="Project docs candidates exist but are not indexed. Run sync_project_docs, then retry get_project_docs.",
            )

        chunks = self.query_project_docs(
            str(root), query, tokens=tokens, limit=limit, expand=expand,
            scope=query_scope, module_path=resolved_module_path, evidence_path=evidence_path,
            requirements=requirements,
            lookup_queries=lookup_queries,
            documentation_query_plan=documentation_query_plan,
        )
        current_by_path = {
            normalize_doc_path(item.get("path")): item
            for item in indexed_sources
            if item.get("path")
        }
        exact_document_fallback_used = False
        if (
            evidence_path
            and current_by_path.get(normalize_doc_path(evidence_path))
        ):
            exact_source = current_by_path[normalize_doc_path(evidence_path)]
            exact_chunks = _exact_document_index_chunks(
                self._agent_instance(),
                root=root,
                evidence_path=str(exact_source.get("path") or evidence_path),
                indexed_source=str(exact_source.get("source") or ""),
                requirements=requirements,
            )
            exact_query_id = next((
                item.query_id for item in (documentation_query_plan.queries if documentation_query_plan else ())
                if item.origin == "exact_path"
            ), "query-path-1")
            exact_chunks = _tag_retrieval_query(
                exact_chunks, exact_query_id, evidence_path,
            )
            chunks = [*exact_chunks, *chunks]
            exact_document_fallback_used = bool(exact_chunks)
        safe_chunks = []
        dropped_placeholder_chunks = 0
        answer_lifecycle_intent = str(
            getattr(requirements, "lifecycle_intent", "") or lifecycle_intent(query)
        )
        for chunk in chunks:
            metadata_for_chunk = chunk.metadata or {}
            chunk_path = (
                metadata_for_chunk.get("project_doc_path")
                or metadata_for_chunk.get("source_path")
            )
            normalized_chunk_path = normalize_doc_path(chunk_path)
            current_source = current_by_path.get(normalized_chunk_path)
            if not current_source:
                continue
            if metadata_for_chunk.get("project_doc_content_hash") != current_source.get("content_hash"):
                continue
            if not lifecycle_allows(metadata_for_chunk, answer_lifecycle_intent):
                continue
            canonical_path = str(current_source.get("path") or chunk_path or "")
            if self._looks_like_placeholder_search_result(canonical_path, chunk.text):
                dropped_placeholder_chunks += 1
                continue
            # Retrieval/index internals may normalize path case. Once the chunk
            # is rebound to the exact current catalog entry, restore that
            # canonical identity before projection and evidence-path checks.
            canonical_metadata = {
                **metadata_for_chunk,
                "project_doc_path": canonical_path,
                "source_path": canonical_path,
            }
            safe_chunks.append(chunk.model_copy(update={"metadata": canonical_metadata}))
        chunks = safe_chunks
        seen_sources: set[str] = set()
        result_indexed_sources = []
        for chunk in chunks:
            source = chunk.source
            if source in seen_sources:
                continue
            seen_sources.add(source)
            result_indexed_sources.append({
                "source": source,
                "path": (chunk.metadata or {}).get("project_doc_path"),
                "source_class": (chunk.metadata or {}).get("source_class"),
                "content_hash": (chunk.metadata or {}).get("project_doc_content_hash"),
                "mtime_ns": (chunk.metadata or {}).get("project_doc_mtime_ns"),
                "doc_scope": (chunk.metadata or {}).get("doc_scope") or "project",
                "module_id": (chunk.metadata or {}).get("module_id"),
                "module_name": (chunk.metadata or {}).get("module_name"),
                "module_path": (chunk.metadata or {}).get("module_path"),
                "module_type": (chunk.metadata or {}).get("module_type"),
                "description": (chunk.metadata or {}).get("project_doc_description"),
                "authority": (chunk.metadata or {}).get("project_doc_authority"),
                "lifecycle_status": (chunk.metadata or {}).get("project_doc_lifecycle_status"),
                "impact_policy": (chunk.metadata or {}).get("project_doc_impact_policy"),
            })
        stale_paths = {
            normalize_doc_path(item.get("path"))
            for item in stale_sources
            if item.get("path")
        }
        results = [
            ProjectDocsChunk(
                title=(chunk.metadata or {}).get("title"),
                content=chunk.text,
                source=chunk.source,
                url=None,
                metadata={**(chunk.metadata or {}), "score": float(chunk.score)},
                stable_chunk_id=(chunk.metadata or {}).get("stable_chunk_id"),
                parent_logical_id=(chunk.metadata or {}).get("parent_logical_id"),
                display_content_hash=hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
                char_start=((chunk.metadata or {}).get("char_span") or [None, None])[0],
                char_end=((chunk.metadata or {}).get("char_span") or [None, None])[1],
                line_start=((chunk.metadata or {}).get("line_span") or [None, None])[0],
                line_end=((chunk.metadata or {}).get("line_span") or [None, None])[1],
                source_class=(chunk.metadata or {}).get("source_class"),
                path=(chunk.metadata or {}).get("project_doc_path") or (chunk.metadata or {}).get("source_path"),
                heading_path=(chunk.metadata or {}).get("anchor") or (chunk.metadata or {}).get("title"),
                content_hash=(chunk.metadata or {}).get("project_doc_content_hash"),
                mtime_ns=(chunk.metadata or {}).get("project_doc_mtime_ns"),
                stale=(
                    normalize_doc_path((chunk.metadata or {}).get("project_doc_path"))
                    in stale_paths
                ),
                doc_scope=(chunk.metadata or {}).get("doc_scope") or "project",
                module_id=(chunk.metadata or {}).get("module_id"),
                module_name=(chunk.metadata or {}).get("module_name"),
                module_path=(chunk.metadata or {}).get("module_path"),
                module_type=(chunk.metadata or {}).get("module_type"),
                description=(chunk.metadata or {}).get("project_doc_description"),
                authority=(chunk.metadata or {}).get("project_doc_authority"),
                lifecycle_status=(chunk.metadata or {}).get("project_doc_lifecycle_status"),
                impact_policy=(chunk.metadata or {}).get("project_doc_impact_policy"),
                project_identity=(chunk.metadata or {}).get("project_identity"),
            )
            for chunk in chunks
        ]
        next_actions: list[dict[str, Any]] = []
        next_action: dict[str, Any] = {}
        requires_confirmation = False
        confirmation_reason = None
        arguments_patch: dict[str, Any] = {}
        preflight_diagnostics: dict[str, Any] = {}
        if dropped_placeholder_chunks:
            preflight_diagnostics["dropped_placeholder_project_docs"] = dropped_placeholder_chunks
        if exact_document_fallback_used:
            preflight_diagnostics["exact_document_index_fallback"] = True
        if preflight_inspect:
            next_action = preflight_inspect.next_action
            requires_confirmation = True
            confirmation_reason = preflight_inspect.confirmation_reason
            arguments_patch = preflight_inspect.arguments_patch
            next_actions.extend(preflight_inspect.recommended_next_actions)
            preflight_diagnostics = preflight_inspect.diagnostics
        elif stale_sources:
            next_action, requires_confirmation, confirmation_reason, arguments_patch, _, _ = self._project_docs_structured_next_action(
                reason_code="project_docs_stale",
                root=root,
                query=query,
            )
            next_actions.append({
                "tool": "sync_project_docs",
                "requires_confirmation": False,
                "arguments_patch": self._project_sync_arguments(root),
                "reason": "Some indexed project docs are stale; reconcile before relying on repo-specific answers.",
            })
        if results:
            status = "stale" if stale_sources else ("confirmation_required" if preflight_inspect else "success")
            reason_code = preflight_inspect.reason_code if preflight_inspect else ("project_docs_stale" if stale_sources else "project_docs_ready")
            reason = "project_docs_stale" if stale_sources else ("project_docs_preflight_confirmation_required" if preflight_inspect else None)
            return ProjectDocsResult(
                project_path=str(root),
                query=query,
                resolved_evidence_path=evidence_path,
                status=status,
                reason_code=reason_code,
                next_action=next_action,
                requires_confirmation=requires_confirmation,
                confirmation_reason=confirmation_reason,
                arguments_patch=arguments_patch,
                reason=reason,
                answer_available=True,
                results=results,
                warnings=metadata.warnings,
                candidate_sources=candidate_sources,
                indexed_sources=result_indexed_sources or indexed_sources,
                stale_sources=stale_sources,
                ignored_sources=ignored_sources,
                source_state_guidance=self._source_state_guidance(),
                diagnostics=preflight_diagnostics,
                next_actions=next_actions,
                message=f"Returned {len(results)} project docs result(s)." + (" Project docs preflight requires confirmation before sync/reconcile." if preflight_inspect else (" Some indexed project docs are stale." if stale_sources else "")),
            )
        if preflight_inspect:
            return _confirmation_required_result(
                status="stale" if stale_sources else "confirmation_required",
                reason="project_docs_stale" if stale_sources else "project_docs_preflight_confirmation_required",
            )
        reason_code = (
            "project_docs_stale"
            if stale_sources
            else "resolved_document_no_witness"
            if evidence_path
            else "no_project_docs_results"
        )
        if stale_sources:
            next_action, requires_confirmation, confirmation_reason, arguments_patch, _, _ = self._project_docs_structured_next_action(
                reason_code="project_docs_stale",
                root=root,
                query=query,
            )
        else:
            next_action = {"type": "inspect_project_docs", "tool": "inspect_project_docs"}
            requires_confirmation = False
            confirmation_reason = None
            arguments_patch = {"project_path": str(root)}
        return ProjectDocsResult(
            project_path=str(root),
            query=query,
            resolved_evidence_path=evidence_path,
            status="stale" if stale_sources else "no_results",
            reason_code=reason_code,
            next_action=next_action,
            requires_confirmation=requires_confirmation,
            confirmation_reason=confirmation_reason,
            arguments_patch=arguments_patch,
            reason=(
                "project_docs_stale"
                if stale_sources
                else "resolved_document_no_witness"
                if evidence_path
                else "no_project_docs_results"
            ),
            answer_available=False,
            warnings=metadata.warnings,
            candidate_sources=candidate_sources,
            indexed_sources=indexed_sources,
            stale_sources=stale_sources,
            ignored_sources=ignored_sources,
            source_state_guidance=self._source_state_guidance(),
            next_actions=[{
                "tool": "sync_project_docs" if stale_sources else "inspect_project_docs",
                "requires_confirmation": False,
                "arguments_patch": (
                    self._project_sync_arguments(root)
                    if stale_sources
                    else {"project_path": str(root)}
                ),
                "reason": "Project docs are stale; sync and retry." if stale_sources else "Project docs are indexed, but no indexed project docs matched this query. Inspect candidates or refine the query.",
            }],
            message=(
                f"Indexed document {evidence_path!r} was resolved, but no bounded witness matched the requested requirements."
                if evidence_path and not stale_sources
                else "Indexed project docs exist, but no results matched this query."
            ) + (" Some indexed docs are stale." if stale_sources else ""),
        )
