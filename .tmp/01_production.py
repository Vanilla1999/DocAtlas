from pathlib import Path


def r(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: replacement count={text.count(old)}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


r(
    "docmancer/docs/domain/_answer_units_part02.py",
    '''    if not _SOURCE_DOCUMENT_SUBJECT_RE.fullmatch(_normal(obligation.subject)):\n        return None\n    if not _subject_present(obligation, source_text):\n        return None\n    for _start, _end, clause in _bounded_clauses(text):\n        for match in _GENERIC_BEHAVIOR_RE.finditer(clause):\n            if _predicate_has_local_value(match, clause):\n                return clause, _predicate_is_negated(match, clause)\n    return None\n''',
    '''    if not _SOURCE_DOCUMENT_SUBJECT_RE.fullmatch(_normal(obligation.subject)):\n        return None\n    if not _subject_present(obligation, source_text):\n        return None\n    requested_topic = obligation.context or obligation.target or obligation.expected_value\n    for _start, _end, clause in _bounded_clauses(text):\n        if requested_topic and not _contains_term(requested_topic, clause):\n            continue\n        for match in _GENERIC_BEHAVIOR_RE.finditer(clause):\n            if _predicate_has_local_value(match, clause):\n                return clause, _predicate_is_negated(match, clause)\n    return None\n''',
)

r(
    "docmancer/docs/domain/question_plan_proof.py",
    '    """Accept a subject-bound multi-item requirement clause or explicit list."""\n',
    '    """Accept a subject-bound requirement clause or explicit list."""\n',
)
r(
    "docmancer/docs/domain/question_plan_proof.py",
    '        if detail_count >= 2:\n            best_detail_count = max(best_detail_count, detail_count)\n',
    '        if detail_count >= 1:\n            best_detail_count = max(best_detail_count, detail_count)\n',
)
r(
    "docmancer/docs/domain/question_plan_proof.py",
    '    if best_detail_count >= 2:\n        return True, best_detail_count\n',
    '    if best_detail_count >= 1:\n        return True, best_detail_count\n',
)
r(
    "docmancer/docs/domain/question_plan_proof.py",
    '        if detail_count >= 2:\n            return True, detail_count\n',
    '        if detail_count >= 1:\n            return True, detail_count\n',
)

r(
    "docmancer/docs/domain/tool_selection.py",
    '''    if status_action:\n        arguments = dict(normalized.get("arguments_patch") or {})\n        arguments["action"] = status_action\n        normalized.update({\n''',
    '''    if status_action:\n        arguments = dict(normalized.get("arguments_patch") or {})\n        arguments["action"] = status_action\n        if status_action == "project":\n            arguments["details"] = True\n        normalized.update({\n''',
)
r(
    "docmancer/docs/domain/tool_selection.py",
    '''    if next_action_tool == "prepare_docs":\n        return ToolSelectionDecision(\n            tool="prepare_docs",\n            reason_code="returned_next_action",\n            confidence=1.0,\n        )\n''',
    '''    if next_action_tool in PUBLIC_DOCS_TOOLS:\n        return ToolSelectionDecision(\n            tool=next_action_tool,\n            reason_code="returned_next_action",\n            confidence=1.0,\n        )\n''',
)

path = "docmancer/docs/interfaces/mcp/context_tools.py"
anchor = '''def _prioritize_module_recovery_projection(payload: dict[str, Any]) -> None:\n    """Keep actionable module recovery ahead of redundant failure prose."""\n\n    if str(payload.get("operational_reason_code") or "") not in _MODULE_RECOVERY_REASON_CODES:\n        return\n    missing = payload.get("missing")\n    if isinstance(missing, list) and len(missing) > 2:\n        payload["missing"] = missing[:2]\n\n\n'''
helpers = anchor + '''def _minimal_module_recovery_action(action: Any) -> dict[str, Any] | None:\n    """Keep only the callable public recovery contract under tiny budgets."""\n\n    if not isinstance(action, dict) or action.get("tool") != "docs_status":\n        return None\n    result: dict[str, Any] = {\n        "tool": "docs_status",\n        "auto_execute": False,\n    }\n    arguments = action.get("arguments_patch")\n    if isinstance(arguments, dict) and arguments:\n        result["arguments_patch"] = deepcopy(arguments)\n    if action.get("requires_confirmation") is not None:\n        result["requires_confirmation"] = bool(action.get("requires_confirmation"))\n    return result\n\n\ndef _bound_module_recovery_projection(\n    payload: dict[str, Any], *, max_tokens: int\n) -> None:\n    """Bound ambiguity recovery without truncating an exact module path."""\n\n    reason = str(payload.get("operational_reason_code") or "")\n    if reason not in _MODULE_RECOVERY_REASON_CODES:\n        bound_insufficient_projection(payload, max_tokens=max_tokens)\n        return\n\n    limit = min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max(1, int(max_tokens)))\n    action = deepcopy(payload.get("recommended_next_action"))\n    rows = payload.get("module_candidates")\n    candidates = [\n        {"module_path": str(row.get("module_path") or "").strip()}\n        for row in (rows if isinstance(rows, list) else [])[:8]\n        if isinstance(row, dict) and str(row.get("module_path") or "").strip()\n    ]\n    candidates = list({row["module_path"]: row for row in candidates}.values())\n\n    _prioritize_module_recovery_projection(payload)\n    payload["edit_ready"] = False\n    if candidates:\n        payload["module_candidates"] = deepcopy(candidates)\n    _refresh_projection_estimate(payload)\n    while int(payload.get("estimated_tokens") or 0) > limit and len(candidates) > 1:\n        candidates.pop()\n        payload["module_candidates"] = deepcopy(candidates)\n        _refresh_projection_estimate(payload)\n    if int(payload.get("estimated_tokens") or 0) <= limit:\n        return\n\n    payload.pop("module_candidates", None)\n    bound_insufficient_projection(payload, max_tokens=limit)\n    payload["operational_reason_code"] = reason\n    payload["edit_ready"] = False\n    if action is not None:\n        payload["recommended_next_action"] = action\n    _refresh_projection_estimate(payload)\n\n    if int(payload.get("estimated_tokens") or 0) > limit:\n        minimal_action = _minimal_module_recovery_action(action)\n        missing = payload.get("missing")\n        first_missing = (\n            str(missing[0]).strip()\n            if isinstance(missing, list) and missing and str(missing[0]).strip()\n            else "Required source-backed evidence is unavailable."\n        )\n        kind = payload.get("kind")\n        payload.clear()\n        payload.update({\n            "status": "insufficient_evidence",\n            "kind": "docs_answer" if kind == "docs_answer" else "patch_context",\n            "missing": [first_missing],\n            "answer_supported": False,\n            "answer_available": False,\n            "support_status": "insufficient_evidence",\n            "operational_reason_code": reason,\n            "edit_ready": False,\n            "estimated_tokens": 0,\n        })\n        if minimal_action is not None:\n            payload["recommended_next_action"] = minimal_action\n        _refresh_projection_estimate(payload)\n        if int(payload.get("estimated_tokens") or 0) > limit:\n            raise ValueError("minimum module-recovery projection exceeds the requested budget")\n\n    fitted: list[dict[str, str]] = []\n    for candidate in candidates:\n        trial = [*fitted, candidate]\n        payload["module_candidates"] = trial\n        _refresh_projection_estimate(payload)\n        if int(payload.get("estimated_tokens") or 0) <= limit:\n            fitted = trial\n        else:\n            payload.pop("module_candidates", None)\n            if fitted:\n                payload["module_candidates"] = fitted\n            _refresh_projection_estimate(payload)\n    if not fitted:\n        payload.pop("module_candidates", None)\n        _refresh_projection_estimate(payload)\n\n\ndef _bound_agent_insufficient_projection(\n    payload: dict[str, Any], *, max_tokens: int\n) -> None:\n    if str(payload.get("operational_reason_code") or "") in _MODULE_RECOVERY_REASON_CODES:\n        _bound_module_recovery_projection(payload, max_tokens=max_tokens)\n    else:\n        bound_insufficient_projection(payload, max_tokens=max_tokens)\n\n\n'''
r(path, anchor, helpers)
r(
    path,
    '''                _prioritize_module_recovery_projection(projection)\n                bound_insufficient_projection(projection, max_tokens=output_budget)\n            if projection.get("status") == "insufficient_evidence":\n                _prioritize_module_recovery_projection(projection)\n                bound_insufficient_projection(\n                    projection, max_tokens=output_budget,\n                )\n''',
    '''                _prioritize_module_recovery_projection(projection)\n                _bound_agent_insufficient_projection(\n                    projection, max_tokens=output_budget,\n                )\n            if projection.get("status") == "insufficient_evidence":\n                _prioritize_module_recovery_projection(projection)\n                _bound_agent_insufficient_projection(\n                    projection, max_tokens=output_budget,\n                )\n''',
)
