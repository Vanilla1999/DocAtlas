from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from eval.task_level.evaluators.tests import run_command
from eval.task_level.schemas import TASK_LEVEL_ROOT, TaskSpec


CONTRACTS_PATH = TASK_LEVEL_ROOT / "task33_evaluation_contracts.json"
CompileMode = Literal["command", "not_applicable"]


@dataclass(frozen=True)
class CompileGate:
    mode: CompileMode
    command: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class TaskEvaluationContract:
    task_id: str
    patch_contract_id: str
    public_test_command: str
    local_test_command: str
    compile_gate: CompileGate
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    semantic_checks: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "patch_contract_id": self.patch_contract_id,
            "public_test_command": self.public_test_command,
            "local_test_command": self.local_test_command,
            "compile_gate": {
                "mode": self.compile_gate.mode,
                "command": self.compile_gate.command,
                "reason": self.compile_gate.reason,
            },
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "semantic_checks": list(self.semantic_checks),
        }


@dataclass(frozen=True)
class ContractValidation:
    status: Literal["valid", "invalid"]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return self.status == "valid"


def load_task_evaluation_contracts(path: Path = CONTRACTS_PATH) -> dict[str, TaskEvaluationContract]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load Task 33 evaluation contracts: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "task33-evaluation-contracts-1":
        raise ValueError("Unsupported Task 33 evaluation-contract schema")
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("Task 33 evaluation contracts require a non-empty tasks list")

    contracts: dict[str, TaskEvaluationContract] = {}
    for index, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            raise ValueError(f"Task 33 evaluation contract at index {index} must be an object")
        contract = _parse_contract(raw, index=index)
        if contract.task_id in contracts:
            raise ValueError(f"Duplicate Task 33 evaluation contract: {contract.task_id}")
        contracts[contract.task_id] = contract
    return contracts


def evaluation_contract_sha256(contract: TaskEvaluationContract) -> str:
    payload = json.dumps(contract.to_json(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def evaluation_contract_registry_sha256(path: Path = CONTRACTS_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_task_evaluation_contract(task: TaskSpec, contract: TaskEvaluationContract | None) -> ContractValidation:
    errors: list[str] = []
    if contract is None:
        return ContractValidation("invalid", ("patch_contract_not_defined",))
    if contract.task_id != task.task_id:
        errors.append("task_id_mismatch")
    if contract.public_test_command != task.test_command:
        errors.append("public_test_command_mismatch")
    if not contract.local_test_command.startswith("python -m pytest "):
        errors.append("local_test_command_must_use_python_module_pytest")
    if _pytest_target(contract.local_test_command) != _pytest_target(contract.public_test_command):
        errors.append("local_test_target_mismatch")
    if not contract.allowed_paths:
        errors.append("allowed_paths_required")
    if not contract.semantic_checks:
        errors.append("semantic_checks_required")
    if contract.compile_gate.mode == "command":
        if not contract.compile_gate.command:
            errors.append("compile_command_required")
        if contract.compile_gate.reason:
            errors.append("compile_reason_forbidden_for_command")
    elif contract.compile_gate.mode == "not_applicable":
        if contract.compile_gate.command:
            errors.append("compile_command_forbidden_when_not_applicable")
        if not contract.compile_gate.reason:
            errors.append("compile_not_applicable_reason_required")
    else:
        errors.append("unsupported_compile_mode")
    return ContractValidation("invalid" if errors else "valid", tuple(errors))


def evaluate_patch_surface(contract: TaskEvaluationContract, changed_files: list[str]) -> dict[str, Any]:
    normalized = [Path(path).as_posix() for path in changed_files]
    forbidden = sorted(path for path in normalized if _matches_any(path, contract.forbidden_paths))
    outside_allowed = sorted(path for path in normalized if path not in contract.allowed_paths)
    violations = sorted(set(forbidden + outside_allowed))
    return {
        "status": "failed" if violations else "passed",
        "allowed_paths": list(contract.allowed_paths),
        "forbidden_paths": list(contract.forbidden_paths),
        "changed_files": normalized,
        "forbidden_changes": forbidden,
        "outside_allowed_surface": outside_allowed,
        "violations": violations,
    }


def run_compile_gate(contract: TaskEvaluationContract, workspace: Path, timeout_seconds: int = 120) -> dict[str, Any]:
    gate = contract.compile_gate
    if gate.mode == "not_applicable":
        return {
            "status": "not_applicable",
            "passed": True,
            "command": None,
            "reason": gate.reason,
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }
    result = run_command(gate.command or "", workspace, timeout_seconds)
    return {
        "status": "passed" if result.passed else "failed",
        "passed": result.passed,
        "command": result.command,
        "reason": None,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _parse_contract(raw: dict[str, Any], *, index: int) -> TaskEvaluationContract:
    task_id = _required_string(raw, "task_id", index)
    patch_contract_id = _required_string(raw, "patch_contract_id", index)
    public_test_command = _required_string(raw, "public_test_command", index)
    compile_raw = raw.get("compile_gate")
    if not isinstance(compile_raw, dict):
        raise ValueError(f"Task 33 contract {task_id} requires compile_gate")
    mode = compile_raw.get("mode")
    if mode not in {"command", "not_applicable"}:
        raise ValueError(f"Task 33 contract {task_id} has unsupported compile mode: {mode!r}")
    compile_gate = CompileGate(
        mode=mode,
        command=_optional_string(compile_raw.get("command")),
        reason=_optional_string(compile_raw.get("reason")),
    )
    contract = TaskEvaluationContract(
        task_id=task_id,
        patch_contract_id=patch_contract_id,
        public_test_command=public_test_command,
        local_test_command=_required_string(raw, "local_test_command", index),
        compile_gate=compile_gate,
        allowed_paths=_string_tuple(raw.get("allowed_paths"), task_id, "allowed_paths"),
        forbidden_paths=_string_tuple(raw.get("forbidden_paths"), task_id, "forbidden_paths"),
        semantic_checks=_string_tuple(raw.get("semantic_checks"), task_id, "semantic_checks"),
    )
    if compile_gate.mode == "command" and not compile_gate.command:
        raise ValueError(f"Task 33 contract {task_id} requires a compile command")
    if compile_gate.mode == "not_applicable" and not compile_gate.reason:
        raise ValueError(f"Task 33 contract {task_id} requires a not-applicable reason")
    return contract


def _required_string(raw: dict[str, Any], key: str, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Task 33 evaluation contract at index {index} requires {key}")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_tuple(value: Any, task_id: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"Task 33 contract {task_id} requires a string list for {field}")
    result = tuple(item.strip() for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"Task 33 contract {task_id} contains duplicate {field}")
    return result


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _pytest_target(command: str) -> str | None:
    parts = command.split()
    try:
        pytest_index = parts.index("pytest")
    except ValueError:
        return None
    return parts[pytest_index + 1] if len(parts) > pytest_index + 1 else None
