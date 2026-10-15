"""Legacy QuestionPlan facade without natural-language semantic inference.

Caller-supplied PlannedFacet/QuestionPlan DTOs remain available. Untyped question
text is unresolved: quoted identifiers are retrieval literals, not evidence of a
requested relation, expected answer, exhaustive inventory, or API invocation.
"""
from __future__ import annotations

from dataclasses import replace
import re

from docmancer.docs.domain.question_component_rewrite import rewrite_component
from docmancer.docs.domain.question_frame_core import (
    QuestionClause, ambiguous_frame_reason, match_action_frame,
    match_inventory_frame, match_requirements_frame, split_question_clause_spans,
)
from docmancer.docs.domain.question_semantic_frames import (
    match_argument_value_frame, match_before_behavior_frame, match_comparison_frame,
    match_condition_frame, match_contract_scope_frame, match_decision_frame,
    match_location_frame, match_premise_frame, match_purpose_behavior_frame,
)
from docmancer.docs.domain.question_surface_normalization import (
    normalize_question_surface, rebind_surface_plan,
)
from docmancer.docs.domain.technical_terms import TechnicalTermKind
from docmancer.docs.domain.query_terms import documentation_technical_anchors, query_constraint_roles
from docmancer.docs.domain.question_plan_core import (
    PlanKind, PlannedFacet, QuestionPlan, Rule, _bind_plan_to_clause,
    _bind_whole_plan, _clean, _normalized_clause, _safe_coverage_gap,
    _finalize_full_span_coverage, _technical, _unsafe_free_text,
)
from docmancer.docs.domain.question_retrieval_needs import RetrievalNeed, retrieval_needs
from docmancer.docs.domain.question_plan_command_rules import (
    _command_sync, _docs_mcp_server_command, _offline_suite_run, _two_cell_cardinality,
)
from docmancer.docs.domain.question_plan_surface_rules import (
    governance_facets, mcp_request_handling, provider_request_timeout,
    public_tool_usage, public_tools_with_purposes, python_version_support, semantic_components,
)

# Compatibility entry points remain callable but no longer recognize prose.
# No vocabulary is relocated to another producer or normalization adapter.
def _release_docs_line_limit(q: str) -> QuestionPlan | None:
    return None


def _storage_coordination_contract(q: str) -> QuestionPlan | None:
    return None


def _remove_library_during_refresh(q: str) -> QuestionPlan | None:
    return None


def _source_type_inventory(q: str) -> QuestionPlan | None:
    return None


def _release_checklist_compound(q: str) -> QuestionPlan | None:
    return None


def _token_bounding_compound(q: str) -> QuestionPlan | None:
    return None


def _public_tools_with_usage(q: str) -> QuestionPlan | None:
    return None


def _env_var_purpose_usage(q: str) -> QuestionPlan | None:
    return None


def _conditional_clear_index(q: str) -> QuestionPlan | None:
    return None


def _configuration_workflow(q: str) -> QuestionPlan | None:
    return None


def _contamination_definition(q: str) -> QuestionPlan | None:
    return None


def _v4_protocol_run(q: str) -> QuestionPlan | None:
    return None


def _named_run_or_verify(q: str) -> QuestionPlan | None:
    return None


def _named_behavior(q: str) -> QuestionPlan | None:
    return None


def _two_cell_smoke(q: str) -> QuestionPlan | None:
    return None


def _test_markers_and_offline_suite(q: str) -> QuestionPlan | None:
    return None


def _semantic_comparison(q: str) -> QuestionPlan | None:
    return None


def _semantic_location(q: str) -> QuestionPlan | None:
    return None


def _semantic_condition(q: str) -> QuestionPlan | None:
    return None


def _semantic_premise(q: str) -> QuestionPlan | None:
    return None


_SPECIFIC_RULES: tuple[Rule, ...] = ()
_GENERIC_RULES: tuple[Rule, ...] = ()


def _reusable_frame_plan(q: str) -> QuestionPlan | None:
    return None


def _normal_subject(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _guard_plan_subjects(plan: QuestionPlan) -> QuestionPlan:
    # Explicit DTOs are not interpreted or rewritten by this legacy facade.
    return plan


def _compile_specific_question(q: str) -> QuestionPlan | None:
    return None


def _compile_generic_question(q: str) -> QuestionPlan | None:
    return None


def _compile_atomic_question(q: str) -> QuestionPlan | None:
    return None


def _unresolved_compound(clauses: tuple[str, ...], *, trace: str) -> QuestionPlan:
    return QuestionPlan(
        clauses=clauses,
        unresolved_parts=tuple(f"unresolved_question_clause:{clause}" for clause in clauses),
        parse_trace=(trace,), component_scope_complete=False,
    )


def _combine_clause_plans(
    question: str,
    clauses: tuple[QuestionClause, ...],
) -> QuestionPlan | None:
    return None


def _prefix_plan_is_owned(plan: QuestionPlan) -> bool:
    return False


def _recognized_prefix_residue_plan(q: str) -> QuestionPlan | None:
    return None


def _compile_question_plan_core(raw: str) -> QuestionPlan:
    return QuestionPlan(
        clauses=(raw,),
        unresolved_parts=("unresolved_question_semantics",),
        parse_trace=("fail_closed:untyped_question",),
        component_scope_complete=False,
    )


def compile_question_plan(question: str) -> QuestionPlan:
    # Preserve the existing public input ceiling and the original Unicode text
    # within it. Do not normalize, split, translate, or synthesize subjects.
    raw = str(question or "")[:4000]
    return _compile_question_plan_core(raw)


__all__ = ["PlannedFacet", "QuestionPlan", "RetrievalNeed", "retrieval_needs", "compile_question_plan"]
