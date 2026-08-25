"""Implementation shard 3 for action_packet."""
from __future__ import annotations

from ._action_packet_shared import *  # noqa: F401,F403

from ._action_packet_part01 import _add_mandatory_requirement_witnesses, _authority, _blocked_source_keys, _content_instruction_risk_flags, _content_text, _critical_fact_count, _declares_canonical_authority, _dedupe_cited, _editable_target_path, _effective_authority, _ensure_selection_survives_packet, _evidence_id, _explicit_acceptance_conditions, _explicit_symbols, _extract_facts, _has_actionable_items, _instruction_risk_flags, _item_source_keys, _normalized_source_key, _rank_and_dedupe, _refresh_estimated_tokens, _rejected_source_keys, _section, _snippet_text, _source_path, _source_row, _source_scope, _version_binding
from ._action_packet_part02 import _authority_conflicts, _bounded_text, _compact_failure_packet, _dedupe_dicts, _drop_superseded_fallbacks, _ensure_post_fit_status, _fit_packet, _has_behavioral_contract, _may_guide_workflow, _prune_orphan_sources, _remove_one_budget_item, _validation_bucket

def build_action_packet(
    *,
    question: str,
    context_pack: Iterable[dict[str, Any]],
    trust_contract: dict[str, Any] | None = None,
    max_tokens: int = DEFAULT_ACTION_PACKET_TOKENS,
    project_path: str | None = None,
    module_path: str | None = None,
    retrieval_issues: Iterable[str] | None = None,
    required_evidence_paths: Iterable[str] = (),
    required_target_paths: Iterable[str] = (),
    public_requirements: Iterable[dict[str, Any] | str] = (),
    exact_version: str | None = None,
    project_identity: str | None = None,
    module_id: str | None = None,
    selection_diagnostics: dict[str, Any] | None = None,
    behavioral_contract_required: bool = False,
    mutation_intent_contract: MutationIntentContract | None = None,
) -> dict[str, Any]:
    """Render selected retrieval evidence into a bounded, deterministic packet.

    The formatter only copies source-backed facts. It does not infer acceptance
    conditions, ownership, target symbols, or validation commands from filenames.
    """

    budget = min(
        HARD_ACTION_PACKET_TOKENS,
        max(MIN_ACTION_PACKET_TOKENS, int(max_tokens or DEFAULT_ACTION_PACKET_TOKENS)),
    )
    mutation_intent = mutation_intent_contract or build_mutation_intent(question)
    required_evidence_paths = tuple(required_evidence_paths)
    required_target_paths = tuple(required_target_paths)
    if mutation_intent_contract is None and required_target_paths:
        mutation_intent = with_explicit_path_targets(
            mutation_intent,
            required_target_paths,
            provenance="explicit_required_target",
        )
    requested_path_targets = tuple(
        target.value
        for target in mutation_intent.requested_targets
        if target.kind == "path"
        and mutation_intent.operation in {"modify", "delete", "rename"}
        and target.value.casefold() != str(mutation_intent.destination or "").casefold()
    )
    required_target_paths = tuple(dict.fromkeys((
        *required_target_paths,
        *requested_path_targets,
    )))
    public_requirements = tuple(public_requirements)
    raw_items = [dict(item) for item in context_pack if isinstance(item, dict)]
    retrieval_issue_list = [str(issue) for issue in (retrieval_issues or []) if str(issue).strip()]
    required_source_keys = {
        _normalized_source_key(path) for path in required_evidence_paths if str(path).strip()
    }
    required_target_keys = {
        _normalized_source_key(path) for path in required_target_paths if str(path).strip()
    }
    blocked_scope_sources = _blocked_source_keys(trust_contract or {})
    code_target_hints = [
            _source_path(item)
            for item in raw_items
            if str(item.get("source_class") or "") in _CODE_SOURCE_CLASSES
            and _source_path(item)
            and _editable_target_path(_source_path(item))
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
    selection = select_evidence(
        scoped_items,
        question=question,
        config=patch_selection_config(budget),
        trust_contract=trust_contract or {},
        required_evidence_paths=required_evidence_paths,
        required_target_paths=required_target_paths,
        public_requirements=public_requirements,
        exact_version=exact_version,
        project_identity=project_identity,
        module_id=module_id,
    )
    if selection_diagnostics is not None:
        selection_diagnostics.update(selection.audit_manifest())
    normalized_scoped, _ = normalize_candidates(scoped_items, result_kind="patch_context")
    scoped_by_id = {candidate.stable_id: candidate for candidate in normalized_scoped}
    selector_rejected_critical_facts = sum(
        _critical_fact_count(dict(scoped_by_id[omission.stable_id].original))
        for omission in selection.omissions
        if omission.reason_code == "forbidden_source"
        and omission.stable_id in scoped_by_id
        and scoped_by_id[omission.stable_id].authority == "canonical"
    )
    selector_risky_critical_facts = sum(
        _critical_fact_count(dict(scoped_by_id[omission.stable_id].original))
        for omission in selection.omissions
        if omission.reason_code == "instruction_risk"
        and omission.stable_id in scoped_by_id
        and scoped_by_id[omission.stable_id].authority == "canonical"
    )
    selection_budget_critical_facts = 0
    budget_omission_ids = {
        omission.stable_id
        for omission in selection.omissions
        if omission.reason_code in {"budget", "zero_marginal_utility"}
    }
    if budget_omission_ids:
        selection_budget_critical_facts = sum(
            _critical_fact_count(dict(candidate.original))
            for candidate in normalized_scoped
            if candidate.stable_id in budget_omission_ids and candidate.authority == "canonical"
        )
    if selection.status == "insufficient_evidence":
        retrieval_issue_list.extend(
            f"Missing required evidence: {requirement}"
            for requirement in selection.missing_requirements
        )
        retrieval_issue_list.extend(
            f"Unresolved evidence conflict: {conflict}"
            for conflict in selection.unresolved_conflicts
        )
    scoped_items = selection.selected_items
    authority_conflicts = _authority_conflicts(scoped_items, trust_contract or {})
    rejected_sources = _rejected_source_keys(trust_contract or {})
    rejected_critical_facts = selector_rejected_critical_facts + sum(
        _critical_fact_count(item)
        for item in scoped_items
        if _declares_canonical_authority(item) and _item_source_keys(item) & rejected_sources
    )
    items = _rank_and_dedupe(scoped_items, trust_contract or {})
    items.sort(key=lambda item: (
        0 if _normalized_source_key(_source_path(item)) in required_source_keys else
        1 if _normalized_source_key(_source_path(item)) in required_target_keys else
        2
    ))
    resolved_mutation = resolve_mutation_targets(
        mutation_intent,
        items if mutation_intent.operation != "create" else scoped_items,
        evidence_id_for_item=_evidence_id,
    )
    mutation_readiness = evaluate_mutation_readiness(resolved_mutation)
    objective, objective_omitted = _bounded_text(question.strip(), 1_000)
    source_rows = [_source_row(item) for item in items if _source_path(item)]
    source_rows = _dedupe_dicts(source_rows, ("evidence_id",))

    acceptance_conditions: list[dict[str, Any]] = []
    required: list[dict[str, Any]] = []
    forbidden: list[dict[str, Any]] = []
    compile_checks: list[dict[str, Any]] = []
    test_checks: list[dict[str, Any]] = []
    semantic_checks: list[dict[str, Any]] = []
    guidance: list[dict[str, Any]] = []
    critical_fact_omissions = 0
    snippet_omissions = 0
    risky_content_omissions = 0
    risky_critical_omissions = selector_risky_critical_facts
    untrusted_validation_omissions = 0
    for item in items:
        evidence_id = _evidence_id(item) if _source_path(item) else None
        if not evidence_id:
            continue
        facts, omitted_facts = _extract_facts(_content_text(item))
        if _instruction_risk_flags(item):
            risky_content_omissions += len(facts) + (1 if item.get("snippet") else 0)
            if _declares_canonical_authority(item):
                risky_critical_omissions += sum(
                    1 for fact_type, _ in facts if fact_type in {"required", "forbidden", "validation"}
                ) + omitted_facts
            continue
        if _authority(item) == "canonical":
            for condition in sorted(_explicit_acceptance_conditions(item)):
                bounded_condition, omitted = _bounded_text(condition, 1_000)
                if omitted:
                    critical_fact_omissions += 1
                    continue
                if _content_instruction_risk_flags(bounded_condition):
                    risky_content_omissions += 1
                    risky_critical_omissions += 1
                    continue
                acceptance_conditions.append({
                    "text": bounded_condition,
                    "evidence_ids": [evidence_id],
                })
        critical_fact_omissions += omitted_facts if _authority(item) == "canonical" else 0
        for fact_type, fact in facts:
            if _content_instruction_risk_flags(fact):
                risky_content_omissions += 1
                if _authority(item) == "canonical":
                    risky_critical_omissions += 1
                continue
            cited = {"text": fact, "evidence_ids": [evidence_id]}
            if _authority(item) != "canonical":
                if fact_type in {"required", "forbidden"}:
                    # Supporting repository documents may inform an edit but
                    # cannot become canonical invariants or prohibitions.
                    # Keep the distinction explicit through the cited source
                    # row's authority instead of silently dropping the fact.
                    guidance.append(cited)
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
        if snippet and _content_instruction_risk_flags(snippet):
            risky_content_omissions += 1
        elif snippet:
            guidance.append({"text": snippet, "evidence_ids": [evidence_id]})

    has_source_backed_constraints = bool(acceptance_conditions or required or forbidden)
    has_resolved_edit_target = any(
        target.binding_kind == "target" and target.exists
        for target in resolved_mutation.resolved_targets
    )
    constraints_only = bool(
        resolved_mutation.operation != "none"
        and not mutation_readiness.ready
        and not has_resolved_edit_target
        and has_source_backed_constraints
    )

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
            "acceptance_conditions": _dedupe_cited(acceptance_conditions, "text"),
        },
        "source_of_truth": source_rows,
        "target_surface": {
            "likely_files": _dedupe_cited([
                {"path": _source_path(item), "evidence_ids": [_evidence_id(item)]}
                for item in items
                if str(item.get("source_class") or "") in _CODE_SOURCE_CLASSES
                and _source_path(item)
                and _editable_target_path(_source_path(item))
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
        "mutation_intent": {
            "operation": resolved_mutation.operation,
            "artifact_kind": resolved_mutation.artifact_kind,
            "requested_targets": [asdict(item) for item in resolved_mutation.requested_targets],
            "resolved_targets": [asdict(item) for item in resolved_mutation.resolved_targets],
            "preserved_targets": [asdict(item) for item in resolved_mutation.preserved_targets],
            "destination": resolved_mutation.destination,
            "acceptance_conditions": list(resolved_mutation.acceptance_conditions),
            "request_plan": (
                {
                    **resolved_mutation.request_plan.hash_payload,
                    "plan_hash": resolved_mutation.request_plan.plan_hash,
                }
                if (
                    resolved_mutation.request_plan is not None
                    and resolved_mutation.request_plan.preserve_targets
                ) else None
            ),
            "ready": mutation_readiness.ready,
            "constraints_only": constraints_only,
            "missing": list(mutation_readiness.missing),
            "contract_hash": mutation_readiness.contract_hash,
        },
        "uncertainties": [],
        "missing_evidence": [],
        "omitted_counts": {},
        "estimated_tokens": 0,
    }
    mandatory_guidance = _add_mandatory_requirement_witnesses(packet, selection)
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
        ("critical_source_facts", selection_budget_critical_facts),
        ("required_invariants", selection_budget_critical_facts),
    ):
        if count:
            packet["omitted_counts"][field] = count
            if packet["status"] == "ok":
                packet["status"] = "truncated"

    if (
        critical_fact_omissions
        or filtered_critical_facts
        or rejected_critical_facts
        or risky_critical_omissions
        or selection_budget_critical_facts
    ):
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

    for issue in retrieval_issue_list[:5]:
        text, _ = _bounded_text(str(issue).strip(), 240)
        if text and text not in packet["missing_evidence"]:
            packet["missing_evidence"].append(text)
    if packet["missing_evidence"]:
        packet["status"] = "insufficient_evidence"

    if resolved_mutation.operation != "none" and not mutation_readiness.ready:
        packet["status"] = "insufficient_evidence"
        for reason in mutation_readiness.missing:
            message = f"Mutation target readiness is incomplete: {reason}."
            if message not in packet["missing_evidence"]:
                packet["missing_evidence"].append(message)
        if constraints_only:
            message = "Documentation constraints do not authorize or identify the requested edit target."
            if message not in packet["missing_evidence"]:
                packet["missing_evidence"].append(message)

    available_paths = {_normalized_source_key(_source_path(item)) for item in items}
    missing_required_sources = sorted(required_source_keys - available_paths)
    missing_required_targets = sorted(required_target_keys - available_paths)
    if missing_required_sources:
        packet["status"] = "insufficient_evidence"
        packet["missing_evidence"].append(
            "Required evidence paths were not retrieved: " + ", ".join(missing_required_sources)
        )
    if missing_required_targets:
        packet["status"] = "insufficient_evidence"
        packet["missing_evidence"].append(
            "Required target paths were not retrieved: " + ", ".join(missing_required_targets)
        )

    _prune_orphan_sources(packet, required_source_keys)

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
    if behavioral_contract_required and not _has_behavioral_contract(packet):
        packet["status"] = "insufficient_evidence"
        message = "Source-backed behavioral contract is required before editing."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)

    _fit_packet(
        packet, budget, required_source_keys, required_target_keys,
        mandatory_guidance,
    )
    _ensure_post_fit_status(packet, required_source_keys)
    _refresh_estimated_tokens(packet)
    # Account for the estimate field itself. If it crosses the caller budget,
    # remove another complete item and recompute rather than slicing text.
    while packet["estimated_tokens"] > budget and _remove_one_budget_item(
        packet, required_source_keys, required_target_keys, mandatory_guidance
    ):
        _refresh_estimated_tokens(packet)
    _ensure_selection_survives_packet(packet, selection)
    if behavioral_contract_required and not _has_behavioral_contract(packet):
        packet["status"] = "insufficient_evidence"
        message = "Source-backed behavioral contract is required before editing."
        if message not in packet["missing_evidence"]:
            packet["missing_evidence"].append(message)
    _refresh_estimated_tokens(packet)
    if packet["estimated_tokens"] > budget:
        _compact_failure_packet(packet, budget)
    if selection_diagnostics is not None:
        selection_diagnostics["mutation_intent"] = {
            "contract_hash": mutation_readiness.contract_hash,
            "operation": resolved_mutation.operation,
            "artifact_kind": resolved_mutation.artifact_kind,
            "ready": mutation_readiness.ready,
            "missing": list(mutation_readiness.missing),
        }
    return packet


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
                    _content_text(evidence_map.get(ref, {}))
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
                    _content_text(evidence_map.get(ref, {}))
                )[0]
                for ref in refs
            ):
                errors.append(f"validation.{field} contains a command not present in its cited evidence")
                break
    for item in _cited_dict_items(packet.get("implementation_guidance")):
        text = str(item.get("text") or "")
        if any(
            text != _snippet_text(evidence_map.get(ref, {}).get("snippet"))[0]
            and text not in _content_text(evidence_map.get(ref, {}))
            and text not in {
                fact for _, fact in _extract_facts(
                    _content_text(evidence_map.get(ref, {}))
                )[0]
            }
            for ref in _string_refs(item)
        ):
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

__all__=['build_action_packet', '_object_field', '_validate_cited_items', '_all_cited_items', '_cited_dict_items', '_string_refs', '_validate_evidence_fidelity']
