"""ProjectContextService implementation shard 1."""
from __future__ import annotations

from ._project_context_service_shared import *  # noqa: F401,F403


class _ProjectContextServicePart01:
    def __init__(self, facade: Any):
        self.facade = facade

    def get_project_context(
        self,
        project_path: str,
        question: str,
        *,
        tokens: int | None = None,
        limit: int | None = None,
        expand: str | None = None,
        library: str | None = None,
        libraries: list[str] | None = None,
        ecosystem: str | None = None,
        version: str | None = None,
        module: str | None = None,
        module_path: str | None = None,
        scope: str | None = None,
        mode: str = "auto",
        response_style: str | None = None,
        allow_network: bool = False,
        mutation_intent: MutationIntentContract | None = None,
        lookup_queries: tuple[str, ...] = (),
    ) -> ProjectContextResult:
        response_style = validate_response_style(response_style)
        mutation_intent = mutation_intent or build_mutation_intent(question)
        routing_budget_issues: list[str] = []
        routing_stage_observed: dict[str, list[Any]] = {}
        mode = mode.lower()
        if mode not in {"auto", "project-only", "deps-only", "public-docs"}:
            raise ValueError("mode must be one of: auto, project-only, deps-only, public-docs")
        root = Path(project_path).expanduser().resolve()
        intent = classify_project_query_intent(question)
        evidence_path = extract_document_locator(question)
        documentation_query_plan = build_documentation_query_plan(
            question, lookup_queries=lookup_queries, explicit_path=evidence_path,
        )
        mutation_target_paths = tuple(
            target.value
            for target in mutation_intent.requested_targets
            if target.kind == "path"
            and mutation_intent.operation in {"modify", "delete", "rename"}
            and target.value.casefold() != str(mutation_intent.destination or "").casefold()
        )
        patch_request = is_change_request(question)
        canonical_requirements = (
            build_patch_evidence_requirements(mutation_intent.request_plan)
            if patch_request and mutation_intent.request_plan is not None
            else build_requirements(
                question,
                required_evidence_paths=(evidence_path,) if evidence_path else (),
                required_target_paths=mutation_target_paths,
                profile="project_document_answer" if evidence_path else "project_docs_answer",
            )
        )
        metadata = self.facade.read_project_metadata(str(root))
        project_docs = None
        if mode in {"auto", "project-only"}:
            candidate_limit = min(20, max(12, (limit or 4) * 3))
            project_docs_kwargs = {
                "tokens": tokens, "limit": candidate_limit, "expand": expand,
                "module": module, "module_path": module_path, "scope": scope,
                "requirements": canonical_requirements,
            }
            if lookup_queries:
                project_docs_kwargs["lookup_queries"] = lookup_queries
            if evidence_path:
                project_docs_kwargs["evidence_path"] = evidence_path
            project_docs = self.facade.get_project_docs(str(root), question, **project_docs_kwargs)
            if project_docs and project_docs.requires_confirmation and project_docs.confirmation_reason == "project_docs_preflight":
                return _project_docs_preflight_confirmation_result(root=root, question=question, mode=mode, project_docs=project_docs)
            if project_docs and project_docs.results:
                if evidence_path:
                    evidence_path = project_docs.resolved_evidence_path or evidence_path
                    normalized_evidence_path = normalize_doc_path(evidence_path)
                    project_docs = replace(
                        project_docs,
                        results=[
                            chunk for chunk in project_docs.results
                            if normalize_doc_path(chunk.path) == normalized_evidence_path
                        ],
                    )
                project_docs = _inject_broad_architecture_docs(
                    project_docs, root=root, intent=intent, evidence_path=evidence_path,
                    lifecycle_intent_value=canonical_requirements.lifecycle_intent,
                    # The mere presence of an explicit catalog disables guessed
                    # architecture sources. An invalid catalog must fail closed.
                    catalog_authoritative=metadata.docs_catalog_present,
                )
                project_docs = replace(
                    project_docs,
                    results=rerank_project_doc_chunks(
                        project_docs.results,
                        question=question,
                        intent=intent,
                        limit=limit,
                        broad_max_per_source=4 if evidence_path else 2,
                        lifecycle_intent_value=canonical_requirements.lifecycle_intent,
                    ),
                )
                routing_stage_observed["project_docs"] = list(project_docs.results)
                bounded_results, budget_issue = fit_stage_items("project_docs", project_docs.results)
                project_docs = replace(project_docs, results=bounded_results)
                if budget_issue:
                    routing_budget_issues.append(f"project_docs: {budget_issue}")

        explicit_dependency = library or (libraries[0] if libraries else None)
        inferred_dependency = self.dependency_mentioned_in_question(metadata, question)
        selected_dependency = explicit_dependency or inferred_dependency
        explicit_dependency_requested = bool(explicit_dependency or mode in {"deps-only", "public-docs"})
        dependency_docs: DocsResult | None = None
        dependency_confirmation: dict[str, Any] | None = None
        if selected_dependency and mode in {"auto", "deps-only", "public-docs"}:
            if not allow_network:
                dependency_confirmation = {
                    "type": "ask_user_to_fetch_dependency_docs",
                    "tool": "get_project_context",
                    "reason": "dependency_docs_network_fetch_required",
                    "dependency": selected_dependency,
                    "requires_confirmation": True,
                    "confirmation_reason": "network_fetch",
                    "arguments_patch": {
                        "project_path": str(root),
                        "question": question,
                        "library": selected_dependency,
                        "mode": "deps-only" if mode in {"deps-only", "public-docs"} else "auto",
                        "allow_network": True,
                    },
                    "user_message": "Dependency/public documentation may require network fetch. Proceed?",
                }
            else:
                dependency_docs = self.facade.get_docs(
                    selected_dependency,
                    topic=question,
                    tokens=tokens,
                    ecosystem=ecosystem,
                    version=version,
                    project_path=str(root),
                )
                routing_stage_observed["dependency_docs"] = list(dependency_docs.results)
                bounded_results, budget_issue = fit_stage_items("dependency_docs", dependency_docs.results)
                if budget_issue:
                    dependency_docs = replace(dependency_docs, results=bounded_results)
                    routing_budget_issues.append(f"dependency_docs: {budget_issue}")

        warnings = [*(project_docs.warnings if project_docs else [])]
        if dependency_docs:
            warnings.extend(dependency_docs.warnings)
        next_actions = [*(project_docs.next_actions if project_docs else [])]
        if dependency_docs:
            next_actions.extend(_library_next_action(dependency_docs, action) for action in dependency_docs.next_actions)
        if dependency_confirmation:
            next_actions.append(dependency_confirmation)
        requires_confirmation = bool(project_docs and project_docs.requires_confirmation) or bool(dependency_confirmation and explicit_dependency_requested)
        confirmation_reason = project_docs.confirmation_reason if project_docs and project_docs.requires_confirmation else ("network_fetch" if dependency_confirmation and explicit_dependency_requested else None)
        project_docs_blocked = bool(
            project_docs and project_docs.status == "invalid_project_docs_catalog"
        )
        next_action = (
            project_docs.next_action
            if project_docs and (project_docs.requires_confirmation or project_docs_blocked)
            else (dependency_confirmation or {})
        )
        arguments_patch = (
            project_docs.arguments_patch
            if project_docs and (project_docs.requires_confirmation or project_docs_blocked)
            else ({"allow_network": True} if dependency_confirmation else {})
        )
        if mode in {"auto", "project-only"} and project_docs and hasattr(self.facade, "inspect_project_docs"):
            inspection = self.facade.inspect_project_docs(str(root))
            if (
                inspection.reason_code in {"no_project_docs", "architecture_doc_creation_recommended"}
                and not _documentation_gap_actions(next_actions)
            ):
                gap_action = next(
                    (
                        action for action in inspection.recommended_next_actions
                        if action.get("action") == "create_reviewable_project_doc"
                    ),
                    None,
                )
                if gap_action:
                    next_actions.append(gap_action)
        context_pack = project_context_pack(question=question, project_docs=project_docs, dependency_docs=dependency_docs)
        requirements = (
            [
                *[target.value for target in mutation_intent.request_plan.mutation_targets],
                *[target.value for target in mutation_intent.request_plan.preserve_targets],
                *mutation_intent.request_plan.scope_terms,
            ]
            if patch_request and mutation_intent.request_plan is not None
            else extract_project_answer_requirements(question)
        )
        retrieval_route = route_initial_stages(
            question=question,
            mode=mode,
            dependency_requested=bool(selected_dependency),
            project_doc_items=(project_docs.results if project_docs else []),
        )
        routing_record = new_routing_record(
            retrieval_route,
            project_docs_used=bool(project_docs),
            dependency_docs_used=bool(dependency_docs),
        )
        record_stage(
            routing_record, "project_docs",
            status="used" if project_docs else "skipped",
            reason="selected project documentation mode" if project_docs else "project documentation not selected",
            items=(routing_stage_observed.get("project_docs", project_docs.results if project_docs else [])),
        )
        record_stage(
            routing_record, "dependency_docs",
            status="used" if dependency_docs else "skipped",
            reason="selected exact-version dependency documentation" if dependency_docs else "dependency documentation not selected or not available",
            items=(routing_stage_observed.get("dependency_docs", dependency_docs.results if dependency_docs else [])),
        )
        repo_map_items: list[dict[str, Any]] = []
        source_evidence_items: list[dict[str, Any]] = []
        code_graph = None
        code_graph_items: list[dict[str, Any]] = []
        code_graph_error: str | None = None
        if retrieval_route.use_source_evidence:
            observed_source_evidence = build_project_source_evidence(
                root,
                question=question,
                requirements=requirements,
                max_items=max(1, min(12, (limit or 4) * 2)),
                token_budget=_source_evidence_token_budget(tokens),
            )
            source_evidence_items, budget_issue = fit_stage_items("source_evidence", observed_source_evidence)
            if budget_issue:
                routing_budget_issues.append(f"source_evidence: {budget_issue}")
            context_pack.extend(source_evidence_items)
            record_stage(
                routing_record, "source_evidence",
                status="used" if source_evidence_items else "insufficient",
                reason=retrieval_route.source_reason,
                items=observed_source_evidence,
            )
        else:
            record_stage(
                routing_record, "source_evidence", status="skipped",
                reason=retrieval_route.source_reason,
            )
        run_repo_map, repo_reason = should_run_repo_map(retrieval_route, source_evidence_items)
        if run_repo_map:
            observed_repo_map = build_project_repo_map(
                root,
                question=question,
                max_files=max(1, min(8, limit or 4)),
                token_budget=_repo_map_token_budget(tokens),
            )
            repo_map_items, budget_issue = fit_stage_items("repo_map", observed_repo_map)
            if budget_issue:
                routing_budget_issues.append(f"repo_map: {budget_issue}")
            context_pack.extend(repo_map_items)
            record_stage(
                routing_record, "repo_map",
                status="used" if repo_map_items else "insufficient",
                reason=repo_reason,
                items=observed_repo_map,
            )
        else:
            record_stage(routing_record, "repo_map", status="skipped", reason=repo_reason)
        run_code_graph, graph_reason = should_run_code_graph(
            retrieval_route,
            question=question,
            source_items=source_evidence_items,
            repo_map_items=repo_map_items,
        )
        if run_code_graph:
            try:
                code_graph = build_project_code_graph(
                    root,
                    question=question,
                    requirements=requirements,
                    max_files=max(8, min(24, (limit or 4) * 3)),
                    token_budget=_code_graph_build_token_budget(tokens),
                )
                observed_code_graph_items = build_code_graph_context_items(
                    code_graph,
                    question=question,
                    max_items=max(1, min(8, limit or 4)),
                    token_budget=_code_graph_context_token_budget(tokens),
                )
                code_graph_items, budget_issue = fit_stage_items("code_graph", observed_code_graph_items)
                if budget_issue:
                    routing_budget_issues.append(f"code_graph: {budget_issue}")
                context_pack.extend(code_graph_items)
                record_stage(
                    routing_record, "code_graph",
                    status="used" if code_graph_items else "insufficient",
                    reason=graph_reason,
                    items=observed_code_graph_items,
                )
            except Exception as exc:
                from docmancer.docs.application.library_refresh_policy import bounded_exception_diagnostics
                safe = bounded_exception_diagnostics(exc, failure_phase="retrieval", failure_operation="code_graph")
                code_graph_error = safe["exception_message"]
                record_stage(
                    routing_record, "code_graph", status="failed", reason=graph_reason,
                    error=type(exc).__name__,
                )
        else:
            record_stage(routing_record, "code_graph", status="skipped", reason=graph_reason)
        gap_route = route_gap_recovery_stages(
            has_documentation_gap=bool(_documentation_gap_actions(next_actions)),
            repo_map_attempted=run_repo_map,
            code_graph_attempted=run_code_graph,
        )
        gap_repo_map, gap_code_graph = _source_ground_documentation_gap(
            next_actions,
            root=root,
            repo_map=(repo_map_items if run_repo_map else None),
            code_graph=code_graph,
            allow_repo_map_build=gap_route.use_repo_map,
            allow_code_graph_build=gap_route.use_code_graph,
        )
        if _documentation_gap_actions(next_actions):
            if not run_repo_map:
                _, gap_repo_budget_issue = fit_stage_items("repo_map", gap_repo_map)
                if gap_repo_budget_issue:
                    routing_budget_issues.append(f"repo_map: {gap_repo_budget_issue}")
                record_stage(
                    routing_record, "repo_map", status="used" if gap_repo_map else "insufficient",
                    reason=gap_route.repo_map_reason,
                    items=gap_repo_map,
                )
            if not run_code_graph:
                observed_gap_graph_items = (
                    build_code_graph_context_items(
                        gap_code_graph, question=question,
                        max_items=max(1, min(8, limit or 4)),
                        token_budget=_code_graph_context_token_budget(tokens),
                    ) if gap_code_graph is not None else []
                )
                _, gap_graph_budget_issue = fit_stage_items("code_graph", observed_gap_graph_items)
                if gap_graph_budget_issue:
                    routing_budget_issues.append(f"code_graph: {gap_graph_budget_issue}")
                record_stage(
                    routing_record, "code_graph", status="used" if observed_gap_graph_items else "insufficient",
                    reason=gap_route.code_graph_reason,
                    items=observed_gap_graph_items,
                )
        gap_actions = _documentation_gap_actions(next_actions)
        if gap_actions:
            requires_confirmation = True
            confirmation_reason = "repo_write"
            next_action = gap_actions[0]
            arguments_patch = {"project_path": str(root)}
        context_pack, content_trust_warnings = annotate_context_pack(context_pack, repository_root=root)
        warnings.extend(warning["code"] for warning in content_trust_warnings)
        if evidence_path:
            normalized_evidence_path = normalize_doc_path(evidence_path)
            context_pack = [
                item for item in context_pack
                if normalize_doc_path(
                    item.get("path")
                    or ((item.get("source") or {}).get("path") if isinstance(item.get("source"), dict) else None)
                ) == normalized_evidence_path
            ]
        trust_contract = build_project_context_trust_contract(
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            requested_library=selected_dependency,
            mode=mode,
            context_pack=context_pack,
        )
        selection_decision = select_evidence(
            context_pack,
            question=question,
            config=project_docs_selection_config(tokens or 4000),
            trust_contract=trust_contract,
            requirements=canonical_requirements,
        )
        support_decision = selection_decision.support_decision
        # An inferred dependency is an optional recall lane, not authority to
        # suppress a complete project-document answer.  Explicit dependency
        # requests still preserve the confirmation boundary, and an inferred
        # dependency may still request confirmation when project evidence is
        # insufficient.  This prevents package-name collisions (notably the
        # Python package ``mcp`` versus the Docs MCP product surface) from
        # turning a supported local answer into a network-confirmation result.
        # Explicit dependency requests retain their network-confirmation
        # boundary immediately. Inferred dependencies remain advisory while we
        # finish local relevance/completeness/trust checks; only if the local
        # answer ultimately fails do they become a recovery action.
        dependency_confirmation_preblocks_answer = bool(
            dependency_confirmation and explicit_dependency_requested
        )
        answer_outline = build_project_answer_outline(question=question, intent=intent, context_pack=context_pack)
        metrics = project_context_metrics(context_pack=context_pack, project_docs=project_docs, dependency_docs=dependency_docs, intent=intent)
        lane_priority = ["project"] if mode == "project-only" else (["dependency"] if mode in {"deps-only", "public-docs"} else ["project", "dependency"])
        snippet_presentation = build_snippet_presentation(
            context_pack,
            question=question,
            response_style=response_style,
            lane_priority=lane_priority,
        )
        metrics["snippet_metrics"] = snippet_presentation.metrics
        routing_errors = validate_routing_record(routing_record)
        if routing_errors:
            raise ValueError("invalid retrieval routing record: " + "; ".join(routing_errors))
        diagnostics: dict[str, Any] = {
            "query_intent": intent.name,
            "retrieval_routing": routing_record,
        }
        if repo_map_items:
            diagnostics["repo_map"] = source_map_diagnostics(repo_map_items)
        if source_evidence_items:
            diagnostics["source_evidence"] = source_evidence_diagnostics(source_evidence_items)
        if code_graph_items:
            diagnostics["code_graph"] = code_graph_context_diagnostics(code_graph_items)
        if code_graph is not None and (code_graph_items or code_graph.diagnostics.get("status") == "ok"):
            diagnostics.setdefault("code_graph", {"selected_items": 0})["graph"] = _compact_code_graph_diagnostics(code_graph_diagnostics(code_graph))
        if code_graph_error:
            diagnostics["code_graph"] = {"error": code_graph_error, "selected_items": 0}
        if project_docs is not None and hasattr(self.facade, "active_index_diagnostics"):
            diagnostics["active_index"] = self.facade.active_index_diagnostics(str(root))
        if intent.name == "mcp_disambiguation":
            diagnostics["mcp_surfaces"] = [
                {
                    "name": "Docs MCP server",
                    "command": "doc-atlas mcp docs-serve",
                    "purpose": "Serve local/version-aware documentation context to agents.",
                    "preferred_for": ["documentation Q&A", "Context7-style docs", "project docs", "library docs"],
                },
                {
                    "name": "Packs MCP runtime",
                    "command": "doc-atlas mcp packs-serve",
                    "purpose": "Expose version-pinned API action tools from installed packs.",
                    "preferred_for": ["API calls", "agent actions", "installed packs"],
                },
            ]
        relevance_terms = [] if requirements else extract_query_relevance_terms(question, intent=intent)
        source_evidence_answer_available = any(
            item.get("evidence_class") == "source_snippet"
            and _context_has_query_evidence([item], relevance_terms)
            for item in source_evidence_items
        )
        answer_available = bool(project_docs and project_docs.answer_available) or bool(dependency_docs and dependency_docs.results) or source_evidence_answer_available
        if dependency_confirmation_preblocks_answer:
            answer_available = False
        if routing_budget_issues:
            warnings.append("retrieval_stage_budget_exceeded")
            next_actions.append({
                "tool": "get_docs_context",
                "reason": "Narrow the question because a deterministic retrieval-stage budget was exceeded.",
                "arguments_patch": {"question": question, "project_path": str(root)},
            })
        relevance_gate = _query_relevance_gate(
            question=question,
            intent=intent,
            context_pack=context_pack,
            relevance_terms=relevance_terms,
        )
        diagnostics["relevance_gate"] = relevance_gate
        if (
            answer_available
            and not relevance_gate["passed"]
            and not support_decision.answer_supported
        ):
            warning = {
                "code": "no_query_relevance_evidence",
                "message": (
                    "Selected context does not contain high-signal terms from the question; "
                    "do not treat the result as an exact trusted answer."
                ),
                "missing_terms": relevance_gate.get("required_terms", []),
            }
            answer_available = False
            answer_outline.setdefault("warnings", []).append(warning)
            metrics.setdefault("quality", {}).setdefault("warnings", []).append(warning)
            next_actions.append({
                "tool": "code_search",
                "reason": "No selected cited source contains high-signal query terms; search project docs/source before answering.",
                "query_terms": relevance_gate.get("required_terms", [])[:8],
            })
        if getattr(intent, "wants_code_symbols", False) and not any(
            has_code_symbol_evidence(
                str(item.get("content") or ""),
                str(item.get("title") or ""),
                str(item.get("heading_path") or ""),
                str(item.get("path") or ""),
            )
            for item in context_pack
        ):
            warning = {
                "code": "insufficient_code_symbol_evidence",
                "message": "Selected project docs do not contain concrete files, classes, or functions for this code-symbol query.",
            }
            answer_available = False
            answer_outline.setdefault("warnings", []).append(warning)
            metrics.setdefault("quality", {}).setdefault("warnings", []).append(warning)
            next_actions.extend([
                {"tool": "code_search", "reason": "Use code search / ripgrep for MCP server classes and functions"},
                {"tool": "project_docs", "reason": "Add module docs or ADR linking MCP server implementation files"},
            ])
        answer_available = answer_available and (
            support_decision.answer_supported
            or bool(dependency_docs and dependency_docs.results)
        )
        completeness_result = derive_project_answer_completeness(
            question=question,
            context_pack=context_pack,
            answer_available=answer_available,
            intent=intent,
            support_decision=support_decision,
            assigned_requirement_ids=[
                assignment.requirement_id for assignment in selection_decision.assignments
            ],
        )
        answer_type = completeness_result["answer_type"]
        answer_completeness = completeness_result["answer_completeness"]
        recommended_next_actions = completeness_result["recommended_next_actions"]
        if recommended_next_actions:
            next_actions.extend(recommended_next_actions)
            warning = {
                "code": answer_type,
                "message": "Selected context is partial/navigational for this story-specific question; search project source for missing source-backed terms.",
            }
            answer_outline.setdefault("warnings", []).append(warning)
            metrics.setdefault("quality", {}).setdefault("warnings", []).append(warning)
        answer_outline["answer_completeness"] = answer_completeness
        metrics["answer_completeness"] = answer_completeness
        trust_decision = _make_context_trust_decision(
            question=question,
            context_pack=context_pack,
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            source_evidence_items=source_evidence_items,
            relevance_gate=relevance_gate,
            answer_available=answer_available,
            answer_type=answer_type,
            intent=intent,
            support_decision=support_decision,
        )
        diagnostics["trust_decision"] = {
            "answer_available": trust_decision.answer_available,
            "reason": trust_decision.reason,
            "confidence": trust_decision.confidence,
            "passed_relevance_gate": trust_decision.passed_relevance_gate,
            "max_project_score": trust_decision.max_project_score,
            "query_terms_matched": trust_decision.query_terms_matched,
            "query_terms_missing": trust_decision.query_terms_missing,
        }
        answer_available = trust_decision.answer_available
        dependency_confirmation_blocks_answer = _dependency_confirmation_blocks_local_answer(
            has_confirmation=bool(dependency_confirmation),
            explicit_dependency_requested=explicit_dependency_requested,
            local_answer_available=answer_available,
        )
        if dependency_confirmation_blocks_answer:
            answer_available = False
        elif dependency_confirmation:
            next_actions = [
                action for action in next_actions
                if action is not dependency_confirmation and action != dependency_confirmation
            ]
            if next_action is dependency_confirmation or next_action == dependency_confirmation:
                next_action = {}
            if arguments_patch == {"allow_network": True}:
                arguments_patch = {}
        status = "success" if answer_available else (project_docs.status if project_docs else dependency_docs.status if dependency_docs else "no_results")
        if not answer_available and trust_decision.reason == "no_reliable_context" and _is_low_signal_single_token_query(question):
            status = "no_results"
        if (project_docs and project_docs.status == "stale") or (dependency_docs and dependency_docs.stale_before_refresh):
            status = "stale"
        if dependency_confirmation_blocks_answer and not answer_available and status != "stale":
            status = "confirmation_required"
        elif requires_confirmation and not answer_available and status != "stale":
            status = "confirmation_required"
        reason = trust_decision.reason
        if (
            project_docs
            and project_docs.reason_code in {"document_not_indexed", "ambiguous_document_locator"}
        ):
            reason = project_docs.reason_code
        if dependency_confirmation_blocks_answer and not answer_available:
            reason = "dependency_docs_network_fetch_required"
        elif getattr(intent, "wants_code_symbols", False) and trust_decision.confidence != "trusted":
            reason = "insufficient_code_symbol_evidence"
        message = "Returned project context with Trust Contract." if answer_available else (project_docs.message if project_docs else "No trusted context matched this question.")
        if answer_available and answer_type == "partial_navigational":
            message = "Returned partial/navigational project context; search project source for missing story-specific terms."
        if dependency_confirmation_blocks_answer and not answer_available:
            message = f"Dependency docs for {selected_dependency} require network access; retry with allow_network=true after user confirmation."
        delivery_decision = DeliveryDecision(
            deliverable=bool(answer_available),
            reason_code=None if answer_available else str(reason or "operational_delivery_blocked"),
        )
        return ProjectContextResult(
            project_path=str(root),
            question=question,
            status=status,
            answer_available=answer_available,
            answer_type=answer_type,
            answer_completeness=answer_completeness,
            selection_profile="project_docs_answer",
            requirements=canonical_requirements,
            selection_decision=selection_decision,
            support_decision=support_decision,
            delivery_decision=delivery_decision,
            mode=mode,
            reason=reason,
            documentation_query_plan=documentation_query_plan.as_payload(),
            context_pack=context_pack,
            project_docs=project_docs,
            dependency_docs=dependency_docs,
            trust_contract=trust_contract,
            warnings=[*warnings, *[warning["code"] for warning in snippet_presentation.warnings]],
            next_actions=next_actions,
            recommended_next_actions=recommended_next_actions,
            next_action=next_action,
            requires_confirmation=requires_confirmation,
            confirmation_reason=confirmation_reason,
            arguments_patch=arguments_patch,
            response_style=snippet_presentation.response_style,
            primary_snippet=snippet_presentation.primary_snippet,
            supporting_snippets=snippet_presentation.supporting_snippets,
            primary_snippets=snippet_presentation.primary_snippets,
            primary_snippet_confidence=snippet_presentation.primary_snippet_confidence,
            primary_snippet_selection_reason=snippet_presentation.primary_snippet_selection_reason,
            primary_snippet_alternatives=snippet_presentation.primary_snippet_alternatives,
            snippet_metrics=snippet_presentation.metrics,
            metrics=metrics,
            diagnostics=diagnostics,
            answer_outline=answer_outline,
            message=message,
        )

    @staticmethod
    def dependency_mentioned_in_question(metadata: ProjectMetadata, question: str) -> str | None:
        query = str(question or "")
        dependency_context = bool(_DEPENDENCY_REFERENCE_CUE_RE.search(query))
        for dependency in metadata.dependencies:
            name = dependency.package_name
            aliases = {name.casefold()}
            if name.casefold().startswith("flutter_"):
                aliases.add(name[8:].casefold())
            for alias in aliases:
                tokens = re.findall(r"[a-z0-9]+", alias)
                if not tokens:
                    continue
                pattern = r"(?<![a-z0-9])" + r"[\s._-]*".join(
                    re.escape(token) for token in tokens
                ) + r"(?![a-z0-9])"
                match = re.search(pattern, query, re.IGNORECASE)
                if match is None:
                    continue
                compact_alias = "".join(tokens)
                explicitly_quoted = bool(re.search(
                    rf"[`\"']\s*{pattern}\s*[`\"']",
                    query,
                    re.IGNORECASE,
                ))
                if compact_alias in _AMBIGUOUS_DEPENDENCY_NAMES and not (
                    dependency_context or explicitly_quoted
                ):
                    continue
                return name
        return None
