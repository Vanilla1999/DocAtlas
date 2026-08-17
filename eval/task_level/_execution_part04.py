"""Implementation shard 4 for execution."""
from __future__ import annotations

from ._execution_shared import *  # noqa: F401,F403

from ._execution_part01 import _estimate_tokens, _load_optional_json, _optional_int, _persist_delivery_prompt_sources, _task_contract_validation, _write_json_atomic, _write_text_atomic, build_tool_policy, capture_patch, fresh_run_environment, is_infrastructure_failure, run_artifact_integrity, serialize_run_results_jsonl
from ._execution_part02 import _archive_run_attempt, _load_run_results, _run_condition_setup, evaluate_agent_patch
from ._execution_part03 import _prepare_shared_task33_evidence, build_bounded_direct_packet, inject_docatlas_context, prepare_docatlas, runner_unavailable_result

def execute_pilot(
    tasks: list[TaskSpec],
    conditions: list[str],
    repeats: int,
    run_id: str,
    runner: AgentRunner,
    model: str,
    timeout_seconds: int,
    prompt_template: str,
    *,
    retry_infrastructure_failures: bool = False,
    isolated_worker: IsolatedWorker | None = None,
    isolated_worker_timeout_seconds: int = 60,
    evidence_tier: str = "causal",
    evaluation_backend: str = "docker",
) -> list[dict[str, Any]]:
    _assert_task33_run_preconditions(
        tasks,
        runner,
        evidence_tier=evidence_tier,
        conditions=conditions,
        repeats=repeats,
        evaluation_backend=evaluation_backend,
    )
    if retry_infrastructure_failures and any(task.task_id in TASK23_PROTOCOL_TASKS for task in tasks):
        raise ValueError("Task 33 one-attempt cells cannot use infrastructure retry")
    run_dir = RESULTS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    runs_path = run_dir / "runs.jsonl"
    if retry_infrastructure_failures and not runs_path.exists():
        raise FileNotFoundError(f"Cannot retry without existing run results: {runs_path}")
    results = _load_run_results(runs_path) if retry_infrastructure_failures else []
    result_indexes = {
        (result.get("task_id"), result.get("condition_id"), result.get("repeat")): index
        for index, result in enumerate(results)
    }
    configured_root = configured_runtime_root()
    runtime_root = Path(
        tempfile.mkdtemp(
            prefix=f"docatlas-task-level-{run_id}-",
            dir=str(configured_root) if configured_root is not None else None,
        )
    )
    try:
        total_runs = len(tasks) * len(conditions) * repeats
        for task in tasks:
            for repeat in range(repeats):
                shared_evidence: HostEvidenceSnapshot | None = None
                shared_preparation: dict[str, Any] = {}
                shared_evidence_error: str | None = None
                if any(CONDITIONS[condition].tool_policy.delivery_strategy for condition in conditions):
                    try:
                        shared_evidence, shared_preparation = _prepare_shared_task33_evidence(
                            task, runtime_root, repeat
                        )
                    except IsolatedDeliveryError as exc:
                        shared_evidence_error = str(exc)
                randomized = conditions[:]
                random.Random(f"{run_id}:{task.task_id}:{repeat}").shuffle(randomized)
                for condition_id in randomized:
                    run_output_dir = run_dir / task.task_id / condition_id / f"repeat_{repeat}"
                    run_output_dir.mkdir(parents=True, exist_ok=True)
                    cell = (task.task_id, condition_id, repeat)
                    existing_index = result_indexes.get(cell)
                    if existing_index is not None and not is_infrastructure_failure(results[existing_index]):
                        continue
                    if existing_index is not None:
                        _archive_run_attempt(run_output_dir)
                    workspace = runtime_root / task.task_id / condition_id / f"repeat_{repeat}" / "workspace"
                    materialized = materialize_fixture(task, workspace)
                    task_contract = TASK33_EVALUATION_CONTRACTS.get(task.task_id)
                    if task.task_id in TASK23_PROTOCOL_TASKS and (
                        task_contract is None
                        or materialized.get("fixture_hash") != task_contract.fixture_sha256
                        or materialized.get("protocol_fixture_hash") != task_contract.protocol_fixture_sha256
                    ):
                        raise ValueError(f"Task 33 materialized fixture identity mismatch: {task.task_id}")
                    (run_output_dir / "materialized.json").write_text(json.dumps(materialized, indent=2, sort_keys=True), encoding="utf-8")
                    policy_path, mcp_config = build_tool_policy(condition_id, run_output_dir)
                    env = fresh_run_environment(run_output_dir)
                    condition_setup = _run_condition_setup(
                        task,
                        workspace,
                        run_output_dir,
                        env,
                    )
                    setup_failed = condition_setup.get("status") == "condition_setup_failed"
                    delivery_strategy = CONDITIONS[condition_id].tool_policy.delivery_strategy
                    if not setup_failed and delivery_strategy:
                        if shared_evidence is None:
                            setup_failed = True
                            _write_json_atomic(run_output_dir / "host_retrieval_error.json", {
                                "status": "condition_setup_failed",
                                "reason": shared_evidence_error or "shared_host_evidence_unavailable",
                            })
                        else:
                            stage_task33_host_evidence(shared_evidence, shared_preparation, run_output_dir)
                    elif not setup_failed and condition_id in DOCATLAS_CONDITIONS:
                        diagnostics = prepare_docatlas(task, workspace, run_output_dir, env)
                        setup_failed = diagnostics.get("status") == "condition_setup_failed"
                    prompt = prompt_template.format(issue_text=task.issue_text) + "\nUse the tools available in this environment when they are useful.\n"
                    if delivery_strategy == "bounded_direct":
                        if not setup_failed and shared_evidence is not None:
                            try:
                                packet = build_bounded_direct_packet(
                                    task, workspace, run_output_dir, shared_evidence
                                )
                            except IsolatedDeliveryError as exc:
                                setup_failed = True
                                _write_json_atomic(run_output_dir / "bounded_direct_error.json", {
                                    "status": "condition_setup_failed", "reason": str(exc),
                                })
                            else:
                                if packet.get("status") == "insufficient_evidence":
                                    setup_failed = True
                                    _write_json_atomic(run_output_dir / "bounded_direct_error.json", {
                                        "status": "condition_setup_failed",
                                        "reason": "bounded_direct_insufficient_evidence",
                                    })
                                else:
                                    _persist_delivery_prompt_sources(run_output_dir, packet)
                                    projection = _load_optional_json(
                                        run_output_dir / "model_visible_patch_context.json"
                                    )
                                    prompt += (
                                        "\nDocAtlas source-backed Patch Contract (bounded direct):\n"
                                        + json.dumps(projection, sort_keys=True)
                                        + "\n"
                                        + BOUNDED_DIRECT_EXECUTION_POLICY
                                    )
                    elif delivery_strategy == "bounded_subagent":
                        if isolated_worker is None:
                            setup_failed = True
                            _write_json_atomic(run_output_dir / "isolated_delivery_error.json", {
                                "status": "condition_setup_failed",
                                "reason": "isolated_worker_capability_unavailable",
                            })
                        elif not setup_failed and shared_evidence is not None:
                            envelope = DelegationEnvelope(
                                task_objective=task.issue_text,
                                suspected_modules=task_contract.allowed_paths if task_contract else (),
                                changed_files=(),
                                required_evidence_categories=TASK33C_REQUIRED_EVIDENCE_CATEGORIES,
                                project_revision=shared_evidence.project_revision,
                                index_revision=shared_evidence.index_revision,
                                required_evidence_paths=TASK33C_REQUIRED_EVIDENCE_PATHS,
                                token_budget=2_000,
                            )
                            try:
                                delivery = (
                                    deliver_with_exploratory_worker
                                    if evidence_tier == "exploratory"
                                    else deliver_with_isolated_worker
                                )
                                handoff = delivery(
                                    worker=isolated_worker,
                                    envelope=envelope,
                                    evidence=shared_evidence,
                                    output_dir=run_output_dir,
                                    timeout_seconds=isolated_worker_timeout_seconds,
                                )
                            except IsolatedDeliveryError as exc:
                                setup_failed = True
                                _write_json_atomic(run_output_dir / "isolated_delivery_error.json", {
                                    "status": "condition_setup_failed", "reason": str(exc),
                                })
                            else:
                                if handoff["status"] == "insufficient_evidence":
                                    setup_failed = True
                                    _write_json_atomic(run_output_dir / "isolated_delivery_error.json", {
                                        "status": "condition_setup_failed",
                                        "reason": "isolated_action_packet_insufficient_evidence",
                                    })
                                else:
                                    _persist_delivery_prompt_sources(run_output_dir, handoff["packet"])
                                    prompt += "\nDocAtlas ActionPacket (isolated worker):\n" + json.dumps(handoff["packet"], sort_keys=True) + "\n"
                    if CONDITIONS[condition_id].tool_policy.inject_external_context:
                        external = inject_audited_external_context(task, run_output_dir)
                        if external.get("status") == "condition_setup_failed":
                            setup_failed = True
                        else:
                            prompt += "\n" + (run_output_dir / "audited_external_context.md").read_text(encoding="utf-8") + "\n"
                    if CONDITIONS[condition_id].tool_policy.inject_docatlas_context or CONDITIONS[condition_id].tool_policy.inject_action_checklist or CONDITIONS[condition_id].tool_policy.inject_patch_constraints:
                        injected = inject_docatlas_context(task, workspace, run_output_dir, env)
                        if injected.get("status") == "condition_setup_failed":
                            setup_failed = True
                        else:
                            if CONDITIONS[condition_id].tool_policy.inject_action_checklist:
                                checklist = inject_action_checklist(task, workspace, run_output_dir)
                                if checklist.get("status") == "condition_setup_failed":
                                    setup_failed = True
                            if CONDITIONS[condition_id].tool_policy.inject_patch_constraints:
                                constraints = inject_patch_constraints(task, workspace, run_output_dir)
                                if constraints.get("status") == "condition_setup_failed":
                                    setup_failed = True
                            if CONDITIONS[condition_id].tool_policy.inject_docatlas_context:
                                prompt += "\n" + (run_output_dir / "injected_context.md").read_text(encoding="utf-8") + "\n"
                            if CONDITIONS[condition_id].tool_policy.inject_action_checklist and (run_output_dir / "action_checklist.md").exists():
                                prompt += "\n" + (run_output_dir / "action_checklist.md").read_text(encoding="utf-8") + "\n"
                            if CONDITIONS[condition_id].tool_policy.inject_patch_constraints and (run_output_dir / "patch_constraints.md").exists():
                                prompt += "\n" + (run_output_dir / "patch_constraints.md").read_text(encoding="utf-8") + "\n"
                    if condition_id == "docatlas_patch_constraints_workflow":
                        prompt += "\nDocAtlas patch-constraints workflow guidance: before editing, use the available DocAtlas/docmancer docs tool to compile task-specific project constraints, including generated files, lockfiles, source-of-truth layers, architecture rules, dependency versions, and suggested checks. After editing, inspect your changed files and patch against those constraints; perform one repair pass if you find deterministic violations. Do not use hidden tests, gold patches, or oracle files.\n"
                    elif CONDITIONS[condition_id].tool_policy.recommend_docatlas_before_edit:
                        prompt += "\nDocAtlas workflow guidance: Use DocAtlas/docmancer documentation context before making code changes when the task may depend on library APIs, exact dependency versions, or project docs. Ask a task-specific documentation question, then use or ignore the returned context based on relevance.\n"
                    if CONDITIONS[condition_id].tool_policy.require_docatlas_call_before_edit:
                        prompt += "\n" + TOOL_REQUIRED_ONCE_INSTRUCTION + "\n"
                    if setup_failed:
                        result = condition_setup_failed_result(task, condition_id, run_output_dir)
                        _mark_exploratory_result(result, run_output_dir, evidence_tier)
                        if existing_index is None:
                            result_indexes[cell] = len(results)
                            results.append(result)
                        else:
                            results[existing_index] = result
                        write_run_progress(run_dir, results, total_runs, current={"task_id": task.task_id, "condition_id": condition_id, "repeat": repeat, "status": result["status"]})
                        continue
                    request = AgentRunRequest(
                        task_id=task.task_id,
                        condition_id=condition_id,
                        workspace=workspace,
                        prompt=prompt,
                        model=model,
                        timeout_seconds=timeout_seconds,
                        max_turns=(
                            min(task.max_turns, TASK33C_AGENT_TURN_LIMIT)
                            if task.task_id in TASK23_PROTOCOL_TASKS
                            else task.max_turns
                        ),
                        environment=env,
                        mcp_config_path=mcp_config,
                        tool_policy_path=policy_path,
                        output_dir=run_output_dir,
                        test_command=task.test_command,
                        allowed_write_paths=task_contract.allowed_paths if task_contract else (),
                        task_objective=task.issue_text,
                        max_input_tokens=task.max_input_tokens,
                    )
                    try:
                        output = runner.run(request)
                    except Exception as exc:
                        result = runner_unavailable_result(
                            task,
                            condition_id,
                            run_output_dir,
                            exc,
                            runner_id=getattr(runner, "runner_id", "unknown"),
                            model=model,
                        )
                    else:
                        result = evaluate_agent_patch(
                            task,
                            workspace,
                            run_output_dir,
                            condition_id,
                            output.trajectory_path,
                            output,
                            evaluation_backend=evaluation_backend,
                        )
                    _mark_exploratory_result(result, run_output_dir, evidence_tier)
                    if existing_index is None:
                        result_indexes[cell] = len(results)
                        results.append(result)
                    else:
                        results[existing_index] = result
                    write_run_progress(run_dir, results, total_runs, current={"task_id": task.task_id, "condition_id": condition_id, "repeat": repeat, "status": result["status"]})
    finally:
        shutil.rmtree(runtime_root, ignore_errors=True)
    write_run_progress(run_dir, results, len(tasks) * len(conditions) * repeats, current=None, finished=True)
    return results


