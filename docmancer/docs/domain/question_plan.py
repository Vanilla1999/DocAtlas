"""Bounded compositional parser for project-documentation questions.

This layer exists to keep natural-language parsing separate from proof
validation. It intentionally recognizes a small auditable grammar and marks
unresolved subjects/operations instead of inventing generic proof identities.
Rule precedence is explicit in ``_RULES``; adding a rule cannot silently change
another rule's order inside one long conditional chain.
"""
from __future__ import annotations

from dataclasses import replace
import re

from docmancer.docs.domain.question_frame_core import (
    QuestionClause,
    ambiguous_frame_reason,
    match_action_frame,
    match_inventory_frame,
    match_requirements_frame,
    split_question_clause_spans,
)
from docmancer.docs.domain.question_semantic_frames import (
    match_argument_value_frame,
    match_before_behavior_frame,
    match_comparison_frame,
    match_condition_frame,
    match_contract_scope_frame,
    match_decision_frame,
    match_location_frame,
    match_premise_frame,
    match_purpose_behavior_frame,
)
from docmancer.docs.domain.question_surface_normalization import (
    normalize_question_surface,
    rebind_surface_plan,
)
from docmancer.docs.domain.technical_terms import TechnicalTermKind

from docmancer.docs.domain.question_plan_core import (
    PlanKind,
    PlannedFacet,
    QuestionPlan,
    Rule,
    _bind_plan_to_clause,
    _bind_whole_plan,
    _clean,
    _normalized_clause,
    _technical,
    _unsafe_free_text,
)
from docmancer.docs.domain.question_plan_command_rules import (
    _command_sync,
    _docs_mcp_server_command,
    _offline_suite_run,
    _two_cell_cardinality,
)
from docmancer.docs.domain.question_plan_surface_rules import (
    governance_facets,
    mcp_request_handling,
    provider_request_timeout,
    public_tool_usage,
    public_tools_with_purposes,
    python_version_support,
)


def _release_docs_line_limit(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*which\s+(?:docs|documentation)\s+files\s+must\s+stay\s+under\s+"
        r"(?:the\s+)?(?:1,?000|1000)[- ]line\s+release\s+limit\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation",
            "canonical user-facing release set",
            relation="release_line_limit",
            context="1000-line release limit",
            span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("relation:release_line_limit",),
    )


def _storage_coordination_contract(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*(?:"
        r"what\s+is\s+the\s+storage\s+mutation\s+coordination\s+contract"
        r"(?:\s+for\s+cleanup\s+and\s+refresh)?|"
        r"explain\s+the\s+storage\s+mutation\s+coordination\s+contract"
        r")\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation",
            "storage mutation coordination",
            relation="storage_coordination",
            context="cleanup and refresh",
            span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("relation:storage_coordination",),
    )


def _remove_library_during_refresh(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*what\s+happens\s+if\s+(remove_library_docs)\s+runs\s+while\s+"
        r"(?:a\s+)?library\s+refresh\s+is\s+in\s+flight\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    subject, kind, aliases = _technical(match.group(1), "code_symbol")
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation",
            subject,
            relation="conditional_library_removal",
            context="library refresh in flight",
            subject_kind=kind,
            subject_aliases=aliases,
            span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("relation:conditional_library_removal",),
    )


def _source_type_inventory(q: str) -> QuestionPlan | None:
    if re.match(r"^\s*what\s+source\s+types?\s+are\s+supported\s+for\s+indexing\s*[?!.]*\s*$", q, re.I) is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            kind="inventory",
            subject="source types",
            attribute="source",
            item_kind="source",
            value_kind="identifier_list",
            response_mode="names",
            span_text="source types",
        ),),
        clauses=(q,),
        parse_trace=("inventory:source_types",),
    )


