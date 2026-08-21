#!/usr/bin/env python3
"""Materialize v3 and expose exact-fixture preflight diagnostics on failure."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v3 = root / "scripts/_materialize_recoverable_docs_failures_v3.py"
exec(compile(v3.read_text(encoding="utf-8"), str(v3), "exec"), {"__name__": "__main__", "__file__": str(v3)})

gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old = '''        original_query = service.project_docs.query_project_docs\n        service.project_docs.query_project_docs = lambda *args, **kwargs: []\n'''
new = '''        inspection = service.inspect_project_docs(str(project))\n        print("EXACT_FIXTURE_INSPECTION=" + json.dumps({\n            "reason_code": inspection.reason_code,\n            "requires_confirmation": inspection.requires_confirmation,\n            "confirmation_reason": inspection.confirmation_reason,\n            "diagnostics": inspection.diagnostics,\n            "warnings": inspection.warnings,\n        }, indent=2, default=str))\n        original_query = service.project_docs.query_project_docs\n        service.project_docs.query_project_docs = lambda *args, **kwargs: []\n'''
if gate.count(old) != 1:
    raise SystemExit(f"exact fixture diagnostic patch count={gate.count(old)}")
gate_path.write_text(gate.replace(old, new, 1), encoding="utf-8")
