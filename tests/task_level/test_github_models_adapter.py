from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path
from typing import cast

import pytest

from docmancer.docs.application.action_packet import (
    build_action_packet,
    estimate_action_packet_tokens,
    validate_action_packet,
)
from eval.task_level.github_models import (
    OPENAI_API_PROVIDER,
    GitHubModelsClient,
    GitHubModelsCompletion,
    GitHubModelsIsolatedWorker,
    GitHubModelsRunner,
    _bounded_runner_messages,
    _estimate_message_tokens,
    _required_once_retrieval_metadata,
)
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    TASK33_QUERY_DERIVATION,
)
from eval.task_level.runners.base import AgentRunRequest
from eval.task_level.sandbox_execution import DockerCommandSandbox, SandboxCommandResult


class _TestSandbox:
    def verify(self) -> dict[str, object]:
        return {"schema_version": 1, "status": "verified", "image_id_sha256": "test-boundary"}

    def run(self, command, workspace: Path, timeout_seconds: float) -> SandboxCommandResult:
        argv = tuple(shlex.split(command) if isinstance(command, str) else command)
        started = time.monotonic()
        completed = subprocess.run(
            argv, cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout_seconds, check=False,
        )
        return SandboxCommandResult(
            command=argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            wall_time_seconds=time.monotonic() - started,
            boundary=self.verify(),
        )


