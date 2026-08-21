#!/usr/bin/env python3
"""Regression gate for legacy project-answer contract completeness."""
from __future__ import annotations

import sys

from docmancer.docs.application.evidence_selection import (
    build_requirements,
    project_docs_selection_config,
    select_evidence,
)
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.question_ownership import frozen_ownership_mismatches
from docmancer.docs.domain.question_plan import compile_question_plan


MIGRATED_PARTIAL_CASES = (
    "What are the public tools and their purposes?",
    "Назови три публичных инструмента Docs MCP и когда использовать каждый.",
    "What is the difference between evidence selection and question planning?",
    "Explain the storage mutation coordination contract.",
)

PARTIAL_LEGACY_CASES = (
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

GENERIC_PROJECT_CASES = (
    (
        "How should treasure campaigns configure trip positions, persist campaign progress, "
        "and safely select encounters while preserving gold and gem targets?"
    ),
    (
        "What documented safety rules apply to treasure campaign trip.take, meet.accept, "
        "trip.back, checkpoint counters, and accepting gold/gem meet types?"
    ),
    "How should takeAPicture be handled when the NBO scanner returns an image?",
)

GENERIC_REQUIRED_ANCHORS = {
    GENERIC_PROJECT_CASES[0]: {
        "treasure", "trip", "positions", "campaign", "progress", "encounters",
        "gold", "gem", "targets",
    },
    GENERIC_PROJECT_CASES[1]: {
        "trip.take", "meet.accept", "trip.back", "checkpoint", "counters", "types",
    },
    GENERIC_PROJECT_CASES[2]: {"takeapicture", "nbo", "scanner", "image"},
}

GENERIC_FORBIDDEN_SCAFFOLD = {
    "and", "an", "be", "configure", "documented", "handled", "persist", "preserving",
    "returns", "safely", "select", "accepting",
}

GENERIC_PROJECT_WITNESSES = {
    GENERIC_PROJECT_CASES[0]: (
        "Treasure campaigns use trip positions to record location. "
        "Campaign progress is stored at checkpoints. "
        "Encounters follow campaign safety rules. "
        "Gold and gem targets remain unchanged across the trip."
    ),
    GENERIC_PROJECT_CASES[1]: (
        "Treasure campaign safety rules require `trip.take` to update checkpoint counters. "
        "`meet.accept` accepts only approved gold/gem meet types. "
        "`trip.back` restores the documented checkpoint state."
    ),
    GENERIC_PROJECT_CASES[2]: (
        "`takeAPicture` is handled by the NBO scanner. "
        "The scanner returns an image to the caller."
    ),
}

SILENT_EMPTY_PROBES = (
    "xyzzy",
    "Bitcoin price",
)

CAUSAL_UNSUPPORTED_PROBES = (
    "Why does clear-index delete remote Qdrant collections?",
    "Why does clear-index sometimes delete remote Qdrant collections?",
    "Why are there four storage layers?",
)

GENERIC_ADVERSARIAL_TAIL = (
    "How should treasure campaigns configure trip positions, persist campaign progress, "
    "and safely select encounters while preserving gold and gem targets? "
    "Also calculate the unrelated Bitcoin price."
)


def _requirements(question: str):
    return build_requirements(question, profile="project_docs_answer")


def _unsupported_requirement_present(question: str) -> bool:
    return any(row.kind == "unsupported_query" for row in _requirements(question))


def _generic_witness_candidate(index: int, content: str) -> dict[str, str]:
    return {
        "stable_id": f"generic-project-witness-{index}",
        "source": f"docs/generic-project-witness-{index}.md",
        "content": content,
    }


def main() -> int:
    errors: list[str] = []

    for question in MIGRATED_PARTIAL_CASES:
        plan = compile_question_plan(question)
        contract = build_project_answer_contract(question)
        if not plan.handled:
            errors.append(f"reviewed legacy migration lost QuestionPlan ownership: {question!r}")
        if contract.unresolved_parts:
            errors.append(
                f"reviewed legacy migration regressed to unresolved: {question!r}; "
                f"unresolved={contract.unresolved_parts!r}"
            )
        if not contract.proof_obligations:
            errors.append(f"reviewed legacy migration produced no obligations: {question!r}")
        if "fail_closed:legacy_coverage" in contract.parse_trace:
            errors.append(f"reviewed legacy migration still traversed legacy coverage: {question!r}")

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

    for index, question in enumerate(GENERIC_PROJECT_CASES):
        plan = compile_question_plan(question)
        contract = build_project_answer_contract(question)
        requirements = _requirements(question)
        if plan.handled:
            errors.append(f"generic project case unexpectedly became QuestionPlan-owned: {question!r}")
        if contract.unresolved_parts:
            errors.append(
                f"generic project case remained unresolved: {question!r}; "
                f"unresolved={contract.unresolved_parts!r}"
            )
        if "fallback:generic_project_terms" not in contract.parse_trace:
            errors.append(f"generic project case did not use bounded fallback: {question!r}")
        if len(contract.proof_obligations) < 3:
            errors.append(
                f"generic project case produced too little proof surface: {question!r}; "
                f"obligations={contract.proof_obligations!r}"
            )
        if any(row.kind != "exact_fact" for row in contract.proof_obligations):
            errors.append(f"generic project fallback produced a non-exact-fact obligation: {question!r}")

        subjects = {row.subject.casefold() for row in contract.proof_obligations}
        missing_anchors = GENERIC_REQUIRED_ANCHORS[question] - subjects
        if missing_anchors:
            errors.append(
                f"generic project fallback lost required anchors: {question!r}; "
                f"missing={sorted(missing_anchors)!r}; subjects={sorted(subjects)!r}"
            )
        leaked_scaffold = subjects & GENERIC_FORBIDDEN_SCAFFOLD
        if leaked_scaffold:
            errors.append(
                f"generic project fallback promoted query scaffolding to proof: {question!r}; "
                f"leaked={sorted(leaked_scaffold)!r}"
            )
        for row in contract.proof_obligations:
            if (
                row.query_span_start is None
                or row.query_span_end is None
                or row.query_span_text is None
                or row.query_span_text.casefold() != row.subject.casefold()
            ):
                errors.append(
                    f"generic project obligation is not bound to its exact query span: "
                    f"{question!r}; obligation={row!r}"
                )

        if any(row.kind == "unsupported_query" for row in requirements):
            errors.append(f"generic project case still reached unsupported requirement gate: {question!r}")
        mandatory = [row for row in requirements if row.mandatory]
        if len(mandatory) != len(contract.proof_obligations):
            errors.append(
                f"generic project requirements are not all mandatory: {question!r}; "
                f"mandatory={len(mandatory)} obligations={len(contract.proof_obligations)}"
            )

        witness = _generic_witness_candidate(index, GENERIC_PROJECT_WITNESSES[question])
        decision = select_evidence(
            [witness],
            question=question,
            config=project_docs_selection_config(800),
            requirements=requirements,
        )
        if decision.status != "ok" or not decision.support_decision.answer_supported:
            errors.append(
                f"generic project contract is not satisfiable by natural project documentation: "
                f"{question!r}; missing={decision.missing_requirements!r}; "
                f"subjects={sorted(subjects)!r}"
            )

    adversarial_contract = build_project_answer_contract(GENERIC_ADVERSARIAL_TAIL)
    if not adversarial_contract.unresolved_parts:
        guarded_terms = " ".join(
            row.subject.casefold() for row in adversarial_contract.proof_obligations
        )
        if "bitcoin" not in guarded_terms and "calculate" not in guarded_terms:
            errors.append(
                "generic fallback silently dropped an unrelated adversarial tail instead of "
                "failing closed or representing it as mandatory evidence"
            )

    for question in SILENT_EMPTY_PROBES:
        silent = build_project_answer_contract(question)
        if silent.proof_obligations:
            errors.append(
                f"silent-empty probe unexpectedly produced obligations: {question!r}; "
                f"obligations={silent.proof_obligations!r}"
            )
        if "unsupported_query:legacy_no_contract" not in silent.unresolved_parts:
            errors.append(
                f"silent-empty probe remained silent: {question!r}; "
                f"unresolved={silent.unresolved_parts!r}"
            )
        if not _unsupported_requirement_present(question):
            errors.append(f"silent-empty probe did not reach unsupported requirement gate: {question!r}")

    for question in CAUSAL_UNSUPPORTED_PROBES:
        contract = build_project_answer_contract(question)
        if contract.proof_obligations:
            errors.append(
                f"causal why probe must not use exact-fact fallback: {question!r}; "
                f"obligations={contract.proof_obligations!r}"
            )
        if "unsupported_query:legacy_no_contract" not in contract.unresolved_parts:
            errors.append(
                f"causal why probe lost fail-closed status: {question!r}; "
                f"unresolved={contract.unresolved_parts!r}"
            )
        if not _unsupported_requirement_present(question):
            errors.append(f"causal why probe did not reach unsupported requirement gate: {question!r}")

    errors.extend(frozen_ownership_mismatches())

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(
        "PASS: reviewed QuestionPlan migrations remain stable; partial legacy semantics fail "
        "closed; complete legacy controls remain supported; 3 novel project-specific questions "
        "receive bounded mandatory anchor contracts with exact query spans and natural-doc "
        "witnesses; unrelated tails are represented or rejected; silent-empty and causal-why "
        "probes remain unsupported; canonical ownership signatures stable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
