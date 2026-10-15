#!/usr/bin/env python3
"""Require green full baselines and specific, source-verified mutation failures."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATE = "scripts/run_agent_developer_adversarial_gate.py"
SELF_TEST = (GATE, "--self-test")
FULL_GATE = (GATE,)
ORACLE_FILES = (
    "eval/agent_developer_v1/tasks.json",
    "eval/agent_developer_v1/expected_trajectories.json",
    "eval/agent_developer_v2/cases.json",
)


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    command: tuple[str, ...]
    expected_controls: tuple[str, ...] = ()
    expected_cases: tuple[tuple[str, str], ...] = ()
    expected_v1_tasks: tuple[tuple[str, str], ...] = ()


MUTANTS = (
    Mutant("agent_cost_measurement", GATE,
           "return math.ceil(_projection_bytes(payload, project_path) / 4)",
           "return 0  # mutation: hide delivered DTO cost", SELF_TEST,
           expected_controls=("serialized_cost_measured",)),
    Mutant("agent_source_fidelity", "scripts/run_agent_developer_gate.py",
           '    return errors\n\n\ndef _call_target_mismatches(',
           '    return []  # mutation: accept invented quotes\n\n\ndef _call_target_mismatches(', SELF_TEST,
           expected_controls=("source_quote_fidelity",)),
    Mutant("agent_forbidden_source_guard", GATE,
           "return tuple(sorted(source for source in actual if source in forbidden))",
           "return ()  # mutation: hide foreign source", SELF_TEST,
           expected_controls=("forbidden_source",)),
    Mutant("agent_exact_scope_guard", GATE,
           "def _scope_matches(expected: dict[str, str], actual: dict[str, str]) -> bool:\n    return expected == actual",
           "def _scope_matches(expected: dict[str, str], actual: dict[str, str]) -> bool:\n    return True  # mutation: allow scope drift", SELF_TEST,
           expected_controls=("exact_scope",)),
    Mutant("agent_retry_candidate_guard", GATE,
           "def _retry_candidate_valid(module_path: str, candidates: tuple[str, ...]) -> bool:\n    return module_path in candidates",
           "def _retry_candidate_valid(module_path: str, candidates: tuple[str, ...]) -> bool:\n    return True  # mutation: allow unreturned scope", SELF_TEST,
           expected_controls=("retry_inventory",)),
    Mutant("agent_edit_readiness_guard", GATE,
           "def _edit_safe(payload: dict[str, Any] | None) -> bool:\n    return not base._authorizes_edit(payload)",
           "def _edit_safe(payload: dict[str, Any] | None) -> bool:\n    return True  # mutation: accept edit grant", SELF_TEST,
           expected_controls=("edit_authority",)),
    Mutant("project_exact_module_path_guard", "docmancer/docs/application/_project_docs_service_part01.py",
           '            if item.get("module_path") == requested\n',
           '            if str(item.get("module_path") or "").startswith(requested)  # mutation: prefix selects another module\n', FULL_GATE,
           expected_cases=(("prefix_collision_module_path_rejected", "forbidden_visible_context"),)),
    Mutant("project_status_module_projection_guard", "docmancer/docs/interfaces/mcp/prefetch_tools.py",
           "_DOCS_STATUS_MODULE_LIMIT = 8", "_DOCS_STATUS_MODULE_LIMIT = 0  # mutation: hide exact inventory", FULL_GATE,
           expected_cases=(("ambiguity_recovery_whole_trajectory_budget", "status_inventory"),
                           ("many_auth_ambiguity_bounded_recovery", "status_inventory")),
           expected_v1_tasks=(("ambiguous_module_recovery_named_gap", "status_inventory"),)),
    Mutant("module_recovery_reason_projection_guard", "docmancer/docs/interfaces/mcp/recovery_projection.py",
           '    "module_ambiguous", "module_not_found", "no_module_docs",',
           '    "module_ambiguous", "no_module_docs",  # mutation: hide missing-module reason', FULL_GATE,
           expected_cases=tuple((case_id, "operational reason=") for case_id in (
               "traversal_module_path_rejected", "absolute_module_path_rejected",
               "prefix_collision_module_path_rejected", "case_collision_module_path_rejected",
               "long_missing_module_path_bounded"))),
)


def _ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in {".git", ".venv", ".pytest_cache", "__pycache__"}
               or name.endswith((".pyc", ".pyo"))}
    if Path(directory).relative_to(ROOT) == Path("eval/task_level"):
        ignored.update({"results", "runtime", "workspaces", "oracles", "hidden_tests"})
    return ignored


def _copy_source(destination: Path) -> None:
    for directory in ("docmancer", "eval", "scripts"):
        shutil.copytree(ROOT / directory, destination / directory, ignore=_ignore)
    shutil.copy2(ROOT / "pyproject.toml", destination / "pyproject.toml")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _environment(copy_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(copy_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DOCATLAS_OFFLINE"] = "1"
    return env


def _run(copy_root: Path, command: tuple[str, ...], name: str) -> dict[str, Any]:
    path = copy_root / f"{name}.json"
    completed = subprocess.run(
        [sys.executable, *command, "--output", str(path)], cwd=copy_root,
        env=_environment(copy_root), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=600,
    )
    (copy_root / f"{name}.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (copy_root / f"{name}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if not path.is_file():
        raise RuntimeError("child produced no assertion report (crash/import/setup/timeout is not a kill)")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != 2 or type(report.get("passed")) is not bool:
        raise RuntimeError("child report identity is invalid")
    if completed.returncode != (0 if report["passed"] else 1):
        raise RuntimeError("child exit status contradicts its assertion report")
    if report.get("execution_errors"):
        raise RuntimeError(f"child execution errors are not mutation kills: {report['execution_errors']!r}")
    identities = report.get("execution_identity")
    if not isinstance(identities, dict) or not identities:
        raise RuntimeError("child source/import identity is missing")
    for relative, identity in identities.items():
        expected = (copy_root / relative).resolve()
        if (identity.get("imported_from_checkout") is not True
                or identity.get("imported_path") != str(expected)
                or identity.get("expected_path") != str(expected)
                or identity.get("sha256") != _digest(expected)):
            raise RuntimeError(f"child did not import the expected source: {relative}")
    for relative in ORACLE_FILES:
        if _digest(copy_root / relative) != _digest(ROOT / relative):
            raise RuntimeError(f"oracle changed in the evaluated copy: {relative}")
    return report


def _apply_mutant(copy_root: Path, mutant: Mutant) -> tuple[str, str]:
    path = copy_root / mutant.path
    source = path.read_text(encoding="utf-8")
    if source.count(mutant.old) != 1:
        raise RuntimeError(f"{mutant.name}: mutation anchor must match exactly once")
    changed = source.replace(mutant.old, mutant.new, 1)
    if changed == source:
        raise RuntimeError("no-op mutation")
    ast.parse(changed, filename=str(path))
    before = _digest(path)
    path.write_text(changed, encoding="utf-8")
    return before, _digest(path)


def _unique_rows(rows: Any, key: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("complete nonempty assertion roster is required")
    mapped = {str(row.get(key) or ""): row for row in rows}
    if "" in mapped or len(mapped) != len(rows):
        raise RuntimeError("assertion roster contains duplicates or missing IDs")
    return mapped


def _same_roster(baseline: dict[str, Any], report: dict[str, Any], field: str, key: str) -> tuple[dict, dict]:
    before, after = _unique_rows(baseline.get(field), key), _unique_rows(report.get(field), key)
    if list(before) != list(after):
        raise RuntimeError(f"{field} roster/order changed or cases were skipped")
    return before, after


def _verify_kill(mutant: Mutant, baseline: dict[str, Any], report: dict[str, Any]) -> None:
    if report.get("passed") is not False:
        raise RuntimeError("mutant survived")
    if mutant.command == SELF_TEST:
        _, rows = _same_roster(baseline, report, "checks", "id")
        failed = {key for key, row in rows.items() if row.get("passed") is False}
        if any(type(row.get("passed")) is not bool for row in rows.values()) or failed != set(mutant.expected_controls):
            raise RuntimeError(f"unexpected control failure instead of expected assertion: {failed!r}")
        return
    before, after = _same_roster(baseline, report, "cases", "case_id")
    expected = dict(mutant.expected_cases)
    failed = {key for key, row in after.items() if row.get("passed") is False}
    if failed != set(expected):
        raise RuntimeError(f"unexpected failed cases: {failed!r}; expected={set(expected)!r}")
    for case_id, row in after.items():
        if [event.get("kind") for event in row.get("events") or ()] != [event.get("kind") for event in before[case_id].get("events") or ()]:
            raise RuntimeError(f"event roster changed or recovery was skipped: {case_id}")
        if case_id in expected and not any(expected[case_id] in error for error in row.get("errors") or ()):
            raise RuntimeError(f"expected assertion did not fail: {case_id}")
    baseline_v1, v1 = baseline["v1"]["report"], report["v1"]["report"]
    _, tasks = _same_roster(baseline_v1, v1, "tasks", "task_id")
    _, controls = _same_roster(baseline_v1, v1, "migration_controls", "task_id")
    if any(row.get("target_closed") is not True for row in controls.values()):
        raise RuntimeError("unrelated positive migration control failed")
    failed_tasks = {key for key, row in tasks.items() if row.get("target_closed") is not True}
    if failed_tasks != set(dict(mutant.expected_v1_tasks)):
        raise RuntimeError(f"unexpected v1 task failure: {failed_tasks!r}")
    for task_id, marker in mutant.expected_v1_tasks:
        messages = [message for call in tasks[task_id]["calls"]
                    for message in (call.get("target_mismatches") or []) + ((call.get("recovery") or {}).get("errors") or [])]
        if not any(marker in message for message in messages):
            raise RuntimeError(f"v1 expected assertion did not fail: {task_id}")


def _new_copy() -> Path:
    return Path(tempfile.mkdtemp(prefix="docatlas-agent-v2-mutant-", dir=Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))))


def main() -> int:
    baseline_root = _new_copy()
    try:
        _copy_source(baseline_root)
        baselines = {
            SELF_TEST: _run(baseline_root, SELF_TEST, "baseline-controls"),
            FULL_GATE: _run(baseline_root, FULL_GATE, "baseline-full"),
        }
        if any(report["passed"] is not True for report in baselines.values()):
            raise RuntimeError("both evaluator controls and full public trajectories must have a green baseline")
        for mutant in MUTANTS:
            copy_root = _new_copy()
            try:
                _copy_source(copy_root)
                before, after = _apply_mutant(copy_root, mutant)
                report = _run(copy_root, mutant.command, mutant.name)
                identity = report["execution_identity"].get(mutant.path) or {}
                if before == after or identity.get("sha256") != after:
                    raise RuntimeError("changed source was not imported by the child")
                _verify_kill(mutant, baselines[mutant.command], report)
                print(f"KILLED: {mutant.name}; exact assertion and imported source verified")
            except Exception as exc:
                print(f"MUTATION ERROR: {mutant.name}: {exc}; artifacts={copy_root}", file=sys.stderr)
                return 1
            shutil.rmtree(copy_root)
    except Exception as exc:
        print(f"Agent Developer mutation baseline/error: {exc}; artifacts={baseline_root}", file=sys.stderr)
        return 1
    shutil.rmtree(baseline_root)
    print(f"PASS: full baseline green; {len(MUTANTS)} specifically detected mutants; no crash/skip credit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
