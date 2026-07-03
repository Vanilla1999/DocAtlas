from __future__ import annotations

from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

from docmancer.docs.service import LibraryDocsService
from docmancer.docs.interfaces.mcp.project_tools import _bounded_int_arg


PREFETCH_TOOL_NAMES = {
    "validate_docs_manifest",
    "prefetch_docs_manifest",
    "prefetch_docs_targets",
    "get_docs_job_status",
    "list_docs_jobs",
    "cancel_docs_job",
}


def _bounded_targets(targets: Any) -> Any:
    if not isinstance(targets, list):
        return []
    bounded = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        item = dict(target)
        if not item.get("allowed_domains"):
            inferred = _infer_allowed_domains(item)
            if inferred:
                item["allowed_domains"] = inferred
        if item.get("max_pages") is not None:
            item["max_pages"] = max(1, min(500, int(item["max_pages"])))
        bounded.append(item)
    return bounded


def _infer_allowed_domains(target: dict[str, Any]) -> list[str]:
    domains: list[str] = []
    urls: list[str] = [*(target.get("seed_urls") or [])]
    if target.get("docs_url"):
        urls.insert(0, target["docs_url"])
    for url in urls:
        parsed = urlparse(str(url))
        if parsed.scheme in {"http", "https"} and parsed.hostname and parsed.hostname not in domains:
            domains.append(parsed.hostname)
    return domains


def prefetch_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool for tool in tools if tool["name"] in PREFETCH_TOOL_NAMES]


def handle_prefetch_tool(name: str, args: dict[str, Any], service: LibraryDocsService) -> dict[str, Any] | None:
    if name == "validate_docs_manifest":
        return asdict(service.validate_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets")))
    if name == "prefetch_docs_manifest":
        return asdict(service.prefetch_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    if name == "prefetch_docs_targets":
        return asdict(service.prefetch_docs_targets(_bounded_targets(args.get("targets")), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    if name == "get_docs_job_status":
        job = service.get_docs_job_status(args["job_id"])
        return {"job_id": args["job_id"], "status": "not_found"} if job is None else asdict(job)
    if name == "list_docs_jobs":
        return {"jobs": [{"job_id": job.job_id, "kind": job.kind, "status": job.status, "phase": job.phase, "message": job.message, "started_at": job.started_at, "updated_at": job.updated_at} for job in service.list_docs_jobs(status=args.get("status"), limit=_bounded_int_arg(args, "limit", default=None, max_value=200))]}
    if name == "cancel_docs_job":
        return asdict(service.cancel_docs_job(args["job_id"]))
    return None
