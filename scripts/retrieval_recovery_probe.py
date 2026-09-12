from __future__ import annotations

import json
import shutil
from pathlib import Path

from eval.evidence_quality_v2.run import run


OUTPUT = Path("/tmp/docatlas-systemic-retrieval-final")


def main() -> int:
    shutil.rmtree(OUTPUT, ignore_errors=True)
    summary = run(OUTPUT)
    current = summary["variants"]["A-current"]
    no_expansion = summary["variants"]["D-no-expansion-replay"]
    report = {
        "a_current": {
            "cases": current["cases"],
            "within_budget": current["within_budget"],
            "within_budget_sufficient": current["within_budget_sufficient"],
            "sufficiency": current["sufficiency"],
            "integrity_violations": current["source_integrity_or_contract_violations"],
            "operational_errors": current["operational_errors"],
            "tokens": current["tokens"],
        },
        "no_expansion": {
            "within_budget_sufficient": no_expansion["within_budget_sufficient"],
            "integrity_violations": no_expansion["source_integrity_or_contract_violations"],
            "operational_errors": no_expansion["operational_errors"],
        },
        "historical_floors": {
            "a_current_within_budget_sufficient": 28,
            "no_expansion_within_budget_sufficient": 18,
        },
    }
    print("SYSTEMIC_RETRIEVAL_ACCEPTANCE_BEGIN")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    print("SYSTEMIC_RETRIEVAL_ACCEPTANCE_END")

    if current["operational_errors"] or current["source_integrity_or_contract_violations"]:
        raise SystemExit("A-current has operational or source-integrity failures")
    if no_expansion["operational_errors"] or no_expansion["source_integrity_or_contract_violations"]:
        raise SystemExit("no-expansion replay has operational or source-integrity failures")
    if current["within_budget"] != 48:
        raise SystemExit(f"frozen within-budget inventory changed: {current['within_budget']}")
    if current["within_budget_sufficient"] < 28:
        raise SystemExit(
            "current retrieval regressed below historical 28/48 exposed-corpus floor"
        )
    if no_expansion["within_budget_sufficient"] < 18:
        raise SystemExit(
            "no-expansion replay regressed below historical 18/48 exposed-corpus floor"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
