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
    base.validate()
    base.commit()


if __name__ == "__main__":
    main()
