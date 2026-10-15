"""New offline evaluator smoke cases; not historical quality acceptance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_action_packet_v4_public import necessary_evidence, OfflineRetrieval
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool


@pytest.fixture
def case(necessary_evidence):
    return {
        "case_id": "offline-v4-protocols", "result_kind": "patch_context",
        "question": "Inspect protocol implementations", "maximum_visible_tokens": 128,
        "expected_status": "data", "candidates": necessary_evidence["context_pack"],
        "required_facts": necessary_evidence["public_requirements"],
        "required_evidence_paths": necessary_evidence["required_evidence_paths"],
        "project_identity": necessary_evidence["project_identity"],
    }
























def test_real_provider_tool_dispatch_uses_explicit_read_only_format(necessary_evidence, tmp_path, monkeypatch):
    import time
    import docmancer.docs.service as service_module
    from eval.task_level._github_models_part02 import _execute_agent_tool

    service = OfflineRetrieval(necessary_evidence)
    monkeypatch.setattr(service_module, "LibraryDocsService", lambda: service)
    request = SimpleNamespace(workspace=tmp_path, environment={}, condition_id="docatlas_tool_required_once")
    result = _execute_agent_tool(request, {"tool": "get_docs_context", "query": "Inspect protocol implementations"},
                                 sandbox=None, deadline=time.monotonic() + 30)
    packet = json.loads(result)
    assert packet["kind"] == "patch_context" and packet["result"] == "data"
    assert packet["edit_ready"] is False and len(packet["sources"]) == 12
    assert result == json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert "context_format" not in service.calls[0][1]








def test_mocked_provider_request_keeps_full_v4_after_history_selection(necessary_evidence, tmp_path, monkeypatch):
    import docmancer.docs.service as service_module
    import eval.task_level._github_models_part02 as runner_module
    from eval.task_level.runners.base import AgentRunRequest

    service = OfflineRetrieval(necessary_evidence)
    monkeypatch.setattr(service_module, "LibraryDocsService", lambda: service)
    monkeypatch.setattr(runner_module, "_absolute_deadline_supported", lambda: True)
    calls = []
    expected = []

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def complete_json(self, **kwargs):
            messages = deepcopy(kwargs["messages"])
            calls.append(messages)
            if len(calls) > 1:
                packet_message = next(row for row in messages if row["content"].startswith("Observed tool output:\n{"))
                if not expected:
                    expected.append(packet_message)
                assert packet_message == expected[0]
                packet = json.loads(packet_message["content"].split("\n", 1)[1])
                assert packet["result"] == "data" and len(packet["sources"]) == 12
                assert len(packet_message["content"]) > 32000
                assert packet["edit_ready"] is False
            action = ({"tool": "get_docs_context", "query": "Inspect protocol implementations"} if len(calls) == 1
                      else {"tool": "finish", "summary": "offline composer smoke"} if len(calls) == 7
                      else {"tool": "list_files"})
            completion = SimpleNamespace(model="offline", request_id="offline", request_ids={},
                                         raw_usage={"prompt_tokens": 1, "completion_tokens": 1},
                                         request_payload_sha256="offline", estimated_input_tokens=1)
            return action, completion

    monkeypatch.setattr(runner_module, "GitHubModelsClient", MockClient)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "example.py").write_text("value = 1\n", encoding="utf-8")
    request = AgentRunRequest(
        task_id="offline", condition_id="docatlas_tool_optional", workspace=workspace,
        prompt="Inspect protocol implementations", model="offline", timeout_seconds=30, max_turns=7,
        environment={}, mcp_config_path=None, tool_policy_path=tmp_path / "policy.json",
        output_dir=tmp_path / "output", allowed_write_paths=("example.py",),
    )
    sandbox = SimpleNamespace(verify=lambda: {"status": "verified"})
    result = runner_module.GitHubModelsRunner("offline-placeholder", sandbox=sandbox).run(request)
    assert result.status == "completed" and len(calls) == 7
    assert expected[0] in calls[-1]  # Survives both the old six-message selection and byte slice.