def _release_checklist_compound(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*what\s+is\s+(.+?)\s+and\s+what\s+(.+?)\s*[?!.]*\s*$", q, re.I)
    if match is None:
        return None
    left, right = _clean(match.group(1)), _clean(match.group(2))
    if re.fullmatch(r".*?gates?\s+(?:that\s+)?block\s+release", right, re.I) is None:
        return None
    return QuestionPlan(
        facets=(
            PlannedFacet("purpose", left, relation="purpose", response_mode="purpose", span_text=match.group(1)),
            PlannedFacet("relation", "release", relation="blocking_gates", span_text=match.group(2)),
        ),
        clauses=(left, right),
        parse_trace=("compound:purpose", "compound:blocking_gates"),
    )

def _token_bounding_compound(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*what\s+is\s+(.+?)\s+and\s+how\s+is\s+(.+?)\s*[?!.]*\s*$", q, re.I)
    if match is None:
        return None
    left, right = _clean(match.group(1)), _clean(match.group(2))
    if re.fullmatch(r".*?token[- ]bounded", right, re.I) is None:
        return None
    return QuestionPlan(
        facets=(
            PlannedFacet("definition", left, span_text=match.group(1)),
            PlannedFacet("relation", left, relation="token_bounding", context=right, span_text=match.group(2)),
        ),
        clauses=(left, right),
        parse_trace=("compound:definition", "compound:token_bounding"),
    )

def _public_tools_with_usage(q: str) -> QuestionPlan | None:
    if re.match(
        r"^\s*what\s+are\s+the\s+three\s+public\s+docs\s+mcp\s+tools\s+"
        r"and\s+when\s+do\s+i\s+use\s+each\s+one\s*[?!.]*\s*$",
        q,
        re.I,
    ) is None:
        return None
    # Decompose the compound request into atomic mandatory facets.  The selector
    # can then satisfy each tool from a different bounded evidence candidate
    # without weakening local proof or inventing a cross-document AnswerUnit.
    tools = ("get_docs_context", "prepare_docs", "docs_status")
    return QuestionPlan(
        facets=tuple(
            PlannedFacet(
                "relation",
                tool,
                relation="public_tool_usage",
                context="Docs MCP public tools",
                subject_kind="code_symbol",
                subject_aliases=(tool,),
                span_text="three public Docs MCP tools",
            )
            for tool in tools
        ),
        clauses=(q,),
        parse_trace=("frame:public_tools_atomic_usage",),
    )


def _env_var_purpose_usage(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*what\s+is\s+(DOCMANCER_[A-Z0-9_]+)\s+and\s+when\s+should\s+it\s+be\s+used\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    subject, kind, aliases = _technical(match.group(1), "env_var")
    return QuestionPlan(
        facets=(
            PlannedFacet(
                "purpose", subject, relation="purpose", response_mode="purpose",
                subject_kind=kind, subject_aliases=aliases, span_text=match.group(1),
            ),
            PlannedFacet(
                "usage", subject, relation="usage", subject_kind=kind,
                subject_aliases=aliases, span_text="when should it be used",
            ),
        ),
        clauses=(q,),
        parse_trace=("env:purpose", "env:usage"),
    )


_CLEAR_INDEX_CONDITION_RE = re.compile(
    r"(?:"
    r"(?:a\s+)?live(?:\s+mcp)?\s+process(?:\s+pid)?\s+"
    r"(?:holds|owns|locks)\s+(?:the\s+)?index|"
    r"(?:a\s+)?live(?:\s+mcp)?\s+process(?:\s+pid)?\s+is\s+"
    r"(?:holding|using)\s+(?:the\s+)?index|"
    r"(?:an?\s+)?index\s+writer\s+is\s+active|"
    r"(?:the\s+)?index\s+is\s+held\s+by\s+"
    r"(?:a\s+)?live(?:\s+mcp)?\s+process(?:\s+pid)?"
    r")",
    re.I,
)


def _conditional_clear_index(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*what\s+does\s+(clear-index)\s+do\s+when\s+"
        r"(.+?)\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if (
        match is None
        or _unsafe_free_text(match.group(2))
        or _CLEAR_INDEX_CONDITION_RE.fullmatch(_clean(match.group(2))) is None
    ):
        return None
    subject, kind, aliases = _technical(match.group(1), "cli_command")
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation", subject, relation="conditional_behavior", context=_clean(match.group(2)),
            subject_kind=kind, subject_aliases=aliases, span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("relation:conditional_behavior",),
    )

_CONFIG_TARGET_RE = (
    r"(?:[A-Za-z]:[\\/])?"
    r"(?:[A-Za-z0-9_.-]+[\\/])*[A-Za-z0-9_.-]+"
)


def _configuration_workflow(q: str) -> QuestionPlan | None:
    match = re.match(
        rf"^\s*how\s+do\s+i\s+configure\s+(?:a\s+)?project\s+in\s+"
        rf"([`\"']?{_CONFIG_TARGET_RE}[`\"']?)\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None or _unsafe_free_text(match.group(1)):
        return None
    raw = _clean(match.group(1)).strip("`\"'")
    preferred: TechnicalTermKind | None = (
        "config_key"
        if "." in match.group(1) and not match.group(1).endswith(".yaml")
        else None
    )
    subject, kind, aliases = _technical(raw, preferred)
    return QuestionPlan(
        facets=(PlannedFacet(
            "workflow", subject, relation="configuration", context="project configuration",
            response_mode="workflow", subject_kind=kind, subject_aliases=aliases,
            span_text=match.group(1),
        ),),
        clauses=(q,),
        parse_trace=("workflow:configuration",),
    )


def _contamination_definition(q: str) -> QuestionPlan | None:
    if re.match(
        r"^\s*what\s+is\s+contamination\s+protection\s+in\s+"
        r"(?:the\s+)?eval\s+protocols\s*[?!.]*\s*$",
        q,
        re.I,
    ) is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "definition", "contamination protection", context="eval protocols",
            span_text="contamination protection",
        ),),
        clauses=(q,),
        parse_trace=("definition:contamination_protection",),
    )


