from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any

from docmancer.docs.domain.tool_selection import normalize_public_docs_actions
from docmancer.docs.service import LibraryDocsService
from docmancer.docs.interfaces.mcp.output_contract import normalize_output_mode
from docmancer.docs.interfaces.mcp.project_tools import _attach_output_contract, _bad_request, _bounded_int_arg, _clean_string, _compact_mcp_payload, _strip_mcp_debug_noise


CONTEXT_TOOL_NAMES = {"get_docs_context"}


def context_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in CONTEXT_TOOL_NAMES]


def _output_mode(args: dict[str, Any]) -> str:
    return normalize_output_mode(args)


def _agent_instruction(answer_type: str) -> dict[str, Any]:
    if answer_type == "direct":
        return {
            "agent_instruction": (
                "You may answer from primary_snippet/supporting_snippets and selected_sources. "
                "Cite or mention source paths when useful."
            ),
            "required_next_step": "answer_from_returned_context",
            "safe_to_answer": True,
            "not_a_code_auditor": True,
        }

    return {
        "agent_instruction": (
            "Do not treat this as a complete answer. Docmancer returned navigation/source guidance. "
            "Read or search the suggested files/sources first, then produce your own answer."
        ),
        "required_next_step": "read_or_search_suggested_sources",
        "safe_to_answer": False,
        "not_a_code_auditor": True,
    }


def _answer_payload(payload: dict[str, Any]) -> dict[str, Any]:
    primary_snippet = payload.get("primary_snippet")
    supporting_snippets = payload.get("supporting_snippets") or []
    has_direct_answer = bool(primary_snippet or supporting_snippets)
    answer_available = bool(payload.get("answer_available")) and has_direct_answer
    answer_type = "direct" if answer_available else "navigation_only"
    answer = {
        "tool": payload.get("tool"),
        "status": payload.get("status"),
        "answer_available": answer_available,
        "answer_type": answer_type,
        **_agent_instruction(answer_type),
        "mode_selected": payload.get("mode_selected"),
        "reason_code": payload.get("reason_code"),
        "response_style": payload.get("response_style"),
        "primary_snippet": primary_snippet,
        "primary_snippets": payload.get("primary_snippets") or ([primary_snippet] if primary_snippet else []),
        "primary_snippet_confidence": payload.get("primary_snippet_confidence"),
        "primary_snippet_selection_reason": payload.get("primary_snippet_selection_reason"),
        "primary_snippet_alternatives": payload.get("primary_snippet_alternatives") or [],
        "selected_sources": _trust_sources(payload.get("trust_contract"), "selected"),
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
        "primary_snippets": payload.get("primary_snippets") or [],
        "primary_snippet_confidence": payload.get("primary_snippet_confidence"),
        "primary_snippet_selection_reason": payload.get("primary_snippet_selection_reason"),
        "primary_snippet_alternatives": payload.get("primary_snippet_alternatives") or [],
        "supporting_snippets": payload.get("supporting_snippets") or [],
        "context_pack": payload.get("context_pack") or [],
        "next_action": payload.get("next_action"),
        "next_actions": payload.get("next_actions") or [],
        "arguments_patch": payload.get("arguments_patch"),
        "warnings": payload.get("warnings") or [],
        "requires_confirmation": payload.get("requires_confirmation"),
        "confirmation_reason": payload.get("confirmation_reason"),
        "ingestion_diagnostics": payload.get("ingestion_diagnostics") or {},
        "retrieval_diagnostics": payload.get("retrieval_diagnostics") or {},
    }


