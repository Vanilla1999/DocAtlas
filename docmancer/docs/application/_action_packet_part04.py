"""Strict structure, canonical DTO and visible witness integrity validation."""
from __future__ import annotations

from jsonschema import Draft202012Validator, validators
from docmancer.docs.application._evidence_selection_part01 import (
    _candidate_window_valid, validate_assignment_binding,
)
from ._action_packet_shared import *  # noqa: F401,F403
from ._action_packet_part03 import _bound_items, _candidate_source, _mutation_payload

_StrictValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda checker, value: type(value) is int,
    ),
)


def _restore_dto(cls, payload):
    hints = get_type_hints(cls)
    def restore(annotation, value):
        origin, args = get_origin(annotation), get_args(annotation)
        if origin in (types.UnionType, Union):
            return restore(next(arg for arg in args if arg is not type(None)), value)
        if origin is tuple:
            return tuple(restore(args[0] if args[-1] is Ellipsis else args[index], item)
                         for index, item in enumerate(value))
        if is_dataclass(annotation):
            return _restore_dto(annotation, value)
        return value
    values = {key: restore(hints[key], value) for key, value in payload.items() if key in hints}
    for field in fields(cls):
        if field.name not in values and type(None) in get_args(hints[field.name]):
            values[field.name] = None
        elif field.name not in values and get_origin(hints[field.name]) is tuple:
            values[field.name] = ()
    return cls(**values)


