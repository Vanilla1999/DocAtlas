"""UnifiedDocsContextService implementation shard 1."""
from __future__ import annotations

from ._unified_context_service_shared import *  # noqa: F401,F403


_MODULE_RECOVERY_REASON_CODES = frozenset({
    "module_ambiguous", "module_not_found", "no_module_docs",
})


def _project_module_recovery_metadata(
    project_result: Any,
    *,
    module: str | None,
    module_path: str | None,
) -> tuple[str | None, list[dict[str, str]]]:
    """Return bounded module-recovery metadata already discovered by Project Docs."""

    project_docs = getattr(project_result, "project_docs", None)
    reason = str(getattr(project_docs, "reason_code", None) or "").strip()
    if not reason and str(getattr(project_result, "status", "")) in _MODULE_RECOVERY_REASON_CODES:
        reason = str(project_result.status)
    if reason not in _MODULE_RECOVERY_REASON_CODES:
        return None, []

    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    requested_name = str(module or "").strip()
    for source in getattr(project_docs, "candidate_sources", ()) or ():
        if not isinstance(source, dict):
            continue
        candidate_path = str(source.get("module_path") or "").strip()
        if not candidate_path or candidate_path in seen:
            continue
        if reason == "module_ambiguous" and requested_name and not module_path:
            if requested_name not in {
                str(source.get("module_name") or "").strip(),
                str(source.get("module_id") or "").strip(),
            }:
                continue
        seen.add(candidate_path)
        candidate = {"module_path": candidate_path}
        for key in ("module_name", "module_type"):
            value = str(source.get(key) or "").strip()
            if value:
                candidate[key] = value
        candidates.append(candidate)
        if len(candidates) >= 8:
            break
    return reason, candidates


