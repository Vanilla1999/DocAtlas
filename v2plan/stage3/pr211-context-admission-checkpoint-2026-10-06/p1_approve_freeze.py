"""Record explicit owner approval on top of immutable reviewed P1 artifacts."""
from __future__ import annotations

import json

from p1_contract_corpus import BASE, validate
from p1_pin_reference import sha, write


def main():
    reference_path = BASE / "archives/p1-reviewed-reference-manifest.json"
    reference = json.loads(reference_path.read_text())
    review = reference["review"]
    assert sha(BASE / review["path"]) == review["sha256"]
    assessment = json.loads((BASE / review["path"]).read_text())
    assert assessment["status"] == "REVIEW_PASSED"
    assert assessment["reference_pin_eligible"] and not assessment["blocking_findings"]
    assert reference["reviewed_inputs"] == assessment["source_sha256"]
    for name, expected in reference["reviewed_inputs"].items():
        assert sha(BASE / name) == expected, f"Reviewed input changed: {name}"
    corpus = json.loads((BASE / "archives/p1-contract-corpus-review.json").read_text())
    checks = validate(corpus)
    all_rows = []
    for entry, split in zip(reference["files"], ("development", "holdout-candidate"), strict=True):
        assert sha(BASE / entry["path"]) == entry["sha256"]
        rows = json.loads((BASE / entry["path"]).read_text())["cases"]
        assert rows == [r for r in corpus["cases"] if r["split"] == split]
        assert len(rows) == entry["cases"]
        all_rows.extend(rows)
    assert len(all_rows) == len({r["id"] for r in all_rows}) == 224
    ledger = reference["ledger"]
    assert sha(BASE / ledger["path"]) == ledger["sha256"]
    ledger_rows = json.loads((BASE / ledger["path"]).read_text())["rows"]
    assert len(ledger_rows) == 159
    assert all(r["status"] == "NO_CHANGE_NOT_AUTHORIZED" for r in ledger_rows)
    approval = BASE / "P1_APPROVAL_RU.md"
    manifest = dict(
        schema="p1-approved-freeze-v1", date="2026-10-06", status="P1_DONE",
        approved_freeze=True, p1_done=True, p2_entry_ready=True, p2_started=False,
        owner_approval=dict(response="Да, утвердить и закрыть", source="interactive owner confirmation in this session",
                            path=approval.name, sha256=sha(approval)),
        reference=dict(path=str(reference_path.relative_to(BASE)), sha256=sha(reference_path)),
        review=review, reviewed_inputs=reference["reviewed_inputs"], files=reference["files"],
        test_migration_ledger=ledger, checks=checks,
        technical_decisions=["TD01", "TD02", "TD03", "TD04", "TD05", "TD06"],
        test_migration_process_approved=True, individual_test_changes_authorized=False,
        p0=dict(status="ACTIVE_ARCHIVAL_DEBT", prerequisite_waiver_approved=True,
                evidence="P0_FINAL_BASELINE_LINKAGE_RU.md",
                debt=["exact frozen command/environment/exit provenance", "same-P0 required-control evidence linkage"]),
        resource_limits=dict(external_api_cost_usd=0, external_replacement_request_calls=0,
                             additional_storage_bytes=2147483648, warm_p95_delta_seconds=1,
                             cold_p95_delta_seconds=5, output_search_budget_increase=0),
        pre_execution_requirements=["pin actual environment/config/serializer/tokenizer/model/prompt/index",
                                    "fix paired cold/warm sample protocol before candidate results",
                                    "preserve existing required release and typed-proof controls"],
        blind_holdout=False, source_disjoint_holdout=False, product_acceptance_passed=False,
        merge_authorized=False,
    )
    write(BASE / "archives/p1-approved-freeze-manifest.json", manifest)
    print(json.dumps(dict(status=manifest["status"], checks=checks, approved_freeze=True,
                         p0="ACTIVE_ARCHIVAL_DEBT", p2="NOT_STARTED")))


if __name__ == "__main__":
    main()