def validate_action_packet(
    packet: Any, *, evidence_items: Iterable[dict[str, Any]] | None = None,
    project_path: str | None = None, module_path: str | None = None,
    requirements: EvidenceRequirementSet | None = None,
    mutation_intent_contract: MutationIntentContract | None = None,
) -> list[str]:
    errors = [f"{'.'.join(map(str, error.absolute_path)) or 'packet'}: {error.message}"
              for error in _StrictValidator(ACTION_PACKET_OUTPUT_SCHEMA).iter_errors(packet)]
    if errors:
        return errors
    try:
        if packet["estimated_tokens"] != estimate_action_packet_tokens(packet):
            errors.append("estimated_tokens mismatch")
        if packet.get("missing", []) != sorted(set(packet.get("missing", []))):
            errors.append("missing must be sorted unique machine reasons")
        rows = packet.get("requirements", [])
        canonical = EvidenceRequirementSet(tuple(_restore_dto(EvidenceRequirement, row) for row in rows))
        if rows != [_compact_value(row) for row in canonical]:
            errors.append("requirements differ from canonical DTO serialization")
        if requirements is not None and rows != [_compact_value(row) for row in requirements]:
            errors.append("requirements differ from supplied canonical inputs")
        by_requirement = {row.requirement_id: row for row in canonical}
        assignments = [_restore_dto(EvidenceAssignment, row) for row in packet.get("assignments", [])]
        if packet.get("assignments", []) != [_compact_value(row) for row in assignments]:
            errors.append("assignments differ from canonical DTO serialization")
        if len({row.requirement_id for row in assignments}) != len(assignments):
            errors.append("duplicate assignment requirement_id")
        sources = packet.get("sources", [])
        by_stable = {row["stable_id"]: row for row in sources}
        if len(by_stable) != len(sources):
            errors.append("duplicate source stable_id")
        for source in sources:
            if source["content_sha256"] != hashlib.sha256(source["text"].encode("utf-8")).hexdigest():
                errors.append("source content_sha256 mismatch")
            for prefix in ("char", "line"):
                start, end = source.get(prefix + "_start"), source.get(prefix + "_end")
                if start is not None and end is not None and end < start:
                    errors.append("invalid source span")
            if source.get("char_start") is not None and source.get("char_end") is not None:
                if source["char_end"] - source["char_start"] != len(source["text"]):
                    errors.append("source character span does not match display window")
        # Re-extract witnesses from visible text; never trust a caller's unit claims.
        visible_items = [{"stable_id": row["stable_id"], "path": row["path"],
                          "title": row["symbol_or_section"], "content": row["text"],
                          "authority": row["authority"], "version_binding": row["version_binding"],
                          **{key: row[key] for key in ("char_start", "char_end", "line_start", "line_end") if key in row}}
                         for row in sources]
        candidates, _ = normalize_candidates(
            _bound_items(evidence_items, project_path=project_path, module_path=module_path)
            if evidence_items is not None else visible_items, result_kind="patch_context",
        )
        by_candidate = {row.stable_id: row for row in candidates}
        for source in sources:
            candidate = by_candidate.get(source["stable_id"])
            if candidate is None or not _candidate_window_valid(candidate):
                errors.append("source window identity, freshness or hash is invalid")
        if evidence_items is not None:
            for source in sources:
                candidate = by_candidate.get(source["stable_id"])
                if candidate is None or source != _candidate_source(candidate):
                    errors.append("source differs from bound retrieval window")
        for assignment in assignments:
            requirement = by_requirement.get(assignment.requirement_id)
            candidate = by_candidate.get(assignment.evidence_id)
            if assignment.evidence_id not in by_stable or requirement is None or candidate is None:
                errors.append("assignment does not resolve to canonical visible inputs")
            elif not validate_assignment_binding(requirement, candidate, assignment):
                errors.append("assignment witness binding is invalid")
            elif assignment.qualifiers != requirement.qualifiers:
                # The canonical selector does not infer qualifiers from prose.
                errors.append("assignment qualifiers differ from canonical inputs")
        if assignments != sorted(assignments, key=lambda row: row.requirement_id):
            errors.append("assignments must retain canonical requirement ordering")
        mandatory = {row.requirement_id for row in canonical if row.mandatory}
        assigned = {row.requirement_id for row in assignments}
        if packet["completeness"] == "complete":
            if mandatory - assigned:
                errors.append("complete data is missing mandatory assignments")
            if not any(row.unit_id is not None for row in assignments):
                errors.append("complete data requires a visible content assignment")
        mutation = packet.get("mutation_intent")
        if mutation_intent_contract is not None and mutation is None:
            errors.append("supplied explicit mutation contract was omitted")
        if mutation is not None:
            contract = _restore_dto(MutationIntentContract, mutation)
            if mutation != _mutation_payload(contract):
                errors.append("mutation contract or request-plan hash/content mismatch")
            if mutation_intent_contract is not None and mutation != _mutation_payload(mutation_intent_contract):
                errors.append("mutation differs from supplied explicit contract")
            plan = contract.request_plan
            if plan is not None:
                if plan.operation != contract.operation and not (
                    contract.operation == "none" and plan.unresolved_parts
                ):
                    errors.append("mutation and request-plan operations are inconsistent")
                mutate_values = [target.value for target in plan.mutation_targets]
                requested_values = [target.value for target in contract.requested_targets
                                    if target.provenance == "user_request"]
                if mutate_values != requested_values:
                    errors.append("mutation and request-plan targets are inconsistent")
                if {value.casefold() for value in mutate_values}.intersection(
                    target.value.casefold() for target in plan.preserve_targets
                ):
                    errors.append("request-plan target polarity is inconsistent")
                if plan.destination is not None and plan.destination.value != contract.destination:
                    errors.append("mutation and request-plan destinations are inconsistent")
            for binding in (*contract.resolved_targets, *contract.preserved_targets):
                bound_sources = [row for row in sources if row["evidence_id"] == binding.evidence_id]
                if not bound_sources:
                    errors.append("mutation binding references unavailable evidence")
                elif binding.binding_kind == "target" and binding.exists:
                    if not any(row["path"] == binding.path for row in bound_sources):
                        errors.append("mutation target path differs from bound evidence")
                    if binding.requested_value not in {row.value for row in contract.requested_targets} and binding not in contract.preserved_targets:
                        errors.append("mutation binding has no explicit requested target")
                    requested = next((row for row in contract.requested_targets
                                      if row.value == binding.requested_value), None)
                    if requested is not None and requested.kind == "path":
                        wanted = requested.value.replace("\\", "/").casefold()
                        actual = binding.path.replace("\\", "/").casefold()
                        if actual != wanted and not actual.endswith("/" + wanted):
                            errors.append("mutation requested path does not match its binding")
                    if binding.symbol is not None and evidence_items is not None:
                        candidates_for_binding = [by_candidate[row["stable_id"]] for row in bound_sources
                                                  if row["stable_id"] in by_candidate]
                        if not any(binding.symbol in row.symbols for row in candidates_for_binding):
                            errors.append("mutation symbol does not match bound retrieval evidence")
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        errors.append(f"invalid canonical packet: {error}")
    return errors

__all__ = ["validate_action_packet"]