def _completion(content: dict, *, turn: int = 1) -> GitHubModelsCompletion:
    return GitHubModelsCompletion(
        content=json.dumps(content),
        model="openai/gpt-4.1-mini",
        request_id=f"request-{turn}",
        request_ids={"x-github-request-id": f"request-{turn}"},
        input_tokens=100,
        output_tokens=20,
        reasoning_tokens=0,
        raw_usage={
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
        request_payload_sha256=hashlib.sha256(f"request-{turn}".encode()).hexdigest(),
        estimated_input_tokens=100,
    )


def _action(tool: str, **values) -> dict:
    return {
        "tool": tool,
        "path": None,
        "query": None,
        "old": None,
        "new": None,
        "start_line": None,
        "end_line": None,
        "summary": None,
        **values,
    }


def test_github_models_runner_enforces_turns_and_edits_with_closed_tool_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (workspace / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    actions = iter([
        _action("read_file", path="calc.py", start_line=1, end_line=20),
        _action("replace_text", path="calc.py", old="return a - b", new="return a + b"),
        _action("run_tests"),
        _action("finish", summary="fixed and tested"),
    ])
    calls = 0

    def fake_complete(self, **kwargs):
        nonlocal calls
        calls += 1
        if calls >= 3:
            assert any(
                "Latest exact test output" in message.get("content", "")
                for message in kwargs["messages"]
            )
        value = next(actions)
        return value, _completion(value, turn=calls)

    monkeypatch.setattr(
        "eval.task_level.github_models.GitHubModelsClient.complete_json",
        fake_complete,
    )
    output_dir = tmp_path / "output"
    request = AgentRunRequest(
        task_id="runner_canary",
        condition_id="repo_only",
        workspace=workspace,
        prompt="Fix add and run tests.",
        model="openai/gpt-4.1-mini",
        timeout_seconds=30,
        max_turns=8,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=output_dir,
        allowed_write_paths=("calc.py",),
    )

    output = GitHubModelsRunner("token", sandbox=_TestSandbox()).run(request)

    assert output.status == "completed"
    assert output.exit_code == 0
    assert output.max_turns_enforced is True
    assert output.input_tokens == 400
    assert output.output_tokens == 80
    assert calls == 4
    assert "return a + b" in (workspace / "calc.py").read_text(encoding="utf-8")
    trajectory = json.loads((output_dir / "trajectory.normalized.json").read_text(encoding="utf-8"))
    assert any(event["tool_name"] == "Edit.replace_text" for event in trajectory)
    assert any("pytest" in event["tool_name"].lower() for event in trajectory)
    assert "Bearer token" not in (output_dir / "github_models_usage.json").read_text(encoding="utf-8")


def test_github_models_runner_stops_at_host_owned_turn_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    calls = 0

    def fake_complete(self, **kwargs):
        nonlocal calls
        calls += 1
        action = _action("read_file", path="module.py")
        return action, _completion(action, turn=calls)

    monkeypatch.setattr(
        "eval.task_level.github_models.GitHubModelsClient.complete_json",
        fake_complete,
    )
    output_dir = tmp_path / "output"
    request = AgentRunRequest(
        task_id="runner_canary",
        condition_id="repo_only",
        workspace=workspace,
        prompt="Keep reading forever.",
        model="openai/gpt-4.1-mini",
        timeout_seconds=30,
        max_turns=2,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=output_dir,
        allowed_write_paths=("module.py",),
    )

    output = GitHubModelsRunner(
        "token", sandbox=cast(DockerCommandSandbox, _TestSandbox())
    ).run(request)
    usage = json.loads((output_dir / "github_models_usage.json").read_text(encoding="utf-8"))

    assert calls == 2
    assert output.status == "max_turns_exhausted"
    assert output.exit_code == 2
    assert output.max_turns_enforced is True
    assert [turn["turn"] for turn in usage["turns"]] == [1, 2]
    assert output.token_usage["completed_turn_events"] == 2
    assert output.token_usage["effective_max_turns"] == 2


def test_required_once_runner_uses_bounded_direct_docs_delivery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    module = workspace / "module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    actions = iter([
        _action("get_docs_context", query="Fix the permission gate."),
        _action("replace_text", path="module.py", old="VALUE = 1", new="VALUE = 2"),
        _action("finish", summary="used documentation"),
    ])
    captured: dict[str, object] = {}

    def fake_complete(self, **kwargs):
        value = next(actions)
        return value, _completion(value)

    def fake_handle(name, args, service):
        packet = build_action_packet(
            question="Fix the permission gate.",
            context_pack=[{
                "doc_scope": "project",
                "path": "AGENTS.md",
                "heading_path": "Architecture",
                "authority": "canonical",
                "source_class": "project_doc",
                "content": (
                    "The permission gate must preserve whole facts. "
                    "Do not bypass the gate."
                ),
            }],
            max_tokens=2_000,
        )
        evidence_id = packet["source_of_truth"][0]["evidence_id"]
        packet["task_interpretation"]["acceptance_conditions"] = [{
            "text": "Preserve the documented permission semantics. " + "x" * 5_200,
            "evidence_ids": [evidence_id],
        }]
        for _ in range(3):
            packet["estimated_tokens"] = estimate_action_packet_tokens(packet)
        assert not validate_action_packet(packet, max_tokens=2_000)
        payload = {
            "delivery_strategy": "bounded_direct",
            "action_packet": packet,
        }
        captured.update({
            "name": name,
            "args": args,
            "service": service,
            "payload_chars": len(json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        })
        return payload

    sentinel_service = object()
    monkeypatch.setattr(
        "eval.task_level.github_models.GitHubModelsClient.complete_json",
        fake_complete,
    )
    monkeypatch.setattr(
        "docmancer.docs.interfaces.mcp.context_tools.handle_context_tool",
        fake_handle,
    )
    monkeypatch.setattr(
        "docmancer.docs.service.LibraryDocsService",
        lambda: sentinel_service,
    )
    output_dir = tmp_path / "output"
    request = AgentRunRequest(
        task_id="task",
        condition_id="docatlas_tool_required_once",
        workspace=workspace,
        prompt="Fix the permission gate.",
        model="openai/gpt-4.1-mini",
        timeout_seconds=30,
        max_turns=3,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=output_dir,
        allowed_write_paths=("module.py",),
        task_objective="Fix the permission gate.",
    )

    sandbox = cast(DockerCommandSandbox, _TestSandbox())
    output = GitHubModelsRunner("token", sandbox=sandbox).run(request)

    assert output.status == "completed"
    assert module.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert isinstance(captured["payload_chars"], int)
    assert captured["payload_chars"] > 6_000
    assert captured["name"] == "get_docs_context"
    assert captured["service"] is sentinel_service
    args = captured["args"]
    assert isinstance(args, dict)
    assert args["question"] == "Fix the permission gate."
    assert args["project_path"] == str(workspace)
    assert args["delivery_strategy"] == "bounded_direct"
    assert args["prepare_project_docs"] is False
    trajectory = json.loads((output_dir / "trajectory.normalized.json").read_text())
    assert trajectory[0]["arguments"]["project_path"] == "."
    assert trajectory[0]["arguments"]["delivery_strategy"] == "bounded_direct"
    assert trajectory[0]["arguments"]["question_matches_task_objective"] is True
    assert trajectory[0]["arguments"]["retrieval_succeeded"] is True
    assert trajectory[0]["arguments"]["action_packet_status"] == "ok"


def test_required_once_runner_blocks_edit_after_insufficient_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    module = workspace / "module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    actions = iter([
        _action("get_docs_context", query="Fix the permission gate."),
        _action("replace_text", path="module.py", old="VALUE = 1", new="VALUE = 2"),
        _action("finish", summary="retrieval failed"),
    ])

    def fake_complete(self, **kwargs):
        value = next(actions)
        return value, _completion(value)

    monkeypatch.setattr(
        "eval.task_level.github_models.GitHubModelsClient.complete_json",
        fake_complete,
    )
    monkeypatch.setattr(
        "docmancer.docs.interfaces.mcp.context_tools.handle_context_tool",
        lambda *args, **kwargs: {
            "delivery_strategy": "bounded_direct",
            "action_packet": {
                "status": "insufficient_evidence",
                "missing_evidence": ["permission architecture"],
            },
        },
    )
    monkeypatch.setattr(
        "docmancer.docs.service.LibraryDocsService",
        lambda: object(),
    )
    output_dir = tmp_path / "output"
    request = AgentRunRequest(
        task_id="task",
        condition_id="docatlas_tool_required_once",
        workspace=workspace,
        prompt="Fix the permission gate.",
        model="openai/gpt-4.1-mini",
        timeout_seconds=30,
        max_turns=3,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=output_dir,
        allowed_write_paths=("module.py",),
    )

    output = GitHubModelsRunner(
        "token", sandbox=cast(DockerCommandSandbox, _TestSandbox())
    ).run(request)

    assert output.status == "completed"
    assert module.read_text(encoding="utf-8") == "VALUE = 1\n"
    trajectory_path = output_dir / "trajectory.normalized.json"
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    assert trajectory[0]["arguments"]["retrieval_succeeded"] is False
    assert trajectory[0]["arguments"]["action_packet_status"] == "insufficient_evidence"
    assert trajectory[1]["tool_name"] == "Repo.replace_text_rejected"
    audit = audit_trajectory("docatlas_tool_required_once", trajectory_path)
    assert not audit.clean
    assert "required_docatlas_retrieval_unsuccessful" in audit.violations


