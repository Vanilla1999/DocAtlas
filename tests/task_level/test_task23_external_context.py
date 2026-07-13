from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from eval.task_level.conditions import CONDITIONS
from eval.task_level.execution import inject_audited_external_context


def _snapshot(task_id: str, content: str) -> dict:
    return {
        "schema_version": "audited-external-context-1",
        "task_id": task_id,
        "library": "example_dependency",
        "version": "1.2.3",
        "source_url": "https://example.test/docs/1.2.3",
        "retrieved_at": "2026-07-13T00:00:00Z",
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "content": content,
    }


def test_task23_external_lane_is_injected_and_has_no_live_tools():
    policy = CONDITIONS["repo_plus_audited_external_context"].tool_policy

    assert policy.inject_external_context is True
    assert policy.allow_docatlas is False
    assert policy.allow_context7 is False
    assert policy.allow_web is False


def test_audited_external_context_injection_verifies_hash_and_writes_provenance(tmp_path):
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(_snapshot("task_a", "Pinned API contract.")), encoding="utf-8")
    output_dir = tmp_path / "run"

    result = inject_audited_external_context(
        SimpleNamespace(task_id="task_a"),
        output_dir,
        snapshot_path=snapshot_path,
    )

    assert result["status"] == "success"
    assert result["content_sha256"] == _snapshot("task_a", "Pinned API contract.")["content_sha256"]
    assert "Pinned API contract." in (output_dir / "audited_external_context.md").read_text(encoding="utf-8")
    provenance = json.loads((output_dir / "audited_external_context.json").read_text(encoding="utf-8"))
    assert provenance["source_url"] == "https://example.test/docs/1.2.3"
    assert provenance["version"] == "1.2.3"


def test_audited_external_context_injection_fails_closed_on_hash_or_task_mismatch(tmp_path):
    snapshot = _snapshot("other_task", "Pinned API contract.")
    snapshot["content_sha256"] = "0" * 64
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    result = inject_audited_external_context(
        SimpleNamespace(task_id="task_a"),
        tmp_path / "run",
        snapshot_path=snapshot_path,
    )

    assert result["status"] == "condition_setup_failed"
    assert set(result["errors"]) == {"task_id_mismatch", "content_hash_mismatch"}
