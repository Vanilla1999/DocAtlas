from __future__ import annotations

import json
from pathlib import Path

import pytest

import eval.agent_developer_v1.model_benchmark as model_benchmark
import scripts.run_agent_developer_gate as agent_gate
from scripts.opencode_chat_support import OpenCodeModelOutputError
from scripts.run_agent_developer_opencode_chat import OpenCodeChatPlanner


ROOT = Path(__file__).resolve().parents[1]


def test_readme_leads_with_one_docs_mcp_journey_before_advanced_surfaces() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    beginner = text.split("## Advanced surfaces", maxsplit=1)[0]

    assert "install → get_docs_context → follow a returned prepare_docs action when needed → answer with sources" in beginner
    assert "MCP Packs" not in beginner
    assert "get_patch_constraints" not in beginner


def test_installer_prints_the_docs_mcp_happy_path() -> None:
    text = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")

    assert "Ask it to call get_docs_context first" in text
    assert "prepare_docs next action" in text
    assert "Answer from the returned sources" in text


def test_three_real_project_task_designs_are_fairness_screened_and_distributed() -> None:
    payload = json.loads((ROOT / "eval" / "task_level" / "product_scope_proof_tasks.json").read_text(encoding="utf-8"))
    tasks = payload["tasks"]
    registered = {
        item["task_id"]: item
        for line in (ROOT / "eval" / "task_level" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
        for item in [json.loads(line)]
    }

    assert len(tasks) == 3
    for task in tasks:
        assert task["fixture_status"] == "validated"
        assert task["fairness_status"] == "passed"
        assert task["differentiation_candidate"] is True
        assert task["differentiating"] is False
        assert task["selection_status"] == "rejected_too_easy"
        assert task["benchmark_metric"] == "repeated policy-clean public_and_hidden_test_pass_rate"
        assert len(task["required_context"]) == 4
        assert any(path.endswith("pubspec.lock") for path in task["required_context"])
        assert any(path.startswith("docs/") or path.endswith("ARCHITECTURE.md") for path in task["required_context"])
        assert any("dependency_docs/permission_handler/11.4.0.json" in path for path in task["required_context"])

        spec = registered[task["task_id"]]
        assert spec["task_type"] == "real"
        assert spec["suite"] == "differentiation"
        assert spec["repo"] == f"fixture://{task['task_id']}"
        assert spec["differentiating"] is False
        assert spec["selection_status"] == "rejected_too_easy"
        assert any(dependency["name"] == "permission_handler" for dependency in spec["dependencies"])
        assert "pubspec.lock" in spec["expected_project_docs"]
        assert "pub.dev" in spec["expected_docs_domains"]

        artifacts = task["artifacts"]
        assert (ROOT / artifacts["template"]).is_dir()
        assert (ROOT / artifacts["hidden_tests"]).is_dir()
        assert (ROOT / artifacts["gold_patch"]).is_file()

        dependency_docs = json.loads((ROOT / artifacts["dependency_docs"]).read_text(encoding="utf-8"))
        assert dependency_docs["library"] == "permission_handler"
        assert dependency_docs["version"] == "11.4.0"
        assert all(url.startswith("https://pub.dev/documentation/permission_handler/11.4.0/") for url in dependency_docs["sources"])
        assert {"permanentlyDenied", "provisional"} <= set(dependency_docs["facts"]["PermissionStatus.values"])
        assert {"notification", "locationAlways"} <= set(dependency_docs["facts"]["Permission.members"])

        validation = json.loads((ROOT / artifacts["validation"]).read_text(encoding="utf-8"))
        assert validation["task_id"] == task["task_id"]
        assert validation["status"] == "validated"
        assert validation["oracle_isolated"] is True
        assert validation["gold"]["public_tests_passed"] is True
        assert validation["gold"]["hidden_tests_passed"] is True

        fairness = (ROOT / artifacts["fairness_review"]).read_text(encoding="utf-8")
        assert "hidden" in fairness.lower()
        assert "visible" in fairness.lower()
        assert "| no |" not in fairness
        assert (
            "No hidden requirement is oracle-only" in fairness
            or "Fairness clean for strict-offline screening" in fairness
        )

    _assert_agent_developer_protocol_baseline()


def _assert_agent_developer_protocol_baseline() -> None:
    public = json.loads((ROOT / "eval" / "agent_developer_v1" / "tasks.json").read_text(encoding="utf-8"))
    oracle = json.loads((ROOT / "eval" / "agent_developer_v1" / "expected_trajectories.json").read_text(encoding="utf-8"))
    tasks = public["tasks"]
    trajectories = oracle["trajectories"]

    assert public["schema_version"] == 1
    assert public["protocol"] == "agent-developer-v1"
    assert oracle["protocol"] == "agent-developer-v1-oracle"
    assert len(tasks) == 11
    assert {task["id"] for task in tasks} == {item["id"] for item in trajectories}
    assert all(not ({"calls", "required_scopes", "forbidden_sources", "known_gap"} & set(task)) for task in tasks)
    assert {
        "module_only", "project_only", "module_plus_project", "cross_module",
        "module_plus_dependency", "negative_contamination", "recovery",
    } <= {task["class"] for task in tasks}

    report = agent_gate.run_protocol()
    assert report["baseline_ok"] is True, report["errors"]
    assert report["target_ok"] is True, report["target_gaps"]
    assert report["task_count"] == 11
    assert report["executed_task_count"] == 11
    assert report["target_closed_tasks"] == 11
    assert report["false_supported"] == 0
    assert report["forbidden_source_contamination"] == 0
    assert report["errors"] == []
    assert report["target_gaps"] == []
    assert report["metrics"] == report["target_metrics"]

    ambiguity = next(
        task for task in report["tasks"]
        if task["task_id"] == "ambiguous_module_recovery_named_gap"
    )
    assert ambiguity["context_call_count"] == 2
    assert ambiguity["recovery_contract_ok"] is True
    recovery = ambiguity["calls"][0]["recovery"]
    assert recovery["errors"] == []
    assert ambiguity["calls"][0]["module_candidates"] == [
        "packages/auth", "services/auth",
    ]
    assert recovery["docs_status_modules"] == []
    assert recovery["retry"] == {
        "status": "ok",
        "sources": ["packages/auth/README.md"],
        "module_path": "packages/auth",
    }

    dependency = next(
        task for task in report["tasks"]
        if task["task_id"] == "dependency_prefetch_recovery"
    )
    assert dependency["context_call_count"] == 2
    assert [call["status"] for call in dependency["calls"]] == [
        "ok", "insufficient_evidence",
    ]


def test_agent_developer_protocol_rejects_scope_and_working_path_drift(
    monkeypatch, tmp_path,
) -> None:
    public = json.loads(agent_gate.TASKS_PATH.read_text(encoding="utf-8"))
    oracle = json.loads(agent_gate.ORACLE_PATH.read_text(encoding="utf-8"))
    public_path = tmp_path / "tasks.json"
    oracle_path = tmp_path / "oracle.json"
    public_path.write_text(json.dumps(public), encoding="utf-8")

    drifted_oracle = json.loads(json.dumps(oracle))
    drifted_oracle["trajectories"][0]["required_scopes"] = [{"scope": "project"}]
    oracle_path.write_text(json.dumps(drifted_oracle), encoding="utf-8")
    monkeypatch.setattr(agent_gate, "TASKS_PATH", public_path)
    monkeypatch.setattr(agent_gate, "ORACLE_PATH", oracle_path)
    with pytest.raises(ValueError, match="required_scopes do not match"):
        agent_gate._load_protocol()

    drifted_public = json.loads(json.dumps(public))
    drifted_public["tasks"][0]["working_path"] = "packages/payments/src/outbox.py"
    public_path.write_text(json.dumps(drifted_public), encoding="utf-8")
    oracle_path.write_text(json.dumps(oracle), encoding="utf-8")
    with pytest.raises(ValueError, match="outside every exact module scope"):
        agent_gate._load_protocol()

    drifted_public["tasks"][0]["working_path"] = "../outside.py"
    public_path.write_text(json.dumps(drifted_public), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or unsafe"):
        agent_gate._load_protocol()


def _agent_model_oracle_task(task_id: str) -> dict:
    return next(
        task for task in agent_gate._load_protocol()["tasks"]
        if task["id"] == task_id
    )


def _model_context_record(
    *,
    question: str,
    scope: str,
    mode: str,
    module: str = "",
    module_path: str = "",
    status: str,
    sources: list[str],
) -> dict:
    return {
        "tool": "get_docs_context",
        "action": {
            "action": "get_docs_context",
            "question": question,
            "scope": scope,
            "mode": mode,
            "module": module,
            "module_path": module_path,
            "reason": "test",
        },
        "payload": {
            "status": status,
            "sources": [{"path_or_url": source} for source in sources],
        },
        "project_path": "/tmp/project",
    }


def _assert_agent_developer_model_benchmark_contract() -> None:
    task = next(
        task for task in model_benchmark.load_public_tasks()
        if task["id"] == "module_plus_project_two_call_trajectory"
    )
    messages = model_benchmark.task_messages(task)
    model_view = json.loads(messages[1]["content"])
    assert set(model_view) == {
        "task_id", "developer_task", "working_path", "max_get_docs_context_calls",
    }
    assert "class" not in model_view
    assert "fixture" not in model_view
    serialized_messages = json.dumps(messages, ensure_ascii=False)
    for evaluator_term in (
        "expected_trajectories", "required_scopes", "forbidden_sources",
        "required_sources", "known_gap", "mutation_before_calls",
    ):
        assert evaluator_term not in serialized_messages

    schema = model_benchmark.action_schema()
    assert set(schema["properties"]["action"]["enum"]) == {
        "get_docs_context", "docs_status", "finish",
    }
    serialized_schema = json.dumps(schema, sort_keys=True)
    for forbidden_tool in (
        "prepare_docs", "sync_project_docs", "prefetch_project_dependency_docs",
        "replace_text", "write_file", "run_tests", "shell",
    ):
        assert forbidden_tool not in serialized_schema

    usage = {
        "request_id": "ses-format-failure",
        "request_ids": {"opencode-session-1": "ses-format-failure"},
        "model": "gpt-5.6-luna",
        "reasoning_effort": "medium",
        "input_tokens": 10,
        "output_tokens": 2,
        "reasoning_tokens": 1,
        "request_payload_sha256": "a" * 64,
        "estimated_input_tokens": 10,
    }
    planner = OpenCodeChatPlanner.__new__(OpenCodeChatPlanner)

    class _FormatFailingClient:
        def complete_json(self, **_kwargs):
            raise OpenCodeModelOutputError(
                "no schema-valid JSON",
                usage=usage,
            )

    planner.model_id = "openai/gpt-5.6-luna"
    planner._client = _FormatFailingClient()
    invalid_action, invalid_usage = planner.choose(messages)
    assert invalid_action["action"] == "invalid_model_output"
    assert invalid_usage["model_output_valid"] is False
    assert invalid_usage["model_output_error"] == "schema_invalid_after_format_repair"
    assert invalid_usage["request_id"] == "ses-format-failure"

    module_task = _agent_model_oracle_task("module_definition_supported")
    exact = _model_context_record(
        question="What is OrdersDraftStore?",
        scope="module",
        mode="project",
        module_path="packages/orders",
        status="ok",
        sources=["packages/orders/README.md"],
    )
    accepted = model_benchmark.score_task(module_task, [exact])
    assert accepted["passed"] is True, accepted["errors"]

    drift = json.loads(json.dumps(exact))
    drift["action"]["scope"] = "project"
    drift["action"]["module_path"] = ""
    rejected = model_benchmark.score_task(module_task, [drift])
    assert rejected["passed"] is False
    assert any("missing required scope" in error for error in rejected["errors"])

    contaminated = json.loads(json.dumps(exact))
    contaminated["payload"]["sources"].append(
        {"path_or_url": "packages/payments/README.md"}
    )
    rejected = model_benchmark.score_task(module_task, [contaminated])
    assert rejected["passed"] is False
    assert rejected["forbidden_source_contamination"] == 1

    ambiguity_task = _agent_model_oracle_task("ambiguous_module_recovery_named_gap")
    exact_ambiguity = _model_context_record(
        question="What is PackageAuthBoundary?",
        scope="module",
        mode="project",
        module_path="packages/auth",
        status="ok",
        sources=["packages/auth/README.md"],
    )
    accepted = model_benchmark.score_task(ambiguity_task, [exact_ambiguity])
    assert accepted["passed"] is True, accepted["errors"]
    assert accepted["direct_recovery_shortcut"] is True
    assert accepted["recovery_contract_ok"] is True

    wrong_module = json.loads(json.dumps(exact_ambiguity))
    wrong_module["action"]["module_path"] = "services/auth"
    wrong_module["payload"]["sources"] = [
        {"path_or_url": "services/auth/README.md"}
    ]
    rejected = model_benchmark.score_task(ambiguity_task, [wrong_module])
    assert rejected["passed"] is False
    assert rejected["direct_recovery_shortcut"] is False

    workflow = (
        ROOT / ".github" / "workflows" / "agent-developer-model-benchmark.yml"
    ).read_text(encoding="utf-8")
    trigger_block = workflow.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
    assert "  workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "push:" not in trigger_block
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in workflow
    assert "python scripts/run_agent_developer_openai_benchmark.py" in workflow
    assert (
        "python -m pytest tests/test_product_scope.py tests/docs/test_tool_choice_eval.py -q"
        in workflow
    )
    for line in workflow.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert len(ref) == 40
            assert all(char in "0123456789abcdef" for char in ref)


def test_agent_developer_protocol_is_a_hard_ci_gate(monkeypatch, capsys) -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python scripts/run_agent_developer_gate.py" in ci
    _assert_agent_developer_model_benchmark_contract()

    partial_report = {
        "tasks": [{
            "task_id": "ambiguous_module_recovery_named_gap",
            "target_closed": False,
            "known_gap": "bounded_module_ambiguity_projection",
        }],
        "errors": [],
        "target_ok": False,
        "target_closed_tasks": 10,
        "task_count": 11,
        "target_gap_count": 1,
        "target_gaps": [{
            "task_id": "ambiguous_module_recovery_named_gap",
            "gap": "bounded_module_ambiguity_projection",
            "actual_status": "insufficient_evidence",
            "target_status": "insufficient_evidence",
        }],
        "false_supported": 0,
        "forbidden_source_contamination": 0,
    }
    monkeypatch.setattr(agent_gate, "run_protocol", lambda: partial_report)

    assert agent_gate.main() == 1
    assert "Agent Developer Protocol v1: TARGET FAIL" in capsys.readouterr().out
