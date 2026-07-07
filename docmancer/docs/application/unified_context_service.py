from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass, replace
from typing import Any

from docmancer.docs.application.project_context_service import context_pack_snippet
from docmancer.docs.domain.library_source_options import library_docs_source_options, source_required_diagnostics
from docmancer.docs.domain.snippets import build_snippet_presentation, validate_response_style
from docmancer.docs.exact_version import resolve_python_versioned_docs
from docmancer.docs.models import DocsResult, ProjectContextResult, UnifiedDocsContextResult
from docmancer.docs.resolver import docs_snapshot_is_exact


_LATEST_ALIASES = {"latest", "stable", "main", "*"}
_PATCH_TASK_TERMS = {
    "change",
    "changed",
    "changes",
    "changing",
    "diff",
    "diffs",
    "edit",
    "edited",
    "editing",
    "edits",
    "fix",
    "fixed",
    "fixes",
    "fixing",
    "implement",
    "implemented",
    "implementing",
    "implements",
    "modify",
    "modified",
    "modifies",
    "modifying",
    "patch",
    "patched",
    "patching",
    "patches",
    "refactor",
    "refactored",
    "refactoring",
    "refactors",
    "validate",
    "validated",
    "validates",
    "validating",
}
_IMPERATIVE_PATCH_TASK_TERMS = {
    "add",
    "added",
    "adding",
    "adds",
    "create",
    "created",
    "creates",
    "creating",
    "delete",
    "deleted",
    "deletes",
    "deleting",
    "migrate",
    "migrated",
    "migrates",
    "migrating",
    "remove",
    "removed",
    "removes",
    "removing",
    "rename",
    "renamed",
    "renames",
    "renaming",
    "update",
    "updated",
    "updates",
    "updating",
    "upgrade",
    "upgraded",
    "upgrades",
    "upgrading",
}
_IMPERATIVE_PATCH_TASK_PREFIX_TERMS = {"please", "task", "todo", "todos"}
_PATCH_TASK_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _looks_like_imperative_patch_task(tokens: list[str]) -> bool:
    for token in tokens:
        if token in _IMPERATIVE_PATCH_TASK_PREFIX_TERMS:
            continue
        return token in _IMPERATIVE_PATCH_TASK_TERMS
    return False


def _snippet_first_fallback_question(question: str, library: str) -> str:
    text = (question or "").strip()
    base = text if text else library
    lowered = base.lower()
    if "example" in lowered or "code" in lowered:
        return base
    return f"{base} example code snippet"


def _without_snippet_not_available(warnings: list[Any]) -> list[Any]:
    return [
        warning
        for warning in warnings
        if warning != "snippet_not_available"
        and not (isinstance(warning, dict) and warning.get("code") == "snippet_not_available")
    ]


