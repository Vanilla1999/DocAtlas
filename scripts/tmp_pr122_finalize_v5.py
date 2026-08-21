from __future__ import annotations

import tmp_pr122_finalize as base


def main() -> None:
    base.apply()

    base.replace_once(
        "docmancer/docs/interfaces/mcp/context_tools.py",
        '''        if action.get("tool") == "prepare_docs":
            # Network approval is a user decision, not a callable MCP field.
            # The returned lifecycle action must pass its own public validator.
            arguments.pop("allow_network", None)
            if arguments.get("action") == "prefetch_library_docs" and not arguments.get("question"):
                arguments["question"] = request.get("question")
            return {**action, "arguments_patch": arguments}
''',
        '''        if action.get("tool") == "prepare_docs":
            # Network approval is a user decision, not a callable MCP field.
            # The returned lifecycle action must pass its own public validator.
            arguments.pop("allow_network", None)
            if arguments.get("action") == "prefetch_library_docs" and not arguments.get("question"):
                arguments["question"] = request.get("question")
            prepared = {**action, "arguments_patch": arguments}
            if payload.get("requires_confirmation") and "requires_confirmation" not in prepared:
                prepared["requires_confirmation"] = True
            if payload.get("confirmation_reason") and not prepared.get("confirmation_reason"):
                prepared["confirmation_reason"] = payload["confirmation_reason"]
            return prepared
''',
    )
    base.replace_once(
        "docmancer/docs/interfaces/mcp/context_tools.py",
        '        return {**action, "type": "prepare_docs", "tool": "prepare_docs", "arguments_patch": patch}\n',
        '''        return {
            **action,
            "type": "prepare_docs",
            "tool": "prepare_docs",
            "arguments_patch": patch,
            **({"requires_confirmation": True} if payload.get("requires_confirmation") else {}),
            **({"confirmation_reason": payload["confirmation_reason"]} if payload.get("confirmation_reason") else {}),
        }
''',
    )

    # Canonical requirement identifiers are the most actionable missing evidence.
    # Put the human summary last so ordinary bounded list compaction cannot erase
    # the machine-readable blocker while preserving only generic prose.
    base.replace_once(
        "docmancer/docs/application/model_visible_projection.py",
        '''        missing = [str(retrieval.get("message") or "No complete source-backed documentation answer is available.")]
        missing.extend(decision.missing_requirements)
        missing.extend(decision.unresolved_conflicts)
        missing.extend(retrieval_issues)
''',
        '''        missing = list(decision.missing_requirements)
        missing.extend(decision.unresolved_conflicts)
        missing.extend(retrieval_issues)
        missing.append(str(retrieval.get("message") or "No complete source-backed documentation answer is available."))
''',
    )

    # Keep the large projector orchestration-only: budget-sensitive recovery
    # compaction lives in the bounded helper module extracted by base.apply().
    base.replace_once(
        "docmancer/docs/application/model_visible_projection.py",
        '''from docmancer.docs.application.insufficient_projection import (
    apply_terminal_insufficient_projection,
    bounded_missing_value,
)
''',
        '''from docmancer.docs.application.insufficient_projection import (
    apply_terminal_insufficient_projection,
    bounded_missing_value,
    compact_recovery_action_for_budget,
)
''',
    )
    base.replace_once(
        "docmancer/docs/application/model_visible_projection.py",
        '''    action = payload.get("recommended_next_action")
    original_action = deepcopy(action) if isinstance(action, dict) else None
    if isinstance(action, dict):
        for key in (
            "observations", "decision_options", "agent_question", "security_scope",
            "reason", "confirmation_reason",
        ):
            action.pop(key, None)
            _refresh_estimate(payload)
            if estimate_projection_tokens(payload) <= limit:
                return
    payload.pop("recommended_next_action", None)
    missing = payload.get("missing")
    bounded_missing = bounded_missing_value(missing, default=_MINIMAL_MISSING)
''',
        '''    action = payload.get("recommended_next_action")
    original_action = deepcopy(action) if isinstance(action, dict) else None
    action_fits, protected_confirmation = compact_recovery_action_for_budget(
        payload, limit, estimate_tokens=estimate_projection_tokens, refresh_estimate=_refresh_estimate
    )
    if action_fits:
        return
    if not protected_confirmation:
        payload.pop("recommended_next_action", None)
    missing = payload.get("missing")
    bounded_missing = bounded_missing_value(missing, default=_MINIMAL_MISSING)
''',
    )

    path = "docmancer/docs/application/insufficient_projection.py"
    text = base.read(path)
    insert_at = text.index("\ndef _minimal_rephrase_action")
    compact_helper = '''

def compact_recovery_action_for_budget(
    payload: dict[str, Any],
    limit: int,
    *,
    estimate_tokens: Any,
    refresh_estimate: Any,
) -> tuple[bool, bool]:
    """Compact a recovery action without splitting confirmation semantics."""
    action = payload.get("recommended_next_action")
    if not isinstance(action, dict):
        return False, False
    protected = bool(
        action.get("requires_confirmation") and action.get("confirmation_reason")
    )
    removable = [
        "observations", "decision_options", "agent_question", "security_scope", "reason"
    ]
    if not protected:
        removable.append("confirmation_reason")
    for key in removable:
        action.pop(key, None)
        refresh_estimate(payload)
        if estimate_tokens(payload) <= limit:
            return True, protected
    return False, protected
'''
    text = text[:insert_at] + compact_helper + text[insert_at:]
    start = text.index("def _minimal_rephrase_action")
    end = text.index("\n\ndef apply_terminal_insufficient_projection", start)
    recovery_helper = '''def _minimal_recovery_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("requires_confirmation") and value.get("confirmation_reason"):
        tool = value.get("tool")
        arguments = value.get("arguments_patch") if isinstance(value.get("arguments_patch"), dict) else {}
        if tool in {"prepare_docs", "docs_status"} and arguments:
            return {
                "tool": tool,
                "type": value.get("type") or tool,
                "arguments_patch": deepcopy(arguments),
                "requires_confirmation": True,
                "confirmation_reason": str(value["confirmation_reason"]),
                "auto_execute": False,
            }
    if value.get("type") != "rephrase_question":
        return None
    arguments = value.get("arguments_patch") if isinstance(value.get("arguments_patch"), dict) else {}
    question = str(arguments.get("question") or "")[:320]
    if not question:
        return None
    return {
        "tool": "get_docs_context",
        "type": "rephrase_question",
        "arguments_patch": {"question": question},
        "auto_execute": False,
    }
'''
    text = text[:start] + recovery_helper + text[end:]
    if text.count("_minimal_rephrase_action(original_action)") != 1:
        raise SystemExit("terminal recovery call target drifted")
    text = text.replace(
        "_minimal_rephrase_action(original_action)",
        "_minimal_recovery_action(original_action)",
        1,
    )
    base.write(path, text)

    base.validate()
    base.commit()


if __name__ == "__main__":
    main()
