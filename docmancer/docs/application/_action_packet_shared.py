from __future__ import annotations

import hashlib
import json
import math
import os
import re
import types
from dataclasses import MISSING, asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Union, get_args, get_origin, get_type_hints

from docmancer.docs.application.evidence_selection import (
    EvidenceRequirementSet, SelectionDecision, build_requirements, normalize_candidates,
    patch_selection_config, requirement_value_visible, select_evidence,
)
from docmancer.docs.application.evidence_models import EvidenceAssignment, EvidenceRequirement
from docmancer.docs.application.evidence_requirements import (
    _ALLOWED_REQUIREMENT_PROVENANCE, build_patch_evidence_requirements,
)
from docmancer.docs.domain.mutation_intent import MutationIntentContract

ACTION_PACKET_SCHEMA_VERSION = 4
_CODE_SOURCE_CLASSES = {"repo_map", "source_evidence", "code_graph"}
_SYMBOL_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:(?:\.|::|#)[A-Za-z_][A-Za-z0-9_]*)*")


def serialize_action_packet(value: Any) -> str:
    """Canonical wire serialization, including final projection metadata."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def estimate_action_packet_tokens(value: Any) -> int:
    return max(1, math.ceil(len(serialize_action_packet(value).encode("utf-8")) / 4))


def refresh_action_packet_estimate(packet: dict[str, Any]) -> None:
    """Refresh in place to the fixed point including the estimate itself."""
    packet["estimated_tokens"] = 1
    while True:
        actual = estimate_action_packet_tokens(packet)
        if actual == packet["estimated_tokens"]:
            return
        packet["estimated_tokens"] = actual


def _compact_value(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: _compact_value(item) for key, item in value.items()
                if item is not None and item != "" and item != [] and item != () and item != {}}
    if isinstance(value, (tuple, list)):
        return [_compact_value(item) for item in value]
    return value


def _type_schema(annotation: Any) -> dict[str, Any]:
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        return {"enum": list(args)}
    if origin in (types.UnionType, Union):
        return {"anyOf": [_type_schema(arg) for arg in args if arg is not type(None)]}
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return {"type": "array", "minItems": 1, "items": _type_schema(args[0])}
        return {"type": "array", "minItems": len(args), "maxItems": len(args),
                "prefixItems": [_type_schema(arg) for arg in args]}
    if is_dataclass(annotation):
        hints = get_type_hints(annotation)
        properties = {field.name: _type_schema(hints[field.name]) for field in fields(annotation)}
        required = [field.name for field in fields(annotation)
                    if (field.default is MISSING and type(None) not in get_args(hints[field.name])
                        and get_origin(hints[field.name]) is not tuple)
                    or (field.default is not MISSING and field.default not in (None, "", (), []))]
        return {"type": "object", "additionalProperties": False,
                "required": required, "properties": properties}
    return {"type": {str: "string", int: "integer", bool: "boolean", float: "number"}[annotation],
            **({"minLength": 1} if annotation is str else {})}


_SOURCE_PROPERTIES = {
    key: {"type": "string", "minLength": 1} for key in (
        "evidence_id", "stable_id", "path", "symbol_or_section", "scope", "version_binding", "text",
    )
}
_SOURCE_PROPERTIES.update({
    "evidence_id": {"type": "string", "pattern": "^ev-[0-9a-f]{16}$"},
    "authority": {"enum": ["canonical", "supporting"]},
    "instruction_trust": {"const": "untrusted_data"},
    "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
})
_SOURCE_REQUIRED = list(_SOURCE_PROPERTIES)
_SOURCE_PROPERTIES.update({key: {"type": "integer", "minimum": 0}
                           for key in ("char_start", "char_end", "line_start", "line_end")})
_MUTATION_SCHEMA = _type_schema(MutationIntentContract)
_MUTATION_SCHEMA["properties"]["contract_hash"] = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_MUTATION_SCHEMA["required"].append("contract_hash")
_PLAN_SCHEMA = _MUTATION_SCHEMA["properties"]["request_plan"]["anyOf"][0]
_PLAN_SCHEMA["properties"]["plan_hash"] = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_PLAN_SCHEMA["required"].append("plan_hash")
_REQUIREMENT_SCHEMA = _type_schema(EvidenceRequirement)
_REQUIREMENT_SCHEMA["properties"]["public_provenance"] = {
    "enum": sorted(_ALLOWED_REQUIREMENT_PROVENANCE),
}
ACTION_PACKET_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "result", "completeness", "edit_ready", "estimated_tokens"],
    "properties": {
        "schema_version": {"const": 4, "type": "integer"}, "result": {"enum": ["data", "failure"]},
        "completeness": {"enum": ["complete", "partial", "unavailable"]},
        "edit_ready": {"const": False}, "estimated_tokens": {"type": "integer", "minimum": 1},
        "sources": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "required": _SOURCE_REQUIRED, "properties": _SOURCE_PROPERTIES,
        }},
        "requirements": {"type": "array", "minItems": 1, "items": _REQUIREMENT_SCHEMA},
        "assignments": {"type": "array", "minItems": 1, "items": _type_schema(EvidenceAssignment)},
        "missing": {"type": "array", "minItems": 1, "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1}},
        "mutation_intent": _MUTATION_SCHEMA,
    },
    "allOf": [
        {"if": {"properties": {"result": {"const": "data"}}},
         "then": {"required": ["sources"], "properties": {"completeness": {"enum": ["complete", "partial"]}}}},
        {"if": {"properties": {"result": {"const": "failure"}}},
         "then": {"required": ["missing"], "properties": {"completeness": {"const": "unavailable"}},
                  "not": {"anyOf": [{"required": ["sources"]}, {"required": ["assignments"]}]}}},
        {"if": {"properties": {"completeness": {"const": "partial"}}}, "then": {"required": ["missing"]}},
        {"if": {"properties": {"completeness": {"const": "complete"}}}, "then": {"not": {"required": ["missing"]}}},
    ],
}

__all__ = [name for name in globals() if not name.startswith("__")]
