#!/usr/bin/env python3
"""Public-boundary trajectories: original tasks, explicit membership, fidelity and cost."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
from collections import defaultdict, deque
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.run_agent_developer_gate as base  # noqa: E402

CASES_PATH = REPO_ROOT / "eval" / "agent_developer_v2" / "cases.json"
PROJECT_PATH_MARKER = "$PROJECT_PATH"
_EXECUTION_MODULES = {
    "scripts/run_agent_developer_adversarial_gate.py": __name__,
    "scripts/run_agent_developer_gate.py": "scripts.run_agent_developer_gate",
    "docmancer/docs/application/_project_docs_service_part01.py": "docmancer.docs.application._project_docs_service_part01",
    "docmancer/docs/interfaces/mcp/prefetch_tools.py": "docmancer.docs.interfaces.mcp.prefetch_tools",
    "docmancer/docs/interfaces/mcp/recovery_projection.py": "docmancer.docs.interfaces.mcp.recovery_projection",
}


def _execution_identity() -> dict[str, Any]:
    """The child identifies the source it imported, including mutation targets."""
    rows = {}
    for path, name in _EXECUTION_MODULES.items():
        module = sys.modules.get(name)
        location = getattr(module, "__file__", None)
        actual = Path(location).resolve() if location else None
        expected = (REPO_ROOT / path).resolve()
        rows[path] = {
            "imported_path": str(actual) if actual else None,
            "expected_path": str(expected),
            "imported_from_checkout": actual == expected,
            "sha256": hashlib.sha256(actual.read_bytes()).hexdigest() if actual else None,
        }
    return rows


def _contaminated_sources(actual: tuple[str, ...], forbidden: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(source for source in actual if source in forbidden))


def _scope_matches(expected: dict[str, str], actual: dict[str, str]) -> bool:
    return expected == actual


def _retry_candidate_valid(module_path: str, candidates: tuple[str, ...]) -> bool:
    return module_path in candidates


def _edit_safe(payload: dict[str, Any] | None) -> bool:
    return not base._authorizes_edit(payload)


def _normalized_for_tokens(value: Any, project_path: str) -> Any:
    if isinstance(value, str):
        return value.replace(project_path, PROJECT_PATH_MARKER) if project_path else value
    if isinstance(value, dict):
        return {str(key): _normalized_for_tokens(child, project_path) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalized_for_tokens(child, project_path) for child in value]
    return value


def _projection_bytes(payload: dict[str, Any] | None, project_path: str) -> int:
    if not isinstance(payload, dict):
        return 0
    normalized = _normalized_for_tokens(payload, project_path)
    return len(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _projection_tokens(payload: dict[str, Any] | None, project_path: str) -> int:
    # Independent measurement: an absent or false estimated_tokens field cannot
    # turn a delivered DTO into zero cost. This is an estimate, not client usage.
    return math.ceil(_projection_bytes(payload, project_path) / 4)


def self_test() -> dict[str, Any]:
    """Named positive/negative controls for the evaluator, not the product gate."""
    with TemporaryDirectory(prefix="docatlas-agent-controls-") as raw_tmp:
        root = Path(raw_tmp)
        source = root / "README.md"
        source.write_text("# Boundary\n\nOriginal complete fact.\n", encoding="utf-8")
        good = {"sources": [{
            "path_or_url": "README.md", "snippet": "Original complete fact.",
            "line_start": 3, "line_end": 3, "content_sha256": "a" * 64,
            "project_identity": "local:" + hashlib.sha256(str(root).encode()).hexdigest(),
            "evidence_id": "ev-control", "version_binding": "unversioned",
        }]}
        bad = json.loads(json.dumps(good))
        bad["sources"][0]["snippet"] = "Invented fact."
        read_only_call = {"target_expected_status": "ok", "target_read_only": True}
        read_only_payload = {"status": "ok", "kind": "docs_context", "context_available": True,
                             "support_status": "retrieval_only", **good}
        status_payload = {"tool": "docs_status", "action": "project",
                          "project": {"project_path": str(root), "project_docs": {"modules": [
                              {"module_path": "packages/auth"}, {"module_path": "services/auth"},
                          ]}}}
        raw_fidelity_checks = []
        for path, ending, changed_ending in (
            ("raw-lf.md", "\n", "\r\n"), ("raw-crlf.md", "\r\n", "\n"),
        ):
            text = "Raw λ source fact."
            (root / path).write_bytes(("# Raw source" + ending + ending + text + ending).encode("utf-8"))
            row = {**good["sources"][0], "path_or_url": path, "snippet": text + ending}
            raw_fidelity_checks.append(not base._source_fidelity_mismatches({"sources": [row]}, root))
            for changes in (
                {"line_start": 1, "line_end": 1},
                {"line_end": 4},
                {"snippet": text + changed_ending},
            ):
                raw_fidelity_checks.append(bool(base._source_fidelity_mismatches(
                    {"sources": [{**row, **changes}]}, root)))
        checks = [
            ("serialized_cost_measured", _projection_tokens({"estimated_tokens": 0, "sources": ["x" * 1000]}, "") > 250
             and _projection_tokens({"estimated_tokens": 1}, "") > 1),
            ("source_quote_fidelity", not base._source_fidelity_mismatches(good, root)
             and bool(base._source_fidelity_mismatches(bad, root)) and all(raw_fidelity_checks)),
            ("forbidden_source", _contaminated_sources(("docs/a.md", "docs/b.md"), ("docs/b.md",)) == ("docs/b.md",)
             and not _contaminated_sources(("docs/a.md",), ("docs/b.md",))),
            ("exact_scope", not _scope_matches({"scope": "module", "module_path": "packages/orders"}, {"scope": "project"})
             and _scope_matches({"scope": "module", "module_path": "packages/orders"}, {"scope": "module", "module_path": "packages/orders"})),
            ("retry_inventory", not _retry_candidate_valid("packages/auth", ("services/auth",))
             and _retry_candidate_valid("packages/auth", ("packages/auth", "services/auth"))
             and not base._status_binding_mismatches(status_payload, project_path=str(root))
             and all(base._status_binding_mismatches({**status_payload, **change}, project_path=str(root))
                     for change in ({"tool": "get_docs_context"}, {"action": "library"},
                                    {"project": {**status_payload["project"], "project_path": "foreign-project"}},
                                    {"status": "failed"}, {"error": {"reason_code": "permission_denied"}}))),
            ("edit_authority", _edit_safe({"status": "insufficient_evidence", "edit_ready": False})
             and not _edit_safe({"status": "insufficient_evidence", "edit_ready": True})
             and all(not _edit_safe({"edit_ready": False, flag: True}) for flag in (
                 "mutation_ready", "mutation_authorized", "edit_authorized", "authorized",
                 "authorization_granted", "can_edit"))
             and not _edit_safe({"edit_ready": False, "authorized_actions": ["edit"]})
             and not base._call_target_mismatches(read_only_call, read_only_payload, project_path=str(root))
             and any(error.startswith("retrieval_only_answer:") for error in base._call_target_mismatches(
                 read_only_call, {**read_only_payload, "answer": "Unsupported server-composed answer."},
                 project_path=str(root)))
             and any(error.startswith("retrieval_only_kind:") for error in base._call_target_mismatches(
                 read_only_call, {**read_only_payload, "kind": "docs_answer"}, project_path=str(root)))),
            ("setup_confinement", base._safe_fixture_path(root, "README.md") is not None
             and base._safe_fixture_path(root, "../outside.md") is None
             and base._safe_fixture_path(root, "/absolute.md") is None),
            ("original_fact_required", bool(base._call_target_mismatches(
                {"target_expected_status": "ok", "target_required_facts": ["Original complete fact."]},
                {"status": "ok", "sources": [{"snippet": "Other fact."}]}, project_path=str(root)))),
        ]
    return {"schema_version": 2, "protocol": "agent-developer-evaluator-controls",
            "checks": [{"id": name, "passed": bool(passed)} for name, passed in checks],
            "passed": all(passed for _, passed in checks), "execution_identity": _execution_identity()}


def _load_cases() -> dict[str, Any]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("protocol") != "agent-developer-adversarial-v2":
        raise ValueError("adversarial protocol identity mismatch")
    if payload.get("cost_policy", {}).get("fixed_output_ceiling", "missing") is not None:
        raise ValueError("output cost policy must be measurement-only")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("adversarial protocol requires cases")
    seen: set[str] = set()
    for case in cases:
        case_id = str(case.get("id") or "")
        if not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate adversarial case id: {case_id!r}")
        seen.add(case_id)
        calls = case.get("calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError(f"{case_id}: calls are required")
        planned = 0
        for call in calls:
            if not isinstance(call, dict) or not str(call.get("question") or ""):
                raise ValueError(f"{case_id}: invalid context call")
            planned += 1
            if call.get("recovery") is not None:
                recovery = call["recovery"]
                if not isinstance(recovery, dict) or not isinstance(recovery.get("retry"), dict):
                    raise ValueError(f"{case_id}: recovery requires retry")
                planned += 1
        if not 1 <= planned <= int(case.get("max_get_docs_context_calls") or 0):
            raise ValueError(f"{case_id}: planned calls exceed operational call budget")
        rows = case.get("setup_files") or []
        if not isinstance(rows, list) or len(rows) > 24:
            raise ValueError(f"{case_id}: invalid setup_files bound")
    return payload


def _v1_event_plan() -> deque[dict[str, Any]]:
    protocol = base._load_protocol()
    events: deque[dict[str, Any]] = deque()
    for task in [*protocol["tasks"], *protocol["migration_controls"]]:
        for call in task["calls"]:
            events.append({"task_id": task["id"], "kind": "context", "call": call})
            recovery = call.get("target_recovery")
            if isinstance(recovery, dict):
                events.append({"task_id": task["id"], "kind": "docs_status"})
                events.append({"task_id": task["id"], "kind": "context", "call": recovery["retry"]})
    return events


def _capture_v1_token_contract() -> dict[str, Any]:
    events = _v1_event_plan()
    originals = (base.handle_context_tool, base.handle_prefetch_tool)
    records: list[dict[str, Any]] = []
    totals: dict[str, int] = defaultdict(int)
    violations: list[str] = []

    def record(kind: str, name: str, args: dict[str, Any], service: Any) -> dict[str, Any]:
        if not events or events[0]["kind"] != kind:
            raise RuntimeError("v1 public event order differs from the authored plan")
        event = events.popleft()
        if kind == "context" and not _scope_matches(base._scope_signature(event["call"]), base._scope_signature(args)):
            violations.append(f"{event['task_id']}: public scope drift")
        payload = originals[0 if kind == "context" else 1](name, args, service)
        project = str(args.get("project_path") or "")
        tokens = _projection_tokens(payload, project)
        totals[event["task_id"]] += tokens
        records.append({"task_id": event["task_id"], "kind": kind, "tokens": tokens,
                        "utf8_bytes": _projection_bytes(payload, project)})
        return payload

    base.handle_context_tool = lambda name, args, service: record("context", name, args, service)
    base.handle_prefetch_tool = lambda name, args, service: record("docs_status", name, args, service)
    try:
        report = base.run_protocol()
    finally:
        base.handle_context_tool, base.handle_prefetch_tool = originals
    if events:
        violations.append(f"v1 public event plan left {len(events)} unconsumed events")
    if not report.get("target_ok") or not report.get("migration_controls_ok"):
        violations.append("Agent Developer Protocol v1 or required migration controls are not target-green")
    violations.extend(f"v1: {message}" for message in report.get("errors") or ())
    for task in [*report.get("tasks", []), *report.get("migration_controls", [])]:
        for call in task.get("calls") or ():
            violations.extend(f"v1/{task['task_id']}: {message}"
                              for message in call.get("target_mismatches") or ())
    return {"target_ok": bool(report.get("target_ok")), "task_count": report["task_count"],
            "events": records, "trajectory_tokens": dict(sorted(totals.items())),
            "max_trajectory_tokens": max(totals.values(), default=0), "violations": violations,
            "report": report}


def _safe_setup_path(project: Path, raw_path: Any) -> Path | None:
    return base._safe_fixture_path(project, raw_path)


def _apply_setup_files(project: Path, rows: Any) -> None:
    if rows in (None, []):
        return
    if not isinstance(rows, list) or len(rows) > 24:
        raise ValueError("setup_files must contain at most 24 files")
    seen: set[Path] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"path", "content"}:
            raise ValueError(f"setup_files[{index}] must contain exactly path and content")
        target = _safe_setup_path(project, row.get("path"))
        content = row.get("content")
        if target is None or target in seen:
            raise ValueError(f"setup_files[{index}] path is unsafe or duplicate")
        if not isinstance(content, str) or len(content.encode("utf-8")) > 4096:
            raise ValueError(f"setup_files[{index}] exceeds the fixture input bound")
        seen.add(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _apply_setup_catalog(project: Path, rows: Any) -> None:
    """Only explicitly authored document rows extend the already finite catalog."""
    if rows in (None, []):
        return
    import yaml
    if not isinstance(rows, list) or len(rows) > 24:
        raise ValueError("setup_catalog_documents must contain at most 24 entries")
    path = project / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    existing = {row["path"] for row in catalog["documents"]}
    for row in rows:
        target = _safe_setup_path(project, row.get("path"))
        if target is None or not target.is_file() or target.suffix != ".md" or row["path"] in existing:
            raise ValueError("catalog extension is not a unique explicit documentation file")
        catalog["documents"].append(dict(row))
        existing.add(row["path"])
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")


def _run_adversarial_case(case: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    context_calls = 0
    with TemporaryDirectory(prefix=f"docatlas-agent-v2-{case['id']}-") as raw_tmp, ExitStack() as lifetime:
        tmp, project = Path(raw_tmp), Path(raw_tmp) / "project"
        shutil.copytree(base.PROJECTS_ROOT / case["fixture"], project)
        _apply_setup_files(project, case.get("setup_files"))
        _apply_setup_catalog(project, case.get("setup_catalog_documents"))
        working = _safe_setup_path(project, case.get("working_path"))
        if working is None or not working.is_file():
            raise ValueError("working_path is missing or unsafe")
        service = lifetime.enter_context(base._service(tmp, project))
        mutation = case.get("mutation_before_calls")
        if isinstance(mutation, dict):
            target = _safe_setup_path(project, mutation.get("path"))
            if target is None or not target.is_file():
                raise ValueError("mutation target is missing or unsafe")
            with target.open("a", encoding="utf-8") as stream:
                stream.write(str(mutation.get("append") or ""))

        def context(call: dict[str, Any], kind: str, label: str) -> dict[str, Any]:
            nonlocal context_calls
            args = base._context_args(call, project)
            if not _scope_matches(base._scope_signature(call), base._scope_signature(args)):
                errors.append(f"{label}: public scope drift")
            payload = base.handle_context_tool("get_docs_context", args, service)
            context_calls += 1
            errors.extend(f"{label}: {message}" for message in base._call_target_mismatches(call, payload, project_path=str(project)))
            contaminated = _contaminated_sources(base._source_paths(payload), tuple(call.get("forbidden_sources") or ()))
            if contaminated:
                errors.append(f"{label}: forbidden source contamination {contaminated!r}")
            if not _edit_safe(payload):
                errors.append(f"{label}: context authorized edits")
            events.append({"kind": kind, "tokens": _projection_tokens(payload, str(project)),
                           "utf8_bytes": _projection_bytes(payload, str(project)), "payload": payload,
                           "status": payload.get("status"), "sources": list(base._source_paths(payload))})
            return payload

        for index, call in enumerate(case["calls"], 1):
            payload = context(call, "context", f"call {index}")
            recovery = call.get("recovery")
            if not isinstance(recovery, dict):
                continue
            action = base._recommended_action(payload)
            explicit = recovery.get("status_request")
            action_args = (base._resolved_expected(explicit, str(project)) if isinstance(explicit, dict)
                           else action.get("arguments_patch") if action.get("tool") == "docs_status" else None)
            if not isinstance(action_args, dict):
                errors.append(f"call {index}: recovery lacks an explicit or returned docs_status request")
                continue
            status = base.handle_prefetch_tool("docs_status", action_args, service)
            errors.extend(f"call {index}: {message}" for message in base._status_binding_mismatches(
                status, project_path=str(project)))
            modules = tuple(sorted(base._status_module_paths(status)))
            expected = tuple(sorted(recovery.get("expected_module_paths") or ()))
            if not expected or modules != expected:
                errors.append(f"call {index}: status_inventory: modules={modules!r} expected={expected!r}")
            events.append({"kind": "docs_status", "tokens": _projection_tokens(status, str(project)),
                           "utf8_bytes": _projection_bytes(status, str(project)), "modules": list(modules), "payload": status})
            retry = recovery["retry"]
            candidates = modules if isinstance(explicit, dict) else base._module_candidate_paths(payload)
            if not _retry_candidate_valid(str(retry.get("module_path") or ""), candidates):
                errors.append(f"call {index}: retry_inventory: exact retry path was not returned")
            context(retry, "retry", f"call {index}: retry")
        if context_calls > int(case["max_get_docs_context_calls"]):
            errors.append("operational context-call budget exceeded")
    return {"case_id": case["id"], "class": case["class"], "passed": not errors,
            "context_call_count": context_calls, "trajectory_tokens": sum(row["tokens"] for row in events),
            "trajectory_utf8_bytes": sum(row["utf8_bytes"] for row in events), "events": events, "errors": errors,
            "historical_max_trajectory_tokens": case["historical_max_trajectory_tokens"]}


def run_gate() -> dict[str, Any]:
    protocol = _load_cases()
    execution_errors: list[dict[str, str]] = []
    try:
        v1 = _capture_v1_token_contract()
    except Exception as exc:
        execution_errors.append({"case_id": "v1", "exception": type(exc).__name__, "message": str(exc)})
        v1 = {"target_ok": False, "task_count": 0, "max_trajectory_tokens": 0,
              "violations": ["v1 execution error"], "report": {}}
    cases = []
    for case in protocol["cases"]:
        try:
            cases.append(_run_adversarial_case(case))
        except Exception as exc:
            execution_errors.append({"case_id": case["id"], "exception": type(exc).__name__, "message": str(exc)})
            cases.append({"case_id": case["id"], "passed": False, "trajectory_tokens": 0,
                          "events": [], "errors": ["execution error; not an assertion failure"]})
    errors = list(v1["violations"])
    for case in cases:
        errors.extend(f"{case['case_id']}: {message}" for message in case["errors"])
    return {"schema_version": 2, "protocol": "agent-developer-adversarial-v2",
            "cost_policy": protocol["cost_policy"], "v1_target_ok": v1["target_ok"],
            "v1_task_count": v1["task_count"], "v1_max_trajectory_tokens": v1["max_trajectory_tokens"],
            "adversarial_case_count": len(cases), "adversarial_passed_cases": sum(row["passed"] for row in cases),
            "adversarial_max_trajectory_tokens": max(row["trajectory_tokens"] for row in cases),
            "passed": not errors and not execution_errors, "errors": errors, "execution_errors": execution_errors,
            "v1": v1, "cases": cases, "execution_identity": _execution_identity()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = self_test() if args.self_test else run_gate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for error in report.get("errors") or ():
        print(f"- {error}")
    for check in report.get("checks") or ():
        print(f"{check['id']}: {'PASS' if check['passed'] else 'FAIL'}")
    if not args.self_test:
        print(f"v1={report['v1_task_count']}; adversarial={report['adversarial_passed_cases']}/{report['adversarial_case_count']}; "
              f"maximum estimated trajectory tokens={report['adversarial_max_trajectory_tokens']}; output ceiling=none")
    print(f"Agent Developer adversarial v2: {'PASS' if report['passed'] else 'FAIL'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
