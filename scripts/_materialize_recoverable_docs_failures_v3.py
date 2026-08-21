#!/usr/bin/env python3
"""Materialize v2 plus the substring-preserving rephrase integrity invariant."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / "scripts/_materialize_recoverable_docs_failures.py"
source = base.read_text(encoding="utf-8")
start = source.index("# Fix the generated exact-rephrase marker.")
end = source.index("# Exact-document recovery reuses canonical stored sections")
source = source[:start] + source[end:]
exec(compile(source, str(base), "exec"), {"__name__": "__main__", "__file__": str(base)})

gate_path = root / "scripts/run_recovery_contract_gate.py"
gate = gate_path.read_text(encoding="utf-8")
old = '''def _assert_suggestion_integrity(original: str, suggestion: str) -> None:\n    original_tokens = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/=+-]+", original.casefold()))\n    suggestion_tokens = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/=+-]+", suggestion.casefold()))\n    invented = {\n        token for token in suggestion_tokens\n        if token not in original_tokens and token not in FIXED_WRAPPER\n    }\n    if invented:\n        raise AssertionError(f"rephrase invented domain tokens: {sorted(invented)!r}; {suggestion!r}")\n'''
new = '''def _assert_suggestion_integrity(original: str, suggestion: str) -> None:\n    original_folded = original.casefold()\n    suggestion_tokens = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/=+-]+", suggestion.casefold()))\n    invented = {\n        token for token in suggestion_tokens\n        if token not in FIXED_WRAPPER and token not in original_folded\n    }\n    if invented:\n        raise AssertionError(f"rephrase invented domain tokens: {sorted(invented)!r}; {suggestion!r}")\n'''
if gate.count(old) != 1:
    raise SystemExit(f"recovery gate integrity patch count={gate.count(old)}")
gate_path.write_text(gate.replace(old, new, 1), encoding="utf-8")