def _mark_exploratory_result(
    result: dict[str, Any],
    output_dir: Path,
    evidence_tier: str,
) -> None:
    if evidence_tier != "exploratory":
        return
    result["execution_classification"] = "EXPLORATORY_NON_CAUSAL"
    result["causal_eligible"] = False
    result["hard_turn_limit_verified"] = False
    _write_json_atomic(output_dir / "result.json", result)


def _assert_task33_run_preconditions(
    tasks: list[TaskSpec],
    runner: AgentRunner,
    *,
    evidence_tier: str = "causal",
    conditions: list[str] | tuple[str, ...] | None = None,
    repeats: int | None = None,
    evaluation_backend: str = "docker",
) -> None:
    if evidence_tier not in {"causal", "exploratory"}:
        raise ValueError("Unknown Task 33 evidence tier: " + evidence_tier)
    formal_tasks = [task for task in tasks if task.task_id in TASK23_PROTOCOL_TASKS]
    if not formal_tasks:
        return
    if evaluation_backend not in {"docker", "host_exploratory"}:
        raise ValueError("Unknown evaluation backend: " + evaluation_backend)
    if evaluation_backend == "host_exploratory" and evidence_tier != "exploratory":
        raise ValueError("Task 33 host evaluator requires exploratory evidence tier")
    errors: list[str] = []
    for task in formal_tasks:
        validation = _task_contract_validation(
            task,
            TASK33_EVALUATION_CONTRACTS.get(task.task_id),
            TASK23_PROTOCOL_TASKS.get(task.task_id),
        )
        errors.extend(f"{task.task_id}:{error}" for error in validation.errors)
    if errors:
        raise ValueError("Task 33 evaluation preconditions failed: " + ",".join(errors))
    if evidence_tier == "causal":
        if not bool(getattr(runner, "hard_turn_limit_enforced", False)):
            raise ValueError(
                "Task 33 causal execution requires a runner with a proven hard turn limit"
            )
        if not bool(getattr(runner, "hard_input_budget_enforced", False)):
            raise ValueError(
                "Task 33 causal execution requires a runner with a proven hard cumulative input budget"
            )
        return
    allowed_conditions = {
        tuple(TASK33C_PILOT_CONDITIONS),
        tuple(TASK33C_EXPLORATORY_SMOKE_CONDITIONS),
    }
    if (
        [task.task_id for task in tasks] != [TASK33C_PILOT_TASK_ID]
        or tuple(conditions or ()) not in allowed_conditions
        or repeats != 1
        or getattr(runner, "runner_id", None) != "codex"
    ):
        raise ValueError(
            "Task 33 exploratory execution requires Codex and exactly the frozen protocol cells or two-cell smoke"
        )


