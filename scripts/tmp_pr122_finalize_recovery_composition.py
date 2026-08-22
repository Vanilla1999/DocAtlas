from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_TOOLS = ROOT / "docmancer/docs/interfaces/mcp/context_tools.py"
RECOVERY_PROJECTION = ROOT / "docmancer/docs/interfaces/mcp/recovery_projection.py"
TEST_FILE = ROOT / "tests/docs/test_model_visible_projection.py"

MODULE_RECOVERY_CONSTANTS = '''_MODULE_RECOVERY_REASON_CODES = frozenset({
    "module_ambiguous", "module_not_found", "no_module_docs",
})
_MODULE_RECOVERY_MISSING = "Select an exact module_path and retry."
_MODULE_RECOVERY_SUPPORT_SUMMARY_KEYS = frozenset({
    "answer_supported", "answer_available", "support_status", "reason_code",
    "decision_hash",
})
'''

MODULE_RECOVERY_FUNCTIONS = '''def _bound_module_recovery_projection(
    payload: dict[str, Any],
    *,
    max_tokens: int,
) -> None:
    """Keep an executable recovery action and complete exact module locators."""

    reason = str(payload.get("operational_reason_code") or "")
    if reason not in _MODULE_RECOVERY_REASON_CODES:
        return
    rows = payload.get("module_candidates")
    candidates = [
        deepcopy(row)
        for row in rows or []
        if isinstance(row, dict) and str(row.get("module_path") or "").strip()
    ]
    if not candidates:
        return

    limit = min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max(1, int(max_tokens)))
    for key in SUPPORT_ENVELOPE_KEYS:
        if key not in _MODULE_RECOVERY_SUPPORT_SUMMARY_KEYS:
            payload.pop(key, None)
    payload.pop("support_envelope", None)
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) <= limit:
        return

    missing = payload.get("missing")
    if isinstance(missing, list):
        payload["missing"] = missing[:1] or [_MODULE_RECOVERY_MISSING]
    action = payload.get("recommended_next_action")
    if isinstance(action, dict):
        for key in (
            "type", "reason", "message", "confirmation_reason", "agent_question",
            "observations", "security_scope", "decision_options",
        ):
            action.pop(key, None)
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) <= limit:
        return

    for row in candidates:
        row.pop("module_name", None)
        row.pop("module_type", None)
    payload["module_candidates"] = candidates
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) <= limit:
        return

    # Preserve the complete ambiguity set whenever the requested budget allows it.
    # Compact surrounding diagnostics before sacrificing candidate coverage.
    for key in (
        "operational_status", "context_available", "disposition", "edit_ready",
        "source_search_status", "requires_confirmation", "decision_hash", "reason_code",
        "documentation_supported", "investigation_allowed", "hard_stop",
        "recovery_origin", "recovery_reason_code", "recovery_disposition",
    ):
        payload.pop(key, None)
    payload["missing"] = [_MODULE_RECOVERY_MISSING]
    payload["module_candidates"] = candidates
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) <= limit:
        return

    # A tight budget keeps one complete exact locator. Never truncate a path.
    candidates.sort(
        key=lambda row: (len(str(row["module_path"])), str(row["module_path"]))
    )
    payload["module_candidates"] = [candidates[0]]
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) <= limit:
        return

    minimal_action = payload.get("recommended_next_action")
    if isinstance(minimal_action, dict):
        minimal_action = {
            key: deepcopy(minimal_action[key])
            for key in ("tool", "arguments_patch", "requires_confirmation", "auto_execute")
            if key in minimal_action
        }
    kind = payload.get("kind")
    payload.clear()
    payload.update({
        "status": "insufficient_evidence",
        "kind": "docs_answer" if kind == "docs_answer" else "patch_context",
        "missing": [_MODULE_RECOVERY_MISSING],
        "answer_supported": False,
        "answer_available": False,
        "support_status": "insufficient_evidence",
        "operational_reason_code": reason,
        "module_candidates": [candidates[0]],
        "estimated_tokens": 0,
    })
    if minimal_action:
        payload["recommended_next_action"] = minimal_action
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) > limit:
        raise ValueError("minimum module-recovery projection exceeds the requested budget")


def _bound_recoverable_insufficient_projection(
    payload: dict[str, Any],
    *,
    max_tokens: int,
) -> None:
    """Make module-aware recovery the final step after generic compaction."""

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
    # Module ambiguity is an MCP recovery extension, so restore its immutable
    # snapshot afterwards and make the module-aware budget pass authoritative.
    bound_insufficient_projection(payload, max_tokens=max_tokens)
    if reason not in _MODULE_RECOVERY_REASON_CODES or not candidates:
        return

    payload["operational_reason_code"] = reason
    payload["module_candidates"] = candidates
    if operational_action is not None:
        payload["recommended_next_action"] = operational_action
    _bound_module_recovery_projection(payload, max_tokens=max_tokens)
'''

