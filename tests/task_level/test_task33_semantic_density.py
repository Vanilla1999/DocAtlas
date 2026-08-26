from __future__ import annotations

import hashlib
import json
from pathlib import Path

from docmancer.docs.application.action_packet import build_action_packet
from docmancer.docs.application.model_visible_projection import project_patch_context
from eval.task_level.schemas import TASK_LEVEL_ROOT
from eval.task_level.task33_pilot import (
    TASK33C_PILOT_TASK_ID,
    TASK33C_REQUIRED_EVIDENCE_PATHS,
    TASK33C_REQUIRED_TARGET_PATHS,
    build_task33c_validation_evidence,
)


VALIDATION_COMMAND = "uv run --offline pytest tests/test_browser_permission_gate.py"


def _frozen_issue_text() -> str:
    tasks_path = TASK_LEVEL_ROOT / "tasks.jsonl"
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        task = json.loads(line)
        if task.get("task_id") == TASK33C_PILOT_TASK_ID:
            return str(task["issue_text"])
    raise AssertionError(f"Frozen task not found: {TASK33C_PILOT_TASK_ID}")


def _evidence_item(path: str, text: str, *, authority: str, source_class: str) -> dict:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "stable_chunk_id": "task33-regression-" + hashlib.sha256(path.encode()).hexdigest()[:32],
        "parent_logical_id": "task33-regression-parent-" + hashlib.sha256(path.encode()).hexdigest()[:24],
        "display_content_hash": digest,
        "display_text": text,
        "content": text,
        "path": path,
        "heading_path": Path(path).name,
        "authority": authority,
        "source_class": source_class,
        "retrieval_rank": 1,
        "score": 1.0,
        "matched": True,
    }


def _frozen_fixture_evidence() -> list[dict]:
    root = TASK_LEVEL_ROOT / "fixtures" / "templates" / TASK33C_PILOT_TASK_ID
    authorities = {
        "docs/permission-architecture.md": "source_of_truth",
        "docs/browser-flow.md": "project_rule",
        "docs/scan-flow.md": "project_rule",
        "docs/offline-sync.md": "project_rule",
    }
    rows: list[dict] = []
    for relative in TASK33C_REQUIRED_EVIDENCE_PATHS:
        rows.append(_evidence_item(
            relative,
            (root / relative).read_text(encoding="utf-8"),
            authority=authorities[relative],
            source_class="project_doc",
        ))
    for relative in TASK33C_REQUIRED_TARGET_PATHS:
        rows.append(_evidence_item(
            relative,
            (root / relative).read_text(encoding="utf-8"),
            authority="supporting",
            source_class="project_file",
        ))
    rows.append(build_task33c_validation_evidence(VALIDATION_COMMAND))
    return rows


def test_frozen_task33_model_visible_packet_preserves_semantics_under_2000_tokens():
    issue_text = _frozen_issue_text()
    evidence = _frozen_fixture_evidence()
    packet = build_action_packet(
        question=issue_text,
        context_pack=evidence,
        trust_contract={"selected": [], "risky": [], "rejected": []},
        max_tokens=2_000,
        project_path=str(
            TASK_LEVEL_ROOT / "fixtures" / "templates" / TASK33C_PILOT_TASK_ID
        ),
        required_evidence_paths=(
            *TASK33C_REQUIRED_EVIDENCE_PATHS,
            "host-policy://task33c/validation",
        ),
        required_target_paths=TASK33C_REQUIRED_TARGET_PATHS,
        behavioral_contract_required=True,
    )

    assert packet["status"] != "insufficient_evidence"
    assert packet["mutation_intent"]["operation"] == "modify"
    assert packet["mutation_intent"]["ready"] is True
    assert {
        row["path"] for row in packet["target_surface"]["likely_files"]
    } >= set(TASK33C_REQUIRED_TARGET_PATHS)
    assert {
        row["path"] for row in packet["source_of_truth"]
    } >= set(TASK33C_REQUIRED_EVIDENCE_PATHS)

    projection, _ = project_patch_context(
        packet=packet,
        evidence_items=evidence,
        max_tokens=2_000,
    )
    visible = json.dumps(projection, ensure_ascii=False, sort_keys=True)

    assert projection["status"] != "insufficient_evidence"
    assert projection["estimated_tokens"] <= 2_000
    assert projection["mutation_ready"] is True
    assert projection["edit_ready"] is True
    assert "Browser entry is allowed only for PermissionDecision.allow" in visible
    assert "allowOfflineFallback: false" in visible
    assert VALIDATION_COMMAND in visible
    for path in TASK33C_REQUIRED_TARGET_PATHS:
        assert path in visible

    browser_invariants = [
        row for row in projection.get("invariants") or []
        if "Browser entry is allowed only for PermissionDecision.allow" in str(row.get("text") or "")
    ]
    assert browser_invariants
    assert all(row.get("evidence_ids") for row in browser_invariants)
