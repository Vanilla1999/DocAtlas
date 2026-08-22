from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_TOOLS = ROOT / "docmancer/docs/interfaces/mcp/context_tools.py"
TEST_FILE = ROOT / "tests/docs/test_model_visible_projection.py"

WRAPPER = '''def _bound_recoverable_insufficient_projection(
    payload: dict[str, Any],
    *,
    max_tokens: int,
) -> None:
    """Apply generic compaction before restoring typed module recovery."""

    reason = str(payload.get("operational_reason_code") or "")
    rows = payload.get("module_candidates")
    candidates = [
        deepcopy(row)
        for row in rows or []
        if isinstance(row, dict) and str(row.get("module_path") or "").strip()
    ]
    action = payload.get("recommended_next_action")
    operational_action = (
        deepcopy(action)
        if is_operational_recovery_action(action)
        else None
    )

    # Generic projection compaction owns ordinary support and failure metadata.
    # Module ambiguity is an interface-specific recovery extension, so restore
    # its immutable snapshot afterwards and make the module-aware pass final.
    bound_insufficient_projection(payload, max_tokens=max_tokens)
    if reason not in _MODULE_RECOVERY_REASON_CODES or not candidates:
        return

    payload["operational_reason_code"] = reason
    payload["module_candidates"] = candidates
    if operational_action is not None:
        payload["recommended_next_action"] = operational_action
    _bound_module_recovery_projection(payload, max_tokens=max_tokens)
'''

CALL_PATTERN = re.compile(
    r"(?m)^(?P<indent> +)_bound_module_recovery_projection\(\n"
    r"(?P=indent)    projection, max_tokens=output_budget,\n"
    r"(?P=indent)\)\n"
    r"(?P=indent)bound_insufficient_projection\("
    r"(?:projection, max_tokens=output_budget\)|\n"
    r"(?P=indent)    projection, max_tokens=output_budget,\n"
    r"(?P=indent)\))"
)


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def patch_context_tools() -> None:
    text = CONTEXT_TOOLS.read_text(encoding="utf-8")
    if "def _bound_recoverable_insufficient_projection(" in text:
        raise SystemExit("recovery composition wrapper already exists")
    marker = "\n\ndef context_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:\n"
    if text.count(marker) != 1:
        raise SystemExit("context_tools insertion target drifted")
    text = text.replace(marker, "\n\n" + WRAPPER + marker, 1)

    def replace_call(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return (
            f"{indent}_bound_recoverable_insufficient_projection(\n"
            f"{indent}    projection, max_tokens=output_budget,\n"
            f"{indent})"
        )

    text, count = CALL_PATTERN.subn(replace_call, text)
    if count != 3:
        raise SystemExit(f"expected 3 production compaction sequences, found {count}")
    CONTEXT_TOOLS.write_text(text, encoding="utf-8")


def patch_test() -> None:
    text = TEST_FILE.read_text(encoding="utf-8")
    old_import = (
        "from docmancer.docs.interfaces.mcp.context_tools import "
        "_bound_module_recovery_projection"
    )
    new_import = (
        "from docmancer.docs.interfaces.mcp.context_tools import "
        "_bound_recoverable_insufficient_projection"
    )
    if text.count(old_import) != 1:
        raise SystemExit("test import target drifted")
    text = text.replace(old_import, new_import, 1)

    old_calls = (
        "    _bound_module_recovery_projection(payload, max_tokens=256)\n"
        "    bound_insufficient_projection(payload, max_tokens=256)\n"
    )
    new_calls = (
        "    _bound_recoverable_insufficient_projection(payload, max_tokens=256)\n"
    )
    if text.count(old_calls) != 1:
        raise SystemExit("test composition target drifted")
    text = text.replace(old_calls, new_calls, 1)

    old_assertions = (
        "    assert visible_paths\n"
        "    assert set(visible_paths) <= set(paths)\n"
    )
    new_assertions = (
        "    assert len(visible_paths) == 1\n"
        "    assert set(visible_paths) <= set(paths)\n"
    )
    if text.count(old_assertions) != 1:
        raise SystemExit("test locator assertion target drifted")
    text = text.replace(old_assertions, new_assertions, 1)
    TEST_FILE.write_text(text, encoding="utf-8")


def main() -> None:
    patch_context_tools()
    patch_test()

    run("python", "-m", "compileall", "-q", "docmancer", "scripts", "tests")
    run("python", "scripts/check_python_module_size.py")
    run(
        "pytest", "-q",
        "tests/docs/test_model_visible_projection.py::test_module_recovery_keeps_action_and_one_complete_exact_path_at_tiny_budget",
    )
    run(
        "pytest", "-q",
        "tests/docs/test_model_visible_projection.py",
        "tests/docs/test_model_visible_projection_part02.py",
    )
    run("python", "scripts/run_recovery_contract_gate.py")
    run("python", "scripts/run_recovery_mutation_gate.py")
    run("python", "scripts/run_agent_developer_adversarial_gate.py")

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run(
        "git", "add",
        str(CONTEXT_TOOLS.relative_to(ROOT)),
        str(TEST_FILE.relative_to(ROOT)),
    )
    run("git", "commit", "-m", "fix: preserve module recovery after generic compaction")
    run("git", "push", "origin", "HEAD:p0/recoverable-docs-failures")


if __name__ == "__main__":
    main()
