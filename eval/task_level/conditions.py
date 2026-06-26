from __future__ import annotations

from .schemas import Condition, ToolPolicy


CONDITIONS: dict[str, Condition] = {
    "repo_only": Condition(
        condition_id="repo_only",
        label="A - repo-only",
        tool_policy=ToolPolicy(),
    ),
    "context7": Condition(
        condition_id="context7",
        label="B - Context7",
        tool_policy=ToolPolicy(allow_context7=True),
    ),
    "docatlas_evidence_first": Condition(
        condition_id="docatlas_evidence_first",
        label="C - DocAtlas preindexed evidence-first",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="evidence-first",
            preindex=True,
        ),
    ),
    "docatlas_snippet_first": Condition(
        condition_id="docatlas_snippet_first",
        label="D - DocAtlas tool optional snippet-first (deprecated alias)",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
        ),
    ),
    "docatlas_tool_optional": Condition(
        condition_id="docatlas_tool_optional",
        label="D - DocAtlas tool optional snippet-first",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
        ),
    ),
    "docatlas_tool_recommended": Condition(
        condition_id="docatlas_tool_recommended",
        label="E - DocAtlas tool recommended before edit",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
            recommend_docatlas_before_edit=True,
        ),
    ),
    "docatlas_context_injected": Condition(
        condition_id="docatlas_context_injected",
        label="F - DocAtlas verified context injected",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
            inject_docatlas_context=True,
        ),
    ),
    "docatlas_tool_required_once": Condition(
        condition_id="docatlas_tool_required_once",
        label="G - DocAtlas tool required once before edit",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
            require_docatlas_call_before_edit=True,
        ),
    ),
    "docatlas_zero_setup": Condition(
        condition_id="docatlas_zero_setup",
        label="H - DocAtlas zero-setup exploratory",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=False,
        ),
    ),
}


DEFAULT_CONDITIONS = (
    "repo_only",
    "context7",
    "docatlas_evidence_first",
    "docatlas_tool_recommended",
)


DOCATLAS_OPTIONAL_ALIASES = {"docatlas_snippet_first", "docatlas_tool_optional"}
