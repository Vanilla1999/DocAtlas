#!/usr/bin/env python3
"""Materialize v14 and make the rephrase mutation target unambiguous."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v14 = root / "scripts/_materialize_recoverable_docs_failures_v14.py"
exec(compile(v14.read_text(encoding="utf-8"), str(v14), "exec"), {"__name__": "__main__", "__file__": str(v14)})

path = root / "scripts/run_recovery_mutation_gate.py"
text = path.read_text(encoding="utf-8")
old = '''    (\n        "rephrase-auto-executes",\n        "docmancer/docs/application/recovery.py",\n        '"auto_execute": False,',\n        '"auto_execute": True,',\n    ),\n'''
new = '''    (\n        "rephrase-auto-executes",\n        "docmancer/docs/application/recovery.py",\n        '"repeat_docs_context": True,\\n            "auto_execute": False,',\n        '"repeat_docs_context": True,\\n            "auto_execute": True,',\n    ),\n'''
if text.count(old) != 1:
    raise SystemExit(f"rephrase mutation precision patch count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
