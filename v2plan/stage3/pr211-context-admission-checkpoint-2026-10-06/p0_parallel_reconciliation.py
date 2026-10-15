"""Validate and reconcile independent audit outputs, never product policy."""
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path("v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06")


def load(path):
    raw = (BASE / path).read_bytes()
    return json.loads(gzip.decompress(raw) if path.endswith(".gz") else raw)


def key(row):
    return row["path"], row["owner"]


def main():
    rows = {}
    artifacts = []
    for partition in ("domain", "application", "interfaces", "infrastructure"):
        input_path = f"archives/p0-agent-input-{partition}.json.gz"
        output_path = f"archives/p0-agent-{partition}-decisions.json"
        inputs = load(input_path)["units"]
        outputs = load(output_path)["rows"]
        assert len(outputs) == len(inputs)
        assert len({key(r) for r in outputs}) == len(outputs)
        assert {key(r) for r in inputs} == {key(r) for r in outputs}
        pins = {key(r): r["source_sha256"] for r in inputs}
        for row in outputs:
            assert key(row) not in rows
            assert row["source_sha256"] == pins[key(row)]
            row = dict(row, partition=partition, audit_origin=output_path)
            rows[key(row)] = row
        artifacts.extend((input_path, output_path))
    for batch in range(3):
        input_path = f"archives/p0-application-open-{batch}.json"
        output_path = f"archives/p0-application-resolved-{batch}.json"
        inputs, outputs = load(input_path)["rows"], load(output_path)["rows"]
        assert len(inputs) == len(outputs) == 83
        assert {key(r) for r in inputs} == {key(r) for r in outputs}
        for row in outputs:
            assert rows[key(row)]["partition"] == "application"
            rows[key(row)] = dict(row, partition="application", audit_origin=output_path)
        artifacts.extend((input_path, output_path))
    final_path = "archives/p0-application-final-review.json"
    final = load(final_path)["rows"]
    assert {key(r) for r in final} == {k for k, r in rows.items() if r["decision"] == "OPEN"}
    for row in final:
        rows[key(row)] = dict(row, partition="application", audit_origin=final_path)
    artifacts.append(final_path)
    # Independent review rejected two overly broad technical proposals.
    corrections = {
        ("docmancer/docs/application/_patch_constraints_service_part02.py", "_PatchConstraintsServicePart02._symbol_from_line"):
            "D30: literal call/declaration extraction must be separated from GENERIC_CALL_SYMBOLS library blacklist, known Future/Widget types and last-call selection",
        ("docmancer/docs/application/_evidence_selection_part04.py", "requirement_probe_query"):
            "D25: result_access inserts result search term; supplied aliases/expected values have semantic producers; 320-char cap applies only to obligation branch",
    }
    for identity, reason in corrections.items():
        assert identity in rows
        row = rows[identity]
        row["superseded_decision"] = row["decision"]
        row.update(decision="SPLIT", reason=reason,
                   consumer_closure_status="OPEN",
                   consumer_closure_gaps=["Reconcile semantic producer/consumer branches named in independent review"],
                   integration_correction="P0_APPLICATION_FINAL_REVIEW_RU.md:91–117")
    assert len(rows) == 1954
    for row in rows.values():
        assert hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() == row["source_sha256"]
        assert row["decision"] in {"REMOVE", "SPLIT", "TECHNICAL-RETAIN-CANDIDATE", "OPEN"}
        assert row["reason"] and isinstance(row["preserve"], list)
    grouped = load("archives/p0-grouped-review-units.json.gz")
    assert {key(u) for u in grouped["units"] if u["status"] == "REVIEW-REQUIRED"} == set(rows)
    counts = dict(Counter(r["decision"] for r in rows.values()))
    report = {
        "schema": "p0-parallel-reconciliation-v1", "rows": [rows[k] for k in sorted(rows)],
        "counts": {"input_review_units": 1954, "reconciled_review_units": len(rows), "by_decision": counts,
                   "explicit_closure_open": sum(r.get("consumer_closure_status") == "OPEN" for r in rows.values()),
                   "reachability_unresolved": sum(r.get("reachability") == "unresolved" for r in rows.values())},
        "prior_units": {"node_complete": 568, "prior_owner_decisions": 102},
        "artifacts": [{"path": p, "sha256": hashlib.sha256((BASE / p).read_bytes()).hexdigest()} for p in artifacts],
        "classification_open": sum(r["decision"] == "OPEN" for r in rows.values()),
        "p0_done": False,
        "limitations": ["Local classification completion is distinct from semantic consumer closure",
                        "Source-edge maps are not runtime execution proofs",
                        "Technical retain candidates are not approved P1 exceptions",
                        "Prior module/owner decisions require consistency review; asset boundaries remain separately audited"],
    }
    output = json.dumps(report, ensure_ascii=False, indent=2).encode()
    (BASE / "archives/p0-parallel-reconciliation.json.gz").write_bytes(gzip.compress(output, mtime=0))
    print(json.dumps(report["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
