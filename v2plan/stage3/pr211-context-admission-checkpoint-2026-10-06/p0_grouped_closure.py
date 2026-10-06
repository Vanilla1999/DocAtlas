"""Group raw scan nodes into review units without hiding unresolved decisions."""
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path("v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06")


def main() -> None:
    ledger_path = BASE / "archives/p0-candidate-ledger.json.gz"
    ledger = json.loads(gzip.decompress(ledger_path.read_bytes()))
    grouped = defaultdict(list)
    for row in ledger["candidates"]:
        owner = ".".join(row["owner"])
        if not owner:
            owner = "assignment:" + ",".join(row["assignment"]) if row["assignment"] else f"module-expression:{row['line']}"
        grouped[(row["path"], owner)].append(row)
    units = []
    for (path, owner), rows in sorted(grouped.items()):
        decisions = sorted({row["candidate_decision"] for row in rows if row["candidate_decision"]})
        prior = sorted({row["prior_owner_decision"] for row in rows if row["prior_owner_decision"]})
        unresolved = [row for row in rows if row["candidate_decision"] is None]
        units.append({"path": path, "owner": owner, "source_sha256": rows[0]["source_sha256"],
                      "node_ids": [row["id"] for row in rows], "node_count": len(rows),
                      "classified_node_count": len(rows) - len(unresolved),
                      "unresolved_node_count": len(unresolved), "existing_decisions": decisions,
                      "existing_owner_review": prior,
                      "status": "NODE-CLASSIFICATION-COMPLETE" if not unresolved else "OWNER-AUDIT-DECISION-RECORDED" if len(prior) == 1 else "REVIEW-REQUIRED",
                      "owner_audit_decision": prior[0] if len(prior) == 1 else None,
                      "owner_decision_basis": "Pinned 157-symbol frame source review; atomic nodes retained for migration, not separately exempted" if len(prior) == 1 else None,
                      "unresolved_expressions": [{"line": row["line"], "kind": row["kind"], "expression": row["expression"]}
                                                 for row in unresolved],
                      "bridge_exports": [export for row in rows for export in row["real_bridge_exports"]],
                      "consumer_closure": "Not implied by grouping; reconcile with caller audits"})
    assert sum(unit["node_count"] for unit in units) == len(ledger["candidates"])
    counts = Counter(unit["status"] for unit in units)
    result = {"schema": "p0-symbol-review-units-v1", "input_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
              "counts": {"raw_nodes": len(ledger["candidates"]), "review_units": len(units), "by_status": dict(counts)},
              "units": units, "p0_done": False,
              "limitations": "Grouping preserves every raw node and existing decisions; it neither grants technical exemptions nor proves caller closure."}
    (BASE / "archives/p0-grouped-review-units.json.gz").write_bytes(gzip.compress(json.dumps(result, ensure_ascii=False, indent=2).encode(), mtime=0))
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