def _v4_protocol_run(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*how\s+do\s+i\s+run\s+the\s+project\s+answer\s+quality\s+v4\s+protocol\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "workflow",
            "project answer quality v4 protocol",
            relation="protocol_run",
            context="v4",
            response_mode="workflow",
            span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("workflow:v4_protocol_run",),
    )


def _named_run_or_verify(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*how\s+do\s+i\s+(run|verify)\s+(.+?)\s*[?!.]*\s*$", q, re.I)
    if match is None or _unsafe_free_text(
        match.group(2),
        allow_initial_request_head=True,
    ):
        return None
    action, subject = match.group(1).casefold(), _clean(match.group(2))
    if subject.casefold() == "project answer quality protocols":
        subject = "project answer quality protocol"
    context = None
    if " from " in subject:
        subject, context = subject.split(" from ", 1)
    return QuestionPlan(
        facets=(PlannedFacet(
            "workflow" if action == "run" else "relation",
            subject,
            relation="procedure" if action == "run" else "verification",
            context=context,
            response_mode="workflow" if action == "run" else "value",
            span_text=match.group(2),
        ),),
        clauses=(q,),
        parse_trace=(f"{action}:{subject}",),
    )

_CHOICE_TAIL_RE = re.compile(
    r"(?:(?:which|what)\s+)?"
    r"(?:evidence\s+)?(?:candidates?|witnesses?|proofs?|items?|results?|"
    r"sources?|documents?|chunks?|units?)"
    r"(?:\s+(?:are|should\s+be)\s+(?:selected|chosen|ranked))?"
    r"|(?:which|what)\s+(?:evidence|candidates?|items?|results?)\s+"
    r"(?:to\s+)?(?:use|select|choose|rank)",
    re.I,
)
_SPLIT_TAIL_RE = re.compile(
    r"(?:documents?|input|text|content|files?|pages?|questions?|queries?|"
    r"results?|evidence)"
    r"(?:\s+(?:into|by|across)\s+"
    r"(?:sections?|chunks?|clauses?|units?|groups?)"
    r"(?:\s+and\s+(?:sections?|chunks?|clauses?|units?|groups?))?"
    r"|\s+(?:sections?|chunks?|clauses?|units?))",
    re.I,
)


def _named_behavior(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*how\s+does\s+(.+?)\s+(work|choose|split)"
        r"(?:\s+(.+?))?\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    subject = _clean(match.group(1))
    action = match.group(2).casefold()
    tail = _clean(match.group(3) or "")
    if subject.casefold() == "prepare_docs sync_project_docs":
        return None
    if not subject or _unsafe_free_text(subject):
        return None
    if action == "work" and tail:
        return None
    if action == "choose" and (not tail or _CHOICE_TAIL_RE.fullmatch(tail) is None):
        return None
    if action == "split" and (not tail or _SPLIT_TAIL_RE.fullmatch(tail) is None):
        return None

    relation = "behavior"
    if subject.casefold() == "indexing" and action == "split":
        relation = "chunking"
    elif action == "choose":
        relation = "selection_policy"
    return QuestionPlan(
        facets=(PlannedFacet(
            "behavior",
            subject,
            relation=relation,
            target=tail or None,
            span_text=match.group(1),
        ),),
        clauses=(q,),
        parse_trace=(f"behavior:{relation}:{subject}",),
    )


_SMOKE_CONTEXT_RE = re.compile(
    r"(?:"
    r"(?:local\s+)?Task\s+\d+(?:\.\d+)*\s+benchmarks?|"
    r"(?:local\s+)?benchmarks?|DocAtlas"
    r")",
    re.I,
)


def _two_cell_smoke(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*what\s+is\s+the\s+(.+?smoke\s+procedure)\s+for\s+"
        r"(.+?)\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if (
        match is None
        or _unsafe_free_text(match.group(2))
        or _SMOKE_CONTEXT_RE.fullmatch(_clean(match.group(2))) is None
    ):
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "workflow", _clean(match.group(1)), relation="procedure",
            context=_clean(match.group(2)), response_mode="workflow", span_text=match.group(1),
        ),),
        clauses=(q,),
        parse_trace=("workflow:smoke_procedure",),
    )

