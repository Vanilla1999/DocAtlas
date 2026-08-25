from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from docmancer.docs.application.evidence_selection import (
    EvidenceRequirementSet,
    SelectionDecision,
    build_requirements,
    normalize_candidates,
    patch_selection_config,
    requirement_value_visible,
    select_evidence,
)
from docmancer.docs.application.evidence_requirements import build_patch_evidence_requirements
from docmancer.docs.domain.normative_language import (
    classify_normative_modality,
    python_declaration_line_indexes,
)
from docmancer.docs.domain.mutation_intent import (
    MutationIntentContract,
    build_mutation_intent,
    evaluate_mutation_readiness,
    resolve_mutation_targets,
    with_explicit_path_targets,
)
from docmancer.docs.domain.patch_requirements import build_patch_requirements
from docmancer.docs.domain.request_intent import is_change_request


ACTION_PACKET_SCHEMA_VERSION = 3
DEFAULT_ACTION_PACKET_TOKENS = 1_500
HARD_ACTION_PACKET_TOKENS = 2_000
MIN_ACTION_PACKET_TOKENS = 128

_VALIDATION_START_RE = re.compile(
    r"^(?:run\s+)?(?:python\s+-m\s+(?:pytest|unittest|compileall)|pytest|"
    r"uv\s+run(?:\s+--offline)?\s+(?:pytest|ruff|mypy|python\s+-m\s+(?:pytest|unittest|compileall))|"
    r"npm\s+(?:test|run\s+[A-Za-z0-9_.:-]+)|pnpm\s+(?:test|run\s+[A-Za-z0-9_.:-]+)|"
    r"yarn\s+(?:test|run\s+[A-Za-z0-9_.:-]+|build)|cargo\s+(?:test|check|build)|"
    r"go\s+(?:test|build|vet)|(?:\./)?gradlew?|flutter\s+test|dart\s+(?:test|analyze)|"
    r"make(?:\s+[A-Za-z0-9_.:-]+)?|ruff|mypy|tsc|dotnet\s+(?:test|build)|"
    r"mvn\s+(?:test|package)|swift\s+test)(?:\s+[A-Za-z0-9_./:=,@+%\-]+)*\.?$",
    re.I,
)
_UNSAFE_COMMAND_RE = re.compile(r"(?:[;&|<>`]|\$\(|\n|\r)")
_SYMBOL_RE = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:(?:\.|::|#)[A-Za-z_][A-Za-z0-9_]*)*"
)
_CODE_SOURCE_CLASSES = {"repo_map", "source_evidence", "code_graph"}
_MAX_SOURCE_PATH = 500
_MAX_SOURCE_SECTION = 300
_DANGEROUS_CONTENT_PATTERNS = (
    (
        "credential_exfiltration_instruction",
        re.compile(
            r"\b(?:(?:must|should)\s+(?!not\b)|(?:please|need\s+to|required\s+to)\s+)"
            r"(?:[a-z]+\s+){0,4}(?:upload|send|post|transmit|share|paste|provide)\b"
            r".{0,120}\b(?:credentials?|tokens?|secrets?|passwords?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "network_tool_instruction",
        re.compile(r"\b(?:run|execute|invoke)\s+(?:curl|wget|ssh|scp|nc)\b", re.IGNORECASE),
    ),
    (
        "remote_instruction",
        re.compile(
            r"\b(?:must|should|please|visit|open|fetch|download|upload)\b.{0,100}https?://",
            re.IGNORECASE,
        ),
    ),
    (
        "instruction_override",
        re.compile(
            r"\b(?:ignore|disregard|override)\b.{0,80}"
            r"\b(?:previous|prior|system|developer|agent)\s+(?:instructions?|messages?|rules?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt_disclosure",
        re.compile(
            r"\b(?:reveal|show|print|expose|disclose)\b.{0,80}"
            r"\b(?:system|developer)\s+(?:prompt|message|instructions?)\b",
            re.IGNORECASE,
        ),
    ),
)


def _non_empty_string_schema(*, max_length: int | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "minLength": 1}
    if max_length is not None:
        schema["maxLength"] = max_length
    return schema


def _cited_item_schema(value_key: str) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [value_key, "evidence_ids"],
        "properties": {
            value_key: _non_empty_string_schema(),
            "evidence_ids": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "pattern": r"^ev-[0-9a-f]{16}$"},
            },
        },
    }


def _request_constraint_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "text", "provenance", "request_plan_hash",
            "query_span_start", "query_span_end",
        ],
        "properties": {
            "text": _non_empty_string_schema(max_length=500),
            "provenance": {"const": "user_request"},
            "request_plan_hash": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
            "query_span_start": {"type": "integer", "minimum": 0},
            "query_span_end": {"type": "integer", "minimum": 1},
        },
    }


