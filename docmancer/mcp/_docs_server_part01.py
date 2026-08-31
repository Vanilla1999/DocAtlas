"""Implementation shard 1 for docs_server."""
from __future__ import annotations

from ._docs_server_shared import *  # noqa: F401,F403

def current_docs_surface(env: Mapping[str, str] | None = None) -> DocsMcpSurface:
    """Build the docs MCP surface from the current environment.

    The live server calls this so environment changes are not frozen by module
    import order.
    """
    return build_docs_surface(DocsServerConfig.from_env(os.environ if env is None else env))


def current_tools(env: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    return [spec.to_tool_dict() for spec in current_docs_surface(env).tools]


def _exception_reason_code(exc: Exception) -> str:
    typed_reason = getattr(exc, "reason_code", None)
    if isinstance(typed_reason, str) and typed_reason:
        return typed_reason
    if isinstance(exc, ValueError):
        return "bad_request"
    if isinstance(exc, TimeoutError):
        return "network_required"
    if isinstance(exc, PermissionError):
        return "permission_denied"
    return "handler_exception"


def _public_handler_arguments(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return args


def _service_for_project_path(
    service: LibraryDocsService,
    arguments: dict[str, Any],
) -> LibraryDocsService:
    if arguments.get("action") == "clear_index":
        return service
    if not isinstance(service, LibraryDocsService):
        return service
    project_path = arguments.get("project_path")
    if not isinstance(project_path, str) or not project_path.strip():
        return service
    project_root = validate_project_path(project_path).path
    topology = StorageTopologyResolver(
        fallback_config=service.config,
        fallback_source=service.config_source,
        prefer_fallback=service.config_source == "explicit",
    ).resolve(project_root)
    if topology.config == service.config and topology.config_source == service.config_source:
        return service
    cache_key = (str(project_root), topology.config_identity, str(topology.library_index_root or ""))
    cache = service._project_service_cache
    lock = service._project_service_cache_lock
    with lock:
        cached = cache.get(cache_key)
        if cached is not None:
            cache.move_to_end(cache_key)
            return cached
        # A changed resolved config invalidates the prior service for this root.
        for stale_key in [key for key in cache if key[0] == str(project_root)]:
            cache.pop(stale_key, None)
        project_service = LibraryDocsService(
        config=topology.config,
        config_source=topology.config_source,
        config_path=topology.config_path or service.config_path,
        agent_factory=service.agent_gateway._agent_factory,
        project_reader=service.project_reader,
        stale_after_days=service.stale_after_days,
        library_index_root=topology.library_index_root,
        )
        cache[cache_key] = project_service
        while len(cache) > 8:
            cache.popitem(last=False)
        return project_service


def _destructive_project_scope_error(name: str, arguments: dict[str, Any]) -> str | None:
    if name != "remove_library_docs" and arguments.get("action") != "remove_library_docs":
        return None
    project_path = arguments.get("project_path")
    if not isinstance(project_path, str) or not project_path.strip():
        return "project_path must resolve to a project-owned storage topology for library removal"
    topology = StorageTopologyResolver().resolve(project_path)
    if topology.config_source != "project_local":
        return "project_path must resolve to a project-owned storage topology for library removal"
    return None


def call_docs_tool_payload(
    name: str,
    arguments: dict[str, Any] | None,
    service: LibraryDocsService,
    *,
    surface: DocsMcpSurface | None = None,
) -> dict[str, Any]:
    args = arguments or {}
    active_surface = surface or current_docs_surface()
    handler = active_surface.handlers.get(name)
    if handler is None:
        return build_mcp_error_payload(
            reason_code="unknown_tool",
            message=f"unknown tool: {name}",
            tool=name,
            phase="validation",
        )
    spec = next(spec for spec in active_surface.tools if spec.name == name)
    validation_schema = spec.validation_schema or spec.input_schema
    try:
        jsonschema.validate(args, validation_schema)
    except jsonschema.ValidationError as exc:
        field_path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        return build_mcp_error_payload(
            reason_code="validation_error",
            message=f"invalid arguments for {name} at {field_path}",
            tool=name,
            phase="validation",
        )
    allowed_fields = set(validation_schema.get("properties", {}))
    unknown_fields = sorted(set(args) - allowed_fields)
    if unknown_fields:
        return build_mcp_error_payload(
            reason_code="validation_error",
            message=f"unknown field(s) for {name}: {', '.join(unknown_fields)}",
            tool=name,
            phase="validation",
        )
    destructive_scope_error = _destructive_project_scope_error(name, args)
    if destructive_scope_error:
        return build_mcp_error_payload(
            reason_code="validation_error",
            message=destructive_scope_error,
            tool=name,
            phase="validation",
        )
    handler_args = _public_handler_arguments(name, args)
    try:
        active_service = _service_for_project_path(service, handler_args)
        payload = handler(name, handler_args, active_service)
    except Exception as exc:
        reason_code = _exception_reason_code(exc)
        return build_mcp_error_payload(
            reason_code=reason_code,
            message=f"{reason_code}: request failed",
            exception=exc,
            tool=name,
            phase="execution",
            debug=debug_errors_enabled(args),
        )
    if payload is None:
        return build_mcp_error_payload(
            reason_code="unknown_tool",
            message=f"unknown tool: {name}",
            tool=name,
            phase="validation",
        )
    if payload.get("status") == "error" and isinstance(payload.get("reason_code"), str):
        return build_mcp_error_payload(
            reason_code=payload["reason_code"],
            message=str(payload.get("message") or "request failed"),
            tool=name,
            phase="validation",
        )
    return payload


def read_docs_resource(uri: str) -> dict[str, str] | None:
    for resource in MCP_RESOURCES:
        if resource["uri"] == uri:
            return resource
    if uri.startswith("docmancer://workflow/project-docs/"):
        project_path = uri.removeprefix("docmancer://workflow/project-docs/")
        return {
            "uri": uri,
            "name": "Project-specific docs workflow",
            "mimeType": "text/markdown",
            "text": f"""# Project docs workflow for `{project_path}`

1. `get_docs_context(project_path=\"{project_path}\", question=..., mode=\"auto\")`
2. If the response returns `prepare_docs` as `recommended_next_action`, follow it and retry the same request.
3. Inspect canonical `status` and cite `sources` through each factual item's `evidence_ids`.
""",
        }
    if uri.startswith("docmancer://library/"):
        parts = uri.removeprefix("docmancer://library/").split("/", 2)
        if len(parts) == 3:
            ecosystem, library, version = parts
            return {
                "uri": uri,
                "name": "Registered library docs lookup",
                "mimeType": "text/markdown",
                "text": f"""# Library docs workflow for `{ecosystem}:{library}@{version}`

1. `get_docs_context(
       question=...,
       library=\"{library}\",
       ecosystem=\"{ecosystem}\",
       version=\"{version}\",
       mode=\"library\"
   )`

2. If docs are missing/stale and network is approved:
   `prepare_docs(
       action=\"prefetch_library_docs\",
       library=\"{library}\",
       ecosystem=\"{ecosystem}\",
       version=\"{version}\"
   )`

3. Retry `get_docs_context(...)`.

Do not assume legacy `resolve_library_id` / `get_library_docs` tools are available on the public surface.
""",
            }
    return None


def _json_text(
    mcp_types: Any,
    payload: dict[str, Any],
    *,
    text_fallback: bool = False,
) -> list[Any]:
    text = json.dumps(payload, ensure_ascii=False) if text_fallback else BOUNDED_STRUCTURED_CONTENT_MARKER
    return [mcp_types.TextContent(type="text", text=text)]


def _mcp_tool_result(
    mcp_types: Any,
    payload: dict[str, Any],
    *,
    text_fallback: bool,
) -> Any:
    kwargs: dict[str, Any] = {
        "content": _json_text(mcp_types, payload, text_fallback=text_fallback),
    }
    if not text_fallback:
        kwargs["structuredContent"] = payload
    if payload.get("status") == "failed":
        kwargs["isError"] = True
    return mcp_types.CallToolResult(**kwargs)


async def _run_async(service: LibraryDocsService) -> None:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as mcp_types

    server: Server = Server("docmancer-docs")

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [mcp_types.Tool(**tool) for tool in current_tools()]

    @server.list_resources()
    async def _list_resources() -> list[mcp_types.Resource]:
        return [
            mcp_types.Resource(
                uri=cast(Any, resource["uri"]),
                name=resource["name"],
                description=resource["description"],
                mimeType=resource["mimeType"],
            )
            for resource in MCP_RESOURCES
        ]

    @server.list_resource_templates()
    async def _list_resource_templates() -> list[mcp_types.ResourceTemplate]:
        return [
            mcp_types.ResourceTemplate(
                uriTemplate=template["uriTemplate"],
                name=template["name"],
                description=template["description"],
                mimeType=template["mimeType"],
            )
            for template in MCP_RESOURCE_TEMPLATES
        ]

    @server.read_resource()
    async def _read_resource(uri: Any) -> str:
        resource = read_docs_resource(str(uri))
        if resource is None:
            raise ValueError(f"unknown resource: {uri}")
        return resource["text"]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> mcp_types.CallToolResult:
        # Tool handlers include synchronous indexing and HTTP clients.  Keep
        # them off the MCP event loop so docs_status can report a running job
        # while another request is still doing bounded retrieval work.
        payload = await asyncio.to_thread(call_docs_tool_payload, name, arguments, service)
        return _mcp_tool_result(
            mcp_types,
            payload,
            text_fallback=os.environ.get("DOCATLAS_MCP_TEXT_FALLBACK") == "1",
        )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def serve(config_path: str | Path | None = None) -> None:
    from docmancer.core.config_resolution import resolve_config

    resolved = resolve_config(explicit_path=config_path)
    asyncio.run(_run_async(LibraryDocsService(
        config=resolved.config,
        config_source=resolved.source,
        config_path=resolved.path,
    )))

__all__=['current_docs_surface', 'current_tools', '_exception_reason_code', '_public_handler_arguments', '_service_for_project_path', '_destructive_project_scope_error', 'call_docs_tool_payload', 'read_docs_resource', '_json_text', '_mcp_tool_result', '_run_async', 'serve']
