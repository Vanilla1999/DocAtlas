from __future__ import annotations

from dataclasses import asdict
from typing import Any

from docmancer.docs.service import LibraryDocsService


LIBRARY_TOOL_NAMES = {
    "resolve_library_id",
    "get_library_docs",
    "refresh_library_docs",
    "prefetch_library_docs",
    "inspect_library_docs",
    "remove_library_docs",
    "prune_library_docs",
    "list_library_docs",
}


def library_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in LIBRARY_TOOL_NAMES]


def handle_library_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    if name == "resolve_library_id":
        return asdict(service.resolve_library(args["library"], args.get("ecosystem"), args.get("version"), args.get("docs_url"), args.get("docs_url_template"), args.get("source_type")))
    if name == "get_library_docs":
        return asdict(service.get_docs(args["library"], topic=args.get("topic"), tokens=args.get("tokens"), ecosystem=args.get("ecosystem"), version=args.get("version"), docs_url=args.get("docs_url"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force_refresh=bool(args.get("force_refresh") or False), project_path=args.get("project_path"), response_style=args.get("response_style")))
    if name == "refresh_library_docs":
        return asdict(service.refresh_docs(args["library"], ecosystem=args.get("ecosystem"), version=args.get("version"), docs_url=args.get("docs_url"), versions=args.get("versions"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force=bool(args.get("force") if args.get("force") is not None else True)))
    if name == "prefetch_library_docs":
        return asdict(service.prefetch_docs(args["library"], ecosystem=args.get("ecosystem"), versions=args.get("versions"), docs_url=args.get("docs_url"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    if name == "inspect_library_docs":
        return asdict(service.inspect_library_docs(args["canonical_id"]))
    if name == "remove_library_docs":
        return asdict(service.remove_library_docs(args["canonical_id"]))
    if name == "prune_library_docs":
        return asdict(service.prune_library_docs(library=args.get("library"), keep_versions=args.get("keep_versions") or [], older_than_days=int(args.get("older_than_days") or 90), dry_run=bool(args.get("dry_run") if args.get("dry_run") is not None else True)))
    if name == "list_library_docs":
        return {"libraries": [asdict(item) for item in service.list_libraries(stale_only=bool(args.get("stale_only") or False), limit=args.get("limit"))]}
    return None