def write_run_progress(run_dir: Path, results: list[dict[str, Any]], total_runs: int, *, current: dict[str, Any] | None, finished: bool = False) -> None:
    completed = len(results)
    _write_text_atomic(run_dir / "runs.jsonl", serialize_run_results_jsonl(results))
    integrity = run_artifact_integrity(run_dir, in_memory_results=completed, total_runs=total_runs, finished=finished)
    status = "finished" if finished else "running"
    if finished and not integrity["ok"]:
        status = "artifact_integrity_failed"
    infrastructure_failed_runs = sum(is_infrastructure_failure(result) for result in results)
    payload = {
        "status": status,
        "completed_runs": completed,
        "total_runs": total_runs,
        "remaining_runs": max(total_runs - completed, 0),
        "current": current,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_integrity": integrity,
        "runtime_integrity": {
            "ok": integrity["ok"] and infrastructure_failed_runs == 0,
            "valid_runs": completed - infrastructure_failed_runs,
            "infrastructure_failed_runs": infrastructure_failed_runs,
        },
        "latest_results": [
            {
                "task_id": result.get("task_id"),
                "condition_id": result.get("condition_id"),
                "status": result.get("status"),
                "resolved": result.get("resolved"),
                "public_tests_passed": result.get("public_tests_passed"),
                "hidden_tests_passed": result.get("hidden_tests_passed"),
                "agent_docatlas_calls": result.get("docatlas", {}).get("agent_calls") if isinstance(result.get("docatlas"), dict) else None,
                "context_used": result.get("docatlas", {}).get("context_used") if isinstance(result.get("docatlas"), dict) else None,
                "policy_clean": result.get("policy_clean"),
                "checklist_items": len(result.get("actionability", {}).get("checklist_items", [])) if isinstance(result.get("actionability"), dict) else 0,
                "checklist_used": result.get("actionability", {}).get("action_checklist_used") if isinstance(result.get("actionability"), dict) else None,
            }
            for result in results[-8:]
        ],
    }
    _write_json_atomic(run_dir / "status.json", payload)