CONTEXT_CONSTANTS = '''_MODULE_RECOVERY_REASON_CODES = frozenset({
    "module_ambiguous", "module_not_found", "no_module_docs",
})
_MODULE_RECOVERY_MISSING = "Select an exact module_path and retry."
_MODULE_RECOVERY_SUPPORT_SUMMARY_KEYS = frozenset({
    "answer_supported", "answer_available", "support_status", "reason_code",
    "decision_hash",
})
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


def patch_recovery_projection() -> None:
    text = RECOVERY_PROJECTION.read_text(encoding="utf-8")
    old_import = (
        "from docmancer.docs.application.model_visible_projection import "
        "estimate_projection_tokens"
    )
    new_import = '''from docmancer.docs.application.model_visible_projection import (
    INSUFFICIENT_EVIDENCE_MAX_TOKENS,
    SUPPORT_ENVELOPE_KEYS,
    bound_insufficient_projection,
    estimate_projection_tokens,
)'''
    if text.count(old_import) != 1:
        raise SystemExit("recovery projection import target drifted")
    text = text.replace(old_import, new_import, 1)

    constants_marker = '''_RECOVERY_SUMMARY_KEYS = (
    "documentation_supported", "investigation_allowed", "hard_stop",
    "recovery_origin", "recovery_reason_code", "recovery_disposition",
)
'''
    if text.count(constants_marker) != 1:
        raise SystemExit("recovery projection constants target drifted")
    text = text.replace(
        constants_marker,
        constants_marker + "\n" + MODULE_RECOVERY_CONSTANTS,
        1,
    )

    function_marker = "\n\ndef _attach_recovery_diagnosis(\n"
    if text.count(function_marker) != 1:
        raise SystemExit("recovery projection function target drifted")
    text = text.replace(
        function_marker,
        "\n\n" + MODULE_RECOVERY_FUNCTIONS + function_marker,
        1,
    )

    old_all = '''__all__ = [
    "_annotate_recovery_handoff",
    "_attach_recovery_diagnosis",
    "_recovery_summary",
    "is_operational_recovery_action",
]
'''
    new_all = '''__all__ = [
    "_MODULE_RECOVERY_REASON_CODES",
    "_annotate_recovery_handoff",
    "_attach_recovery_diagnosis",
    "_bound_module_recovery_projection",
    "_bound_recoverable_insufficient_projection",
    "_recovery_summary",
    "is_operational_recovery_action",
]
'''
    if text.count(old_all) != 1:
        raise SystemExit("recovery projection exports target drifted")
    RECOVERY_PROJECTION.write_text(text.replace(old_all, new_all, 1), encoding="utf-8")


def patch_context_tools() -> None:
    text = CONTEXT_TOOLS.read_text(encoding="utf-8")
    old_import = '''from docmancer.docs.interfaces.mcp.recovery_projection import (
    _annotate_recovery_handoff,
    _attach_recovery_diagnosis,
    _recovery_summary,
    is_operational_recovery_action,
)'''
    new_import = '''from docmancer.docs.interfaces.mcp.recovery_projection import (
    _MODULE_RECOVERY_REASON_CODES,
    _annotate_recovery_handoff,
    _attach_recovery_diagnosis,
    _bound_recoverable_insufficient_projection,
    _recovery_summary,
    is_operational_recovery_action,
)'''
    if text.count(old_import) != 1:
        raise SystemExit("context_tools recovery import target drifted")
    text = text.replace(old_import, new_import, 1)

    if text.count(CONTEXT_CONSTANTS) != 1:
        raise SystemExit("context_tools module recovery constants target drifted")
    text = text.replace(CONTEXT_CONSTANTS + "\n", "", 1)

    helper_pattern = re.compile(
        r"\n\ndef _bound_module_recovery_projection\(.*?"
        r"\n\ndef context_tools\(tools: list\[dict\[str, Any\]\]\) -> list\[dict\[str, Any\]\]:",
        re.DOTALL,
    )
    replacement = (
        "\n\ndef context_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:"
    )
    text, helper_count = helper_pattern.subn(replacement, text)
    if helper_count != 1:
        raise SystemExit(f"expected one context_tools recovery helper, found {helper_count}")

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
        "from docmancer.docs.interfaces.mcp.recovery_projection import "
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
    TEST_FILE.write_text(text.replace(old_assertions, new_assertions, 1), encoding="utf-8")


def main() -> None:
    patch_recovery_projection()
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
        str(RECOVERY_PROJECTION.relative_to(ROOT)),
        str(TEST_FILE.relative_to(ROOT)),
    )
    run("git", "commit", "-m", "fix: preserve module recovery after generic compaction")
    run("git", "push", "origin", "HEAD:p0/recoverable-docs-failures")


if __name__ == "__main__":
    main()
