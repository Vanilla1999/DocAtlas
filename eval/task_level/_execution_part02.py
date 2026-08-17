"""Implementation shard 2 for execution."""
from __future__ import annotations

from ._execution_shared import *  # noqa: F401,F403

from ._execution_part01 import _activated_run_environment, _first_optional_int, _load_optional_json, _optional_int, _run_evaluation_command, _run_setup, _runner_id_from_version, _seal_condition_setup_baseline, _semantic_check_execution_rows, _task_contract_validation, _trajectory_elapsed_seconds, _write_json_atomic, action_packet_project_doc_metrics, capture_patch, shell_call_metrics, trajectory_evidence_metrics, trajectory_tool_output_metrics

def evaluate_agent_patch(
    task: TaskSpec,
    workspace: Path,
    run_output_dir: Path,
    condition_id: str,
    trajectory_path: str | None,
    runner_output: Any,
    *,
    evaluation_backend: str = "docker",
) -> dict[str, Any]:
    patch_path, _, _, changed_files = capture_patch(workspace, run_output_dir)
    patch_exists = bool(patch_path.read_text(encoding="utf-8").strip())
    task_evaluation_contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
    protocol_task = TASK23_PROTOCOL_TASKS.get(task.task_id)
    contract_validation = _task_contract_validation(task, task_evaluation_contract, protocol_task)
    setup_evidence = _load_optional_json(run_output_dir / "condition_setup.json")
    if not setup_evidence:
        # Direct evaluator callers predate the pre-run setup gate. Keep them
        # functional, but mark this fallback so Task 33 completeness cannot
        # mistake a post-run setup for causal precondition evidence.
        setup_evidence = _run_condition_setup(
            task,
            workspace,
            run_output_dir,
            {},
            phase="evaluator_fallback",
        )
    setup_ok = setup_evidence.get("status") in {"success", "not_required"}
    evaluation_errors: list[str] = []
    public = None
    if setup_ok:
        try:
            public = _run_evaluation_command(
                task,
                task.test_command,
                workspace,
                run_output_dir,
                "public",
                180,
                evaluation_backend=evaluation_backend,
            )
        except Exception as exc:
            evaluation_errors.append(f"public:{exc.__class__.__name__}:{str(exc)[:1_000]}")
    _write_json_atomic(run_output_dir / "public_test_result.json", {
        "schema_version": 1,
        "status": "executed" if public is not None else "execution_failed" if evaluation_errors else "not_run",
        "command": public.command if public is not None else task.test_command,
        "returncode": public.returncode if public is not None else None,
        "stdout": public.stdout if public is not None else "",
        "stderr": public.stderr if public is not None else "",
        "errors": list(evaluation_errors),
    })
    hidden = None
    if setup_ok and contract_validation.valid and not evaluation_errors:
        copy_hidden_tests(task.task_id, workspace)
        hidden_command = task_evaluation_contract.semantic_test_command if task_evaluation_contract else "python -m pytest tests/hidden"
        try:
            hidden = _run_evaluation_command(
                task,
                hidden_command,
                workspace,
                run_output_dir,
                "hidden",
                180,
                evaluation_backend=evaluation_backend,
            )
        except Exception as exc:
            evaluation_errors.append(f"hidden:{exc.__class__.__name__}:{str(exc)[:1_000]}")
    _write_json_atomic(run_output_dir / "hidden_test_result.json", {
        "schema_version": 1,
        "status": "executed" if hidden is not None else "execution_failed" if evaluation_errors else "not_run",
        "command": hidden.command if hidden is not None else (
            task_evaluation_contract.semantic_test_command if task_evaluation_contract else None
        ),
        "returncode": hidden.returncode if hidden is not None else None,
        "stdout": hidden.stdout if hidden is not None else "",
        "stderr": hidden.stderr if hidden is not None else "",
        "errors": list(evaluation_errors),
    })
    if task.task_id in TASK23_PROTOCOL_TASKS or task_evaluation_contract is not None:
        compile_gate = (
            _run_compile_gate(
                task,
                task_evaluation_contract,
                workspace,
                run_output_dir,
                evaluation_backend=evaluation_backend,
            )
            if task_evaluation_contract is not None and setup_ok and contract_validation.valid and not evaluation_errors
            else {
                "status": "not_run",
                "passed": False,
                "command": task_evaluation_contract.compile_gate.command if task_evaluation_contract else None,
                "reason": "evaluation_contract_invalid_or_setup_failed",
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
        )
        patch_surface = evaluate_patch_surface(task_evaluation_contract, changed_files) if task_evaluation_contract and contract_validation.valid else {
            "status": "not_run",
            "violations": [],
        }
        evaluation_contract_status = contract_validation.status
        evaluation_contract_errors = list(contract_validation.errors)
    else:
        legacy_compile = run_command("python -m compileall -q src", workspace, 120) if patch_exists and setup_ok else None
        compile_gate = {
            "status": "passed" if legacy_compile and legacy_compile.passed else "failed" if legacy_compile else "not_run",
            "passed": bool(legacy_compile and legacy_compile.passed),
            "command": "python -m compileall -q src",
            "reason": "legacy_unfrozen_contract",
            "returncode": legacy_compile.returncode if legacy_compile else None,
            "stdout": legacy_compile.stdout if legacy_compile else "",
            "stderr": legacy_compile.stderr if legacy_compile else "",
        }
        patch_surface = {"status": "legacy", "violations": []}
        evaluation_contract_status = "legacy_unfrozen"
        evaluation_contract_errors = []
    generic_forbidden = forbidden_changed_paths(changed_files, ALLOWED_PATCH_PREFIXES) if patch_exists else []
    forbidden = sorted(set(generic_forbidden + list(patch_surface.get("violations", []))))
    audit = audit_trajectory(condition_id, Path(trajectory_path) if trajectory_path else None, run_output_dir / "policy_audit.json")
    stats = diff_stats_from_patch(patch_path.read_text(encoding="utf-8", errors="replace")) if patch_exists else None
    utilization = evaluate_docatlas_utilization(
        task=task,
        condition_id=condition_id,
        run_output_dir=run_output_dir,
        patch_path=patch_path,
        trajectory_path=Path(trajectory_path) if trajectory_path else None,
        agent_docatlas_calls=audit.docatlas_calls,
    )
    contract = evaluate_contract(task, workspace, patch_path)
    actionability = evaluate_actionability(
        task=task,
        condition_id=condition_id,
        run_output_dir=run_output_dir,
        patch_path=patch_path,
        trajectory_path=Path(trajectory_path) if trajectory_path else None,
        contract=contract,
    )
    patch_packet = load_patch_constraint_packet(run_output_dir / "patch_constraints.json")
    patch_constraint_usage = evaluate_patch_constraint_usage(
        patch_packet,
        patch_path,
        Path(trajectory_path) if trajectory_path else None,
    )
    constraint_validation = validate_patch_against_constraints(
        packet=patch_packet,
        changed_files=changed_files,
        diff_text=patch_path.read_text(encoding="utf-8", errors="replace") if patch_path.exists() else "",
        checks_run=[task.test_command] if public else [],
    ) if patch_packet else {"constraint_validation": {"total_constraints": 0, "satisfied": 0, "violated": 0, "unknown": 0, "violations": []}}
    (run_output_dir / "validation.json").write_text(json.dumps(constraint_validation, indent=2, sort_keys=True), encoding="utf-8")
    public_passed = bool(public and public.passed)
    hidden_passed = bool(hidden and hidden.passed)
    semantic_check_rows = _semantic_check_execution_rows(
        task_evaluation_contract.semantic_checks,
        hidden,
    ) if task_evaluation_contract else []
    semantic_gate = {
        "command": task_evaluation_contract.semantic_test_command if task_evaluation_contract else None,
        "status": "passed" if hidden_passed else "failed" if hidden is not None else "not_run",
        "passed": hidden_passed,
        "returncode": hidden.returncode if hidden is not None else None,
        "hidden_tests_sha256": task_evaluation_contract.hidden_tests_sha256 if task_evaluation_contract else None,
        "checks": semantic_check_rows,
    }
    compile_success = (
        None if compile_gate["status"] == "not_applicable" else bool(compile_gate["passed"])
    )
    evaluation_contract_valid = evaluation_contract_status in {"valid", "legacy_unfrozen"}
    resolved = (
        patch_exists
        and public_passed
        and hidden_passed
        and bool(compile_gate["passed"])
        and evaluation_contract_valid
        and audit.clean
        and not forbidden
    )
    runner_status = str(getattr(runner_output, "status", "completed") or "completed")
    if not setup_ok:
        status = "condition_setup_failed"
    elif runner_status in INFRASTRUCTURE_FAILURE_STATUSES:
        status = runner_status
    elif runner_status == "completed":
        status = "completed" if resolved or patch_exists else "no_patch"
    else:
        # Budget exhaustion and an explicit non-successful finish are valid
        # agent outcomes. Preserve them rather than relabelling any patch as a
        # successful runner completion.
        status = runner_status
    if not audit.clean:
        status = "policy_violation"
    if evaluation_errors:
        status = "runner_failed"
    injection = _load_optional_json(run_output_dir / "docatlas_context_injection.json")
    checklist_injection = _load_optional_json(run_output_dir / "action_checklist_injection.json")
    constraints_injection = _load_optional_json(run_output_dir / "patch_constraints_injection.json")
    external_injection = _load_optional_json(run_output_dir / "audited_external_context.json")
    docatlas_preparation = _load_optional_json(run_output_dir / "docatlas_preparation.json")
    isolated_delivery = _load_optional_json(run_output_dir / "isolated_delivery_metrics.json")
    bounded_direct = _load_optional_json(run_output_dir / "bounded_direct_metrics.json")
    host_retrieval = _load_optional_json(run_output_dir / "host_retrieval_metrics.json")
    action_packet = _load_optional_json(run_output_dir / "action_packet.json")
    runner_boundary = _load_optional_json(run_output_dir / "runner_execution_boundary.json")
    evaluator_boundary = _load_optional_json(run_output_dir / "evaluator_execution_boundary.json")
    packet_evidence_metrics = action_packet_project_doc_metrics(task, action_packet)
    materialized_identity = _load_optional_json(run_output_dir / "materialized.json")
    trajectory = Path(trajectory_path) if trajectory_path else run_output_dir / "missing-trajectory.json"
    evidence_metrics = trajectory_evidence_metrics(task, trajectory)
    tool_calls = getattr(runner_output, "tool_calls", [])
    tool_output_metrics = trajectory_tool_output_metrics(task, tool_calls)
    input_tokens = getattr(runner_output, "input_tokens", None)
    output_tokens = getattr(runner_output, "output_tokens", None)
    provider_usage = getattr(runner_output, "token_usage", {})
    provider_usage = provider_usage if isinstance(provider_usage, dict) else {}
    cached_input_tokens = _optional_int(provider_usage.get("cached_input_tokens"))
    reasoning_tokens = _optional_int(provider_usage.get("reasoning_tokens"))
    completed_turn_events = _optional_int(provider_usage.get("completed_turn_events"))
    effective_max_turns = _optional_int(provider_usage.get("effective_max_turns"))
    uncached_input_tokens = (
        input_tokens - cached_input_tokens
        if isinstance(input_tokens, int)
        and isinstance(cached_input_tokens, int)
        and 0 <= cached_input_tokens <= input_tokens
        else None
    )
    total_tokens = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
    worker_input_tokens = _optional_int(isolated_delivery.get("worker_input_tokens"))
    worker_output_tokens = _optional_int(isolated_delivery.get("worker_output_tokens"))
    worker_total_tokens = (
        worker_input_tokens + worker_output_tokens
        if worker_input_tokens is not None and worker_output_tokens is not None else None
    )
    system_total_tokens = (
        total_tokens + worker_total_tokens
        if total_tokens is not None and worker_total_tokens is not None
        else total_tokens if not isolated_delivery and total_tokens is not None else None
    )
    time_to_first_edit = _trajectory_elapsed_seconds(
        trajectory, getattr(runner_output, "started_at", None), event_kind="edit"
    )
    time_to_first_test = _trajectory_elapsed_seconds(
        trajectory, getattr(runner_output, "started_at", None), event_kind="test"
    )
    budget = {
        "max_input_tokens": task.max_input_tokens,
        "max_output_tokens": task.max_output_tokens,
        "measured_input_tokens": input_tokens,
        "input_token_basis": (
            "parent_provider_reported_input_including_cached"
            if isinstance(input_tokens, int)
            else None
        ),
        "indexing_provider_tokens_included": False,
        "configured_max_turns": task.max_turns,
        "effective_max_turns": effective_max_turns,
        "max_turns": effective_max_turns,
        "input_tokens_exceeded": isinstance(input_tokens, int) and input_tokens > task.max_input_tokens,
        "output_tokens_exceeded": isinstance(output_tokens, int) and output_tokens > task.max_output_tokens,
        "max_turns_enforced_by_runner": bool(getattr(runner_output, "max_turns_enforced", False)),
        "attempt_control": "one_ephemeral_process_with_timeout",
    }
    setup_wall_time = float(setup_evidence.get("wall_time_seconds") or 0.0) + sum(
        float(payload.get("wall_time_seconds", 0.0))
        for payload in (external_injection, docatlas_preparation, injection, checklist_injection, constraints_injection)
        if isinstance(payload.get("wall_time_seconds"), (int, float))
    )
    setup_wall_time += float(host_retrieval.get("retrieval_wall_time_seconds") or 0.0)
    setup_wall_time += float(isolated_delivery.get("broker_wall_time_seconds") or 0.0)
    total_latency = (
        setup_wall_time + float(getattr(runner_output, "wall_time_seconds", 0.0))
        if isinstance(getattr(runner_output, "wall_time_seconds", None), (int, float))
        else None
    )
    parent_retained_context_tokens = _first_optional_int(
        action_packet.get("estimated_tokens"),
        injection.get("injected_context_tokens"),
        tool_output_metrics.get("tool_output_tokens_estimate"),
    )
    normalized_shell_metrics = shell_call_metrics(tool_calls)
    metrics = RunMetrics(
        wall_time_seconds=getattr(runner_output, "wall_time_seconds", None),
        time_to_first_edit=time_to_first_edit,
        time_to_first_test=time_to_first_test,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        uncached_input_tokens=uncached_input_tokens,
        reasoning_tokens=reasoning_tokens,
        completed_turn_events=completed_turn_events,
        shell_calls=normalized_shell_metrics["shell_calls"],
        successful_shell_calls=normalized_shell_metrics["successful_shell_calls"],
        failed_shell_calls=normalized_shell_metrics["failed_shell_calls"],
        unknown_shell_outcomes=normalized_shell_metrics["unknown_shell_outcomes"],
        exec_error_count=normalized_shell_metrics["exec_error_count"],
        retried_command_count=normalized_shell_metrics["retried_command_count"],
        pytest_invocations=normalized_shell_metrics["pytest_invocations"],
        edit_calls=sum(1 for call in tool_calls if "edit" in json.dumps(call).lower()),
        test_runs=normalized_shell_metrics["test_runs"],
        docs_tool_calls=audit.docatlas_calls,
        patch_files_changed=stats[0] if stats else 0,
        patch_lines_added=stats[1] if stats else 0,
        patch_lines_removed=stats[2] if stats else 0,
        context_chunks_returned=int(injection.get("sources", 0)) if isinstance(injection, dict) else 0,
        injected_context_tokens=int(injection.get("injected_context_tokens")) if isinstance(injection.get("injected_context_tokens"), int) else None,
        retrieved_context_tokens=int(injection.get("retrieved_context_tokens")) if isinstance(injection.get("retrieved_context_tokens"), int) else None,
        raw_doc_context_tokens=int(injection.get("raw_doc_context_tokens")) if isinstance(injection.get("raw_doc_context_tokens"), int) else None,
        checklist_tokens=int(checklist_injection.get("checklist_tokens")) if isinstance(checklist_injection.get("checklist_tokens"), int) else None,
        constraint_packet_tokens=_optional_int(constraints_injection.get("constraint_packet_tokens")),
    )
    result = {
        "run_id": run_output_dir.parents[2].name,
        "task_id": task.task_id,
        "condition_id": condition_id,
        "repeat": int(run_output_dir.name.removeprefix("repeat_")),
        "runner_id": _runner_id_from_version(
            str(getattr(runner_output, "runner_version", ""))
        ),
        "runner_version": getattr(runner_output, "runner_version", "unknown"),
        "model": getattr(runner_output, "model", "unknown"),
        "status": status,
        "resolved": resolved,
        "public_tests_passed": public_passed,
        "hidden_tests_passed": hidden_passed,
        "tests_passed": public_passed,
        "compile_success": compile_success,
        "compile_status": compile_gate["status"],
        "evaluation_execution": {
            "setup": setup_evidence,
            "boundaries": {
                "runner": runner_boundary,
                "evaluator": evaluator_boundary,
            },
            "public_tests": {
                "status": "executed" if public is not None else "execution_failed" if evaluation_errors else "not_run",
                "command": task.test_command,
                "returncode": public.returncode if public is not None else None,
                "errors": evaluation_errors,
            },
            "hidden_tests": {
                "status": "executed" if hidden is not None else "execution_failed" if evaluation_errors else "not_run",
                "command": task_evaluation_contract.semantic_test_command if task_evaluation_contract else None,
                "returncode": hidden.returncode if hidden is not None else None,
                "errors": evaluation_errors,
            },
        },
        "evaluation_contract": {
            "status": evaluation_contract_status,
            "errors": evaluation_contract_errors,
            "patch_contract_id": task_evaluation_contract.patch_contract_id if task_evaluation_contract else None,
            "contract_sha256": evaluation_contract_sha256(task_evaluation_contract) if task_evaluation_contract else None,
            "registry_sha256": evaluation_contract_registry_sha256() if task_evaluation_contract else None,
            "artifact_identity": {
                "fixture_hash_algorithm": materialized_identity.get("fixture_hash_algorithm"),
                "fixture_sha256": materialized_identity.get("fixture_hash"),
                "protocol_fixture_hash_algorithm": materialized_identity.get("protocol_fixture_hash_algorithm"),
                "protocol_fixture_sha256": materialized_identity.get("protocol_fixture_hash"),
                "oracle_sha256": task_evaluation_contract.oracle_sha256 if task_evaluation_contract else None,
                "hidden_tests_sha256": task_evaluation_contract.hidden_tests_sha256 if task_evaluation_contract else None,
                "external_context_sha256": task_evaluation_contract.external_context_sha256 if task_evaluation_contract else None,
            },
            "compile_gate": compile_gate,
            "semantic_gate": semantic_gate,
            "patch_surface": patch_surface,
            "semantic_checks": semantic_check_rows,
        },
        "policy_clean": audit.clean,
        "policy": audit.to_json(),
        "docatlas": utilization.to_json(),
        "contract": contract.to_json(),
        "actionability": actionability.to_json(),
        "patch_constraints": patch_constraint_usage,
        "constraint_validation": constraint_validation["constraint_validation"],
        "constraint_packet_tokens": patch_constraint_usage.get("constraint_packet_tokens"),
        "constraint_count": patch_constraint_usage.get("constraint_count", 0),
        "constraint_used": patch_constraint_usage.get("constraint_used", False),
        "constraint_violations_after_patch": constraint_validation["constraint_validation"]["violated"],
        "patch_path": str(patch_path),
        "trajectory_path": trajectory_path,
        "changed_files": changed_files,
        "forbidden_changes": forbidden,
        "metrics": {
            "wall_time_seconds": metrics.wall_time_seconds,
            "time_to_first_edit": metrics.time_to_first_edit,
            "made_edit": metrics.time_to_first_edit is not None,
            "time_to_first_test": metrics.time_to_first_test,
            "total_latency": total_latency,
            "parent_retained_context_tokens": parent_retained_context_tokens,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "total_tokens": total_tokens,
            "cached_input_tokens": metrics.cached_input_tokens,
            "uncached_input_tokens": metrics.uncached_input_tokens,
            "reasoning_tokens": metrics.reasoning_tokens,
            **tool_output_metrics,
            "condition_setup_wall_time_seconds": setup_wall_time,
            "audited_external_context_tokens": _optional_int(external_injection.get("injected_context_tokens")),
            "completed_turn_events": metrics.completed_turn_events,
            "shell_calls": metrics.shell_calls,
            "successful_shell_calls": metrics.successful_shell_calls,
            "failed_shell_calls": metrics.failed_shell_calls,
            "unknown_shell_outcomes": metrics.unknown_shell_outcomes,
            "exec_error_count": metrics.exec_error_count,
            "retried_command_count": metrics.retried_command_count,
            "pytest_invocations": metrics.pytest_invocations,
            "edit_calls": metrics.edit_calls,
            "test_runs": metrics.test_runs,
            "docatlas_calls": audit.docatlas_calls,
            "agent_docatlas_calls": audit.docatlas_calls,
            "network_attempts": audit.network_attempts,
            "harness_docatlas_calls": utilization.harness_calls,
            "injected_context_tokens": metrics.injected_context_tokens,
            "checklist_tokens": metrics.checklist_tokens,
            "retrieved_context_tokens": metrics.retrieved_context_tokens,
            "constraint_packet_tokens": metrics.constraint_packet_tokens,
            "raw_doc_context_tokens": metrics.raw_doc_context_tokens,
            "action_packet_tokens": _optional_int(action_packet.get("estimated_tokens")),
            "worker_input_tokens": worker_input_tokens,
            "worker_output_tokens": worker_output_tokens,
            "worker_reasoning_tokens": _optional_int(isolated_delivery.get("worker_reasoning_tokens")),
            "worker_total_tokens": worker_total_tokens,
            "system_total_tokens": system_total_tokens,
            "delivery_retrieval_calls": _optional_int(
                (isolated_delivery or bounded_direct).get("retrieval_calls")
            ),
            "delivery_attempts": _optional_int(
                (isolated_delivery or bounded_direct).get("attempts")
            ),
            "action_packet_status": action_packet.get("status"),
            "action_packet_truncated": action_packet.get("status") == "truncated",
            "action_packet_insufficient_evidence": action_packet.get("status") == "insufficient_evidence",
            "action_packet_fidelity": "validated" if action_packet else "not_applicable",
            **packet_evidence_metrics,
            "evidence_fingerprint": (
                isolated_delivery.get("evidence_fingerprint")
                or bounded_direct.get("evidence_fingerprint")
                or host_retrieval.get("evidence_fingerprint")
            ),
            "fallback_used": utilization.fallback_used,
            "fallback_source": getattr(utilization, "fallback_source", None),
            "docatlas_retrieval_status": utilization.docatlas_retrieval_status,
            "vector_indexing_timed_out": utilization.vector_indexing_timed_out,
            **evidence_metrics,
        },
        "context": {
            "retrieved_count": int(utilization.context_retrieved) + audit.docatlas_calls,
            "used_count": int(utilization.context_used),
            "utilization_rate": 1.0 if utilization.context_used else 0.0 if utilization.context_retrieved or audit.docatlas_calls else None,
        },
        "notes": getattr(runner_output, "notes", []),
        "budget": budget,
        "token_attribution": {
            "schema_version": "task33-token-attribution-1",
            "parent": {
                "input_tokens": metrics.input_tokens,
                "cached_input_tokens": metrics.cached_input_tokens,
                "uncached_input_tokens": metrics.uncached_input_tokens,
                "output_tokens": metrics.output_tokens,
                "reasoning_tokens": metrics.reasoning_tokens,
                "total_tokens": total_tokens,
            },
            "worker": {
                "status": (
                    "measured" if isolated_delivery and worker_total_tokens is not None
                    else "partial" if isolated_delivery else "not_applicable"
                ),
                "input_tokens": worker_input_tokens,
                "output_tokens": worker_output_tokens,
                "reasoning_tokens": _optional_int(isolated_delivery.get("worker_reasoning_tokens")),
                "total_tokens": worker_total_tokens,
            },
            "indexing": {
                "status": docatlas_preparation.get("status") or "not_applicable",
                "provider_input_tokens": (
                    _optional_int(docatlas_preparation.get("provider_input_tokens")) or 0
                ),
                "provider_output_tokens": (
                    _optional_int(docatlas_preparation.get("provider_output_tokens")) or 0
                ),
                "included_in_parent_budget": False,
            },
            "raw_tool_output_tokens_estimate": _first_optional_int(
                isolated_delivery.get("raw_retrieval_tokens"),
                bounded_direct.get("raw_retrieval_tokens"),
                tool_output_metrics.get("tool_output_tokens_estimate"),
            ),
            "action_packet_tokens": _optional_int(action_packet.get("estimated_tokens")),
            "system_total_tokens": system_total_tokens,
            "system_total_definition": "parent provider total plus worker provider input/output; raw retrieval is reported separately to avoid double counting worker input",
            "system_total_complete": total_tokens is not None and (
                not isolated_delivery or worker_total_tokens is not None
            ),
            "provider_fields_available": sorted(
                key for key in ("cached_input_tokens", "reasoning_tokens", "completed_turn_events")
                if provider_usage.get(key) is not None
            ),
        },
    }
    if not setup_ok:
        result["notes"].append("condition setup was not valid; evaluator tests were not run")
    if evaluation_errors:
        result["notes"].append("evaluator command boundary failed: " + "; ".join(evaluation_errors))
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _run_compile_gate(
    task: TaskSpec,
    contract: Any,
    workspace: Path,
    run_output_dir: Path,
    *,
    evaluation_backend: str = "docker",
) -> dict[str, Any]:
    gate = contract.compile_gate
    if gate.mode == "not_applicable":
        return run_compile_gate(contract, workspace)
    completed = _run_evaluation_command(
        task,
        gate.command or "",
        workspace,
        run_output_dir,
        "compile",
        120,
        evaluation_backend=evaluation_backend,
    )
    return {
        "status": "passed" if completed.passed else "failed",
        "passed": completed.passed,
        "command": completed.command,
        "reason": None,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_condition_setup(
    task: TaskSpec,
    workspace: Path,
    run_output_dir: Path,
    env: dict[str, str],
    *,
    phase: str = "pre_runner",
) -> dict[str, Any]:
    started = time.monotonic()
    command = task.setup_command.strip()
    if not command:
        payload = {
            "schema_version": 1,
            "phase": phase,
            "status": "not_required",
            "command": "",
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "wall_time_seconds": 0.0,
        }
        _write_json_atomic(run_output_dir / "condition_setup.json", payload)
        return payload
    try:
        with _activated_run_environment(env):
            completed = _run_setup(task, workspace)
    except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
        payload = {
            "schema_version": 1,
            "phase": phase,
            "status": "condition_setup_failed",
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": f"{exc.__class__.__name__}: {str(exc)[:2_000]}",
            "wall_time_seconds": round(time.monotonic() - started, 6),
        }
    else:
        payload = {
            "schema_version": 1,
            "phase": phase,
            "status": "success" if completed.returncode == 0 else "condition_setup_failed",
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-20_000:],
            "stderr": completed.stderr[-20_000:],
            "wall_time_seconds": round(time.monotonic() - started, 6),
        }
        if completed.returncode == 0:
            baseline = _seal_condition_setup_baseline(
                workspace,
                run_output_dir,
                allowed_changed_files=("uv.lock",) if task.task_id in TASK23_PROTOCOL_TASKS else None,
            )
            payload.update(baseline)
            if baseline.get("baseline_status") != "sealed":
                payload["status"] = "condition_setup_failed"
                payload["stderr"] = (
                    payload["stderr"] + "\nsetup baseline sealing failed: "
                    + str(baseline.get("baseline_error") or "unknown")
                ).strip()
    _write_json_atomic(run_output_dir / "condition_setup.json", payload)
    return payload


def _archive_run_attempt(run_output_dir: Path) -> None:
    existing = [path for path in run_output_dir.iterdir() if path.name != "attempts"]
    if not existing:
        return
    attempts_dir = run_output_dir / "attempts"
    attempt_dir = attempts_dir / f"attempt_{len(list(attempts_dir.glob('attempt_*'))) + 1}"
    attempt_dir.mkdir(parents=True, exist_ok=False)
    for path in existing:
        shutil.move(str(path), str(attempt_dir / path.name))


def _load_run_results(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _host_evidence_categories(items: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    categories: set[str] = set()
    for item in items:
        source_class = str(item.get("source_class") or item.get("source_kind") or "").lower()
        if "project" in source_class or source_class in {"readme", "agent_policy"}:
            categories.add("project_docs")
        symbols = item.get("symbols")
        has_explicit_symbols = isinstance(symbols, (list, tuple)) and any(
            str(symbol.get("name") or "").strip() if isinstance(symbol, dict) else str(symbol).strip()
            for symbol in symbols
        )
        if source_class in {"repo_map", "code_graph"} and has_explicit_symbols:
            categories.add("symbols")
        if source_class in {"library_doc", "dependency_doc", "package_doc"}:
            categories.add("dependencies")
    return tuple(sorted(categories))


def _replace_path_in_json(value: Any, path: Path, replacement: str) -> Any:
    needle = str(path)
    if isinstance(value, dict):
        return {str(key): _replace_path_in_json(item, path, replacement) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_path_in_json(item, path, replacement) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_path_in_json(item, path, replacement) for item in value)
    if isinstance(value, str):
        return value.replace(needle, replacement)
    return value

__all__=['evaluate_agent_patch', '_run_compile_gate', '_run_condition_setup', '_archive_run_attempt', '_load_run_results', '_host_evidence_categories', '_replace_path_in_json']