def inject_audited_external_context(
    task: TaskSpec,
    output_dir: Path,
    *,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = snapshot_path or AUDITED_EXTERNAL_CONTEXT_ROOT / f"{task.task_id}.json"
    snapshot = _load_optional_json(source_path)
    content = snapshot.get("content") if isinstance(snapshot.get("content"), str) else ""
    actual_hash = hashlib.sha256(content.encode()).hexdigest()
    errors: list[str] = []
    if snapshot.get("schema_version") != "audited-external-context-1":
        errors.append("unsupported_schema_version")
    if snapshot.get("task_id") != task.task_id:
        errors.append("task_id_mismatch")
    if not content:
        errors.append("empty_content")
    if snapshot.get("content_sha256") != actual_hash:
        errors.append("content_hash_mismatch")
    if any(not snapshot.get(field) for field in ("library", "version", "source_url", "retrieved_at")):
        errors.append("missing_provenance")
    if errors:
        payload = {
            "status": "condition_setup_failed",
            "errors": errors,
            "snapshot_path": str(source_path),
            "wall_time_seconds": time.monotonic() - started,
        }
        _write_json_atomic(output_dir / "audited_external_context.json", payload)
        return payload

    markdown = (
        "# Audited external dependency context\n\n"
        f"Library: {snapshot['library']} {snapshot['version']}\n"
        f"Source: {snapshot['source_url']}\n"
        f"Snapshot SHA-256: {actual_hash}\n\n"
        f"{content}\n"
    )
    if len(markdown) > CONTEXT_INJECTION_LIMIT_CHARS:
        markdown = markdown[:CONTEXT_INJECTION_LIMIT_CHARS] + "\n\n[truncated by benchmark harness]\n"
    (output_dir / "audited_external_context.md").write_text(markdown, encoding="utf-8")
    payload = {
        "status": "success",
        "task_id": task.task_id,
        "library": snapshot["library"],
        "version": snapshot["version"],
        "source_url": snapshot["source_url"],
        "retrieved_at": snapshot["retrieved_at"],
        "content_sha256": actual_hash,
        "injected_context_tokens": _estimate_tokens(markdown),
        "wall_time_seconds": time.monotonic() - started,
    }
    _write_json_atomic(output_dir / "audited_external_context.json", payload)
    return payload


def stage_task33_host_evidence(
    evidence: HostEvidenceSnapshot,
    preparation: dict[str, Any],
    output_dir: Path,
) -> None:
    persist_host_evidence(evidence, output_dir)
    _write_json_atomic(output_dir / "docatlas_preparation.json", preparation)
    _write_json_atomic(output_dir / "host_retrieval_metrics.json", {
        "schema_version": 1,
        "status": evidence.response_status,
        "retrieval_calls": evidence.retrieval_calls,
        "query_sha256": hashlib.sha256(evidence.query.encode("utf-8")).hexdigest(),
        "objective_sha256": evidence.objective_sha256,
        "query_derivation": evidence.query_derivation,
        "evidence_fingerprint": evidence.fingerprint,
        "evidence_count": len(evidence.evidence_items),
        "evidence_categories": list(evidence.evidence_categories),
        "project_revision": evidence.project_revision,
        "index_revision": evidence.index_revision,
        "raw_retrieval_tokens": evidence.raw_retrieval_tokens,
        "retrieval_wall_time_seconds": evidence.retrieval_wall_time_seconds,
        "retrieval_issues": list(evidence.retrieval_issues),
        "shared_frozen_capture": True,
    })


def inject_action_checklist(task: TaskSpec, workspace: Path, output_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    response_path = output_dir / "docatlas_response.json"
    try:
        response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else {}
        items = build_action_checklist(
            task_id=task.task_id,
            issue_text=task.issue_text,
            docatlas_response=response,
            workspace=workspace,
        )
        save_action_checklist(items, output_dir)
    except Exception as exc:
        payload = {"status": "condition_setup_failed", "error": repr(exc), "wall_time_seconds": round(time.monotonic() - started, 4)}
        (output_dir / "action_checklist_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload
    markdown = (output_dir / "action_checklist.md").read_text(encoding="utf-8") if (output_dir / "action_checklist.md").exists() else ""
    payload = {"status": "success", "checklist_items": len(items), "checklist_tokens": _estimate_tokens(markdown), "wall_time_seconds": round(time.monotonic() - started, 4)}
    (output_dir / "action_checklist_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def inject_patch_constraints(task: TaskSpec, workspace: Path, output_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    response_path = output_dir / "docatlas_response.json"
    policy = CONDITIONS["docatlas_patch_constraints_workflow"].tool_policy
    try:
        response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else {}
        packet = build_patch_constraint_packet(
            task=task,
            workspace=workspace,
            docatlas_response=response,
            max_constraints=policy.max_constraints,
            max_sources=policy.max_sources,
            max_tokens=policy.max_constraint_packet_tokens,
        )
        save_patch_constraint_packet(packet, output_dir)
        # Stable artifact names for the targeted patch-constraints workflow.
        (output_dir / "constraints.json").write_text((output_dir / "patch_constraints.json").read_text(encoding="utf-8"), encoding="utf-8")
        (output_dir / "constraints.md").write_text((output_dir / "patch_constraints.md").read_text(encoding="utf-8"), encoding="utf-8")
    except Exception as exc:
        payload = {"status": "condition_setup_failed", "error": repr(exc), "wall_time_seconds": round(time.monotonic() - started, 4)}
        (output_dir / "patch_constraints_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload
    payload = {
        "status": "success",
        "constraint_count": len(packet.constraints),
        "constraint_packet_tokens": packet.token_estimate,
        "wall_time_seconds": round(time.monotonic() - started, 4),
    }
    (output_dir / "patch_constraints_injection.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def condition_setup_failed_result(task: TaskSpec, condition_id: str, run_output_dir: Path) -> dict[str, Any]:
    action_packet = _load_optional_json(run_output_dir / "action_packet.json")
    delivery = (
        _load_optional_json(run_output_dir / "isolated_delivery_metrics.json")
        or _load_optional_json(run_output_dir / "bounded_direct_metrics.json")
    )
    host_retrieval = _load_optional_json(run_output_dir / "host_retrieval_metrics.json")
    condition_setup = _load_optional_json(run_output_dir / "condition_setup.json")
    reason_payload = (
        condition_setup
        if condition_setup.get("status") == "condition_setup_failed"
        else {}
    ) or (
        _load_optional_json(run_output_dir / "isolated_delivery_error.json")
        or _load_optional_json(run_output_dir / "bounded_direct_error.json")
        or _load_optional_json(run_output_dir / "host_retrieval_error.json")
    )
    result = {
        "run_id": run_output_dir.parents[2].name,
        "task_id": task.task_id,
        "condition_id": condition_id,
        "repeat": int(run_output_dir.name.removeprefix("repeat_")),
        "runner_id": "not_run",
        "status": "condition_setup_failed",
        "resolved": False,
        "public_tests_passed": False,
        "hidden_tests_passed": False,
        "tests_passed": False,
        "compile_success": False,
        "compile_status": "not_run",
        "evaluation_execution": {
            "setup": condition_setup,
            "public_tests": {"status": "not_run", "command": task.test_command, "returncode": None},
            "hidden_tests": {"status": "not_run", "command": None, "returncode": None},
        },
        "policy_clean": False,
        "policy": {"clean": False, "violations": ["condition_setup_failed"]},
        "docatlas": {
            "available": True,
            "harness_calls": _optional_int(host_retrieval.get("retrieval_calls")) or 0,
            "agent_calls": 0,
            "context_retrieved": bool(host_retrieval.get("evidence_count")),
            "context_injected": False,
            "context_used": False,
            "context_used_confidence": "none",
            "used_symbols": [],
            "used_sources": [],
            "docatlas_retrieval_status": host_retrieval.get("status"),
        },
        "contract": {},
        "actionability": {"checklist_items": [], "action_checklist_used": False},
        "metrics": {
            "delivery_retrieval_calls": _optional_int(host_retrieval.get("retrieval_calls")),
            "raw_doc_context_tokens": _optional_int(host_retrieval.get("raw_retrieval_tokens")),
            "action_packet_tokens": _optional_int(action_packet.get("estimated_tokens")),
            "action_packet_status": action_packet.get("status"),
            "action_packet_truncated": action_packet.get("status") == "truncated",
            "action_packet_insufficient_evidence": action_packet.get("status") == "insufficient_evidence",
            "action_packet_fidelity": "validated" if action_packet else "not_available",
            "evidence_fingerprint": delivery.get("evidence_fingerprint") or host_retrieval.get("evidence_fingerprint"),
            "worker_input_tokens": _optional_int(delivery.get("worker_input_tokens")),
            "worker_output_tokens": _optional_int(delivery.get("worker_output_tokens")),
            "time_to_first_edit": None,
            "total_latency": (
                float(condition_setup["wall_time_seconds"])
                if isinstance(condition_setup.get("wall_time_seconds"), (int, float))
                and not isinstance(condition_setup.get("wall_time_seconds"), bool)
                else None
            ),
        },
        "notes": [
            "Condition setup failed; agent and evaluator tests were not run.",
            str(
                reason_payload.get("reason")
                or reason_payload.get("stderr")
                or "condition_setup_failed"
            )[:2_000],
        ],
    }
    (run_output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def run_canary(runner: AgentRunner, model: str, timeout_seconds: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="docatlas-runner-canary-"))
    try:
        (workspace / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        (workspace / "normalization.py").write_text("def normalize(value):\n    return value - 1\n", encoding="utf-8")
        (workspace / "policy.py").write_text("def may_enter(allowed):\n    return not allowed\n", encoding="utf-8")
        (workspace / "test_calc.py").write_text(
            "from calc import add\nfrom normalization import normalize\nfrom policy import may_enter\n\n\n"
            "def test_add():\n    assert add(2, 3) == 5\n\n\n"
            "def test_normalize():\n    assert normalize(-4) == 4\n\n\n"
            "def test_policy():\n    assert may_enter(True) is True\n    assert may_enter(False) is False\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=workspace, check=False)
        subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=workspace, check=False)
        subprocess.run(["git", "add", "."], cwd=workspace, check=False)
        subprocess.run(["git", "commit", "-m", "canary base"], cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        policy_path, mcp_config = build_tool_policy("repo_only", output_dir)
        env = fresh_run_environment(output_dir)
        canary_test_command = f"{shlex.quote(sys.executable)} -m pytest test_calc.py -q"
        request = AgentRunRequest(
            task_id="runner_canary",
            condition_id="repo_only",
            workspace=workspace,
            prompt=(
                "Fix three independent defects: add(a, b) currently subtracts, normalize(value) "
                "must return the absolute magnitude, and may_enter(allowed) must preserve the allowed boolean. "
                "Change all three source files and run the tests. "
                "Do not use web, curl, wget, or external network."
            ),
            model=model,
            timeout_seconds=timeout_seconds,
            max_turns=8,
            environment=env,
            mcp_config_path=mcp_config,
            tool_policy_path=policy_path,
            output_dir=output_dir,
            test_command=canary_test_command,
            allowed_write_paths=("calc.py", "normalization.py", "policy.py"),
        )
        runner_output = runner.run(request)
        patch_path, _, _, changed = capture_patch(workspace, output_dir)
        if os.environ.get("TASK33C_REQUIRE_DOCKER_SANDBOX") == "1":
            sandbox, boundary = verified_task33_sandbox(os.environ.get("TASK33C_TEST_CONTAINER_IMAGE", ""))
            persist_boundary(output_dir / "canary_execution_boundary.json", boundary)
            if boundary.get("status") != "verified":
                raise RuntimeError("runner canary requires a verified Docker execution boundary")
            sandbox_result = sandbox.run(canary_test_command, workspace, 60)
            tests = CommandResult(
                command=shlex.join(sandbox_result.command),
                returncode=sandbox_result.returncode,
                stdout=sandbox_result.stdout,
                stderr=sandbox_result.stderr,
            )
        else:
            tests = run_command(canary_test_command, workspace, 60)
        audit = audit_trajectory("repo_only", Path(runner_output.trajectory_path) if runner_output.trajectory_path else None, output_dir / "policy_audit.json")
        raw_stdout = Path(runner_output.raw_stdout_path).read_text(encoding="utf-8") if Path(runner_output.raw_stdout_path).exists() else ""
        network_probe_denied = "blocked by benchmark network policy" in raw_stdout
        canary_policy_clean = audit.clean or (network_probe_denied and audit.docatlas_calls == 0 and audit.context7_calls == 0)
        payload = {
            "task_id": "runner_canary",
            "status": "passed" if patch_path.read_text(encoding="utf-8").strip() and tests.passed and canary_policy_clean and runner_output.exit_code is not None and {"calc.py", "normalization.py", "policy.py"}.issubset(changed) else "failed",
            "runner_status": runner_output.status,
            "runner_exit_code": runner_output.exit_code,
            "patch_exists": bool(patch_path.read_text(encoding="utf-8").strip()),
            "pytest_passes": tests.passed,
            "trajectory_exists": bool(runner_output.trajectory_path and Path(runner_output.trajectory_path).exists()),
            "runner_exit_interpretable": runner_output.exit_code is not None,
            "policy_clean": canary_policy_clean,
            "network_probe_denied": network_probe_denied,
            "changed_files": changed,
            "multi_file_edit_proven": {"calc.py", "normalization.py", "policy.py"}.issubset(changed),
            "same_shape_three_file_canary": True,
            "failure_summary": "runner did not produce a patch" if not patch_path.read_text(encoding="utf-8").strip() else "",
            "workspace": str(workspace),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        return payload
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

__all__=['execute_pilot', '_mark_exploratory_result', '_assert_task33_run_preconditions', 'write_run_progress', 'inject_audited_external_context', 'stage_task33_host_evidence', 'inject_action_checklist', 'inject_patch_constraints', 'condition_setup_failed_result', 'run_canary']
