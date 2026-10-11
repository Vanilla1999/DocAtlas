from __future__ import annotations

import json
import hashlib
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from docmancer.docs.application.action_packet import build_action_packet, refresh_action_packet_estimate
from docmancer.docs.application.model_visible_projection import (
    project_patch_context,
    validate_model_visible_projection,
)
from eval.task_level.execution import capture_patch, fresh_run_environment, run_canary
from eval.task_level.evaluators.policy import audit_trajectory
from eval.task_level.runners.base import AgentRunOutput, AgentRunRequest
from eval.task_level.runners.claude import ClaudeRunner
from eval.task_level.runners.codex import (
    _is_provider_failure,
    _normalize_jsonl,
    _prepare_blocked_network_tools,
    _prepare_codex_home,
    _redact,
    _token_usage_summary,
)
from eval.task_level.runners.opencode import _normalize_events, _write_opencode_config


class MockRunner:
    runner_id = "mock"

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        target = request.workspace / "calc.py"
        if target.exists():
            target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        normalization = request.workspace / "normalization.py"
        if normalization.exists():
            normalization.write_text(
                "def normalize(value):\n    return abs(value)\n",
                encoding="utf-8",
            )
        policy = request.workspace / "policy.py"
        if policy.exists():
            policy.write_text(
                "def may_enter(allowed):\n    return allowed\n",
                encoding="utf-8",
            )
        request.output_dir.mkdir(parents=True, exist_ok=True)
        stdout = request.output_dir / "stdout.log"
        stderr = request.output_dir / "stderr.log"
        trajectory = request.output_dir / "trajectory.normalized.json"
        stdout.write_text("{}\n", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        trajectory.write_text(json.dumps([{
            "event_type": "edit",
            "tool_name": "Edit",
            "arguments": {},
            "result_summary": "edited calc.py, normalization.py, and policy.py",
        }]), encoding="utf-8")
        now = datetime.now(timezone.utc).isoformat()
        return AgentRunOutput(
            status="completed",
            exit_code=0,
            started_at=now,
            finished_at=now,
            wall_time_seconds=0.1,
            raw_stdout_path=str(stdout),
            raw_stderr_path=str(stderr),
            trajectory_path=str(trajectory),
            patch_path=None,
            tool_calls=[],
            input_tokens=None,
            output_tokens=None,
            model="mock",
            runner_version="mock",
            notes=[],
        )






def test_patch_capture(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=tmp_path, check=False)
    subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=tmp_path, check=False)
    (tmp_path / "file.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=False)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (tmp_path / "file.txt").write_text("after\n", encoding="utf-8")

    patch_path, status_path, changed_path, changed = capture_patch(tmp_path, tmp_path)

    assert patch_path.read_text(encoding="utf-8")
    assert status_path.read_text(encoding="utf-8")
    assert json.loads(changed_path.read_text(encoding="utf-8")) == ["file.txt"]
    assert changed == ["file.txt"]


def test_patch_capture_includes_pure_untracked_file(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=tmp_path, check=True)
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    (tmp_path / "new.txt").write_text("new content\n", encoding="utf-8")

    patch_path, _status_path, _changed_path, changed = capture_patch(tmp_path, tmp_path)

    assert changed == ["new.txt"]
    assert "new content" in patch_path.read_text(encoding="utf-8")










def test_codex_normalizes_successful_required_once_retrieval_metadata(tmp_path: Path):
    objective = "Preserve the permission gate contract."
    source_text = "Must preserve the permission gate contract."
    evidence = [{
        "doc_scope": "project",
        "source_class": "project_doc",
        "path": "AGENTS.md",
        "heading_path": "Permission gate",
        "authority": "canonical",
        "content": source_text,
        "char_start": 0,
        "char_end": len(source_text),
        "line_start": 1,
        "line_end": 1,
    }]
    packet = build_action_packet(
        question=objective,
        context_pack=evidence,
        # Source completeness covers this explicit literal, never an inferred
        # interpretation of the unchanged task objective.
        public_requirements=(source_text,),
    )
    projection, snapshot = project_patch_context(packet=packet, evidence_items=evidence)
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []
    assert projection["result"] == "data" and projection["completeness"] == "complete"
    assert projection["sources"] == packet["sources"] and len(projection["sources"]) == 1
    source = projection["sources"][0]
    assert source["path"] == "AGENTS.md" and source["text"] == source_text
    assert source["content_sha256"] == hashlib.sha256(source_text.encode()).hexdigest()
    assert (source["char_start"], source["char_end"], source["line_start"], source["line_end"]) == (0, len(source_text), 1, 1)
    assert source["instruction_trust"] == "untrusted_data" and projection["edit_ready"] is False
    requirement, = projection["requirements"]
    assert requirement["kind"] == "required_fact" and requirement["value"] == source_text
    assert requirement["mandatory"] is True and requirement["public_provenance"] == "public_task_contract"
    assignment, = projection["assignments"]
    assert assignment["requirement_id"] == requirement["requirement_id"]
    assert assignment["evidence_id"] == source["stable_id"] and assignment["path"] == source["path"]
    assert assignment["proof_role"] == "generic_fact" and assignment["unit_id"]
    assert assignment["unit_content_hash"] == source["content_sha256"]
    assert (assignment["unit_char_start"], assignment["unit_char_end"]) == (0, len(source_text))
    assert "missing" not in projection

    partial_packet = build_action_packet(question=objective, context_pack=evidence)
    partial, partial_snapshot = project_patch_context(packet=partial_packet, evidence_items=evidence)
    assert validate_model_visible_projection(partial, snapshot=partial_snapshot) == []
    assert partial["result"] == "data" and partial["completeness"] == "partial"
    assert partial["sources"] == projection["sources"] and partial["edit_ready"] is False
    assert partial["missing"] == ["visible_content_assignment_required"]
    item = {
        "id": "item-1",
        "type": "mcp_tool_call",
        "server": "docmancer-docs",
        "tool": "get_docs_context",
        "arguments": {
            "question": objective,
            "context_format": "patch_context",
        },
    }
    raw = "\n".join([
        json.dumps({"type": "item.started", "item": item}),
        json.dumps({
            "type": "item.completed",
            "item": {
                **item,
                "result": {
                    "structured_content": projection,
                },
            },
        }),
    ])

    events, tool_calls, _input, _output = _normalize_jsonl(
        raw,
        task_objective=objective,
    )
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps(events), encoding="utf-8")
    audit = audit_trajectory("docatlas_tool_required_once", trajectory)

    assert audit.clean
    assert audit.get_docs_context_calls == 1 and len(tool_calls) == 1
    assert events[0]["arguments"]["question_matches_task_objective"] is True
    assert events[0]["arguments"]["retrieval_succeeded"] is True
    assert events[0]["arguments"]["context_format"] == "patch_context"
    assert events[0]["arguments"]["action_packet_result"] == "data"
    assert events[0]["arguments"]["action_packet_completeness"] == "complete"
    for change in ("question", "format", "legacy_envelope", "edit_authority", "partial_content"):
        invalid_item = deepcopy(item)
        invalid_projection = deepcopy(projection)
        if change == "question":
            invalid_item["arguments"]["question"] = "A different objective."
        elif change == "format":
            invalid_item["arguments"].pop("context_format")
        elif change == "legacy_envelope":
            invalid_projection = {"delivery_strategy": "bounded_direct", "action_packet": packet}
        elif change == "partial_content":
            invalid_projection = deepcopy(partial)
        else:
            invalid_projection["edit_ready"] = True
            refresh_action_packet_estimate(invalid_projection)
        invalid_item["result"] = {"structured_content": invalid_projection}
        invalid_events, _, _, _ = _normalize_jsonl(
            json.dumps({"type": "item.completed", "item": invalid_item}), task_objective=objective,
        )
        assert invalid_events[0]["arguments"]["retrieval_succeeded"] is False, change
        if change == "partial_content":
            assert invalid_events[0]["arguments"]["question_matches_task_objective"] is True
            assert invalid_events[0]["arguments"]["context_format"] == "patch_context"
            assert invalid_events[0]["arguments"]["action_packet_result"] == "data"
            assert invalid_events[0]["arguments"]["action_packet_completeness"] == "partial"



















