from __future__ import annotations

import tmp_pr122_finalize as base


def main() -> None:
    base.apply()

    # Confirmation belongs to the result envelope but must survive on the
    # concrete public lifecycle action after normalization/compaction.
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
            **(
                {"requires_confirmation": True}
                if payload.get("requires_confirmation") else {}
            ),
            **(
                {"confirmation_reason": payload["confirmation_reason"]}
                if payload.get("confirmation_reason") else {}
            ),
        }
''',
    )

    # A required confirmation is an atomic operational contract. Compact
    # diagnostics first; never keep a callable action while silently dropping
    # why user approval is required.
    base.replace_once(
        "docmancer/docs/application/model_visible_projection.py",
        '''    action = payload.get("recommended_next_action")
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
''',
        '''    action = payload.get("recommended_next_action")
    protected_confirmation = bool(
        isinstance(action, dict)
        and action.get("requires_confirmation")
        and action.get("confirmation_reason")
    )
    if isinstance(action, dict):
        for key in (
            "observations", "decision_options", "agent_question", "security_scope",
            "reason",
        ):
            action.pop(key, None)
            _refresh_estimate(payload)
            if estimate_projection_tokens(payload) <= limit:
                return
        if not protected_confirmation:
            action.pop("confirmation_reason", None)
            _refresh_estimate(payload)
            if estimate_projection_tokens(payload) <= limit:
                return
    if not protected_confirmation:
        payload.pop("recommended_next_action", None)
    missing = payload.get("missing")
''',
    )

    # Terminal fallback must also retain a minimal confirmation action if all
    # less important public metadata had to be discarded.
    path = "docmancer/docs/application/insufficient_projection.py"
    text = base.read(path)
    old = '''def _minimal_rephrase_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("type") != "rephrase_question":
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
    new = '''def _minimal_recovery_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("requires_confirmation") and value.get("confirmation_reason"):
        tool = value.get("tool")
        arguments = (
            value.get("arguments_patch")
            if isinstance(value.get("arguments_patch"), dict)
            else {}
        )
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
    arguments = (
        value.get("arguments_patch")
        if isinstance(value.get("arguments_patch"), dict)
        else {}
    )
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
    if text.count(old) != 1:
        raise SystemExit("insufficient projection recovery helper target drifted")
    text = text.replace(old, new, 1)
    text = text.replace(
        "    minimal_recovery = _minimal_rephrase_action(original_action)\n",
        "    minimal_recovery = _minimal_recovery_action(original_action)\n",
        1,
    )
    base.write(path, text)

    base.validate()
    base.commit()


if __name__ == "__main__":
    main()
