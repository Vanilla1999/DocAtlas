#!/usr/bin/env python3
"""Materialize v5 and assert generated exact rephrases exhaust recovery."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v5 = root / "scripts/_materialize_recoverable_docs_failures_v5.py"
exec(compile(v5.read_text(encoding="utf-8"), str(v5), "exec"), {"__name__": "__main__", "__file__": str(v5)})

gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old = '''    locator_miss = build_recovery_diagnosis(\n        locator_question,\n        _decision(locator_question, [], profile="project_document_answer"),\n    )\n    locator_suggestions = locator_miss.get("suggested_questions") or []\n    assert locator_suggestions, locator_miss\n    assert "what does it say about adaptive_treasure_contract.md" not in locator_suggestions[0].casefold()\n    with tempfile.TemporaryDirectory(prefix="docatlas-recovery-") as tmp:\n'''
new = '''    locator_miss = build_recovery_diagnosis(\n        locator_question,\n        _decision(locator_question, [], profile="project_document_answer"),\n    )\n    assert locator_miss["disposition"] == "search_local_source", locator_miss\n    assert locator_miss["rephrase_exhausted"] is True\n    assert "suggested_questions" not in locator_miss\n\n    # A first-time exact-path wording that is not the server-generated wrapper\n    # may still offer one narrower facet retry. The locator itself must not be\n    # reflected back as the requested semantic topic.\n    initial_exact = "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type."\n    initial_diag = build_recovery_diagnosis(\n        initial_exact,\n        _decision(initial_exact, [], profile="project_document_answer"),\n    )\n    assert initial_diag["disposition"] == "rephrase_question", initial_diag\n    initial_suggestions = initial_diag.get("suggested_questions") or []\n    assert initial_suggestions, initial_diag\n    assert "about meet_type" in initial_suggestions[0].casefold(), initial_suggestions\n    assert "about adaptive_treasure_contract" not in initial_suggestions[0].casefold()\n    with tempfile.TemporaryDirectory(prefix="docatlas-recovery-") as tmp:\n'''
if gate.count(old) != 1:
    raise SystemExit(f"generated exact rephrase test patch count={gate.count(old)}")
gate_path.write_text(gate.replace(old, new, 1), encoding="utf-8")
