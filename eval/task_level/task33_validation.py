from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from docmancer.docs.application.action_packet import validate_action_packet
from eval.task_level.evaluators.task_contract import (
    evaluation_contract_registry_sha256,
    evaluation_contract_sha256,
    load_task_evaluation_contracts,
)
from eval.task_level.isolated_delivery import (
    HostEvidenceSnapshot,
    TASK33_QUERY_DERIVATION,
    derive_task33_retrieval_query,
    missing_packet_evidence_categories,
    missing_packet_evidence_paths,
)
from eval.task_level.task33_pilot import evaluate_task33c_pilot_completeness


PROTOCOL_PATH = Path(__file__).with_name("task33c_protocol.lock.json")
VALIDATION_FILENAME = "task33c_validation.json"
MANIFEST_FILENAME = "task33c_artifact_manifest.json"
_TOP_LEVEL_ALLOWLIST = frozenset({
    "metadata.json",
    "runner_canary.json",
    "report.md",
    "docatlas_tool_visibility_canary.json",
    "runs.jsonl",
    "status.json",
    "task33c_completeness.json",
    "task33c_pilot_plan.json",
    "task33c_protocol.lock.json",
    "task33c_sandbox_provenance.json",
})
_CELL_ALLOWLIST = frozenset({
    "action_packet.json",
    "bounded_direct_metrics.json",
    "changed_files.json",
    "changed_files.raw.json",
    "condition_setup.json",
    "context_sources.json",
    "delivery_prompt_sources.json",
    "docatlas_preparation.json",
    "docatlas_tool_response_excerpt.txt",
    "evaluator_execution_boundary.json",
    "git_status.raw.txt",
    "git_status.txt",
    "github_models_usage.json",
    "hidden_test_result.json",
    "host_evidence_manifest.json",
    "host_evidence_snapshot.json",
    "host_retrieval_metrics.json",
    "ignored_runtime_artifacts.json",
    "isolated_delegation_envelope.json",
    "isolated_delivery_attempt.json",
    "isolated_delivery_metrics.json",
    "materialized.json",
    "mcp_config.json",
    "patch.diff",
    "patch.raw.diff",
    "patch_hygiene.json",
    "policy_audit.json",
    "public_test_result.json",
    "result.json",
    "runner_execution_boundary.json",
    "stderr.log",
    "stdout.log",
    "tool_policy.json",
    "trajectory.normalized.json",
    "validation.json",
    "worker_usage_proof.json",
})


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    value = _load_json(path)
    if value.get("schema_version") != "task33c-frozen-protocol-1":
        raise ValueError("unsupported Task 33C protocol lock")
    return value


def protocol_sha256(path: Path = PROTOCOL_PATH) -> str:
    return _file_sha256(path)


