#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = [sys.executable, "scripts/run_recovery_contract_gate.py"]
MUTANTS = (
    (
        "rephrase-auto-executes",
        "docmancer/docs/application/recovery.py",
        '"repeat_docs_context": True,\n            "auto_execute": False,',
        '"repeat_docs_context": True,\n            "auto_execute": True,',
    ),
    (
        "authoritative-conflict-does-not-stop",
        "docmancer/docs/application/recovery.py",
        '"hard_stop": True,',
        '"hard_stop": False,',
    ),
    (
        "unbounded-rephrase-loop",
        "docmancer/docs/application/recovery.py",
        'if _already_rephrased(question):',
        'if False and _already_rephrased(question):',
    ),
    (
        "rephrase-invents-domain-fact",
        "docmancer/docs/application/recovery.py",
        'fragment = _clean_fragment(fragment, max_chars=140)',
        'fragment = "INVENTED_DOMAIN_FACT"',
    ),
    (
        "eligibility-treated-as-retrieval",
        "docmancer/docs/application/recovery.py",
        'elif proof_origin == "eligibility":',
        'elif False and proof_origin == "eligibility":',
    ),
    (
        "exact-document-fallback-disabled",
        "docmancer/docs/application/_project_docs_service_part03.py",
        'if (\n            evidence_path\n            and not chunks\n            and current_by_path.get(normalize_doc_path(evidence_path))\n        ):',
        'if (\n            False\n            and evidence_path\n            and not chunks\n            and current_by_path.get(normalize_doc_path(evidence_path))\n        ):',
    ),
)


def run_gate() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        GATE,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )


def main() -> int:
    baseline = run_gate()
    if baseline.returncode != 0:
        print(baseline.stdout, file=sys.stderr)
        print("FAIL: recovery mutation baseline is red", file=sys.stderr)
        return 1

    killed = 0
    for name, relative, old, new in MUTANTS:
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        if original.count(old) != 1:
            print(f"FAIL: mutant {name} patch target count={original.count(old)}", file=sys.stderr)
            return 1
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            result = run_gate()
        finally:
            path.write_text(original, encoding="utf-8")
        if result.returncode == 0:
            print(f"FAIL: mutant survived: {name}\n{result.stdout}", file=sys.stderr)
            return 1
        killed += 1
        print(f"KILLED: {name}")

    if killed != len(MUTANTS):
        print(f"FAIL: killed {killed}/{len(MUTANTS)}", file=sys.stderr)
        return 1
    print(f"PASS: recoverable documentation failure mutation gate killed {killed}/{len(MUTANTS)} mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
