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

_PREPARE_ACTION_FIELDS = {
    "sync_project_docs": {
        "action", "project_path", "with_vectors", "changed_paths", "deleted_paths", "renamed_paths",
    },
    "prefetch_project_dependency_docs": {"action", "project_path", "include_flutter", "include_dart", "include_rust", "include_packages", "force_refresh", "continue_on_error", "async"},
    "prefetch_library_docs": {"action", "library", "ecosystem", "version", "source_type", "docs_url", "docs_url_template", "force_refresh", "continue_on_error", "async"},
    "prefetch_docs_targets": {"action", "targets", "force_refresh", "continue_on_error", "async"},
    "validate_docs_manifest": {"action", "manifest_path", "project_path", "targets"},
    "prefetch_docs_manifest": {"action", "manifest_path", "project_path", "targets", "force_refresh", "continue_on_error", "async"},
    "refresh_library_docs": {"action", "library", "ecosystem", "version", "source_type", "docs_url", "force"},
    "prune_library_docs": {"action", "library", "keep_versions", "older_than_days", "dry_run"},
    "remove_library_docs": {"action", "canonical_id"},
    "cancel_docs_job": {"action", "job_id"},
}
_PREPARE_REQUIRED_FIELDS = {
    "sync_project_docs": {"project_path"},
    "prefetch_project_dependency_docs": {"project_path"},
    "prefetch_library_docs": {"library"},
    "prefetch_docs_targets": {"targets"},
    "validate_docs_manifest": {"manifest_path"},
    "prefetch_docs_manifest": {"manifest_path"},
    "refresh_library_docs": {"library"},
    "remove_library_docs": {"canonical_id"},
    "cancel_docs_job": {"job_id"},
}
_REMOTE_PREPARE_ACTIONS = {
    "prefetch_project_dependency_docs",
    "prefetch_library_docs",
    "prefetch_docs_targets",
    "prefetch_docs_manifest",
    "refresh_library_docs",
}


def _job_summary(job: Any) -> dict[str, Any]:
    fields = (
        "job_id", "kind", "status", "phase", "message", "reason_code", "retryable",
        "deadline_at", "queue_position", "running_jobs", "queued_jobs",
        "max_running_jobs", "max_queued_jobs", "page_failure_summary", "started_at", "updated_at",
    )
    return {field: getattr(job, field) for field in fields}


def _prepare_validation_error(action: str, message: str) -> dict[str, Any]:
    return {
        "tool": "prepare_docs",
        "action": action or None,
        "status": "error",
        "reason_code": "validation_error",
        "message": message,
    }