def test_required_once_retrieval_rejects_wrong_objective_error_and_malformed_packet(
    tmp_path: Path,
):
    request = AgentRunRequest(
        task_id="task",
        condition_id="docatlas_tool_required_once",
        workspace=tmp_path,
        prompt="wrapped prompt with runner guidance",
        model="model",
        timeout_seconds=30,
        max_turns=1,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=tmp_path / "output",
        task_objective="Fix the permission gate.",
    )
    valid_packet = build_action_packet(
        question="Fix the permission gate.",
        context_pack=[{
            "doc_scope": "project",
            "source_class": "project_doc",
            "path": "AGENTS.md",
            "heading_path": "Architecture",
            "authority": "canonical",
            "content": "The permission gate must preserve whole facts.",
        }],
        max_tokens=2_000,
    )
    valid_result = json.dumps({
        "delivery_strategy": "bounded_direct",
        "action_packet": valid_packet,
    })

    assert _required_once_retrieval_metadata(
        request,
        {"tool": "get_docs_context", "query": "Different objective"},
        valid_result,
    )["retrieval_succeeded"] is False
    assert _required_once_retrieval_metadata(
        request,
        {"tool": "get_docs_context", "query": "Fix the permission gate."},
        "ERROR: retrieval failed",
    )["retrieval_succeeded"] is False
    assert _required_once_retrieval_metadata(
        request,
        {"tool": "get_docs_context", "query": "Fix the permission gate."},
        json.dumps({
            "delivery_strategy": "bounded_direct",
            "action_packet": {"status": "ok"},
        }),
    )["retrieval_succeeded"] is False


