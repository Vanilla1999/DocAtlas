#!/usr/bin/env python3
"""Materialize v12 and use the internal ProjectContextService mode."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v12 = root / "scripts/_materialize_recoverable_docs_failures_v12.py"
exec(compile(v12.read_text(encoding="utf-8"), str(v12), "exec"), {"__name__": "__main__", "__file__": str(v12)})

gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old = '''            raw_context = service.get_project_context(\n                str(project), exact_question, mode="project", scope="project"\n            )\n'''
new = '''            raw_context = service.get_project_context(\n                str(project), exact_question, mode="project-only", scope="project"\n            )\n'''
if gate.count(old) != 1:
    raise SystemExit(f"internal mode diagnostic patch count={gate.count(old)}")
gate_path.write_text(gate.replace(old, new, 1), encoding="utf-8")
