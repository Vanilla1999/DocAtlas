"""Prove whether legacy contracts can authorize incomplete answers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


def unit(text: str) -> AnswerUnit:
    return AnswerUnit(
        unit_id=hashlib.sha256(text.encode()).hexdigest()[:16],
        kind="sentence",
        text=text,
        char_start=0,
        char_end=len(text),
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        proposition=True,
    )


def evaluate(probe_id: str, question: str, evidence: tuple[str, ...]) -> dict:
    contract = build_project_answer_contract(question)
    rows = []
    for obligation in contract.proof_obligations:
        proofs = [
            local_proof_for_obligation(
                obligation,
                unit(text),
                source={
                    "authority": "source_of_truth",
                    "title": "Canonical project documentation",
                    "path": "docs/canonical.md",
                },
            )
            for text in evidence
        ]
        valid = [proof for proof in proofs if proof.valid]
        rows.append({
            "kind": obligation.kind,
            "subject": obligation.subject,
            "relation": obligation.relation,
            "target": obligation.target,
            "valid": bool(valid),
            "valid_reasons": [proof.reason for proof in valid],
        })
    return {
        "id": probe_id,
        "question": question,
        "contract_unresolved": list(contract.unresolved_parts),
        "obligations": rows,
        "all_obligations_provable": bool(rows) and all(row["valid"] for row in rows),
        "evidence": list(evidence),
    }


def main() -> int:
    probes = [
        evaluate(
            "tools_without_purposes",
            "What are the public tools and their purposes?",
            ("Docs MCP exposes exactly three public tools: `get_docs_context`, `prepare_docs`, and `docs_status`.",),
        ),
        evaluate(
            "russian_usage_without_inventory",
            "Назови три публичных инструмента Docs MCP и когда использовать каждый.",
            ("Docs MCP should be used when an agent needs project documentation.",),
        ),
        evaluate(
            "difference_without_contrast",
            "What is the difference between evidence selection and question planning?",
            ("The difference between evidence selection and question planning is documented here.",),
        ),
        evaluate(
            "storage_contract_without_coordination",
            "Explain the storage mutation coordination contract.",
            ("Storage has a documented contract for maintainers.",),
        ),
        evaluate(
            "phase_requirements_subset",
            (
                "What does Phase 3.1 require for RetrievalDispatcher, the raw topic, "
                "EvidenceRequirementSet hints, and vector or embedding calls?"
            ),
            (
                "The Phase 3.1 contract defines RetrievalDispatcher.",
                "The Phase 3.1 contract defines EvidenceRequirementSet.",
                "The Phase 3.1 contract defines vectors.",
            ),
        ),
    ]
    report = {
        "schema_version": "docatlas-legacy-partial-support-probe-v1",
        "total": len(probes),
        "partial_support_candidates": sum(row["all_obligations_provable"] for row in probes),
        "results": probes,
    }
    Path("legacy-partial-support-probe-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("LEGACY_PARTIAL_SUPPORT_PROBE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
