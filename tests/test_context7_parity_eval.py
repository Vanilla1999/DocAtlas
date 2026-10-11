from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("context7_parity_eval", ROOT / "eval" / "context7_parity" / "parity_eval.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _dataset(module):
    return module.load_jsonl(ROOT / "eval" / "context7_parity" / "dataset.jsonl")


def _trace(item: dict, provider: str, *, phase: str = "warm", source: str | None = None) -> dict:
    evidence = item["expected_evidence"]
    symbol = evidence["symbols"][0]
    snippet = "x = 1" if item["ecosystem"] == "python" else "const x = 1;"
    return {
        "provider": provider,
        "case_id": item["id"],
        "first_tool": item["expected_first_tool"][provider],
        "results": [{"source": source or evidence["source"], "section": evidence["section"], "content": symbol, "snippet": snippet}],
        "latency_ms": 10,
        "phase": phase,
        "resolved_version": item["requested_version"],
        "network_fetch_count": 0,
        "lifecycle_call_count": 0,
    }











