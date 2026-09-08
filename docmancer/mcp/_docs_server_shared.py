"""Import-time shared state for the docs MCP server."""
from __future__ import annotations
from ._docs_server_schema import *  # noqa: F401,F403
from ._docs_server_tool_data import *  # noqa: F401,F403

_GET_DOCS_CONTEXT_QUESTION_PLANNING_GUIDANCE = """

Question planning:
- One get_docs_context call answers one concrete user question. If the user provides multiple independent questions (for example, a multi-question evaluation), make separate get_docs_context calls.
- A benchmark or evaluation request is not itself the documentation question when it contains or asks you to generate multiple concrete questions. Put each concrete documentation question in question on its own call.
- lookup_queries may translate, paraphrase, or decompose facets of the same question only. They are not a batch channel for independent questions or separate tasks.
"""
_GET_DOCS_CONTEXT_QUESTION_DESCRIPTION = (
    "One concrete user question for this call. For multiple independent questions, "
    "make separate get_docs_context calls. Never replace the concrete question with "
    "a generic evaluation or meta request."
)
_GET_DOCS_CONTEXT_LOOKUP_DESCRIPTION = (
    "Optional bounded single-concept lookups used only to improve retrieval recall for "
    "the same question. A lookup may translate, paraphrase, or decompose one facet of "
    "that question. Do not put independent questions or separate tasks here. Preserve "
    "exact identifiers."
)
_ORIGINAL_REQUEST_GUIDANCE = (
    "Pass the user's original request unchanged as question; never substitute a "
    "documentation-governance meta-question. "
)
_CONCRETE_QUESTION_GUIDANCE = (
    "Pass one concrete documentation question unchanged as question; never substitute "
    "the surrounding benchmark/evaluation request or a documentation-governance "
    "meta-question. "
)


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
    advertised_schema = _strip_null_enum_values(copy.deepcopy(
        PUBLIC_ADVERTISED_INPUT_SCHEMAS.get(name, raw["inputSchema"])
    ))
    description = PUBLIC_ADVERTISED_DESCRIPTIONS.get(name, str(raw["description"]))
    if name == "get_docs_context":
        description = description.replace(
            _ORIGINAL_REQUEST_GUIDANCE,
            _CONCRETE_QUESTION_GUIDANCE,
        )
        description = f"{description}{_GET_DOCS_CONTEXT_QUESTION_PLANNING_GUIDANCE}"
        properties = advertised_schema.get("properties", {})
        question_schema = properties.get("question")
        if isinstance(question_schema, dict):
            question_schema["description"] = _GET_DOCS_CONTEXT_QUESTION_DESCRIPTION
        lookup_schema = properties.get("lookup_queries")
        if isinstance(lookup_schema, dict):
            lookup_schema["description"] = _GET_DOCS_CONTEXT_LOOKUP_DESCRIPTION
        validation_schema = copy.deepcopy(advertised_schema)
    return ToolSpec(
        name=name,
        description=description,
        input_schema=advertised_schema,
        handler=_handler_for_tool(name),
        output_schema=(
            None
            if text_fallback
            else copy.deepcopy(PUBLIC_ADVERTISED_OUTPUT_SCHEMAS.get(name, raw.get("outputSchema")))
        ),
        validation_schema=(
            validation_schema
            if name == "get_docs_context"
            else _strip_null_enum_values(copy.deepcopy(
                PUBLIC_ADVERTISED_INPUT_SCHEMAS.get(name, validation_schema)
            ))
        ),
    )


def build_docs_surface(config: DocsServerConfig) -> DocsMcpSurface:
    specs: list[ToolSpec] = []
    for raw in RAW_TOOLS:
        name = str(raw.get("name") or "")
        if name not in CLASSIFIED_TOOL_NAMES:
            raise ValueError(f"Unclassified MCP docs tool: {name}")
        if name in ADMIN_TOOL_NAMES and not config.expose_admin:
            continue
        if name in ADVANCED_TOOL_NAMES and not config.expose_advanced:
            continue
        specs.append(_tool_spec(raw, text_fallback=config.text_fallback))
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
