from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from eval.agent_developer_v1.first_divergence import (
    EXPECTED_FAILURE_COUNTS,
    build_atlas,
    load_json,
    render_markdown,
    sha256_json,
    validate_atlas,
)


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "eval/agent_developer_v1/tasks.json"
ORACLE = ROOT / "eval/agent_developer_v1/results/first-divergence-oracle-5a36a15.json"
REPORT = ROOT / "eval/agent_developer_v1/results/model-benchmark.json"
ATLAS = ROOT / "eval/agent_developer_v1/results/first-divergence-atlas.json"
MARKDOWN = ROOT / "docs/analysis/p1.2-agent-developer-first-divergence.md"


def generated() -> dict:
    return build_atlas(load_json(TASKS), load_json(ORACLE), load_json(REPORT))













