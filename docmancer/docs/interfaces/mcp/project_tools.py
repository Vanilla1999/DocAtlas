from __future__ import annotations

from dataclasses import asdict
from copy import deepcopy
from typing import Any

from docmancer.docs.interfaces.mcp.error_contract import build_bad_request_payload
from docmancer.docs.interfaces.mcp.output_contract import compact_mcp_payload, json_bytes, normalize_output_mode
from docmancer.docs.patch_plan_context import build_patch_plan_context
from docmancer.docs.service import LibraryDocsService


MCP_COMPACT_OUTPUT_MAX_BYTES = 32_000
_MCP_COMPACT_TEXT_KEYS = {"content", "snippet", "text", "primary_snippet"}
_MCP_COMPACT_DEFAULT_TEXT_LIMIT = 1_200
_MCP_COMPACT_LIST_LIMIT = 8
_MCP_HARD_CAP_SECTION_ORDER = (
    "context_pack",
    "supporting_snippets",
    "trust_contract",
    "answer_outline",
    "project_docs",
    "dependency_docs",
    "diagnostics",
    "metrics",
    "snippet_metrics",
    "recommended_next_actions",
    "next_actions",
    "arguments_patch",
)


PROJECT_TOOL_NAMES = {
    "inspect_project_docs",
    "ingest_project_docs",
    "sync_project_docs",
    "bootstrap_project_docs",
    "get_project_docs",
    "get_project_context",
    "get_patch_plan_context",
    "get_patch_constraints",
    "validate_patch_against_constraints",
    "prefetch_project_docs",
    "prefetch_project_dependency_docs",
}

_MCP_MAX_TOKENS = 20_000
_MCP_MAX_PROJECT_LIMIT = 20
_MCP_MAX_PATCH_CONSTRAINTS = 40
_MCP_MAX_PATCH_TOKENS = 8_000


def _bad_request(reason_code: str, message: str) -> dict[str, Any]:
    return build_bad_request_payload(reason_code, message)


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bounded_int_arg(
    args: dict[str, Any],
    key: str,
    *,
    default: int | None = None,
    min_value: int = 1,
    max_value: int,
) -> int | None:
    value = args.get(key)
    if value is None:
        return default
    number = int(value)
    return max(min_value, min(max_value, number))


def project_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in PROJECT_TOOL_NAMES]


def _json_bytes(payload: dict[str, Any]) -> int:
    return json_bytes(payload)


def _truncate_text(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    suffix = f" … [truncated {len(value) - limit} chars]"
    return value[: max(0, limit - len(suffix))].rstrip() + suffix, True


def _compact_value_for_mcp(value: Any, *, text_limit: int, list_limit: int, key: str | None = None, stats: dict[str, int]) -> Any:
    if isinstance(value, str):
        limit = text_limit if key in _MCP_COMPACT_TEXT_KEYS else max(text_limit * 2, text_limit)
        compact, truncated = _truncate_text(value, limit)
        if truncated:
            stats["truncated_strings"] += 1
            stats["truncated_chars"] += len(value) - len(compact)
        return compact
    if isinstance(value, list):
        items = value[:list_limit]
        omitted = max(0, len(value) - len(items))
        if omitted:
            stats["omitted_list_items"] += omitted
        return [_compact_value_for_mcp(item, text_limit=text_limit, list_limit=list_limit, stats=stats) for item in items]
    if isinstance(value, dict):
        return {k: _compact_value_for_mcp(v, text_limit=text_limit, list_limit=list_limit, key=str(k), stats=stats) for k, v in value.items()}
    return value


def _summarize_omitted_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"omitted": True, "type": "object", "key_count": len(value), "keys": list(value.keys())[:12]}
    if isinstance(value, list):
        return {"omitted": True, "type": "array", "item_count": len(value)}
    if isinstance(value, str):
        return {"omitted": True, "type": "string", "char_count": len(value)}
    return {"omitted": True, "type": type(value).__name__}


