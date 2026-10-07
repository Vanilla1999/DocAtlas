"""Strict structure, canonical DTO and visible witness integrity validation."""
from __future__ import annotations

from pathlib import PurePosixPath

from jsonschema import Draft202012Validator, validators
from docmancer.docs.application._evidence_selection_part01 import (
    _candidate_source_view, _candidate_window_valid, validate_assignment_binding,
)
from docmancer.docs.domain.mutation_intent import _artifact_for_target
from docmancer.retrieval.contracts import canonical_hash
from ._action_packet_shared import *  # noqa: F401,F403
from ._action_packet_part03 import _bound_items, _candidate_source, _mutation_payload, _mutation_requirements

_StrictValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda checker, value: type(value) is int,
    ),
)


def _identity_collisions(candidates):
    """Use the same complete patch identity binding as canonical selection."""
    bindings, collisions = {}, set()
    for candidate in candidates:
        binding = (
            candidate.identity_kind, candidate.source_identity, candidate.parent_logical_id,
            candidate.content_sha256, candidate.symbols, candidate.exact_terms,
            candidate.evidence_id, candidate.hydration_id, candidate.identity_aliases,
            candidate.path_or_url, candidate.section, candidate.authority,
            candidate.source_class, candidate.version_binding, candidate.resolved_version,
            candidate.docs_snapshot_exact, candidate.project_identity, candidate.module_id,
            candidate.doc_scope, candidate.char_start, candidate.char_end,
            candidate.line_start, candidate.line_end, candidate.freshness,
            canonical_hash(_candidate_source_view(candidate)),
            canonical_hash({key: candidate.original.get(key) for key in (
                "module_path", "matched", "evidence_class", "collision_free_targets",
            )}),
        )
        if bindings.setdefault(candidate.stable_id, binding) != binding:
            collisions.add(candidate.stable_id)
    return collisions


def _normal_path(value):
    return str(PurePosixPath(value.replace("\\", "/").removeprefix("./"))).casefold()


def _mutation_binding_valid(contract, binding, candidate, *, preserved=False):
    """Prove every asserted resolution from positive local evidence, not DTO hashes."""
    item = candidate.original
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    source_class = str(item.get("source_class") or metadata.get("source_class") or "").casefold()
    if item.get("matched") is False or str(item.get("evidence_class") or "").casefold() in {
        "absent_in_source", "missing_source_evidence",
    }:
        return False
    local_classes = {"code_graph", "repo_map", "project_file", "source_evidence", "test_evidence"}
    local = source_class in local_classes
    path = candidate.path_or_url
    def matches(target):
        if target.kind == "symbol":
            return binding.symbol == target.value and any(
                symbol.casefold() == target.value.casefold() for symbol in candidate.symbols
            )
        actual, wanted = _normal_path(path), _normal_path(target.value)
        return binding.symbol is None and (actual == wanted or actual.endswith("/" + wanted))
    if preserved:
        targets = contract.request_plan.preserve_targets if contract.request_plan else ()
    else:
        targets = contract.requested_targets
    associated = [target for target in targets if target.value == binding.requested_value]
    if binding.binding_kind == "target":
        # A create destination may have positive collision evidence even when it
        # was supplied only as the explicit destination rather than a target row.
        create_collision = (not preserved and contract.operation == "create"
                            and contract.destination == binding.requested_value
                            and _normal_path(path) == _normal_path(contract.destination))
        return (
            binding.exists and binding.collision_free is not True
            and binding.path == path and binding.artifact_kind == _artifact_for_target(path)
            and (local or contract.artifact_kind == "docs" and binding.artifact_kind == "docs")
            and (any(matches(target) for target in associated) or create_collision and binding.symbol is None)
        )
    if preserved or not local or contract.operation not in {"create", "rename"}:
        return False
    destination = contract.destination
    if not destination and contract.operation == "create":
        paths = {target.value for target in targets if target.kind == "path"}
        destination = next(iter(paths)) if len(paths) == 1 else None
    if not destination or binding.requested_value != destination:
        return False
    if binding.binding_kind == "parent_context":
        if (contract.operation != "create" or binding.exists or binding.collision_free is not True
                or binding.symbol is not None or binding.path != path
                or binding.artifact_kind != _artifact_for_target(destination)):
            return False
        parent = str(PurePosixPath(destination.replace("\\", "/")).parent)
        requested_parent = (contract.request_plan.parent_context.value
                            if contract.request_plan and contract.request_plan.parent_context else parent)
        module = str(item.get("module_path") or metadata.get("module_path") or "").strip("/")
        module_parent = module and (_normal_path(parent) == _normal_path(module)
                                    or _normal_path(parent).startswith(_normal_path(module) + "/"))
        return (_normal_path(path) == _normal_path(requested_parent)
                or bool(module_parent) and source_class in {"code_graph", "repo_map", "project_file"})
    if binding.binding_kind != "destination_context":
        return False
    target = contract.request_plan.destination if contract.request_plan else None
    symbolic = target is not None and target.kind == "symbol"
    if binding.exists:
        matched = (binding.symbol == destination and destination in candidate.symbols) if symbolic else (
            binding.symbol is None and (_normal_path(path) == _normal_path(destination)
                                       or _normal_path(path).endswith("/" + _normal_path(destination))))
        return (contract.operation == "rename" and binding.collision_free is False and matched
                and binding.path == path and binding.artifact_kind == _artifact_for_target(path))
    declared = item.get("collision_free_targets") or metadata.get("collision_free_targets") or ()
    return (binding.collision_free is True and source_class in {"code_graph", "repo_map"}
            and binding.path == destination and binding.symbol == (destination if symbolic else None)
            and binding.artifact_kind == (contract.artifact_kind if symbolic else _artifact_for_target(destination))
            and isinstance(declared, (list, tuple))
            and any(_normal_path(str(value)) == _normal_path(destination) for value in declared))


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
        collisions = _identity_collisions(candidates)
        errors.extend(f"stable_identity_collision:{stable_id}" for stable_id in sorted(collisions))
        by_candidate = {row.stable_id: row for row in candidates if row.stable_id not in collisions}
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
            elif not validate_assignment_binding(requirement, candidate, assignment, requirements=canonical):
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
            derived = _mutation_requirements(
                contract, target_paths=tuple(row.value for row in canonical if row.kind == "target_path"
                                             and row.public_provenance == "required_target_paths"),
            )
            for obligation in derived:
                if by_requirement.get(obligation.requirement_id) != obligation:
                    errors.append(f"explicit mutation obligation missing or altered:{obligation.requirement_id}")
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
            for preserved, bindings in ((False, contract.resolved_targets), (True, contract.preserved_targets)):
                for binding in bindings:
                    bound = [by_candidate[row["stable_id"]] for row in sources
                             if row["evidence_id"] == binding.evidence_id and row["stable_id"] in by_candidate]
                    if evidence_items is None or not any(
                        _mutation_binding_valid(contract, binding, candidate, preserved=preserved)
                        for candidate in bound
                    ):
                        errors.append("mutation resolution assertion is not bound to canonical local evidence")
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        errors.append(f"invalid canonical packet: {error}")
    return errors

__all__ = ["validate_action_packet"]
