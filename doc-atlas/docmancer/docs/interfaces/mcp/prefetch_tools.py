from __future__ import annotations

from dataclasses import asdict
from typing import Any

from docmancer.docs.service import LibraryDocsService


PREFETCH_TOOL_NAMES = {
    "validate_docs_manifest",
    "prefetch_docs_manifest",
    "prefetch_docs_targets",
    "get_docs_job_status",
    "list_docs_jobs",
    "cancel_docs_job",
}


def prefetch_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in PREFETCH_TOOL_NAMES]


def handle_prefetch_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    if name == "validate_docs_manifest":
        return asdict(service.validate_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets")))
    if name == "prefetch_docs_manifest":
        return asdict(service.prefetch_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    if name == "prefetch_docs_targets":
        return asdict(service.prefetch_docs_targets(args.get("targets") or [], force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    if name == "get_docs_job_status":
        job = service.get_docs_job_status(args["job_id"])
        return {"job_id": args["job_id"], "status": "not_found"} if job is None else asdict(job)
    if name == "list_docs_jobs":
        return {"jobs": [{"job_id": job.job_id, "kind": job.kind, "status": job.status, "phase": job.phase, "message": job.message, "started_at": job.started_at, "updated_at": job.updated_at} for job in service.list_docs_jobs(status=args.get("status"), limit=args.get("limit"))]}
    if name == "cancel_docs_job":
        return asdict(service.cancel_docs_job(args["job_id"]))
    return None
