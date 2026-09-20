"""ProjectDocsService implementation shard 3."""
from __future__ import annotations

from ._project_docs_service_shared import *  # noqa: F401,F403
from docmancer.core.models import RetrievedChunk
from ._project_docs_exact_document import (
    _EXACT_DOCUMENT_FALLBACK_LIMIT,
    _exact_document_index_chunks,
)
from docmancer.docs.application.context_selection import merge_query_matches, select_context_candidates
from docmancer.docs.domain.documentation_query_plan import (
    DocumentationLookup,
    DocumentationQueryPlan,
)
from docmancer.docs.domain.evidence_qualification import (
    derived_parent_trace,
    qualify_evidence,
)
from docmancer.docs.domain.project_doc_ranking import condition_lead_priority
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
from docmancer.docs.application.retrieval_need_support import apply_retrieval_need_witness
from docmancer.docs.domain.query_terms import (
    documentation_query_terms,
    documentation_technical_anchors,
    query_constraint_roles,
    supplemental_query_is_useful,
)


from .reference_query_tagging import _tag_retrieval_query
from .source_reference_evidence import SourceReferenceContext

_INTERNAL_DIAGNOSTIC_LIMIT = 32


def _candidate_admission_priority(query: str, chunk: Any) -> tuple[bool, int]:
    """Keep qualified condition-bearing evidence inside the bounded pool.

    This is only an admission ordering preference. It cannot qualify a chunk,
    alter source policy, or increase the candidate/query budget.
    """
    qualified = bool((chunk.metadata or {}).get("retrieval_query_ids"))
    return (
        not qualified,
        -condition_lead_priority(query, str(getattr(chunk, "text", "") or "")),
    )


def _diagnostic_candidate_id(chunk: Any) -> dict[str, str]:
    metadata = chunk.metadata or {}
    return {
        key: value
        for key, value in {
            "stable_chunk_id": str(metadata.get("stable_chunk_id") or ""),
            "document_id": str(metadata.get("document_id") or chunk.source or ""),
            "parent_logical_id": str(metadata.get("parent_logical_id") or ""),
        }.items()
        if value
    }


def _retrieval_stage_diagnostics(
    plan: DocumentationQueryPlan, candidates: list[Any],
) -> dict[str, Any]:
    rows = []
    outcomes = []
    for chunk in candidates[:_INTERNAL_DIAGNOSTIC_LIMIT]:
        identity = _diagnostic_candidate_id(chunk)
        if identity:
            rows.append(identity)
        matches = (chunk.metadata or {}).get("retrieval_query_matches") or {}
        for query_id, trace in matches.items():
            if not isinstance(trace, dict):
                continue
            outcomes.append({
                **identity,
                "query_id": str(query_id),
                "outcome": (
                    "qualified" if trace.get("qualified") is True else
                    "rejected" if trace.get("qualified") is False else
                    "unclassified"
                ),
                "reason": str(trace.get("qualification_reason") or trace.get("reason_code") or trace.get("reason") or "unclassified")[:120],
            })
            if len(outcomes) >= _INTERNAL_DIAGNOSTIC_LIMIT:
                break
        if len(outcomes) >= _INTERNAL_DIAGNOSTIC_LIMIT:
            break
    return {
        "planned_query_ids": [
            str(item.query_id) for item in plan.queries[:_INTERNAL_DIAGNOSTIC_LIMIT]
        ],
        "retrieved_candidates": rows,
        "qualification_outcomes": outcomes,
    }



def _starts_markdown_list_item(text: str) -> bool:
    value = str(text or "").lstrip()
    if value.startswith(("- ", "+ ", "* ")):
        return True
    first = value.split(None, 1)[0] if value else ""
    return len(first) > 1 and first[:-1].isdigit() and first[-1] in ".)"


