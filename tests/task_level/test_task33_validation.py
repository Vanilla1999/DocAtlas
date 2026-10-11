from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import eval.task_level.task33_validation as task33_validation
from eval.task_level.isolated_delivery import (
    HostEvidenceSnapshot,
    TASK33_QUERY_DERIVATION,
    derive_task33_retrieval_query,
    persist_host_evidence,
)
from eval.task_level.task33_validation import (
    PROTOCOL_PATH,
    _check_bounded_evidence,
    _check_boundaries,
    _check_cell_result,
    _check_runner_usage,
    _check_worker_usage,
    build_artifact_manifest,
    load_protocol,
    validate_task33c_run,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")





















