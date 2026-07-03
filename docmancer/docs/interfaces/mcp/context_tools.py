from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from docmancer.docs.service import LibraryDocsService
from docmancer.docs.interfaces.mcp.project_tools import _bad_request, _bounded_int_arg, _clean_string, _compact_mcp_payload, _strip_mcp_debug_noise


CONTEXT_TOOL_NAMES = {"get_docs_context"}


def context_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in CONTEXT_TOOL_NAMES]


def _output_mode(args: dict[str, Any]) -> str:
    mode = str(args.get("output_mode") or "answer").lower()
    return mode if mode in {"answer", "compact", "debug", "full"} else "answer"


def _answer_payload(payload: dict[str, Any]) -> dict[str, Any]:
    answer = {
        "tool": payload.get("tool"),
        "status": payload.get("status"),
        "answer_available": payload.get("answer_available"),
        "mode_selected": payload.get("mode_selected"),
        "reason_code": payload.get("reason_code"),
        "primary_snippet": payload.get("primary_snippet"),
        "selected_sources": (payload.get("trust_contract") or {}).get("selected") or (payload.get("trust_contract") or {}).get("selected_sources") or [],
        "next_action": payload.get("next_action"),
        "next_actions": payload.get("next_actions") or [],
        "arguments_patch": payload.get("arguments_patch"),
        "warnings": payload.get("warnings") or [],
    }
    if payload.get("requires_confirmation"):
        answer["requires_confirmation"] = payload.get("requires_confirmation")
        answer["confirmation_reason"] = payload.get("confirmation_reason")
    return {key: value for key, value in answer.items() if value not in (None, {}, [])}


def _compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": payload.get("tool"),
        "status": payload.get("status"),
        "answer_available": payload.get("answer_available"),
        "mode_requested": payload.get("mode_requested"),
        "mode_selected": payload.get("mode_selected"),
        "routing": payload.get("routing") or {},
        "lanes": payload.get("lanes") or {},
        "source_summary": payload.get("source_summary") or {},
        "trust_contract": payload.get("trust_contract") or {},
        "primary_snippet": payload.get("primary_snippet"),
        "supporting_snippets": payload.get("supporting_snippets") or [],
        "context_pack": payload.get("context_pack") or [],
        "next_action": payload.get("next_action"),
        "next_actions": payload.get("next_actions") or [],
        "arguments_patch": payload.get("arguments_patch"),
        "warnings": payload.get("warnings") or [],
        "requires_confirmation": payload.get("requires_confirmation"),
        "confirmation_reason": payload.get("confirmation_reason"),
    }


def handle_context_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    if name != "get_docs_context":
        return None
    question = _clean_string(args.get("question"))
    if not question:
        return _bad_request("empty_question", "question must not be empty")
    result = service.get_docs_context(
        question,
        project_path=args.get("project_path"),
        library=args.get("library"),
        libraries=args.get("libraries"),
        ecosystem=args.get("ecosystem"),
        version=args.get("version"),
        source_type=args.get("source_type"),
        docs_url=args.get("docs_url"),
        module=args.get("module"),
        module_path=args.get("module_path"),
        scope=args.get("scope"),
        mode=args.get("mode"),
        tokens=_bounded_int_arg(args, "tokens", max_value=20_000),
        limit=_bounded_int_arg(args, "limit", default=None, max_value=20),
        expand=args.get("expand"),
        prepare_project_docs=args.get("prepare_project_docs"),
        allow_network=args.get("allow_network"),
        allow_latest_fallback=args.get("allow_latest_fallback"),
        force_refresh=args.get("force_refresh"),
        details=args.get("details"),
        response_style=args.get("response_style"),
    )
    if is_dataclass(result):
        raw = asdict(result)
    elif isinstance(result, dict):
        raw = result
    else:
        raw = dict(getattr(result, "__dict__", {}))
        for key in ("tool", "status", "reason_code", "message", "response_style", "primary_snippet", "supporting_snippets", "snippet_metrics"):
            if hasattr(result, key):
                raw[key] = getattr(result, key)
    mode = _output_mode(args)
    if mode == "full":
        raw["output_mode"] = "full"
        return raw
    payload = raw if mode == "debug" else (_compact_payload(raw) if mode == "compact" else _answer_payload(raw))
    payload["output_mode"] = mode
    payload = _compact_mcp_payload(payload)
    return payload if mode == "debug" else _strip_mcp_debug_noise(payload)
