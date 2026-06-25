from __future__ import annotations

from eval.task_level.schemas import ToolPolicy



def policy(response_style: str, *, preindex: bool) -> ToolPolicy:
    if response_style not in {"evidence-first", "snippet-first"}:
        raise ValueError(f"Unsupported DocAtlas response style: {response_style}")
    return ToolPolicy(
        allow_docatlas=True,
        docatlas_response_style=response_style,  # type: ignore[arg-type]
        preindex=preindex,
    )


def mcp_tool_allowlist() -> tuple[str, ...]:
    return ("docmancer-docs_get_docs_context",)