def _structured_continuation_route(anchor: Any, candidate: Any) -> str | None:
    """Return a provenance-only continuation route for adjacent retrieval chunks."""
    left = anchor.metadata or {}
    right = candidate.metadata or {}
    left_span = left.get("char_span") or ()
    right_span = right.get("char_span") or ()
    left_parent = str(left.get("parent_logical_id") or "")
    right_parent = str(right.get("parent_logical_id") or "")
    if (
        len(left_span) != 2 or len(right_span) != 2
        or right_span[0] != left_span[1]
        or not left_parent or left_parent != right_parent
        or candidate.source != anchor.source
    ):
        return None
    left_atom = str(left.get("atom_id") or "")
    right_atom = str(right.get("atom_id") or "")
    if left_atom and left_atom == right_atom:
        return "same_atom_continuation"
    if (
        str(left.get("atom_type") or "") == "list"
        and str(right.get("atom_type") or "") == "list"
        and not _starts_markdown_list_item(str(getattr(candidate, "text", "") or ""))
    ):
        return "same_list_item_continuation"
    return None


def _qualify_same_atom_continuations(chunks: list[Any], query_id: str) -> list[Any]:
    """Carry one qualified canonical probe into its immediate structural continuation.

    Same-atom children retain the historical route. A packed list fragment may
    also bridge an atom-id change only when source/parent spans are contiguous
    and the next list chunk does not start a new list item. This is provenance,
    not semantic proof, and never derives public/original query coverage.
    """
    result = list(chunks)
    anchors = []
    for chunk in result:
        metadata = chunk.metadata or {}
        trace = (metadata.get("retrieval_query_matches") or {}).get(query_id) or {}
        span = metadata.get("char_span") or ()
        if trace.get("qualified") is True and len(span) == 2:
            anchors.append(chunk)
    for anchor in anchors:
        anchor_meta = anchor.metadata or {}
        for index, candidate in enumerate(result):
            route = _structured_continuation_route(anchor, candidate)
            if route is None:
                continue
            metadata = candidate.metadata or {}
            matches = dict(metadata.get("retrieval_query_matches") or {})
            current = dict(matches.get(query_id) or {})
            if current.get("qualified") is True:
                continue
            anchor_trace = dict(
                (anchor_meta.get("retrieval_query_matches") or {}).get(query_id) or {}
            )
            if anchor_trace.get("qualified") is not True:
                continue
            derived = dict(anchor_trace)
            derived.update({
                "qualified": True,
                "qualification_reason": route,
                "qualification_route": route,
                "coverage_kind": "derived",
                "coverage_kinds": ["derived"],
                "derived_from_stable_chunk_id": str(anchor_meta.get("stable_chunk_id") or ""),
                "matched_terms": [],
                "body_matched_terms": [],
                "match_ratio": 0.0,
            })
            matches[query_id] = derived
            updated = dict(metadata)
            updated["retrieval_query_matches"] = matches
            updated["retrieval_query_ids"] = tuple(
                key for key, value in matches.items() if value.get("qualified") is True
            )
            result[index] = candidate.model_copy(update={"metadata": updated})
            break
    return result
def _merge_same_atom_continuations(
    chunks: list[Any], query_id: str, *, max_chars: int = 1024,
) -> list[Any]:
    """Reassemble one immediate structured continuation within the existing cap."""
    result = list(chunks)
    remove: set[int] = set()
    for index, anchor in enumerate(tuple(result)):
        if index in remove:
            continue
        metadata = dict(anchor.metadata or {})
        trace = (metadata.get("retrieval_query_matches") or {}).get(query_id) or {}
        span = metadata.get("char_span") or ()
        if trace.get("qualified") is not True or len(span) != 2:
            continue
        for other_index, candidate in enumerate(result):
            if other_index == index or other_index in remove:
                continue
            route = _structured_continuation_route(anchor, candidate)
            if route is None:
                continue
            other = candidate.metadata or {}
            other_trace = (other.get("retrieval_query_matches") or {}).get(query_id) or {}
            other_span = other.get("char_span") or ()
            if (
                other_trace.get("qualification_route") != route
                or other_trace.get("qualified") is not True
                or len(other_span) != 2
            ):
                continue
            text = f"{anchor.text}{candidate.text}"
            if len(text) > max_chars:
                continue
            metadata["char_span"] = [span[0], other_span[1]]
            for field in ("byte_span", "line_span"):
                left = metadata.get(field) or ()
                right = other.get(field) or ()
                if len(left) == 2 and len(right) == 2:
                    metadata[field] = [left[0], right[1]]
            metadata["reassembled_from_stable_chunk_ids"] = [
                str(metadata.get("stable_chunk_id") or ""),
                str(other.get("stable_chunk_id") or ""),
            ]
            metadata["display_token_estimate"] = int(metadata.get("display_token_estimate") or 0) + int(other.get("display_token_estimate") or 0)
            metadata["token_estimate"] = int(metadata.get("token_estimate") or 0) + int(other.get("token_estimate") or 0)
            result[index] = anchor.model_copy(update={"text": text, "metadata": metadata})
            remove.add(other_index)
            break
    return [chunk for index, chunk in enumerate(result) if index not in remove]