def _exact_version_match(result: DocsResult) -> bool | None:
    if not result.requested_version:
        return None
    url = result.identity.get("docs_url_resolved") or result.identity.get("docs_url") if isinstance(result.identity, dict) else None
    return docs_snapshot_is_exact(result.requested_version, url) and (result.resolved_version or result.version) == result.requested_version


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
        prefetch_auto: bool | None = None,
        details: bool | None = None,
        response_style: str | None = None,
    ) -> UnifiedDocsContextResult:
        response_style = validate_response_style(response_style)
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
        if prepare_project_docs and project_path and mode_selected in {"project", "mixed", "dependency"}:
            bootstrap = self.service.bootstrap_project_docs(project_path, question=question)
            lane_details["project_bootstrap"] = self._to_dict(bootstrap)
            bootstrap_reason = getattr(bootstrap, "reason_code", None) or "project_docs_confirmation_required"
            if getattr(bootstrap, "requires_confirmation", False) and "dependency_docs" not in bootstrap_reason:
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
            delegated_mode = "auto" if project_auto and effective_allow_network else "project-only"
            routing["delegated_mode"] = delegated_mode
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, module=module, module_path=module_path, scope=scope, mode=delegated_mode, response_style=response_style, allow_network=effective_allow_network)
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
                    lanes=lanes,
                    lane_details=lane_details if details else {},
                )
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, library=library, libraries=libraries, ecosystem=ecosystem, version=version, module=module, module_path=module_path, scope=scope, mode="deps-only", response_style=response_style, allow_network=effective_allow_network)
        elif mode_selected == "mixed":
            project_result = self.service.get_project_context(project_path, question, tokens=tokens, limit=limit, expand=expand, library=library, libraries=libraries, ecosystem=ecosystem, version=version, module=module, module_path=module_path, scope=scope, mode="auto", response_style=response_style, allow_network=effective_allow_network)
            routing["dependency_detected"] = bool(getattr(project_result, "dependency_docs", None))
            explicit_library_results = []
            for lib in libs:
                safe = self._ensure_library_safe(lib, ecosystem, version, source_type, docs_url, force_refresh, effective_allow_network)
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
                safe = self._ensure_library_safe(lib, ecosystem, version, source_type, docs_url, force_refresh, effective_allow_network)
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
            lanes["project"] = {"status": project_result.status, "source_count": len([i for i in project_items if i.get("doc_scope") == "project"])}
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
        self._refresh_lane_counts(lanes, context_pack)
        trust_contract = self._trust_contract(context_pack, project_result, library_results)
        source_summary = self._source_summary(context_pack, trust_contract)
        snippet_presentation = build_snippet_presentation(
            context_pack,
            question=question,
            response_style=response_style,
            lane_priority=lane_priority,
        )
        if snippet_fallback and snippet_presentation.primary_snippet:
            warnings = _without_snippet_not_available(warnings)
        answer_available = bool(context_pack)
        pending_actions = self._collect_pending_actions(pending_lane_results)
        requested_lanes = [name for name, lane in lanes.items() if lane.get("status") != "not_requested"]
        successful_lanes = [name for name, lane in lanes.items() if self._lane_succeeded(lane)]
        pending_confirmation_lanes = [name for name, lane in lanes.items() if lane.get("requires_confirmation") or lane.get("status") == "confirmation_required"]
        failed_lanes = [name for name, lane in lanes.items() if lane.get("status") not in {"not_requested", "success", "partial_success", "confirmation_required"} and not self._lane_succeeded(lane)]
        status = self._aggregate_status(requested_lanes, successful_lanes, pending_confirmation_lanes, failed_lanes)
        reason = None if answer_available else "no_docs_context_available"
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
        if status == "failed":
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
                    "reason_code": "library_docs_failed",
                    "project_path_used": False,
                    "libraries_requested": [library],
                    "dependency_detected": False,
                    "failed_status": status,
                    "failed_message": message,
                },
                reason_code="library_docs_failed",
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
            snippet = context_pack_snippet(chunk)
            if snippet:
                item["snippet"] = snippet
                item["surrounding_context"] = chunk.content
            items.append(item)
        return items

    def _dedupe_and_guard(self, items: list[dict[str, Any]], libs: list[str], project_path: str | None) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        seen = set()
        out = []
        contamination_dropped = 0
        contamination_reasons: list[str] = []
        dedup_dropped = 0
        dedup_reasons: list[str] = []
        requested = {lib.lower().replace("-", "_") for lib in libs}
        for item in items:
            scope = item.get("doc_scope")
            if scope not in {"project", "dependency", "library"}:
                contamination_dropped += 1
                contamination_reasons.append("wrong_doc_scope")
                continue
            if scope == "project" and project_path:
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
            stable = (str(source_identity), item.get("heading_path") or (item.get("section") or {}).get("heading_path") or item.get("title"))
            if stable in seen:
                dedup_dropped += 1
                dedup_reasons.append("duplicate_source")
                continue
            seen.add(stable)
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
            count = sum(1 for item in items if item.get("doc_scope") == scope)
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
        scopes = {item.get("doc_scope") for item in items if item.get("doc_scope") in {"project", "dependency"}}
        if scopes == {"dependency"}:
            return "dependency"
        if scopes == {"project", "dependency"}:
            return "mixed"
        return "project"

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
            deduplication={"dropped_count": 0, "reason_codes": []},
            lane_details=lane_details or {},
        )
