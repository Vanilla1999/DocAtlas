from __future__ import annotations

import tmp_pr122_finalize as base


def main() -> None:
    base.apply()
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