def _qualify_candidate_lookups(
    chunks: list[Any], plan: DocumentationQueryPlan, *,
    expected_project_identity: str, lifecycle_intent: str,
) -> list[Any]:
    """Check independent public lookups before admission, across discovery lanes.

    No extra retrieval is performed and no original/parent coverage is derived.
    Existing discovery traces keep their scores; a cross-check has no BM25 score.
    """
    lookups = [item for item in plan.queries
               if item.origin in {"original", "host_lookup", "retrieval_need"} and not item.public_parent_query_id]
    result = []
    for chunk in chunks:
        for lookup in lookups:
            if lookup.query_id in (chunk.metadata or {}).get("retrieval_query_matches", {}):
                continue
            chunk = _tag_retrieval_query(
                [chunk], lookup.query_id, lookup.text, lookup,
                expected_project_identity=expected_project_identity,
                lifecycle_intent=lifecycle_intent,
            )[0]
            trace = chunk.metadata["retrieval_query_matches"][lookup.query_id]
            for field in ("bm25_cost", "field_matches", "mode"):
                trace.pop(field, None)
            trace.update(lexical_score=0.0, qualification_route="cross_lane_body",
                         query_term_count=len(trace.get("query_terms") or ()))
            if lookup.origin == "original": trace["admission_only"] = True
        result.append(chunk)
    return result
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
        internal_diagnostics: dict[str, Any] | None = None,
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
        reference_context = SourceReferenceContext(getattr(agent, "store", None), question=query,
            queries=documentation_query_plan.queries, filters=filters, lifecycle_intent=answer_lifecycle_intent)
        lookup_by_id = {
            item.query_id: item for item in documentation_query_plan.queries
        }
        lookup_query_ids = {
            item.text: item.query_id
            for item in documentation_query_plan.queries
            if item.origin in {"exact_anchor", "exact_path", "host_lookup", "canonical_intent", "concept_alias", "retrieval_hint", "lexical_topic"}
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
        # The query plan owns the optional lookup budget. Do not append the
        # raw requirements again: that resurrects rejected/duplicate hints and
        # turns a grouped replacement into additional internal requests.
        planned_lookup_queries = tuple(
            item.text for item in documentation_query_plan.queries
            if item.origin in {"exact_anchor", "exact_path", "host_lookup", "canonical_intent", "concept_alias", "retrieval_hint", "lexical_topic"}
        )
        supplemental_queries = tuple(dict.fromkeys(
            text for text in (
                *planned_lookup_queries,
                *probe_queries,
            ) if supplemental_query_is_useful(text)
        ))[:12]
        next_supplemental_id = 1
        for supplemental_query in supplemental_queries:
            if supplemental_query in lookup_query_ids:
                continue
            lookup_query_ids[supplemental_query] = (
                f"query-supplemental-{next_supplemental_id}"
            )
            next_supplemental_id += 1
        supplemental_budget = min(budget, max(128, min(400, budget // 4)))

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

        _retrieve = _run
        def _run(text, **kwargs):
            return reference_context.prepare(_retrieve(text, **kwargs), text)

        chunks = _run(
            query,
            query_limit=effective_limit,
            query_budget=budget,
            query_expand=effective_expand,
            query_filters=filters,
        )
        chunks = _tag_retrieval_query(
            chunks, "query-original", query, lookup_by_id.get("query-original"),
            expected_project_identity=filters["project_identity"], lifecycle_intent=answer_lifecycle_intent,
        )
        chunks = _tag_retrieval_query(
            chunks, exact_path_query_id, evidence_path,
            lookup_by_id.get(exact_path_query_id or ""),
            expected_project_identity=filters["project_identity"], lifecycle_intent=answer_lifecycle_intent,
        )
        if exact_path_query_id:
            for anchor_lookup in documentation_query_plan.queries:
                if anchor_lookup.origin == "exact_anchor":
                    chunks = _tag_retrieval_query(
                        chunks,
                        anchor_lookup.query_id,
                        anchor_lookup.text,
                        anchor_lookup,
                        expected_project_identity=filters["project_identity"], lifecycle_intent=answer_lifecycle_intent,
                    )
        authoritative_chunks = _run(
            query,
            query_limit=max(effective_limit, 20),
            query_budget=budget,
            query_expand=effective_expand or "page",
            query_filters={**filters, "authority": "source_of_truth"},
        )
        authoritative_chunks = _tag_retrieval_query(
            authoritative_chunks, "query-original", query,
            lookup_by_id.get("query-original"),
            expected_project_identity=filters["project_identity"], lifecycle_intent=answer_lifecycle_intent,
        )
        authoritative_chunks = _tag_retrieval_query(
            authoritative_chunks, exact_path_query_id, evidence_path,
            lookup_by_id.get(exact_path_query_id or ""),
            expected_project_identity=filters["project_identity"], lifecycle_intent=answer_lifecycle_intent,
        )
        if exact_path_query_id:
            for anchor_lookup in documentation_query_plan.queries:
                if anchor_lookup.origin == "exact_anchor":
                    authoritative_chunks = _tag_retrieval_query(
                        authoritative_chunks,
                        anchor_lookup.query_id,
                        anchor_lookup.text,
                        anchor_lookup,
                        expected_project_identity=filters["project_identity"], lifecycle_intent=answer_lifecycle_intent,
                    )
        same_atom_canonical_texts = {
            alias.text
            for alias in build_project_retrieval_aliases(query)
            if alias.intent_id == "fail_closed_workflow"
        }
        supplemental_chunks_by_query = {}
        for supplemental_query in supplemental_queries:
            lookups = [item for item in documentation_query_plan.queries if item.text == supplemental_query]
            public_lookup = requirements is not None and any(item.origin == "host_lookup" for item in lookups)
            # Public lookups need the same pre-qualification candidate window
            # as the original question; projection owns the public budget.
            preserve_canonical_neighbors = any(
                item.origin == "canonical_intent"
                and item.text in same_atom_canonical_texts
                for item in lookups
            )
            lane = _run(
                supplemental_query,
                query_limit=effective_limit if public_lookup else 4,
                query_budget=(
                    budget if public_lookup else
                    min(budget, max(800, supplemental_budget))
                    if preserve_canonical_neighbors else supplemental_budget
                ),
                query_expand="adjacent" if preserve_canonical_neighbors else "none",
                query_filters=filters,
            )
            if not lookups:
                lane = _tag_retrieval_query(
                    lane, lookup_query_ids.get(supplemental_query), supplemental_query,
                    expected_project_identity=filters["project_identity"], lifecycle_intent=answer_lifecycle_intent,
                )
            for lookup in lookups:
                lane = _tag_retrieval_query(
                    lane, lookup.query_id, lookup.text, lookup,
                    expected_project_identity=filters["project_identity"], lifecycle_intent=answer_lifecycle_intent,
                )
                if lookup.origin == "canonical_intent":
                    lane = _qualify_same_atom_continuations(lane, lookup.query_id)
                    lane = _merge_same_atom_continuations(lane, lookup.query_id)
            supplemental_chunks_by_query[supplemental_query] = lane
        queries_by_origin: dict[str, list[list[Any]]] = {}
        for item in documentation_query_plan.queries:
            lane = supplemental_chunks_by_query.get(item.text)
            if lane:
                queries_by_origin.setdefault(item.origin, []).append(lane)
        candidates = select_context_candidates([
            [
                *queries_by_origin.get("exact_path", []),
                *queries_by_origin.get("exact_anchor", []),
                *queries_by_origin.get("lexical_topic", []),
            ],
            [[*authoritative_chunks, *chunks]],
            queries_by_origin.get("host_lookup", []),
            [
                *queries_by_origin.get("canonical_intent", []),
                *queries_by_origin.get("concept_alias", []),
                *queries_by_origin.get("retrieval_hint", []),
            ],
        ])
        # Cross-check selected candidates without extra retrieval.
        candidates = _qualify_candidate_lookups(
            candidates, documentation_query_plan,
            expected_project_identity=filters["project_identity"],
            lifecycle_intent=answer_lifecycle_intent,
        )
        candidates.sort(key=lambda chunk: _candidate_admission_priority(query, chunk))
        if internal_diagnostics is not None:
            internal_diagnostics.update(
                _retrieval_stage_diagnostics(documentation_query_plan, candidates)
            )
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

        internal_retrieval_diagnostics: dict[str, Any] = {}
        chunks = self.query_project_docs(
            str(root), query, tokens=tokens, limit=limit, expand=expand,
            scope=query_scope, module_path=resolved_module_path, evidence_path=evidence_path,
            requirements=requirements,
            lookup_queries=lookup_queries,
            documentation_query_plan=documentation_query_plan,
            internal_diagnostics=internal_retrieval_diagnostics,
        )
        current_by_source = {str(item.get("source")): item for item in indexed_sources if item.get("source")}
        current_by_exact_path = {str(item["path"]): item for item in indexed_sources if item.get("path")}
        path_groups: dict[str, list[Any]] = {}
        for item in indexed_sources:
            if item.get("path"):
                path_groups.setdefault(normalize_doc_path(item["path"]), []).append(item)
        current_by_path = {path: items[0] for path, items in path_groups.items() if len(items) == 1}
        exact_document_fallback_used = False
        if (
            evidence_path
            and (current_by_exact_path.get(evidence_path) or current_by_path.get(normalize_doc_path(evidence_path)))
        ):
            exact_source = current_by_exact_path.get(evidence_path) or current_by_path[normalize_doc_path(evidence_path)]
            exact_chunks = _exact_document_index_chunks(
                self._agent_instance(),
                root=root,
                evidence_path=str(exact_source.get("path") or evidence_path),
                indexed_source=str(exact_source.get("source") or ""),
                requirements=requirements,
            )
            # Stored sections bypass the normal query lanes. Qualify them against
            # the same plan rather than attributing only the document path: a path
            # match cannot stand in for the requested topic or exact identifier.
            exact_plan = documentation_query_plan or build_documentation_query_plan(
                query, lookup_queries=lookup_queries, explicit_path=evidence_path,
                requirements=requirements,
            )
            exact_filters = {"project_path": str(root), "project_identity": self._repository_identity(root), "source_class": "project_file"}
            if query_scope: exact_filters["doc_scope"] = query_scope
            if resolved_module_path: exact_filters["module_path"] = resolved_module_path
            exact_context = SourceReferenceContext(self._agent_instance().store, question=query,
                queries=exact_plan.queries, filters=exact_filters,
                lifecycle_intent=str(getattr(requirements, "lifecycle_intent", "") or lifecycle_intent(query)))
            exact_chunks = exact_context.prepare(exact_chunks)
            for lookup in exact_plan.queries:
                exact_chunks = _tag_retrieval_query(
                    exact_chunks, lookup.query_id, lookup.text, lookup=lookup,
                    expected_project_identity=self._repository_identity(root),
                    lifecycle_intent=str(getattr(requirements, "lifecycle_intent", "") or lifecycle_intent(query)),
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
            current_source = (current_by_source.get(str(chunk.source)) or current_by_exact_path.get(str(chunk_path))
                or current_by_path.get(normalized_chunk_path))
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
                "freshness": metadata_for_chunk.get("freshness") or "current",
                "index_freshness": metadata_for_chunk.get("index_freshness") or "synchronized",
                "lifecycle_status": metadata_for_chunk.get("project_doc_lifecycle_status") or metadata_for_chunk.get("lifecycle_status") or "active",
                "risk_flags": list(metadata_for_chunk.get("risk_flags") or ()),
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
        if internal_retrieval_diagnostics:
            preflight_diagnostics["same_call_pipeline"] = internal_retrieval_diagnostics
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
            preflight_diagnostics = {
                **preflight_inspect.diagnostics,
                **({"same_call_pipeline": internal_retrieval_diagnostics}
                   if internal_retrieval_diagnostics else {}),
            }
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
