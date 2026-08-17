"""Implementation shard 2 for github_models."""
from __future__ import annotations

from ._github_models_shared import *  # noqa: F401,F403

from ._github_models_part01 import GitHubModelsClient, GitHubModelsIsolatedWorker, _absolute_deadline_supported, _action_fingerprint, _agent_action_schema, _bounded_runner_messages, _compact_action_history, _docatlas_allowed, _event, _json_sha256, _list_repository_files, _normalize_model, _repository_source_snapshot, _required_once_retrieval_metadata, _runner_system_prompt, _test_command, _trajectory_arguments, _trajectory_tool_name

class GitHubModelsRunner:
    """Hard-turn controlled coding loop with a closed, host-owned tool surface."""

    runner_id = "github-models"
    hard_turn_limit_enforced = True
    hard_input_budget_enforced = False

    def __init__(
        self,
        token: str,
        *,
        endpoint: str | None = None,
        sandbox: DockerCommandSandbox | None = None,
        provider: HostedProviderConfig = GITHUB_MODELS_PROVIDER,
    ) -> None:
        self._token = token
        self._provider = provider
        self._endpoint = endpoint or provider.endpoint
        self.runner_id = provider.runner_id
        self._sandbox = sandbox or DockerCommandSandbox.from_environment()

    def verify(self) -> RunnerCapabilities:
        boundary = self._sandbox.verify()
        deadline_supported = _absolute_deadline_supported()
        available = bool(self._token.strip()) and boundary.get("status") == "verified" and deadline_supported
        return RunnerCapabilities(
            runner_id=self.runner_id,
            version=self._provider.runner_version,
            structured_trajectory=available,
            patch_capture=available,
            tool_isolation=available,
            mcp_isolation=available,
            shell_network_isolation=available,
            token_usage=available,
            independent_process=available,
            verified=available,
            hard_turn_limit=True,
            hard_input_budget=False,
            verification_notes=[
                f"Each model turn is a stateless {self._provider.provider_id} request in a host-controlled loop.",
                "The runner exposes only bounded repository reads, contract-allowlisted exact text replacement, sandboxed local tests, and condition-scoped DocAtlas retrieval.",
                "No arbitrary shell, network, MCP, recursive-agent, or generated-file editing tool is exposed.",
                "The Python loop enforces the requested maximum number of model turns and a monotonic wall-clock deadline.",
                "Cumulative provider-reported input usage is recorded after requests, not hard-stopped before budget exceedance.",
                "Provider token usage and request IDs are persisted per turn without persisting the bearer token.",
                f"Docker command boundary: {boundary.get('status')}; image identity: {boundary.get('image_id_sha256') or 'missing'}.",
                f"Interruptible absolute provider deadline: {deadline_supported}.",
            ],
        )

    @property
    def boundary_evidence(self) -> dict[str, object]:
        return self._sandbox.verify()

    @property
    def provider_identity(self) -> dict[str, str]:
        return {
            "provider_id": self._provider.provider_id,
            "runner_id": self._provider.runner_id,
            "endpoint": self._endpoint,
        }

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        if request.max_turns > _TASK33C_MAX_RUNNER_REQUESTS:
            raise RuntimeError(
                f"{self._provider.provider_id} runner request budget exceeds "
                f"{_TASK33C_MAX_RUNNER_REQUESTS} turns"
            )
        request.output_dir.mkdir(parents=True, exist_ok=True)
        boundary = self._sandbox.verify()
        persist_boundary(request.output_dir / "runner_execution_boundary.json", boundary)
        if boundary.get("status") != "verified" or not _absolute_deadline_supported():
            raise RuntimeError(
                f"{self._provider.provider_id} runner requires a verified Docker boundary "
                "and interruptible absolute deadlines"
            )
        if not request.allowed_write_paths and request.task_id != "docatlas_tool_visibility_canary":
            raise RuntimeError("controlled runner requires an explicit write-path allowlist")
        stdout_path = request.output_dir / "stdout.log"
        stderr_path = request.output_dir / "stderr.log"
        trajectory_path = request.output_dir / "trajectory.normalized.json"
        usage_path = request.output_dir / self._provider.usage_filename
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        deadline = started + request.timeout_seconds
        model = _normalize_model(request.model, self._provider)
        inventory = _list_repository_files(request.workspace)
        source_snapshot, bootstrap_read_paths = _repository_source_snapshot(request.workspace)
        base_messages: list[dict[str, str]] = [
            {"role": "system", "content": _runner_system_prompt(request)},
            {
                "role": "user",
                "content": (
                    request.prompt
                    + "\n\nExact repository file inventory:\n" + inventory
                    + "\n\nInitial source snapshot (these paths count as already inspected):\n"
                    + source_snapshot
                ),
            },
        ]
        recent_messages: list[dict[str, str]] = []
        events: list[dict[str, Any]] = []
        usage_rows: list[dict[str, Any]] = []
        stdout_rows: list[str] = []
        stderr_rows: list[str] = []
        status = "max_turns_exhausted"
        exit_code = 2
        client = GitHubModelsClient(
            self._token,
            endpoint=self._endpoint,
            provider=self._provider,
        )
        read_paths: set[str] = set(bootstrap_read_paths)
        last_test_result: str | None = None
        rejected_actions: dict[str, int] = {}
        compaction_rows: list[dict[str, Any]] = []
        required_once_retrieval_succeeded = False

        for turn in range(1, request.max_turns + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                status, exit_code = "timeout", 124
                break
            try:
                pinned_test_feedback = (
                    [{
                        "role": "user",
                        "content": (
                            "Latest exact test output (do not lose this while repairing):\n"
                            + last_test_result[:8_000]
                        ),
                    }]
                    if last_test_result is not None else []
                )
                messages, compaction = _bounded_runner_messages(
                    base_messages,
                    recent_messages,
                    pinned_test_feedback,
                    token_limit=_PROVIDER_INPUT_TOKEN_LIMIT,
                )
                action, completion = client.complete_json(
                    model=model,
                    messages=messages,
                    schema_name="controlled_agent_action",
                    schema=_agent_action_schema(_docatlas_allowed(request.condition_id)),
                    timeout_seconds=min(remaining, 90),
                    max_tokens=2_048,
                )
                compaction_rows.append({"turn": turn, **compaction})
            except TimeoutError as exc:
                stderr_rows.append(f"turn {turn}: TimeoutError: {exc}")
                status, exit_code = "timeout", 124
                break
            except Exception as exc:
                stderr_rows.append(f"turn {turn}: {exc.__class__.__name__}: {exc}")
                status, exit_code = "runner_failed", 1
                break
            usage_rows.append({
                "turn": turn,
                "provider": self._provider.provider_id,
                "model": completion.model,
                "request_id": completion.request_id,
                "request_ids": completion.request_ids,
                "usage": completion.raw_usage,
                "request_payload_sha256": completion.request_payload_sha256,
                "estimated_input_tokens": completion.estimated_input_tokens,
                "prompt_revision": _RUNNER_PROMPT_REVISION,
            })
            stdout_rows.append(json.dumps({"turn": turn, "action": action}, ensure_ascii=False, sort_keys=True))
            tool = action.get("tool")
            if tool == "finish":
                summary = str(action.get("summary") or "")[:4_000]
                events.append(_event(len(events) + 1, "assistant", "", {}, summary))
                status, exit_code = "completed", 0
                break
            action_fingerprint = _action_fingerprint(action)
            terminate_repetition = False
            if action_fingerprint in rejected_actions:
                rejected_actions[action_fingerprint] += 1
                result = (
                    "ERROR: exact rejected action repeated; inspect current state and choose a different action. "
                    f"fingerprint={action_fingerprint}"
                )
                terminate_repetition = rejected_actions[action_fingerprint] >= 3
            elif (
                tool == "replace_text"
                and request.condition_id == "docatlas_tool_required_once"
                and not required_once_retrieval_succeeded
            ):
                result = (
                    "ERROR: successful bounded_direct get_docs_context retrieval with the "
                    "original task objective is required before replace_text"
                )
                rejected_actions[action_fingerprint] = 1
            else:
                result = _execute_agent_tool(
                    request, action, read_paths=read_paths,
                    sandbox=self._sandbox, deadline=deadline,
                )
                if result.startswith(("ERROR:", "NO_CHANGE_ALREADY_APPLIED")):
                    rejected_actions[action_fingerprint] = 1
            if tool == "get_docs_context" and request.condition_id == "docatlas_tool_required_once":
                required_once_retrieval_succeeded = bool(
                    _required_once_retrieval_metadata(request, action, result)[
                        "retrieval_succeeded"
                    ]
                )
            event = _event(
                len(events) + 1,
                "tool_call",
                _trajectory_tool_name(str(tool), result),
                _trajectory_arguments(action, result=result, request=request),
                result,
            )
            events.append(event)
            observed_result = result
            if tool == "run_tests" and result.startswith("exit_code="):
                last_test_result = result
            if tool == "replace_text" and result.startswith("UPDATED "):
                test_result = _execute_agent_tool(
                    request, {"tool": "run_tests"}, read_paths=read_paths,
                    sandbox=self._sandbox, deadline=deadline,
                )
                if test_result.startswith("exit_code="):
                    last_test_result = test_result
                events.append(_event(
                    len(events) + 1,
                    "tool_call",
                    _trajectory_tool_name("run_tests", test_result),
                    {
                        **_trajectory_arguments(
                            {"tool": "run_tests"}, result=test_result, request=request
                        ),
                        "trigger": "post_edit_verification",
                    },
                    test_result,
                ))
                stdout_rows.append(json.dumps({
                    "turn": turn,
                    "post_edit_verification": test_result[:4_000],
                }, ensure_ascii=False, sort_keys=True))
                observed_result += "\n\nPost-edit verification:\n" + test_result
            recent_messages.append({
                "role": "assistant",
                "content": json.dumps(_compact_action_history(action), ensure_ascii=False, sort_keys=True),
            })
            recent_messages.append({
                "role": "user",
                "content": "Observed tool output:\n" + observed_result[:8_000],
            })
            if terminate_repetition:
                status, exit_code = "stalled_action_loop", 2
                break

        finished_at = datetime.now(timezone.utc).isoformat()
        stdout_path.write_text("\n".join(stdout_rows) + ("\n" if stdout_rows else ""), encoding="utf-8")
        stderr_path.write_text("\n".join(stderr_rows) + ("\n" if stderr_rows else ""), encoding="utf-8")
        trajectory_path.write_text(json.dumps(events, indent=2, sort_keys=True), encoding="utf-8")
        usage_path.write_text(json.dumps({
            "schema_version": 1,
            "provider": self._provider.provider_id,
            "endpoint": self._endpoint,
            "model": model,
            "prompt_revision": _RUNNER_PROMPT_REVISION,
            "provider_input_token_limit": _PROVIDER_INPUT_TOKEN_LIMIT,
            "request_budget": min(request.max_turns, _TASK33C_MAX_RUNNER_REQUESTS),
            "compaction": compaction_rows,
            "turns": usage_rows,
        }, indent=2, sort_keys=True), encoding="utf-8")
        input_tokens = sum(row["usage"]["prompt_tokens"] for row in usage_rows)
        output_tokens = sum(row["usage"]["completion_tokens"] for row in usage_rows)
        cached_values = [
            details.get("cached_tokens") if isinstance(details, dict) else None
            for row in usage_rows
            for details in [row["usage"].get("prompt_tokens_details")]
        ]
        cached_input_tokens = (
            sum(cached_values)
            if all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in cached_values)
            else None
        )
        reasoning_values = [
            details.get("reasoning_tokens") if isinstance(details, dict) else None
            for row in usage_rows
            for details in [row["usage"].get("completion_tokens_details")]
        ]
        reasoning_tokens = (
            sum(reasoning_values)
            if all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in reasoning_values)
            else None
        )
        return AgentRunOutput(
            status=status,
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            wall_time_seconds=round(time.monotonic() - started, 6),
            raw_stdout_path=str(stdout_path),
            raw_stderr_path=str(stderr_path),
            trajectory_path=str(trajectory_path),
            patch_path=None,
            tool_calls=[event for event in events if event["event_type"] == "tool_call"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            runner_version=self._provider.runner_version,
            max_turns_enforced=True,
            token_usage={
                "cached_input_tokens": cached_input_tokens,
                "reasoning_tokens": reasoning_tokens,
                "completed_turn_events": len(usage_rows),
                "effective_max_turns": request.max_turns,
            },
            notes=[
                f"{self._provider.provider_id} controlled tool loop; tests execute inside the "
                "verified Docker boundary."
            ],
        )


def create_github_models_runner() -> GitHubModelsRunner:
    return GitHubModelsRunner(os.environ.get("GITHUB_TOKEN", ""))


def create_github_models_worker() -> GitHubModelsIsolatedWorker:
    return GitHubModelsIsolatedWorker(
        os.environ.get("GITHUB_TOKEN", ""),
        model=os.environ.get("TASK33C_GITHUB_MODEL", DEFAULT_GITHUB_MODEL),
    )


def create_openai_api_runner() -> GitHubModelsRunner:
    return GitHubModelsRunner(
        os.environ.get("OPENAI_API_KEY", ""),
        endpoint=OPENAI_API_ENDPOINT,
        provider=OPENAI_API_PROVIDER,
    )


def create_openai_api_worker() -> GitHubModelsIsolatedWorker:
    return GitHubModelsIsolatedWorker(
        os.environ.get("OPENAI_API_KEY", ""),
        model=os.environ.get("TASK33C_OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        endpoint=OPENAI_API_ENDPOINT,
        compressor_identity="openai-api-task33c-selector-v2",
        usage_verifier_identity="openai-api-response-headers-and-usage-v1",
        provider=OPENAI_API_PROVIDER,
    )


def _execute_agent_tool(
    request: AgentRunRequest,
    action: dict[str, Any],
    *,
    read_paths: set[str] | None = None,
    sandbox: DockerCommandSandbox,
    deadline: float,
) -> str:
    read_paths = read_paths if read_paths is not None else set()
    tool = action.get("tool")
    try:
        if tool == "list_files":
            return _list_repository_files(request.workspace)
        if tool == "read_file":
            path = _safe_path(request.workspace, action.get("path"), write=False)
            relative = path.relative_to(request.workspace.resolve()).as_posix()
            read_paths.add(relative)
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            start = max(1, action.get("start_line") if isinstance(action.get("start_line"), int) else 1)
            end = min(len(lines), action.get("end_line") if isinstance(action.get("end_line"), int) else start + 300)
            return "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))[:6_000]
        if tool == "search":
            query = action.get("query")
            if not isinstance(query, str) or not query or len(query) > 300:
                return "ERROR: invalid search query"
            base = _safe_path(request.workspace, action.get("path") or ".", write=False)
            paths = [base] if base.is_file() else sorted(path for path in base.rglob("*") if path.is_file())
            terms = [term.lower() for term in query.split() if len(term) >= 3]
            rows: list[tuple[int, str]] = []
            for path in paths:
                if ".git" in path.parts or "__pycache__" in path.parts or ".venv" in path.parts:
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    lowered = line.lower()
                    score = sum(term in lowered for term in terms) if terms else int(query.lower() in lowered)
                    if score:
                        rows.append((score, f"{path.relative_to(request.workspace).as_posix()}:{number}:{line}"))
            ranked = [row for _score, row in sorted(rows, key=lambda item: (-item[0], item[1]))[:80]]
            return "\n".join(ranked)[:6_000] or "NO MATCHES"
        if tool == "replace_text":
            path = _safe_path(
                request.workspace, action.get("path"), write=True,
                allowed_write_paths=request.allowed_write_paths,
            )
            relative = path.relative_to(request.workspace.resolve()).as_posix()
            if relative not in read_paths:
                return "ERROR: read_file must successfully inspect this exact path before replace_text"
            old, new = action.get("old"), action.get("new")
            if not isinstance(old, str) or not old or not isinstance(new, str):
                return "ERROR: old and new must be strings and old must be non-empty"
            if len(old) > 50_000 or len(new) > 50_000:
                return "ERROR: replacement exceeds 50 KB"
            text = path.read_text(encoding="utf-8")
            count = text.count(old)
            if count != 1:
                if text == new:
                    return (
                        f"NO_CHANGE_ALREADY_APPLIED {relative}. Do not submit this replacement again; "
                        "use the latest test output to choose a different action."
                    )
                lines = text.splitlines()
                start = max(1, action.get("start_line") if isinstance(action.get("start_line"), int) else 1)
                end = min(len(lines), action.get("end_line") if isinstance(action.get("end_line"), int) else start + 80)
                excerpt = "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))
                return (
                    f"ERROR: old text matched {count} times; expected exactly once. "
                    "Do not repeat this action. Current numbered excerpt:\n" + excerpt[:5_000]
                )
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            return f"UPDATED {path.relative_to(request.workspace).as_posix()}"
        if tool == "run_tests":
            command = _test_command(request)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("runner deadline expired before test execution")
            completed = sandbox.run(command, request.workspace, min(180, remaining))
            output = (completed.stdout + ("\n" + completed.stderr if completed.stderr else ""))[-18_000:]
            return f"exit_code={completed.returncode}\n{output}"
        if tool == "get_docs_context" and _docatlas_allowed(request.condition_id):
            query = action.get("query")
            if not isinstance(query, str) or not query.strip() or len(query) > 1_000:
                return "ERROR: invalid documentation query"
            from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
            from docmancer.docs.service import LibraryDocsService

            with _activated_environment(request.environment):
                result = handle_context_tool(
                    "get_docs_context",
                    {
                        "question": query,
                        "project_path": str(request.workspace),
                        "delivery_strategy": "bounded_direct",
                        "packet_tokens": 2_000,
                        "mode": "project",
                        "response_style": "snippet-first",
                        "prepare_project_docs": False,
                        "allow_network": False,
                        "allow_latest_fallback": False,
                        "tokens": 2_500,
                        "limit": 6,
                    },
                    LibraryDocsService(),
                )
            if result is None:
                return "ERROR: bounded documentation retrieval was not handled"
            return json.dumps(_jsonable(result), ensure_ascii=False, sort_keys=True)
        return "ERROR: unavailable action"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return f"ERROR: {exc.__class__.__name__}: {str(exc)[:1_000]}"
    except Exception as exc:
        return f"ERROR: tool failed closed: {exc.__class__.__name__}: {str(exc)[:1_000]}"


def _safe_path(
    root: Path,
    value: Any,
    *,
    write: bool,
    allowed_write_paths: tuple[str, ...] = (),
) -> Path:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("invalid repository path")
    candidate = (root / value).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("path escapes repository")
    relative = candidate.relative_to(resolved_root)
    if ".git" in relative.parts:
        raise ValueError("git metadata is not exposed")
    if write and relative.as_posix() not in allowed_write_paths:
        raise ValueError("path is outside the frozen task write allowlist")
    if write and (
        relative.parts[:1] in (("tests",), ("docs",))
        or candidate.name in {"README.md", "pubspec.lock", "pyproject.toml"}
        or candidate.name.startswith("test_")
        or candidate.name.endswith("_test.py")
        or candidate.name.endswith((".freezed.dart", ".g.dart"))
    ):
        raise ValueError("editing this path is forbidden by runner policy")
    if not candidate.exists() or not candidate.is_file() and value != ".":
        raise ValueError("path does not exist")
    return candidate


def run_github_models_capability_probe(
    token: str,
    *,
    model: str = DEFAULT_GITHUB_MODEL,
    endpoint: str = GITHUB_MODELS_ENDPOINT,
) -> dict[str, Any]:
    """Exercise the production structured adapter and every required usage field."""

    return _run_hosted_models_capability_probe(
        token,
        model=model,
        endpoint=endpoint,
        provider=GITHUB_MODELS_PROVIDER,
    )


def run_openai_api_capability_probe(
    token: str,
    *,
    model: str = DEFAULT_OPENAI_MODEL,
    endpoint: str = OPENAI_API_ENDPOINT,
) -> dict[str, Any]:
    """Exercise the direct OpenAI API contract used by the local Task 33C profile."""

    return _run_hosted_models_capability_probe(
        token,
        model=model,
        endpoint=endpoint,
        provider=OPENAI_API_PROVIDER,
    )


def _run_hosted_models_capability_probe(
    token: str,
    *,
    model: str,
    endpoint: str,
    provider: HostedProviderConfig,
) -> dict[str, Any]:

    schema = _agent_action_schema(False)
    messages = [
        {
            "role": "system",
            "content": "Return one schema-valid finish action. Use null for every field except summary.",
        },
        {"role": "user", "content": "Finish now with summary set to capability probe."},
    ]
    action, completion = GitHubModelsClient(
        token,
        endpoint=endpoint,
        provider=provider,
    ).complete_json(
        model=model,
        messages=messages,
        schema_name="controlled_agent_action",
        schema=schema,
        timeout_seconds=60,
        max_tokens=256,
    )
    expected_keys = set(schema["required"])
    valid_action = set(action) == expected_keys and action.get("tool") == "finish"
    prompt_details = completion.raw_usage.get("prompt_tokens_details") or {}
    completion_details = completion.raw_usage.get("completion_tokens_details") or {}
    verified = (
        valid_action
        and bool(completion.request_ids)
        and _strict_probe_int(prompt_details.get("cached_tokens"))
        and _strict_probe_int(completion_details.get("reasoning_tokens"))
        and bool(completion.request_payload_sha256)
        and 0 < completion.estimated_input_tokens <= _PROVIDER_INPUT_TOKEN_LIMIT
    )
    return {
        "schema_version": 1,
        "status": "verified" if verified else "failed",
        "provider": provider.provider_id,
        "model": completion.model,
        "prompt_revision": _RUNNER_PROMPT_REVISION,
        "response_schema_sha256": _json_sha256(schema),
        "request_id": completion.request_id,
        "request_ids": completion.request_ids,
        "request_payload_sha256": completion.request_payload_sha256,
        "estimated_input_tokens": completion.estimated_input_tokens,
        "usage": completion.raw_usage,
        "action": action,
    }


def _strict_probe_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dict__"):
        return {key: _jsonable(item) for key, item in vars(value).items() if not key.startswith("_")}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@contextmanager
def _activated_environment(environment: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

__all__=['GitHubModelsRunner', 'create_github_models_runner', 'create_github_models_worker', 'create_openai_api_runner', 'create_openai_api_worker', '_execute_agent_tool', '_safe_path', 'run_github_models_capability_probe', 'run_openai_api_capability_probe', '_run_hosted_models_capability_probe', '_strict_probe_int', '_jsonable', '_activated_environment']
