from __future__ import annotations

from eval.task_level.schemas import ToolPolicy



POLICY = ToolPolicy(allow_context7=True)


def mcp_tool_allowlist() -> tuple[str, ...]:
    return ("context7_resolve-library-id", "context7_query-docs")
