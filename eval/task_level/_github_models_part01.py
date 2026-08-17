"""Implementation shard 1 for github_models."""
from __future__ import annotations

from ._github_models_shared import *  # noqa: F401,F403


@dataclass(frozen=True)
class GitHubModelsCompletion:
    content: str
    model: str
    request_id: str
    request_ids: dict[str, str]
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None
    raw_usage: dict[str, Any]
    request_payload_sha256: str = ""
    estimated_input_tokens: int = 0


class GitHubModelsClient:
    """Small, auditable client for hosted OpenAI-compatible structured completions."""

    def __init__(
        self,
        token: str,
        *,
        endpoint: str | None = None,
        provider: HostedProviderConfig = GITHUB_MODELS_PROVIDER,
    ) -> None:
        if not token.strip():
            raise ValueError(f"credential is required for {provider.provider_id}")
        self._token = token
        self.provider = provider
        self.endpoint = endpoint or provider.endpoint

    def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        timeout_seconds: float,
        max_tokens: int,
    ) -> tuple[dict[str, Any], GitHubModelsCompletion]:
        if timeout_seconds <= 0:
            raise TimeoutError(f"{self.provider.provider_id} request deadline expired")
        deadline = time.monotonic() + timeout_seconds
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        serialized_payload = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        estimated_input_tokens = _estimate_message_tokens(messages)
        if estimated_input_tokens > _PROVIDER_INPUT_TOKEN_LIMIT:
            raise RuntimeError(
                f"{self.provider.provider_id} input budget exceeded: "
                f"{estimated_input_tokens}>{_PROVIDER_INPUT_TOKEN_LIMIT}"
            )
        _pace_provider_request(self.provider.minimum_request_interval_seconds)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"{self.provider.provider_id} request deadline expired during rate pacing")
        client_request_id = str(uuid.uuid4())
        headers = {
            "Accept": "text/event-stream",
            "Authorization": "Bearer " + self._token,
            "Content-Type": "application/json",
            "X-Client-Request-Id": client_request_id,
            **dict(self.provider.extra_headers),
        }
        request = urllib.request.Request(
            self.endpoint,
            data=serialized_payload,
            headers=headers,
            method="POST",
        )
        try:
            with _absolute_deadline(remaining), urllib.request.urlopen(request, timeout=remaining) as response:
                provider_request_ids = {
                    name: value
                    for name in self.provider.request_id_headers
                    if (value := response.headers.get(name))
                }
                if not provider_request_ids:
                    raise RuntimeError(
                        f"{self.provider.provider_id} response omitted provider request identity"
                    )
                request_ids = dict(provider_request_ids)
                request_ids["x-client-request-id"] = client_request_id
                chunks: list[str] = []
                usage: dict[str, Any] | None = None
                response_model = model
                finish_reasons: list[str] = []
                received_bytes = 0
                for raw_line in response:
                    received_bytes += len(raw_line)
                    if received_bytes > 4_000_000:
                        raise RuntimeError(f"{self.provider.provider_id} response exceeded 4 MB")
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if not data or data == "[DONE]":
                        continue
                    event = json.loads(data)
                    if isinstance(event.get("error"), dict):
                        raise RuntimeError(f"{self.provider.provider_id} stream returned an error event")
                    if isinstance(event.get("model"), str):
                        response_model = event["model"]
                    if isinstance(event.get("usage"), dict):
                        usage = event["usage"]
                    for choice in event.get("choices", []):
                        if not isinstance(choice, dict):
                            continue
                        delta = choice.get("delta")
                        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                            chunks.append(delta["content"])
                        if isinstance(choice.get("finish_reason"), str):
                            finish_reasons.append(choice["finish_reason"])
        except urllib.error.HTTPError as exc:
            # HTTPError is file-like; reading its body here would happen after
            # the transport deadline context has unwound and could block.
            detail = str(exc.reason or "provider error")[:1_000]
            raise RuntimeError(f"{self.provider.provider_id} HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self.provider.provider_id} transport failure: {exc.reason}") from exc

        content = "".join(chunks)
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            finish = ",".join(finish_reasons) or "missing"
            raise RuntimeError(
                f"{self.provider.provider_id} returned an invalid structured completion "
                f"(finish={finish}, chars={len(content)})"
            ) from exc
        if not isinstance(value, dict) or not isinstance(usage, dict):
            raise RuntimeError(f"{self.provider.provider_id} structured completion contract failed")
        input_tokens = _strict_nonnegative_int(usage.get("prompt_tokens"), "prompt_tokens")
        output_tokens = _strict_nonnegative_int(usage.get("completion_tokens"), "completion_tokens")
        total_tokens = _strict_nonnegative_int(usage.get("total_tokens"), "total_tokens")
        if total_tokens != input_tokens + output_tokens:
            raise RuntimeError(f"{self.provider.provider_id} usage totals are inconsistent")
        details = usage.get("completion_tokens_details")
        reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
        reasoning = _strict_nonnegative_int(reasoning, "reasoning_tokens")
        prompt_details = usage.get("prompt_tokens_details")
        cached = prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else None
        _strict_nonnegative_int(cached, "cached_tokens")
        request_id = next(
            request_ids[name]
            for name in self.provider.request_id_headers
            if name in request_ids
        )
        completion = GitHubModelsCompletion(
            content=content,
            model=response_model,
            request_id=request_id,
            request_ids=request_ids,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning,
            raw_usage=dict(usage),
            request_payload_sha256=hashlib.sha256(serialized_payload).hexdigest(),
            estimated_input_tokens=estimated_input_tokens,
        )
        return value, completion


