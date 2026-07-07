from __future__ import annotations

from dataclasses import asdict
from typing import Any

from docmancer.docs.interfaces.mcp.error_contract import build_bad_request_payload
from docmancer.docs.service import LibraryDocsService


LIBRARY_TOOL_NAMES = {
    "list_docs_sources",
    "resolve_library_id",
    "get_library_docs",
    "refresh_library_docs",
    "prefetch_library_docs",
    "inspect_library_docs",
    "remove_library_docs",
    "prune_library_docs",
    "list_library_docs",
}

_MCP_MAX_TOKENS = 20_000
_MCP_MAX_LIST_LIMIT = 200


def _bad_request(reason_code: str, message: str) -> dict[str, Any]:
    return build_bad_request_payload(reason_code, message)


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _library_arg(args: dict[str, Any]) -> str | None:
    return _clean_string(args.get("library") or args.get("libraryName"))


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


def library_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in LIBRARY_TOOL_NAMES]


def handle_library_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    app = getattr(service, "library_docs", service)
    if name == "resolve_library_id":
        library = _library_arg(args)
        if not library:
            return _bad_request("empty_library", "library must not be empty")
        return asdict(app.resolve_library(library, args.get("ecosystem"), args.get("version"), args.get("docs_url"), args.get("docs_url_template"), args.get("source_type")))
    if name == "get_library_docs":
        library = _library_arg(args)
        if not library:
            return _bad_request("empty_library", "library must not be empty")
        return asdict(app.get_docs(library, topic=_clean_string(args.get("topic")), tokens=_bounded_int_arg(args, "tokens", max_value=_MCP_MAX_TOKENS), ecosystem=args.get("ecosystem"), version=args.get("version"), docs_url=args.get("docs_url"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force_refresh=bool(args.get("force_refresh") or False), project_path=args.get("project_path"), response_style=args.get("response_style")))
    if name == "refresh_library_docs":
        return asdict(app.refresh_docs(args["library"], ecosystem=args.get("ecosystem"), version=args.get("version"), docs_url=args.get("docs_url"), versions=args.get("versions"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force=bool(args.get("force") if args.get("force") is not None else True)))
    if name == "prefetch_library_docs":
        return asdict(app.prefetch_docs(args["library"], ecosystem=args.get("ecosystem"), versions=args.get("versions"), docs_url=args.get("docs_url"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    if name == "inspect_library_docs":
        return asdict(app.inspect_library_docs(args["canonical_id"]))
    if name == "remove_library_docs":
        return asdict(app.remove_library_docs(args["canonical_id"]))
    if name == "prune_library_docs":
        return asdict(app.prune_library_docs(library=args.get("library"), keep_versions=args.get("keep_versions") or [], older_than_days=int(args.get("older_than_days") or 90), dry_run=bool(args.get("dry_run") if args.get("dry_run") is not None else True)))
    if name == "list_library_docs":
        return {"libraries": [asdict(item) for item in app.list_libraries(stale_only=bool(args.get("stale_only") or False), limit=_bounded_int_arg(args, "limit", default=None, max_value=_MCP_MAX_LIST_LIMIT))]}
    if name == "list_docs_sources":
        kind = str(args.get("kind") or "library").strip()
        if kind not in {"library", "all"}:
            return {"status": "error", "reason_code": "unsupported_source_kind", "message": "list_docs_sources currently supports kind='library' or kind='all'"}
        payload: dict[str, Any] = {"tool": "list_docs_sources", "kind": kind}
        canonical_id = _clean_string(args.get("canonical_id"))
        if canonical_id:
            payload["library_source"] = asdict(app.inspect_library_docs(canonical_id))
        else:
            payload["libraries"] = [
                asdict(item)
                for item in app.list_libraries(
                    stale_only=bool(args.get("stale_only") or False),
                    limit=_bounded_int_arg(args, "limit", default=None, max_value=_MCP_MAX_LIST_LIMIT),
                )
            ]
        return payload
    return None