def validate_task33c_run(
    run_dir: Path,
    *,
    protocol_path: Path = PROTOCOL_PATH,
    write: bool = True,
) -> dict[str, Any]:
    """Independently recompute Task 33C evidence from persisted artifacts."""

    run_dir = run_dir.resolve()
    protocol = load_protocol(protocol_path)
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}

    _check_live_protocol(protocol, errors)
    frozen_copy = run_dir / protocol_path.name
    if not frozen_copy.is_file():
        errors.append("protocol_snapshot_missing")
    elif _file_sha256(frozen_copy) != _file_sha256(protocol_path):
        errors.append("protocol_snapshot_hash_mismatch")
    checks["protocol_lock"] = not any(error.startswith("protocol_") for error in errors)

    plan = _load_optional_json(run_dir / "task33c_pilot_plan.json")
    _check_plan(plan, protocol, errors)
    checks["pilot_plan"] = not any(error.startswith("plan_") for error in errors)
    runner_canary = _load_optional_json(run_dir / "runner_canary.json")
    if (
        runner_canary.get("status") != "passed"
        or runner_canary.get("same_shape_three_file_canary") is not True
        or runner_canary.get("multi_file_edit_proven") is not True
        or runner_canary.get("pytest_passes") is not True
    ):
        errors.append("runner_same_shape_canary_not_verified")
    docs_canary = _load_optional_json(run_dir / "docatlas_tool_visibility_canary.json")
    if (
        docs_canary.get("status") != "passed"
        or docs_canary.get("docatlas_tool_visibility_verified") is not True
        or docs_canary.get("no_code_edits") is not True
    ):
        errors.append("docatlas_visibility_canary_not_verified")
    checks["causal_canaries"] = not any(error.endswith("canary_not_verified") for error in errors)

    rows = _load_jsonl(run_dir / "runs.jsonl", errors)
    expected_cells = {
        (protocol["task_id"], condition, protocol["repeat"])
        for condition in protocol["conditions"]
    }
    indexed: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in rows:
        repeat = row.get("repeat")
        key = (str(row.get("task_id")), str(row.get("condition_id")), repeat)
        if isinstance(repeat, bool) or not isinstance(repeat, int):
            errors.append("invalid_cell_repeat")
            continue
        if key in indexed:
            errors.append("duplicate_cell:" + key[1])
        indexed[key] = row
    for key in sorted(expected_cells - set(indexed)):
        errors.append("missing_cell:" + key[1])
    for key in sorted(set(indexed) - expected_cells):
        errors.append("unexpected_cell:" + key[1])
    if len(rows) != len(protocol["conditions"]):
        errors.append("run_row_count_mismatch")
    checks["four_unique_cells"] = set(indexed) == expected_cells and len(rows) == len(expected_cells)

    provider_request_ids: set[str] = set()
    bounded_identities: list[tuple[str, str, str]] = []
    image_id_hashes: set[str] = set()
    for key in sorted(expected_cells):
        row = indexed.get(key)
        if row is None:
            continue
        condition = key[1]
        cell_dir = run_dir / protocol["task_id"] / condition / f"repeat_{protocol['repeat']}"
        persisted = _load_optional_json(cell_dir / "result.json")
        if not persisted:
            errors.append(f"{condition}:result_artifact_missing")
            continue
        if _json_sha256(persisted) != _json_sha256(row):
            errors.append(f"{condition}:result_jsonl_mismatch")
        _check_cell_result(condition, cell_dir, row, protocol, errors)
        _check_setup_artifacts(condition, cell_dir, row, errors)
        image_id_hashes.update(_check_boundaries(condition, cell_dir, row, errors))
        provider_request_ids.update(
            _check_runner_usage(condition, cell_dir, row, protocol, provider_request_ids, errors)
        )
        if condition.startswith("docatlas_bounded_"):
            identity = _check_bounded_evidence(condition, cell_dir, row, protocol, errors)
            if identity is not None:
                bounded_identities.append(identity)
        if condition == "docatlas_bounded_subagent":
            provider_request_ids.update(
                _check_worker_usage(cell_dir, row, protocol, provider_request_ids, errors)
            )

    if len(set(bounded_identities)) != 1 or len(bounded_identities) != 2:
        errors.append("bounded_lanes_do_not_share_exact_evidence")
    if len(provider_request_ids) > protocol["provider_request_budget"]:
        errors.append("provider_request_budget_exceeded")
    if len(image_id_hashes) != 1:
        errors.append("evaluator_image_identity_mismatch")
    provenance = _load_optional_json(run_dir / "task33c_sandbox_provenance.json")
    container_protocol = protocol.get("container") or {}
    if provenance.get("base_image") != container_protocol.get("base_image"):
        errors.append("sandbox_provenance_base_image_mismatch")
    if provenance.get("requirements_sha256") != container_protocol.get("requirements_sha256"):
        errors.append("sandbox_provenance_requirements_mismatch")
    if provenance.get("protocol_sha256") != _file_sha256(protocol_path):
        errors.append("sandbox_provenance_protocol_mismatch")
    if provenance.get("boundary_status") != "verified":
        errors.append("sandbox_provenance_boundary_not_verified")
    if image_id_hashes and provenance.get("image_id_sha256") not in image_id_hashes:
        errors.append("sandbox_provenance_image_id_mismatch")
    checks["shared_frozen_evidence"] = len(bounded_identities) == 2 and len(set(bounded_identities)) == 1
    checks["provider_request_identity"] = not any("request_id" in error for error in errors)
    checks["provider_request_budget"] = (
        len(provider_request_ids) <= protocol["provider_request_budget"]
    )
    checks["sandbox_identity"] = (
        len(image_id_hashes) == 1
        and provenance.get("image_id_sha256") in image_id_hashes
        and provenance.get("base_image") == container_protocol.get("base_image")
    )

    completeness = evaluate_task33c_pilot_completeness(rows)
    if completeness.get("complete") is not True:
        errors.extend("completeness:" + str(error) for error in completeness.get("errors", []))
    checks["legacy_completeness_recomputed"] = completeness.get("complete") is True

    manifest = build_artifact_manifest(run_dir)
    if not manifest["files"]:
        errors.append("empty_artifact_manifest")
    checks["artifact_allowlist"] = manifest["rejected"] == []
    if manifest["rejected"]:
        errors.extend("artifact_rejected:" + path for path in manifest["rejected"])

    errors = sorted(dict.fromkeys(errors))
    verdict = "VALID" if not errors else "INCONCLUSIVE"
    result = {
        "schema_version": "task33c-independent-validation-1",
        "valid": verdict == "VALID",
        "verdict": verdict,
        "protocol_sha256": _file_sha256(protocol_path),
        "run_directory": run_dir.name,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "cell_count": len(indexed),
        "artifact_count": len(manifest["files"]),
        "artifact_manifest_sha256": _json_sha256(manifest),
        "legacy_completeness_sha256": _json_sha256(completeness),
    }
    if write:
        _write_json(run_dir / MANIFEST_FILENAME, manifest)
        _write_json(run_dir / VALIDATION_FILENAME, result)
    return result