def validate_prepare_docs_arguments(args: dict[str, Any]) -> dict[str, Any] | None:
    """Validate the public action union before a service can be called."""
    action = str(args.get("action") or "").strip()
    if action not in _PREPARE_ACTION_FIELDS:
        return _prepare_validation_error(action, f"unsupported action: {action or '<missing>'}")
    irrelevant = sorted(set(args) - _PREPARE_ACTION_FIELDS[action])
    if irrelevant:
        return _prepare_validation_error(action, f"field(s) not allowed for action '{action}': {', '.join(irrelevant)}")
    missing = sorted(
        field for field in _PREPARE_REQUIRED_FIELDS.get(action, set())
        if args.get(field) in (None, "", [])
    )
    if missing:
        return _prepare_validation_error(action, f"missing required field(s) for action '{action}': {', '.join(missing)}")
    if action in _REMOTE_PREPARE_ACTIONS and args.get("async") is False:
        return _prepare_validation_error(action, f"action '{action}' always runs asynchronously; omit async or set it to true")
    if action == "sync_project_docs":
        for field in ("changed_paths", "deleted_paths", "renamed_paths"):
            value = args.get(field)
            if value is not None and not isinstance(value, list):
                return _prepare_validation_error(action, f"{field} must be an array")
            if isinstance(value, list) and len(value) > 500:
                return _prepare_validation_error(action, f"{field} accepts at most 500 entries")
        for field in ("changed_paths", "deleted_paths"):
            for index, value in enumerate(args.get(field) or []):
                if not isinstance(value, str) or not value.strip():
                    return _prepare_validation_error(action, f"{field}[{index}] must be a non-empty string")
        for index, value in enumerate(args.get("renamed_paths") or []):
            if not isinstance(value, dict) or set(value) != {"old_path", "new_path"}:
                return _prepare_validation_error(
                    action,
                    f"renamed_paths[{index}] must contain exactly old_path and new_path",
                )
            if any(not isinstance(value[key], str) or not value[key].strip() for key in value):
                return _prepare_validation_error(
                    action, f"renamed_paths[{index}] paths must be non-empty strings"
                )
    targets = args.get("targets")
    if targets is not None:
        for index, target in enumerate(targets):
            max_pages = target.get("max_pages")
            if max_pages is not None and (isinstance(max_pages, bool) or not isinstance(max_pages, int)):
                return _prepare_validation_error(action, f"targets[{index}].max_pages must be an integer")
            if isinstance(max_pages, int) and max_pages <= 0:
                return _prepare_validation_error(action, f"targets[{index}].max_pages must be positive")
    return None


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
                    _job_summary(job)
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
        validation_error = validate_prepare_docs_arguments(args)
        if validation_error:
            return validation_error
        if action == "validate_docs_manifest":
            payload = asdict(docs_manifest_app.validate_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets")))
        elif action == "prefetch_docs_manifest":
            payload = asdict(docs_manifest_app.prefetch_docs_manifest(args["manifest_path"], project_path=args.get("project_path"), targets=args.get("targets"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=True))
        elif action == "prefetch_docs_targets":
            payload = asdict(docs_prefetch_app.prefetch_docs_targets(_bounded_targets(args.get("targets")), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=True))
        elif action == "sync_project_docs":
            payload = asdict(project_docs_app.sync_project_docs(
                args["project_path"],
                with_vectors=bool(args.get("with_vectors") if args.get("with_vectors") is not None else True),
                changed_paths=args.get("changed_paths"),
                deleted_paths=args.get("deleted_paths"),
                renamed_paths=args.get("renamed_paths"),
            ))
        elif action == "prefetch_project_dependency_docs":
            payload = asdict(dependency_docs_app.prefetch_project_dependency_docs(args["project_path"], include_flutter=bool(args.get("include_flutter") if args.get("include_flutter") is not None else True), include_dart=bool(args.get("include_dart") or False), include_rust=bool(args.get("include_rust") if args.get("include_rust") is not None else True), include_packages=args.get("include_packages") or [], force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=True))
        elif action == "prefetch_library_docs":
            # Public MCP calls must not block the server while a remote source is crawled.
            versions = [args["version"]] if args.get("version") else None
            payload = asdict(library_docs_app.prefetch_docs(args["library"], ecosystem=args.get("ecosystem"), versions=versions, docs_url=args.get("docs_url"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force_refresh=bool(args.get("force_refresh") or False), continue_on_error=bool(args.get("continue_on_error") if args.get("continue_on_error") is not None else True), async_=True))
        elif action == "refresh_library_docs":
            versions = [args["version"]] if args.get("version") else None
            payload = asdict(library_docs_app.prefetch_docs(args["library"], ecosystem=args.get("ecosystem"), versions=versions, docs_url=args.get("docs_url"), docs_url_template=args.get("docs_url_template"), source_type=args.get("source_type"), force_refresh=bool(args.get("force") if args.get("force") is not None else True), continue_on_error=True, async_=True))
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
            return {"tool": "docs_job", "action": action, "jobs": [_job_summary(job) for job in service.list_docs_jobs(status=args.get("status"), limit=_bounded_int_arg(args, "limit", default=None, max_value=200))]}
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
        return {"jobs": [_job_summary(job) for job in service.list_docs_jobs(status=args.get("status"), limit=_bounded_int_arg(args, "limit", default=None, max_value=200))]}
    if name == "cancel_docs_job":
        return asdict(service.cancel_docs_job(args["job_id"]))
    return None
