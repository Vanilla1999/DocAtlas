"""Pin reviewed evaluation bytes without granting owner approval."""
from __future__ import annotations

import hashlib
import json
import platform

from p1_contract_corpus import BASE, validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        assert path.read_text() == text, f"Refusing to replace pinned reference: {path}"
    else:
        path.write_text(text)


def main():
    review_path = BASE / "archives/p1-independent-review-v2.json"
    review = json.loads(review_path.read_text())
    assert review["reference_pin_eligible"] and review["status"] == "REVIEW_PASSED"
    for name, expected in review["source_sha256"].items():
        assert sha(BASE / name) == expected, f"Reviewed bytes changed: {name}"
    corpus = json.loads((BASE / "archives/p1-contract-corpus-review.json").read_text())
    checks = validate(corpus)
    files = []
    for split, filename in (("development", "p1-development-reference-v1.json"),
                            ("holdout-candidate", "p1-holdout-reference-v1.json")):
        path = BASE / "archives" / filename
        rows = [r for r in corpus["cases"] if r["split"] == split]
        write(path, dict(schema=corpus["schema"], status="REVIEWED_REFERENCE_NOT_OWNER_APPROVED", cases=rows))
        files.append(dict(path=str(path.relative_to(BASE)), sha256=sha(path), cases=len(rows)))
    transition = BASE / "archives/p0-transition-manifest.json"
    assertions = json.loads(transition.read_text())["assertions"]
    assert len(assertions) == 159
    ledger = []
    for index, assertion in enumerate(assertions):
        ledger.append(dict(assertion_id=f"TM-A{index + 1:03d}", **assertion,
                           old_guarantee_status="exact assertion preserved; individual semantic mapping required before change",
                           incompatible_detail=None, replacement_test_id=None,
                           positive_negative_evidence=None, owner_approval=None, reviewer=None,
                           candidate_sha=None, status="NO_CHANGE_NOT_AUTHORIZED"))
    ledger_path = BASE / "archives/p1-test-migration-ledger.json"
    write(ledger_path, dict(source_manifest_sha256=sha(transition), rows=ledger))
    manifest = dict(schema="p1-reviewed-reference-manifest-v1",
                    status="REVIEWED_REFERENCE_NOT_OWNER_APPROVED",
                    approved_freeze=False, p1_done=False, p2_authorized=False,
                    review=dict(path=str(review_path.relative_to(BASE)), sha256=sha(review_path)),
                    reviewed_inputs=review["source_sha256"], files=files,
                    ledger=dict(path=str(ledger_path.relative_to(BASE)), sha256=sha(ledger_path), assertions=159),
                    checks=checks, generation_environment=dict(python=platform.python_version()),
                    pending=["owner TD/TM/behavior decisions", "formal P0 archival waiver or closure before approved freeze",
                             "numeric backend latency/cost/storage ceilings before model choice/download/run",
                             "actual product config/serializer/tokenizer/environment binding before execution"],
                    limitations=["family-disjoint, not blind or source-disjoint holdout",
                                 "quantum control intentionally reuses development Pebble document",
                                 "offline validation is not product retrieval acceptance"])
    write(BASE / "archives/p1-reviewed-reference-manifest.json", manifest)
    print(json.dumps(dict(checks=checks, splits=files, approvals="PENDING")))


if __name__ == "__main__":
    main()
