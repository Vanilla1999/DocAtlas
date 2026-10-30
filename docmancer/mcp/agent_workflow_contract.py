"""Runtime-derived identity for the default three-tool Docs MCP agent workflow."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface

CONTRACT_SCHEMA = "docatlas-agent-contract-v1"
PUBLIC_TOOL_ORDER = ("get_docs_context", "prepare_docs", "docs_status")

WORKFLOW_POLICY: dict[str, Any] = {
    "retrieval_only_answer": {
        "synthesize_from_returned_snippets": True,
        "false_answer_flags_mean": "no_server_certification",
        "retrieval_full_proves_semantic_completeness": False,
        "cite_returned_context": True,
        "context_is_answer_proof": False,
        "lookup_coverage_transfers_to_original": False,
        "source_link_requires_read": False,
        "false_or_unverified_flags_require_read": False,
        "continuation_requires": "explicit_lookup_or_issued_bounded_source_read",
        "repeat_same_source_span": False,
        "authorizes_edit": False,
        "mutation_requires_separate_explicit_target_and_authorization": True,
    },
    "first_call": {
        "tool": "get_docs_context",
        "for": ["documentation_question", "coding_task", "patch_task"],
        "before_first_edit": True,
        "max_calls_before_first_edit": 1,
        "target_binding": "host_bound_current_project_or_known_absolute_project_path_or_explicit_registered_library",
        "bound_project_default_scope": "all",
        "conflicting_project_path": "typed_error_no_retargeting",
        "missing_target": "typed_validation_error_correct_binding_before_retry",
        "implicit_mcp_process_cwd_is_target": False,
        "call_limit_scope": "per_concrete_question_and_evidence_scope",
        "coding_context_format": None,
        "documentation_context_format": None,
        "context_format_inferred_from_prose": False,
        "skill_read_required": False,
        "tool_catalog_reload_required": False,
        "optional_preflight": "language mode enabled + bound language unknown: docs_status(action=project or library, include_language=true) BEFORE retrieval",
        "selection_or_unassessed_coverage_requires_retry": False,
    },
    "advanced_patch": {
        "default_available": False,
        "startup_setting": "DOCATLAS_MCP_ADVANCED_TOOLS=1",
        "context_format": "patch_context",
        "patch_evidence_representation_cap": None,
        "authorizes_edit": False,
    },
    "prepare_docs": {
        "tool": "prepare_docs",
        "allowed_when": ["recommended_next_action", "explicit_lifecycle_request"],
        "speculative": False,
        "project_discovery": "host_bound_project_explicit_confirm_only_private_atomic_manifest_and_index",
        "discovery_in_query": False,
    },
    "docs_status": {
        "tool": "docs_status",
        "allowed_when": ["explicit_status_request", "recommended_next_action", "returned_job_id", "declared_language_preflight_for_bound_source"],
        "discovery": False,
    },
    "scope_planning": {
        "explicit_scope_is_authoritative": True,
        "module_path_implies_scope": "module",
        "all_requires_no_module_filter": True,
        "never_widen_project_to_all": True,
        "all_is_repository_local": True,
    },
    "free_form_lookup": {
        "explicit_lookup_queries_only": True,
        "maximum_lookup_queries": 5,
        "original_question_unchanged": True,
        "search_question": "explicit_full_translation_in_declared_documentation_language",
        "search_question_counts_as_lookup": True,
        "section_scorer_uses_explicit_search_question": True,
        "preserve_exact_technical_anchors": True,
        "preserve_conditions_negation_and_comparison_sides": True,
        "expected_answer_in_lookup_allowed": False,
        "guessed_source_names_in_lookup_allowed": False,
        "independent_questions_use_separate_calls": True,
        "lookup_queries_must_refine_same_question": True,
        "meta_request_must_not_replace_concrete_question": True,
        "answer_only_from_returned_sources": True,
        "partial_coverage_is_not_completeness": True,
        "authorizes_answer_or_edit": False,
        "inferred_semantic_equivalence": False,
    },
    "gap_resolution": {
        "continuation_requires": "explicit_lookup_or_issued_bounded_source_read",
        "root_question_immutable": True,
        "inferred_subquestions": False,
        "scope_and_budget_limits_unchanged": True,
        "missing_fact_required": True,
        "unchanged_input_and_state_requires_retry": False,
    },
    "version_binding": {
        "project_query_default": "resolve_current_project_version",
        "explicit_version": "explicit_exact_or_historical_request",
        "after_lockfile_change": "requery_current_project_do_not_reuse_previous_context",
        "cached_previous_version_is_current_evidence": False,
    },
    "recovery": {
        "after_prepare": "retry_original_get_docs_context_unchanged",
        "retry_after_prepare_requires": "terminal_success",
        "after_prepare_job_id": "poll_docs_status",
        "after_prepare_failure": "inspect_failure_no_automatic_retry",
        "rephrase_retry_limit": 1,
        "rephrase_auto_execute": False,
        "hard_stop_false_authorizes_edit": False,
        "documentation_claim_requires_cited_context": True,
        "stop_before_edit_when": "hard_stop",
    },
    "transport_delivery": {
        "client_truncation_means_missing_docs": False,
        "follow_returned_actionable_recovery": True,
        "retry_requires_changed_input_or_delivery_state": True,
        "preparation_or_scope_widening_is_delivery_recovery": False,
        "automatic_full_saved_output_dump": False,
        "client_artifact_read_requires": "issued_artifact_and_bounded_missing_fact",
        "forensic_recovery_is_normal_delivery": False,
        "server_partial_status_proves_client_truncation": False,
    },
}

PUBLIC_EXAMPLES: tuple[dict[str, Any], ...] = (
    {
        "id": "repository-first-call",
        "tool": "get_docs_context",
        "condition": "normal documentation question on a host-bound project (omitted format retains docs mode)",
        "arguments": {
            "question": "How is authentication configured?",
        },
    },
    {
        "id": "coding-first-call",
        "tool": "get_docs_context",
        "condition": "coding or patch task on a host-bound project before first edit; representation is not authorization",
        "arguments": {
            "question": "Which documented constraints apply to changing authentication?",
        },
    },
    {
        "id": "repository-overview",
        "tool": "get_docs_context",
        "condition": "caller explicitly requests repository-local all scope",
        "arguments": {
            "question": "Explain this repository's architecture and module responsibilities.",
            "project_path": "/repo",
            "scope": "all",
        },
    },
    {
        "id": "repository-policy",
        "tool": "get_docs_context",
        "condition": "caller explicitly requests project scope",
        "arguments": {
            "question": "What are the repository-wide contribution rules?",
            "project_path": "/repo",
            "scope": "project",
        },
    },
    {
        "id": "known-module",
        "tool": "get_docs_context",
        "condition": "caller supplies an exact discovered module path",
        "arguments": {
            "question": "How does the orders module handle retries?",
            "project_path": "/repo",
            "scope": "module",
            "module_path": "packages/orders",
        },
    },
    {
        "id": "explicit-single-question-lookup",
        "tool": "get_docs_context",
        "condition": "caller explicitly supplies a lookup for the same question",
        "arguments": {
            "question": "Как проверить актуальность индекса?",
            "project_path": "/repo",
            "scope": "project",
            "lookup_queries": [
                "актуальность индекса",
            ],
        },
    },
    {
        "id": "returned-preparation",
        "tool": "prepare_docs",
        "condition": "host-bound project; only after a returned action or explicit lifecycle request AND confirmation",
        "arguments": {
            "action": "discover_project_docs",
            "confirm": True,
        },
    },
    {
        "id": "explicit-status",
        "tool": "docs_status",
        "condition": "only for explicit status/health or returned recovery",
        "arguments": {
            "action": "project",
            "project_path": "/repo",
        },
    },
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def runtime_public_tool_dicts() -> tuple[dict[str, Any], ...]:
    surface = build_docs_surface(DocsServerConfig())
    tools = tuple(spec.to_tool_dict() for spec in surface.tools)
    names = tuple(tool["name"] for tool in tools)
    if names != PUBLIC_TOOL_ORDER:
        raise RuntimeError(
            f"public Docs MCP tool order drifted: expected {PUBLIC_TOOL_ORDER!r}, got {names!r}"
        )
    return deepcopy(tools)


def public_agent_contract() -> dict[str, Any]:
    tool_records: list[dict[str, Any]] = []
    for tool in runtime_public_tool_dicts():
        tool_records.append(
            {
                "name": tool["name"],
                "description_sha256": _sha256(tool["description"]),
                "input_schema_sha256": _sha256(tool["inputSchema"]),
                "output_schema_sha256": _sha256(tool.get("outputSchema")),
                "tool_contract_sha256": _sha256(tool),
            }
        )

    payload: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "workflow": deepcopy(WORKFLOW_POLICY),
        "examples": deepcopy(list(PUBLIC_EXAMPLES)),
        "tools": tool_records,
    }
    payload["identity"] = f"sha256:{_sha256(payload)}"
    return payload


def public_agent_contract_identity() -> str:
    return str(public_agent_contract()["identity"])


__all__ = [
    "CONTRACT_SCHEMA",
    "PUBLIC_EXAMPLES",
    "PUBLIC_TOOL_ORDER",
    "WORKFLOW_POLICY",
    "public_agent_contract",
    "public_agent_contract_identity",
    "runtime_public_tool_dicts",
]