def test_github_models_client_streams_structured_output_and_usage(
    monkeypatch: pytest.MonkeyPatch,
):
    class Response:
        headers = {"x-github-request-id": "request-stream-1"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def __iter__(self):
            events = [
                {
                    "model": "gpt-4.1-mini-2025-04-14",
                    "choices": [{"delta": {"content": '{"selected_'}, "finish_reason": None}],
                },
                {"choices": [{"delta": {"content": 'indices":[0,1,2]}'}, "finish_reason": "stop"}]},
                {"choices": [], "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 18,
                    "prompt_tokens_details": {"cached_tokens": 0},
                    "completion_tokens_details": {"reasoning_tokens": 0},
                }},
            ]
            return iter([*(f"data: {json.dumps(event)}\n\n".encode() for event in events), b"data: [DONE]\n\n"])

    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("eval.task_level.github_models.urllib.request.urlopen", fake_urlopen)

    value, completion = GitHubModelsClient("token").complete_json(
        model="openai/gpt-4.1-mini",
        messages=[{"role": "user", "content": "select"}],
        schema_name="selection",
        schema={"type": "object"},
        timeout_seconds=10,
        max_tokens=64,
    )

    assert value == {"selected_indices": [0, 1, 2]}
    assert completion.request_id == "request-stream-1"
    assert completion.input_tokens == 10
    assert completion.output_tokens == 8
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["stream_options"] == {"include_usage": True}


def test_openai_api_profile_uses_server_request_id_and_separate_usage_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    class Response:
        headers = {"x-request-id": "openai-request-1"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def __iter__(self):
            action = _action("finish", summary="done")
            events = [
                {"model": "gpt-4o-mini-2024-07-18", "choices": [{
                    "delta": {"content": json.dumps(action)}, "finish_reason": "stop",
                }]},
                {"choices": [], "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 18,
                    "prompt_tokens_details": {"cached_tokens": 0},
                    "completion_tokens_details": {"reasoning_tokens": 0},
                }},
            ]
            return iter([*(f"data: {json.dumps(event)}\n\n".encode() for event in events), b"data: [DONE]\n\n"])

    captured = {}

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        return Response()

    monkeypatch.setattr("eval.task_level.github_models.urllib.request.urlopen", fake_urlopen)
    value, completion = GitHubModelsClient(
        "openai-key",
        provider=OPENAI_API_PROVIDER,
    ).complete_json(
        model=OPENAI_API_PROVIDER.default_model,
        messages=[{"role": "user", "content": "finish"}],
        schema_name="controlled_agent_action",
        schema={"type": "object"},
        timeout_seconds=10,
        max_tokens=64,
    )

    assert value["tool"] == "finish"
    assert completion.request_id == "openai-request-1"
    assert completion.request_ids["x-client-request-id"]
    assert "X-github-api-version" not in captured["headers"]
    assert captured["headers"]["Authorization"] == "Bearer openai-key"

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

    def fake_complete(self, **kwargs):
        action = _action("finish", summary="done")
        completion = _completion(action)
        return action, GitHubModelsCompletion(
            **{**completion.__dict__, "model": OPENAI_API_PROVIDER.default_model}
        )

    monkeypatch.setattr(
        "eval.task_level.github_models.GitHubModelsClient.complete_json",
        fake_complete,
    )
    request = AgentRunRequest(
        task_id="task",
        condition_id="repo_only_strict_offline",
        workspace=workspace,
        prompt="inspect",
        model=OPENAI_API_PROVIDER.default_model,
        timeout_seconds=30,
        max_turns=2,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=tmp_path / "output",
        allowed_write_paths=("module.py",),
    )
    output = GitHubModelsRunner(
        "openai-key",
        provider=OPENAI_API_PROVIDER,
        sandbox=_TestSandbox(),
    ).run(request)

    assert output.status == "completed"
    usage = json.loads((tmp_path / "output" / "openai_api_usage.json").read_text())
    assert usage["provider"] == "openai-api"
    assert usage["endpoint"] == OPENAI_API_PROVIDER.endpoint


def test_github_models_runner_forbids_root_conftest_edits_outside_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    test_path = workspace / "conftest.py"
    test_path.write_text("assert False\n", encoding="utf-8")
    actions = iter([
        _action("replace_text", path="conftest.py", old="False", new="True"),
        _action("finish", summary="done"),
    ])

    def fake_complete(self, **kwargs):
        value = next(actions)
        return value, _completion(value)

    monkeypatch.setattr(
        "eval.task_level.github_models.GitHubModelsClient.complete_json",
        fake_complete,
    )
    request = AgentRunRequest(
        task_id="task",
        condition_id="repo_only_strict_offline",
        workspace=workspace,
        prompt="fix",
        model="model",
        timeout_seconds=30,
        max_turns=2,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=tmp_path / "output",
        allowed_write_paths=("module.py",),
    )

    GitHubModelsRunner("token", sandbox=_TestSandbox()).run(request)

    assert test_path.read_text(encoding="utf-8") == "assert False\n"


