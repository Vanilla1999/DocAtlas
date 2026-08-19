#!/usr/bin/env python3
"""Regression gate for legacy project-answer contract completeness."""
from __future__ import annotations

import sys

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.question_ownership import frozen_ownership_mismatches


PARTIAL_LEGACY_CASES = (
    (
        "What are the public tools and their purposes?",
        "legacy_unresolved:purpose",
    ),
    (
        "Назови три публичных инструмента Docs MCP и когда использовать каждый.",
        "legacy_unresolved:inventory",
    ),
    (
        "What is the difference between evidence selection and question planning?",
        "legacy_unresolved:comparison",
    ),
    (
        "Explain the storage mutation coordination contract.",
        "legacy_unresolved:contract_scope",
    ),
    (
        "What does Phase 3.1 require for RetrievalDispatcher, the raw topic, "
        "EvidenceRequirementSet hints, and vector or embedding calls?",
        "legacy_unresolved:requirement_items",
    ),
)

COMPLETE_LEGACY_CONTROLS = (
    "How does prepare_docs sync_project_docs work?",
    "What does docs_status report and when should it be used?",
    "What are the three public Docs MCP tools?",
)

SILENT_EMPTY_PROBE = "xyzzy"


def _unsupported_requirement_present(question: str) -> bool:
    return any(
        row.kind == "unsupported_query"
        for row in build_requirements(question, profile="project_docs_answer")
    )


def main() -> int:
    errors: list[str] = []

    for question, reason in PARTIAL_LEGACY_CASES:
        contract = build_project_answer_contract(question)
        if reason not in contract.unresolved_parts:
            errors.append(
                f"partial legacy contract did not fail closed: {question!r}; "
                f"unresolved={contract.unresolved_parts!r}"
            )
        if "fail_closed:legacy_coverage" not in contract.parse_trace:
            errors.append(
                f"legacy coverage trace missing: {question!r}; "
                f"trace={contract.parse_trace!r}"
            )
        if not _unsupported_requirement_present(question):
            errors.append(
                f"partial legacy contract did not reach unsupported requirement gate: "
                f"{question!r}"
            )

    for question in COMPLETE_LEGACY_CONTROLS:
        contract = build_project_answer_contract(question)
        if contract.unresolved_parts:
            errors.append(
                f"complete legacy contract regressed: {question!r}; "
                f"unresolved={contract.unresolved_parts!r}"
            )
        if not contract.proof_obligations:
            errors.append(f"complete legacy contract became empty: {question!r}")

    silent = build_project_answer_contract(SILENT_EMPTY_PROBE)
    if silent.proof_obligations:
        errors.append(
            f"silent-empty probe unexpectedly produced obligations: "
            f"{silent.proof_obligations!r}"
        )
    if "unsupported_query:legacy_no_contract" not in silent.unresolved_parts:
        errors.append(
            f"silent-empty probe remained silent: unresolved={silent.unresolved_parts!r}"
        )
    if not _unsupported_requirement_present(SILENT_EMPTY_PROBE):
        errors.append("silent-empty probe did not reach unsupported requirement gate")

    errors.extend(frozen_ownership_mismatches())

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(
        "PASS: 5 partial legacy contracts fail closed; 3 complete legacy controls "
        "remain supported; silent-empty is explicit; canonical ownership signatures stable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
