#!/usr/bin/env python3
"""Provider-free Task 42 evidence-selection acceptance harness."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application.model_visible_projection import (
    project_docs_answer,
    project_patch_context,
    validate_model_visible_projection,
)
from eval.parent_child_index_grid import run_grid


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "evidence_selection"
CASE_FILES = ("docs_cases.json", "patch_cases.json", "adversarial_cases.json")
CODE_FILES = (
    "docmancer/docs/application/evidence_selection.py",
    "docmancer/docs/application/action_packet.py",
    "docmancer/docs/application/model_visible_projection.py",
    "docmancer/docs/interfaces/mcp/context_tools.py",
)
COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases() -> tuple[list[dict[str, Any]], dict[str, str]]:
    cases: list[dict[str, Any]] = []
    digests: dict[str, str] = {}
    for name in CASE_FILES:
        path = DATA / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases.extend(payload["cases"])
        digests[name] = _digest(path)
    return cases, digests


def _task41_baseline_gate(
    task41_report: dict[str, Any],
    selected_variant: dict[str, Any] | None,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    expected_commit_sha = str(baseline.get("commit_sha") or "")
    observed_commit_sha = str(task41_report.get("published_commit_sha") or "")
    commit_sha_match = (
        COMMIT_SHA_PATTERN.fullmatch(expected_commit_sha) is not None
        and observed_commit_sha == expected_commit_sha
    )
    candidate_trace_hash = str(
        (selected_variant or {}).get("candidate_trace_hash") or ""
    )
    retrieval_config_hash = str(
        (selected_variant or {}).get("retrieval_config_hash") or ""
    )
    baseline_match = (
        task41_report.get("status") == "PASS"
        and commit_sha_match
        and candidate_trace_hash == baseline.get("task41_candidate_trace_hash")
        and retrieval_config_hash == baseline.get("retrieval_config_hash")
    )
    return {
        "status": task41_report.get("status"),
        "expected_commit_sha": expected_commit_sha,
        "observed_commit_sha": observed_commit_sha,
        "commit_sha_match": commit_sha_match,
        "candidate_trace_hash": candidate_trace_hash,
        "retrieval_config_hash": retrieval_config_hash,
        "baseline_match": baseline_match,
    }


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    kind = case["result_kind"]
    maximum = int(case["maximum_visible_tokens"])
    candidates = [_host_bind_candidate(item) for item in case["candidates"]]
    trust_contract = {"sources": {"rejected": [
            {"source": source} for source in case.get("forbidden_sources", [])
    ]}}
    started = time.perf_counter_ns()
    trace: dict[str, Any] = {}
    validation_errors: list[str] = []
    if kind == "docs_answer":
        retrieval = {
            "status": "success", "answer_available": True,
            "context_pack": candidates, "trust_contract": trust_contract,
            "docs_exactness": "exact" if case.get("exact_version") else None,
            "requested_version": case.get("exact_version"),
            "required_evidence_paths": case.get("required_evidence_paths", []),
            "required_target_paths": case.get("required_target_paths", []),
            "public_requirements": case.get("required_facts", []),
            "project_identity": case.get("project_identity"),
            "module_id": case.get("module_id"),
        }
        projection, snapshot = project_docs_answer(
            question=case["question"], retrieval=retrieval, max_tokens=maximum,
            selection_diagnostics=trace,
        )
        validation_errors.extend(validate_model_visible_projection(
            projection, snapshot=snapshot,
            max_tokens=300 if projection.get("status") == "insufficient_evidence" else maximum,
        ))
    else:
        packet = build_action_packet(
            question=case["question"], context_pack=candidates,
            trust_contract=trust_contract, max_tokens=maximum,
            project_path=case.get("project_path"),
            required_evidence_paths=case.get("required_evidence_paths", []),
            required_target_paths=case.get("required_target_paths", []),
            public_requirements=case.get("required_facts", []),
            exact_version=case.get("exact_version"), selection_diagnostics=trace,
            project_identity=case.get("project_identity"),
            module_id=case.get("module_id"),
        )
        validation_errors.extend(validate_action_packet(
            packet, evidence_items=candidates, max_tokens=maximum,
            project_path=case.get("project_path"),
        ))
        projection, snapshot = project_patch_context(
            packet=packet, evidence_items=candidates, max_tokens=maximum,
        )
        validation_errors.extend(validate_model_visible_projection(
            projection, snapshot=snapshot,
            max_tokens=300 if projection.get("status") == "insufficient_evidence" else maximum,
        ))
    selector_latency_ns = time.perf_counter_ns() - started
    permuted_case = {**case, "candidates": list(reversed(case["candidates"]))}
    permuted_trace, permuted_projection = _evaluate_projection_only(permuted_case)
    selected = list(trace.get("selected_stable_ids") or [])
    selected_rows = [item for item in candidates if item.get("stable_chunk_id") in selected]
    selected_versions = {str(item.get("version") or "") for item in selected_rows}
    selected_sources = {str(item.get("source") or "").casefold() for item in selected_rows}
    visible_text = json.dumps(projection, ensure_ascii=False, sort_keys=True).casefold()
    required_facts_present = (
        projection.get("status") == "insufficient_evidence"
        or all(str(fact).casefold() in visible_text for fact in case.get("required_facts", []))
    )
    checks = {
        "expected_status": projection.get("status") == case["expected_status"],
        "expected_selected": (
            not case.get("expected_selected")
            or set(selected) == set(case["expected_selected"])
        ),
        "deterministic": (
            _canonical_bytes(trace) == _canonical_bytes(permuted_trace)
            and _canonical_bytes(projection) == _canonical_bytes(permuted_projection)
        ),
        "sufficient_contract": not validation_errors,
        "required_facts_present": required_facts_present,
        "token_ceiling": int(projection.get("estimated_tokens") or maximum + 1) <= (
            300 if projection.get("status") == "insufficient_evidence" else maximum
        ),
        "forbidden_sources": not selected_sources.intersection(
            source.casefold() for source in case.get("forbidden_sources", [])
        ),
        "forbidden_versions": not selected_versions.intersection(case.get("forbidden_versions", [])),
    }
    return {
        "case_id": case["case_id"],
        "result_kind": kind,
        "status": projection.get("status"),
        "selected_stable_ids": selected,
        "selected_tokens": (trace.get("metrics") or {}).get("selected_tokens"),
        "selector_budgeted_tokens": (trace.get("metrics") or {}).get("projected_total_tokens"),
        "legacy_budgeted_tokens": _legacy_budgeted_tokens(case),
        "projected_tokens": projection.get("estimated_tokens"),
        "selector_latency_ns": selector_latency_ns,
        "selector_config_hash": trace.get("selector_config_hash"),
        "candidate_trace_hash": trace.get("candidate_trace_hash"),
        "selection_hash": trace.get("selection_hash"),
        "checks": checks,
        "errors": validation_errors,
        "passed": all(checks.values()),
    }


def evaluate() -> dict[str, Any]:
    cases, digests = load_cases()
    results = [evaluate_case(case) for case in cases]
    baseline = json.loads((DATA / "baseline_v1.json").read_text(encoding="utf-8"))
    digest_match = digests == baseline.get("dataset_digests")
    with tempfile.TemporaryDirectory(prefix="docatlas-task42-task41-") as temporary:
        task41_report = run_grid(Path(temporary) / "task41-grid.json")
    selected_variant = next(
        (
            row for row in task41_report["variants"]
            if row["target_tokens"] == task41_report["selected_target_tokens"]
        ),
        None,
    )
    task41_gate = _task41_baseline_gate(task41_report, selected_variant, baseline)
    groups: dict[str, Any] = {}
    for kind in ("docs_answer", "patch_context"):
        rows = [row for row in results if row["result_kind"] == kind]
        tokens = [row["projected_tokens"] for row in rows]
        selector_budgeted = [row["selector_budgeted_tokens"] for row in rows]
        legacy_budgeted = [row["legacy_budgeted_tokens"] for row in rows]
        groups[kind] = {
            "cases": len(rows),
            "passed": sum(row["passed"] for row in rows),
            "median_projected_tokens": statistics.median(tokens) if tokens else None,
            "maximum_projected_tokens": max(tokens) if tokens else None,
            "median_selector_budgeted_tokens": statistics.median(selector_budgeted) if selector_budgeted else None,
            "median_legacy_budgeted_tokens": statistics.median(legacy_budgeted) if legacy_budgeted else None,
            "median_budgeted_token_reduction": (
                statistics.median(legacy_budgeted) - statistics.median(selector_budgeted)
                if selector_budgeted and legacy_budgeted else None
            ),
        }
    baseline_metrics_match = baseline.get("metrics") == {
        kind: {
            "cases": groups[kind]["cases"],
            "median_legacy_budgeted_tokens": groups[kind]["median_legacy_budgeted_tokens"],
        }
        for kind in groups
    }
    task41_match = task41_gate["baseline_match"]
    token_gate = all(
        row["median_selector_budgeted_tokens"] <= row["median_legacy_budgeted_tokens"]
        for row in groups.values()
    )
    correctness = (
        digest_match and baseline_metrics_match and task41_match and token_gate
        and all(row["passed"] for row in results)
    )
    verdict = "PASS" if correctness and baseline.get("status") == "PASS" else "INCONCLUSIVE" if correctness else "FAIL"
    return {
        "schema_version": "task42-evidence-selection-report-v1",
        "verdict": verdict,
        "correctness_gate": "PASS" if correctness else "FAIL",
        "baseline_status": baseline.get("status"),
        "baseline_dataset_digest_match": digest_match,
        "baseline_metrics_match": baseline_metrics_match,
        "task41_gate": {
            **task41_gate,
            "selected_target_tokens": task41_report["selected_target_tokens"],
        },
        "token_gate": "PASS" if token_gate else "FAIL",
        "dataset_digests": digests,
        "code_digests": {
            name: _digest(REPOSITORY_ROOT / name) for name in CODE_FILES
        },
        "selector_config_hashes": sorted({
            str(row["selector_config_hash"])
            for row in results if row.get("selector_config_hash")
        }),
        "candidate_trace_hashes": sorted({
            str(row["candidate_trace_hash"])
            for row in results if row.get("candidate_trace_hash")
        }),
        "groups": groups,
        "results": results,
    }


def _host_bind_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    item = dict(raw)
    display = str(item.get("display_text") or item.get("code") or item.get("snippet") or item.get("content") or "")
    item.setdefault("content", display)
    if item.get("stable_chunk_id"):
        item.setdefault("display_content_hash", hashlib.sha256(display.encode("utf-8")).hexdigest())
    return item


def _legacy_budgeted_tokens(case: dict[str, Any]) -> int:
    reserve = 120 if case["result_kind"] == "docs_answer" else min(
        300, int(case["maximum_visible_tokens"]) // 3
    )
    selected = case["candidates"][:3] if case["result_kind"] == "docs_answer" else case["candidates"][:12]
    visible = sum(
        max(1, (len(str(
            item.get("display_text") or item.get("code") or item.get("snippet")
            or item.get("content") or ""
        ).encode("utf-8")) + 3) // 4)
        + (88 if case["result_kind"] == "patch_context" else 0)
        for item in selected
    )
    return min(int(case["maximum_visible_tokens"]), reserve + visible)


def _evaluate_projection_only(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    kind = case["result_kind"]
    maximum = int(case["maximum_visible_tokens"])
    candidates = [_host_bind_candidate(item) for item in case["candidates"]]
    trust = {"sources": {"rejected": [
        {"source": source} for source in case.get("forbidden_sources", [])
    ]}}
    trace: dict[str, Any] = {}
    if kind == "docs_answer":
        projection, _ = project_docs_answer(
            question=case["question"],
            retrieval={
                "status": "success", "answer_available": True,
                "context_pack": candidates, "trust_contract": trust,
                "docs_exactness": "exact" if case.get("exact_version") else None,
                "requested_version": case.get("exact_version"),
                "required_evidence_paths": case.get("required_evidence_paths", []),
                "required_target_paths": case.get("required_target_paths", []),
                "public_requirements": case.get("required_facts", []),
                "project_identity": case.get("project_identity"),
                "module_id": case.get("module_id"),
            },
            max_tokens=maximum, selection_diagnostics=trace,
        )
    else:
        packet = build_action_packet(
            question=case["question"], context_pack=candidates,
            trust_contract=trust, max_tokens=maximum,
            project_path=case.get("project_path"),
            required_evidence_paths=case.get("required_evidence_paths", []),
            required_target_paths=case.get("required_target_paths", []),
            public_requirements=case.get("required_facts", []),
            exact_version=case.get("exact_version"), selection_diagnostics=trace,
            project_identity=case.get("project_identity"),
            module_id=case.get("module_id"),
        )
        projection, _ = project_patch_context(
            packet=packet, evidence_items=candidates, max_tokens=maximum,
        )
    return trace, projection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["verdict"] == "PASS" else 1 if report["verdict"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
