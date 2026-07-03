from __future__ import annotations

from dataclasses import asdict
import json
from copy import deepcopy
from typing import Any

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
    "get_patch_constraints",
    "validate_patch_against_constraints",
    "prefetch_project_docs",
    "prefetch_project_dependency_docs",
}


def project_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in PROJECT_TOOL_NAMES]


def _json_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


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


def _compact_mcp_payload(payload: dict[str, Any], *, max_bytes: int = MCP_COMPACT_OUTPUT_MAX_BYTES) -> dict[str, Any]:
    """Apply the MCP compact-response hard cap without changing explicit full output."""

    if _json_bytes(payload) <= max_bytes:
        return payload

    last_compact = deepcopy(payload)
    last_stats: dict[str, int] = {"truncated_strings": 0, "truncated_chars": 0, "omitted_list_items": 0}
    for text_limit, list_limit in ((_MCP_COMPACT_DEFAULT_TEXT_LIMIT, _MCP_COMPACT_LIST_LIMIT), (800, 6), (480, 4), (240, 3), (120, 2)):
        stats = {"truncated_strings": 0, "truncated_chars": 0, "omitted_list_items": 0}
        compact = _compact_value_for_mcp(payload, text_limit=text_limit, list_limit=list_limit, stats=stats)
        compact["mcp_compaction"] = {
            "max_bytes": max_bytes,
            "truncated": True,
            "text_limit": text_limit,
            "list_limit": list_limit,
            "truncated_strings": stats["truncated_strings"],
            "truncated_chars": stats["truncated_chars"],
            "omitted_list_items": stats["omitted_list_items"],
        }
        warnings = list(compact.get("warnings") or [])
        warning = {
            "code": "mcp_compact_output_truncated",
            "message": f"Compact MCP response was truncated to stay under {max_bytes} bytes; pass output_mode='full' only when a full get_project_context dump is explicitly required.",
        }
        if warning not in warnings:
            warnings.append(warning)
        compact["warnings"] = warnings
        last_compact = compact
        last_stats = stats
        if _json_bytes(compact) <= max_bytes:
            return compact

    compact = deepcopy(last_compact)
    compact["context_pack"] = []
    compact["supporting_snippets"] = []
    compact["mcp_compaction"] = {
        "max_bytes": max_bytes,
        "truncated": True,
        "content_omitted": True,
        "truncated_strings": last_stats["truncated_strings"],
        "truncated_chars": last_stats["truncated_chars"],
        "omitted_list_items": last_stats["omitted_list_items"],
    }
    compact["warnings"] = [
        *(compact.get("warnings") or []),
        {
            "code": "mcp_compact_output_content_omitted",
            "message": f"Large context fields were omitted to keep the compact MCP response under {max_bytes} bytes; use narrower tokens/limit or explicit full output when appropriate.",
        },
    ]
    return _enforce_mcp_hard_cap(compact, max_bytes=max_bytes)


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
        "primary_snippet": result.get("primary_snippet"),
        "selected_sources": (result.get("trust_contract") or {}).get("selected") or (result.get("trust_contract") or {}).get("selected_sources") or [],
        "next_actions": result.get("next_actions") or [],
        "next_action": result.get("next_action") or {},
        "arguments_patch": result.get("arguments_patch") or {},
        "warnings": result.get("warnings") or [],
    }
    if result.get("requires_confirmation"):
        compact["requires_confirmation"] = result.get("requires_confirmation")
        compact["confirmation_reason"] = result.get("confirmation_reason")
    return {key: value for key, value in compact.items() if value not in (None, {}, [])}


def _debug_project_context(result: dict[str, Any]) -> dict[str, Any]:
    return _compact_project_context(result)


def _project_context_output_mode(args: dict[str, Any]) -> str:
    output_mode = str(args.get("output_mode") or ("debug" if args.get("details") else "answer")).lower()
    return output_mode if output_mode in {"answer", "compact", "debug", "full"} else "answer"


def _strip_mcp_debug_noise(payload: dict[str, Any]) -> dict[str, Any]:
    payload.pop("mcp_compaction", None)
    warnings = [
        warning for warning in (payload.get("warnings") or [])
        if not (isinstance(warning, dict) and str(warning.get("code") or "").startswith("mcp_compact_output_"))
    ]
    payload["warnings"] = warnings
    return payload


