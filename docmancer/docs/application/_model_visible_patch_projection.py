"""Strict patch projection/snapshot and non-authorizing recovery validation."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .action_packet import refresh_action_packet_estimate, serialize_action_packet


def _validate_patch_projection(payload: dict[str, Any], *, snapshot: dict[str, dict[str, Any]]) -> list[str]:
    # Resolve facade hooks at call time, preserving observation/monkeypatch seams.
    from . import model_visible_projection as public

    metadata = {"kind", "recommended_next_action", "source_search_status"}
    core = {key: deepcopy(value) for key, value in payload.items() if key not in metadata}
    estimated = deepcopy(payload)
    refresh_action_packet_estimate(estimated)
    errors = []
    if payload.get("estimated_tokens") != estimated["estimated_tokens"]:
        errors.append("projection estimate mismatch")
    refresh_action_packet_estimate(core)
    canonical = snapshot.get("__action_packet__") or {}
    if not isinstance(canonical, dict):
        return ["invalid canonical patch snapshot"]
    evidence = canonical.get("evidence_items", ())
    if not isinstance(evidence, (tuple, list)):
        return ["invalid canonical patch evidence"]
    errors.extend(public.validate_action_packet(
        core, evidence_items=evidence, project_path=canonical.get("project_path"),
        module_path=canonical.get("module_path"),
    ))
    if errors:
        return errors
    if canonical:
        if (not isinstance(canonical.get("packet"), dict)
            or serialize_action_packet(core) != serialize_action_packet(canonical["packet"])):
            errors.append("patch packet does not match the internal snapshot")
    elif core.get("sources") or core.get("requirements") or core.get("mutation_intent"):
        errors.append("patch contract is missing its canonical snapshot")
    ids = set()
    for source in core.get("sources") or []:
        if not isinstance(source, dict):
            continue
        identity = source.get("evidence_id")
        if not isinstance(identity, str):
            continue
        ids.add(identity)
        bound = snapshot.get(identity) or {}
        if not isinstance(bound, dict):
            errors.append("invalid patch source snapshot")
            continue
        if source != bound.get("projected_source"):
            errors.append("patch source does not match the internal snapshot")
        if bound.get("source") not in evidence:
            errors.append("patch snapshot source does not match admitted evidence")
    if set(snapshot) - {"__action_packet__"} != ids:
        errors.append("patch snapshot evidence identities do not match visible sources")
    errors.extend(public._patch_recovery_errors(payload, core))
    return errors


def _patch_recovery_errors(payload: dict[str, Any], core: dict[str, Any]) -> list[str]:
    from . import model_visible_projection as public

    errors = []
    action = payload.get("recommended_next_action")
    search_status = payload.get("source_search_status")
    if ("recommended_next_action" in payload and action is None
        or "source_search_status" in payload and search_status is None):
        errors.append("empty patch recovery metadata must be omitted")
    if action is not None:
        targets = public.patch_search_targets(core)
        expected = {
            "tool": "code_search", "type": "search_local_source",
            "handled_by": "coding_agent", "auto_execute": False,
            "requires_confirmation": False, "repeat_docs_context": False,
            "query_terms": [row["value"] for row in targets],
            "suggested_doc_paths": [row["value"] for row in targets if row["kind"] == "path"],
            "suggested_symbols": [row["value"] for row in targets if row["kind"] == "symbol"],
        }
        expected = {key: value for key, value in expected.items() if value != []}
        if (not targets or not isinstance(action, dict) or action != expected
            or search_status != "required"
            or any(action.get(key) is not False for key in (
                "auto_execute", "requires_confirmation", "repeat_docs_context",
            ))):
            errors.append("invalid non-authorizing patch recovery metadata")
    elif search_status is not None:
        errors.append("patch source search status requires explicit recovery metadata")
    return errors
