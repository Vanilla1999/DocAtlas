from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

TEST_MODULE = "tests/docs/test_projection_structural_completion.py"
MANIFEST = "tests/diagnostic_labels.projection_structural_completion.json"


def node_digest(module: str) -> str:
    tree = ast.parse(Path(module).read_text(encoding="utf-8"))
    nodes = [
        f"{module}::{node.name}"
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    return hashlib.sha256("\n".join(sorted(nodes)).encode()).hexdigest()


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"{path}: expected one replacement, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def write_tests() -> None:
    item = (
        "5. If the result is `docs_context`, answer only claims directly grounded in its "
        "returned sources, cite their paths, and do not claim complete or verified coverage; "
        "it never authorizes an edit. If the result is `insufficient_evidence`, do not claim "
        "documentation support. Follow at most one non-automatic `rephrase_question` recovery "
        "for parser/retrieval uncertainty; if it still fails and `hard_stop=false`, continue "
        "repository investigation with local source/tests while keeping the documentary claim "
        "unproved. Stop before an edit when `hard_stop=true` or when the task explicitly requires "
        "a documentary contract that remains unproved."
    )
    content = f'''from docmancer.docs.domain.context_windows import (\n    _is_complete_source_span,\n    _projection_limits,\n)\n\n\nITEM = {item!r}\n\n\ndef test_numbered_list_item_is_a_complete_source_local_span():\n    text = "4. Previous independent rule.\\n" + ITEM + "\\n6. Next independent rule."\n    assert 520 < len(ITEM) <= 704\n    assert len(ITEM) in _projection_limits(ITEM)\n    assert _is_complete_source_span(text, ITEM) is True\n\n\ndef test_prefix_of_numbered_list_item_is_not_complete():\n    text = "4. Previous independent rule.\\n" + ITEM + "\\n6. Next independent rule."\n    prefix = ITEM[:520].rsplit(" ", 1)[0]\n    assert _is_complete_source_span(text, prefix) is False\n'''
    Path(TEST_MODULE).write_text(content, encoding="utf-8")
    payload = {
        "schema_version": 1,
        "module_labels": {TEST_MODULE: "behavioral"},
        "node_overrides": {},
        "module_node_hashes": {TEST_MODULE: node_digest(TEST_MODULE)},
    }
    Path(MANIFEST).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def apply_fix() -> None:
    replace_once(
        "docmancer/docs/domain/context_windows.py",
        '''    left = text[:start]\n    right = text[end:]\n    left_complete = not left.strip() or left.endswith("\\n\\n")\n    stripped = snippet.rstrip()\n    right_complete = (\n        not right.strip()\n        or right.startswith("\\n\\n")\n        or stripped.endswith((".", "!", "?", "|", "```", "~~~"))\n    )\n    return left_complete and right_complete''',
        '''    left = text[:start]\n    right = text[end:]\n    stripped = snippet.rstrip()\n    list_item = bool(re.match(r"(?:[-*+]\\s+|\\d+[.)]\\s+)", snippet.lstrip()))\n    line_start = text.rfind("\\n", 0, start) + 1\n    starts_at_line_item = list_item and not text[line_start:start].strip()\n    left_complete = (\n        not left.strip()\n        or left.endswith("\\n\\n")\n        or starts_at_line_item\n    )\n    next_list_item = bool(re.match(\n        r"\\n[ \\t]*(?:[-*+]\\s+|\\d+[.)]\\s+)", right, re.M,\n    ))\n    right_complete = (\n        not right.strip()\n        or right.startswith("\\n\\n")\n        or stripped.endswith((".", "!", "?", "|", "```", "~~~"))\n        or (list_item and next_list_item)\n    )\n    return left_complete and right_complete''',
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("tests", "fix"))
    args = parser.parse_args()
    if args.mode == "tests":
        write_tests()
    else:
        apply_fix()
    print(f"projection TDD {args.mode} complete")


if __name__ == "__main__":
    main()
