from __future__ import annotations

from dataclasses import asdict
from typing import Any

from docmancer.docs.service import LibraryDocsService


PROJECT_TOOL_NAMES = {
    "inspect_project_docs",
    "ingest_project_docs",
    "bootstrap_project_docs",
    "get_project_docs",
    "get_project_context",
    "prefetch_project_docs",
    "prefetch_project_dependency_docs",
}


def project_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in PROJECT_TOOL_NAMES]


def handle_project_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    if name == "inspect_project_docs":
        return asdict(service.inspect_project_docs(args["project_path"]))
    if name == "ingest_project_docs":
        return asdict(service.ingest_project_docs(args["project_path"], skip_known=bool(args.get("skip_known") if args.get("skip_known") is not None else True), with_vectors=bool(args.get("with_vectors") if args.get("with_vectors") is not None else True)))
    if name == "bootstrap_project_docs":
        return asdict(service.bootstrap_project_docs(args["project_path"], question=args.get("question")))
    if name == "get_project_docs":
        return asdict(service.get_project_docs(args["project_path"], args["query"], tokens=args.get("tokens"), limit=args.get("limit"), expand=args.get("expand")))
    if name == "get_project_context":
        return asdict(service.get_project_context(args["project_path"], args["question"], tokens=args.get("tokens"), limit=args.get("limit"), expand=args.get("expand"), library=args.get("library"), libraries=args.get("libraries"), ecosystem=args.get("ecosystem"), version=args.get("version"), mode=args.get("mode") or "auto"))
    if name in {"prefetch_project_docs", "prefetch_project_dependency_docs"}:
        method = service.prefetch_project_dependency_docs if name == "prefetch_project_dependency_docs" else service.prefetch_project_docs
        return asdict(method(args["project_path"], include_flutter=bool(args.get("include_flutter") if args.get("include_flutter") is not None else True), include_dart=bool(args.get("include_dart") or False), include_rust=bool(args.get("include_rust") if args.get("include_rust") is not None else True), include_packages=args.get("include_packages") or [], force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    return None
