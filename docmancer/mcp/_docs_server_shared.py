"""Import-time shared state for the docs MCP server."""
from __future__ import annotations
from ._docs_server_schema import *  # noqa: F401,F403
from ._docs_server_tool_data import *  # noqa: F401,F403

def _handler_for_tool(name: str) -> ToolHandler:
    if name == "read_docs_source":
        return _handle_source_read_tool
    if name in {tool["name"] for tool in context_tools(RAW_TOOLS)}:
        return handle_context_tool
    if name in {tool["name"] for tool in library_tools(RAW_TOOLS)}:
        return handle_library_tool
    if name in {tool["name"] for tool in prefetch_tools(RAW_TOOLS)}:
        return handle_prefetch_tool
    if name in {tool["name"] for tool in project_tools(RAW_TOOLS)}:
        return handle_project_tool
    raise ValueError(f"No MCP docs handler registered for tool: {name}")


def _handle_source_read_tool(name: str, arguments: dict, service: Any) -> dict:
    # Lazy import avoids the shared-state/server import cycle. The resource
    # reader remains the sole authority and consumes the very same capability.
    from ._docs_server_part01 import read_docs_resource
    resource = read_docs_resource(arguments["uri"], service)
    if resource is None:
        return {"status": "source_unavailable", "reason_code": "unknown_or_expired_reference"}
    return json.loads(resource["text"])


def _strip_null_enum_values(value: Any) -> Any:
    """Strip legacy null enum members only when the declared type excludes null."""
    if isinstance(value, dict):
        cleaned = {key: _strip_null_enum_values(child) for key, child in value.items()}
        declared_type = cleaned.get("type")
        nullable = declared_type == "null" or (
            isinstance(declared_type, list) and "null" in declared_type
        )
        if "enum" in cleaned and isinstance(cleaned["enum"], list) and not nullable:
            cleaned["enum"] = [item for item in cleaned["enum"] if item is not None]
        return cleaned
    if isinstance(value, list):
        return [_strip_null_enum_values(item) for item in value]
    return value


def _tool_spec(raw: dict[str, Any], *, config: DocsServerConfig) -> ToolSpec:
    name = str(raw["name"])
    advertised_schema = _strip_null_enum_values(copy.deepcopy(
        PUBLIC_ADVERTISED_INPUT_SCHEMAS.get(name, raw["inputSchema"])
    ))
    description = PUBLIC_ADVERTISED_DESCRIPTIONS.get(name, str(raw["description"]))
    if name == "get_docs_context":
        from docmancer.docs.domain.minimal_context_config import minimal_context_enabled
        if minimal_context_enabled():
            properties = advertised_schema["properties"]
            properties["search_question"].pop("maxLength", None)
            properties["source_path"].pop("maxLength", None)
            properties["lookup_queries"].pop("maxItems", None)
            properties["lookup_queries"]["items"].pop("maxLength", None)
            description = (
                "Retrieve checked project documentation for one unchanged original question. "
                "Minimal-context candidate scans the complete authorized scope; source_path "
                "narrows to an exact relative document path. Optional search_question is a full "
                "host translation; lookup_queries refer to the same question, with no count or "
                "text-length quota. Never add expected answers or independent subquestions. "
                "Selection uses the pinned semantic policy; without a policy all sections are "
                "retained diagnostically. A 50000-token emergency stop is separate from selection. "
                "Context remains unverified and grants no mutation authority."
            )
    output_schema = copy.deepcopy(PUBLIC_ADVERTISED_OUTPUT_SCHEMAS.get(name, raw.get("outputSchema")))
    if name == "get_docs_context" and config.expose_advanced:
        advertised_schema["properties"]["context_format"] = copy.deepcopy(
            raw["inputSchema"]["properties"]["context_format"]
        )
        description += " Optional context_format=patch_context selects read-only evidence, never edit permission; omitted/null returns docs."
        output_schema = {"oneOf": [output_schema, copy.deepcopy(_PATCH_CONTEXT_OUTPUT_SCHEMA)]}
    # This opt-in uses text plus a private ledger, not the legacy structured schema.
    from docmancer.docs.domain.minimal_context_config import minimal_context_enabled
    candidate_text = minimal_context_enabled() and name in {"get_docs_context", "read_docs_source"}
    model_view = name == "get_docs_context" and os.environ.get("DOCATLAS_MCP_MODEL_VIEW") == "1"
    return ToolSpec(
        name=name,
        description=description,
        input_schema=advertised_schema,
        handler=_handler_for_tool(name),
        output_schema=None if config.text_fallback or model_view or candidate_text else output_schema,
        validation_schema=copy.deepcopy(advertised_schema),
    )


def build_docs_surface(config: DocsServerConfig) -> DocsMcpSurface:
    specs: list[ToolSpec] = []
    for raw in RAW_TOOLS:
        name = str(raw.get("name") or "")
        if name in CANDIDATE_TOOL_NAMES:
            from docmancer.docs.domain.minimal_context_config import minimal_context_enabled
            if not minimal_context_enabled():
                continue
        if name not in CLASSIFIED_TOOL_NAMES:
            raise ValueError(f"Unclassified MCP docs tool: {name}")
        if name in ADMIN_TOOL_NAMES and not config.expose_admin:
            continue
        if name in ADVANCED_TOOL_NAMES and not config.expose_advanced:
            continue
        specs.append(_tool_spec(raw, config=config))
    return DocsMcpSurface(
        tools=tuple(specs),
        handlers={spec.name: spec.handler for spec in specs},
    )


ALL_SURFACE = build_docs_surface(DocsServerConfig(expose_admin=True, expose_advanced=True))
DOCS_SURFACE = build_docs_surface(DocsServerConfig.from_env(os.environ))

ALL_TOOLS = [spec.to_tool_dict() for spec in ALL_SURFACE.tools]
TOOLS = [spec.to_tool_dict() for spec in DOCS_SURFACE.tools]

CONTEXT_TOOLS = context_tools(TOOLS)
LIBRARY_TOOLS = library_tools(TOOLS)
PROJECT_TOOLS = project_tools(TOOLS)
PREFETCH_TOOLS = prefetch_tools(TOOLS)

from ._docs_server_resources import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith('__')]
