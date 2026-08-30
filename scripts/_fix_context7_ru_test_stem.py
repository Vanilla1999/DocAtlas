#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    intent = ROOT / "docmancer/docs/domain/project_retrieval_intent.py"
    if not intent.exists():
        for candidate in ROOT.glob("scripts/_*context7*project_chat*v2.py"):
            subprocess.run(["python", str(candidate)], cwd=ROOT, check=True)
            if intent.exists():
                break
    text = intent.read_text(encoding="utf-8")
    text = text.replace(
        'if _has(tokens, "тест", "test", "pytest") and not any(row.intent_id == "pytest_markers" for row in rows):',
        'if _has(tokens, "тест", "протест", "test", "pytest") and not any(row.intent_id == "pytest_markers" for row in rows):',
    )
    text = text.replace(
        '            (("тест",), "testing"),',
        '            (("тест", "протест"), "testing"),',
    )
    intent.write_text(text, encoding="utf-8")

    tests = ROOT / "tests/docs/test_context7_style_project_chat.py"
    value = tests.read_text(encoding="utf-8")
    row = '        ("Что нужно протестировать перед открытием pull request?", "testing_contribution"),\n'
    marker = '        ("Архитектура?", "project_architecture"),\n'
    if row not in value:
        if marker not in value:
            raise RuntimeError("parameter marker missing")
        value = value.replace(marker, row + marker, 1)
        tests.write_text(value, encoding="utf-8")


if __name__ == "__main__":
    main()
