from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from eval.task_level.github_models import (
    GitHubModelsClient,
    GitHubModelsCompletion,
    GitHubModelsIsolatedWorker,
    GitHubModelsRunner,
)
from eval.task_level.isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    TASK33_QUERY_DERIVATION,
)
from eval.task_level.runners.base import AgentRunRequest


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
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
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
    )

    output = GitHubModelsRunner("token").run(request)

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
                {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}},
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


def test_github_models_runner_forbids_test_edits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = tmp_path / "workspace"
    (workspace / "tests").mkdir(parents=True)
    test_path = workspace / "tests/test_example.py"
    test_path.write_text("assert False\n", encoding="utf-8")
    actions = iter([
        _action("replace_text", path="tests/test_example.py", old="False", new="True"),
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
    )

    GitHubModelsRunner("token").run(request)

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
    )

    GitHubModelsRunner("token").run(request)

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
