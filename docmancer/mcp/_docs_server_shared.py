"""Import-time shared state for the docs MCP server."""
from __future__ import annotations
from ._docs_server_schema import *  # noqa: F401,F403
from ._docs_server_tool_data import *  # noqa: F401,F403

def _handler_for_tool(name: str) -> ToolHandler:
    if name in {tool["name"] for tool in context_tools(RAW_TOOLS)}:
        return handle_context_tool
    if name in {tool["name"] for tool in library_tools(RAW_TOOLS)}:
        return handle_library_tool
    if name in {tool["name"] for tool in prefetch_tools(RAW_TOOLS)}:
        return handle_prefetch_tool
    if name in {tool["name"] for tool in project_tools(RAW_TOOLS)}:
        return handle_project_tool
    raise ValueError(f"No MCP docs handler registered for tool: {name}")


def _strip_null_enum_values(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {key: _strip_null_enum_values(child) for key, child in value.items()}
        if "enum" in cleaned and isinstance(cleaned["enum"], list):
            cleaned["enum"] = [item for item in cleaned["enum"] if item is not None]
        return cleaned
    if isinstance(value, list):
        return [_strip_null_enum_values(item) for item in value]
    return value


def _tool_spec(raw: dict[str, Any], *, text_fallback: bool = False) -> ToolSpec:
    name = str(raw["name"])
    validation_schema = _strip_null_enum_values(copy.deepcopy(raw["inputSchema"]))
    return ToolSpec(
        name=name,
        description=PUBLIC_ADVERTISED_DESCRIPTIONS.get(name, str(raw["description"])),
        input_schema=_strip_null_enum_values(copy.deepcopy(
            PUBLIC_ADVERTISED_INPUT_SCHEMAS.get(name, raw["inputSchema"])
        )),
        handler=_handler_for_tool(name),
        output_schema=(
            None
            if text_fallback
            else copy.deepcopy(PUBLIC_ADVERTISED_OUTPUT_SCHEMAS.get(name, raw.get("outputSchema")))
        ),
        validation_schema=validation_schema,
    )


def build_docs_surface(config: DocsServerConfig) -> DocsMcpSurface:
    specs: list[ToolSpec] = []
    for raw in RAW_TOOLS:
        name = str(raw.get("name") or "")
        if name not in CLASSIFIED_TOOL_NAMES:
            raise ValueError(f"Unclassified MCP docs tool: {name}")
        if name in LEGACY_TOOL_NAMES and not config.expose_legacy:
            continue
        if name in ADMIN_TOOL_NAMES and not config.expose_admin:
            continue
        if name in ADVANCED_TOOL_NAMES and not config.expose_advanced:
            continue
        specs.append(_tool_spec(raw, text_fallback=config.text_fallback))
    return DocsMcpSurface(
        tools=tuple(specs),
        handlers={spec.name: spec.handler for spec in specs},
    )


ALL_SURFACE = build_docs_surface(DocsServerConfig(expose_legacy=True, expose_admin=True, expose_advanced=True))
DOCS_SURFACE = build_docs_surface(DocsServerConfig.from_env(os.environ))

ALL_TOOLS = [spec.to_tool_dict() for spec in ALL_SURFACE.tools]
TOOLS = [spec.to_tool_dict() for spec in DOCS_SURFACE.tools]

CONTEXT_TOOLS = context_tools(TOOLS)
LIBRARY_TOOLS = library_tools(TOOLS)
PROJECT_TOOLS = project_tools(TOOLS)
PREFETCH_TOOLS = prefetch_tools(TOOLS)








_EXPLICIT_UNBOUNDED_COMPATIBILITY_FIELDS = frozenset({
    "output_mode", "details", "include_sections", "page", "page_size", "maintenance",
})

from ._docs_server_resources import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith('__')]
