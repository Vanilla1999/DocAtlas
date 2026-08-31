"""UnifiedDocsContextService implementation shard 2."""
from __future__ import annotations

from ._unified_context_service_shared import *  # noqa: F401,F403


class _UnifiedDocsContextServicePart02:
    def _ensure_library_safe(self, library: str, ecosystem: str | None, version: str | None, source_type: str | None, docs_url: str | None, force_refresh: bool, allow_network: bool, project_path: str | None = None) -> UnifiedDocsContextResult | None:
        if allow_network:
            return None
        project_version_for = getattr(self.service, "_project_version_for", None)
        if project_path and (version is None or docs_url is None) and callable(project_version_for):
            detected_version, detected_docs_url, detected_template, *_ = project_version_for(
                library=library,
                ecosystem=ecosystem,
                project_path=project_path,
            )
            version = version or detected_version
            docs_url = docs_url or detected_docs_url
            if docs_url is None and detected_template and version:
                docs_url = detected_template.format(library=library, version=version)
        if ecosystem == "python" and version and str(version).lower() not in _LATEST_ALIASES and docs_url is None:
            normalized = library.lower().replace("-", "_").replace(" ", "_")
            exact = resolve_python_versioned_docs(normalized, version)
            if exact and exact.status == "exact_version_not_supported":
                return None
        info = self.service.resolve_library(library, ecosystem, version, docs_url, None, source_type)
        if getattr(info, "status", None) == "exact_version_not_supported":
            return None
        status = getattr(info, "status", "")
        if status == "needs_docs_url":
            candidates = list(getattr(info, "candidates", []) or [])
            source_options = library_docs_source_options(library, ecosystem, version, source_type, candidates)
            next_action = {
                "type": "ask_user_for_library_docs_source",
                "tool": None,
                "requires_confirmation": True,
                "question": f"Which documentation source should be used for {library}?",
                "options": source_options,
                "quality_warning": "If the user does not know, best-effort web discovery can be used, but quality is not guaranteed.",
            }
            return self._confirmation_result(
                question=f"Which documentation source should be used for {library}?",
                mode_requested="library",
                mode_selected="library",
                routing={"reason_code": "library_docs_source_required", "legacy_reason_code": "needs_docs_url", "project_path_used": False, "libraries_requested": [library], "dependency_detected": False},
                reason_code="library_docs_source_required",
                confirmation_reason="library_docs_source",
                next_action=next_action,
                arguments_patch={"library": library, "ecosystem": ecosystem, "version": version, "source_type": source_type},
                lanes={**self._empty_lanes(), "library": {"status": "confirmation_required", "source_count": 0, "canonical_ids": [], "requires_confirmation": True, "next_action": next_action}},
                warnings=[source_required_diagnostics({"code": "library_docs_source_required", "blocking": True, "source_options": source_options})],
            )
        if status in {"failed", "partial"}:
            message = getattr(info, "message", None) or "Registered library documentation source is in failed state."
            next_action = {
                "type": "repair_library_docs_source",
                "tool": "prepare_docs",
                "arguments_patch": {
                    "action": "refresh_library_docs",
                    "library": library,
                    "ecosystem": ecosystem,
                    "version": version,
                    "source_type": source_type,
                    "force": True,
                    "allow_network": True,
                },
            }
            return self._confirmation_result(
                question="",
                mode_requested="library",
                mode_selected="library",
                routing={
                    "reason_code": "library_docs_partial" if status == "partial" else "library_docs_failed",
                    "project_path_used": False,
                    "libraries_requested": [library],
                    "dependency_detected": False,
                    "failed_status": status,
                    "failed_message": message,
                },
                reason_code="library_docs_partial" if status == "partial" else "library_docs_failed",
                confirmation_reason="library_docs_repair",
                next_action=next_action,
                arguments_patch=next_action["arguments_patch"],
                lanes={
                    **self._empty_lanes(),
                    "library": {
                        "status": "failed",
                        "source_count": 0,
                        "canonical_ids": [getattr(info, "library_id", None)] if getattr(info, "library_id", None) else [],
                        "requires_confirmation": True,
                        "next_action": next_action,
                    },
                },
                warnings=[{
                    "code": "library_docs_failed",
                    "blocking": True,
                    "library": library,
                    "canonical_id": getattr(info, "canonical_id", None) or getattr(info, "library_id", None),
                    "message": message,
                }],
            )
        if force_refresh or not getattr(info, "local", False) or getattr(info, "stale", False) or status in {"needs_refresh"}:
            return self._confirmation_result(
                question="",
                mode_requested="library",
                mode_selected="library",
                routing={"reason_code": "library_docs_network_fetch_required", "project_path_used": False, "libraries_requested": [library], "dependency_detected": False},
                reason_code="library_docs_network_fetch_required",
                confirmation_reason="network_fetch",
                next_action={"type": "get_docs_context", "tool": "get_docs_context", "arguments_patch": {"allow_network": True}},
                arguments_patch={"allow_network": True},
                lanes={**self._empty_lanes(), "library": {"status": "confirmation_required", "source_count": 0, "canonical_ids": [getattr(info, "library_id", None)] if getattr(info, "library_id", None) else []}},
                warnings=list(getattr(info, "candidates", []) or []),
            )
        return None

    def _get_library_docs_with_latest_fallback(
        self,
        library: str,
        *,
        question: str,
        tokens: int | None,
        ecosystem: str | None,
        version: str | None,
        docs_url: str | None,
        source_type: str | None,
        force_refresh: bool,
        project_path: str | None,
        allow_network: bool,
        allow_latest_fallback: bool,
        response_style: str | None = None,
    ) -> DocsResult | UnifiedDocsContextResult:
        exact = self.service.get_docs(library, topic=question, tokens=tokens, ecosystem=ecosystem, version=version, docs_url=docs_url, source_type=source_type, force_refresh=force_refresh, project_path=project_path, response_style=response_style)
        exact_diag = (exact.diagnostics or {}).get("exact_version") if isinstance(exact.diagnostics, dict) else None
        if not (exact.status == "exact_version_not_supported" and allow_latest_fallback and isinstance(exact_diag, dict) and exact_diag.get("fallback_available")):
            return exact

        fallback_docs_url = exact_diag.get("fallback_docs_url") or None
        if not allow_network:
            info = self.service.resolve_library(library, ecosystem, None, fallback_docs_url or docs_url, None, source_type)
            if not getattr(info, "local", False) or getattr(info, "stale", False) or getattr(info, "status", "") in {"needs_docs_url", "needs_refresh"}:
                return self._confirmation_result(
                    question=question,
                    mode_requested="library",
                    mode_selected="library",
                    routing={"reason_code": "latest_fallback_network_fetch_required", "project_path_used": bool(project_path), "libraries_requested": [library], "dependency_detected": False},
                    reason_code="latest_fallback_network_fetch_required",
                    confirmation_reason="network_fetch",
                    next_action={"type": "get_docs_context", "tool": "get_docs_context", "arguments_patch": {"allow_network": True, "allow_latest_fallback": True}},
                    arguments_patch={"allow_network": True, "allow_latest_fallback": True},
                    lanes={**self._empty_lanes(), "library": {"status": "confirmation_required", "source_count": 0, "canonical_ids": [getattr(info, "library_id", None)] if getattr(info, "library_id", None) else [], "requires_confirmation": True, "next_action": {"type": "get_docs_context", "tool": "get_docs_context", "arguments_patch": {"allow_network": True, "allow_latest_fallback": True}}}},
                )

        latest = self.service.get_docs(library, topic=question, tokens=tokens, ecosystem=ecosystem, version=None, docs_url=fallback_docs_url or docs_url, source_type=source_type, force_refresh=force_refresh, project_path=project_path, response_style=response_style)
        if latest.results:
            diag = dict(latest.diagnostics or {})
            diag["exact_version"] = {
                "expected": exact.requested_version or version,
                "used": "latest",
                "match": False,
                "fallback": True,
                "status": "exact_version_fallback_latest",
                "reason_code": "versioned_docs_unavailable",
            }
            return replace(latest, requested_version=exact.requested_version or version, diagnostics=diag)

        diag = dict(latest.diagnostics or {})
        diag["exact_version"] = {
            "expected": exact.requested_version or version,
            "used": None,
            "match": None,
            "fallback": False,
            "status": latest.status,
            "reason_code": latest.diagnostics.get("reason_code") if isinstance(latest.diagnostics, dict) else latest.status,
        }
        return replace(latest, requested_version=exact.requested_version or version, diagnostics=diag)

    def _augment_snippet_first_context(
        self,
        context_pack: list[dict[str, Any]],
        *,
        question: str,
        response_style: str,
        lane_priority: list[str],
        library_results: list[DocsResult],
        libs: list[str],
        tokens: int | None,
        ecosystem: str | None,
        version: str | None,
        docs_url: str | None,
        source_type: str | None,
        project_path: str | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        if response_style != "snippet-first" or not library_results:
            return context_pack, None
        current = build_snippet_presentation(
            context_pack,
            question=question,
            response_style=response_style,
            lane_priority=lane_priority,
        )
        if current.primary_snippet:
            return context_pack, None

        added = 0
        for lib in libs:
            fallback = self.service.get_docs(
                lib,
                topic=_snippet_first_fallback_question(question, lib),
                tokens=tokens,
                ecosystem=ecosystem,
                version=version,
                docs_url=docs_url,
                source_type=source_type,
                force_refresh=False,
                project_path=project_path,
                response_style=response_style,
            )
            if not isinstance(fallback, DocsResult) or not fallback.results:
                continue
            fallback_items = self._library_context_pack(fallback)
            snippet_items = [item for item in fallback_items if item.get("snippet")]
            if not snippet_items:
                continue
            context_pack = [*context_pack, *snippet_items]
            added += len(snippet_items)
            break

        if not added:
            return context_pack, None
        return context_pack, {"reason": "snippet_first_requested_without_selected_snippet", "added_context_items": added}

    def _dependency_prefetch_needed(self, project_path: str | None) -> bool:
        if not project_path:
            return True
        metadata = self.service.read_project_metadata(project_path)
        deps = getattr(metadata, "dependencies", []) or []
        if not deps:
            return False
        state = self.service._project_dependency_docs_state(metadata)
        if not isinstance(state, dict):
            return False
        return bool(state.get("missing") or state.get("stale"))

    def _dependency_prefetch_guidance(self, project_path: str | None, question: str, *, limit: int = 20) -> dict[str, Any]:
        if not project_path:
            return {
                "available": 0,
                "missing": 0,
                "network_fetch_required": True,
                "recommended_prefetch": [],
                "agent_instruction": "Ask the user before prefetching dependency docs.",
            }
        metadata = self.service.read_project_metadata(project_path)
        deps = getattr(metadata, "dependencies", []) or []
        state = self.service._project_dependency_docs_state(metadata)
        unavailable = []
        if isinstance(state, dict):
            unavailable = [str(value) for value in [*(state.get("missing") or []), *(state.get("stale") or [])]]
        available = max(0, len(deps) - len(set(unavailable)))
        recommended = self._rank_dependencies_for_prefetch(deps, unavailable, question, limit=limit)
        return {
            "available": available,
            "missing": len(set(unavailable)),
            "network_fetch_required": bool(unavailable),
            "recommended_prefetch": recommended,
            "agent_instruction": "Ask the user before prefetching dependency docs. The user can approve prefetching all dependencies or only the recommended top-N.",
            "next_action": {
                "tool": "prepare_docs",
                "arguments_patch": {
                    "action": "prefetch_project_dependency_docs",
                    "project_path": project_path,
                    "include_packages": [item["library"] for item in recommended],
                    "include_flutter": False,
                },
            } if recommended else None,
        }

    @staticmethod
    def _rank_dependencies_for_prefetch(deps: list[Any], unavailable: list[str], question: str, *, limit: int) -> list[dict[str, Any]]:
        unavailable_set = {str(value).lower() for value in unavailable}
        query = question.lower().replace("-", "_")
        rows: list[tuple[int, str, Any]] = []
        for dep in deps:
            name = str(getattr(dep, "package_name", "") or getattr(dep, "name", "") or dep)
            if not name or name.lower() not in unavailable_set:
                continue
            normalized = name.lower().replace("-", "_")
            score = 10 if normalized in query else 0
            rows.append((-score, normalized, dep))
        rows.sort(key=lambda row: (row[0], row[1]))
        result: list[dict[str, Any]] = []
        for _, _, dep in rows[:limit]:
            name = str(getattr(dep, "package_name", "") or getattr(dep, "name", "") or dep)
            result.append({"ecosystem": getattr(dep, "ecosystem", None) or "unknown", "library": name, "version": getattr(dep, "version", None)})
        return result

    def _normalize_project_context(self, result: ProjectContextResult) -> list[dict[str, Any]]:
        items = []
        for item in result.context_pack or []:
            normalized = dict(item)
            source_class = normalized.get("source_class")
            if source_class == "dependency_doc":
                scope = "dependency"
                lane = "dependency"
            else:
                scope = normalized.get("doc_scope") or "project"
                lane = "project"
            normalized["doc_scope"] = scope
            normalized["origin_lane"] = lane
            normalized.setdefault("canonical_id", normalized.get("library_id"))
            normalized.setdefault("library_id", normalized.get("dependency"))
            normalized.setdefault("version", normalized.get("resolved_version") or normalized.get("version"))
            normalized.setdefault("why_selected", f"selected by {lane} context lane")
            items.append(normalized)
        return items

    def _library_context_pack(self, result: DocsResult) -> list[dict[str, Any]]:
        items = []
        result_chunks = result.results or []
        for index, chunk in enumerate(result_chunks):
            token_estimate = max(1, len(chunk.content or "") // 4)
            chunk_metadata = chunk.metadata or {}
            item = {
                "doc_scope": "library",
                "origin_lane": "library",
                "source_class": "library_doc",
                "source": chunk.source,
                "url": chunk.url,
                "title": chunk.title,
                "content": chunk.content,
                "canonical_id": result.library_id,
                "library_id": result.library_id,
                "library": result.library,
                "version": chunk_metadata.get("version") or result.resolved_version or result.version,
                "requested_version": chunk_metadata.get("requested_version") or result.requested_version,
                "docs_exactness": chunk_metadata.get("docs_exactness") or result.docs_exactness,
                "docs_binding_source": chunk_metadata.get("docs_binding_source") or result.docs_binding_source,
                "exact_version_match": chunk_metadata.get("exact_version_match") if "exact_version_match" in chunk_metadata else _exact_version_match(result),
                "freshness": "stale" if result.stale_before_refresh else "current",
                "why_selected": "library docs resolved through Docmancer registry",
                "token_estimate": token_estimate,
                "section": {"title": chunk.title, "freshness": "stale" if result.stale_before_refresh else "current"},
            }
            if (
                "stable_chunk_id" not in item
                and len(result.selected_evidence_ids) == len(result_chunks)
                and index < len(result.selected_evidence_ids)
            ):
                item["stable_chunk_id"] = result.selected_evidence_ids[index]
            snippet = context_pack_snippet(chunk)
            if snippet:
                item["snippet"] = snippet
                item["surrounding_context"] = chunk.content
            items.append(item)
        return items

    def _dedupe_and_guard(self, items: list[dict[str, Any]], libs: list[str], project_path: str | None) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        seen: dict[Any, int] = {}
        out = []
        contamination_dropped = 0
        contamination_reasons: list[str] = []
        dedup_dropped = 0
        dedup_reasons: list[str] = []
        requested = {lib.lower().replace("-", "_") for lib in libs}
        for item in items:
            scope = item.get("doc_scope")
            if scope not in {"project", "module", "dependency", "library"}:
                contamination_dropped += 1
                contamination_reasons.append("wrong_doc_scope")
                continue
            if scope in {"project", "module"} and project_path:
                path = str(item.get("path") or item.get("source") or "")
                if path.startswith("/") and not path.startswith(str(project_path).rstrip("/") + "/") and path != str(project_path):
                    contamination_dropped += 1
                    contamination_reasons.append("foreign_project")
                    continue
            if scope == "library" and requested:
                lib_text = " ".join(str(item.get(key) or "") for key in ("library", "library_id", "canonical_id")).lower().replace("-", "_")
                if not any(lib in lib_text for lib in requested):
                    contamination_dropped += 1
                    contamination_reasons.append("wrong_library_id")
                    continue
            source_identity = item.get("canonical_id") or item.get("source") or item.get("url") or item.get("path")
            if isinstance(source_identity, dict):
                source_identity = source_identity.get("url") or source_identity.get("path") or source_identity.get("source") or str(sorted(source_identity.items()))
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            section = item.get("section") if isinstance(item.get("section"), dict) else {}
            evidence_payload = json.dumps(
                {
                    "content": item.get("content"),
                    "snippet": item.get("snippet"),
                    "symbols": item.get("symbols"),
                    "metadata_symbols": metadata.get("symbols"),
                    "line_start": item.get("line_start"),
                    "line_end": item.get("line_end"),
                    "docs_exactness": item.get("docs_exactness"),
                    "version": item.get("version"),
                    "requested_version": item.get("requested_version"),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            source_class = str(item.get("source_class") or "")
            payload_distinguishes_evidence = bool(
                source_class in {"code_graph", "repo_map", "source_evidence", "library_doc", "dependency_doc"}
                or item.get("snippet")
                or item.get("symbols")
                or metadata.get("symbols")
                or item.get("line_start") is not None
                or item.get("line_end") is not None
                or item.get("docs_exactness")
            )
            stable = (
                str(source_identity),
                item.get("heading_path") or section.get("heading_path") or item.get("title"),
                evidence_payload if payload_distinguishes_evidence else None,
            )
            if stable in seen:
                existing_index = seen[stable]
                from docmancer.docs.application.context_selection import merge_query_matches
                merged_matches = merge_query_matches(
                    out[existing_index].get("retrieval_query_matches"),
                    item.get("retrieval_query_matches"),
                )
                merged_query_ids = [
                    key for key, value in merged_matches.items() if value.get("qualified") is True
                ]
                if merged_query_ids:
                    out[existing_index] = {
                        **out[existing_index],
                        "retrieval_query_matches": merged_matches,
                        "retrieval_query_ids": merged_query_ids,
                    }
                dedup_dropped += 1
                dedup_reasons.append("duplicate_source")
                continue
            seen[stable] = len(out)
            out.append(item)
        return out, {"detected": bool(contamination_dropped), "dropped_count": contamination_dropped, "reason_codes": sorted(set(contamination_reasons))}, {"dropped_count": dedup_dropped, "reason_codes": sorted(set(dedup_reasons))}

    def _trust_contract(self, items: list[dict[str, Any]], project_result: ProjectContextResult | None, library_results: list[DocsResult]) -> dict[str, Any]:
        selected = []
        risky = []
        for item in items:
            entry = {
                "source": item.get("source") or item.get("url") or item.get("path"),
                "doc_scope": item.get("doc_scope"),
                "origin_lane": item.get("origin_lane"),
                "why_selected": item.get("why_selected"),
                "freshness": item.get("freshness"),
                "version_binding": item.get("docs_exactness") or item.get("version") or item.get("version_binding"),
                "source_provenance": item.get("source_provenance"),
                "repository_authority": item.get("repository_authority"),
                "instruction_trust": item.get("instruction_trust") or "untrusted_data",
                "content_boundary": item.get("content_boundary"),
                "risk_flags": [],
            }
            if item.get("freshness") == "stale":
                entry["risk_flags"].append("stale")
                risky.append(entry)
            selected.append(entry)
        rejected = []
        if project_result and project_result.trust_contract:
            sources = project_result.trust_contract.get("sources") or {}
            rejected.extend(sources.get("rejected") or [])
            risky.extend(sources.get("risky") or [])
        for result in library_results:
            for warning in result.warnings or []:
                if "fallback" in warning or "stale" in warning:
                    risky.append({"source": result.library_id, "doc_scope": "library", "origin_lane": "library", "why_selected": str(warning), "freshness": "unknown", "version_binding": result.docs_exactness, "risk_flags": [str(warning)]})
        sources = {"selected": selected, "rejected": rejected, "risky": risky}
        return {
            "schema_version": "trust-contract-1.2",
            "sources": sources,
            "source_dimensions": ["source_provenance", "version_exactness", "repository_authority", "instruction_trust"],
            "policy": {
                "document_content": "cited_data_never_lifecycle_instruction",
                "typed_lifecycle_actions_only": True,
            },
        }

    @staticmethod
    def _lane_priority_for(mode_selected: str) -> list[str]:
        if mode_selected == "library":
            return ["library"]
        if mode_selected == "dependency":
            return ["dependency"]
        if mode_selected == "project":
            return ["project"]
        if mode_selected == "mixed":
            return ["project", "dependency", "library"]
        return ["project", "dependency", "library"]

    @staticmethod
    def _source_summary(items: list[dict[str, Any]], trust: dict[str, Any]) -> dict[str, int]:
        return {
            "project": sum(1 for item in items if item.get("doc_scope") in {"project", "module"}),
            "library": sum(1 for item in items if item.get("doc_scope") == "library"),
            "dependency": sum(1 for item in items if item.get("doc_scope") == "dependency"),
            "rejected": len(trust.get("rejected") or []),
            "risky": len(trust.get("risky") or []),
        }

    def _exact_version(self, result: DocsResult, allow_latest_fallback: bool) -> dict[str, Any] | None:
        expected = result.requested_version
        if not expected or str(expected).lower() in _LATEST_ALIASES:
            return None
        diagnostic = (result.diagnostics or {}).get("exact_version") if isinstance(result.diagnostics, dict) else None
        if diagnostic:
            return diagnostic
        used = result.resolved_version or result.version
        return {"expected": expected, "used": used, "match": used == expected, "fallback": used == "latest" and used != expected, "status": "exact_version_indexed" if used == expected else "exact_version_fallback_latest"}

    @staticmethod
    def _merge_lane_status(existing: str | None, incoming: str) -> str:
        if existing in {None, "not_requested"}:
            return incoming
        if existing == incoming:
            return existing
        if "success" in {existing, incoming}:
            return "partial_success"
        return incoming

    @staticmethod
    def _lane_succeeded(lane: dict[str, Any]) -> bool:
        return (lane.get("source_count") or 0) > 0

    @staticmethod
    def _refresh_lane_counts(lanes: dict[str, Any], items: list[dict[str, Any]]) -> None:
        for name, scope in (("project", "project"), ("library", "library"), ("dependency", "dependency")):
            lane = lanes.get(name)
            if not lane or lane.get("status") == "not_requested":
                continue
            count = sum(1 for item in items if item.get("doc_scope") in ({"project", "module"} if scope == "project" else {scope}))
            lane["source_count"] = count
            if count == 0 and lane.get("status") == "success":
                lane["status"] = "not_found"

    @staticmethod
    def _aggregate_status(requested_lanes: list[str], successful_lanes: list[str], pending_confirmation_lanes: list[str], failed_lanes: list[str]) -> str:
        if requested_lanes and len(successful_lanes) == len(requested_lanes) and not pending_confirmation_lanes and not failed_lanes:
            return "success"
        if successful_lanes and (pending_confirmation_lanes or failed_lanes):
            return "partial_success"
        if not successful_lanes and pending_confirmation_lanes:
            return "confirmation_required"
        if not successful_lanes and failed_lanes and all(lane in failed_lanes for lane in requested_lanes):
            return "not_found"
        if failed_lanes:
            return "failed"
        return "not_found"

    @staticmethod
    def _infer_project_auto_mode(result: ProjectContextResult, items: list[dict[str, Any]]) -> str:
        diagnostics = result.diagnostics or {}
        selected = diagnostics.get("mode_selected") or diagnostics.get("selected_mode") if isinstance(diagnostics, dict) else None
        if selected in {"project", "dependency", "mixed"}:
            return selected
        scopes = {("project" if item.get("doc_scope") == "module" else item.get("doc_scope")) for item in items if item.get("doc_scope") in {"project", "module", "dependency"}}
        if scopes == {"dependency"}:
            return "dependency"
        if scopes == {"project", "dependency"}:
            return "mixed"
        return "project"

    @staticmethod
    def _can_return_partial_project_context(bootstrap: Any) -> bool:
        """Return already indexed context when preflight only flags placeholder docs."""
        reason_code = str(getattr(bootstrap, "reason_code", "") or "")
        if reason_code != "project_docs_preflight_confirmation_required":
            return False
        next_action = getattr(bootstrap, "next_action", None) or {}
        risk_codes = set(next_action.get("risk_codes") or []) if isinstance(next_action, dict) else set()
        return bool(risk_codes) and risk_codes <= {"placeholder_project_doc"}

    @staticmethod
    def _project_index_recovery_action(bootstrap: Any, project_path: str) -> dict[str, Any] | None:
        """Return typed sync recovery when discovered project docs have no index evidence."""
        inspect_result = getattr(bootstrap, "inspect_result", None)
        project_docs = getattr(inspect_result, "project_docs", None)
        if not isinstance(project_docs, dict):
            return None
        found = project_docs.get("found") or []
        indexed = project_docs.get("indexed") or []
        next_action = getattr(bootstrap, "next_action", None) or {}
        if not found or indexed or not isinstance(next_action, dict):
            return None
        if next_action.get("tool_after_confirmation") != "sync_project_docs":
            return None
        return {
            "type": "prepare_docs",
            "tool": "prepare_docs",
            "arguments_patch": {"action": "sync_project_docs", "project_path": project_path},
            "requires_confirmation": True,
            "confirmation_reason": getattr(bootstrap, "confirmation_reason", None),
        }

    @staticmethod
    def _collect_pending_actions(lane_results: list[Any]) -> dict[str, Any]:
        pending: dict[str, Any] = {"requires_confirmation": False, "next_actions": []}
        merged_patch: dict[str, Any] = {}
        patch_conflict = False
        for result in lane_results:
            if not getattr(result, "requires_confirmation", False):
                continue
            pending["requires_confirmation"] = True
            if not pending.get("confirmation_reason"):
                pending["confirmation_reason"] = getattr(result, "confirmation_reason", None)
            next_action = getattr(result, "next_action", None) or None
            patch = getattr(result, "arguments_patch", None) or None
            if next_action:
                pending["next_actions"].append(next_action)
                pending.setdefault("next_action", next_action)
            if patch:
                action = next_action or {"type": "get_docs_context", "tool": "get_docs_context", "arguments_patch": patch}
                if action not in pending["next_actions"]:
                    pending["next_actions"].append(action)
                for key, value in patch.items():
                    if key in merged_patch and merged_patch[key] != value:
                        patch_conflict = True
                    else:
                        merged_patch[key] = value
        if merged_patch and not patch_conflict:
            pending["arguments_patch"] = merged_patch
        return pending

    @staticmethod
    def _to_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, UnifiedDocsContextResult):
            return asdict(value)
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _empty_lanes() -> dict[str, Any]:
        return {
            "project": {"status": "not_requested", "source_count": 0},
            "library": {"status": "not_requested", "source_count": 0, "canonical_ids": []},
            "dependency": {"status": "not_requested", "source_count": 0},
        }

    def _confirmation_result(self, *, question: str, mode_requested: str, mode_selected: str, routing: dict[str, Any], reason_code: str, confirmation_reason: str | None, lanes: dict[str, Any], next_action: dict[str, Any] | None = None, arguments_patch: dict[str, Any] | None = None, dependency_docs: dict[str, Any] | None = None, lane_details: dict[str, Any] | None = None, warnings: list[Any] | None = None) -> UnifiedDocsContextResult:
        return UnifiedDocsContextResult(
            status="confirmation_required",
            question=question,
            mode_requested=mode_requested,
            mode_selected=mode_selected,
            routing=routing,
            answer_available=False,
            lanes=lanes,
            source_summary={"project": 0, "library": 0, "dependency": 0, "rejected": 0, "risky": 0},
            trust_contract={"selected": [], "rejected": [], "risky": []},
            reason_code=reason_code,
            requires_confirmation=True,
            confirmation_reason=confirmation_reason,
            next_action=next_action,
            arguments_patch=arguments_patch,
            dependency_docs=dependency_docs or {},
            warnings=warnings or [],
            contamination={"detected": False, "dropped_count": 0, "reason_codes": []},
            deduplication={"dropped_count": 0, "reason_codes": []},
            lane_details=lane_details or {},
        )
