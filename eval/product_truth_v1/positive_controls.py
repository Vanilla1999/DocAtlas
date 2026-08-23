from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable

from eval.task_level.fixtures.builder import materialize_fixture, validate_fixture
from eval.task_level.schemas import TASKS_PATH, VALIDATION_ROOT, TaskSpec


SCHEMA_VERSION = 1
PROTOCOL = "product-truth-positive-controls-v1"
DEFAULT_TASK_IDS = (
    "decisive_docmancer_vector_timeout_fallback_001",
    "real_project_help_chat_linearizable_module_lifecycle_001",
    "real_project_viscanner_client_owned_disable_signal_001",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def load_tasks(path: Path = TASKS_PATH) -> dict[str, TaskSpec]:
    rows: dict[str, TaskSpec] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        task = TaskSpec.from_json(json.loads(raw))
        if task.task_id in rows:
            raise ValueError(f"duplicate task id: {task.task_id}")
        rows[task.task_id] = task
    return rows


def task_budgets(task: TaskSpec) -> dict[str, int | bool]:
    return {
        "max_turns": task.max_turns,
        "max_requests": task.max_turns,
        "max_input_tokens": task.max_input_tokens,
        "max_output_tokens": task.max_output_tokens,
        "max_wall_seconds": task.max_minutes * 60,
        "max_edit_calls": 40,
        "max_test_runs": 10,
        "hard_enforcement_required": True,
    }


def _normalized_gold(result: dict[str, Any]) -> dict[str, Any]:
    gold = result.get("gold") if isinstance(result.get("gold"), dict) else {}
    base = result.get("base") if isinstance(result.get("base"), dict) else {}
    contract = result.get("evaluation_contract")
    contract = contract if isinstance(contract, dict) else {}
    return {
        "status": result.get("status"),
        "fixture_hash": result.get("fixture_hash"),
        "base_setup_success": base.get("setup_success"),
        "base_expected_tests_failed": base.get("expected_tests_failed"),
        "patch_applied": gold.get("patch_applied"),
        "public_tests_passed": gold.get("public_tests_passed"),
        "hidden_tests_passed": gold.get("hidden_tests_passed"),
        "compile_success": gold.get("compile_success"),
        "oracle_isolated": result.get("oracle_isolated"),
        "contract_status": contract.get("status", "legacy_unfrozen"),
        "patch_surface_status": (
            contract.get("patch_surface", {}).get("status")
            if isinstance(contract.get("patch_surface"), dict)
            else None
        ),
    }


def _restore_validation(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(previous)


def run_gold_attempt(task: TaskSpec, *, attempt: int) -> dict[str, Any]:
    validation_path = VALIDATION_ROOT / f"{task.task_id}.json"
    previous = validation_path.read_bytes() if validation_path.is_file() else None
    try:
        with TemporaryDirectory(prefix=f"p2-gold-{task.task_id}-{attempt}-") as raw:
            workspace = Path(raw) / "workspace"
            materialize_fixture(task, workspace)
            result = validate_fixture(task, workspace, local_commands=True)
            normalized = _normalized_gold(result)
    finally:
        _restore_validation(validation_path, previous)
    normalized["attempt"] = attempt
    normalized["passed"] = bool(
        normalized["status"] == "validated"
        and normalized["base_setup_success"] is True
        and normalized["base_expected_tests_failed"] is True
        and normalized["patch_applied"] is True
        and normalized["public_tests_passed"] is True
        and normalized["hidden_tests_passed"] is True
        and normalized["oracle_isolated"] is True
        and normalized["compile_success"] in {True, None}
        and normalized["patch_surface_status"] in {None, "passed", "legacy"}
    )
    return normalized


def load_oracle_control(path: Path | None, *, task: TaskSpec, protocol_sha256: str) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {
            "status": "not_run",
            "real_model": False,
            "correct_patch": False,
            "same_budgets": False,
            "same_tools": False,
            "provider_id": None,
            "model_snapshot": None,
            "request_ids": [],
            "report_sha256": None,
        }
    payload = load_json(path)
    required = {
        "schema_version": 1,
        "protocol_sha256": protocol_sha256,
        "task_id": task.task_id,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ValueError(f"oracle control {path} has invalid {key}")
    if payload.get("budgets") != task_budgets(task):
        raise ValueError(f"oracle control {path} changed task budgets")
    if payload.get("gold_oracle_hidden_from_model") is not True:
        raise ValueError(f"oracle control {path} exposed evaluator-only gold data")
    request_ids = payload.get("request_ids")
    if not isinstance(request_ids, list) or len(request_ids) != len(set(request_ids)):
        raise ValueError(f"oracle control {path} has invalid request ids")
    return {
        "status": str(payload.get("status") or "invalid"),
        "real_model": payload.get("real_model") is True,
        "correct_patch": payload.get("correct_patch") is True,
        "same_budgets": payload.get("same_budgets") is True,
        "same_tools": payload.get("same_tools") is True,
        "provider_id": payload.get("provider_id"),
        "model_snapshot": payload.get("model_snapshot"),
        "request_ids": request_ids,
        "report_sha256": sha256_file(path),
    }


def run_task(
    task: TaskSpec,
    *,
    repo_root: Path,
    protocol_sha256: str,
    oracle_control_root: Path | None = None,
) -> dict[str, Any]:
    attempts = [run_gold_attempt(task, attempt=index) for index in (1, 2)]
    gold_reproducible = bool(
        all(row["passed"] for row in attempts)
        and attempts[0]["fixture_hash"] == attempts[1]["fixture_hash"]
        and {
            key: attempts[0][key]
            for key in attempts[0]
            if key not in {"attempt"}
        }
        == {
            key: attempts[1][key]
            for key in attempts[1]
            if key not in {"attempt"}
        }
    )
    oracle_context = repo_root / "eval" / "task_level" / "oracles" / f"{task.task_id}.context.json"
    oracle_control_path = (
        oracle_control_root / f"{task.task_id}.json"
        if oracle_control_root is not None
        else None
    )
    oracle = load_oracle_control(
        oracle_control_path,
        task=task,
        protocol_sha256=protocol_sha256,
    )
    oracle_passed = bool(
        oracle["status"] == "passed"
        and oracle["real_model"]
        and oracle["correct_patch"]
        and oracle["same_budgets"]
        and oracle["same_tools"]
        and oracle["request_ids"]
    )
    valid = bool(gold_reproducible and oracle_context.is_file() and oracle_passed)
    return {
        "task_id": task.task_id,
        "source_project": task.source_project or task.repo,
        "ecosystem": task.ecosystem,
        "gold_attempts": attempts,
        "gold_reproducible": gold_reproducible,
        "oracle_evidence": {
            "present": oracle_context.is_file(),
            "sha256": sha256_file(oracle_context) if oracle_context.is_file() else None,
        },
        "oracle_model_control": oracle,
        "task_valid": valid,
        "invalid_reason": (
            None if valid else
            "gold_control_failed" if not gold_reproducible else
            "oracle_evidence_missing" if not oracle_context.is_file() else
            "real_model_oracle_control_missing_or_failed"
        ),
    }


def build_report(
    *,
    repo_root: Path,
    task_ids: Iterable[str] = DEFAULT_TASK_IDS,
    oracle_control_root: Path | None = None,
) -> dict[str, Any]:
    protocol = load_json(repo_root / "eval" / "product_truth_v1" / "protocol.lock.json")
    protocol_sha = str(protocol["protocol_sha256"])
    tasks = load_tasks(repo_root / "eval" / "task_level" / "tasks.jsonl")
    selected = []
    for task_id in task_ids:
        task = tasks.get(task_id)
        if task is None:
            raise ValueError(f"unknown positive-control task: {task_id}")
        selected.append(
            run_task(
                task,
                repo_root=repo_root,
                protocol_sha256=protocol_sha,
                oracle_control_root=oracle_control_root,
            )
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "protocol_sha256": protocol_sha,
        "tasks": selected,
        "summary": {
            "task_count": len(selected),
            "gold_reproducible": sum(row["gold_reproducible"] for row in selected),
            "oracle_evidence_present": sum(row["oracle_evidence"]["present"] for row in selected),
            "real_model_oracle_passed": sum(
                row["oracle_model_control"]["status"] == "passed"
                and row["oracle_model_control"]["real_model"]
                and row["oracle_model_control"]["correct_patch"]
                for row in selected
            ),
            "valid_tasks": sum(row["task_valid"] for row in selected),
        },
        "claim_boundary": {
            "product_truth_proven": False,
            "single_task_claim_allowed": False,
            "provider_free_run_counts_as_oracle_control": False,
            "minimum_valid_tasks_for_pilot": 24,
            "product_maturity": "Beta",
        },
        "decision": {
            "p2_1b_execution": "complete",
            "task_pack_ready": sum(row["task_valid"] for row in selected) >= 24,
            "next_step": "P2.1C task-pack eligibility and real-model oracle controls",
        },
    }
    verify_report(report)
    return report


def verify_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P2.1B report identity mismatch")
    tasks = report.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("P2.1B requires at least one task")
    ids = [row.get("task_id") for row in tasks if isinstance(row, dict)]
    if len(ids) != len(tasks) or len(ids) != len(set(ids)):
        raise ValueError("P2.1B task identities are invalid")
    for row in tasks:
        attempts = row.get("gold_attempts")
        if not isinstance(attempts, list) or [item.get("attempt") for item in attempts] != [1, 2]:
            raise ValueError(f"{row.get('task_id')}: exactly two clean gold attempts are required")
        recomputed_gold = bool(
            all(item.get("passed") is True for item in attempts)
            and attempts[0].get("fixture_hash") == attempts[1].get("fixture_hash")
            and {
                key: attempts[0].get(key)
                for key in attempts[0]
                if key != "attempt"
            }
            == {
                key: attempts[1].get(key)
                for key in attempts[1]
                if key != "attempt"
            }
        )
        if row.get("gold_reproducible") is not recomputed_gold:
            raise ValueError(f"{row.get('task_id')}: gold reproducibility was hidden or invented")
        oracle = row.get("oracle_model_control")
        if not isinstance(oracle, dict):
            raise ValueError(f"{row.get('task_id')}: oracle model control missing")
        oracle_passed = bool(
            oracle.get("status") == "passed"
            and oracle.get("real_model") is True
            and oracle.get("correct_patch") is True
            and oracle.get("same_budgets") is True
            and oracle.get("same_tools") is True
            and oracle.get("request_ids")
        )
        expected_valid = bool(
            recomputed_gold
            and row.get("oracle_evidence", {}).get("present") is True
            and oracle_passed
        )
        if row.get("task_valid") is not expected_valid:
            raise ValueError(f"{row.get('task_id')}: task validity was hidden or invented")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("P2.1B summary missing")
    expected_valid = sum(bool(row["task_valid"]) for row in tasks)
    if summary.get("valid_tasks") != expected_valid:
        raise ValueError("P2.1B valid-task count mismatch")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("P2.1B claim boundary missing")
    if boundary.get("product_truth_proven") is not False:
        raise ValueError("P2.1B overclaims Product Truth")
    if boundary.get("provider_free_run_counts_as_oracle_control") is not False:
        raise ValueError("P2.1B accepts provider-free oracle substitution")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P2.1B promotes product maturity")
    ready = expected_valid >= int(boundary.get("minimum_valid_tasks_for_pilot") or 0)
    if report.get("decision", {}).get("task_pack_ready") is not ready:
        raise ValueError("P2.1B task-pack readiness mismatch")


__all__ = [
    "DEFAULT_TASK_IDS",
    "PROTOCOL",
    "SCHEMA_VERSION",
    "build_report",
    "canonical_json",
    "load_json",
    "load_tasks",
    "task_budgets",
    "verify_report",
]
