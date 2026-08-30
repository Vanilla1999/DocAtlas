#!/usr/bin/env python3
"""Apply the final compatibility-preserving parser guard for PR #173."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    value = read(path)
    count = value.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    write(path, value.replace(old, new, 1))


def main() -> None:
    if not (ROOT / "docmancer/docs/domain/project_retrieval_intent.py").exists():
        for candidate in (
            ROOT / "scripts/_repair_context7_project_chat_v2.py",
            ROOT / "scripts/_apply_context7_project_chat_v2.py",
        ):
            if candidate.is_file():
                subprocess.run(["python", str(candidate)], cwd=ROOT, check=True)
                break
        else:
            raise RuntimeError("retrieval-first implementation is missing")

    shared = "docmancer/docs/domain/_project_answer_contract_shared.py"
    value = read(shared)
    narrowed = 'r"\\b(?:tools|инструмент(?:ы|ов))\\b", re.I,'
    original = 'r"\\b(?:tools|commands|methods|инструмент(?:ы|ов)|команд(?:ы|ах))\\b", re.I,'
    if narrowed in value:
        value = value.replace(narrowed, original, 1)
        write(shared, value)

    part = "docmancer/docs/domain/_project_answer_contract_part02.py"
    value = read(part)
    old = '''    inventory_noun = _PLURAL_TOOL_RE.search(raw_question)\n    surface_inventory = re.search(r"\\b(?:tool(?:s)?(?:[- ]\\w+){0,5}\\s+surface|three[- ]tool(?:[- ]\\w+){0,5}\\s+surface|public(?:[- ]\\w+){0,5}\\s+surface)\\b", raw_question, re.I)\n    if not command_question and (inventory_noun or surface_inventory) and _INVENTORY_RE.search(raw_question):\n'''
    new = '''    inventory_noun = _PLURAL_TOOL_RE.search(raw_question)\n    surface_inventory = re.search(r"\\b(?:tool(?:s)?(?:[- ]\\w+){0,5}\\s+surface|three[- ]tool(?:[- ]\\w+){0,5}\\s+surface|public(?:[- ]\\w+){0,5}\\s+surface)\\b", raw_question, re.I)\n    generic_command_inventory = re.search(\n        r"\\b(?:commands?|methods?|команд(?:ы|а|ах|у)?|метод(?:ы|а|ов)?)\\b",\n        raw_question,\n        re.I,\n    )\n    explicit_public_tool_context = bool(\n        surface_inventory\n        or re.search(\n            r"\\b(?:MCP|Docs\\s+MCP|public\\s+tools?|public\\s+commands?|"\n            r"публичн\\w*\\s+(?:инструмент|команд)\\w*)\\b",\n            raw_question,\n            re.I,\n        )\n    )\n    if (\n        not command_question\n        and (inventory_noun or surface_inventory)\n        and _INVENTORY_RE.search(raw_question)\n        and (not generic_command_inventory or explicit_public_tool_context)\n    ):\n'''
    if old in value:
        value = value.replace(old, new, 1)
        write(part, value)
    elif "generic_command_inventory = re.search(" not in value:
        raise RuntimeError("inventory guard insertion point not found")

    tests = "tests/docs/test_context7_style_project_chat.py"
    value = read(tests)
    marker = "def test_explicit_docs_mcp_tool_inventory_remains_supported():\n"
    extra = '''def test_explicit_docs_mcp_command_inventory_remains_supported():\n    contract = build_project_answer_contract(\n        "What public commands does Docs MCP expose?"\n    )\n\n    assert any(\n        obligation.attribute == "public_tools"\n        for obligation in contract.proof_obligations\n    )\n\n\n'''
    if extra not in value:
        if marker not in value:
            raise RuntimeError("test insertion marker not found")
        value = value.replace(marker, extra + marker, 1)
        write(tests, value)

    print("precise command inventory guard applied")


if __name__ == "__main__":
    main()