def _test_markers_and_offline_suite(q: str) -> QuestionPlan | None:
    if re.match(
        r"^\s*what\s+test\s+markers\s+are\s+available\s+and\s+how\s+do\s+i\s+run\s+the\s+offline\s+suite\s*[?!.]*\s*$",
        q,
        re.I,
    ) is None:
        return None
    return QuestionPlan(
        facets=(
            PlannedFacet(
                "inventory", "test suite", attribute="marker", item_kind="marker",
                value_kind="identifier_list", response_mode="names", span_text="test markers",
            ),
            PlannedFacet(
                "workflow", "offline suite", relation="procedure",
                response_mode="workflow", span_text="run the offline suite",
            ),
        ),
        clauses=(q,),
        parse_trace=("inventory:test_marker", "workflow:offline_suite"),
    )


def _semantic_comparison(q: str) -> QuestionPlan | None:
    frame = match_comparison_frame(q)
    if frame is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "comparison", frame.left, relation="contrast", target=frame.right,
            span_text=q,
        ),),
        clauses=(q,),
        parse_trace=("frame:comparison",),
    )


def _semantic_location(q: str) -> QuestionPlan | None:
    frame = match_location_frame(q)
    if frame is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "location", frame.subject, relation="location",
            value_kind="path", response_mode="path", span_text=q,
        ),),
        clauses=(q,),
        parse_trace=("frame:location",),
    )


def _semantic_condition(q: str) -> QuestionPlan | None:
    frame = match_condition_frame(q)
    if frame is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation", frame.subject, relation=frame.relation,
            context=frame.condition, span_text=q,
        ),),
        clauses=(q,),
        parse_trace=(f"frame:condition:{frame.relation}",),
    )