def test_github_models_runner_does_not_claim_rejected_test_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    actions = iter([
        _action("run_tests"),
        _action("finish", summary="test command unavailable"),
    ])

    def fake_complete(self, **kwargs):
        value = next(actions)
        return value, _completion(value)

    monkeypatch.setattr(
        "eval.task_level.github_models.GitHubModelsClient.complete_json",
        fake_complete,
    )
    output_dir = tmp_path / "output"
    request = AgentRunRequest(
        task_id="task",
        condition_id="repo_only_strict_offline",
        workspace=workspace,
        prompt="test",
        model="model",
        timeout_seconds=30,
        max_turns=2,
        environment={},
        mcp_config_path=None,
        tool_policy_path=tmp_path / "policy.json",
        output_dir=output_dir,
        test_command="definitely-missing-test-command",
        allowed_write_paths=("module.py",),
    )

    GitHubModelsRunner("token", sandbox=_TestSandbox()).run(request)

    trajectory = json.loads((output_dir / "trajectory.normalized.json").read_text(encoding="utf-8"))
    rejected = [event for event in trajectory if event["tool_name"] == "Repo.run_tests_rejected"]
    assert len(rejected) == 1
    assert rejected[0]["arguments"]["executed"] is False
    assert not any(event["tool_name"].startswith("Bash.") for event in trajectory)


def test_github_models_worker_selects_host_evidence_and_binds_usage(
    monkeypatch: pytest.MonkeyPatch,
):
    objective = "Keep all permission gates consistent."
    envelope = DelegationEnvelope(
        task_objective=objective,
        suspected_modules=(),
        changed_files=(),
        required_evidence_categories=("project_docs",),
        project_revision="project-revision",
        index_revision="index-revision",
    )
    items = tuple({
        "path": f"docs/permission-{index}.md",
        "heading_path": "Permission gate",
        "authority": "canonical",
        "source_class": "project_doc",
        "instruction_trust": "scoped_agent_policy",
        "content": "The shared permission gate must block missing immediate permissions.",
    } for index in range(4))
    snapshot = HostEvidenceSnapshot(
        query="permission gates consistent",
        objective_sha256=hashlib.sha256(objective.encode("utf-8")).hexdigest(),
        query_derivation=TASK33_QUERY_DERIVATION,
        evidence_items=items,
        trust_contract={"selected": [], "rejected": [], "risky": []},
        retrieval_issues=(),
        evidence_categories=("project_docs",),
        project_revision=envelope.project_revision,
        index_revision=envelope.index_revision,
        response_status="success",
        raw_retrieval_tokens=500,
        retrieval_wall_time_seconds=0.1,
    )
    # Use the exact frozen derivation expected by HostEvidenceSnapshot.
    from eval.task_level.isolated_delivery import derive_task33_retrieval_query
    snapshot = HostEvidenceSnapshot(
        **{**snapshot.__dict__, "query": derive_task33_retrieval_query(objective)}
    )

    def fake_complete(self, **kwargs):
        selected = kwargs["schema"]["properties"]["selected_indices"]
        assert selected == {"type": "array", "items": {"type": "integer"}}
        value = {"selected_indices": [0, 1, 2]}
        return value, _completion(value)

    monkeypatch.setattr(
        "eval.task_level.github_models.GitHubModelsClient.complete_json",
        fake_complete,
    )

    output = GitHubModelsIsolatedWorker("token").run(envelope, snapshot, timeout_seconds=10)

    assert output.packet["task_interpretation"]["objective"] == objective
    assert output.packet["source_of_truth"]
    assert output.usage.provider == "github-models"
    assert output.usage.proof["selected_indices"] == [0, 1, 2]
    output.usage.validate()


def test_runner_context_compaction_is_deterministic_and_hard_bounded():
    base = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "objective\n" + ("source line\n" * 4_000)},
    ]
    recent = [
        {"role": "assistant" if index % 2 == 0 else "user", "content": str(index) * 8_000}
        for index in range(8)
    ]
    pinned = [{"role": "user", "content": "latest test\n" + ("failure\n" * 2_000)}]

    first, first_proof = _bounded_runner_messages(base, recent, pinned, token_limit=7_000)
    second, second_proof = _bounded_runner_messages(base, recent, pinned, token_limit=7_000)

    assert first == second
    assert first_proof == second_proof
    assert _estimate_message_tokens(first) <= 7_000
    assert first_proof["dropped_message_sha256"] or first_proof["clipped_messages"]
