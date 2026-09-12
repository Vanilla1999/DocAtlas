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
        "preserve_supported_partial_answer": True,
        "name_concrete_missing_facts": True,
        "source_link_requires_read": False,
        "false_or_unverified_flags_require_read": False,
        "continuation_requires": "concrete_missing_fact_and_available_bounded_reader",
        "stop_when_sufficient": True,
        "repeat_same_source_span": False,
        "authorizes_edit": False,
    },
    "first_call": {
        "tool": "get_docs_context",
        "for": ["documentation_question", "coding_task", "patch_task"],
        "before_first_edit": True,
        "max_calls_before_first_edit": 1,
    },
    "prepare_docs": {
        "tool": "prepare_docs",
        "allowed_when": ["recommended_next_action", "explicit_lifecycle_request"],
        "speculative": False,
    },
    "docs_status": {
        "tool": "docs_status",
        "allowed_when": ["explicit_status_request", "recommended_next_action"],
        "discovery": False,
    },
    "scope_planning": {
        "explicit_scope_is_authoritative": True,
        "repository_overview_scope": "all",
        "repo_level_policy_scope": "project",
        "known_module_scope": "module",
        "cross_module_scope": "all",
        "module_path_implies_scope": "module",
        "all_requires_no_module_filter": True,
        "mixed_module_and_project_prefer_two_calls": True,
        "never_widen_project_to_all": True,
        "all_is_repository_local": True,
    },
    "free_form_lookup": {
        "host_formulates_lookup_queries": True,
        "one_concept_per_lookup": True,
        "maximum_lookup_queries": 5,
        "original_question_unchanged": True,
        "preserve_exact_technical_anchors": True,
        "compound_or_cross_language_decomposition_required": True,
        "independent_questions_use_separate_calls": True,
        "lookup_queries_must_refine_same_question": True,
        "meta_request_must_not_replace_concrete_question": True,
        "answer_only_from_returned_sources": True,
        "partial_coverage_is_not_completeness": True,
        "authorizes_answer_or_edit": False,
    },
    "recovery": {
        "after_prepare": "retry_original_get_docs_context_unchanged",
        "rephrase_retry_limit": 1,
        "rephrase_auto_execute": False,
        "investigation_allowed_when_hard_stop_false": True,
        "source_search_after_rephrase_exhausted": True,
        "documentation_claim_requires_support": True,
        "stop_before_edit_when": "hard_stop",
    },
}

PUBLIC_EXAMPLES: tuple[dict[str, Any], ...] = (
    {
        "id": "repository-first-call",
        "tool": "get_docs_context",
        "condition": "normal documentation/coding question",
        "arguments": {
            "question": "How is authentication configured?",
            "project_path": "/repo",
        },
    },
    {
        "id": "repository-overview",
        "tool": "get_docs_context",
        "condition": "repository onboarding or architecture overview; no explicit narrower scope",
        "arguments": {
            "question": "Explain this repository's architecture and module responsibilities.",
            "project_path": "/repo",
            "scope": "all",
        },
    },
    {
        "id": "repository-policy",
        "tool": "get_docs_context",
        "condition": "repository-level policy only",
        "arguments": {
            "question": "What are the repository-wide contribution rules?",
            "project_path": "/repo",
            "scope": "project",
        },
    },
    {
        "id": "known-module",
        "tool": "get_docs_context",
        "condition": "one module identified by an exact discovered path",
        "arguments": {
            "question": "How does the orders module handle retries?",
            "project_path": "/repo",
            "scope": "module",
            "module_path": "packages/orders",
        },
    },
    {
        "id": "cross-language-single-question",
        "tool": "get_docs_context",
        "condition": "one user question needs same-question lookups in the documentation language",
        "arguments": {
            "question": "Как проверить актуальность индекса после изменения документации?",
            "project_path": "/repo",
            "scope": "project",
            "lookup_queries": [
                "check project documentation index freshness after editing files",
                "sync project docs after file changes",
            ],
        },
    },
    {
        "id": "returned-preparation",
        "tool": "prepare_docs",
        "condition": "only after recommended_next_action or explicit lifecycle request",
        "arguments": {
            "action": "sync_project_docs",
            "project_path": "/repo",
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