@dataclass(frozen=True)
class GitHubModelsIsolatedWorker:
    """Tool-less hosted compressor over one immutable host evidence snapshot."""

    token: str
    model: str = DEFAULT_GITHUB_MODEL
    endpoint: str = GITHUB_MODELS_ENDPOINT
    compressor_identity: str = "github-models-task33c-selector-v2"
    usage_verifier_identity: str = "github-models-response-headers-and-usage-v2"
    provider: HostedProviderConfig = GITHUB_MODELS_PROVIDER

    @property
    def capability_evidence(self) -> dict[str, Any]:
        deadline_supported = _absolute_deadline_supported()
        return {
            "schema_version": 1,
            "status": "verified" if bool(self.token.strip()) and deadline_supported else "unavailable",
            "boundary_type": "remote_toolless_inference",
            "boundary": "tool-less hosted inference request",
            "provider": self.provider.provider_id,
            "provider_endpoint": self.endpoint,
            "model": self.model,
            "fresh_context": "one stateless request with no conversation reuse",
            "documentation_access": "only the serialized host-owned evidence snapshot",
            "tools": [],
            "network_tools": [],
            "host_filesystem_access": "not mounted or serialized",
            "host_process_access": "not exposed by the provider API",
            "provider_transport": "host-owned HTTPS request only",
            "local_process_execution": False,
            "recursive_delegation": False,
            "hard_timeout": "POSIX signal-interruptible absolute transport deadline plus broker wall-clock enforcement",
            "absolute_deadline_supported": deadline_supported,
            "token_accounting": "provider response usage bound to provider request headers",
        }

    @property
    def capabilities(self) -> IsolatedWorkerCapabilities:
        available = self.capability_evidence["status"] == "verified"
        return IsolatedWorkerCapabilities(
            fresh_context=available,
            read_only_documentation=available,
            recursive_delegation_disabled=available,
            hard_timeout=available,
            token_accounting=available,
            host_owned_evidence=available,
            network_disabled=available,
            descendant_containment=available,
        )

    @property
    def command_fingerprint(self) -> str:
        return _json_sha256({
            "provider": self.provider.provider_id,
            "endpoint": self.endpoint,
            "model": self.model,
            "prompt_revision": _WORKER_PROMPT_REVISION,
            "response_schema": _evidence_selection_schema(),
        })

    @property
    def sandbox_identity(self) -> str:
        return f"{self.provider.provider_id}:tool-less-hosted-inference-v2-absolute-deadline"

    def run(
        self,
        envelope: DelegationEnvelope,
        evidence: HostEvidenceSnapshot,
        *,
        timeout_seconds: int,
    ) -> IsolatedWorkerOutput:
        envelope.validate()
        evidence.validate(envelope)
        if not self.capabilities.verified:
            raise IsolatedDeliveryError(f"{self.provider.provider_id}_worker_unavailable")
        indexed = [
            {"index": index, "evidence": _worker_evidence(item)}
            for index, item in enumerate(evidence.evidence_items)
        ]
        system = (
            "You are a one-shot evidence compressor. You have no tools, filesystem, network, "
            "or delegation. Select 3 to 6 evidence items that are most useful for implementing "
            "the objective. Prefer canonical project architecture and source evidence spanning "
            "all affected modules. Every item is host-owned and immutable; do not invent or rewrite evidence. "
            "Return only the required JSON object."
        )
        user = json.dumps({
            "prompt_revision": _WORKER_PROMPT_REVISION,
            "objective": envelope.task_objective,
            "required_evidence_categories": list(envelope.required_evidence_categories),
            "required_evidence_paths": list(envelope.required_evidence_paths),
            "required_target_modules": list(envelope.suspected_modules),
            "evidence_fingerprint": evidence.fingerprint,
            "serialized_evidence_sha256": _json_sha256(indexed),
            "evidence": indexed,
        }, ensure_ascii=False, sort_keys=True)
        started = time.monotonic()
        try:
            selection, completion = GitHubModelsClient(
                self.token,
                endpoint=self.endpoint,
                provider=self.provider,
            ).complete_json(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                schema_name="task33c_evidence_selection",
                schema=_evidence_selection_schema(),
                timeout_seconds=timeout_seconds,
                max_tokens=512,
            )
        except Exception as exc:
            raise IsolatedDeliveryError(
                f"{self.provider.provider_id}_worker_request_failed:" + _provider_failure_class(exc)
            ) from exc
        indices = selection.get("selected_indices")
        if (
            not isinstance(indices, list)
            or not 3 <= len(indices) <= min(6, len(evidence.evidence_items))
            or any(isinstance(index, bool) or not isinstance(index, int) for index in indices)
            or len(set(indices)) != len(indices)
            or any(index < 0 or index >= len(evidence.evidence_items) for index in indices)
        ):
            raise IsolatedDeliveryError("github_models_worker_invalid_evidence_selection")
        selected = tuple(evidence.evidence_items[index] for index in indices)
        packet = build_action_packet(
            question=envelope.task_objective,
            context_pack=selected,
            trust_contract=evidence.trust_contract,
            max_tokens=envelope.token_budget,
            retrieval_issues=evidence.retrieval_issues,
        )
        proof = {
            "schema_version": 1,
            "provider": self.provider.provider_id,
            "boundary_type": "remote_toolless_inference",
            "endpoint": self.endpoint,
            "requested_model": self.model,
            "model": completion.model,
            "prompt_revision": _WORKER_PROMPT_REVISION,
            "response_schema_sha256": _json_sha256(_evidence_selection_schema()),
            "message_count": 2,
            "tools": [],
            "request_id": completion.request_id,
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "reasoning_tokens": completion.reasoning_tokens,
            "request_ids": completion.request_ids,
            "usage": completion.raw_usage,
            "request_payload_sha256": completion.request_payload_sha256,
            "estimated_input_tokens": completion.estimated_input_tokens,
            "message_sha256": _json_sha256([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]),
            "evidence_fingerprint": evidence.fingerprint,
            "selected_indices": indices,
        }
        usage = WorkerUsage(
            provider=self.provider.provider_id,
            model=completion.model,
            request_id=completion.request_id,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            reasoning_tokens=completion.reasoning_tokens,
            proof=proof,
        )
        return IsolatedWorkerOutput(
            packet=packet,
            usage=usage,
            wall_time_seconds=round(time.monotonic() - started, 6),
        )