def _semantic_premise(q: str) -> QuestionPlan | None:
    frame = match_premise_frame(q)
    if frame is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation", frame.subject, relation=frame.relation,
            target=frame.target, expected_value=frame.expected_value,
            span_text=q,
        ),),
        clauses=(q,),
        parse_trace=(f"frame:premise:{frame.relation}",),
    )


_SPECIFIC_RULES: tuple[Rule, ...] = (
    governance_facets,
    _semantic_premise,
    _semantic_comparison,
    _semantic_location,
    _semantic_condition,
    public_tool_usage,
    public_tools_with_purposes,
    python_version_support,
    mcp_request_handling,
    provider_request_timeout,
    _docs_mcp_server_command,
    _command_sync,
    _offline_suite_run,
    _two_cell_cardinality,
    _release_docs_line_limit,
    _storage_coordination_contract,
    _remove_library_during_refresh,
    _source_type_inventory,
    _release_checklist_compound,
    _token_bounding_compound,
    _public_tools_with_usage,
    _env_var_purpose_usage,
    _conditional_clear_index,
    _configuration_workflow,
    _contamination_definition,
    _v4_protocol_run,
    _two_cell_smoke,
    _test_markers_and_offline_suite,
)

_GENERIC_RULES: tuple[Rule, ...] = (
    _named_run_or_verify,
    _named_behavior,
)




def _reusable_frame_plan(q: str) -> QuestionPlan | None:
    decision = match_decision_frame(q)
    if decision is not None:
        return QuestionPlan(facets=(PlannedFacet(
            "attribute", decision.subject, relation="decision_for_action",
            attribute=decision.decision_kind, target=decision.action,
            value_kind="code", response_mode="value", span_text=q,
        ),), clauses=(q,), parse_trace=("frame:decision_for_action",))

    argument = match_argument_value_frame(q)
    if argument is not None:
        return QuestionPlan(facets=(PlannedFacet(
            "attribute", argument.callee, relation="argument_value",
            attribute=argument.argument, context=argument.actor,
            value_kind="boolean", response_mode="value", span_text=q,
        ),), clauses=(q,), parse_trace=("frame:argument_value",))

    contract = match_contract_scope_frame(q)
    if contract is not None:
        return QuestionPlan(facets=(PlannedFacet(
            "relation", contract.subject, relation="applicable_contract",
            target=contract.contract, context=contract.condition,
            value_kind="text", response_mode="value", span_text=q,
        ),), clauses=(q,), parse_trace=("frame:applicable_contract",))

    before = match_before_behavior_frame(q)
    if before is not None:
        return QuestionPlan(facets=(PlannedFacet(
            "behavior", before.subject, relation="behavior_before",
            target=before.action, response_mode="value", span_text=q,
        ),), clauses=(q,), parse_trace=("frame:behavior_before",))

    purpose = match_purpose_behavior_frame(q)
    if purpose is not None:
        return QuestionPlan(facets=(PlannedFacet(
            "behavior", purpose.subject, relation="purpose_behavior",
            target=purpose.purpose, response_mode="value", span_text=q,
        ),), clauses=(q,), parse_trace=("frame:purpose_behavior",))

    # Exact typed frames take precedence over broad ambiguity sentinels.  A
    # phrase such as "file formats" or "pytest markers" is already a closed
    # category; only bare "formats"/"markers" remain ambiguous.
    inventory = match_inventory_frame(q)
    if inventory is not None:
        return QuestionPlan(
            facets=(PlannedFacet(
                "inventory", inventory.subject, attribute=inventory.attribute,
                item_kind=inventory.item_kind, value_kind="identifier_list",
                response_mode="names", context=inventory.context, span_text=q,
            ),),
            clauses=(q,),
            parse_trace=(f"frame:inventory:{inventory.item_kind}",),
        )

    ambiguity = ambiguous_frame_reason(q)
    if ambiguity is not None:
        return QuestionPlan(
            clauses=(q,),
            unresolved_parts=(ambiguity,),
            parse_trace=("fail_closed:ambiguous_frame",),
        )

    requirements = match_requirements_frame(q)
    if requirements is not None:
        return QuestionPlan(
            facets=(PlannedFacet(
                "relation", requirements.subject, relation="requirements",
                response_mode="value", span_text=q,
            ),),
            clauses=(q,),
            parse_trace=("frame:requirements",),
        )

    action = match_action_frame(q)
    if action is not None and action.operation == "sync_project_docs":
        return QuestionPlan(
            facets=(PlannedFacet(
                "command", "sync_project_docs", relation="invocation",
                value_kind="call_expression", expected_value="sync_project_docs",
                response_mode="call", subject_kind="code_symbol",
                subject_aliases=(
                    "sync_project_docs", "sync-project-docs",
                    "sync project docs", "refresh project documentation",
                    "project docs index",
                ),
                span_text=q,
            ),),
            clauses=(q,),
            parse_trace=("frame:action:sync_project_docs",),
        )
    return None


