#!/usr/bin/env python3
"""Materialize v15 and target the hardened exact-fallback condition."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v15 = root / "scripts/_materialize_recoverable_docs_failures_v15.py"
exec(compile(v15.read_text(encoding="utf-8"), str(v15), "exec"), {"__name__": "__main__", "__file__": str(v15)})

path = root / "scripts/run_recovery_mutation_gate.py"
text = path.read_text(encoding="utf-8")
old = '''    (\n        "exact-document-fallback-disabled",\n        "docmancer/docs/application/_project_docs_service_part03.py",\n        'if evidence_path and not chunks and current_by_path.get(evidence_path):',\n        'if False and evidence_path and not chunks and current_by_path.get(evidence_path):',\n    ),\n'''
new = '''    (\n        "exact-document-fallback-disabled",\n        "docmancer/docs/application/_project_docs_service_part03.py",\n        'if (\\n            evidence_path\\n            and not chunks\\n            and current_by_path.get(normalize_doc_path(evidence_path))\\n        ):',\n        'if (\\n            False\\n            and evidence_path\\n            and not chunks\\n            and current_by_path.get(normalize_doc_path(evidence_path))\\n        ):',\n    ),\n'''
if text.count(old) != 1:
    raise SystemExit(f"exact fallback mutation precision patch count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
