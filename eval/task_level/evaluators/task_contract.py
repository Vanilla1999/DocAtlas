from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from eval.task_level.analysis.task23_decision import apply_protocol_amendment
from eval.task_level.artifact_hygiene import is_runtime_artifact
from eval.task_level.evaluators.tests import run_command
from eval.task_level.schemas import TASK_LEVEL_ROOT, TaskSpec


CONTRACTS_PATH = TASK_LEVEL_ROOT / "task33_evaluation_contracts.json"
TASK23_PROTOCOL_PATH = TASK_LEVEL_ROOT / "task23_protocol.json"
TASK23_AMENDMENT_PATH = TASK_LEVEL_ROOT / "task23_protocol_amendment_001.json"
TEMPLATE_ROOT = TASK_LEVEL_ROOT / "fixtures" / "templates"
ORACLE_ROOT = TASK_LEVEL_ROOT / "oracles"
HIDDEN_TEST_ROOT = TASK_LEVEL_ROOT / "hidden_tests"
EXTERNAL_CONTEXT_ROOT = TASK_LEVEL_ROOT / "external_context"
CompileMode = Literal["command", "not_applicable"]


@dataclass(frozen=True)
class CompileGate:
    mode: CompileMode
    command: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SemanticCheck:
    check_id: str
    description: str
    test_ids: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "description": self.description,
            "test_ids": list(self.test_ids),
        }


