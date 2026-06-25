from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from docmancer.docs.application.project_context_service import context_pack_snippet
from docmancer.docs.exact_version import resolve_python_versioned_docs
from docmancer.docs.models import DocsResult, ProjectContextResult, UnifiedDocsContextResult


_LATEST_ALIASES = {"latest", "stable", "main", "*"}


class UnifiedDocsContextService:
    """Route high-level docs-context requests to existing facade methods."""

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
        details: bool | None = None,
    ) -> UnifiedDocsContextResult:
        mode_requested = (mode or "auto").lower()
        prepare_project_docs = True if prepare_project_docs is None else bool(prepare_project_docs)
        allow_network = bool(allow_network) if allow_network is not None else False
        allow_latest_fallback = bool(allow_latest_fallback) if allow_latest_fallback is not None else False
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
        exact_version: dict[str, Any] | None = None

        bootstrap = None
        if prepare_project_docs and project_path and mode_selected in {"project", "mixed", "dependency"}:
            bootstrap = self.service.bootstrap_project_docs(project_path, question=question)
            lane_details["project_bootstrap"] = self._to_dict(bootstrap)
            if getattr(bootstrap, "requires_confirmation", False):
                return self._confirmation_result(
                    question=question,
                    mode_requested=mode_requested,
                    mode_selected=mode_selected,
                    routing=routing,
                    reason_code=getattr(bootstrap, "reason_code", None) or "project_docs_confirmation_required",
                    confirmation_reason=getattr(bootstrap, "confirmation_reason", None),
                    next_action=getattr(bootstrap, "next_action", None) or None,
                    arguments_patch=getattr(bootstrap, "arguments_patch", None) or None,
                    lanes=lanes,
                    lane_details=lane_details if details else {},
                    warnings=list(getattr(bootstrap, "warnings", []) or []),
                )

        project_result = None
        library_results: list[DocsResult] = []

        if mode_selected == "project":
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, module=module, module_path=module_path, scope=scope, mode="project-only")
        elif mode_selected == "dependency":
            if not allow_network and self._dependency_prefetch_needed(project_path):
                lanes["dependency"] = {"status": "confirmation_required", "source_count": 0}
                return self._confirmation_result(
                    question=question,
                    mode_requested=mode_requested,
                    mode_selected=mode_selected,
                    routing=routing,
                    reason_code="dependency_docs_prefetch_required",
                    confirmation_reason="network_fetch",
                    arguments_patch={"allow_network": True},
                    lanes=lanes,
                    lane_details=lane_details if details else {},
                )
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, library=library, libraries=libraries, ecosystem=ecosystem, version=version, module=module, module_path=module_path, scope=scope, mode="deps-only")
        elif mode_selected == "mixed":
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, library=library, libraries=libraries, ecosystem=ecosystem, version=version, module=module, module_path=module_path, scope=scope, mode="auto")
            routing["dependency_detected"] = bool(getattr(project_result, "dependency_docs", None))
            explicit_library_results = []
            for lib in libs:
                safe = self._ensure_library_safe(lib, ecosystem, version, source_type, docs_url, force_refresh, allow_network)
                if safe is not None:
                    explicit_library_results.append(safe)
                    continue
                explicit_library_results.append(self.service.get_docs(lib, topic=question, tokens=tokens, ecosystem=ecosystem, version=version, docs_url=docs_url, source_type=source_type, force_refresh=force_refresh, project_path=project_path))
            library_results = [item for item in explicit_library_results if isinstance(item, DocsResult)]
            lane_details["library"] = [self._to_dict(item) for item in explicit_library_results]
            confirmation = next((item for item in explicit_library_results if isinstance(item, UnifiedDocsContextResult)), None)
            if confirmation and project_result and project_result.answer_available:
                lanes["library"] = {"status": "confirmation_required", "source_count": 0, "canonical_ids": []}
            elif confirmation:
                return confirmation
        elif mode_selected == "library":
            for lib in libs:
                safe = self._ensure_library_safe(lib, ecosystem, version, source_type, docs_url, force_refresh, allow_network)
                if safe is not None:
                    return safe
                result = self.service.get_docs(lib, topic=question, tokens=tokens, ecosystem=ecosystem, version=version, docs_url=docs_url, source_type=source_type, force_refresh=force_refresh, project_path=project_path)
                library_results.append(result)
            lane_details["library"] = [self._to_dict(item) for item in library_results]

        if project_result:
            lane_details["project"] = self._to_dict(project_result)
            project_items = self._normalize_project_context(project_result)
            context_pack.extend(project_items)
            lanes["project"] = {"status": project_result.status, "source_count": len([i for i in project_items if i.get("doc_scope") == "project"])}
            dep_count = len([i for i in project_items if i.get("doc_scope") == "dependency"])
            if dep_count:
                lanes["dependency"] = {"status": getattr(project_result.dependency_docs, "status", "success"), "source_count": dep_count}
            warnings.extend(project_result.warnings or [])
            next_actions.extend(project_result.next_actions or [])

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

        context_pack, contamination = self._dedupe_and_guard(context_pack, libs)
        trust_contract = self._trust_contract(context_pack, project_result, library_results)
        source_summary = self._source_summary(context_pack, trust_contract)
        answer_available = bool(context_pack)
        status = self._overall_status(lanes, answer_available)
        reason = None if answer_available else "no_docs_context_available"

        payload = UnifiedDocsContextResult(
            status=status,
            question=question,
            mode_requested=mode_requested,
            mode_selected=mode_selected,
            routing=routing,
            answer_available=answer_available,
            context_pack=context_pack,
            lanes=lanes,
            source_summary=source_summary,
            trust_contract=trust_contract,
            exact_version=exact_version,
            reason_code=reason,
            requires_confirmation=status == "confirmation_required",
            confirmation_reason="network_fetch" if status == "confirmation_required" else None,
            next_actions=next_actions,
            arguments_patch={"allow_network": True} if status == "confirmation_required" else None,
            warnings=warnings,
            metrics={"context_pack_items": len(context_pack)},
            contamination=contamination,
            lane_details=lane_details if details else {},
        )
        return payload

    def _validate(self, question: str, project_path: str | None, libs: list[str], mode: str) -> UnifiedDocsContextResult | None:
        if not question:
            return self._invalid("docs_context_question_missing", {"question": "Your documentation question"}, mode)
        if mode not in {"auto", "project", "library", "dependency", "mixed"}:
            return self._invalid("docs_context_mode_invalid", {"mode": "auto"}, mode, question=question)
        if not project_path and not libs:
            return self._invalid("docs_context_target_missing", {"project_path": "/path/to/repo"}, mode, question=question)
        if mode == "project" and not project_path:
            return self._invalid("project_path_required", {"project_path": "/path/to/repo"}, mode, question=question)
        if mode == "project" and libs:
            return self._invalid("project_mode_cannot_include_library", {"library": None, "libraries": None}, mode, question=question)
        if mode == "library" and not libs:
            return self._invalid("library_required", {"library": "fastapi"}, mode, question=question)
        if mode in {"dependency", "mixed"} and not project_path:
            return self._invalid("project_path_required", {"project_path": "/path/to/repo"}, mode, question=question)
        return None

    def _invalid(self, reason_code: str, arguments_patch: dict[str, Any], mode: str, *, question: str = "") -> UnifiedDocsContextResult:
        return UnifiedDocsContextResult(
            status="invalid_request",
            question=question,
            mode_requested=mode,
            mode_selected="invalid_request",
            routing={"reason_code": reason_code, "project_path_used": False, "libraries_requested": [], "dependency_detected": False},
            answer_available=False,
            reason_code=reason_code,
            next_action={"type": "retry", "arguments_patch": arguments_patch},
            arguments_patch=arguments_patch,
            lanes=self._empty_lanes(),
            source_summary={"project": 0, "library": 0, "dependency": 0, "rejected": 0, "risky": 0},
            trust_contract={"selected": [], "rejected": [], "risky": []},
            contamination={"detected": False, "dropped_count": 0, "reason_codes": []},
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
    def _libraries(library: str | None, libraries: list[str] | None) -> list[str]:
        result = []
        if library:
            result.append(library)
        result.extend(libraries or [])
        seen = set()
        return [item for item in result if not (item in seen or seen.add(item))]

    def _ensure_library_safe(self, library: str, ecosystem: str | None, version: str | None, source_type: str | None, docs_url: str | None, force_refresh: bool, allow_network: bool) -> UnifiedDocsContextResult | None:
        if allow_network:
            return None
        if ecosystem == "python" and version and str(version).lower() not in _LATEST_ALIASES and docs_url is None:
            normalized = library.lower().replace("-", "_").replace(" ", "_")
            exact = resolve_python_versioned_docs(normalized, version)
            if exact and exact.status == "exact_version_not_supported":
                return None
        info = self.service.resolve_library(library, ecosystem, version, docs_url, None, source_type)
        if getattr(info, "status", None) == "exact_version_not_supported":
            return None
        if force_refresh or not getattr(info, "local", False) or getattr(info, "stale", False) or getattr(info, "status", "") in {"needs_docs_url", "needs_refresh"}:
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
        for chunk in result.results or []:
            token_estimate = max(1, len(chunk.content or "") // 4)
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
                "version": result.resolved_version or result.version,
                "freshness": "stale" if result.stale_before_refresh else "current",
                "why_selected": "library docs resolved through Docmancer registry",
                "token_estimate": token_estimate,
                "section": {"title": chunk.title, "freshness": "stale" if result.stale_before_refresh else "current"},
            }
            snippet = context_pack_snippet(chunk)
            if snippet:
                item["snippet"] = snippet
                item["surrounding_context"] = chunk.content
            items.append(item)
        return items

    def _dedupe_and_guard(self, items: list[dict[str, Any]], libs: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        seen = set()
        out = []
        dropped = 0
        reasons: list[str] = []
        requested = {lib.lower().replace("-", "_") for lib in libs}
        for item in items:
            scope = item.get("doc_scope")
            if scope not in {"project", "dependency", "library"}:
                dropped += 1
                reasons.append("invalid_doc_scope")
                continue
            if scope == "library" and requested:
                lib_text = " ".join(str(item.get(key) or "") for key in ("library", "library_id", "canonical_id")).lower().replace("-", "_")
                if not any(lib in lib_text for lib in requested):
                    dropped += 1
                    reasons.append("wrong_library_id")
                    continue
            source_identity = item.get("canonical_id") or item.get("source") or item.get("url") or item.get("path")
            if isinstance(source_identity, dict):
                source_identity = source_identity.get("url") or source_identity.get("path") or source_identity.get("source") or str(sorted(source_identity.items()))
            stable = (str(source_identity), item.get("heading_path") or (item.get("section") or {}).get("heading_path") or item.get("title"))
            if stable in seen:
                dropped += 1
                reasons.append("duplicate_source")
                continue
            seen.add(stable)
            out.append(item)
        return out, {"detected": bool(dropped), "dropped_count": dropped, "reason_codes": sorted(set(reasons))}

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
                "risk_flags": [],
            }
            if item.get("freshness") == "stale":
                entry["risk_flags"].append("stale")
                risky.append(entry)
            selected.append(entry)
        rejected = []
        if project_result and project_result.trust_contract:
            rejected.extend(project_result.trust_contract.get("rejected") or project_result.trust_contract.get("rejected_sources") or [])
            risky.extend(project_result.trust_contract.get("risky") or project_result.trust_contract.get("risky_sources") or [])
        for result in library_results:
            for warning in result.warnings or []:
                if "fallback" in warning or "stale" in warning:
                    risky.append({"source": result.library_id, "doc_scope": "library", "origin_lane": "library", "why_selected": str(warning), "freshness": "unknown", "version_binding": result.docs_exactness, "risk_flags": [str(warning)]})
        return {"selected": selected, "rejected": rejected, "risky": risky}

    @staticmethod
    def _source_summary(items: list[dict[str, Any]], trust: dict[str, Any]) -> dict[str, int]:
        return {
            "project": sum(1 for item in items if item.get("doc_scope") == "project"),
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
            if allow_latest_fallback and diagnostic.get("fallback_available") and diagnostic.get("used") is None:
                return {"expected": expected, "used": "latest", "match": False, "fallback": True, "status": "exact_version_fallback_latest"}
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
    def _overall_status(lanes: dict[str, Any], answer_available: bool) -> str:
        statuses = {lane.get("status") for lane in lanes.values() if lane.get("status") != "not_requested"}
        if not answer_available:
            return "confirmation_required" if "confirmation_required" in statuses else "not_found"
        if any(status in {"confirmation_required", "needs_input", "exact_version_not_supported", "empty_library_index", "error"} for status in statuses):
            return "partial_success"
        return "success"

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

    def _confirmation_result(self, *, question: str, mode_requested: str, mode_selected: str, routing: dict[str, Any], reason_code: str, confirmation_reason: str | None, lanes: dict[str, Any], next_action: dict[str, Any] | None = None, arguments_patch: dict[str, Any] | None = None, lane_details: dict[str, Any] | None = None, warnings: list[Any] | None = None) -> UnifiedDocsContextResult:
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
            warnings=warnings or [],
            contamination={"detected": False, "dropped_count": 0, "reason_codes": []},
            lane_details=lane_details or {},
        )
