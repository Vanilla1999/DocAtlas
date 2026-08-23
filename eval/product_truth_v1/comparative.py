from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from eval.product_truth_v1.positive_controls import load_json, load_tasks, task_budgets
from eval.product_truth_v1.task_pack import verify_report as verify_task_pack


SCHEMA_VERSION = 1
PROTOCOL = "product-truth-comparative-harness-v1"
EXPECTED_CONDITIONS = (
    "A_repo_only",
    "B_repo_plus_docatlas",
    "C_repo_plus_external_docs",
    "D_code_context_plus_docatlas",
)
CODING_TOOLS = ("read", "search", "edit", "shell")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _conditions(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows = protocol.get("conditions")
    if not isinstance(rows, list) or tuple(row.get("id") for row in rows) != EXPECTED_CONDITIONS:
        raise ValueError("P2.2A condition identity or order changed")
    allowed = {
        "A_repo_only": (False, False, False),
        "B_repo_plus_docatlas": (True, False, False),
        "C_repo_plus_external_docs": (False, True, False),
        "D_code_context_plus_docatlas": (True, False, True),
    }
    normalized: list[dict[str, Any]] = []
    for row in rows:
        flags = (
            row.get("docatlas") is True,
            row.get("external_docs") is True,
            row.get("code_context_engine") is True,
        )
        if flags != allowed[str(row["id"])]:
            raise ValueError(f"P2.2A condition capability drift: {row.get('id')}")
        normalized.append({
            "id": str(row["id"]),
            "label": str(row["label"]),
            "evidence": str(row["evidence"]),
            "docatlas": bool(row["docatlas"]),
            "external_docs": bool(row["external_docs"]),
            "code_context_engine": bool(row["code_context_engine"]),
        })
    return normalized


def _block_sort_key(seed: str, block_id: str) -> str:
    return hashlib.sha256(f"{seed}:{block_id}".encode()).hexdigest()


def _balanced_orders(block_ids: Sequence[str], condition_ids: Sequence[str], seed: str) -> dict[str, list[str]]:
    if len(condition_ids) != 4 or len(set(condition_ids)) != 4:
        raise ValueError("P2.2A requires exactly four unique conditions")
    ordered_blocks = sorted(block_ids, key=lambda value: (_block_sort_key(seed, value), value))
    result: dict[str, list[str]] = {}
    for index, block_id in enumerate(ordered_blocks):
        offset = index % len(condition_ids)
        result[block_id] = [
            condition_ids[(position + offset) % len(condition_ids)]
            for position in range(len(condition_ids))
        ]
    return result


def _select_pack(task_pack: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_pack["tasks"]:
        if row.get("task_valid") is True:
            grouped[str(row["source_project"])].append(dict(row))
    eligible_projects = sorted(
        project for project, rows in grouped.items() if len(rows) >= 8
    )
    if len(eligible_projects) < 3:
        return []
    selected: list[dict[str, Any]] = []
    for project in eligible_projects[:3]:
        selected.extend(sorted(grouped[project], key=lambda row: str(row["task_id"]))[:8])
    return selected


def _task_invariants(task: Any, pack_row: dict[str, Any], model: str, repeat: int) -> dict[str, Any]:
    payload = {
        "task_id": task.task_id,
        "source_project": task.source_project or task.repo,
        "repository_revision": task.base_commit,
        "fixture_sha256": pack_row.get("fixture_hash"),
        "issue_sha256": hashlib.sha256(task.issue_text.encode()).hexdigest(),
        "test_command_sha256": hashlib.sha256(task.test_command.encode()).hexdigest(),
        "budgets": task_budgets(task),
        "coding_tools": list(CODING_TOOLS),
        "model_snapshot": model,
        "repeat": repeat,
    }
    return {**payload, "invariants_sha256": sha256_json(payload)}


def build_matrix(
    *,
    selected_tasks: Sequence[dict[str, Any]],
    task_specs: dict[str, Any],
    model_snapshots: Sequence[str],
    repeats: int,
    conditions: Sequence[dict[str, Any]],
    seed: str,
) -> list[dict[str, Any]]:
    if len(model_snapshots) < 2 or len(set(model_snapshots)) != len(model_snapshots):
        raise ValueError("P2.2A requires at least two unique model snapshots")
    if repeats < 1:
        raise ValueError("P2.2A repeats must be positive")
    block_ids = [
        f"{row['task_id']}:{model}:{repeat}"
        for row in selected_tasks
        for model in model_snapshots
        for repeat in range(repeats)
    ]
    orders = _balanced_orders(block_ids, [str(row["id"]) for row in conditions], seed)
    runs: list[dict[str, Any]] = []
    by_condition = {str(row["id"]): row for row in conditions}
    by_task = {str(row["task_id"]): row for row in selected_tasks}
    for block_id in sorted(block_ids):
        task_id, model, raw_repeat = block_id.rsplit(":", 2)
        task = task_specs[task_id]
        repeat = int(raw_repeat)
        invariants = _task_invariants(task, by_task[task_id], model, repeat)
        for position, condition_id in enumerate(orders[block_id]):
            condition = by_condition[condition_id]
            runs.append({
                "run_id": f"{block_id}:{condition_id}",
                "block_id": block_id,
                "condition_order_index": position,
                "condition_id": condition_id,
                "evidence_configuration": {
                    "docatlas": condition["docatlas"],
                    "external_docs": condition["external_docs"],
                    "code_context_engine": condition["code_context_engine"],
                },
                "invariants": invariants,
                "status": "planned",
            })
    return runs


def _verify_matrix(
    runs: Sequence[dict[str, Any]],
    *,
    conditions: Sequence[dict[str, Any]],
    expected_blocks: int,
) -> None:
    by_block: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in runs:
        by_block[str(row.get("block_id"))].append(row)
    if len(by_block) != expected_blocks:
        raise ValueError("P2.2A block cardinality mismatch")
    expected_ids = {str(row["id"]) for row in conditions}
    expected_flags = {
        str(row["id"]): {
            "docatlas": row["docatlas"],
            "external_docs": row["external_docs"],
            "code_context_engine": row["code_context_engine"],
        }
        for row in conditions
    }
    positions: dict[str, Counter[int]] = {condition_id: Counter() for condition_id in expected_ids}
    for block_id, rows in by_block.items():
        if len(rows) != 4 or {str(row.get("condition_id")) for row in rows} != expected_ids:
            raise ValueError(f"P2.2A block {block_id} lacks one run per condition")
        invariant_hashes = {
            str(row.get("invariants", {}).get("invariants_sha256")) for row in rows
        }
        if len(invariant_hashes) != 1:
            raise ValueError(f"P2.2A non-evidence invariants differ within {block_id}")
        order = sorted(int(row.get("condition_order_index", -1)) for row in rows)
        if order != [0, 1, 2, 3]:
            raise ValueError(f"P2.2A condition order invalid in {block_id}")
        for row in rows:
            condition_id = str(row["condition_id"])
            if row.get("evidence_configuration") != expected_flags[condition_id]:
                raise ValueError(f"P2.2A evidence configuration drift: {condition_id}")
            positions[condition_id][int(row["condition_order_index"])] += 1
    for condition_id, counts in positions.items():
        if set(counts) != {0, 1, 2, 3} or max(counts.values()) - min(counts.values()) > 1:
            raise ValueError(f"P2.2A condition order is not balanced: {condition_id}")


def build_report(
    *,
    repo_root: Path,
    model_snapshots: Sequence[str] = (),
) -> dict[str, Any]:
    protocol = load_json(repo_root / "eval" / "product_truth_v1" / "protocol.lock.json")
    task_pack = load_json(repo_root / "eval" / "product_truth_v1" / "results" / "task-pack.json")
    verify_task_pack(task_pack)
    conditions = _conditions(protocol)
    ready = task_pack["summary"]["task_pack_ready"] is True
    selected = _select_pack(task_pack) if ready else []
    tasks = load_tasks(repo_root / "eval" / "task_level" / "tasks.jsonl")
    seed = str(protocol["benchmark_design"]["randomization"]["seed"])
    repeats = int(protocol["benchmark_design"]["repeats"])

    if ready:
        full_runs = build_matrix(
            selected_tasks=selected,
            task_specs=tasks,
            model_snapshots=model_snapshots,
            repeats=repeats,
            conditions=conditions,
            seed=seed,
        )
        canary_tasks = selected[:2]
        canary_runs = build_matrix(
            selected_tasks=canary_tasks,
            task_specs=tasks,
            model_snapshots=model_snapshots[:2],
            repeats=1,
            conditions=conditions,
            seed=seed + ":canary",
        )
        _verify_matrix(
            full_runs,
            conditions=conditions,
            expected_blocks=len(selected) * len(model_snapshots) * repeats,
        )
        _verify_matrix(canary_runs, conditions=conditions, expected_blocks=4)
    else:
        full_runs = []
        canary_runs = []

    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "protocol_sha256": protocol["protocol_sha256"],
        "conditions": conditions,
        "randomization": protocol["benchmark_design"]["randomization"],
        "authorization": {
            "task_pack_ready": ready,
            "canary_authorized": ready,
            "full_pilot_authorized": ready,
            "blocked_reason": None if ready else "task_pack_not_ready",
        },
        "plans": {
            "canary": {
                "expected_scored_runs": 16,
                "planned_runs": len(canary_runs),
                "runs": canary_runs,
            },
            "full_pilot": {
                "minimum_scored_runs": protocol["benchmark_design"]["minimum_scored_runs"],
                "maximum_scored_runs": protocol["benchmark_design"]["maximum_scored_runs"],
                "selected_tasks": [row["task_id"] for row in selected],
                "model_snapshots": list(model_snapshots) if ready else [],
                "planned_runs": len(full_runs),
                "runs": full_runs,
            },
        },
        "claim_boundary": {
            "harness_infrastructure_only": True,
            "product_truth_proven": False,
            "canary_product_claim_allowed": False,
            "zero_runs_when_unauthorized": True,
            "production_runtime_changed": False,
            "public_api_changed": False,
            "product_maturity": "Beta",
        },
        "decision": {
            "p2_2a_execution": "complete",
            "harness_ready": True,
            "comparative_execution_authorized": ready,
            "next_step": "P2.2B/C execution gate",
        },
    }
    verify_report(report)
    return report


def verify_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P2.2A report identity mismatch")
    conditions = report.get("conditions")
    if not isinstance(conditions, list) or tuple(row.get("id") for row in conditions) != EXPECTED_CONDITIONS:
        raise ValueError("P2.2A condition contract mismatch")
    authorization = report.get("authorization")
    plans = report.get("plans")
    if not isinstance(authorization, dict) or not isinstance(plans, dict):
        raise ValueError("P2.2A authorization or plans missing")
    ready = authorization.get("task_pack_ready") is True
    if authorization.get("canary_authorized") is not ready or authorization.get("full_pilot_authorized") is not ready:
        raise ValueError("P2.2A authorization mismatch")
    canary = plans.get("canary")
    full = plans.get("full_pilot")
    if not isinstance(canary, dict) or not isinstance(full, dict):
        raise ValueError("P2.2A plan rows missing")
    if canary.get("expected_scored_runs") != 16:
        raise ValueError("P2.2A canary cardinality changed")
    if full.get("minimum_scored_runs") != 576 or full.get("maximum_scored_runs") != 720:
        raise ValueError("P2.2A pilot cardinality changed")
    canary_runs = canary.get("runs")
    full_runs = full.get("runs")
    if not isinstance(canary_runs, list) or not isinstance(full_runs, list):
        raise ValueError("P2.2A run arrays missing")
    if canary.get("planned_runs") != len(canary_runs) or full.get("planned_runs") != len(full_runs):
        raise ValueError("P2.2A planned-run count mismatch")
    if not ready:
        if canary_runs or full_runs or canary.get("planned_runs") != 0 or full.get("planned_runs") != 0:
            raise ValueError("P2.2A planned runs despite failed authorization")
        if full.get("selected_tasks") != [] or full.get("model_snapshots") != []:
            raise ValueError("P2.2A retained executable identities while blocked")
    else:
        _verify_matrix(canary_runs, conditions=conditions, expected_blocks=4)
        if not 576 <= len(full_runs) <= 720:
            raise ValueError("P2.2A full-pilot run count outside preregistration")
        _verify_matrix(full_runs, conditions=conditions, expected_blocks=len(full_runs) // 4)
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("P2.2A claim boundary missing")
    if boundary.get("product_truth_proven") is not False:
        raise ValueError("P2.2A overclaims Product Truth")
    if boundary.get("canary_product_claim_allowed") is not False:
        raise ValueError("P2.2A lets the canary support a product claim")
    if boundary.get("production_runtime_changed") is not False or boundary.get("public_api_changed") is not False:
        raise ValueError("P2.2A overclaims runtime or API change")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P2.2A promotes product maturity")
    if report.get("decision", {}).get("comparative_execution_authorized") is not ready:
        raise ValueError("P2.2A decision/authorization mismatch")


__all__ = [
    "CODING_TOOLS",
    "EXPECTED_CONDITIONS",
    "PROTOCOL",
    "SCHEMA_VERSION",
    "build_matrix",
    "build_report",
    "canonical_json",
    "verify_report",
]
