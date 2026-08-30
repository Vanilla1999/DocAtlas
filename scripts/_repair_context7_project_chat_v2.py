#!/usr/bin/env python3
"""Finish the one-PR retrieval-first change and remove itself afterwards."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:120]!r}")
    write(path, content.replace(old, new, 1))


def main() -> None:
    # If the preceding workflow could not commit its staged patch, recover it
    # here before applying the final delivery guard.
    if not (ROOT / "docmancer/docs/domain/project_retrieval_intent.py").exists():
        staged = ROOT / "scripts/_apply_context7_project_chat_v2.py"
        if not staged.is_file():
            raise RuntimeError("base retrieval-first patch is absent")
        subprocess.run(["python", str(staged)], cwd=ROOT, check=True)

    intent_path = "docmancer/docs/domain/project_retrieval_intent.py"
    intent = read(intent_path)
    if "def project_retrieval_requires_context_only(" not in intent:
        replace_once(
            intent_path,
            '\n\n__all__ = ["ProjectRetrievalAlias", "build_project_retrieval_aliases"]\n',
            '''\n\ndef project_retrieval_requires_context_only(question: str) -> bool:\n    """Return whether retrieval is useful but complete answer certification is too strong."""\n\n    return any(\n        alias.force_context_only\n        for alias in build_project_retrieval_aliases(question)\n    )\n\n\n__all__ = [\n    "ProjectRetrievalAlias",\n    "build_project_retrieval_aliases",\n    "project_retrieval_requires_context_only",\n]\n''',
        )

    context_path = "docmancer/docs/interfaces/mcp/context_tools.py"
    context = read(context_path)
    if "project_retrieval_requires_context_only" not in context:
        replace_once(
            context_path,
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\n"
            "from docmancer.docs.application.docs_context_projection import project_docs_context\n"
            "from docmancer.docs.domain.project_retrieval_intent import (\n"
            "    project_retrieval_requires_context_only,\n"
            ")\n",
        )

    context = read(context_path)
    guard_marker = "            force_context_only = project_retrieval_requires_context_only(question)\n"
    if guard_marker not in context:
        start = context.index('        if kind == "docs_answer":\n')
        end = context.index("\n        packet_budget =", start)
        block = context[start:end]
        block = block.replace(
            '        if kind == "docs_answer":\n            selection_trace: dict[str, Any] = {}\n',
            '        if kind == "docs_answer":\n'
            '            force_context_only = project_retrieval_requires_context_only(question)\n'
            '            selection_trace: dict[str, Any] = {}\n',
            1,
        )
        needle = '            raw.setdefault("retrieval_diagnostics", {})["evidence_selection"] = selection_trace\n'
        if block.count(needle) != 1:
            raise RuntimeError("could not locate docs-answer selection trace")
        block = block.replace(
            needle,
            '            if force_context_only:\n'
            '                projection, snapshot = project_docs_context(\n'
            '                    retrieval=raw, max_tokens=min(800, output_budget),\n'
            '                )\n'
            + needle,
            1,
        )
        validation_arg = '                canonical_selection=canonical_selection,\n'
        if block.count(validation_arg) < 2:
            raise RuntimeError("expected project and validation canonical-selection arguments")
        prefix, suffix = block.rsplit(validation_arg, 1)
        block = (
            prefix
            + '                canonical_selection=(\n'
              '                    None if force_context_only else canonical_selection\n'
              '                ),\n'
            + suffix
        )
        write(context_path, context[:start] + block + context[end:])

    tests_path = "tests/docs/test_context7_style_project_chat.py"
    tests = read(tests_path)
    if "test_broad_retrieval_intent_requires_context_only_delivery" not in tests:
        tests = tests.replace(
            "from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases\n",
            "from docmancer.docs.domain.project_retrieval_intent import (\n"
            "    build_project_retrieval_aliases,\n"
            "    project_retrieval_requires_context_only,\n"
            ")\n",
            1,
        )
        tests += '''\n\ndef test_broad_retrieval_intent_requires_context_only_delivery():\n    assert project_retrieval_requires_context_only(\n        "Где хранится индекс и как он изолирован для каждого проекта?"\n    ) is True\n    assert project_retrieval_requires_context_only(\n        "Какая команда запускает Docs MCP сервер?"\n    ) is False\n'''
        write(tests_path, tests)

    print("context-only delivery guard applied")


if __name__ == "__main__":
    main()