def _enforce_mcp_hard_cap(payload: dict[str, Any], *, max_bytes: int) -> dict[str, Any]:
    """Deterministically summarize remaining large sections until the MCP cap is absolute."""

    if _json_bytes(payload) <= max_bytes:
        return payload

    compact = deepcopy(payload)
    compaction = dict(compact.get("mcp_compaction") or {})
    compaction.update({"max_bytes": max_bytes, "truncated": True, "hard_cap_enforced": True})
    compact["mcp_compaction"] = compaction

    omitted_sections: list[str] = []
    for key in _MCP_HARD_CAP_SECTION_ORDER:
        if _json_bytes(compact) <= max_bytes:
            return compact
        if key in compact and compact[key] not in ({}, [], None):
            compact[key] = _summarize_omitted_value(compact[key])
            omitted_sections.append(key)
            compact["mcp_compaction"]["omitted_sections"] = omitted_sections

    if _json_bytes(compact) <= max_bytes:
        return compact

    keep_keys = {
        "project_path",
        "question",
        "query",
        "status",
        "tool",
        "schema_version",
        "answer_available",
        "answer_type",
        "answer_completeness",
        "mode",
        "reason",
        "message",
        "response_style",
        "primary_snippet",
        "next_action",
        "output_mode",
        "full_output_available",
        "requires_confirmation",
        "confirmation_reason",
        "warnings",
        "mcp_compaction",
    }
    omitted_fields = [key for key in compact if key not in keep_keys]
    compact = {key: value for key, value in compact.items() if key in keep_keys}
    compact["mcp_compaction"] = {
        **dict(compact.get("mcp_compaction") or {}),
        "omitted_fields": omitted_fields[:40],
        "omitted_field_count": len(omitted_fields),
    }
    stats = {"truncated_strings": 0, "truncated_chars": 0, "omitted_list_items": 0}
    compact = _compact_value_for_mcp(compact, text_limit=160, list_limit=3, stats=stats)
    if _json_bytes(compact) <= max_bytes:
        return compact

    compact["warnings"] = _summarize_omitted_value(compact.get("warnings") or [])
    return compact


def _compact_mcp_payload(
    payload: dict[str, Any],
    *,
    max_bytes: int = MCP_COMPACT_OUTPUT_MAX_BYTES,
    page: int | None = None,
    page_size: int | None = None,
    include_sections: list[str] | None = None,
) -> dict[str, Any]:
    """Apply the MCP compact-response hard cap without changing explicit full output."""
    return compact_mcp_payload(
        payload,
        max_bytes=max_bytes,
        page=page,
        page_size=page_size,
        include_sections=include_sections,
    )


def _project_sources_summary(result: dict[str, Any]) -> dict[str, int]:
    return {
        "candidates": len(result.get("candidate_sources") or []),
        "indexed": len(result.get("indexed_sources") or []),
        "stale": len(result.get("stale_sources") or []),
        "ignored": len(result.get("ignored_sources") or []),
    }


def _compact_project_docs(result: dict[str, Any], *, omit_results: bool = False) -> dict[str, Any]:
    message = result.get("message")
    if isinstance(message, str) and message.startswith("Returned "):
        message = None
    compact = {
        "project_path": result.get("project_path"),
        "query": result.get("query"),
        "status": result.get("status"),
        "tool": result.get("tool"),
        "reason_code": result.get("reason_code"),
        "answer_available": result.get("answer_available"),
        "message": message,
        "results": [] if omit_results else (result.get("results") or []),
        "next_action": result.get("next_action") or {},
        "next_actions": result.get("next_actions") or [],
        "arguments_patch": result.get("arguments_patch") or {},
        "source_summary": _project_sources_summary(result),
        "diagnostics": result.get("diagnostics") or {},
        "warnings": result.get("warnings") or [],
    }
    if omit_results:
        compact["omitted"] = True
        compact["result_count"] = len(result.get("results") or [])
        compact["see"] = "context_pack"
    if result.get("requires_confirmation"):
        compact["requires_confirmation"] = result.get("requires_confirmation")
        compact["confirmation_reason"] = result.get("confirmation_reason")
    return compact


