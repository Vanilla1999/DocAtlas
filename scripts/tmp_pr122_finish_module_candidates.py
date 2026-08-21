from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docmancer/docs/interfaces/mcp/context_tools.py"

OLD = '''    # Never truncate an exact locator. Prefer the shortest complete candidate
    # when the full ambiguity set cannot fit the model-visible budget.
    candidates.sort(key=lambda row: (len(str(row["module_path"])), str(row["module_path"])))
    payload["module_candidates"] = [candidates[0]]
    _refresh_projection_estimate(payload)
    if payload["estimated_tokens"] <= limit:
        return

    for key in (
        "operational_status", "context_available", "disposition", "edit_ready",
        "source_search_status", "requires_confirmation", "decision_hash", "reason_code",
    ):
        payload.pop(key, None)
    payload["missing"] = [_MODULE_RECOVERY_MISSING]
    _refresh_projection_estimate(payload)
    if payload["estimated_tokens"] <= limit:
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
    _refresh_projection_estimate(payload)
    if payload["estimated_tokens"] > limit:
        raise ValueError("minimum module-recovery projection exceeds the requested budget")
'''

NEW = '''    # Module ambiguity is itself the recovery contract: preserve every complete
    # candidate path and compact surrounding diagnostics before sacrificing the
    # ambiguity set. A caller cannot choose safely from a truncated candidate list.
    for key in (
        "operational_status", "context_available", "disposition", "edit_ready",
        "source_search_status", "requires_confirmation", "decision_hash", "reason_code",
        "documentation_supported", "investigation_allowed", "hard_stop",
        "recovery_origin", "recovery_reason_code", "recovery_disposition",
    ):
        payload.pop(key, None)
    payload["missing"] = [_MODULE_RECOVERY_MISSING]
    payload["module_candidates"] = candidates
    _refresh_projection_estimate(payload)
    if payload["estimated_tokens"] <= limit:
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
        "module_candidates": candidates,
        "estimated_tokens": 0,
    })
    if minimal_action:
        payload["recommended_next_action"] = minimal_action
    _refresh_projection_estimate(payload)
    if payload["estimated_tokens"] > limit:
        raise ValueError("complete module-recovery projection exceeds the requested budget")
'''


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        raise SystemExit("module recovery compaction target drifted")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")

    run("python", "-m", "compileall", "-q", "docmancer", "scripts", "tests")
    run("python", "scripts/check_python_module_size.py")
    run("python", "scripts/run_recovery_contract_gate.py")
    run("python", "scripts/run_agent_developer_adversarial_gate.py")
    run("pytest", "-q", "tests/docs/test_mcp_docs_tools_registration.py")

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "docmancer/docs/interfaces/mcp/context_tools.py")
    run("git", "commit", "-m", "fix: preserve complete module ambiguity recovery")
    run("git", "push", "origin", "HEAD:p0/recoverable-docs-failures")


if __name__ == "__main__":
    main()