_UNSAFE_GENERIC_SUBJECTS = frozenset({
    "project", "system", "workflow", "request", "requested operation",
    "the", "it", "this", "thing",
})


def _normal_subject(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _guard_plan_subjects(plan: QuestionPlan) -> QuestionPlan:
    unsafe = tuple(dict.fromkeys(
        facet.subject
        for facet in plan.facets
        if _normal_subject(facet.subject) in _UNSAFE_GENERIC_SUBJECTS
    ))
    if not unsafe:
        return plan
    unresolved = tuple(dict.fromkeys((
        *plan.unresolved_parts,
        *("unresolved_query_subject" for _ in unsafe),
    )))
    return QuestionPlan(
        clauses=plan.clauses,
        unresolved_parts=unresolved,
        parse_trace=(*plan.parse_trace, "fail_closed:generic_subject"),
    )


def _compile_specific_question(q: str) -> QuestionPlan | None:
    framed = _reusable_frame_plan(q)
    if framed is not None and framed.handled:
        return _guard_plan_subjects(framed)

    for rule in _SPECIFIC_RULES:
        plan = rule(q)
        if plan is not None and plan.handled:
            return _guard_plan_subjects(plan)

    return None


def _compile_generic_question(q: str) -> QuestionPlan | None:
    for rule in _GENERIC_RULES:
        plan = rule(q)
        if plan is not None and plan.handled:
            return _guard_plan_subjects(plan)

    return None


def _compile_atomic_question(q: str) -> QuestionPlan | None:
    specific = _compile_specific_question(q)
    if specific is not None:
        return specific
    return _compile_generic_question(q)


def _unresolved_compound(clauses: tuple[str, ...], *, trace: str) -> QuestionPlan:
    return QuestionPlan(
        clauses=clauses,
        unresolved_parts=tuple(
            f"unresolved_question_clause:{clause}" for clause in clauses
        ),
        parse_trace=(trace,),
    )


def _combine_clause_plans(
    question: str,
    clauses: tuple[QuestionClause, ...],
) -> QuestionPlan | None:
    if len(clauses) <= 1:
        return None

    clause_texts = tuple(
        _normalized_clause(clause, compound=True) for clause in clauses
    )
    raw_plans = tuple(_compile_atomic_question(text) for text in clause_texts)
    plans = tuple(
        _bind_plan_to_clause(plan, clause) if plan is not None else None
        for clause, plan in zip(clauses, raw_plans)
    )
    handled = tuple(plan for plan in plans if plan is not None and plan.handled)

    if handled and any(plan.facets for plan in handled):
        facets = tuple(facet for plan in handled for facet in plan.facets)
        trace = tuple(row for plan in handled for row in plan.parse_trace)
        consumed = tuple(span for plan in handled for span in plan.consumed_spans)
        unresolved = tuple(
            f"unresolved_question_clause:{clause}"
            for clause, plan in zip(clause_texts, plans)
            if plan is None or not plan.handled
        )
        unresolved += tuple(
            row for plan in handled for row in plan.unresolved_parts
        )
        return _guard_plan_subjects(QuestionPlan(
            facets=facets,
            clauses=clause_texts,
            unresolved_parts=tuple(dict.fromkeys(unresolved)),
            parse_trace=("frame:compound", *trace),
            consumed_spans=tuple(sorted(set(consumed))),
        ))

    # Some frozen compound rules are intentionally recognized as a whole
    # (for example the three public Docs MCP tools + per-tool usage). Permit
    # that only when the whole rule produces at least one mandatory facet per
    # detected clause. A one-facet prefix match cannot authorize two clauses.
    normalized_question = " ".join(question.split())
    whole = _compile_atomic_question(normalized_question)
    if (
        whole is not None
        and whole.handled
        and not whole.unresolved_parts
        and len(whole.facets) >= len(clauses)
    ):
        bound = _bind_whole_plan(whole, question, clauses)
        return _guard_plan_subjects(replace(
            bound,
            clauses=clause_texts,
            parse_trace=("frame:whole_compound", *whole.parse_trace),
        ))
    if whole is not None and whole.handled:
        unresolved = tuple(
            f"unresolved_question_clause:{clause}" for clause in clause_texts[1:]
        ) or tuple(
            f"unresolved_question_clause:{clause}" for clause in clause_texts
        )
        if whole.facets:
            bound = _bind_plan_to_clause(
                whole,
                QuestionClause(question, 0, len(question)),
            )
            bound = replace(bound, consumed_spans=())
        else:
            bound = whole
        return _guard_plan_subjects(replace(
            bound,
            clauses=clause_texts,
            unresolved_parts=tuple(dict.fromkeys((*whole.unresolved_parts, *unresolved))),
            parse_trace=("fail_closed:partial_question", *whole.parse_trace),
        ))
    if handled:
        unresolved = tuple(
            row for plan in handled for row in plan.unresolved_parts
        )
        return QuestionPlan(
            clauses=clause_texts,
            unresolved_parts=tuple(dict.fromkeys(unresolved)),
            parse_trace=("fail_closed:unresolved_compound",),
        )
    return None


def _prefix_plan_is_owned(plan: QuestionPlan) -> bool:
    """Only exact parser-owned frames may turn an extension into fail-closed."""

    if not plan.facets or plan.unresolved_parts:
        return False
    traces = set(plan.parse_trace)
    if "frame:requirements" in traces:
        # Generic requirements still have supported legacy extensions such as
        # ``What does Phase 3.1 require for ...?``.  Only the already-modelled
        # two-cell procedure owns a strict prefix until generic trailing
        # requirement relations are represented explicitly.
        return all(
            facet.subject.casefold() == "two-cell smoke procedure"
            for facet in plan.facets
        )
    if any(row.startswith(("run:", "verify:", "behavior:behavior:")) for row in traces):
        return False
    return True


def _recognized_prefix_residue_plan(q: str) -> QuestionPlan | None:
    """Fail closed only when an exact new-parser question is a strict prefix.

    This replaces regex ownership lists.  A legacy-only surface is never
    claimed merely because it resembles a new frame.
    """

    normalized = " ".join(str(q or "").split())
    if not normalized:
        return None
    cut_points = [match.start() for match in re.finditer(r"\s+", normalized)]
    for cut in reversed(cut_points):
        prefix = normalized[:cut].rstrip(" \t\r\n,;:.!?/\u2013\u2014")
        if not prefix:
            continue
        plan = _compile_atomic_question(prefix)
        if plan is None or not _prefix_plan_is_owned(plan):
            continue
        residue = normalized[len(prefix):].strip()
        if not residue:
            continue
        return QuestionPlan(
            clauses=(normalized,),
            unresolved_parts=(f"unresolved_question_clause:{_clean(residue)}",),
            parse_trace=("fail_closed:recognized_prefix_residue",),
        )
    return None


def _safe_coverage_gap(value: str) -> bool:
    residue = re.sub(
        r"\b(?:and\s+also|while\s+also|as\s+well\s+as|along\s+with|"
        r"and|but|plus|then|also|и\s+также|а\s+также|и|но|плюс|затем)\b",
        "",
        value,
        flags=re.I,
    )
    residue = re.sub(r"[\s,;:.!?/\u2013\u2014]+", "", residue)
    return not residue


def _finalize_full_span_coverage(question: str, plan: QuestionPlan) -> QuestionPlan:
    """Fail closed unless every non-separator source span was consumed."""

    if not plan.facets or plan.unresolved_parts:
        return plan
    spans = sorted(set(plan.consumed_spans))
    if not spans:
        return replace(
            plan,
            unresolved_parts=("unresolved_question_clause:missing_consumed_span",),
            parse_trace=(*plan.parse_trace, "fail_closed:missing_consumed_span"),
        )

    cursor = 0
    gaps: list[str] = []
    for start, end in spans:
        if start < cursor or start < 0 or end <= start or end > len(question):
            gaps.append("invalid_consumed_span")
            continue
        gap = question[cursor:start]
        if gap and not _safe_coverage_gap(gap):
            gaps.append(_clean(gap))
        cursor = end
    tail = question[cursor:]
    if tail and not _safe_coverage_gap(tail):
        gaps.append(_clean(tail))
    if not gaps:
        return plan
    return replace(
        plan,
        unresolved_parts=tuple(dict.fromkeys(
            f"unresolved_question_clause:{gap}" for gap in gaps if gap
        )),
        parse_trace=(*plan.parse_trace, "fail_closed:unconsumed_span"),
    )


def _compile_question_plan_core(raw: str) -> QuestionPlan:
    normalized = " ".join(raw.split())
    whole_clause = QuestionClause(raw, 0, len(raw)) if raw else None
    if whole_clause is not None:
        full_span = _reusable_frame_plan(_normalized_clause(whole_clause))
        if full_span is not None and any(
            row in {
                "frame:decision_for_action", "frame:argument_value",
                "frame:applicable_contract", "frame:purpose_behavior",
                "frame:behavior_before",
            }
            for row in full_span.parse_trace
        ):
            return _finalize_full_span_coverage(
                raw, _bind_plan_to_clause(full_span, whole_clause),
            )
    clauses = split_question_clause_spans(raw)
    if not clauses:
        return QuestionPlan()
    if len(clauses) > 1:
        compound = _combine_clause_plans(raw, clauses)
        if compound is not None:
            return _finalize_full_span_coverage(raw, compound)
        residue = _recognized_prefix_residue_plan(normalized)
        if residue is not None:
            return residue
        return QuestionPlan()
    clause = clauses[0]
    norm_clause = _normalized_clause(clause)
    atomic = _compile_atomic_question(norm_clause)
    if atomic is not None:
        # A generic run/verify rule takes an arbitrary subject and could
        # swallow a strict extension of an owned specific frame.
        if any(row.startswith(("run:", "verify:")) for row in atomic.parse_trace):
            residue = _recognized_prefix_residue_plan(norm_clause)
            if residue is not None:
                return residue
        return _finalize_full_span_coverage(
            raw,
            _bind_plan_to_clause(atomic, clause),
        )
    residue = _recognized_prefix_residue_plan(norm_clause)
    if residue is not None:
        return residue
    return QuestionPlan()


def compile_question_plan(question: str) -> QuestionPlan:
    raw = str(question or "")[:4000]
    surface = normalize_question_surface(raw)
    if surface is not None:
        normalized_plan = _compile_question_plan_core(surface.text)
        if normalized_plan.handled:
            return _guard_plan_subjects(rebind_surface_plan(
                normalized_plan,
                raw=raw,
                rule=surface.rule,
                finalize=_finalize_full_span_coverage,
            ))
    return _compile_question_plan_core(raw)


__all__ = ["PlannedFacet", "QuestionPlan", "compile_question_plan"]