def _evidence_selection_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["selected_indices"],
        "properties": {
            "selected_indices": {
                "type": "array",
                "items": {"type": "integer"},
            },
        },
    }


def _agent_action_schema(docatlas_allowed: bool) -> dict[str, Any]:
    tools = ["list_files", "read_file", "search", "replace_text", "run_tests", "finish"]
    if docatlas_allowed:
        tools.insert(-1, "get_docs_context")
    nullable_string = {"type": ["string", "null"]}
    nullable_int = {"type": ["integer", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["tool", "path", "query", "old", "new", "start_line", "end_line", "summary"],
        "properties": {
            "tool": {"type": "string", "enum": tools},
            "path": nullable_string,
            "query": nullable_string,
            "old": nullable_string,
            "new": nullable_string,
            "start_line": nullable_int,
            "end_line": nullable_int,
            "summary": nullable_string,
        },
    }


def _runner_system_prompt(request: AgentRunRequest) -> str:
    tools = (
        "list_files; read_file(path,start_line,end_line); search(query,path); "
        "replace_text(path,old,new); run_tests; finish(summary)"
    )
    if _docatlas_allowed(request.condition_id):
        tools += "; get_docs_context(query)"
    return (
        "You are a controlled coding agent. Take exactly one action per turn using the JSON schema. "
        f"Available actions: {tools}. Inspect before editing, make the smallest source-code fix, run tests, "
        "then finish. Never edit tests, documentation, lockfiles, generated files, or files outside the repository. "
        f"The only writable paths are: {', '.join(request.allowed_write_paths) or '(none)'}. "
        "You have no internet or arbitrary shell. "
        "The user message contains the exact repository inventory; never invent a path outside it. "
        "Files present in the initial source snapshot count as read; otherwise you must read a source file before "
        "editing it. For exact replacement, old must match the current file "
        "byte-for-byte. If replacement fails, read the file again and do not repeat the same failed action. "
        f"The hard turn limit is {request.max_turns}."
    )


def _event(sequence: int, event_type: str, tool_name: str, arguments: dict[str, Any], result: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "tool_name": tool_name,
        "arguments": arguments,
        "result_summary": result[:4_000],
    }


def _trajectory_tool_name(tool: str, result: str) -> str:
    if tool == "replace_text" and not result.startswith("UPDATED "):
        return "Repo.replace_text_rejected"
    if tool == "run_tests" and not result.startswith("exit_code="):
        return "Repo.run_tests_rejected"
    return {
        "replace_text": "Edit.replace_text",
        "run_tests": "Bash.pytest",
        "get_docs_context": "get_docs_context",
    }.get(tool, f"Repo.{tool}")


def _trajectory_arguments(
    action: dict[str, Any],
    *,
    result: str | None = None,
    request: AgentRunRequest | None = None,
) -> dict[str, Any]:
    arguments = {key: value for key, value in action.items() if key != "summary" and value is not None}
    if action.get("tool") == "get_docs_context":
        arguments["question"] = arguments.pop("query", None)
        arguments.update({
            "server": "docmancer-docs",
            "tool": "get_docs_context",
            "project_path": ".",
            "delivery_strategy": "bounded_direct",
        })
        if request is not None and result is not None:
            arguments.update(
                _required_once_retrieval_metadata(request, action, result)
            )
    if action.get("tool") == "run_tests":
        command = _test_command(request) if request is not None else []
        arguments["command"] = shlex.join(command) if command else None
        arguments["executed"] = bool(result and result.startswith("exit_code="))
    return arguments


def _test_command(request: AgentRunRequest) -> list[str]:
    if request.test_command:
        return shlex.split(request.test_command)
    if (request.workspace / "test_calc.py").is_file():
        return [sys.executable, "-m", "pytest", "test_calc.py", "-q"]
    if (request.workspace / "tests/test_browser_permission_gate.py").is_file():
        return ["uv", "run", "--offline", "pytest", "tests/test_browser_permission_gate.py", "-q"]
    return [sys.executable, "-m", "pytest", "-q"]


def _docatlas_allowed(condition_id: str) -> bool:
    return condition_id in {
        "docatlas_tool_optional",
        "docatlas_tool_recommended",
        "docatlas_tool_required_once",
        "docatlas_tool_visibility_canary",
    }


def _required_once_objective(request: AgentRunRequest) -> str:
    if request.task_objective is not None:
        return request.task_objective.strip()
    return request.prompt.split(TOOL_REQUIRED_ONCE_INSTRUCTION, 1)[0].strip()


def _required_once_retrieval_metadata(
    request: AgentRunRequest,
    action: dict[str, Any],
    result: str,
) -> dict[str, Any]:
    query = action.get("query")
    question_matches = (
        isinstance(query, str)
        and query.strip() == _required_once_objective(request)
    )
    payload: dict[str, Any] = {}
    if not result.startswith("ERROR:"):
        try:
            loaded = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            loaded = {}
        if isinstance(loaded, dict):
            payload = loaded
    delivery_strategy = payload.get("delivery_strategy")
    packet = payload.get("action_packet")
    packet_status = packet.get("status") if isinstance(packet, dict) else None
    packet_errors = (
        validate_action_packet(packet, max_tokens=2_000)
        if isinstance(packet, dict)
        else ["ActionPacket missing"]
    )
    succeeded = (
        question_matches
        and delivery_strategy == "bounded_direct"
        and packet_status in {"ok", "truncated"}
        and not packet_errors
    )
    return {
        "question_matches_task_objective": question_matches,
        "retrieval_succeeded": succeeded,
        "action_packet_status": packet_status,
    }


def _normalize_model(model: str, provider: HostedProviderConfig = GITHUB_MODELS_PROVIDER) -> str:
    value = model.strip()
    if provider.provider_id == "github-models":
        return value if "/" in value else provider.default_model
    return value or provider.default_model


def _list_repository_files(workspace: Path) -> str:
    files = [
        path.relative_to(workspace).as_posix()
        for path in workspace.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and ".venv" not in path.parts
    ]
    return "\n".join(sorted(files)[:500])[:12_000]


def _repository_source_snapshot(workspace: Path) -> tuple[str, tuple[str, ...]]:
    allowed_suffixes = {".dart", ".py", ".js", ".jsx", ".ts", ".tsx"}
    rows: list[str] = []
    paths: list[str] = []
    used = 0
    for path in sorted(item for item in workspace.rglob("*") if item.is_file()):
        relative = path.relative_to(workspace)
        if (
            path.suffix not in allowed_suffixes
            or ".git" in relative.parts
            or "tests" in relative.parts
            or "__pycache__" in relative.parts
            or ".venv" in relative.parts
            or path.name.startswith("test_")
            or path.name.endswith(("_test.py", ".freezed.dart", ".g.dart"))
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        block = f"\n--- {relative.as_posix()} ---\n{text[:4_000]}"
        if used + len(block) > 16_000:
            continue
        rows.append(block)
        paths.append(relative.as_posix())
        used += len(block)
    return ("".join(rows) or "(no eligible source files)", tuple(paths))


def _compact_action_history(action: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: value
        for key, value in action.items()
        if value is not None and key not in {"old", "new"}
    }
    for key in ("old", "new"):
        value = action.get(key)
        if isinstance(value, str):
            compact[f"{key}_sha256"] = hashlib.sha256(value.encode("utf-8")).hexdigest()
            compact[f"{key}_chars"] = len(value)
    compact["action_fingerprint"] = _action_fingerprint(action)
    return compact


def _action_fingerprint(action: dict[str, Any]) -> str:
    normalized = {key: value for key, value in action.items() if key != "summary"}
    return hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _worker_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return dict(item)


def _estimate_message_tokens(messages: list[dict[str, str]]) -> int:
    serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return max(1, (len(serialized) + 3) // 4)


def _bounded_runner_messages(
    base_messages: list[dict[str, str]],
    recent_messages: list[dict[str, str]],
    pinned_messages: list[dict[str, str]],
    *,
    token_limit: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    recent = [dict(message) for message in recent_messages[-6:]]
    dropped: list[str] = []
    while recent and _estimate_message_tokens([*base_messages, *recent, *pinned_messages]) > token_limit:
        removed = recent.pop(0)
        dropped.append(_json_sha256(removed))
    messages = [dict(message) for message in [*base_messages, *recent, *pinned_messages]]
    clipped: list[dict[str, Any]] = []
    while _estimate_message_tokens(messages) > token_limit:
        candidates = [
            (len(message.get("content", "")), index)
            for index, message in enumerate(messages)
            if message.get("role") != "system" and len(message.get("content", "")) > 800
        ]
        if not candidates:
            raise RuntimeError("hosted model base prompt cannot fit the frozen input budget")
        _length, index = max(candidates)
        content = messages[index]["content"]
        target = max(800, int(len(content) * 0.75))
        head = int(target * 0.6)
        tail = target - head
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        marker = f"\n[deterministically compacted sha256={digest} original_chars={len(content)}]\n"
        messages[index]["content"] = content[:head] + marker + content[-tail:]
        clipped.append({
            "message_index": index,
            "original_sha256": digest,
            "original_chars": len(content),
            "retained_chars": len(messages[index]["content"]),
        })
    estimate = _estimate_message_tokens(messages)
    return messages, {
        "schema_version": 1,
        "input_token_limit": token_limit,
        "estimated_input_tokens": estimate,
        "dropped_message_sha256": dropped,
        "clipped_messages": clipped,
        "messages_sha256": _json_sha256(messages),
    }


def _pace_provider_request(minimum_interval_seconds: float) -> None:
    global _LAST_REQUEST_AT, _PROCESS_REQUEST_COUNT
    with _REQUEST_RATE_LOCK:
        if _PROCESS_REQUEST_COUNT >= _PROCESS_REQUEST_BUDGET:
            raise RuntimeError(
                f"hosted provider frozen process request budget exceeded: {_PROCESS_REQUEST_BUDGET}"
            )
        _PROCESS_REQUEST_COUNT += 1
        delay = minimum_interval_seconds - (time.monotonic() - _LAST_REQUEST_AT)
        if delay > 0:
            time.sleep(delay)
        _LAST_REQUEST_AT = time.monotonic()


def _provider_failure_class(exc: Exception) -> str:
    text = str(exc).lower()
    if "http 429" in text:
        return "rate_limited"
    if "http 413" in text or "tokens_limit_reached" in text:
        return "context_too_large"
    if "http 400" in text:
        return "invalid_request_contract"
    if "content_filter" in text or "responsibleaipolicyviolation" in text:
        return "content_filtered"
    if "invalid structured completion" in text:
        return "invalid_structured_completion"
    if "structured completion contract failed" in text:
        return "missing_stream_usage_or_contract"
    if "omitted valid" in text or "usage totals are inconsistent" in text:
        return "invalid_provider_usage"
    return exc.__class__.__name__.lower()


def _strict_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"GitHub Models omitted valid {name}")
    return value


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _absolute_deadline_supported() -> bool:
    return (
        os.name == "posix"
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    )


@contextmanager
def _absolute_deadline(seconds: float) -> Iterator[None]:
    """Interrupt DNS, connect, and streaming reads at one monotonic deadline."""

    if seconds <= 0:
        raise TimeoutError("absolute deadline expired")
    if not _absolute_deadline_supported():
        raise RuntimeError("interruptible absolute deadlines require the POSIX main thread")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()

    def _raise_timeout(_signum: int, _frame: Any) -> None:
        raise TimeoutError("absolute provider deadline expired")

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            remaining = max(0.000_001, previous_timer[0] - (time.monotonic() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_timer[1])

__all__=['GitHubModelsCompletion', 'GitHubModelsClient', 'GitHubModelsIsolatedWorker', '_evidence_selection_schema', '_agent_action_schema', '_runner_system_prompt', '_event', '_trajectory_tool_name', '_trajectory_arguments', '_test_command', '_docatlas_allowed', '_required_once_objective', '_required_once_retrieval_metadata', '_normalize_model', '_list_repository_files', '_repository_source_snapshot', '_compact_action_history', '_action_fingerprint', '_worker_evidence', '_estimate_message_tokens', '_bounded_runner_messages', '_pace_provider_request', '_provider_failure_class', '_strict_nonnegative_int', '_json_sha256', '_absolute_deadline_supported', '_absolute_deadline']
