#!/usr/bin/env python3
"""Materialize v3 plus exact-document UX and a complete public-flow fixture."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v3 = root / "scripts/_materialize_recoverable_docs_failures_v3.py"
exec(compile(v3.read_text(encoding="utf-8"), str(v3), "exec"), {"__name__": "__main__", "__file__": str(v3)})

# An evidence locator is routing identity, not a semantic topic to suggest back
# to the user. Keep exact/full locator filtering out of rephrase candidates.
recovery_path = root / "docmancer/docs/application/recovery.py"
recovery = recovery_path.read_text(encoding="utf-8")
old = '''    if not candidates:\n        candidates = _problem_spans(question, requirements)\n\n    result: list[str] = []\n'''
new = '''    if not candidates:\n        candidates = _problem_spans(question, requirements)\n    if evidence_path:\n        normalized_locator = evidence_path.replace("\\\\", "/").casefold()\n        locator_leaf = normalized_locator.rsplit("/", 1)[-1]\n        candidates = [\n            value for value in candidates\n            if _clean_fragment(value, max_chars=240).replace("\\\\", "/").casefold()\n            not in {normalized_locator, locator_leaf}\n        ]\n\n    result: list[str] = []\n'''
if recovery.count(old) != 1:
    raise SystemExit(f"exact locator rephrase filter patch count={recovery.count(old)}")
recovery_path.write_text(recovery.replace(old, new, 1), encoding="utf-8")

# The exact-document fallback is tested through the real public path. Provide a
# normal high-level overview so the fixture does not independently request an
# architecture-document creation confirmation.
gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old_file = '''    (project / "docatlas.project-docs.yaml").write_text(\n        """schema_version: 1\ndocuments:\n  - path: docs/ADAPTIVE_TREASURE_CONTRACT.md\n    role: development\n    scope: project\n    description: Adaptive treasure source-of-truth contract.\n    authority: source_of_truth\n    status: active\n    impact: track\n""",\n        encoding="utf-8",\n    )\n'''
new_file = '''    (project / "ARCHITECTURE.md").write_text(\n        "# Architecture\\n\\nThe project keeps domain contracts under docs/.\\n",\n        encoding="utf-8",\n    )\n    (project / "docatlas.project-docs.yaml").write_text(\n        """schema_version: 1\ndocuments:\n  - path: docs/ADAPTIVE_TREASURE_CONTRACT.md\n    role: development\n    scope: project\n    description: Adaptive treasure source-of-truth contract.\n    authority: source_of_truth\n    status: active\n    impact: track\n  - path: ARCHITECTURE.md\n    role: project_architecture\n    scope: project\n    description: High-level project architecture.\n    authority: source_of_truth\n    status: active\n    impact: track\n""",\n        encoding="utf-8",\n    )\n'''
if gate.count(old_file) != 1:
    raise SystemExit(f"architecture fixture patch count={gate.count(old_file)}")
gate = gate.replace(old_file, new_file, 1)

# Prove the exact-file recovery suggestion talks about the requested facet, not
# the document locator itself.
old_locator = '''    assert extract_document_locator(locator_question) == "ADAPTIVE_TREASURE_CONTRACT.md"\n    with tempfile.TemporaryDirectory(prefix="docatlas-recovery-") as tmp:\n'''
new_locator = '''    assert extract_document_locator(locator_question) == "ADAPTIVE_TREASURE_CONTRACT.md"\n    locator_miss = build_recovery_diagnosis(\n        locator_question,\n        _decision(locator_question, [], profile="project_document_answer"),\n    )\n    locator_suggestions = locator_miss.get("suggested_questions") or []\n    assert locator_suggestions, locator_miss\n    assert "what does it say about adaptive_treasure_contract.md" not in locator_suggestions[0].casefold()\n    with tempfile.TemporaryDirectory(prefix="docatlas-recovery-") as tmp:\n'''
if gate.count(old_locator) != 1:
    raise SystemExit(f"locator suggestion test patch count={gate.count(old_locator)}")
gate_path.write_text(gate.replace(old_locator, new_locator, 1), encoding="utf-8")
