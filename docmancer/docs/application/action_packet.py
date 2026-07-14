from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable


ACTION_PACKET_SCHEMA_VERSION = 1
DEFAULT_ACTION_PACKET_TOKENS = 1_500
HARD_ACTION_PACKET_TOKENS = 2_000
MIN_ACTION_PACKET_TOKENS = 128

_FORBIDDEN_RE = re.compile(r"\b(must\s+not|do\s+not|don't|never|forbidden|prohibited)\b", re.I)
_REQUIRED_RE = re.compile(r"\b(must|required|requires|shall|invariant)\b", re.I)
_NOT_REQUIRED_RE = re.compile(r"\b(?:not|required\s+not\s+to)\s+required\b", re.I)
_VALIDATION_START_RE = re.compile(
    r"^(?:run\s+)?(?:python\s+-m\s+(?:pytest|unittest|compileall)|pytest|"
    r"uv\s+run\s+(?:pytest|ruff|mypy|python\s+-m\s+(?:pytest|unittest|compileall))|"
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


ACTION_PACKET_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version", "status", "task_interpretation", "source_of_truth", "target_surface",
        "required_invariants", "forbidden_changes", "implementation_guidance", "validation",
        "uncertainties", "missing_evidence", "omitted_counts", "estimated_tokens",
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
        "forbidden_changes": {"type": "array", "items": _cited_item_schema("text")},
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


def estimate_action_packet_tokens(value: Any) -> int:
    """Estimate tokens deterministically as ceil(serialized UTF-8 bytes / 4)."""

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return max(1, math.ceil(len(encoded) / 4))


def build_action_packet(
    *,
    question: str,
    context_pack: Iterable[dict[str, Any]],
    trust_contract: dict[str, Any] | None = None,
    max_tokens: int = DEFAULT_ACTION_PACKET_TOKENS,
    project_path: str | None = None,
    module_path: str | None = None,
    retrieval_issues: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Render selected retrieval evidence into a bounded, deterministic packet.

    The formatter only copies source-backed facts. It does not infer acceptance
    conditions, ownership, target symbols, or validation commands from filenames.
    """

    budget = min(
        HARD_ACTION_PACKET_TOKENS,
        max(MIN_ACTION_PACKET_TOKENS, int(max_tokens or DEFAULT_ACTION_PACKET_TOKENS)),
    )
    raw_items = [dict(item) for item in context_pack if isinstance(item, dict)]
    blocked_scope_sources = _blocked_source_keys(trust_contract or {})
    code_target_hints = [
            _source_path(item)
            for item in raw_items
            if str(item.get("source_class") or "") in _CODE_SOURCE_CLASSES
            and _source_path(item)
            and len(_source_path(item)) <= _MAX_SOURCE_PATH
            and item.get("freshness") != "stale"
            and not _instruction_risk_flags(item)
            and not (_item_source_keys(item) & blocked_scope_sources)
    ]
    target_hints = [module_path] if module_path else code_target_hints
    oversized_sources = 0
    filtered_critical_facts = 0
    scoped_items: list[dict[str, Any]] = []
    for item in raw_items:
        path, section = _source_path(item), _section(item)
        if (
            not path
            or len(path) > _MAX_SOURCE_PATH
            or len(section) > _MAX_SOURCE_SECTION
            or len(_source_scope(item)) > _MAX_SOURCE_SECTION
            or len(_version_binding(item)) > 100
        ):
            oversized_sources += 1
            if _declares_canonical_authority(item):
                filtered_critical_facts += _critical_fact_count(item)
            continue
        item["_packet_authority"] = _effective_authority(
            item,
            project_path=project_path,
            target_paths=target_hints,
        )
        scoped_items.append(item)
    scoped_items = _drop_superseded_fallbacks(scoped_items)
    authority_conflicts = _authority_conflicts(scoped_items, trust_contract or {})
    rejected_sources = _rejected_source_keys(trust_contract or {})
    rejected_critical_facts = sum(
        _critical_fact_count(item)
        for item in scoped_items
        if _declares_canonical_authority(item) and _item_source_keys(item) & rejected_sources
    )
    items = _rank_and_dedupe(scoped_items, trust_contract or {})
    objective, objective_omitted = _bounded_text(question.strip(), 1_000)
    source_rows = [_source_row(item) for item in items if _source_path(item)]
    source_rows = _dedupe_dicts(source_rows, ("evidence_id",))

    required: list[dict[str, Any]] = []
    forbidden: list[dict[str, Any]] = []
    compile_checks: list[dict[str, Any]] = []
    test_checks: list[dict[str, Any]] = []
    semantic_checks: list[dict[str, Any]] = []
    guidance: list[dict[str, Any]] = []
    critical_fact_omissions = 0
    snippet_omissions = 0
    risky_content_omissions = 0
    risky_critical_omissions = 0
    untrusted_validation_omissions = 0
    for item in items:
        evidence_id = _evidence_id(item) if _source_path(item) else None
        if not evidence_id:
            continue
        facts, omitted_facts = _extract_facts(str(item.get("content") or ""))
        if _instruction_risk_flags(item):
            risky_content_omissions += len(facts) + (1 if item.get("snippet") else 0)
            if _declares_canonical_authority(item):
                risky_critical_omissions += sum(
                    1 for fact_type, _ in facts if fact_type in {"required", "forbidden", "validation"}
                ) + omitted_facts
            continue
        critical_fact_omissions += omitted_facts if _authority(item) == "canonical" else 0
        for fact_type, fact in facts:
            cited = {"text": fact, "evidence_ids": [evidence_id]}
            if _authority(item) != "canonical":
                continue
            if fact_type == "forbidden":
                forbidden.append(cited)
            elif fact_type == "validation":
                if not _may_guide_workflow(item):
                    untrusted_validation_omissions += 1
                    continue
                bucket = _validation_bucket(fact)
                {"compile": compile_checks, "tests": test_checks, "semantic": semantic_checks}[bucket].append(cited)
            elif fact_type == "required":
                required.append(cited)
        snippet, snippet_omitted = _snippet_text(item.get("snippet"))
        snippet_omissions += snippet_omitted
        if snippet:
            guidance.append({"text": snippet, "evidence_ids": [evidence_id]})

    symbols: list[dict[str, Any]] = []
    for item in items:
        evidence_id = _evidence_id(item) if _source_path(item) else None
        if not evidence_id or str(item.get("source_class") or "") not in _CODE_SOURCE_CLASSES:
            continue
        for symbol in _explicit_symbols(item):
            symbols.append({"name": symbol, "evidence_ids": [evidence_id]})

    packet: dict[str, Any] = {
        "schema_version": ACTION_PACKET_SCHEMA_VERSION,
        "status": "ok",
        "task_interpretation": {
            "objective": objective,
            "acceptance_conditions": [],
        },
        "source_of_truth": source_rows,
        "target_surface": {
            "likely_files": _dedupe_cited([
                {"path": _source_path(item), "evidence_ids": [_evidence_id(item)]}
                for item in items
                if str(item.get("source_class") or "") in _CODE_SOURCE_CLASSES
                and _source_path(item)
            ], "path"),
            "symbols": _dedupe_cited(symbols, "name"),
        },
        "required_invariants": _dedupe_cited(required, "text"),
        "forbidden_changes": _dedupe_cited(forbidden, "text"),
        "implementation_guidance": _dedupe_cited(guidance, "text"),
        "validation": {
            "compile": _dedupe_cited(compile_checks, "text"),
            "tests": _dedupe_cited(test_checks, "text"),
            "semantic_checks": _dedupe_cited(semantic_checks, "text"),
        },
        "uncertainties": [],
        "missing_evidence": [],
        "omitted_counts": {},
        "estimated_tokens": 0,
    }
    if objective_omitted:
        packet["status"] = "insufficient_evidence"
        packet["omitted_counts"]["task_interpretation.objective_characters"] = objective_omitted
        packet["missing_evidence"].append(
            "The task objective exceeded the bounded handoff and must be shortened without losing constraints."
        )

    for field, count in (
        ("oversized_source_identifiers", oversized_sources),
        ("filtered_critical_source_facts", filtered_critical_facts),
        ("rejected_critical_source_facts", rejected_critical_facts),
        ("critical_source_facts", critical_fact_omissions),
        ("implementation_guidance", snippet_omissions),
        ("risky_document_items", risky_content_omissions),
        ("risky_critical_source_facts", risky_critical_omissions),
        ("untrusted_validation_commands", untrusted_validation_omissions),
    ):
        if count:
            packet["omitted_counts"][field] = count
            if packet["status"] == "ok":
                packet["status"] = "truncated"

    if critical_fact_omissions or filtered_critical_facts or rejected_critical_facts or risky_critical_omissions:
        packet["status"] = "insufficient_evidence"
        packet["missing_evidence"].append(
            "At least one critical canonical fact was filtered, rejected, risky, or too large to include safely."
        )

    if authority_conflicts:
        packet["status"] = "insufficient_evidence"
        packet["uncertainties"] = [
            {"type": "authority_conflict", "path": path, "symbol_or_section": section}
            for path, section in authority_conflicts
        ]
        packet["missing_evidence"].append("Conflicting canonical evidence must be resolved before editing.")

    for issue in list(retrieval_issues or [])[:5]:
        text, _ = _bounded_text(str(issue).strip(), 240)
        if text and text not in packet["missing_evidence"]:
            packet["missing_evidence"].append(text)
    if packet["missing_evidence"]:
        packet["status"] = "insufficient_evidence"

    _prune_orphan_sources(packet)

    if not packet["source_of_truth"]:
        packet["status"] = "insufficient_evidence"
        message = "No selected source-backed evidence matched the request."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)
    elif not _has_actionable_items(packet):
        packet["status"] = "insufficient_evidence"
        message = "Selected sources do not contain explicit constraints, validation commands, or code-surface evidence."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)

    _fit_packet(packet, budget)
    _ensure_post_fit_status(packet)
    _refresh_estimated_tokens(packet)
    # Account for the estimate field itself. If it crosses the caller budget,
    # remove another complete item and recompute rather than slicing text.
    while packet["estimated_tokens"] > budget and _remove_one_budget_item(packet):
        _refresh_estimated_tokens(packet)
    _refresh_estimated_tokens(packet)
    if packet["estimated_tokens"] > budget:
        _compact_failure_packet(packet, budget)
    return packet


def validate_action_packet(
    packet: Any,
    *,
    evidence_items: Iterable[dict[str, Any]] | None = None,
    max_tokens: int = HARD_ACTION_PACKET_TOKENS,
    project_path: str | None = None,
    module_path: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["ActionPacket must be an object"]
    required_keys = {
        "schema_version", "status", "task_interpretation", "source_of_truth", "target_surface",
        "required_invariants", "forbidden_changes", "implementation_guidance", "validation",
        "uncertainties", "missing_evidence", "omitted_counts", "estimated_tokens",
    }
    missing = sorted(required_keys - set(packet))
    extra = sorted(set(packet) - required_keys)
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"unknown fields: {', '.join(extra)}")
    if packet.get("schema_version") != ACTION_PACKET_SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if packet.get("status") not in {"ok", "truncated", "insufficient_evidence"}:
        errors.append("invalid status")

    task = _object_field(packet, "task_interpretation", {"objective", "acceptance_conditions"}, errors)
    if task:
        if not isinstance(task.get("objective"), str) or not task["objective"].strip():
            errors.append("task_interpretation.objective must be a non-empty string")
        _validate_cited_items(
            task.get("acceptance_conditions"), "task_interpretation.acceptance_conditions", "text", errors
        )

    target_surface = _object_field(packet, "target_surface", {"likely_files", "symbols"}, errors)
    if target_surface:
        _validate_cited_items(target_surface.get("likely_files"), "target_surface.likely_files", "path", errors)
        _validate_cited_items(target_surface.get("symbols"), "target_surface.symbols", "name", errors)

    validation = _object_field(packet, "validation", {"compile", "tests", "semantic_checks"}, errors)
    if validation:
        for key in ("compile", "tests", "semantic_checks"):
            _validate_cited_items(validation.get(key), f"validation.{key}", "text", errors)

    sources = packet.get("source_of_truth") if isinstance(packet.get("source_of_truth"), list) else []
    if not isinstance(packet.get("source_of_truth"), list):
        errors.append("source_of_truth must be an array")
    evidence_ids: set[Any] = set()
    source_by_evidence: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(sources):
        if not isinstance(row, dict):
            errors.append(f"source_of_truth[{index}] must be an object")
            continue
        expected = {
            "path", "symbol_or_section", "authority", "instruction_trust",
            "scope", "version_binding", "evidence_id",
        }
        if set(row) != expected:
            errors.append(f"source_of_truth[{index}] fields must be {sorted(expected)}")
        if not all(
            isinstance(row.get(key), str) and row[key].strip()
            for key in (
                "path", "symbol_or_section", "instruction_trust", "scope",
                "version_binding", "evidence_id",
            )
        ):
            errors.append("source_of_truth entries require complete source, trust, scope, version, and evidence fields")
            continue
        if row.get("authority") not in {"canonical", "supporting"}:
            errors.append("invalid source authority")
        if row.get("instruction_trust") not in {"scoped_agent_policy", "untrusted_data"}:
            errors.append("invalid source instruction_trust")
        evidence_id = str(row.get("evidence_id"))
        if evidence_id in evidence_ids:
            errors.append("duplicate source evidence_id")
        evidence_ids.add(evidence_id)
        source_by_evidence[evidence_id] = row

    for key in ("required_invariants", "forbidden_changes", "implementation_guidance"):
        _validate_cited_items(packet.get(key), key, "text", errors)

    cited_fields = _all_cited_items(packet, task, target_surface, validation)
    for item in cited_fields:
        refs = item.get("evidence_ids")
        if (
            not isinstance(refs, list)
            or not refs
            or any(not isinstance(ref, str) or ref not in evidence_ids for ref in refs)
        ):
            errors.append("factual item has missing or unknown evidence_ids")
            break

    canonical_fields = {
        "task_interpretation.acceptance_conditions": task.get("acceptance_conditions"),
        "required_invariants": packet.get("required_invariants"),
        "forbidden_changes": packet.get("forbidden_changes"),
    }
    for field, value in canonical_fields.items():
        for item in _cited_dict_items(value):
            refs = _string_refs(item)
            if refs and any(source_by_evidence.get(ref, {}).get("authority") != "canonical" for ref in refs):
                errors.append(f"{field} may cite only canonical evidence")
                break
    for field in ("compile", "tests", "semantic_checks"):
        for item in _cited_dict_items(validation.get(field)):
            refs = _string_refs(item)
            if any(
                source_by_evidence.get(ref, {}).get("instruction_trust") != "scoped_agent_policy"
                for ref in refs
            ):
                errors.append(f"validation.{field} may cite only scoped agent policy")
                break

    uncertainties = packet.get("uncertainties")
    if not isinstance(uncertainties, list):
        errors.append("uncertainties must be an array")
    else:
        for index, item in enumerate(uncertainties):
            expected = {"type", "path", "symbol_or_section"}
            if not isinstance(item, dict) or set(item) != expected or item.get("type") != "authority_conflict" or not all(
                isinstance(item.get(key), str) and item[key].strip() for key in expected
            ):
                errors.append(f"uncertainties[{index}] must be a complete authority-conflict object")

    missing_evidence = packet.get("missing_evidence")
    if not isinstance(missing_evidence, list) or any(
        not isinstance(item, str) or not item.strip() for item in (missing_evidence or [])
    ):
        errors.append("missing_evidence must be an array of non-empty strings")

    omitted_counts = packet.get("omitted_counts")
    if not isinstance(omitted_counts, dict) or any(
        not isinstance(key, str) or not key or isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for key, value in (omitted_counts.items() if isinstance(omitted_counts, dict) else [])
    ):
        errors.append("omitted_counts must map field names to positive integers")

    status = packet.get("status")
    if status == "ok" and (missing_evidence or omitted_counts):
        errors.append("ok packets cannot report missing evidence or omissions")
    if status == "ok" and (not sources or not _has_actionable_items(packet)):
        errors.append("ok packets require cited actionable evidence")
    if status == "ok" and uncertainties:
        errors.append("ok packets cannot report uncertainties")
    if status == "truncated" and not omitted_counts:
        errors.append("truncated packets must report omitted_counts")
    if status == "insufficient_evidence" and not missing_evidence:
        errors.append("insufficient_evidence packets must explain missing_evidence")
    if isinstance(omitted_counts, dict) and any(
        key in omitted_counts for key in (
            "required_invariants", "forbidden_changes", "critical_source_facts",
            "filtered_critical_source_facts", "rejected_critical_source_facts",
            "risky_critical_source_facts", "task_interpretation.objective_characters",
        )
    ) and status != "insufficient_evidence":
        errors.append("critical omissions require insufficient_evidence status")

    if evidence_items is not None:
        raw_evidence_items = [item for item in evidence_items if isinstance(item, dict)]
        code_targets = [
            _source_path(item) for item in raw_evidence_items
            if str(item.get("source_class") or "") in _CODE_SOURCE_CLASSES and _source_path(item)
        ]
        target_hints = [module_path] if module_path else code_targets
        bound_items: list[dict[str, Any]] = []
        for original in raw_evidence_items:
            item = dict(original)
            item["_packet_authority"] = _effective_authority(
                item, project_path=project_path, target_paths=target_hints,
            )
            bound_items.append(item)
        evidence_map = {
            _evidence_id(item): item
            for item in bound_items
            if _source_path(item)
        }
        _validate_evidence_fidelity(packet, evidence_map, errors)

    declared = packet.get("estimated_tokens")
    declared_tokens = declared if isinstance(declared, int) and not isinstance(declared, bool) else -1
    try:
        actual = estimate_action_packet_tokens(packet)
    except (TypeError, ValueError):
        actual = HARD_ACTION_PACKET_TOKENS + 1
        errors.append("ActionPacket must be JSON serializable")
    effective_limit = min(HARD_ACTION_PACKET_TOKENS, max(MIN_ACTION_PACKET_TOKENS, int(max_tokens)))
    if actual > effective_limit or declared_tokens != actual:
        errors.append("estimated_tokens mismatch or hard limit exceeded")
    return errors


def _object_field(
    packet: dict[str, Any], field: str, expected: set[str], errors: list[str]
) -> dict[str, Any]:
    value = packet.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    if set(value) != expected:
        errors.append(f"{field} fields must be {sorted(expected)}")
    return value


def _validate_cited_items(value: Any, field: str, text_key: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return
    expected = {text_key, "evidence_ids"}
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != expected:
            errors.append(f"{field}[{index}] fields must be {sorted(expected)}")
            continue
        if not isinstance(item.get(text_key), str) or not item[text_key].strip():
            errors.append(f"{field}[{index}].{text_key} must be a non-empty string")
        refs = item.get("evidence_ids")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref for ref in refs):
            errors.append(f"{field}[{index}].evidence_ids must be a non-empty string array")
            continue
        identity = (str(item.get(text_key) or ""), tuple(refs))
        if identity in seen:
            errors.append(f"{field} contains duplicate cited items")
        seen.add(identity)


def _all_cited_items(
    packet: dict[str, Any],
    task: dict[str, Any],
    target_surface: dict[str, Any],
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    values = [
        task.get("acceptance_conditions"),
        packet.get("required_invariants"),
        packet.get("forbidden_changes"),
        packet.get("implementation_guidance"),
        target_surface.get("symbols"),
        target_surface.get("likely_files"),
        validation.get("compile"),
        validation.get("tests"),
        validation.get("semantic_checks"),
    ]
    return [item for value in values if isinstance(value, list) for item in value if isinstance(item, dict)]


def _cited_dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_refs(item: dict[str, Any]) -> list[str]:
    refs = item.get("evidence_ids")
    if not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, str) and ref]


def _validate_evidence_fidelity(
    packet: dict[str, Any], evidence_map: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    sources = packet.get("source_of_truth") if isinstance(packet.get("source_of_truth"), list) else []
    for row in sources:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidence_id") or "")
        evidence = evidence_map.get(evidence_id)
        if evidence is None:
            errors.append("source_of_truth contains evidence not present in the retrieval result")
            continue
        expected = _source_row(evidence)
        if any(row.get(key) != expected.get(key) for key in expected):
            errors.append("source attribution does not match the bound retrieval evidence")

    task = packet.get("task_interpretation") if isinstance(packet.get("task_interpretation"), dict) else {}
    for item in _cited_dict_items(task.get("acceptance_conditions")):
        text = str(item.get("text") or "")
        refs = _string_refs(item)
        if refs and any(text not in _explicit_acceptance_conditions(evidence_map.get(ref, {})) for ref in refs):
            errors.append("task_interpretation.acceptance_conditions is not an explicit condition in its cited evidence")
            break
    for field in ("required_invariants", "forbidden_changes"):
        expected_type = "required" if field == "required_invariants" else "forbidden"
        for item in _cited_dict_items(packet.get(field)):
            text = str(item.get("text") or "")
            refs = _string_refs(item)
            if any(
                (expected_type, text) not in _extract_facts(
                    str(evidence_map.get(ref, {}).get("content") or "")
                )[0]
                for ref in refs
            ):
                errors.append(f"{field} contains text not present in its cited evidence")
                break
    for field in ("compile", "tests", "semantic_checks"):
        validation = packet.get("validation") if isinstance(packet.get("validation"), dict) else {}
        for item in _cited_dict_items(validation.get(field)):
            text = str(item.get("text") or "")
            refs = _string_refs(item)
            if any(
                ("validation", text) not in _extract_facts(
                    str(evidence_map.get(ref, {}).get("content") or "")
                )[0]
                for ref in refs
            ):
                errors.append(f"validation.{field} contains a command not present in its cited evidence")
                break
    for item in _cited_dict_items(packet.get("implementation_guidance")):
        text = str(item.get("text") or "")
        if any(text != _snippet_text(evidence_map.get(ref, {}).get("snippet"))[0] for ref in _string_refs(item)):
            errors.append("implementation_guidance does not match its cited snippet")
            break
    target_surface = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    for item in _cited_dict_items(target_surface.get("likely_files")):
        if any(item.get("path") != _source_path(evidence_map.get(ref, {})) for ref in _string_refs(item)):
            errors.append("target_surface.likely_files does not match its cited source")
            break
    for item in _cited_dict_items(target_surface.get("symbols")):
        if any(item.get("name") not in _explicit_symbols(evidence_map.get(ref, {})) for ref in _string_refs(item)):
            errors.append("target_surface.symbols does not match its cited source")
            break


def _explicit_acceptance_conditions(evidence: dict[str, Any]) -> set[str]:
    metadata = evidence.get("metadata") if isinstance(evidence.get("metadata"), dict) else {}
    values: list[Any] = []
    for source in (evidence, metadata):
        value = source.get("acceptance_conditions")
        values.extend(value if isinstance(value, list) else [value] if value else [])
    result: set[str] = set()
    for value in values:
        text = str(value.get("text") or value.get("condition") or "") if isinstance(value, dict) else str(value)
        if text.strip():
            result.add(text.strip())
    return result


def _refresh_estimated_tokens(packet: dict[str, Any]) -> None:
    packet["estimated_tokens"] = 0
    for _ in range(8):
        actual = estimate_action_packet_tokens(packet)
        if actual == packet["estimated_tokens"]:
            return
        packet["estimated_tokens"] = actual


def _authority_conflicts(
    items: Iterable[dict[str, Any]], trust_contract: dict[str, Any]
) -> list[tuple[str, str]]:
    constraints: dict[str, dict[str, set[tuple[str, str]]]] = {}
    blocked_sources = _blocked_source_keys(trust_contract)
    for item in items:
        if (
            _authority(item) != "canonical"
            or item.get("freshness") == "stale"
            or not _source_path(item)
            or _instruction_risk_flags(item)
            or _item_source_keys(item) & blocked_sources
        ):
            continue
        identity = _item_identity(item)
        content = str(item.get("content") or "").strip()
        facts, _ = _extract_facts(content)
        for fact_type, fact in facts:
            if fact_type not in {"required", "forbidden"}:
                continue
            signature = _constraint_signature(fact)
            if signature:
                constraints.setdefault(signature, {}).setdefault(fact_type, set()).add(identity)
    conflicts: set[tuple[str, str]] = set()
    for by_type in constraints.values():
        if by_type.get("required") and by_type.get("forbidden"):
            conflicts.update(by_type["required"])
            conflicts.update(by_type["forbidden"])
    return sorted(conflicts)


def _constraint_signature(value: str) -> str:
    normalized = re.sub(
        r"\b(?:must|shall|required|requires?|invariant|do|not|never|forbidden|prohibited|this|is|be)\b",
        " ",
        value.lower(),
    )
    return " ".join(re.findall(r"[a-z0-9_]+", normalized))


def _effective_authority(
    item: dict[str, Any], *, project_path: str | None, target_paths: Iterable[str]
) -> str:
    declared = {
        str(value).lower()
        for value in (item.get("authority"), item.get("repository_authority"))
        if value
    }
    if not declared & {"canonical", "source_of_truth", "explicit_agent_policy"}:
        return "supporting"
    if _instruction_risk_flags(item):
        return "supporting"
    if item.get("repository_authority") == "explicit_agent_policy":
        return "canonical" if _scope_applies(item, project_path=project_path, target_paths=target_paths) else "supporting"
    if str(item.get("doc_scope") or "") == "module" or item.get("module_path"):
        return "canonical" if _scope_applies(item, project_path=project_path, target_paths=target_paths) else "supporting"
    return "canonical"


def _declares_canonical_authority(item: dict[str, Any]) -> bool:
    declared = {
        str(value).lower()
        for value in (item.get("authority"), item.get("repository_authority"))
        if value
    }
    return bool(declared & {"canonical", "source_of_truth", "explicit_agent_policy"})


def _critical_fact_count(item: dict[str, Any]) -> int:
    facts, oversized = _extract_facts(str(item.get("content") or ""))
    return oversized + sum(
        1 for fact_type, _ in facts if fact_type in {"required", "forbidden", "validation"}
    )


def _scope_applies(
    item: dict[str, Any], *, project_path: str | None, target_paths: Iterable[str]
) -> bool:
    root = str(item.get("authority_root") or project_path or "").strip()
    raw_scope = str(item.get("policy_scope") or item.get("module_path") or root).strip()
    if not raw_scope:
        return False
    scope = _absolute_scope(raw_scope, root)
    targets = [str(value).strip() for value in target_paths if str(value).strip()]
    if not targets:
        return bool(root and _same_path(scope, _absolute_scope(root, root)))
    return any(_is_within(_absolute_scope(target, root), scope) for target in targets)


def _absolute_scope(value: str, root: str) -> str:
    if "://" in value:
        return value
    path = Path(value)
    if not path.is_absolute() and root:
        path = Path(root) / path
    return os.path.normcase(os.path.normpath(str(path)))


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def _is_within(path: str, scope: str) -> bool:
    if "://" in path or "://" in scope:
        return path == scope or path.startswith(scope.rstrip("/") + "/")
    try:
        return os.path.commonpath([path, scope]) == scope
    except ValueError:
        return False


def _instruction_risk_flags(item: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for raw in (item.get("instruction_risk_flags"), item.get("risk_flags")):
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
        elif raw:
            values.append(raw)
    return [
        str(value)
        for value in values
        if value
    ]


def _may_guide_workflow(item: dict[str, Any]) -> bool:
    return (
        _authority(item) == "canonical"
        and item.get("repository_authority") == "explicit_agent_policy"
        and item.get("instruction_trust") == "scoped_agent_policy"
        and bool(item.get("scope_verified"))
        and not _instruction_risk_flags(item)
    )


def _source_scope(item: dict[str, Any]) -> str:
    return str(
        item.get("module_path")
        or item.get("policy_scope")
        or item.get("doc_scope")
        or "unscoped"
    )


def _version_binding(item: dict[str, Any]) -> str:
    return str(
        item.get("docs_exactness")
        or item.get("version_binding")
        or item.get("version")
        or "not_applicable"
    )


def _relevance_score(item: dict[str, Any]) -> float:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    for source in (item, metadata):
        for key in ("score", "relevance_score", "similarity", "rank_score", "confidence_score"):
            value = source.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
                return float(value)
    return 0.0


def _version_exactness_rank(item: dict[str, Any]) -> int:
    exactness = _version_binding(item).strip().lower().replace("-", "_")
    if exactness in {"exact", "exact_version", "version_exact", "exact_version_indexed"}:
        return 0
    if "fallback" in exactness or exactness in {"latest", "best_effort", "unknown"}:
        return 2
    return 1


def _version_candidate_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("canonical_id") or item.get("library_id") or _source_path(item)),
        _section(item),
        str(item.get("requested_version") or ""),
    )


def _drop_superseded_fallbacks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exact_identities = {
        _version_candidate_identity(item)
        for item in items
        if _version_exactness_rank(item) == 0
    }
    return [
        item
        for item in items
        if not (
            _version_exactness_rank(item) == 2
            and _version_candidate_identity(item) in exact_identities
        )
    ]


def _rank_and_dedupe(items: Iterable[dict[str, Any]], trust_contract: dict[str, Any]) -> list[dict[str, Any]]:
    blocked_sources = _blocked_source_keys(trust_contract)
    ranked: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for original in items:
        if not isinstance(original, dict):
            continue
        item = dict(original)
        path = _source_path(item)
        section = _section(item)
        source_keys = _item_source_keys(item)
        if not path or source_keys & blocked_sources or item.get("freshness") == "stale":
            continue
        authority = _authority(item)
        authority_rank = 0 if authority == "canonical" else 1
        class_rank = 0 if item.get("source_class") in _CODE_SOURCE_CLASSES else 1
        version_rank = _version_exactness_rank(item)
        content = str(item.get("content") or "")
        facts, _ = _extract_facts(content)
        snippet, _ = _snippet_text(item.get("snippet"))
        actionable_rank = -len(facts) - (1 if snippet else 0)
        relevance_rank = -_relevance_score(item)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        supplemental = json.dumps(
            {
                "snippet": item.get("snippet"),
                "symbols": item.get("symbols"),
                "metadata": item.get("metadata"),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        supplemental_hash = hashlib.sha256(supplemental.encode("utf-8")).hexdigest()
        ranked.append((
            (
                authority_rank, version_rank, _version_binding(item), class_rank, relevance_rank, actionable_rank,
                path, section, content_hash, supplemental_hash,
            ),
            item,
        ))
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in sorted(ranked, key=lambda row: row[0]):
        dedupe_id = _dedupe_id(item)
        if dedupe_id in seen:
            continue
        seen.add(dedupe_id)
        selected.append(item)
    return selected


def _blocked_source_keys(trust_contract: dict[str, Any]) -> set[str]:
    return _risky_source_keys(trust_contract) | _rejected_source_keys(trust_contract)


def _risky_source_keys(trust_contract: dict[str, Any]) -> set[str]:
    return _trust_source_keys(trust_contract, "risky")


def _rejected_source_keys(trust_contract: dict[str, Any]) -> set[str]:
    return _trust_source_keys(trust_contract, "rejected")


def _trust_source_keys(trust_contract: dict[str, Any], field: str) -> set[str]:
    trust_sources = trust_contract.get("sources") if isinstance(trust_contract.get("sources"), dict) else {}
    rows: list[Any] = []
    aliases = [field]
    if field == "risky":
        aliases.append("risky_sources")
    elif field == "rejected":
        aliases.append("rejected_sources")
    for key in aliases:
        for value in (trust_contract.get(key), trust_sources.get(key)):
            if isinstance(value, list):
                rows.extend(value)
            elif isinstance(value, (str, dict)):
                rows.append(value)
    return {
        key
        for row in rows
        if isinstance(row, (str, dict))
        if (key := _normalized_source_key(
            row.get("source") or row.get("path") or row.get("url")
            or row.get("canonical_id") or row.get("library_id") or row.get("library") or ""
            if isinstance(row, dict) else row
        ))
    }


def _item_source_keys(item: dict[str, Any]) -> set[str]:
    return {
        key
        for value in (
            _source_path(item), item.get("url"), item.get("canonical_id"),
            item.get("library_id"), item.get("library"),
        )
        if value
        if (key := _normalized_source_key(value))
    }


def _normalized_source_key(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("path") or value.get("source") or value.get("url") or ""
    return str(value).strip().replace("\\", "/").rstrip("/").lower()


def _authority(item: dict[str, Any]) -> str:
    packet_authority = item.get("_packet_authority")
    if packet_authority in {"canonical", "supporting"}:
        return str(packet_authority)
    declared = {
        str(value).lower()
        for value in (item.get("authority"), item.get("repository_authority"))
        if value
    }
    if declared & {"canonical", "source_of_truth", "explicit_agent_policy"}:
        return "canonical"
    return "supporting"


def _source_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _source_path(item),
        "symbol_or_section": _section(item),
        "authority": _authority(item),
        "instruction_trust": str(item.get("instruction_trust") or "untrusted_data"),
        "scope": _source_scope(item),
        "version_binding": _version_binding(item),
        "evidence_id": _evidence_id(item),
    }


def _source_path(item: dict[str, Any]) -> str:
    value = item.get("path") or item.get("source") or item.get("url") or ""
    if isinstance(value, dict):
        value = value.get("path") or value.get("source") or value.get("url") or ""
    return str(value).strip()


def _section(item: dict[str, Any]) -> str:
    section = item.get("section") if isinstance(item.get("section"), dict) else {}
    value = item.get("heading_path") or item.get("title") or section.get("heading_path") or section.get("title") or "document"
    if isinstance(value, list):
        return " > ".join(str(part) for part in value)
    return str(value)


def _item_identity(item: dict[str, Any]) -> tuple[str, str]:
    return _source_path(item), _section(item)


def _dedupe_id(item: dict[str, Any]) -> str:
    """Identify the same evidence payload independently of version preference."""

    identity = json.dumps(
        {
            "path": _source_path(item),
            "section": _section(item),
            "content": str(item.get("content") or ""),
            "snippet": item.get("snippet"),
            "symbols": _explicit_symbols(item),
            "source_class": item.get("source_class"),
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _evidence_id(item: dict[str, Any]) -> str:
    identity = json.dumps(
        {
            "path": _source_path(item),
            "source": item.get("source"),
            "url": item.get("url"),
            "canonical_id": item.get("canonical_id"),
            "library_id": item.get("library_id"),
            "section": _section(item),
            "content": str(item.get("content") or ""),
            "snippet": item.get("snippet"),
            "symbols": _explicit_symbols(item),
            "source_class": item.get("source_class"),
            "authority": _authority(item),
            "instruction_trust": item.get("instruction_trust"),
            "scope": _source_scope(item),
            "version_binding": _version_binding(item),
            "requested_version": item.get("requested_version"),
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return "ev-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def _extract_facts(content: str) -> tuple[list[tuple[str, str]], int]:
    facts: list[tuple[str, str]] = []
    omitted_critical = 0
    in_fence = False
    for raw in content.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if (
            in_fence
            or stripped.startswith(">")
            or stripped.startswith("#")
            or (stripped.startswith("|") and stripped.count("|") >= 2)
        ):
            continue
        line = stripped.lstrip("-* ").strip().replace("`", "")
        if not line:
            continue
        segments = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", line)
        for segment in segments:
            fact = segment.strip()
            if not fact:
                continue
            looks_critical = bool(
                _FORBIDDEN_RE.search(fact)
                or (_REQUIRED_RE.search(fact) and not _NOT_REQUIRED_RE.search(fact))
                or _validation_command(fact)
            )
            if len(fact) > 500:
                omitted_critical += int(looks_critical)
                continue
            if _FORBIDDEN_RE.search(fact):
                facts.append(("forbidden", fact))
                continue
            command = _validation_command(fact)
            if command:
                facts.append(("validation", command))
                continue
            if _REQUIRED_RE.search(fact) and not _NOT_REQUIRED_RE.search(fact):
                facts.append(("required", fact))
    return facts, omitted_critical


def _validation_command(value: str) -> str | None:
    command = value.strip()
    if _UNSAFE_COMMAND_RE.search(command):
        return None
    return command if _VALIDATION_START_RE.fullmatch(command) else None


def _validation_bucket(fact: str) -> str:
    lowered = fact.lower()
    if re.search(
        r"\b(python\s+-m\s+compileall|cargo\s+(check|build)|tsc|dart\s+analyze|"
        r"(?:\./)?gradlew?\s+.*build|(?:npm|pnpm|yarn)\s+(?:run\s+)?build|make\s+build|"
        r"go\s+build|dotnet\s+build|mvn\s+package)\b",
        lowered,
    ):
        return "compile"
    if re.search(r"\b(ruff|mypy|lint|go\s+vet)\b", lowered):
        return "semantic"
    return "tests"


def _explicit_symbols(item: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ("symbols", "matched_symbols", "symbol_names", "symbol"):
        value = item.get(key)
        values.extend(value if isinstance(value, list) else [value] if value else [])
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    for key in ("symbols", "matched_symbols", "symbol_names", "symbol"):
        value = metadata.get(key)
        values.extend(value if isinstance(value, list) else [value] if value else [])
    names = [
        value.get("name") if isinstance(value, dict) else value
        for value in values
    ]
    return list(dict.fromkeys(
        str(value) for value in names if value and _SYMBOL_RE.fullmatch(str(value))
    ))


def _snippet_text(value: Any) -> tuple[str, int]:
    if isinstance(value, dict):
        value = value.get("code") or value.get("content") or value.get("text")
    if not isinstance(value, str):
        return "", 0
    text = value.strip()
    if not text:
        return "", 0
    return (text, 0) if len(text) <= 1_000 else ("", 1)


def _bounded_text(value: str, max_characters: int) -> tuple[str, int]:
    if len(value) <= max_characters:
        return value, 0
    prefix = value[:max_characters].rsplit(" ", 1)[0].rstrip()
    if not prefix:
        prefix = value[:max_characters]
    return prefix, len(value) - len(prefix)


def _dedupe_dicts(rows: Iterable[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        identity = tuple(str(row.get(key) or "") for key in keys)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    return result


def _dedupe_cited(rows: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(row.get(key) or "")
        if not identity:
            continue
        if identity not in merged:
            merged[identity] = {key: identity, "evidence_ids": []}
        refs = [str(ref) for ref in row.get("evidence_ids") or [] if ref]
        merged[identity]["evidence_ids"] = sorted(set([*merged[identity]["evidence_ids"], *refs]))
    return list(merged.values())


def _cited_evidence_ids(packet: dict[str, Any]) -> set[str]:
    rows = [
        *packet["target_surface"]["likely_files"],
        *packet["target_surface"]["symbols"],
        *packet["required_invariants"],
        *packet["forbidden_changes"],
        *packet["implementation_guidance"],
        *packet["validation"]["compile"],
        *packet["validation"]["tests"],
        *packet["validation"]["semantic_checks"],
    ]
    return {
        str(ref)
        for row in rows
        for ref in (row.get("evidence_ids") or [])
        if isinstance(row, dict) and ref
    }


def _prune_orphan_sources(packet: dict[str, Any]) -> None:
    used = _cited_evidence_ids(packet)
    packet["source_of_truth"] = [
        row for row in packet["source_of_truth"] if row.get("evidence_id") in used
    ]


def _has_actionable_items(packet: dict[str, Any]) -> bool:
    target = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    validation = packet.get("validation") if isinstance(packet.get("validation"), dict) else {}
    return any((
        target.get("likely_files"),
        target.get("symbols"),
        packet.get("required_invariants"),
        packet.get("forbidden_changes"),
        packet.get("implementation_guidance"),
        validation.get("compile"),
        validation.get("tests"),
        validation.get("semantic_checks"),
    ))


def _fit_packet(packet: dict[str, Any], budget: int) -> None:
    while estimate_action_packet_tokens(packet) > budget and _remove_one_budget_item(packet):
        pass
    _prune_orphan_sources(packet)
    if not packet["source_of_truth"]:
        packet["status"] = "insufficient_evidence"
        message = "No source attribution fit the requested packet budget."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)


def _remove_one_budget_item(packet: dict[str, Any]) -> bool:
    rows_by_name = [
        ("implementation_guidance", packet["implementation_guidance"]),
    ]
    for name, rows in rows_by_name:
        if rows:
            rows.pop()
            _record_omission(packet, name)
            _prune_orphan_sources(packet)
            return True

    objective = str(packet["task_interpretation"].get("objective") or "")
    if len(objective) > 32:
        target = max(32, len(objective) - max(32, len(objective) // 4))
        shortened, removed = _bounded_text(objective, target)
        packet["task_interpretation"]["objective"] = shortened
        _record_omission(packet, "task_interpretation.objective_characters", removed)
        return True

    rows_by_name = [
        ("target_surface.symbols", packet["target_surface"]["symbols"]),
        ("target_surface.likely_files", packet["target_surface"]["likely_files"]),
        ("validation.semantic_checks", packet["validation"]["semantic_checks"]),
        ("validation.compile", packet["validation"]["compile"]),
        ("validation.tests", packet["validation"]["tests"]),
        ("forbidden_changes", packet["forbidden_changes"]),
        ("required_invariants", packet["required_invariants"]),
    ]
    for name, rows in rows_by_name:
        if rows:
            rows.pop()
            _record_omission(packet, name)
            if name in {"forbidden_changes", "required_invariants"}:
                packet["status"] = "insufficient_evidence"
                message = "Critical constraints did not fit the requested packet budget."
                if message not in packet["missing_evidence"]:
                    packet["missing_evidence"].append(message)
            _prune_orphan_sources(packet)
            return True
    return False


def _ensure_post_fit_status(packet: dict[str, Any]) -> None:
    _prune_orphan_sources(packet)
    if "task_interpretation.objective_characters" in packet.get("omitted_counts", {}):
        packet["status"] = "insufficient_evidence"
        message = "The complete task objective did not fit the bounded handoff."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)
    if not _has_actionable_items(packet):
        packet["status"] = "insufficient_evidence"
        message = "No actionable evidence remained after applying the packet budget."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)
    if not packet["source_of_truth"]:
        packet["status"] = "insufficient_evidence"
        message = "No source attribution remained after applying the packet budget."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)


def _compact_failure_packet(packet: dict[str, Any], budget: int) -> None:
    omitted_total = sum(
        int(value) for value in packet.get("omitted_counts", {}).values()
        if isinstance(value, int) and not isinstance(value, bool)
    )
    packet.update({
        "status": "insufficient_evidence",
        "source_of_truth": [],
        "target_surface": {"likely_files": [], "symbols": []},
        "required_invariants": [],
        "forbidden_changes": [],
        "implementation_guidance": [],
        "validation": {"compile": [], "tests": [], "semantic_checks": []},
        "uncertainties": [],
        "missing_evidence": ["The available evidence did not fit the requested packet budget."],
        "omitted_counts": {"packet_items": max(1, omitted_total)},
    })
    objective = str(packet["task_interpretation"].get("objective") or "task")
    packet["task_interpretation"]["objective"] = objective[:64] or "task"
    _refresh_estimated_tokens(packet)
    if packet["estimated_tokens"] > budget:
        packet["task_interpretation"]["objective"] = "task"
        packet["missing_evidence"] = ["Evidence did not fit the packet budget."]
        _refresh_estimated_tokens(packet)


def _record_omission(packet: dict[str, Any], field: str, count: int = 1) -> None:
    packet["omitted_counts"][field] = int(packet["omitted_counts"].get(field) or 0) + count
    if packet["status"] == "ok":
        packet["status"] = "truncated"
