"""Implementation shard 4 for action_packet."""
from __future__ import annotations

from ._action_packet_shared import *  # noqa: F401,F403
from docmancer.retrieval.contracts import canonical_hash

from ._action_packet_part01 import _effective_authority, _evidence_id, _has_actionable_items, _source_path, estimate_action_packet_tokens
from ._action_packet_part03 import _all_cited_items, _cited_dict_items, _object_field, _string_refs, _validate_cited_items, _validate_evidence_fidelity

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
        "mutation_intent", "uncertainties", "missing_evidence", "omitted_counts", "estimated_tokens",
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

    mutation = packet.get("mutation_intent")
    mutation_fields = {
        "operation", "artifact_kind", "requested_targets", "resolved_targets", "preserved_targets",
        "destination", "acceptance_conditions", "request_plan", "ready", "constraints_only",
        "missing", "contract_hash",
    }
    if not isinstance(mutation, dict) or set(mutation) != mutation_fields:
        errors.append("mutation_intent must be a complete bounded mutation contract")
        mutation = {}
    else:
        if mutation.get("operation") not in {"none", "modify", "create", "delete", "rename"}:
            errors.append("mutation_intent.operation is invalid")
        if mutation.get("artifact_kind") not in {"source", "docs", "config", "test", "generated_answer", "unknown"}:
            errors.append("mutation_intent.artifact_kind is invalid")
        if not isinstance(mutation.get("ready"), bool) or not isinstance(mutation.get("constraints_only"), bool):
            errors.append("mutation_intent readiness flags must be booleans")
        if not re.fullmatch(r"[0-9a-f]{64}", str(mutation.get("contract_hash") or "")):
            errors.append("mutation_intent.contract_hash is invalid")
        for key, limit in (("requested_targets", 12), ("resolved_targets", 12), ("preserved_targets", 12), ("acceptance_conditions", 8), ("missing", 12)):
            value = mutation.get(key)
            if not isinstance(value, list) or len(value) > limit:
                errors.append(f"mutation_intent.{key} exceeds its bounded contract")
        request_plan = mutation.get("request_plan")
        if request_plan is not None:
            required_plan_fields = {
                "schema_version", "operation", "mutation_targets", "preserve_targets",
                "destination", "parent_context", "scope_terms", "behavioral_requirements",
                "acceptance_conditions", "consumed_spans", "unresolved_parts",
                "language", "surface_id", "plan_hash",
            }
            if not isinstance(request_plan, dict) or set(request_plan) != required_plan_fields:
                errors.append("mutation_intent.request_plan is incomplete")
            elif (
                not (
                    request_plan.get("operation") == mutation.get("operation")
                    or (
                        mutation.get("operation") == "none"
                        and bool(request_plan.get("unresolved_parts"))
                    )
                )
                or request_plan.get("language") not in {"en", "ru"}
                or not re.fullmatch(r"[0-9a-f]{64}", str(request_plan.get("plan_hash") or ""))
            ):
                errors.append("mutation_intent.request_plan is inconsistent")
            else:
                plan_payload = {key: value for key, value in request_plan.items() if key != "plan_hash"}
                if canonical_hash(plan_payload) != request_plan["plan_hash"]:
                    errors.append("mutation_intent.request_plan hash is invalid")
                mutate_values = [
                    str(item.get("value") or "").casefold()
                    for item in request_plan.get("mutation_targets") or []
                    if isinstance(item, dict)
                ]
                requested_values = [
                    str(item.get("value") or "").casefold()
                    for item in mutation.get("requested_targets") or []
                    if isinstance(item, dict)
                    and str(item.get("provenance") or "user_request") == "user_request"
                ]
                preserve_values = {
                    str(item.get("value") or "").casefold()
                    for item in request_plan.get("preserve_targets") or []
                    if isinstance(item, dict)
                }
                if mutate_values != requested_values or preserve_values.intersection(mutate_values):
                    errors.append("mutation_intent.request_plan target polarity is inconsistent")

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
            if item.get("provenance") == "user_request":
                continue
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
    if status == "truncated" and missing_evidence:
        errors.append("missing evidence requires insufficient_evidence status")
    if status == "ok" and (not sources or not _has_actionable_items(packet)):
        errors.append("ok packets require cited actionable evidence")
    if (
        status == "ok"
        and mutation.get("operation") != "none"
        and mutation.get("ready") is not True
    ):
        errors.append("ok mutation packets require a resolved operation-aware target")
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
            "mandatory_requirements",
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

__all__=['validate_action_packet']
