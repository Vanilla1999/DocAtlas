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
        label="D - DocAtlas preindexed snippet-first",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
        ),
    ),
    "docatlas_zero_setup": Condition(
        condition_id="docatlas_zero_setup",
        label="E - DocAtlas zero-setup exploratory",
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
    "docatlas_snippet_first",
)
