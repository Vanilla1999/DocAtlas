from __future__ import annotations

import json
from pathlib import Path

import pytest

import eval.agent_developer_v1.model_benchmark as model_benchmark
import scripts.run_agent_developer_gate as agent_gate
from scripts.opencode_chat_support import OpenCodeModelOutputError
from scripts.run_agent_developer_opencode_chat import OpenCodeChatPlanner


ROOT = Path(__file__).resolve().parents[1]








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
    assert report["migration_controls_ok"] is True
    assert report["migration_control_count"] == 1
    assert [row["task_id"] for row in report["migration_controls"]] == [
        "explicit_catalog_module_supported",
    ]
    assert report["migration_controls"][0]["target_closed"] is True
    no_catalog = next(row for row in report["tasks"] if row["task_id"] == "autodiscovery_module_supported")
    assert no_catalog["calls"][0]["status"] == "failed"
    assert no_catalog["calls"][0]["sources"] == []

    ambiguity = next(
        task for task in report["tasks"]
        if task["task_id"] == "ambiguous_module_recovery_named_gap"
    )
    assert ambiguity["context_call_count"] == 2
    assert ambiguity["recovery_contract_ok"] is True
    recovery = ambiguity["calls"][0]["recovery"]
    assert recovery["errors"] == []
    # The removed module-name input is rejected at the public schema. The host
    # then explicitly inspects both exact paths and selects the authored retry.
    assert ambiguity["calls"][0]["status"] == "failed"
    assert ambiguity["calls"][0]["module_candidates"] == []
    assert ambiguity["calls"][0]["target_mismatches"] == []
    assert recovery["docs_status_modules"] == [
        "packages/auth", "services/auth",
    ]
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
    import hashlib
    fixture_name = ("ambiguous_modules_monorepo" if any("auth/" in path for path in sources)
                    else "explicit_manifest_monorepo")
    project = (ROOT / "eval/agent_developer_v1/projects" / fixture_name).resolve()
    rows = []
    for path in sources:
        original = (project / path).read_text(encoding="utf-8")
        rows.append({"path_or_url": path, "snippet": original.strip(),
                     "line_start": 1, "line_end": len(original.splitlines()),
                     "project_identity": "local:" + hashlib.sha256(str(project).encode()).hexdigest(),
                     "evidence_id": "ev-test-" + hashlib.sha256(path.encode()).hexdigest()[:16],
                     "content_sha256": hashlib.sha256(original.encode()).hexdigest(),
                     "version_binding": "unversioned"})
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
            "kind": "docs_context", "context_available": bool(rows),
            "answer_supported": False, "answer_available": False,
            "support_status": "retrieval_only", "edit_ready": False,
            "sources": rows,
        },
        "project_path": str(project),
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