class _UnifiedDocsContextServicePart01:
    def __init__(self, service: Any):
        self.service = service

    def get_docs_context(
        self,
        question: str,
        *,
        project_path: str | None = None,
        library: str | None = None,
        libraries: list[str] | None = None,
        ecosystem: str | None = None,
        version: str | None = None,
        source_type: str | None = None,
        docs_url: str | None = None,
        module: str | None = None,
        module_path: str | None = None,
        scope: str | None = None,
        mode: str | None = None,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
        prepare_project_docs: bool | None = None,
        allow_network: bool | None = None,
        allow_latest_fallback: bool | None = None,
        force_refresh: bool | None = None,
        prefetch_auto: bool | None = None,
        details: bool | None = None,
        response_style: str | None = None,
        mutation_intent: MutationIntentContract | None = None,
    ) -> UnifiedDocsContextResult:
        response_style = validate_response_style(response_style)
        mutation_intent = mutation_intent or build_mutation_intent(question)
        mode_requested = (mode or "auto").lower()
        prepare_project_docs = True if prepare_project_docs is None else bool(prepare_project_docs)
        allow_network = bool(allow_network) if allow_network is not None else False
        allow_latest_fallback = bool(allow_latest_fallback) if allow_latest_fallback is not None else False
        prefetch_auto_val = bool(prefetch_auto) if prefetch_auto is not None else False
        effective_allow_network = allow_network or prefetch_auto_val
        force_refresh = bool(force_refresh) if force_refresh is not None else False
        details = bool(details) if details is not None else False
        libs = self._libraries(library, libraries)

        invalid = self._validate(question, project_path, libs, mode_requested)
        if invalid:
            return invalid

        mode_selected, reason_code = self._select_mode(mode_requested, project_path, libs)
        routing = {
            "reason_code": reason_code,
            "project_path_used": bool(project_path),
            "libraries_requested": libs,
            "dependency_detected": False,
        }
        lane_details: dict[str, Any] = {}
        lanes = {
            "project": {"status": "not_requested", "source_count": 0},
            "library": {"status": "not_requested", "source_count": 0, "canonical_ids": []},
            "dependency": {"status": "not_requested", "source_count": 0},
        }
        context_pack: list[dict[str, Any]] = []
        warnings: list[Any] = []
        next_actions: list[Any] = []
        pending_lane_results: list[Any] = []
        exact_version: dict[str, Any] | None = None

        bootstrap = None
        project_preflight_pending = None
        if prepare_project_docs and project_path and mode_selected in {"project", "mixed", "dependency"}:
            bootstrap = self.service.bootstrap_project_docs(project_path, question=question)
            lane_details["project_bootstrap"] = self._to_dict(bootstrap)
            bootstrap_reason = getattr(bootstrap, "reason_code", None) or "project_docs_confirmation_required"
            if getattr(bootstrap, "requires_confirmation", False) and "dependency_docs" not in bootstrap_reason:
                project_recovery_action = self._project_index_recovery_action(bootstrap, project_path)
                if mode_selected == "project" and project_recovery_action:
                    return self._confirmation_result(
                        question=question,
                        mode_requested=mode_requested,
                        mode_selected=mode_selected,
                        routing=routing,
                        reason_code=bootstrap_reason,
                        confirmation_reason=getattr(bootstrap, "confirmation_reason", None),
                        next_action=project_recovery_action,
                        arguments_patch=project_recovery_action["arguments_patch"],
                        lanes=lanes,
                        lane_details=lane_details if details else {},
                        warnings=list(getattr(bootstrap, "warnings", []) or []),
                    )
                if self._can_return_partial_project_context(bootstrap):
                    project_preflight_pending = bootstrap
                    warnings.append({
                        "code": "project_docs_preflight_partial_context",
                        "message": "Project docs preflight requires confirmation; returning indexed project context as partial guidance without syncing/reconciling docs.",
                    })
                else:
                    return self._confirmation_result(
                        question=question,
                        mode_requested=mode_requested,
                        mode_selected=mode_selected,
                        routing=routing,
                        reason_code=bootstrap_reason,
                        confirmation_reason=getattr(bootstrap, "confirmation_reason", None),
                        next_action=getattr(bootstrap, "next_action", None) or None,
                        arguments_patch=getattr(bootstrap, "arguments_patch", None) or None,
                        lanes=lanes,
                        lane_details=lane_details if details else {},
                        warnings=list(getattr(bootstrap, "warnings", []) or []),
                    )

        project_result = None
        library_results: list[DocsResult] = []

        project_auto = mode_requested == "auto" and bool(project_path) and not libs

        if mode_selected == "project":
            delegated_mode = "auto" if project_auto else "project-only"
            routing["delegated_mode"] = delegated_mode
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, module=module, module_path=module_path, scope=scope, mode=delegated_mode, response_style=response_style, allow_network=effective_allow_network, mutation_intent=mutation_intent)
        elif mode_selected == "dependency":
            if not effective_allow_network and self._dependency_prefetch_needed(project_path):
                lanes["dependency"] = {"status": "confirmation_required", "source_count": 0}
                return self._confirmation_result(
                    question=question,
                    mode_requested=mode_requested,
                    mode_selected=mode_selected,
                    routing=routing,
                    reason_code="dependency_docs_prefetch_required",
                    confirmation_reason="network_fetch",
                    arguments_patch={"allow_network": True},
                    dependency_docs=self._dependency_prefetch_guidance(project_path, question),
                    lanes=lanes,
                    lane_details=lane_details if details else {},
                )
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, library=library, libraries=libraries, ecosystem=ecosystem, version=version, module=module, module_path=module_path, scope=scope, mode="deps-only", response_style=response_style, allow_network=effective_allow_network, mutation_intent=mutation_intent)
        elif mode_selected == "mixed":
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, library=library, libraries=libraries, ecosystem=ecosystem, version=version, module=module, module_path=module_path, scope=scope, mode="auto", response_style=response_style, allow_network=effective_allow_network, mutation_intent=mutation_intent)
            routing["dependency_detected"] = bool(getattr(project_result, "dependency_docs", None))
            explicit_library_results = []
            for lib in libs:
                safe = self._ensure_library_safe(lib, ecosystem, version, source_type, docs_url, force_refresh, effective_allow_network, project_path)
                if safe is not None:
                    explicit_library_results.append(safe)
                    continue
                explicit_library_results.append(self._get_library_docs_with_latest_fallback(lib, question=question, tokens=tokens, ecosystem=ecosystem, version=version, docs_url=docs_url, source_type=source_type, force_refresh=force_refresh, project_path=project_path, allow_network=effective_allow_network, allow_latest_fallback=allow_latest_fallback, response_style=response_style))
            library_results = [item for item in explicit_library_results if isinstance(item, DocsResult)]
            lane_details["library"] = [self._to_dict(item) for item in explicit_library_results]
            confirmations = [item for item in explicit_library_results if isinstance(item, UnifiedDocsContextResult)]
            pending_lane_results.extend(confirmations)
            confirmation = confirmations[0] if confirmations else None
            if confirmation and project_result and project_result.answer_available:
                confirmation_lanes = confirmation.lanes or {}
                lanes["library"] = {
                    **(confirmation_lanes.get("library") or {}),
                    "status": "confirmation_required",
                    "source_count": 0,
                    "requires_confirmation": True,
                    "next_action": confirmation.next_action,
                }
            elif confirmation:
                return confirmation
        elif mode_selected == "library":
            for lib in libs:
                safe = self._ensure_library_safe(lib, ecosystem, version, source_type, docs_url, force_refresh, effective_allow_network, project_path)
                if safe is not None:
                    return safe
                result = self._get_library_docs_with_latest_fallback(lib, question=question, tokens=tokens, ecosystem=ecosystem, version=version, docs_url=docs_url, source_type=source_type, force_refresh=force_refresh, project_path=project_path, allow_network=effective_allow_network, allow_latest_fallback=allow_latest_fallback, response_style=response_style)
                if isinstance(result, UnifiedDocsContextResult):
                    return result
                library_results.append(result)
            lane_details["library"] = [self._to_dict(item) for item in library_results]

        if project_result:
            lane_details["project"] = self._to_dict(project_result)
            project_items = self._normalize_project_context(project_result)
            if project_auto:
                mode_selected = self._infer_project_auto_mode(project_result, project_items)
                routing.update({
                    "reason_code": "project_context_auto",
                    "delegated_mode": routing.get("delegated_mode") or "auto",
                    "evidence_scopes": sorted({item.get("doc_scope") for item in project_items if item.get("doc_scope")}),
                    "dependency_detected": any(item.get("doc_scope") == "dependency" for item in project_items),
                })
            context_pack.extend(project_items)
            operational_reason_code, module_candidates = _project_module_recovery_metadata(
                project_result, module=module, module_path=module_path,
            )
            lanes["project"] = {
                "status": project_result.status,
                "source_count": len([i for i in project_items if i.get("doc_scope") in {"project", "module"}]),
                "reason_code": operational_reason_code or project_result.reason,
                **({"module_candidates": module_candidates} if module_candidates else {}),
            }
            dep_count = len([i for i in project_items if i.get("doc_scope") == "dependency"])
            if dep_count:
                lanes["dependency"] = {"status": getattr(project_result.dependency_docs, "status", "success"), "source_count": dep_count}
            if project_auto:
                if mode_selected == "dependency" and lanes["project"]["source_count"] == 0:
                    lanes["project"] = {"status": "not_requested", "source_count": 0}
                elif mode_selected == "project" and dep_count == 0:
                    lanes["dependency"] = {"status": "not_requested", "source_count": 0}
            warnings.extend(project_result.warnings or [])
            next_actions.extend(project_result.next_actions or [])
            pending_lane_results.append(project_result)

        for result in library_results:
            library_items = self._library_context_pack(result)
            context_pack.extend(library_items)
            lanes["library"] = {
                "status": self._merge_lane_status(lanes["library"].get("status"), result.status),
                "source_count": int(lanes["library"].get("source_count") or 0) + len(library_items),
                "canonical_ids": [*lanes["library"].get("canonical_ids", []), result.library_id],
            }
            warnings.extend(result.warnings or [])
            next_actions.extend(result.next_actions or [])
            exact_version = exact_version or self._exact_version(result, allow_latest_fallback)

        context_pack, contamination, deduplication = self._dedupe_and_guard(context_pack, libs, project_path)
        lane_priority = self._lane_priority_for(mode_selected)
        context_pack, snippet_fallback = self._augment_snippet_first_context(
            context_pack,
            question=question,
            response_style=response_style,
            lane_priority=lane_priority,
            library_results=library_results,
            libs=libs,
            tokens=tokens,
            ecosystem=ecosystem,
            version=version,
            docs_url=docs_url,
            source_type=source_type,
            project_path=project_path,
        )
        if snippet_fallback:
            context_pack, contamination, deduplication = self._dedupe_and_guard(context_pack, libs, project_path)
            routing["snippet_first_fallback"] = snippet_fallback
        context_pack, content_trust_warnings = annotate_context_pack(context_pack, repository_root=project_path)
        warnings.extend(content_trust_warnings)
        self._refresh_lane_counts(lanes, context_pack)
        trust_contract = self._trust_contract(context_pack, project_result, library_results)
        source_summary = self._source_summary(context_pack, trust_contract)
        snippet_presentation = build_snippet_presentation(
            context_pack,
            question=question,
            response_style=response_style,
            lane_priority=lane_priority,
            support_decision=(
                library_results[0].support_decision
                if len(library_results) == 1 else None
            ),
            requirements=(
                library_results[0].requirements
                if len(library_results) == 1 else None
            ),
        )
        if snippet_fallback and snippet_presentation.primary_snippet:
            warnings = _without_snippet_not_available(warnings)
        context_available = bool(context_pack)
        support_decision = (
            library_results[0].support_decision
            if len(library_results) == 1 else None
        )
        aggregate_entries: list[tuple[str, str, Any]] = []
        if project_result is not None:
            aggregate_entries.append((
                "project", str(project_result.project_path),
                getattr(project_result, "support_decision", None),
            ))
        aggregate_entries.extend(
            ("library", result.library_id, result.support_decision)
            for result in library_results
        )
        aggregate_selection = None
        if len(aggregate_entries) > 1 and all(
            isinstance(getattr(result, "selection_decision", None), SelectionDecision)
            for result in ([project_result] if project_result is not None else []) + library_results
        ):
            aggregate_selection = aggregate_mixed_selection([
                (
                    lane,
                    identity,
                    getattr(project_result, "selection_decision")
                    if lane == "project" else next(
                        result.selection_decision
                        for result in library_results if result.library_id == identity
                    ),
                )
                for lane, identity, _ in aggregate_entries
            ])
        if library_results:
            decisions = [entry[2] for entry in aggregate_entries]
            answer_supported = bool(
                decisions and all(decision and decision.answer_supported for decision in decisions)
            )
            if aggregate_selection is not None:
                support_decision = aggregate_selection.support_decision
                support_payload = support_decision.as_payload()
                answer_supported = support_decision.answer_supported
            elif len(aggregate_entries) == 1 and support_decision is not None:
                support_payload = support_decision.as_payload()
            else:
                canonical_lanes_missing = len(aggregate_entries) > 1 and aggregate_selection is None
                if canonical_lanes_missing:
                    answer_supported = False
                missing_ids = sorted({
                    item for decision in decisions if decision
                    for item in decision.missing_requirement_ids
                })
                satisfied_ids = sorted({
                    item for decision in decisions if decision
                    for item in decision.satisfied_requirement_ids
                })
                mandatory_ids = sorted({
                    item for decision in decisions if decision
                    for item in decision.mandatory_requirement_ids
                })
                selected_ids = sorted({
                    item for decision in decisions if decision
                    for item in decision.selected_evidence_ids
                })
                missing_ids.extend(
                    f"{lane}:{identity}:canonical_support_decision"
                    for lane, identity, decision in aggregate_entries
                    if decision is None
                )
                missing_ids = sorted(set(missing_ids))
                support_payload = {
                    "support_status": "supported" if answer_supported else "insufficient_evidence",
                    "reason_code": (
                        "canonical_lane_decision_missing" if canonical_lanes_missing else
                        None if answer_supported else
                        "mixed_support_incomplete" if project_result is not None else
                        "multi_library_support_incomplete"
                    ),
                    "missing_requirement_ids": missing_ids,
                    "satisfied_requirement_ids": satisfied_ids,
                    "mandatory_requirement_ids": mandatory_ids,
                    "mandatory_coverage": (
                        min((decision.mandatory_coverage if decision else 0.0 for decision in decisions), default=0.0)
                    ),
                    "selected_evidence_ids": selected_ids,
                    "assignment_hash": None,
                    "decision_hash": None,
                }
        else:
            support_decision = (
                getattr(project_result, "support_decision", None)
                if project_result else None
            )
            answer_supported = bool(
                support_decision and support_decision.answer_supported
            )
            support_payload = (
                support_decision.as_payload()
                if support_decision is not None else {
                    "support_status": "insufficient_evidence",
                    "reason_code": (
                        "canonical_support_decision_missing"
                        if context_available else "no_docs_context_available"
                    ),
                    "missing_requirement_ids": ["canonical_support_decision"] if context_available else [],
                    "satisfied_requirement_ids": [],
                    "mandatory_requirement_ids": [],
                    "mandatory_coverage": 0.0,
                    "selected_evidence_ids": [],
                    "decision_hash": None,
                }
            )
            if (
                support_decision is not None
                and not support_decision.answer_supported
                and project_result is not None
                and (
                    getattr(project_result, "reason", None)
                    or getattr(getattr(project_result, "project_docs", None), "reason_code", None)
                )
                and (
                    not support_payload.get("reason_code")
                    or project_result.reason in {
                        "document_not_indexed", "ambiguous_document_locator",
                    }
                )
            ):
                support_payload["reason_code"] = (
                    project_result.reason or project_result.project_docs.reason_code
                )
        project_delivery_available = bool(
            project_result is None or project_result.answer_available
        )
        answer_available = answer_supported and project_delivery_available
        delivery_decision = DeliveryDecision(
            deliverable=answer_available,
            reason_code=None if answer_available else str(
                support_payload.get("reason_code") or "operational_delivery_blocked"
            ),
        )
        pending_actions = self._collect_pending_actions(pending_lane_results)
        requested_lanes = [name for name, lane in lanes.items() if lane.get("status") != "not_requested"]
        successful_lanes = [name for name, lane in lanes.items() if self._lane_succeeded(lane)]
        pending_confirmation_lanes = [name for name, lane in lanes.items() if lane.get("requires_confirmation") or lane.get("status") == "confirmation_required"]
        failed_lanes = [name for name, lane in lanes.items() if lane.get("status") not in {"not_requested", "success", "partial_success", "confirmation_required"} and not self._lane_succeeded(lane)]
        status = self._aggregate_status(requested_lanes, successful_lanes, pending_confirmation_lanes, failed_lanes)
        reason = support_payload["reason_code"]
        combined_next_actions = [*next_actions, *pending_actions.get("next_actions", [])]
        patch_constraints_action = self._patch_constraints_next_action(question, project_path, mode_selected, mode_requested)
        if patch_constraints_action:
            routing["next_action_reason"] = patch_constraints_action["reason"]
            if patch_constraints_action not in combined_next_actions:
                combined_next_actions.insert(0, patch_constraints_action)
        primary_next_action = pending_actions.get("next_action") or patch_constraints_action

        ingestion_diagnostics = {}
        retrieval_diagnostics = {}
        if project_result:
            project_diagnostics = getattr(project_result, "diagnostics", None) or getattr(project_result, "ingestion_diagnostics", None) or {}
        else:
            project_diagnostics = {}
        for lane_name, lane_payload in [("project", project_diagnostics), ("library", library_results)]:
            if lane_name == "library":
                for lib_result in library_results:
                    lib_diag = getattr(lib_result, "diagnostics", None) or {}
                    if lib_diag:
                        ingestion_diagnostics.setdefault(lane_name, []).append(lib_diag)
                    retrieval_lane_diag = getattr(lib_result, "retrieval_diagnostics", None) or {}
                    if retrieval_lane_diag:
                        retrieval_diagnostics.setdefault(lane_name, []).append(retrieval_lane_diag)
            else:
                if lane_payload:
                    ingestion_diagnostics.setdefault(lane_name, lane_payload)
                    retrieval_lane_diag = getattr(project_result, "retrieval_diagnostics", None) or {}
                    if retrieval_lane_diag:
                        retrieval_diagnostics.setdefault(lane_name, retrieval_lane_diag)

        payload = UnifiedDocsContextResult(
            status=status,
            question=question,
            mode_requested=mode_requested,
            mode_selected=mode_selected,
            routing=routing,
            answer_available=answer_available,
            context_available=context_available,
            answer_supported=answer_supported,
            support_status=support_payload["support_status"],
            missing_requirement_ids=list(support_payload["missing_requirement_ids"]),
            satisfied_requirement_ids=list(support_payload["satisfied_requirement_ids"]),
            mandatory_requirement_ids=list(support_payload["mandatory_requirement_ids"]),
            mandatory_coverage=float(support_payload["mandatory_coverage"]),
            selected_evidence_ids=list(support_payload["selected_evidence_ids"]),
            decision_hash=support_payload["decision_hash"],
            assignment_hash=support_payload.get("assignment_hash"),
            selection_decision=(
                aggregate_selection
                if aggregate_selection is not None else
                library_results[0].selection_decision
                if len(library_results) == 1 else
                getattr(project_result, "selection_decision", None)
                if not library_results and project_result else None
            ),
            support_decision=support_decision,
            delivery_decision=delivery_decision,
            answer_type=getattr(project_result, "answer_type", None) if project_result else None,
            answer_completeness=dict(getattr(project_result, "answer_completeness", None) or {}) if project_result else {},
            disposition=(
                (getattr(project_result, "answer_completeness", None) or {}).get("disposition")
                if project_result else None
            ),
            edit_ready=bool(
                (getattr(project_result, "answer_completeness", None) or {}).get("edit_ready")
                if project_result else answer_supported
            ),
            source_search_status=str(
                (getattr(project_result, "answer_completeness", None) or {}).get(
                    "source_search_status", "not_required"
                ) if project_result else "not_required"
            ),
            context_pack=context_pack,
            lanes=lanes,
            source_summary=source_summary,
            trust_contract=trust_contract,
            exact_version=exact_version,
            reason_code=reason,
            requires_confirmation=bool(pending_actions.get("requires_confirmation")),
            confirmation_reason=pending_actions.get("confirmation_reason"),
            next_action=primary_next_action,
            next_actions=combined_next_actions,
            arguments_patch=pending_actions.get("arguments_patch"),
            warnings=[*warnings, *snippet_presentation.warnings],
            response_style=snippet_presentation.response_style,
            primary_snippet=snippet_presentation.primary_snippet,
            supporting_snippets=snippet_presentation.supporting_snippets,
            primary_snippets=snippet_presentation.primary_snippets,
            primary_snippet_confidence=snippet_presentation.primary_snippet_confidence,
            primary_snippet_selection_reason=snippet_presentation.primary_snippet_selection_reason,
            primary_snippet_alternatives=snippet_presentation.primary_snippet_alternatives,
            snippet_metrics=snippet_presentation.metrics,
            presentation={
                "project_constraints_count": source_summary.get("project", 0),
                "primary_snippet_lane": (snippet_presentation.primary_snippet or {}).get("origin_lane") if snippet_presentation.primary_snippet else None,
                "project_evidence_primary": source_summary.get("project", 0) > 0,
            },
            metrics={"context_pack_items": len(context_pack), "snippet_metrics": snippet_presentation.metrics},
            contamination=contamination,
            deduplication=deduplication,
            lane_details=lane_details if details else {},
            ingestion_diagnostics=ingestion_diagnostics,
            retrieval_diagnostics=retrieval_diagnostics,
            retrieval_routing=(
                project_diagnostics.get("retrieval_routing")
                if isinstance(project_diagnostics, dict) else None
            ),
            requirements=(library_results[0].requirements if len(library_results) == 1 else None),
        )
        return payload

    def _validate(self, question: str, project_path: str | None, libs: list[str], mode: str) -> UnifiedDocsContextResult | None:
        if not question:
            return self._invalid("docs_context_question_missing", {"question": "Your documentation question"}, mode)
        if mode not in {"auto", "project", "library", "dependency", "mixed"}:
            return self._invalid("docs_context_mode_invalid", {"mode": "auto"}, mode, question=question)
        if not project_path and not libs:
            return self._invalid(
                "docs_context_target_missing",
                None,
                mode,
                question=question,
                message="Pass at least one target: project_path, library, or libraries.",
                required_one_of=["project_path", "library", "libraries"],
                examples=[
                    {"project_path": "/repo", "question": question, "mode": "project"},
                    {"library": "flutter_riverpod", "question": question, "mode": "library"},
                    {"project_path": "/repo", "library": "go_router", "question": question, "mode": "mixed"},
                ],
            )
        if mode == "project" and not project_path:
            return self._invalid("project_path_required", {"project_path": "/path/to/repo"}, mode, question=question)
        if mode == "project" and libs:
            return self._invalid("project_mode_cannot_include_library", {"library": None, "libraries": None}, mode, question=question)
        if mode == "library" and not libs:
            return self._invalid("library_required", {"library": "fastapi"}, mode, question=question)
        if mode in {"dependency", "mixed"} and not project_path:
            return self._invalid("project_path_required", {"project_path": "/path/to/repo"}, mode, question=question)
        return None

    def _invalid(
        self,
        reason_code: str,
        arguments_patch: dict[str, Any] | None,
        mode: str,
        *,
        question: str = "",
        message: str | None = None,
        required_one_of: list[str] | None = None,
        examples: list[dict[str, Any]] | None = None,
    ) -> UnifiedDocsContextResult:
        return UnifiedDocsContextResult(
            status="invalid_request",
            question=question,
            mode_requested=mode,
            mode_selected="invalid_request",
            routing={"reason_code": reason_code, "project_path_used": False, "libraries_requested": [], "dependency_detected": False},
            answer_available=False,
            reason_code=reason_code,
            message=message,
            required_one_of=required_one_of or [],
            examples=examples or [],
            next_action={"type": "retry", "arguments_patch": arguments_patch} if arguments_patch else None,
            arguments_patch=arguments_patch,
            lanes=self._empty_lanes(),
            source_summary={"project": 0, "library": 0, "dependency": 0, "rejected": 0, "risky": 0},
            trust_contract={"selected": [], "rejected": [], "risky": []},
            contamination={"detected": False, "dropped_count": 0, "reason_codes": []},
            deduplication={"dropped_count": 0, "reason_codes": []},
        )

    def _select_mode(self, mode: str, project_path: str | None, libs: list[str]) -> tuple[str, str]:
        if mode != "auto":
            return mode, f"explicit_{mode}_mode"
        if project_path and libs:
            return "mixed", "project_and_explicit_library"
        if libs:
            return "library", "explicit_library_only"
        if project_path:
            return "project", "project_path_only"
        return "invalid_request", "docs_context_target_missing"

    @staticmethod
    def _patch_constraints_next_action(question: str, project_path: str | None, mode_selected: str, mode_requested: str) -> dict[str, Any] | None:
        if not project_path or mode_requested == "library" or mode_selected == "library":
            return None
        tokens = _PATCH_TASK_TOKEN_RE.findall(question.lower())
        if not any(token in _PATCH_TASK_TERMS for token in tokens) and not _looks_like_imperative_patch_task(tokens):
            return None
        return {
            "type": "get_patch_constraints",
            "tool": "get_patch_constraints",
            "reason": "patch_like_project_task",
            "arguments_patch": {"project_path": project_path, "task": question},
        }

    @staticmethod
    def _libraries(library: str | None, libraries: list[str] | None) -> list[str]:
        result = []
        if library:
            result.append(library)
        result.extend(libraries or [])
        seen = set()
        return [item for item in result if not (item in seen or seen.add(item))]
