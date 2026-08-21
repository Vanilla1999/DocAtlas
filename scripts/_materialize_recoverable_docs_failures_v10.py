#!/usr/bin/env python3
"""Materialize v9 plus locator-aware canonical requirement construction."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
v9 = root / "scripts/_materialize_recoverable_docs_failures_v9.py"
exec(compile(v9.read_text(encoding="utf-8"), str(v9), "exec"), {"__name__": "__main__", "__file__": str(v9)})

path = root / "docmancer/docs/application/evidence_requirements.py"
text = path.read_text(encoding="utf-8")
old = '''    existing_exact_values = {\n        item.value.casefold() for item in requirements if item.kind == "exact_term"\n    }\n    identifier_values = sorted({\n'''
new = '''    existing_exact_values = {\n        item.value.casefold() for item in requirements if item.kind == "exact_term"\n    }\n    evidence_path_aliases: set[str] = set()\n    for raw_path in required_evidence_paths:\n        normalized_path = str(raw_path).strip().replace("\\\\", "/").casefold()\n        if not normalized_path:\n            continue\n        evidence_path_aliases.add(normalized_path)\n        evidence_path_aliases.add(normalized_path.rsplit("/", 1)[-1])\n    identifier_values = sorted({\n'''
if text.count(old) != 1:
    raise SystemExit(f"evidence path alias setup patch count={text.count(old)}")
text = text.replace(old, new, 1)
old = '''        and token.casefold() not in existing_exact_values\n    }, key=str.casefold)\n'''
new = '''        and token.casefold() not in existing_exact_values\n        and token.casefold().replace("\\\\", "/") not in evidence_path_aliases\n    }, key=str.casefold)\n'''
if text.count(old) != 1:
    raise SystemExit(f"evidence path semantic identifier filter patch count={text.count(old)}")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# Freeze the no-double-count invariant directly.
gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old = '''    assert extract_document_locator(locator_question) == "ADAPTIVE_TREASURE_CONTRACT.md"\n    locator_miss = build_recovery_diagnosis(\n'''
new = '''    assert extract_document_locator(locator_question) == "ADAPTIVE_TREASURE_CONTRACT.md"\n    exact_requirement_probe = build_requirements(\n        "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type.",\n        required_evidence_paths=("docs/ADAPTIVE_TREASURE_CONTRACT.md",),\n        profile="project_document_answer",\n    )\n    exact_mandatory_values = {\n        item.value.casefold() for item in exact_requirement_probe if item.mandatory\n    }\n    assert "docs/adaptive_treasure_contract.md" not in exact_mandatory_values\n    assert "adaptive_treasure_contract.md" not in exact_mandatory_values\n    assert "meet_type" in exact_mandatory_values\n    locator_miss = build_recovery_diagnosis(\n'''
if gate.count(old) != 1:
    raise SystemExit(f"locator requirement invariant test patch count={gate.count(old)}")
gate_path.write_text(gate.replace(old, new, 1), encoding="utf-8")
