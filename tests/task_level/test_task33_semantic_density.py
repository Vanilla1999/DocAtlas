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