def _compact_project_context(result: dict[str, Any]) -> dict[str, Any]:
    message = result.get("message")
    if isinstance(message, str) and message.startswith("Returned "):
        message = None
    compact = {
        "project_path": result.get("project_path"),
        "question": result.get("question"),
        "status": result.get("status"),
        "tool": result.get("tool"),
        "schema_version": result.get("schema_version"),
        "answer_available": result.get("answer_available"),
        "answer_type": result.get("answer_type"),
        "answer_completeness": result.get("answer_completeness") or {},
        "mode": result.get("mode"),
        "reason": result.get("reason"),
        "message": message,
        "response_style": result.get("response_style"),
        "primary_snippet": result.get("primary_snippet"),
        "supporting_snippets": result.get("supporting_snippets") or [],
        "context_pack": result.get("context_pack") or [],
        "answer_outline": result.get("answer_outline") or {},
        "trust_contract": result.get("trust_contract") or {},
        "next_actions": result.get("next_actions") or [],
        "recommended_next_actions": result.get("recommended_next_actions") or [],
        "next_action": result.get("next_action") or {},
        "arguments_patch": result.get("arguments_patch") or {},
        "snippet_metrics": result.get("snippet_metrics") or {},
        "metrics": result.get("metrics") or {},
        "diagnostics": result.get("diagnostics") or {},
        "warnings": result.get("warnings") or [],
    }
    if result.get("requires_confirmation"):
        compact["requires_confirmation"] = result.get("requires_confirmation")
        compact["confirmation_reason"] = result.get("confirmation_reason")
    project_docs = result.get("project_docs") or {}
    if project_docs:
        compact["project_docs"] = _compact_project_docs(project_docs, omit_results=True)
    dependency_docs = result.get("dependency_docs") or {}
    if dependency_docs:
        compact["dependency_docs"] = {
            "status": dependency_docs.get("status"),
            "reason_code": dependency_docs.get("reason_code"),
            "answer_available": dependency_docs.get("answer_available"),
            "results_count": len(dependency_docs.get("results") or []),
            "source_summary": {
                "selected": len(dependency_docs.get("selected_sources") or []),
                "rejected": len(dependency_docs.get("rejected_sources") or []),
                "risky": len(dependency_docs.get("risky_sources") or []),
            },
        }
    return compact


def _answer_project_context(result: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "status": result.get("status"),
        "answer_available": result.get("answer_available"),
        "answer_type": result.get("answer_type"),
        "mode": result.get("mode"),
        "reason": result.get("reason"),
        "response_style": result.get("response_style"),
        "primary_snippet": result.get("primary_snippet"),
        "selected_sources": _trust_sources(result.get("trust_contract"), "selected"),
        "next_actions": result.get("next_actions") or [],
        "next_action": result.get("next_action") or {},
        "arguments_patch": result.get("arguments_patch") or {},
        "diagnostics": result.get("diagnostics") or {},
        "warnings": result.get("warnings") or [],
    }
    if result.get("requires_confirmation"):
        compact["requires_confirmation"] = result.get("requires_confirmation")
        compact["confirmation_reason"] = result.get("confirmation_reason")
    return {key: value for key, value in compact.items() if value not in (None, {}, [])}


def _debug_project_context(result: dict[str, Any]) -> dict[str, Any]:
    return _compact_project_context(result)


def _project_context_output_mode(args: dict[str, Any]) -> str:
    return normalize_output_mode(args, details_fallback=True)


def _trust_sources(contract: Any, lane: str) -> list[dict[str, Any]]:
    if not isinstance(contract, dict):
        return []
    sources = contract.get("sources")
    if isinstance(sources, dict) and isinstance(sources.get(lane), list):
        return sources[lane]
    legacy_key = f"{lane}_sources"
    value = contract.get(lane) or contract.get(legacy_key)
    return value if isinstance(value, list) else []


