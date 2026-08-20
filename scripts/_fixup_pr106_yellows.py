#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

status_path = ROOT / "docmancer/docs/interfaces/mcp/prefetch_tools.py"
text = status_path.read_text(encoding="utf-8")
old = '''        "diagnostics": (\n            {"active_index": {"db_path": active_db_path}}\n            if active_db_path not in (None, "") else {}\n        ),\n'''
new = '''        "diagnostics": (\n            {\n                "active_index": {\n                    key: active_index.get(key)\n                    for key in ("db_path", "config_source", "config_path", "retrieval_mode")\n                    if active_index.get(key) not in (None, "")\n                }\n            }\n            if active_db_path not in (None, "") else {}\n        ),\n'''
if text.count(old) != 1:
    raise RuntimeError(f"bounded diagnostics anchor count={text.count(old)}, expected 1")
status_path.write_text(text.replace(old, new, 1), encoding="utf-8")

cases_path = ROOT / "eval/agent_developer_v2/cases.json"
payload = json.loads(cases_path.read_text(encoding="utf-8"))
rows = payload["cases"]
policy = next(row for row in rows if row["id"] == "project_policy_tiny_budget")
policy["calls"][0]["question"] = "What is ProjectRetryPolicy?"
policy["calls"][0]["packet_tokens"] = 800
policy["calls"][0]["max_projection_tokens"] = 800
policy["max_trajectory_tokens"] = 800

detail_id = "project_policy_detail_fails_closed"
rows[:] = [row for row in rows if row.get("id") != detail_id]
rows.append({
    "id": detail_id,
    "class": "semantic_fail_closed",
    "fixture": "explicit_manifest_monorepo",
    "working_path": "packages/orders/src/submission.py",
    "max_get_docs_context_calls": 1,
    "max_trajectory_tokens": 300,
    "calls": [{
        "question": "How many retry attempts does ProjectRetryPolicy allow?",
        "mode": "project",
        "scope": "project",
        "packet_tokens": 300,
        "max_projection_tokens": 300,
        "target_expected_status": "insufficient_evidence",
        "forbidden_sources": ["packages/orders/README.md", "packages/payments/README.md"],
        "target_edit_ready": False,
    }],
})
if len(rows) != 28:
    raise RuntimeError(f"expected 28 v2 cases after fail-closed split, got {len(rows)}")
cases_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

readme_path = ROOT / "eval/agent_developer_v2/README.md"
readme = readme_path.read_text(encoding="utf-8")
readme = readme.replace("27 reviewed architectural scenarios", "28 reviewed architectural scenarios")
readme = readme.replace("bounded definition/behavior/requirements/project-policy packets", "bounded definition/behavior/requirements/project-policy packets plus an unsupported policy-detail fail-closed case")
readme_path.write_text(readme, encoding="utf-8")

print("preserved bounded active_index identity and split policy detail into a fail-closed case")
