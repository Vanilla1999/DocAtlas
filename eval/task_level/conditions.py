from __future__ import annotations

from .schemas import Condition, ToolPolicy


CONDITIONS: dict[str, Condition] = {
    "repo_only": Condition(
        condition_id="repo_only",
        label="A - repo-only",
        tool_policy=ToolPolicy(),
    ),
    "repo_only_strict_offline": Condition(
        condition_id="repo_only_strict_offline",
        label="A1 - repo-only strict offline",
        tool_policy=ToolPolicy(),
    ),
    "repo_only_web_audited": Condition(
        condition_id="repo_only_web_audited",
        label="A2 - repo-only web/network audited",
        tool_policy=ToolPolicy(allow_web=True),
    ),
    "repo_plus_audited_external_context": Condition(
        condition_id="repo_plus_audited_external_context",
        label="A3 - repo plus pinned audited external context",
        tool_policy=ToolPolicy(inject_external_context=True),
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
    "docatlas_action_checklist_injected": Condition(
        condition_id="docatlas_action_checklist_injected",
        label="G - DocAtlas context plus action checklist injected",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
            inject_docatlas_context=True,
            inject_action_checklist=True,
        ),
    ),
    "docatlas_patch_constraints_injected": Condition(
        condition_id="docatlas_patch_constraints_injected",
        label="H - DocAtlas patch constraints injected",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
            inject_patch_constraints=True,
            max_constraint_packet_tokens=1200,
            max_constraints=12,
            max_sources=8,
        ),
    ),
    "docatlas_patch_constraints_workflow": Condition(
        condition_id="docatlas_patch_constraints_workflow",
        label="H2 - DocAtlas patch constraints workflow",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
            recommend_docatlas_before_edit=True,
            max_constraint_packet_tokens=1200,
            max_constraints=12,
            max_sources=8,
        ),
    ),
    "docatlas_action_checklist_only": Condition(
        condition_id="docatlas_action_checklist_only",
        label="H - DocAtlas action checklist only",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=True,
            inject_action_checklist=True,
        ),
    ),
    "docatlas_zero_setup": Condition(
        condition_id="docatlas_zero_setup",
        label="I - DocAtlas zero-setup exploratory",
        tool_policy=ToolPolicy(
            allow_docatlas=True,
            docatlas_response_style="snippet-first",
            preindex=False,
        ),
    ),
    "docatlas_bounded_direct": Condition(
        condition_id="docatlas_bounded_direct",
        label="J - DocAtlas bounded direct ActionPacket",
        tool_policy=ToolPolicy(
            allow_docatlas=False,
            preindex=True,
            delivery_strategy="bounded_direct",
        ),
    ),
    "docatlas_bounded_subagent": Condition(
        condition_id="docatlas_bounded_subagent",
        label="K - DocAtlas bounded isolated worker",
        tool_policy=ToolPolicy(
            allow_docatlas=False,
            preindex=True,
            delivery_strategy="bounded_subagent",
            isolated_worker_required=True,
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
