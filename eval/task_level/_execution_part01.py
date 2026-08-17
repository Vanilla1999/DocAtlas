"""Implementation shard 1 for execution."""
from __future__ import annotations

from ._execution_shared import *  # noqa: F401,F403


def is_infrastructure_failure(result: dict[str, Any]) -> bool:
    if result.get("status") in INFRASTRUCTURE_FAILURE_STATUSES:
        return True
    metrics = result.get("metrics") or {}
    return result.get("status") == "no_patch" and metrics.get("total_tokens") is None


def _semantic_check_execution_rows(
    checks: tuple[SemanticCheck, ...],
    result: CommandResult | None,
) -> list[dict[str, Any]]:
    if result is None:
        status_by_check = {check.check_id: "not_run" for check in checks}
    elif result.returncode == 0:
        status_by_check = {check.check_id: "passed" for check in checks}
    elif result.returncode == 1:
        output = result.stdout + "\n" + result.stderr
        observed_test_ids: dict[str, set[str]] = {}
        for status in ("PASSED", "FAILED"):
            nodes = re.findall(rf"(?m)^{status}\s+(\S+::\S+)", output)
            nodes.extend(re.findall(rf"(?m)^(\S+::\S+)\s+{status}\b", output))
            observed_test_ids[status] = {
                node.split("::")[-1].split("[", 1)[0]
                for node in nodes
            }
        status_by_check = {}
        for check in checks:
            test_ids = set(check.test_ids)
            if test_ids.intersection(observed_test_ids["FAILED"]):
                status = "failed"
            elif test_ids and test_ids.issubset(observed_test_ids["PASSED"]):
                status = "passed"
            else:
                status = "unknown"
            status_by_check[check.check_id] = status
    else:
        status_by_check = {check.check_id: "unknown" for check in checks}
    return [
        {
            "id": check.check_id,
            "description": check.description,
            "test_ids": list(check.test_ids),
            "status": status_by_check[check.check_id],
        }
        for check in checks
    ]


def _bounded_direct_projection_errors(
    projection: dict[str, Any], validation_errors: list[str]
) -> list[str]:
    errors = list(validation_errors)
    if projection.get("status") not in {"ok", "truncated"}:
        errors.append("bounded direct requires a successful model-visible projection")
        errors.extend(
            f"projection missing: {item}"
            for item in projection.get("missing", [])
            if isinstance(item, str) and item.strip()
        )
    return errors


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


