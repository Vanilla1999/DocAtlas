from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

from eval.task_level._execution_part01 import (
    _command_fingerprint,
    _shell_command,
    _shell_outcome,
    _test_runner,
    _unwrap_shell_command,
)


PROCESS_QUALITY_SCHEMA_VERSION = "task-process-quality-1"
_EXPLORATION_COMMAND_RE = re.compile(
    r"(?:^|[;&|]\s*)(?:[^\s]+/)?(?:rg|grep|find|fd|ls|sed|cat|head|tail)\b",
    re.IGNORECASE,
)


def _load_events(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            events.append(row)
    return events


def _is_edit_event(event: dict[str, Any]) -> bool:
    tool_name = str(
        event.get("tool_name") or event.get("name") or event.get("tool") or ""
    ).casefold()
    arguments = event.get("arguments") if isinstance(event.get("arguments"), dict) else {}
    changes = arguments.get("changes")
    return (
        bool(changes) if isinstance(changes, list) else False
    ) or any(marker in tool_name for marker in ("edit", "apply_patch", "write_file", "file_change"))


def _test_observations(
    events: list[dict[str, Any]],
) -> list[tuple[int, str, str, bool | None]]:
    observed: list[tuple[int, str, str, bool | None]] = []
    for index, event in enumerate(events):
        command = _shell_command(event)
        if command is None:
            continue
        runner = _test_runner(command)
        if runner is None:
            continue
        observed.append((index, command, runner, _shell_outcome(event)))
    return observed


def _repair_count(
    events: list[dict[str, Any]],
    tests: list[tuple[int, str, str, bool | None]],
) -> int:
    repairs = 0
    pending: set[str] = set()
    repair_started: set[str] = set()
    tests_by_index = {row[0]: row for row in tests}
    for index, event in enumerate(events):
        if _is_edit_event(event):
            newly_repaired = pending - repair_started
            repairs += len(newly_repaired)
            repair_started.update(newly_repaired)
        test = tests_by_index.get(index)
        if test is None or test[3] is None:
            continue
        identity = _test_identity(test[1], test[2])
        if test[3] is True:
            pending.discard(identity)
            repair_started.discard(identity)
        else:
            pending.add(identity)
            repair_started.discard(identity)
    return repairs


def _first_edit_correctness(
    events: list[dict[str, Any]],
    tests: list[tuple[int, str, str, bool | None]],
) -> tuple[bool | None, str]:
    edit_indexes = [index for index, event in enumerate(events) if _is_edit_event(event)]
    if not edit_indexes:
        return None, "not_observed:no_edit"
    first_edit = edit_indexes[0]
    next_edit = edit_indexes[1] if len(edit_indexes) > 1 else len(events)
    validations = [
        outcome
        for index, _, _, outcome in tests
        if first_edit < index < next_edit and outcome is not None
    ]
    if not validations:
        return None, "not_observed:no_validation_before_next_edit"
    return all(validations), "observed"


def _test_identity(command: str, runner: str) -> str:
    """Identify the exercised test surface while ignoring presentation flags."""

    try:
        tokens = shlex.split(_unwrap_shell_command(command))
    except ValueError:
        return _command_fingerprint(command)
    selectors = sorted(
        token for token in tokens[1:]
        if not token.startswith("-") and token not in {"true", "false"}
    )
    return json.dumps([runner, selectors], separators=(",", ":"))


def _regression_count(tests: list[tuple[int, str, str, bool | None]]) -> int:
    previous_outcomes: dict[str, bool] = {}
    regressions = 0
    for _, command, runner, outcome in tests:
        identity = _test_identity(command, runner) if command else runner
        if outcome is None:
            continue
        if outcome is False and previous_outcomes.get(identity) is True:
            regressions += 1
        previous_outcomes[identity] = outcome
    return regressions


def evaluate_process_quality(
    result: dict[str, Any],
    *,
    trajectory_path: Path | None,
) -> dict[str, Any]:
    """Measure observable agent process quality without inferring missing events."""

    events = _load_events(trajectory_path)
    tests = _test_observations(events)
    first_edit_correctness, first_edit_status = _first_edit_correctness(events, tests)
    repair_count = _repair_count(events, tests)
    regression_count = _regression_count(tests)

    distinct_commands = sorted({
        _command_fingerprint(command)
        for _, command, _, _ in tests
        if command
    })
    runners = sorted({runner for _, _, runner, _ in tests})
    known_outcomes = sum(1 for _, _, _, outcome in tests if outcome is not None)

    exploration_calls = 0
    for event in events:
        command = _shell_command(event)
        if command is None:
            continue
        normalized = _unwrap_shell_command(command)
        if _EXPLORATION_COMMAND_RE.search(normalized):
            exploration_calls += 1

    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    required_found = metrics.get("required_evidence_found")
    required_total = metrics.get("required_evidence_total")
    required_found = required_found if isinstance(required_found, int) and not isinstance(required_found, bool) else None
    required_total = required_total if isinstance(required_total, int) and not isinstance(required_total, bool) else None
    evidence_recall = (
        required_found / required_total
        if required_found is not None and required_total not in (None, 0)
        else None
    )
    evidence_per_exploration = (
        required_found / exploration_calls
        if required_found is not None and exploration_calls > 0
        else None
    )

    uncached_input = metrics.get("uncached_input_tokens")
    output_tokens = metrics.get("output_tokens")
    uncached_input = uncached_input if isinstance(uncached_input, int) and not isinstance(uncached_input, bool) else None
    output_tokens = output_tokens if isinstance(output_tokens, int) and not isinstance(output_tokens, bool) else None

    final_correctness = bool(result.get("resolved"))
    forbidden = result.get("forbidden_changes")
    forbidden_count = len(forbidden) if isinstance(forbidden, list) else 0
    patch_robust = bool(
        final_correctness
        and forbidden_count == 0
        and regression_count == 0
    )

    return {
        "schema_version": PROCESS_QUALITY_SCHEMA_VERSION,
        "final_correctness": final_correctness,
        "first_edit_correctness": first_edit_correctness,
        "first_edit_correctness_status": first_edit_status,
        "repair_count": repair_count,
        "regression_count": regression_count,
        "validation_breadth": {
            "test_runs_observed": len(tests),
            "known_test_outcomes": known_outcomes,
            "distinct_test_commands": len(distinct_commands),
            "distinct_test_command_hashes": distinct_commands,
            "test_runners": runners,
        },
        "patch_robustness": {
            "robust": patch_robust,
            "final_correctness": final_correctness,
            "public_tests_passed": bool(result.get("public_tests_passed")),
            "hidden_tests_passed": bool(result.get("hidden_tests_passed")),
            "compile_success": result.get("compile_success"),
            "forbidden_change_count": forbidden_count,
            "repair_count": repair_count,
            "regression_count": regression_count,
        },
        "search_efficiency": {
            "required_evidence_found": required_found,
            "required_evidence_total": required_total,
            "required_evidence_recall": evidence_recall,
            "exploration_calls": exploration_calls,
            "evidence_found_per_exploration_call": evidence_per_exploration,
        },
        "provider_efficiency": {
            "uncached_input_tokens": uncached_input,
            "output_tokens": output_tokens,
            "correct_run": final_correctness,
            "uncached_tokens_per_correct_run": uncached_input if final_correctness else None,
            "correct_runs_per_100k_uncached_tokens": (
                round(100_000 / uncached_input, 6)
                if final_correctness and uncached_input and uncached_input > 0
                else 0.0 if uncached_input and uncached_input > 0 else None
            ),
        },
        "observation": {
            "trajectory_available": bool(events),
            "event_count": len(events),
            "edit_events": sum(1 for event in events if _is_edit_event(event)),
        },
    }


__all__ = ["PROCESS_QUALITY_SCHEMA_VERSION", "evaluate_process_quality"]