def build_artifact_manifest(run_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    rejected: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_symlink():
            rejected.append(path.relative_to(run_dir).as_posix() + ":symlink")
            continue
        if not path.is_file() or path.name in {VALIDATION_FILENAME, MANIFEST_FILENAME}:
            continue
        relative = path.relative_to(run_dir)
        if _artifact_allowed(relative):
            files.append({
                "path": relative.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            })
        elif any(part in {"env", ".venv", "__pycache__", ".pytest_cache", "attempts"} for part in relative.parts):
            continue
        else:
            rejected.append(relative.as_posix())
    return {
        "schema_version": "task33c-artifact-manifest-1",
        "files": files,
        "rejected": rejected,
    }


def _artifact_allowed(relative: Path) -> bool:
    if len(relative.parts) == 1:
        return relative.name in _TOP_LEVEL_ALLOWLIST
    if relative.name in _CELL_ALLOWLIST and len(relative.parts) == 4:
        return True
    if len(relative.parts) == 5 and relative.parts[-2] == "setup_baseline_artifacts":
        return relative.name == "uv.lock"
    if relative.parts[0] in {"runner_canary", "docatlas_tool_visibility_canary"}:
        return relative.name in _CELL_ALLOWLIST or relative.name.endswith(".json") or relative.name.endswith(".diff")
    return False


def _check_live_protocol(protocol: dict[str, Any], errors: list[str]) -> None:
    contracts = load_task_evaluation_contracts()
    contract = contracts.get(protocol["task_id"])
    if contract is None:
        errors.append("protocol_task_contract_missing")
        return
    expected = protocol["evaluation"]
    actual = {
        "patch_contract_id": contract.patch_contract_id,
        "contract_sha256": evaluation_contract_sha256(contract),
        "registry_sha256": evaluation_contract_registry_sha256(),
        "fixture_sha256": contract.fixture_sha256,
        "protocol_fixture_sha256": contract.protocol_fixture_sha256,
        "oracle_sha256": contract.oracle_sha256,
        "hidden_tests_sha256": contract.hidden_tests_sha256,
        "external_context_sha256": contract.external_context_sha256,
        "hidden_test_command": contract.semantic_test_command,
    }
    for field, value in actual.items():
        if expected.get(field) != value:
            errors.append("protocol_live_mismatch:" + field)
    if list(contract.allowed_paths) != protocol.get("required_target_paths"):
        errors.append("protocol_live_mismatch:required_target_paths")
    tasks_path = Path(__file__).with_name("tasks.jsonl")
    task = next(
        (
            json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines()
            if json.loads(line).get("task_id") == protocol["task_id"]
        ),
        None,
    )
    if not isinstance(task, dict):
        errors.append("protocol_task_manifest_missing")
    else:
        objective = task.get("issue_text")
        if not isinstance(objective, str) or hashlib.sha256(objective.encode()).hexdigest() != protocol["objective_sha256"]:
            errors.append("protocol_live_mismatch:objective_sha256")
        elif derive_task33_retrieval_query(objective) != protocol["query"]:
            errors.append("protocol_live_mismatch:query")
        if task.get("setup_command") != expected.get("setup_command"):
            errors.append("protocol_live_mismatch:setup_command")
        if task.get("test_command") != expected.get("public_test_command"):
            errors.append("protocol_live_mismatch:public_test_command")
    if protocol.get("query_derivation") != TASK33_QUERY_DERIVATION:
        errors.append("protocol_live_mismatch:query_derivation")
    requirements = Path(__file__).with_name("task33c_evaluator_requirements.txt")
    if _file_sha256(requirements) != (protocol.get("container") or {}).get("requirements_sha256"):
        errors.append("protocol_live_mismatch:evaluator_requirements")


def _check_plan(plan: dict[str, Any], protocol: dict[str, Any], errors: list[str]) -> None:
    expected = {
        "task_id": protocol["task_id"],
        "conditions": protocol["conditions"],
        "repeats": 1,
        "agent_turn_limit": protocol["agent_turn_limit"],
        "retrieval_call_budget": protocol["retrieval_call_budget"],
        "isolated_worker_attempt_budget": protocol["isolated_worker_attempt_budget"],
        "packet_token_budget": protocol["packet_token_budget"],
        "required_evidence_categories": protocol["required_evidence_categories"],
        "required_evidence_paths": protocol["required_evidence_paths"],
        "required_target_paths": protocol["required_target_paths"],
    }
    for field, value in expected.items():
        if plan.get(field) != value:
            errors.append("plan_mismatch:" + field)


def _check_cell_result(
    condition: str,
    cell_dir: Path,
    row: dict[str, Any],
    protocol: dict[str, Any],
    errors: list[str],
) -> None:
    if row.get("model") != protocol["model"]:
        errors.append(f"{condition}:model_mismatch")
    if row.get("runner_id") != "github-models":
        errors.append(f"{condition}:runner_mismatch")
    if row.get("forbidden_changes") != []:
        errors.append(f"{condition}:forbidden_changes")
    identity = ((row.get("evaluation_contract") or {}).get("artifact_identity") or {})
    expected = protocol["evaluation"]
    for result_field, protocol_field in (
        ("fixture_sha256", "fixture_sha256"),
        ("protocol_fixture_sha256", "protocol_fixture_sha256"),
        ("oracle_sha256", "oracle_sha256"),
        ("hidden_tests_sha256", "hidden_tests_sha256"),
        ("external_context_sha256", "external_context_sha256"),
    ):
        if identity.get(result_field) != expected.get(protocol_field):
            errors.append(f"{condition}:artifact_identity_mismatch:{result_field}")
    evaluation = row.get("evaluation_execution") or {}
    for gate in ("public_tests", "hidden_tests"):
        value = evaluation.get(gate) or {}
        if value.get("status") != "executed" or not _strict_int(value.get("returncode")):
            errors.append(f"{condition}:{gate}_evidence_missing")
        artifact_name = "public_test_result.json" if gate == "public_tests" else "hidden_test_result.json"
        artifact = _load_optional_json(cell_dir / artifact_name)
        if not artifact or any(
            artifact.get(field) != value.get(field)
            for field in ("status", "command", "returncode")
        ):
            errors.append(f"{condition}:{gate}_artifact_mismatch")


def _check_setup_artifacts(
    condition: str, cell_dir: Path, row: dict[str, Any], errors: list[str]
) -> None:
    setup = ((row.get("evaluation_execution") or {}).get("setup") or {})
    artifacts = setup.get("baseline_artifact_sha256") or {}
    for relative, expected_hash in artifacts.items():
        path = cell_dir / "setup_baseline_artifacts" / relative
        if not path.is_file() or _file_sha256(path) != expected_hash:
            errors.append(f"{condition}:setup_artifact_hash_mismatch:{relative}")


def _check_boundaries(
    condition: str, cell_dir: Path, row: dict[str, Any], errors: list[str]
) -> set[str]:
    hashes: set[str] = set()
    reported = ((row.get("evaluation_execution") or {}).get("boundaries") or {})
    for name in ("runner", "evaluator"):
        persisted = _load_optional_json(cell_dir / f"{name}_execution_boundary.json")
        if not persisted or persisted != reported.get(name):
            errors.append(f"{condition}:{name}_boundary_artifact_mismatch")
            continue
        if persisted.get("status") != "verified":
            errors.append(f"{condition}:{name}_boundary_not_verified")
        checks = persisted.get("checks")
        if isinstance(checks, dict) and not all(value is True for value in checks.values()):
            errors.append(f"{condition}:{name}_boundary_canary_failed")
        image_hash = persisted.get("image_id_sha256")
        if isinstance(image_hash, str) and len(image_hash) == 64:
            hashes.add(image_hash)
    return hashes


def _check_runner_usage(
    condition: str,
    cell_dir: Path,
    row: dict[str, Any],
    protocol: dict[str, Any],
    seen: set[str],
    errors: list[str],
) -> set[str]:
    usage = _load_optional_json(cell_dir / "github_models_usage.json")
    turns = usage.get("turns") if isinstance(usage.get("turns"), list) else []
    if not turns:
        errors.append(f"{condition}:runner_usage_missing")
        return set()
    request_ids: set[str] = set()
    totals = {"input": 0, "output": 0, "cached": 0, "reasoning": 0}
    for turn in turns:
        request_id = turn.get("request_id")
        if not isinstance(request_id, str) or not request_id or request_id in seen or request_id in request_ids:
            errors.append(f"{condition}:duplicate_or_missing_request_id")
        else:
            request_ids.add(request_id)
        raw = turn.get("usage") or {}
        prompt = raw.get("prompt_tokens")
        completion = raw.get("completion_tokens")
        total = raw.get("total_tokens")
        if not all(_nonnegative_int(value) for value in (prompt, completion, total)) or total != prompt + completion:
            errors.append(f"{condition}:invalid_provider_usage")
            continue
        totals["input"] += prompt
        totals["output"] += completion
        prompt_details = raw.get("prompt_tokens_details") or {}
        completion_details = raw.get("completion_tokens_details") or {}
        cached = prompt_details.get("cached_tokens")
        reasoning = completion_details.get("reasoning_tokens")
        if not _nonnegative_int(cached) or not _nonnegative_int(reasoning):
            errors.append(f"{condition}:incomplete_provider_usage_details")
        else:
            totals["cached"] += cached
            totals["reasoning"] += reasoning
        if not isinstance(turn.get("request_payload_sha256"), str) or len(turn["request_payload_sha256"]) != 64:
            errors.append(f"{condition}:provider_payload_hash_missing")
        if not _nonnegative_int(turn.get("estimated_input_tokens")) or turn["estimated_input_tokens"] > protocol["provider_input_token_limit"]:
            errors.append(f"{condition}:provider_input_budget_unproven")
    metrics = row.get("metrics") or {}
    parent = (row.get("token_attribution") or {}).get("parent") or {}
    for field, expected in (
        ("input_tokens", totals["input"]),
        ("output_tokens", totals["output"]),
        ("cached_input_tokens", totals["cached"]),
        ("reasoning_tokens", totals["reasoning"]),
    ):
        if metrics.get(field) != expected or parent.get(field) != expected:
            errors.append(f"{condition}:provider_total_mismatch:{field}")
    return request_ids


def _check_bounded_evidence(
    condition: str,
    cell_dir: Path,
    row: dict[str, Any],
    protocol: dict[str, Any],
    errors: list[str],
) -> tuple[str, str, str] | None:
    snapshot_json = _load_optional_json(cell_dir / "host_evidence_snapshot.json")
    manifest = _load_optional_json(cell_dir / "host_evidence_manifest.json")
    retrieval = _load_optional_json(cell_dir / "host_retrieval_metrics.json")
    try:
        snapshot = HostEvidenceSnapshot(
            query=snapshot_json["query"],
            objective_sha256=snapshot_json["objective_sha256"],
            query_derivation=snapshot_json["query_derivation"],
            evidence_items=tuple(snapshot_json["evidence_items"]),
            trust_contract=snapshot_json["trust_contract"],
            retrieval_issues=tuple(snapshot_json["retrieval_issues"]),
            evidence_categories=tuple(snapshot_json["evidence_categories"]),
            project_revision=snapshot_json["project_revision"],
            index_revision=snapshot_json["index_revision"],
            response_status=snapshot_json["response_status"],
            raw_retrieval_tokens=snapshot_json["raw_retrieval_tokens"],
            retrieval_wall_time_seconds=snapshot_json["retrieval_wall_time_seconds"],
            retrieval_calls=snapshot_json["retrieval_calls"],
        )
        snapshot.validate()
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        errors.append(f"{condition}:invalid_host_evidence_snapshot:{exc.__class__.__name__}")
        return None
    if snapshot.manifest() != manifest:
        errors.append(f"{condition}:host_evidence_manifest_mismatch")
    if snapshot.query != protocol["query"] or hashlib.sha256(snapshot.query.encode()).hexdigest() != protocol["query_sha256"]:
        errors.append(f"{condition}:frozen_query_mismatch")
    if snapshot.objective_sha256 != protocol["objective_sha256"]:
        errors.append(f"{condition}:objective_hash_mismatch")
    for field, expected in (
        ("evidence_fingerprint", snapshot.fingerprint),
        ("project_revision", snapshot.project_revision),
        ("index_revision", snapshot.index_revision),
        ("retrieval_calls", 1),
    ):
        if retrieval.get(field) != expected:
            errors.append(f"{condition}:retrieval_trace_mismatch:{field}")
    packet = _load_optional_json(cell_dir / "action_packet.json")
    packet_errors = validate_action_packet(
        packet, evidence_items=snapshot.evidence_items,
        max_tokens=protocol["packet_token_budget"],
    )
    errors.extend(f"{condition}:action_packet:{error}" for error in packet_errors)
    objective = (packet.get("task_interpretation") or {}).get("objective")
    if not isinstance(objective, str) or hashlib.sha256(objective.encode()).hexdigest() != protocol["objective_sha256"]:
        errors.append(f"{condition}:action_packet_objective_mismatch")
    missing_categories = missing_packet_evidence_categories(
        packet, snapshot.evidence_items, tuple(protocol["required_evidence_categories"])
    )
    missing_paths = missing_packet_evidence_paths(
        packet, snapshot.evidence_items, tuple(protocol["required_evidence_paths"])
    )
    if missing_categories or missing_paths:
        errors.append(f"{condition}:action_packet_required_evidence_missing")
    targets = {
        item.get("path") for item in (packet.get("target_surface") or {}).get("likely_files", [])
        if isinstance(item, dict)
    }
    if not set(protocol["required_target_paths"]).issubset(targets):
        errors.append(f"{condition}:action_packet_targets_missing")
    try:
        prompt_sources = json.loads(
            (cell_dir / "delivery_prompt_sources.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        prompt_sources = None
    expected_prompt_sources = [
        {"evidence_id": item.get("evidence_id"), "path": item.get("path")}
        for item in packet.get("source_of_truth", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str) and item["path"]
    ]
    if prompt_sources != expected_prompt_sources:
        errors.append(f"{condition}:delivery_prompt_source_manifest_mismatch")
    metrics = row.get("metrics") or {}
    if metrics.get("evidence_fingerprint") != snapshot.fingerprint:
        errors.append(f"{condition}:result_evidence_fingerprint_mismatch")
    return snapshot.fingerprint, snapshot.project_revision, snapshot.index_revision


def _check_worker_usage(
    cell_dir: Path,
    row: dict[str, Any],
    protocol: dict[str, Any],
    seen: set[str],
    errors: list[str],
) -> set[str]:
    condition = "docatlas_bounded_subagent"
    proof = _load_optional_json(cell_dir / "worker_usage_proof.json")
    metrics = _load_optional_json(cell_dir / "isolated_delivery_metrics.json")
    request_id = proof.get("request_id")
    if not isinstance(request_id, str) or not request_id or request_id in seen:
        errors.append(f"{condition}:duplicate_or_missing_worker_request_id")
        return set()
    expected = {
        "provider": metrics.get("worker_provider"),
        "model": metrics.get("worker_model"),
        "request_id": metrics.get("worker_request_id"),
        "input_tokens": metrics.get("worker_input_tokens"),
        "output_tokens": metrics.get("worker_output_tokens"),
        "reasoning_tokens": metrics.get("worker_reasoning_tokens"),
    }
    for field, value in expected.items():
        if proof.get(field) != value:
            errors.append(f"{condition}:worker_usage_proof_mismatch:{field}")
    if proof.get("requested_model") != protocol["model"]:
        errors.append(f"{condition}:worker_model_mismatch")
    if proof.get("prompt_revision") != protocol["worker_prompt_revision"]:
        errors.append(f"{condition}:worker_prompt_revision_mismatch")
    if metrics.get("worker_usage_proof_fingerprint") != _json_sha256(proof):
        errors.append(f"{condition}:worker_usage_proof_hash_mismatch")
    result_metrics = row.get("metrics") or {}
    for field in ("worker_input_tokens", "worker_output_tokens", "worker_reasoning_tokens"):
        if result_metrics.get(field) != metrics.get(field):
            errors.append(f"{condition}:worker_result_total_mismatch:{field}")
    if not _sha256_string(proof.get("response_schema_sha256")):
        errors.append(f"{condition}:worker_schema_hash_missing")
    if not _sha256_string(proof.get("request_payload_sha256")):
        errors.append(f"{condition}:worker_payload_hash_missing")
    if not _sha256_string(proof.get("message_sha256")):
        errors.append(f"{condition}:worker_message_hash_missing")
    if proof.get("evidence_fingerprint") != metrics.get("evidence_fingerprint"):
        errors.append(f"{condition}:worker_evidence_fingerprint_mismatch")
    estimated_input = proof.get("estimated_input_tokens")
    if not _nonnegative_int(estimated_input) or estimated_input > protocol["provider_input_token_limit"]:
        errors.append(f"{condition}:worker_input_budget_unproven")
    request_ids = proof.get("request_ids")
    if not isinstance(request_ids, dict) or request_id not in request_ids.values():
        errors.append(f"{condition}:worker_request_identity_mismatch")
    raw = proof.get("usage") or {}
    prompt = raw.get("prompt_tokens")
    completion = raw.get("completion_tokens")
    total = raw.get("total_tokens")
    cached = (raw.get("prompt_tokens_details") or {}).get("cached_tokens")
    reasoning = (raw.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if (
        not all(_nonnegative_int(value) for value in (prompt, completion, total, cached, reasoning))
        or total != prompt + completion
        or prompt != proof.get("input_tokens")
        or completion != proof.get("output_tokens")
        or reasoning != proof.get("reasoning_tokens")
    ):
        errors.append(f"{condition}:invalid_worker_provider_usage")
    return {request_id}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_optional_json(path: Path) -> dict[str, Any]:
    try:
        return _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        errors.append("runs_jsonl_missing_or_invalid")
        return []
    if any(not isinstance(row, dict) for row in rows):
        errors.append("runs_jsonl_non_object_row")
        return []
    return rows


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _strict_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _sha256_string(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independently validate a Task 33C causal evidence bundle")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = validate_task33c_run(args.run_dir, protocol_path=args.protocol)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