def _align_trust_contract_with_snippets(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep selected source risk metadata consistent with snippet metadata."""

    contract = payload.get("trust_contract")
    if not isinstance(contract, dict):
        return payload
    selected = contract.get("selected")
    if not isinstance(selected, list) or not selected:
        return payload

    snippet_risks: dict[str, dict[str, Any]] = {}
    snippets = [payload.get("primary_snippet"), *(payload.get("supporting_snippets") or [])]
    for snippet in snippets:
        if not isinstance(snippet, dict):
            continue
        keys = {str(value) for value in (snippet.get("source"), snippet.get("source_url")) if value}
        if not keys:
            continue
        stricter = {
            "risk_flags": list(snippet.get("risk_flags") or []),
            "version_binding": snippet.get("version_binding"),
            "exact_version_match": snippet.get("exact_version_match"),
        }
        if not stricter["risk_flags"] and stricter["version_binding"] is None and stricter["exact_version_match"] is None:
            continue
        for key in keys:
            snippet_risks[key] = stricter
    if not snippet_risks:
        return payload

    updated = deepcopy(payload)
    updated_selected = []
    for source in selected:
        if not isinstance(source, dict):
            updated_selected.append(source)
            continue
        keys = [
            str(value)
            for value in (source.get("source"), source.get("source_url"), source.get("url"), source.get("path"))
            if value
        ]
        stricter = next((snippet_risks[key] for key in keys if key in snippet_risks), None)
        if not stricter:
            updated_selected.append(source)
            continue
        merged = dict(source)
        risk_flags = list(dict.fromkeys([*(merged.get("risk_flags") or []), *stricter.get("risk_flags", [])]))
        if risk_flags:
            merged["risk_flags"] = risk_flags
        if stricter.get("version_binding"):
            merged["version_binding"] = stricter["version_binding"]
        if stricter.get("exact_version_match") is not None:
            merged["exact_version_match"] = stricter["exact_version_match"]
        updated_selected.append(merged)
    updated["trust_contract"] = {**dict(updated.get("trust_contract") or {}), "selected": updated_selected}
    return updated


def handle_context_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    if name != "get_docs_context":
        return None
    question = _clean_string(args.get("question"))
    if not question:
        return _bad_request("empty_question", "question must not be empty. Examples: 'Flutter Riverpod providers', 'Firebase Auth signIn', 'How to use go_router redirect', 'FastAPI dependency injection', 'patch_constraints for adding a service'")
    app = getattr(service, "unified_context", service)
    result = app.get_docs_context(
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
        prepare_project_docs=(
            bool(args.get("prepare_project_docs"))
            if args.get("prepare_project_docs") is not None
            else False
        ),
        allow_network=args.get("allow_network"),
        allow_latest_fallback=args.get("allow_latest_fallback"),
        force_refresh=args.get("force_refresh"),
        prefetch_auto=args.get("prefetch_auto"),
        details=args.get("details"),
        response_style=args.get("response_style"),
    )
    if is_dataclass(result):
        raw = asdict(result)
    elif isinstance(result, dict):
        raw = result
    else:
        raw = dict(getattr(result, "__dict__", {}))
        for key in ("tool", "status", "reason_code", "message", "response_style", "primary_snippet", "primary_snippets", "primary_snippet_confidence", "primary_snippet_selection_reason", "primary_snippet_alternatives", "supporting_snippets", "snippet_metrics"):
            if hasattr(result, key):
                raw[key] = getattr(result, key)
    raw = _align_trust_contract_with_snippets(raw)
    raw = normalize_public_docs_actions(raw)
    mode = _output_mode(args)
    if mode == "full":
        raw["output_mode"] = "full"
        return raw
    payload = raw if mode == "debug" else (_compact_payload(raw) if mode == "compact" else _answer_payload(raw))
    payload["output_mode"] = mode
    payload = _compact_mcp_payload(payload, page=_bounded_int_arg(args, "page", default=1, max_value=10_000), page_size=_bounded_int_arg(args, "page_size", default=None, max_value=20), include_sections=args.get("include_sections"))
    return _attach_output_contract(payload, output_mode=mode) if mode == "debug" else _strip_mcp_debug_noise(payload)


def _trust_sources(contract: Any, lane: str) -> list[dict[str, Any]]:
    if not isinstance(contract, dict):
        return []
    sources = contract.get("sources")
    if isinstance(sources, dict) and isinstance(sources.get(lane), list):
        return [_flatten_trust_source(item) for item in sources[lane] if isinstance(item, dict)]
    legacy_key = f"{lane}_sources"
    value = contract.get(lane) or contract.get(legacy_key)
    if not isinstance(value, list):
        return []
    return [_flatten_trust_source(item) for item in value if isinstance(item, dict)]


def _flatten_trust_source(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("source")
    if not isinstance(source, dict):
        return item
    flattened = dict(item)
    flattened.pop("source", None)
    for key in (
        "path", "url", "title", "source_class", "source_type", "source_kind", "authority",
        "doc_scope", "module_id", "module_name", "module_path", "module_type",
    ):
        if source.get(key) not in (None, [], {}) and flattened.get(key) in (None, [], {}):
            flattened[key] = source[key]
    return flattened
