from __future__ import annotations

import copy
from pathlib import Path

import pytest

from eval.agent_developer_v1.contract_v2_ablation import (
    build_ablation,
    load_json,
    render_markdown,
    validate_ablation,
)


ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "eval/agent_developer_v1/results/first-divergence-atlas.json"
REPORT = ROOT / "eval/agent_developer_v1/results/contract-v2-ablation.json"
MARKDOWN = ROOT / "docs/analysis/p1.3-agent-contract-v2-ablation.md"


def generated() -> dict:
    return build_ablation(load_json(ATLAS))











