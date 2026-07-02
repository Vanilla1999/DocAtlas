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
    return compact


def _project_sources_summary(result: dict[str, Any]) -> dict[str, int]:
    return {
        "candidates": len(result.get("candidate_sources") or []),
        "indexed": len(result.get("indexed_sources") or []),
        "stale": len(result.get("stale_sources") or []),
        "ignored": len(result.get("ignored_sources") or []),
    }


def _compact_project_docs(result: dict[str, Any], *, omit_results: bool = False) -> dict[str, Any]:
    compact = {
        "project_path": result.get("project_path"),
        "query": result.get("query"),
        "status": result.get("status"),
        "tool": result.get("tool"),
        "reason_code": result.get("reason_code"),
        "answer_available": result.get("answer_available"),
        "message": result.get("message"),
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
        "message": result.get("message"),
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


def _project_context_output_mode(args: dict[str, Any]) -> str:
    output_mode = str(args.get("output_mode") or "compact").lower()
    return "full" if output_mode == "full" else "compact"


def _add_project_context_output_warning(payload: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    if not args.get("details") or _project_context_output_mode(args) == "full":
        return payload
    warnings = list(payload.get("warnings") or [])
    warning = {
        "code": "project_context_full_output_requires_output_mode_full",
        "message": "details=true no longer returns full get_project_context payloads at the MCP boundary; pass output_mode='full' only when a full dump is explicitly required.",
    }
    if warning not in warnings:
        warnings.append(warning)
    payload["warnings"] = warnings
    payload["output_mode"] = "compact"
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
        result = asdict(service.get_project_context(args["project_path"], args["question"], tokens=args.get("tokens"), limit=args.get("limit"), expand=args.get("expand"), library=args.get("library"), libraries=args.get("libraries"), ecosystem=args.get("ecosystem"), version=args.get("version"), module=args.get("module"), module_path=args.get("module_path"), scope=args.get("scope"), mode=args.get("mode") or "auto", response_style=args.get("response_style")))
        if _project_context_output_mode(args) == "full":
            result["output_mode"] = "full"
            return result
        return _compact_mcp_payload(_add_project_context_output_warning(_compact_project_context(result), args))
    if name == "get_patch_constraints":
        return asdict(service.get_patch_constraints(
            args["question"],
            project_path=args.get("project_path"),
            changed_files=args.get("changed_files"),
            max_constraints=args.get("max_constraints") or 12,
            max_tokens=args.get("max_tokens") or 1200,
            include_sources=bool(args.get("include_sources") if args.get("include_sources") is not None else True),
        ))
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
