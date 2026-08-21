#!/usr/bin/env python3
"""Materialize v8 and normalize the exact fallback activation lookup."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v8 = root / "scripts/_materialize_recoverable_docs_failures_v8.py"
exec(compile(v8.read_text(encoding="utf-8"), str(v8), "exec"), {"__name__": "__main__", "__file__": str(v8)})

path = root / "docmancer/docs/application/_project_docs_service_part03.py"
text = path.read_text(encoding="utf-8")
old = '''        if evidence_path and not chunks and current_by_path.get(evidence_path):\n'''
new = '''        if (\n            evidence_path\n            and not chunks\n            and current_by_path.get(normalize_doc_path(evidence_path))\n        ):\n'''
if text.count(old) != 1:
    raise SystemExit(f"exact fallback activation patch count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