def _strip_mcp_debug_noise(payload: dict[str, Any]) -> dict[str, Any]:
    output_mode = str(payload.get("output_mode") or "answer")
    compaction = payload.get("mcp_compaction")
    if isinstance(compaction, dict) and compaction.get("truncated"):
        payload["response_truncated"] = True
        payload["mcp_compaction"] = {
            key: compaction.get(key)
            for key in (
                "max_bytes",
                "truncated",
                "hard_cap_enforced",
                "content_omitted",
                "truncated_strings",
                "truncated_chars",
                "omitted_list_items",
                "omitted_sections",
            )
            if key in compaction
        }
        warnings = [
            warning for warning in (payload.get("warnings") or [])
            if not (isinstance(warning, dict) and str(warning.get("code") or "").startswith("mcp_compact_output_"))
        ]
        if not any(isinstance(warning, dict) and warning.get("code") == "mcp_response_truncated" for warning in warnings):
            warnings.append({
                "code": "mcp_response_truncated",
                "message": "MCP response was compacted/truncated; narrow query/limit/tokens or use output_mode='full' only when necessary.",
            })
        payload["warnings"] = warnings
        return _attach_output_contract(payload, output_mode=output_mode)

    payload.pop("mcp_compaction", None)
    warnings = [
        warning for warning in (payload.get("warnings") or [])
        if not (isinstance(warning, dict) and str(warning.get("code") or "").startswith("mcp_compact_output_"))
    ]
    payload["warnings"] = warnings
    return _attach_output_contract(payload, output_mode=output_mode)


def _attach_output_contract(payload: dict[str, Any], *, output_mode: str) -> dict[str, Any]:
    raw_compaction = payload.get("mcp_compaction")
    compaction: dict[str, Any] = raw_compaction if isinstance(raw_compaction, dict) else {}
    truncated = bool(payload.get("response_truncated") or compaction.get("truncated"))
    payload["output_contract"] = {
        "mode": output_mode,
        "complete": not truncated,
        "truncated": truncated,
        "safe_to_use_as_complete_context": not truncated,
        "retry_with": {"output_mode": "debug", "page_size": 5, "narrow_query": True} if truncated and output_mode != "debug" else None,
        "omitted": {
            "fields": compaction.get("omitted_fields", []),
            "list_items": compaction.get("omitted_list_items", 0),
            "content_blocks": compaction.get("omitted_content_blocks", 0),
        },
    }
    return payload


def _patch_constraints_output_mode(args: dict[str, Any]) -> str:
    output_mode = str(args.get("output_mode") or "compact").lower()
    return output_mode if output_mode in {"compact", "debug", "full"} else "compact"


def _compact_patch_evidence(items: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        snippet = item.get("snippet")
        if isinstance(snippet, str) and len(snippet) > 300:
            snippet = snippet[:297].rstrip() + "..."
        compact.append({
            key: value
            for key, value in {
                "path": item.get("path"),
                "line_start": item.get("line_start"),
                "line_end": item.get("line_end"),
                "matched_terms": item.get("matched_terms") or item.get("terms"),
                "snippet": snippet,
            }.items()
            if value not in (None, [], "")
        })
    return compact


def _compact_symbol_candidates(items: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in {
                "symbol": item.get("symbol") or item.get("name"),
                "path": item.get("path"),
                "score": item.get("score"),
                "reason": item.get("reason"),
            }.items()
            if value not in (None, [], "")
        }
        for item in items[:limit]
        if isinstance(item, dict)
    ]