@dataclass(frozen=True)
class TaskEvaluationContract:
    task_id: str
    patch_contract_id: str
    public_test_command: str
    local_test_command: str
    semantic_test_command: str
    compile_gate: CompileGate
    fixture_sha256: str
    protocol_fixture_sha256: str
    oracle_sha256: str
    hidden_tests_sha256: str
    external_context_sha256: str
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    semantic_checks: tuple[SemanticCheck, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "patch_contract_id": self.patch_contract_id,
            "public_test_command": self.public_test_command,
            "local_test_command": self.local_test_command,
            "semantic_test_command": self.semantic_test_command,
            "compile_gate": {
                "mode": self.compile_gate.mode,
                "command": self.compile_gate.command,
                "reason": self.compile_gate.reason,
            },
            "artifact_identity": {
                "fixture_hash_algorithm": "sha256-length-prefixed-v2",
                "fixture_sha256": self.fixture_sha256,
                "protocol_fixture_hash_algorithm": "sha256-concat-v1",
                "protocol_fixture_sha256": self.protocol_fixture_sha256,
                "oracle_sha256": self.oracle_sha256,
                "hidden_tests_hash_algorithm": "sha256-length-prefixed-v2",
                "hidden_tests_sha256": self.hidden_tests_sha256,
                "external_context_sha256": self.external_context_sha256,
            },
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "semantic_checks": [check.to_json() for check in self.semantic_checks],
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
    patch_contract_ids: set[str] = set()
    for index, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            raise ValueError(f"Task 33 evaluation contract at index {index} must be an object")
        contract = _parse_contract(raw, index=index)
        if contract.task_id in contracts:
            raise ValueError(f"Duplicate Task 33 evaluation contract: {contract.task_id}")
        if contract.patch_contract_id in patch_contract_ids:
            raise ValueError(f"Duplicate Task 33 patch contract id: {contract.patch_contract_id}")
        contracts[contract.task_id] = contract
        patch_contract_ids.add(contract.patch_contract_id)
    return contracts


def load_effective_task23_protocol_tasks() -> dict[str, dict[str, Any]]:
    try:
        protocol = json.loads(TASK23_PROTOCOL_PATH.read_text(encoding="utf-8"))
        amendment = json.loads(TASK23_AMENDMENT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load frozen Task 23 protocol: {exc}") from exc
    if not isinstance(protocol, dict) or not isinstance(amendment, dict):
        raise ValueError("Frozen Task 23 protocol or amendment is malformed")
    effective_protocol = apply_protocol_amendment(protocol, amendment)
    effective = effective_protocol.get("tasks")
    if not isinstance(effective, list):
        raise ValueError("Frozen Task 23 protocol requires tasks")
    result = {
        str(task.get("task_id")): task
        for task in effective
        if isinstance(task.get("task_id"), str) and task.get("task_id")
    }
    if len(result) != len(effective):
        raise ValueError("Frozen Task 23 protocol requires unique task ids")
    return result


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
    if contract.semantic_test_command != "python -m pytest tests/hidden":
        errors.append("semantic_test_command_mismatch")
    for field, value in (
        ("fixture_sha256", contract.fixture_sha256),
        ("protocol_fixture_sha256", contract.protocol_fixture_sha256),
        ("oracle_sha256", contract.oracle_sha256),
        ("hidden_tests_sha256", contract.hidden_tests_sha256),
        ("external_context_sha256", contract.external_context_sha256),
    ):
        if not _is_sha256(value):
            errors.append(f"{field}_invalid")
    if not contract.allowed_paths:
        errors.append("allowed_paths_required")
    if not contract.semantic_checks:
        errors.append("semantic_checks_required")
    check_ids = [check.check_id for check in contract.semantic_checks]
    if len(set(check_ids)) != len(check_ids):
        errors.append("semantic_check_ids_must_be_unique")
    if any(not check.test_ids for check in contract.semantic_checks):
        errors.append("semantic_check_test_ids_required")
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


def validate_task_evaluation_artifacts(
    contract: TaskEvaluationContract | None,
    protocol_task: dict[str, Any] | None,
) -> ContractValidation:
    if contract is None:
        return ContractValidation("invalid", ("patch_contract_not_defined",))
    errors: list[str] = []
    if not isinstance(protocol_task, dict):
        return ContractValidation("invalid", ("frozen_protocol_task_not_defined",))
    if protocol_task.get("task_id") != contract.task_id:
        errors.append("protocol_task_id_mismatch")
    for field, expected in (
        ("fixture_hash", contract.protocol_fixture_sha256),
        ("oracle_sha256", contract.oracle_sha256),
        ("external_context_sha256", contract.external_context_sha256),
    ):
        if protocol_task.get(field) != expected:
            errors.append(f"protocol_{field}_mismatch")

    template = TEMPLATE_ROOT / contract.task_id
    hidden_tests = HIDDEN_TEST_ROOT / contract.task_id
    oracle = ORACLE_ROOT / f"{contract.task_id}.patch"
    external_context = EXTERNAL_CONTEXT_ROOT / f"{contract.task_id}.json"
    actual_values = {
        "fixture_sha256": directory_sha256(template, algorithm="sha256-length-prefixed-v2"),
        "protocol_fixture_sha256": directory_sha256(template, algorithm="sha256-concat-v1"),
        "oracle_sha256": file_sha256(oracle),
        "hidden_tests_sha256": directory_sha256(hidden_tests, algorithm="sha256-length-prefixed-v2"),
        "external_context_sha256": file_sha256(external_context),
    }
    for field, actual in actual_values.items():
        if actual != getattr(contract, field):
            errors.append(f"actual_{field}_mismatch")
    hidden_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(hidden_tests.rglob("*.py"))
        if not is_runtime_artifact(path.relative_to(hidden_tests).as_posix())
    ) if hidden_tests.is_dir() else ""
    for check in contract.semantic_checks:
        for test_id in check.test_ids:
            if f"def {test_id}(" not in hidden_source:
                errors.append(f"semantic_test_missing:{check.check_id}:{test_id}")
    return ContractValidation("invalid" if errors else "valid", tuple(errors))


def file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def directory_sha256(path: Path, *, algorithm: str = "sha256-length-prefixed-v2") -> str | None:
    if algorithm not in {"sha256-concat-v1", "sha256-length-prefixed-v2"} or not path.is_dir():
        return None
    digest = hashlib.sha256()
    for file_path in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = file_path.relative_to(path).as_posix()
        if is_runtime_artifact(relative):
            continue
        relative_bytes = relative.encode()
        content = file_path.read_bytes()
        if algorithm == "sha256-length-prefixed-v2":
            digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        if algorithm == "sha256-length-prefixed-v2":
            digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


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
    identity = raw.get("artifact_identity")
    if not isinstance(identity, dict):
        raise ValueError(f"Task 33 contract {task_id} requires artifact_identity")
    if identity.get("fixture_hash_algorithm") != "sha256-length-prefixed-v2":
        raise ValueError(f"Task 33 contract {task_id} has unsupported fixture hash algorithm")
    if identity.get("protocol_fixture_hash_algorithm") != "sha256-concat-v1":
        raise ValueError(f"Task 33 contract {task_id} has unsupported protocol fixture hash algorithm")
    if identity.get("hidden_tests_hash_algorithm") != "sha256-length-prefixed-v2":
        raise ValueError(f"Task 33 contract {task_id} has unsupported hidden-tests hash algorithm")
    contract = TaskEvaluationContract(
        task_id=task_id,
        patch_contract_id=patch_contract_id,
        public_test_command=public_test_command,
        local_test_command=_required_string(raw, "local_test_command", index),
        semantic_test_command=_required_string(raw, "semantic_test_command", index),
        compile_gate=compile_gate,
        fixture_sha256=_required_identity_string(identity, "fixture_sha256", task_id),
        protocol_fixture_sha256=_required_identity_string(identity, "protocol_fixture_sha256", task_id),
        oracle_sha256=_required_identity_string(identity, "oracle_sha256", task_id),
        hidden_tests_sha256=_required_identity_string(identity, "hidden_tests_sha256", task_id),
        external_context_sha256=_required_identity_string(identity, "external_context_sha256", task_id),
        allowed_paths=_string_tuple(raw.get("allowed_paths"), task_id, "allowed_paths"),
        forbidden_paths=_string_tuple(raw.get("forbidden_paths"), task_id, "forbidden_paths"),
        semantic_checks=_semantic_checks(raw.get("semantic_checks"), task_id),
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


def _required_identity_string(raw: dict[str, Any], key: str, task_id: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Task 33 contract {task_id} requires artifact_identity.{key}")
    return value.strip()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _string_tuple(value: Any, task_id: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"Task 33 contract {task_id} requires a string list for {field}")
    result = tuple(item.strip() for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"Task 33 contract {task_id} contains duplicate {field}")
    return result


def _semantic_checks(value: Any, task_id: str) -> tuple[SemanticCheck, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Task 33 contract {task_id} requires semantic_checks")
    checks: list[SemanticCheck] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Task 33 contract {task_id} semantic check {index} must be an object")
        check_id = item.get("id")
        description = item.get("description")
        test_ids = item.get("test_ids")
        if not isinstance(check_id, str) or not check_id.strip():
            raise ValueError(f"Task 33 contract {task_id} semantic check {index} requires id")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"Task 33 contract {task_id} semantic check {index} requires description")
        parsed_test_ids = _string_tuple(test_ids, task_id, f"semantic_checks[{index}].test_ids")
        checks.append(SemanticCheck(check_id.strip(), description.strip(), parsed_test_ids))
    return tuple(checks)


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _pytest_target(command: str) -> str | None:
    parts = command.split()
    try:
        pytest_index = parts.index("pytest")
    except ValueError:
        return None
    return parts[pytest_index + 1] if len(parts) > pytest_index + 1 else None
