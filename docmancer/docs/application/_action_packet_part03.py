"""Lossless rendering of the canonical admitted selector decision."""
from __future__ import annotations

from ._action_packet_shared import *  # noqa: F401,F403
from ._action_packet_part01 import (
    _effective_authority, _evidence_id, _section, _source_path, _source_scope,
)


def _bound_items(items, *, project_path=None, module_path=None):
    items = [dict(item) for item in items if isinstance(item, dict)]
    targets = [module_path] if module_path else [
        _source_path(item) for item in items if item.get("source_class") in _CODE_SOURCE_CLASSES
    ]
    for item in items:
        item["_packet_authority"] = _effective_authority(
            item, project_path=project_path, target_paths=targets,
        )
    return items


def _candidate_source(candidate):
    item = dict(candidate.original)
    return _compact_value({
        "evidence_id": _evidence_id(item), "stable_id": candidate.stable_id,
        "path": candidate.path_or_url, "symbol_or_section": _section(item),
        "authority": candidate.authority, "instruction_trust": "untrusted_data",
        "scope": _source_scope(item), "version_binding": candidate.version_binding,
        "text": candidate.display_text,
        "content_sha256": hashlib.sha256(candidate.display_text.encode("utf-8")).hexdigest(),
        **{key: getattr(candidate, key) for key in ("char_start", "char_end", "line_start", "line_end")},
    })


def _mutation_payload(contract):
    payload = contract.hash_payload
    if contract.request_plan is not None:
        payload["request_plan"] = {**contract.request_plan.hash_payload, "plan_hash": contract.request_plan.plan_hash}
    return _compact_value({**payload, "contract_hash": contract.contract_hash})


def build_action_packet(
    *, question: str, context_pack: Iterable[dict[str, Any]],
    trust_contract: dict[str, Any] | None = None,
    project_path: str | None = None, module_path: str | None = None,
    retrieval_issues: Iterable[str] | None = None,
    required_evidence_paths: Iterable[str] = (), required_target_paths: Iterable[str] = (),
    public_requirements: Iterable[dict[str, Any] | str] = (),
    exact_version: str | None = None, project_identity: str | None = None,
    module_id: str | None = None, selection_diagnostics: dict[str, Any] | None = None,
    behavioral_contract_required: bool = False,
    mutation_intent_contract: MutationIntentContract | None = None,
) -> dict[str, Any]:
    """Keep whole admitted windows; completeness never grants editing permission."""
    items = _bound_items(context_pack, project_path=project_path, module_path=module_path)
    normalized, _ = normalize_candidates(items, result_kind="patch_context")
    invalid_spans = {candidate.stable_id for candidate in normalized
                     if candidate.char_start is not None and candidate.char_end is not None
                     and candidate.char_end - candidate.char_start != len(candidate.display_text)}
    if invalid_spans:
        # A parent span cannot be presented as the offset of a shorter display.
        items = [dict(candidate.original) for candidate in normalized
                 if candidate.stable_id not in invalid_spans]
    required_target_paths = tuple(required_target_paths)
    if mutation_intent_contract is not None:
        required_target_paths = tuple(dict.fromkeys((*required_target_paths, *(
            target.value for target in mutation_intent_contract.requested_targets
            if target.kind == "path" and mutation_intent_contract.operation in {"modify", "delete", "rename"}
            and target.value != mutation_intent_contract.destination
        ))))
    explicit = build_requirements(
        question, required_evidence_paths=tuple(required_evidence_paths),
        required_target_paths=required_target_paths, public_requirements=tuple(public_requirements),
        exact_version=exact_version, project_identity=project_identity, module_id=module_id,
        profile="generic", representation_bounded=False,
    )
    requirements = explicit
    if mutation_intent_contract is not None and mutation_intent_contract.request_plan is not None:
        planned = build_patch_evidence_requirements(mutation_intent_contract.request_plan)
        requirements = EvidenceRequirementSet((*explicit.requirements, *planned.requirements))
    selection = select_evidence(
        items, question=question, config=patch_selection_config(),
        trust_contract=trust_contract or {}, requirements=requirements,
    )
    if selection_diagnostics is not None:
        selection_diagnostics.update(selection.audit_manifest())
    missing = set(selection.missing_requirements) | set(selection.unresolved_conflicts)
    missing.update(f"invalid_display_span:{stable_id}" for stable_id in invalid_spans)
    missing.update(str(issue) for issue in (retrieval_issues or ()) if str(issue))
    if behavioral_contract_required and not any(
        assignment.unit_id is not None and assignment.proof_role in {"project_rule", "document_statement"}
        for assignment in selection.assignments
    ):
        missing.add("behavioral_contract_required")
    sources = [_candidate_source(candidate) for candidate in selection.selected_candidates]
    if not sources:
        missing.add("no_admitted_evidence")
    packet = {
        "schema_version": 4, "result": "data" if sources else "failure",
        "completeness": "partial" if sources and missing else "complete" if sources else "unavailable",
        "edit_ready": False, "estimated_tokens": 1,
    }
    if sources:
        packet["sources"] = sources
    if selection.requirements:
        packet["requirements"] = [_compact_value(row) for row in selection.requirements]
    if sources and selection.assignments:
        packet["assignments"] = [_compact_value(row) for row in selection.assignments]
    if missing:
        packet["missing"] = sorted(missing)
    if mutation_intent_contract is not None:
        packet["mutation_intent"] = _mutation_payload(mutation_intent_contract)
    refresh_action_packet_estimate(packet)
    return packet

__all__ = ["build_action_packet"]