def _compact_patch_constraints(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": result.get("tool"),
        "status": result.get("status"),
        "reason_code": result.get("reason_code"),
        "answer_available": result.get("answer_available"),
        "task": result.get("task"),
        "constraints": result.get("constraints") or [],
        "schema_version": result.get("schema_version"),
        "contract_kind": result.get("contract_kind"),
        "contract_id": result.get("contract_id"),
        "project_path": result.get("project_path"),
        "index_state": result.get("index_state") or {},
        "token_budget": result.get("token_budget") or {},
        "next_actions": result.get("next_actions") or [],
        "forbidden_edits": result.get("forbidden_edits") or [],
        "dependency_contracts": result.get("dependency_contracts") or [],
        "source_of_truth_rules": result.get("source_of_truth_rules") or [],
        "suggested_checks": result.get("suggested_checks") or [],
        "warnings": result.get("warnings") or [],
        "sources": result.get("sources") or [],
        "source_evidence": _compact_patch_evidence(result.get("source_evidence") or []),
        "symbol_candidates": _compact_symbol_candidates(result.get("symbol_candidates") or []),
        "token_estimate": result.get("token_estimate"),
        "confidence": result.get("confidence"),
    }


def _add_project_context_output_warning(payload: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    if not args.get("details") or _project_context_output_mode(args) in {"full", "debug"}:
        return payload
    warnings = list(payload.get("warnings") or [])
    warning = {
        "code": "project_context_full_output_requires_output_mode_full",
        "message": "details=true no longer returns full get_project_context payloads at the MCP boundary; pass output_mode='full' only when a full dump is explicitly required.",
    }
    if warning not in warnings:
        warnings.append(warning)
    payload["warnings"] = warnings
    payload["output_mode"] = _project_context_output_mode(args)
    payload["full_output_available"] = True
    return payload


def _compact_inspect_project_docs(result: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "project_path": result.get("project_path"),
        "project_detected": result.get("project_detected"),
        "reason_code": result.get("reason_code"),
        "next_action": result.get("next_action") or {},
        "arguments_patch": result.get("arguments_patch") or {},
        "source_summary": _project_sources_summary(result),
        "recommended_next_actions": result.get("recommended_next_actions") or [],
        "agent_message": result.get("agent_message"),
        "user_message": result.get("user_message"),
        "diagnostics": result.get("diagnostics") or {},
        "warnings": result.get("warnings") or [],
    }
    if result.get("requires_confirmation"):
        compact["requires_confirmation"] = result.get("requires_confirmation")
        compact["confirmation_reason"] = result.get("confirmation_reason")
    return compact


def _compact_ingest_project_docs(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "project_path": (result.get("project") or {}).get("project_path"),
        "candidate_count": result.get("candidate_count") or 0,
        "sections_indexed": result.get("sections_indexed") or 0,
        "source_summary": {
            "indexed": len(result.get("indexed_sources") or []),
            "missing": len(result.get("missing_sources") or []),
            "skipped": len(result.get("skipped_sources") or []),
        },
        "message": result.get("message"),
        "warnings": result.get("warnings") or [],
    }


def _compact_sync_project_docs(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "project_path": (result.get("project") or {}).get("project_path"),
        "candidate_count": result.get("candidate_count") or 0,
        "summary": {
            "current": result.get("current_count") or 0,
            "new": result.get("new_count") or 0,
            "changed": result.get("changed_count") or 0,
            "orphaned": result.get("orphaned_count") or 0,
            "orphaned_removed": result.get("orphaned_removed") or 0,
            "dedup_removed": result.get("dedup_removed") or 0,
            "stale_removed": result.get("stale_removed") or 0,
            "missing": len(result.get("missing_sources") or []),
            "sections_indexed": result.get("sections_indexed") or 0,
        },
        "message": result.get("message"),
        "diagnostics": result.get("diagnostics") or {},
        "warnings": result.get("warnings") or [],
    }


def _compact_bootstrap_project_docs(result: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "project_path": result.get("project_path"),
        "question": result.get("question"),
        "status": result.get("status"),
        "tool": result.get("tool"),
        "reason_code": result.get("reason_code"),
        "actions_taken": result.get("actions_taken") or [],
        "next_action": result.get("next_action") or {},
        "arguments_patch": result.get("arguments_patch") or {},
        "agent_message": result.get("agent_message"),
        "user_message": result.get("user_message"),
        "diagnostics": result.get("diagnostics") or {},
        "warnings": result.get("warnings") or [],
    }
    inspect_result = result.get("inspect_result") or {}
    if inspect_result:
        compact["inspect"] = _compact_inspect_project_docs(inspect_result)
    sync_result = result.get("sync_result") or {}
    if sync_result:
        compact["sync"] = _compact_sync_project_docs(sync_result)
    ingest_result = result.get("ingest_result") or {}
    if ingest_result:
        compact["ingest"] = _compact_ingest_project_docs(ingest_result)
    if result.get("requires_confirmation"):
        compact["requires_confirmation"] = result.get("requires_confirmation")
        compact["confirmation_reason"] = result.get("confirmation_reason")
    return compact


def handle_project_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    project_docs_app = getattr(service, "project_docs", service)
    project_context_app = getattr(service, "project_context", service)
    patch_plan_context_app = getattr(service, "patch_plan_context", service)
    patch_constraints_app = getattr(service, "patch_constraints", service)
    patch_validation_app = getattr(service, "patch_constraint_validation", service)
    dependency_docs_app = getattr(service, "dependency_docs", service)
    if name == "inspect_project_docs":
        result = asdict(project_docs_app.inspect_project_docs(args["project_path"]))
        return result if args.get("details") else _compact_inspect_project_docs(result)
    if name == "ingest_project_docs":
        result = asdict(project_docs_app.ingest_project_docs(args["project_path"], skip_known=bool(args.get("skip_known") if args.get("skip_known") is not None else True), with_vectors=bool(args.get("with_vectors") if args.get("with_vectors") is not None else True)))
        return result if args.get("details") else _compact_ingest_project_docs(result)
    if name == "sync_project_docs":
        result = asdict(project_docs_app.sync_project_docs(args["project_path"], with_vectors=bool(args.get("with_vectors") if args.get("with_vectors") is not None else True)))
        return result if args.get("details") else _compact_sync_project_docs(result)
    if name == "bootstrap_project_docs":
        result = asdict(project_docs_app.bootstrap_project_docs(args["project_path"], question=args.get("question")))
        return result if args.get("details") else _compact_bootstrap_project_docs(result)
    if name == "get_project_docs":
        query = _clean_string(args.get("query"))
        if not query:
            return _bad_request("empty_query", "query must not be empty")
        result = asdict(project_docs_app.get_project_docs(args["project_path"], query, tokens=_bounded_int_arg(args, "tokens", max_value=_MCP_MAX_TOKENS), limit=_bounded_int_arg(args, "limit", default=None, max_value=_MCP_MAX_PROJECT_LIMIT), expand=args.get("expand"), module=args.get("module"), module_path=args.get("module_path"), scope=args.get("scope")))
        return result if args.get("details") else _compact_project_docs(result)
    if name == "get_project_context":
        question = _clean_string(args.get("question"))
        if not question:
            return _bad_request("empty_question", "question must not be empty")
        result = asdict(project_context_app.get_project_context(args["project_path"], question, tokens=_bounded_int_arg(args, "tokens", max_value=_MCP_MAX_TOKENS), limit=_bounded_int_arg(args, "limit", default=None, max_value=_MCP_MAX_PROJECT_LIMIT), expand=args.get("expand"), library=args.get("library"), libraries=args.get("libraries"), ecosystem=args.get("ecosystem"), version=args.get("version"), module=args.get("module"), module_path=args.get("module_path"), scope=args.get("scope"), mode=args.get("mode") or "auto", response_style=args.get("response_style"), allow_network=bool(args.get("allow_network") or False)))
        output_mode = _project_context_output_mode(args)
        if output_mode == "full":
            result["output_mode"] = "full"
            return result
        if output_mode == "debug":
            payload = _debug_project_context(result)
            payload["output_mode"] = "debug"
            return _attach_output_contract(_compact_mcp_payload(payload, page=_bounded_int_arg(args, "page", default=1, max_value=10_000), page_size=_bounded_int_arg(args, "page_size", default=None, max_value=20), include_sections=args.get("include_sections")), output_mode="debug")
        payload = _answer_project_context(result) if output_mode == "answer" else _compact_project_context(result)
        payload["output_mode"] = output_mode
        payload = _compact_mcp_payload(_add_project_context_output_warning(payload, args), page=_bounded_int_arg(args, "page", default=1, max_value=10_000), page_size=_bounded_int_arg(args, "page_size", default=None, max_value=20), include_sections=args.get("include_sections"))
        return _strip_mcp_debug_noise(payload)
    if name == "get_patch_plan_context":
        question = _clean_string(args.get("question"))
        if not question:
            return _bad_request("empty_question", "question must not be empty")
        builder = getattr(patch_plan_context_app, "get_patch_plan_context", build_patch_plan_context)
        return builder(
            question,
            project_path=args.get("project_path"),
            changed_files=args.get("changed_files"),
            symbol_queries=args.get("symbol_queries"),
            design_context=args.get("design_context"),
            include_dependency_source=bool(args.get("include_dependency_source") if args.get("include_dependency_source") is not None else True),
            max_files=_bounded_int_arg(args, "max_files", default=12, max_value=50),
            max_snippets=_bounded_int_arg(args, "max_snippets", default=16, max_value=40),
            max_tokens=_bounded_int_arg(args, "max_tokens", default=2400, min_value=200, max_value=12000),
            output_mode=args.get("output_mode") or "compact",
        )
    if name == "get_patch_constraints":
        question = _clean_string(args.get("question"))
        if not question:
            return _bad_request("empty_question", "question must not be empty")
        result = asdict(patch_constraints_app.get_patch_constraints(
            question,
            project_path=args.get("project_path"),
            changed_files=args.get("changed_files"),
            max_constraints=_bounded_int_arg(args, "max_constraints", default=40, max_value=_MCP_MAX_PATCH_CONSTRAINTS),
            max_tokens=_bounded_int_arg(args, "max_tokens", default=8000, max_value=_MCP_MAX_PATCH_TOKENS),
            include_sources=bool(args.get("include_sources") if args.get("include_sources") is not None else True),
        ))
        result.setdefault("tool", "get_patch_constraints")
        result.setdefault("status", "success")
        result.setdefault("reason_code", None)
        result.setdefault("answer_available", bool(result.get("constraints")))
        output_mode = _patch_constraints_output_mode(args)
        if output_mode == "full":
            result["output_mode"] = "full"
            return result
        payload = _compact_patch_constraints(result)
        payload["output_mode"] = output_mode
        payload = _compact_mcp_payload(payload)
        return payload if output_mode == "debug" else _strip_mcp_debug_noise(payload)
    if name == "validate_patch_against_constraints":
        constraints = args.get("constraints")
        if constraints is None:
            return _bad_request("empty_constraints", "constraints are required")
        return asdict(patch_validation_app.validate_patch_against_constraints(
            constraints,
            project_path=args.get("project_path"),
            changed_files=args.get("changed_files"),
            patch_diff=args.get("patch_diff"),
            strict=bool(args.get("strict") or False),
        ))
    if name in {"prefetch_project_docs", "prefetch_project_dependency_docs"}:
        result = dependency_docs_app.prefetch_project_dependency_docs if name == "prefetch_project_dependency_docs" else dependency_docs_app.prefetch_project_docs
        payload = asdict(result(args["project_path"], include_flutter=bool(args.get("include_flutter") if args.get("include_flutter") is not None else True), include_dart=bool(args.get("include_dart") or False), include_rust=bool(args.get("include_rust") if args.get("include_rust") is not None else True), include_packages=args.get("include_packages") or [], force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
        if name == "prefetch_project_docs":
            payload.setdefault("warnings", []).append({"code": "deprecated_tool_alias", "message": "Use prefetch_project_dependency_docs instead; this alias will be removed in a future release."})
        return payload
    return None
