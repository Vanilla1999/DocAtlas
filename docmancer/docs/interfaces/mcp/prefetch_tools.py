from __future__ import annotations

from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

from docmancer.docs.service import LibraryDocsService
from docmancer.docs.interfaces.mcp.project_tools import _bounded_int_arg, handle_project_tool


PREFETCH_TOOL_NAMES = {
    "prepare_docs",
    "docs_status",
    "docs_job",
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
    docs_manifest_app = getattr(service, "docs_manifest", service)
    docs_prefetch_app = getattr(service, "docs_prefetch", service)
    library_docs_app = getattr(service, "library_docs", service)
    project_docs_app = getattr(service, "project_docs", service)
    dependency_docs_app = getattr(service, "dependency_docs", service)
    if name == "docs_status":
        action = str(args.get("action") or "").strip()
        if action == "project":
            project_path = str(args.get("project_path") or "").strip()
            if not project_path:
                return {
                    "tool": "docs_status",
                    "status": "error",
                    "reason_code": "project_path_required",
                    "message": "project_path is required for action='project'",
                }
            project = handle_project_tool(
                "inspect_project_docs",
                {"project_path": project_path, "details": bool(args.get("details") or False)},
                service,
            )
            return {"tool": "docs_status", "action": action, "project": project}
        if action == "jobs":
            jobs = service.list_docs_jobs(
                status=args.get("status"),
                limit=_bounded_int_arg(args, "limit", default=None, max_value=200),
            )
            return {
                "tool": "docs_status",
                "action": action,
                "jobs": [
                    {
                        "job_id": job.job_id,
                        "kind": job.kind,
                        "status": job.status,
                        "phase": job.phase,
                        "message": job.message,
                        "reason_code": job.reason_code,
                        "retryable": job.retryable,
                        "deadline_at": job.deadline_at,
                        "started_at": job.started_at,
                        "updated_at": job.updated_at,
                    }
                    for job in jobs
                ],
            }
        if action == "job":
            job_id = str(args.get("job_id") or "").strip()
            if not job_id:
                return {
                    "tool": "docs_status",
                    "status": "error",
                    "reason_code": "job_id_required",
                    "message": "job_id is required for action='job'",
                }
            job = service.get_docs_job_status(job_id)
            if job is None:
                return {
                    "tool": "docs_status",
                    "action": action,
                    "job_id": job_id,
                    "status": "not_found",
                }
            return {"tool": "docs_status", "action": action, **asdict(job)}
        return {
            "tool": "docs_status",
            "status": "error",
            "reason_code": "unknown_docs_status_action",
            "message": f"unknown docs_status action: {action}",
            "supported_actions": ["project", "jobs", "job"],
        }
    if name == "prepare_docs":
        action = str(args.get("action") or "").strip()
        if not action:
            return {"status": "error", "reason_code": "empty_action", "message": "action must not be empty"}
        if action == "validate_docs_manifest":
            payload = asdict(docs_manifest_app.validate_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets")))
        elif action == "prefetch_docs_manifest":
            payload = asdict(docs_manifest_app.prefetch_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
        elif action == "prefetch_docs_targets":
            payload = asdict(docs_prefetch_app.prefetch_docs_targets(_bounded_targets(args.get("targets")), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
        elif action == "sync_project_docs":
            payload = asdict(project_docs_app.sync_project_docs(args["project_path"], with_vectors=bool(args.get("with_vectors") if args.get("with_vectors") is not None else True)))
        elif action == "prefetch_project_dependency_docs":
            payload = asdict(dependency_docs_app.prefetch_project_dependency_docs(args["project_path"], include_flutter=bool(args.get("include_flutter") if args.get("include_flutter") is not None else True), include_dart=bool(args.get("include_dart") or False), include_rust=bool(args.get("include_rust") if args.get("include_rust") is not None else True), include_packages=args.get("include_packages") or [], force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
        elif action == "prefetch_library_docs":
            # Public MCP calls must not block the server while a remote source is crawled.
            async_requested = args.get("async")
            payload = asdict(library_docs_app.prefetch_docs(args["library"], ecosystem=args.get("ecosystem"), versions=args.get("versions"), docs_url=args.get("docs_url"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=True if async_requested is None else bool(async_requested)))
        elif action == "refresh_library_docs":
            payload = asdict(library_docs_app.refresh_docs(args["library"], ecosystem=args.get("ecosystem"), version=args.get("version"), docs_url=args.get("docs_url"), versions=args.get("versions"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force=bool(args.get("force") if args.get("force") is not None else True)))
        elif action == "remove_library_docs":
            payload = asdict(library_docs_app.remove_library_docs(args["canonical_id"]))
        elif action == "prune_library_docs":
            payload = asdict(library_docs_app.prune_library_docs(library=args.get("library"), keep_versions=args.get("keep_versions") or [], older_than_days=int(args.get("older_than_days") or 90), dry_run=bool(args.get("dry_run") if args.get("dry_run") is not None else True)))
        elif action == "cancel_docs_job":
            job_id = str(args.get("job_id") or "").strip()
            if not job_id:
                return {
                    "tool": "prepare_docs",
                    "action": action,
                    "status": "error",
                    "reason_code": "job_id_required",
                    "message": "job_id is required for action='cancel_docs_job'",
                }
            payload = asdict(service.cancel_docs_job(job_id))
        else:
            return {"status": "error", "reason_code": "unknown_prepare_action", "message": f"unknown prepare_docs action: {action}", "supported_actions": ["sync_project_docs", "prefetch_project_dependency_docs", "prefetch_library_docs", "prefetch_docs_targets", "validate_docs_manifest", "prefetch_docs_manifest", "refresh_library_docs", "prune_library_docs", "remove_library_docs", "cancel_docs_job"]}
        if isinstance(payload, dict):
            payload.setdefault("action", action)
            payload.setdefault("tool", "prepare_docs")
        return payload
    if name == "docs_job":
        action = str(args.get("action") or "").strip()
        if action == "status":
            job = service.get_docs_job_status(args["job_id"])
            return {"tool": "docs_job", "action": action, "job_id": args["job_id"], "status": "not_found"} if job is None else {"tool": "docs_job", "action": action, **asdict(job)}
        if action == "list":
            return {"tool": "docs_job", "action": action, "jobs": [{"job_id": job.job_id, "kind": job.kind, "status": job.status, "phase": job.phase, "message": job.message, "reason_code": job.reason_code, "retryable": job.retryable, "deadline_at": job.deadline_at, "started_at": job.started_at, "updated_at": job.updated_at} for job in service.list_docs_jobs(status=args.get("status"), limit=_bounded_int_arg(args, "limit", default=None, max_value=200))]}
        if action == "cancel":
            return {"tool": "docs_job", "action": action, **asdict(service.cancel_docs_job(args["job_id"]))}
        return {"status": "error", "reason_code": "unknown_docs_job_action", "message": f"unknown docs_job action: {action}", "supported_actions": ["list", "status", "cancel"]}
    if name == "validate_docs_manifest":
        return asdict(docs_manifest_app.validate_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets")))
    if name == "prefetch_docs_manifest":
        return asdict(docs_manifest_app.prefetch_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    if name == "prefetch_docs_targets":
        return asdict(docs_prefetch_app.prefetch_docs_targets(_bounded_targets(args.get("targets")), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=bool(args.get("async") or False)))
    if name == "get_docs_job_status":
        job = service.get_docs_job_status(args["job_id"])
        return {"job_id": args["job_id"], "status": "not_found"} if job is None else asdict(job)
    if name == "list_docs_jobs":
        return {"jobs": [{"job_id": job.job_id, "kind": job.kind, "status": job.status, "phase": job.phase, "message": job.message, "reason_code": job.reason_code, "retryable": job.retryable, "deadline_at": job.deadline_at, "started_at": job.started_at, "updated_at": job.updated_at} for job in service.list_docs_jobs(status=args.get("status"), limit=_bounded_int_arg(args, "limit", default=None, max_value=200))]}
    if name == "cancel_docs_job":
        return asdict(service.cancel_docs_job(args["job_id"]))
    return None