def trajectory_evidence_metrics(task: Any, trajectory_path: Path) -> dict[str, Any]:
    evidence = list(dict.fromkeys([*task.expected_symbols, *task.expected_project_docs]))
    try:
        events = json.loads(trajectory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        events = []
    ranked_text = [json.dumps(event, sort_keys=True).lower() for event in events if isinstance(event, dict)]
    ranks = [
        index
        for item in evidence
        for index, text in enumerate(ranked_text, start=1)
        if item.lower() in text
        for _ in [None]
    ]
    found = sum(1 for item in evidence if any(item.lower() in text for text in ranked_text))
    return {
        "required_evidence_total": len(evidence),
        "required_evidence_found": found,
        "required_evidence_recall": found / len(evidence) if evidence else None,
        "first_required_evidence_rank": min(ranks) if ranks else None,
    }


def trajectory_tool_output_metrics(task: Any, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [item.lower() for item in dict.fromkeys([*task.expected_symbols, *task.expected_project_docs])]
    total_chars = 0
    docs_chars = 0
    evidence_found: set[str] = set()
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        summary = str(call.get("result_summary") or "")
        result_chars = call.get("result_chars")
        chars = result_chars if isinstance(result_chars, int) and result_chars >= 0 else len(summary)
        total_chars += chars
        tool_name = str(call.get("tool_name") or "").lower()
        is_docs_context = any(marker in tool_name for marker in ("get_docs_context", "prepare_docs", "docs_status", "docmancer", "doc-atlas"))
        if is_docs_context:
            docs_chars += chars
            summary_lower = summary.lower()
            evidence_found.update(marker for marker in evidence if marker in summary_lower)
    return {
        "tool_output_chars": total_chars,
        "tool_output_tokens_estimate": _estimate_tokens_from_chars(total_chars),
        "docs_context_output_chars": docs_chars,
        "docs_output_evidence_total": len(evidence),
        "docs_output_evidence_found": len(evidence_found),
        "docs_output_evidence_coverage": len(evidence_found) / len(evidence) if evidence else None,
        "useful_context_ratio": None,
        "useful_context_ratio_method": "not_measured_without_chunk_usage_attribution",
    }


def _shell_command(call: dict[str, Any]) -> str | None:
    tool_name = str(
        call.get("tool_name") or call.get("name") or call.get("tool") or ""
    ).strip().lower()
    if tool_name not in _SHELL_TOOL_NAMES and not tool_name.startswith("bash."):
        return None
    arguments = call.get("arguments")
    if not isinstance(arguments, dict):
        arguments = call.get("input") if isinstance(call.get("input"), dict) else {}
    command = arguments.get("command") or arguments.get("cmd") or arguments.get("script")
    if isinstance(command, list):
        command = " ".join(str(item) for item in command)
    return str(command).strip() if command not in (None, "") else ""


def _shell_outcome(call: dict[str, Any]) -> bool | None:
    exit_code = call.get("exit_code")
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        return exit_code == 0
    is_error = call.get("is_error")
    if isinstance(is_error, bool):
        return not is_error
    status = str(call.get("execution_status") or call.get("status") or "").strip().lower()
    if status in _SUCCESS_STATUSES:
        return True
    if status in _FAILURE_STATUSES:
        return False
    return None


def _shell_exec_error(call: dict[str, Any]) -> bool:
    """Distinguish runner/spawn failure from a command that executed and exited non-zero."""

    exit_code = call.get("exit_code")
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        return False
    status = str(call.get("execution_status") or call.get("status") or "").strip().lower()
    if status in {"runner_failed", "spawn_failed", "exec_error", "transport_error"}:
        return True
    return call.get("is_error") is True and exit_code is None


def _unwrap_shell_command(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return re.sub(r"\s+", " ", command).strip()
    if not tokens:
        return ""
    executable = Path(tokens[0]).name.lower()
    if executable in {"bash", "sh", "zsh"}:
        for index, token in enumerate(tokens[1:], start=1):
            if token in {"-c", "-lc", "-cl"} and index + 1 < len(tokens):
                return re.sub(r"\s+", " ", tokens[index + 1]).strip()
    return re.sub(r"\s+", " ", command).strip()


def _command_fingerprint(command: str) -> str:
    normalized = _unwrap_shell_command(command)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _test_runner_for_segment(segment: str) -> str | None:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return None
    while tokens and "=" in tokens[0] and not tokens[0].startswith(("/", "./")):
        tokens.pop(0)
    if not tokens:
        return None
    executable = Path(tokens[0]).name.lower()
    rest = [token.lower() for token in tokens[1:]]
    if executable in {"pytest", "py.test"}:
        return "pytest"
    if executable in {"python", "python3", "pypy", "pypy3"}:
        if len(rest) >= 2 and rest[0] == "-m" and rest[1] in {"pytest", "unittest"}:
            return rest[1]
        return None
    if executable == "uv" and "run" in rest:
        run_index = rest.index("run") + 1
        nested = tokens[run_index + 1 :]
        while nested and nested[0].startswith("-"):
            nested.pop(0)
        return _test_runner_for_segment(shlex.join(nested)) if nested else None
    if executable in {"flutter", "dart", "cargo", "go", "npm", "pnpm", "yarn", "dotnet", "mvn", "swift"}:
        return executable if rest and rest[0] == "test" else None
    if executable in {"gradle", "gradlew"} or executable.endswith("gradlew"):
        return "gradle" if any(token == "test" or token.endswith(":test") for token in rest) else None
    return None


def _test_runner(command: str) -> str | None:
    unwrapped = _unwrap_shell_command(command)
    for segment in re.split(r"\s*(?:&&|\|\||;)\s*", unwrapped):
        runner = _test_runner_for_segment(segment)
        if runner:
            return runner
    return None


def shell_call_metrics(tool_calls: list[dict[str, Any]]) -> dict[str, int]:
    """Normalize shell/test outcomes without assuming one runner event shape."""

    shell_calls = 0
    successful = 0
    failed = 0
    unknown = 0
    retries = 0
    test_runs = 0
    pytest_invocations = 0
    exec_errors = 0
    failed_fingerprints: set[str] = set()
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        command = _shell_command(call)
        if command is None:
            continue
        shell_calls += 1
        fingerprint = _command_fingerprint(command) if command else None
        if fingerprint is not None and fingerprint in failed_fingerprints:
            retries += 1
        outcome = _shell_outcome(call)
        if _shell_exec_error(call):
            exec_errors += 1
        if outcome is True:
            successful += 1
        elif outcome is False:
            failed += 1
            if fingerprint is not None:
                failed_fingerprints.add(fingerprint)
        else:
            unknown += 1
        runner = _test_runner(command)
        if runner:
            test_runs += 1
            if runner == "pytest":
                pytest_invocations += 1
    return {
        "shell_calls": shell_calls,
        "successful_shell_calls": successful,
        "failed_shell_calls": failed,
        "unknown_shell_outcomes": unknown,
        "exec_error_count": exec_errors,
        "retried_command_count": retries,
        "test_runs": test_runs,
        "pytest_invocations": pytest_invocations,
    }


def action_packet_project_doc_metrics(task: Any, packet: dict[str, Any]) -> dict[str, Any]:
    expected = {
        str(path).strip().replace("\\", "/").lower()
        for path in getattr(task, "expected_project_docs", ())
        if str(path).strip()
    }
    rows = packet.get("source_of_truth") if isinstance(packet.get("source_of_truth"), list) else []
    packet_paths = {
        str(row.get("path") or "").strip().replace("\\", "/").lower()
        for row in rows
        if isinstance(row, dict) and str(row.get("path") or "").strip()
    }
    found = expected & packet_paths
    target = packet.get("target_surface") if isinstance(packet.get("target_surface"), dict) else {}
    target_paths = {
        str(row.get("path") or "").strip().replace("\\", "/")
        for row in target.get("likely_files", [])
        if isinstance(row, dict) and str(row.get("path") or "").strip()
    }
    return {
        "action_packet_project_docs_total": len(expected),
        "action_packet_project_docs_found": len(found),
        "action_packet_project_doc_coverage": len(found) / len(expected) if expected else None,
        "action_packet_project_doc_paths": sorted(found),
        "action_packet_target_paths": sorted(target_paths),
    }


def _persist_delivery_prompt_sources(output_dir: Path, packet: dict[str, Any]) -> None:
    rows = packet.get("source_of_truth") if isinstance(packet.get("source_of_truth"), list) else []
    sources = [
        {
            "evidence_id": row.get("evidence_id"),
            "path": row.get("path"),
        }
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("path"), str) and row["path"]
    ]
    _write_json_atomic(output_dir / "delivery_prompt_sources.json", sources)


def _estimate_tokens_from_chars(chars: int) -> int:
    return max(1, (chars + 3) // 4) if chars else 0


def _load_optional_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _first_optional_int(*values: Any) -> int | None:
    for value in values:
        parsed = _optional_int(value)
        if parsed is not None:
            return parsed
    return None


def _directory_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        size = path.stat().st_size
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _trajectory_elapsed_seconds(
    trajectory_path: Path,
    started_at: str | None,
    *,
    event_kind: str,
) -> float | None:
    if not started_at or not trajectory_path.exists():
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        events = json.loads(trajectory_path.read_text(encoding="utf-8"))
    except (ValueError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(events, list):
        return None
    for event in events:
        if not isinstance(event, dict) or not _trajectory_event_matches(event, event_kind):
            continue
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, str):
            continue
        try:
            observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        return round(max(0.0, (observed - started).total_seconds()), 6)
    return None


def _trajectory_event_matches(event: dict[str, Any], event_kind: str) -> bool:
    if str(event.get("event_type") or "").lower() != "tool_call":
        return False
    tool_name = str(event.get("tool_name") or "").lower()
    arguments = json.dumps(event.get("arguments") or {}, sort_keys=True).lower()
    if event_kind == "edit":
        return any(token in tool_name for token in ("edit", "write", "apply_patch")) or '"changes"' in arguments
    if event_kind == "test":
        return '"executed": true' in arguments and any(token in arguments for token in (
            "pytest", "unittest", "npm test", "cargo test", "go test", "dart test", "flutter test",
        ))
    return False


def _task_contract_validation(
    task: TaskSpec,
    contract: Any,
    protocol_task: dict[str, Any] | None,
) -> ContractValidation:
    if task.task_id not in TASK23_PROTOCOL_TASKS and contract is None:
        return ContractValidation("valid", ())
    definition = validate_task_evaluation_contract(task, contract)
    artifacts = validate_task_evaluation_artifacts(contract, protocol_task)
    errors = tuple(dict.fromkeys((*definition.errors, *artifacts.errors)))
    return ContractValidation("invalid" if errors else "valid", errors)


def serialize_run_results_jsonl(results: list[dict[str, Any]]) -> str:
    """Serialize run results as JSONL with one physical line per record."""

    if not results:
        return ""
    return "\n".join(json.dumps(result, sort_keys=True) for result in results) + "\n"


def count_jsonl_records(path: Path) -> int:
    """Count non-empty JSONL records on disk."""

    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _write_json_atomic(path: Path, payload: Any) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_artifact_integrity(run_dir: Path, *, in_memory_results: int, total_runs: int, finished: bool) -> dict[str, Any]:
    """Return a machine-checkable consistency summary for run artifacts."""

    runs_jsonl_records = count_jsonl_records(run_dir / "runs.jsonl")
    jsonl_matches_memory = runs_jsonl_records == in_memory_results
    final_run_count_matches = (not finished) or (in_memory_results == total_runs)
    ok = jsonl_matches_memory and final_run_count_matches

    reasons: list[str] = []
    if not jsonl_matches_memory:
        reasons.append("runs_jsonl_record_count_mismatch")
    if not final_run_count_matches:
        reasons.append("finished_before_expected_run_count")

    return {
        "ok": ok,
        "finished": finished,
        "runs_jsonl_records": runs_jsonl_records,
        "in_memory_results": in_memory_results,
        "expected_total_runs": total_runs,
        "reason": reasons or None,
    }


def build_tool_policy(condition_id: str, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = CONDITIONS[condition_id].tool_policy
    policy_path = output_dir / "tool_policy.json"
    policy_path.write_text(json.dumps({
        "condition_id": condition_id,
        "allow_docatlas": policy.allow_docatlas,
        "allow_context7": policy.allow_context7,
        "allow_web": policy.allow_web,
        "docatlas_response_style": policy.docatlas_response_style,
        "inject_docatlas_context": policy.inject_docatlas_context,
        "inject_action_checklist": policy.inject_action_checklist,
        "inject_patch_constraints": policy.inject_patch_constraints,
        "inject_external_context": policy.inject_external_context,
        "max_constraint_packet_tokens": policy.max_constraint_packet_tokens,
        "max_constraints": policy.max_constraints,
        "max_sources": policy.max_sources,
        "recommend_docatlas_before_edit": policy.recommend_docatlas_before_edit,
        "require_docatlas_call_before_edit": policy.require_docatlas_call_before_edit,
        "delivery_strategy": policy.delivery_strategy,
        "isolated_worker_required": policy.isolated_worker_required,
        "network_enforcement": "policy_and_trajectory_audit",
    }, indent=2, sort_keys=True), encoding="utf-8")

    mcp_path = output_dir / "mcp_config.json"
    if condition_id in {"repo_only", "repo_only_strict_offline", "repo_only_web_audited", "repo_plus_audited_external_context"}:
        mcp_path.write_text(json.dumps({"mcpServers": {}}, indent=2), encoding="utf-8")
    elif condition_id in {"docatlas_bounded_direct", "docatlas_bounded_subagent"}:
        mcp_path.write_text(json.dumps({"mcpServers": {}}, indent=2), encoding="utf-8")
    elif condition_id in DOCATLAS_CONDITIONS:
        mcp_path.write_text(json.dumps({
            "mcpServers": {
                "docmancer-docs": {
                    "command": "uv",
                    "args": ["run", "--project", str(Path(__file__).resolve().parents[2]), "doc-atlas", "mcp", "docs-serve"],
                    "env": {"DOCMANCER_TASK_LEVEL_ALLOW_NETWORK": "false"},
                }
            }
        }, indent=2), encoding="utf-8")
    else:
        mcp_path.write_text(json.dumps({"mcpServers": {}}, indent=2), encoding="utf-8")
    return policy_path, mcp_path


def fresh_run_environment(run_output_dir: Path) -> dict[str, str]:
    env_root = (run_output_dir / "env").resolve()
    home = env_root / "home"
    xdg_config = env_root / "xdg_config"
    xdg_cache = env_root / "xdg_cache"
    docmancer_home = env_root / "docmancer_home"
    for path in (home, xdg_config, xdg_cache, docmancer_home):
        path.mkdir(parents=True, exist_ok=True)
    environment = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_CACHE_HOME": str(xdg_cache),
        "DOCMANCER_HOME": str(docmancer_home),
        "DOCMANCER_AUTO_VECTORS": "0",
        "DOCMANCER_INDEX_DB_PATH": str(docmancer_home / "docmancer.db"),
        "DOCMANCER_EMBEDDINGS_CACHE": str(docmancer_home / "embeddings-cache"),
        # Keep dependency environments outside the repository so setup output
        # cannot appear in the agent patch or repository inventory.
        "UV_PROJECT_ENVIRONMENT": str(env_root / "project_venv"),
    }
    if os.environ.get("UV_CACHE_DIR"):
        environment["UV_CACHE_DIR"] = os.environ["UV_CACHE_DIR"]
    return environment


@contextmanager
def _activated_run_environment(env: dict[str, str]):
    previous = {name: os.environ.get(name) for name in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def capture_patch(workspace: Path, output_dir: Path) -> tuple[Path, Path, Path, list[str]]:
    status = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--no-ext-diff"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    changed = subprocess.run(["git", "diff", "HEAD", "--name-only"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    patch_path = output_dir / "patch.diff"
    status_path = output_dir / "git_status.txt"
    changed_path = output_dir / "changed_files.json"
    files = [line for line in changed.stdout.splitlines() if line]
    untracked_files = [line for line in untracked.stdout.splitlines() if line and not is_runtime_artifact(line)]
    files.extend(untracked_files)
    untracked_diff = ""
    for path in untracked_files:
        completed = subprocess.run(
            ["git", "diff", "--binary", "--no-index", "--", "/dev/null", path],
            cwd=workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode not in {0, 1}:
            raise RuntimeError(f"Could not capture untracked file {path}: {completed.stderr.strip()}")
        untracked_diff += completed.stdout
    hygiene = write_patch_hygiene_artifacts(
        output_dir,
        raw_status=status.stdout,
        raw_changed_files=files,
        raw_patch_diff=diff.stdout + untracked_diff,
    )
    return patch_path, status_path, changed_path, hygiene.filtered_changed_files


def _run_evaluation_command(
    task: TaskSpec,
    command: str,
    workspace: Path,
    run_output_dir: Path,
    phase: str,
    timeout_seconds: int,
    *,
    evaluation_backend: str = "docker",
) -> CommandResult:
    if evaluation_backend == "host_exploratory":
        persist_boundary(
            run_output_dir / "evaluator_execution_boundary.json",
            {
                "schema_version": 1,
                "status": "exploratory_unisolated",
                "backend": "host",
                "causal_claim_allowed": False,
                "validator_eligible": False,
            },
        )
        return run_command(command, workspace, timeout_seconds)
    if evaluation_backend != "docker":
        raise ValueError("Unknown evaluation backend: " + evaluation_backend)
    if task.task_id not in TASK23_PROTOCOL_TASKS:
        return run_command(command, workspace, timeout_seconds)
    image = os.environ.get("TASK33C_TEST_CONTAINER_IMAGE", "")
    sandbox, boundary = verified_task33_sandbox(image)
    persist_boundary(run_output_dir / "evaluator_execution_boundary.json", boundary)
    if boundary.get("status") != "verified":
        raise RuntimeError(f"Task 33 evaluator sandbox is not verified for {phase}")
    completed = sandbox.run(command, workspace, timeout_seconds)
    return CommandResult(
        command=shlex.join(completed.command),
        returncode=completed.returncode,
        stdout=completed.stdout[-20_000:],
        stderr=completed.stderr[-20_000:],
    )


def _run_setup(task: TaskSpec, workspace: Path) -> subprocess.CompletedProcess[str]:
    command = task.setup_command
    if task.task_id not in TASK23_PROTOCOL_TASKS and command.startswith("python -m pip "):
        command = "uv pip " + command.removeprefix("python -m pip ") + f" --python {sys.executable}"
    return subprocess.run(command, cwd=workspace, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, check=False)


def _seal_condition_setup_baseline(
    workspace: Path,
    run_output_dir: Path,
    *,
    allowed_changed_files: tuple[str, ...] | None,
) -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if status.returncode != 0:
        return {"baseline_status": "failed", "baseline_error": status.stderr[-2_000:]}
    changed_files = sorted({
        line[3:].split(" -> ")[-1].strip()
        for line in status.stdout.splitlines()
        if len(line) > 3 and line[3:].strip()
    })
    if allowed_changed_files is not None:
        unexpected = sorted(set(changed_files) - set(allowed_changed_files))
        if unexpected:
            return {
                "baseline_status": "failed",
                "baseline_error": "setup changed files outside frozen allowlist: " + ", ".join(unexpected),
                "baseline_changed_files": changed_files,
                "baseline_allowed_changed_files": list(allowed_changed_files),
            }
    artifact_hashes: dict[str, str] = {}
    artifact_dir = run_output_dir / "setup_baseline_artifacts"
    for relative in changed_files if allowed_changed_files is not None else ():
        source = (workspace / relative).resolve()
        if workspace.resolve() not in source.parents or not source.is_file():
            continue
        artifact_dir.mkdir(parents=True, exist_ok=True)
        destination = artifact_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        artifact_hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    if changed_files:
        added = subprocess.run(
            ["git", "add", "-A"], cwd=workspace, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if added.returncode != 0:
            return {"baseline_status": "failed", "baseline_error": added.stderr[-2_000:]}
        commit_env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
        }
        committed = subprocess.run(
            ["git", "commit", "-m", "condition setup baseline"],
            cwd=workspace,
            env=commit_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if committed.returncode != 0:
            return {"baseline_status": "failed", "baseline_error": committed.stderr[-2_000:]}
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workspace, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if revision.returncode != 0:
        return {"baseline_status": "failed", "baseline_error": revision.stderr[-2_000:]}
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=workspace, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if tree.returncode != 0:
        return {"baseline_status": "failed", "baseline_error": tree.stderr[-2_000:]}
    return {
        "baseline_status": "sealed",
        "baseline_revision": revision.stdout.strip(),
        "baseline_tree": tree.stdout.strip(),
        "baseline_changed_files": changed_files,
        "baseline_allowed_changed_files": list(allowed_changed_files or ()),
        "baseline_artifact_sha256": artifact_hashes,
    }


def _runner_id_from_version(version: str) -> str:
    normalized = version.lower()
    for runner_id in ("github-models", "openai-api", "codex"):
        if runner_id in normalized:
            return runner_id
    return "claude"

__all__=['is_infrastructure_failure', '_semantic_check_execution_rows', '_bounded_direct_projection_errors', '_estimate_tokens', 'trajectory_evidence_metrics', 'trajectory_tool_output_metrics', '_shell_command', '_shell_outcome', '_shell_exec_error', '_unwrap_shell_command', '_command_fingerprint', '_test_runner_for_segment', '_test_runner', 'shell_call_metrics', 'action_packet_project_doc_metrics', '_persist_delivery_prompt_sources', '_estimate_tokens_from_chars', '_load_optional_json', '_optional_int', '_first_optional_int', '_directory_sha256', '_trajectory_elapsed_seconds', '_trajectory_event_matches', '_task_contract_validation', 'serialize_run_results_jsonl', 'count_jsonl_records', '_write_text_atomic', '_write_json_atomic', 'run_artifact_integrity', 'build_tool_policy', 'fresh_run_environment', '_activated_run_environment', 'capture_patch', '_run_evaluation_command', '_run_setup', '_seal_condition_setup_baseline', '_runner_id_from_version']