def _patch_constraints_output_mode(args: dict[str, Any]) -> str:
    output_mode = str(args.get("output_mode") or "compact").lower()
    return output_mode if output_mode in {"compact", "debug", "full"} else "compact"


def _compact_patch_constraints(result: dict[str, Any]) -> dict[str, Any]:
    return {
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
    if name == "inspect_project_docs":
        result = asdict(service.inspect_project_docs(args["project_path"]))
        return result if args.get("details") else _compact_inspect_project_docs(result)
    if name == "ingest_project_docs":
        result = asdict(service.ingest_project_docs(args["project_path"], skip_known=bool(args.get("skip_known") if args.get("skip_known") is not None else True), with_vectors=bool(args.get("with_vectors") if args.get("with_vectors") is not None else True)))
        return result if args.get("details") else _compact_ingest_project_docs(result)
    if name == "sync_project_docs":
        result = asdict(service.sync_project_docs(args["project_path"], with_vectors=bool(args.get("with_vectors") if args.get("with_vectors") is not None else True)))
        return result if args.get("details") else _compact_sync_project_docs(result)
    if name == "bootstrap_project_docs":
        result = asdict(service.bootstrap_project_docs(args["project_path"], question=args.get("question")))
        return result if args.get("details") else _compact_bootstrap_project_docs(result)
    if name == "get_project_docs":
        result = asdict(service.get_project_docs(args["project_path"], args["query"], tokens=args.get("tokens"), limit=args.get("limit"), expand=args.get("expand"), module=args.get("module"), module_path=args.get("module_path"), scope=args.get("scope")))
        return result if args.get("details") else _compact_project_docs(result)
    if name == "get_project_context":
        result = asdict(service.get_project_context(args["project_path"], args["question"], tokens=args.get("tokens"), limit=args.get("limit"), expand=args.get("expand"), library=args.get("library"), libraries=args.get("libraries"), ecosystem=args.get("ecosystem"), version=args.get("version"), module=args.get("module"), module_path=args.get("module_path"), scope=args.get("scope"), mode=args.get("mode") or "auto", response_style=args.get("response_style"), allow_network=bool(args.get("allow_network") or False)))
        output_mode = _project_context_output_mode(args)
        if output_mode == "full":
            result["output_mode"] = "full"
            return result
        if output_mode == "debug":
            payload = _debug_project_context(result)
            payload["output_mode"] = "debug"
            return _compact_mcp_payload(payload)
        payload = _answer_project_context(result) if output_mode == "answer" else _compact_project_context(result)
        payload["output_mode"] = output_mode
        payload = _compact_mcp_payload(_add_project_context_output_warning(payload, args))
        return _strip_mcp_debug_noise(payload)
    if name == "get_patch_constraints":
        result = asdict(service.get_patch_constraints(
            args["question"],
            project_path=args.get("project_path"),
            changed_files=args.get("changed_files"),
            max_constraints=args.get("max_constraints") or 12,
            max_tokens=args.get("max_tokens") or 1200,
            include_sources=bool(args.get("include_sources") if args.get("include_sources") is not None else True),
        ))
        output_mode = _patch_constraints_output_mode(args)
        if output_mode == "full":
            result["output_mode"] = "full"
            return result
        payload = result if output_mode == "debug" else _compact_patch_constraints(result)
        payload["output_mode"] = output_mode
        payload = _compact_mcp_payload(payload)
        return payload if output_mode == "debug" else _strip_mcp_debug_noise(payload)
    if name == "validate_patch_against_constraints":
        return asdict(service.validate_patch_against_constraints(
            args.get("constraints") or [],
            project_path=args.get("project_path"),
            changed_files=args.get("changed_files"),
            patch_diff=args.get("patch_diff"),
            strict=bool(args.get("strict") or False),
        ))
    if name in {"prefetch_project_docs", "prefetch_project_dependency_docs"}:
        method = service.prefetch_project_dependency_docs if name == "prefetch_project_dependency_docs" else service.prefetch_project_docs
        return asdict(method(args["project_path"], include_flutter=bool(args.get("include_flutter") if args.get("include_flutter") is not None else True), include_dart=bool(args.get("include_dart") or False), include_rust=bool(args.get("include_rust") if args.get("include_rust") is not None else True), include_packages=args.get("include_packages") or [], force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    return None