ACTION_PACKET_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version", "status", "task_interpretation", "source_of_truth", "target_surface",
        "required_invariants", "forbidden_changes", "implementation_guidance", "validation",
        "mutation_intent", "uncertainties", "missing_evidence", "omitted_counts", "estimated_tokens",
    ],
    "properties": {
        "schema_version": {"const": ACTION_PACKET_SCHEMA_VERSION},
        "status": {"enum": ["ok", "truncated", "insufficient_evidence"]},
        "task_interpretation": {
            "type": "object",
            "additionalProperties": False,
            "required": ["objective", "acceptance_conditions"],
            "properties": {
                "objective": _non_empty_string_schema(max_length=1_000),
                "acceptance_conditions": {"type": "array", "items": _cited_item_schema("text")},
            },
        },
        "source_of_truth": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "path", "symbol_or_section", "authority", "instruction_trust",
                    "scope", "version_binding", "evidence_id",
                ],
                "properties": {
                    "path": _non_empty_string_schema(max_length=_MAX_SOURCE_PATH),
                    "symbol_or_section": _non_empty_string_schema(max_length=_MAX_SOURCE_SECTION),
                    "authority": {"enum": ["canonical", "supporting"]},
                    "instruction_trust": {"enum": ["scoped_agent_policy", "untrusted_data"]},
                    "scope": _non_empty_string_schema(max_length=_MAX_SOURCE_SECTION),
                    "version_binding": _non_empty_string_schema(max_length=100),
                    "evidence_id": {"type": "string", "pattern": r"^ev-[0-9a-f]{16}$"},
                },
            },
        },
        "target_surface": {
            "type": "object",
            "additionalProperties": False,
            "required": ["likely_files", "symbols"],
            "properties": {
                "likely_files": {"type": "array", "items": _cited_item_schema("path")},
                "symbols": {"type": "array", "items": _cited_item_schema("name")},
            },
        },
        "required_invariants": {"type": "array", "items": _cited_item_schema("text")},
        "forbidden_changes": {
            "type": "array",
            "items": {"oneOf": [_cited_item_schema("text"), _request_constraint_schema()]},
        },
        "implementation_guidance": {"type": "array", "items": _cited_item_schema("text")},
        "validation": {
            "type": "object",
            "additionalProperties": False,
            "required": ["compile", "tests", "semantic_checks"],
            "properties": {
                "compile": {"type": "array", "items": _cited_item_schema("text")},
                "tests": {"type": "array", "items": _cited_item_schema("text")},
                "semantic_checks": {"type": "array", "items": _cited_item_schema("text")},
            },
        },
        "mutation_intent": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "operation", "artifact_kind", "requested_targets", "resolved_targets", "preserved_targets",
                "destination", "acceptance_conditions", "request_plan", "ready", "constraints_only",
                "missing", "contract_hash",
            ],
            "properties": {
                "operation": {"enum": ["none", "modify", "create", "delete", "rename"]},
                "artifact_kind": {"enum": ["source", "docs", "config", "test", "generated_answer", "unknown"]},
                "requested_targets": {"type": "array", "maxItems": 12, "items": {"type": "object"}},
                "resolved_targets": {"type": "array", "maxItems": 12, "items": {"type": "object"}},
                "preserved_targets": {"type": "array", "maxItems": 12, "items": {"type": "object"}},
                "destination": {"type": ["string", "null"], "maxLength": 500},
                "acceptance_conditions": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 500}},
                "request_plan": {
                    "type": ["object", "null"],
                },
                "ready": {"type": "boolean"},
                "constraints_only": {"type": "boolean"},
                "missing": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 120}},
                "contract_hash": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
            },
        },
        "uncertainties": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "path", "symbol_or_section"],
                "properties": {
                    "type": {"const": "authority_conflict"},
                    "path": _non_empty_string_schema(max_length=_MAX_SOURCE_PATH),
                    "symbol_or_section": _non_empty_string_schema(max_length=_MAX_SOURCE_SECTION),
                },
            },
        },
        "missing_evidence": {
            "type": "array",
            "items": _non_empty_string_schema(max_length=300),
        },
        "omitted_counts": {
            "type": "object",
            "additionalProperties": {"type": "integer", "minimum": 1},
        },
        "estimated_tokens": {"type": "integer", "minimum": 1, "maximum": HARD_ACTION_PACKET_TOKENS},
    },
    "allOf": [
        {
            "if": {"properties": {"status": {"const": "ok"}}},
            "then": {
                "properties": {
                    "source_of_truth": {"minItems": 1},
                    "uncertainties": {"maxItems": 0},
                    "missing_evidence": {"maxItems": 0},
                    "omitted_counts": {"maxProperties": 0},
                },
            },
        },
        {
            "if": {"properties": {"status": {"const": "truncated"}}},
            "then": {"properties": {"omitted_counts": {"minProperties": 1}}},
        },
        {
            "if": {"properties": {"status": {"const": "insufficient_evidence"}}},
            "then": {"properties": {"missing_evidence": {"minItems": 1}}},
        },
    ],
}

__all__=[n for n in globals() if not n.startswith('__')]
