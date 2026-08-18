"""Diagnostic local-proof probes for semantic QuestionPlan facets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


def _unit(
    text: str,
    *,
    kind: str = "sentence",
    source_field: str | None = None,
) -> AnswerUnit:
    return AnswerUnit(
        unit_id=hashlib.sha256((kind + "\0" + text).encode()).hexdigest()[:16],
        kind=kind,
        text=text,
        char_start=0,
        char_end=len(text),
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        proposition=True,
        source_field=source_field,
    )


def _obligation(question: str, *, subject: str | None = None):
    contract = build_project_answer_contract(question)
    rows = list(contract.proof_obligations)
    if subject is not None:
        rows = [row for row in rows if row.subject == subject]
    if len(rows) != 1:
        raise AssertionError((question, subject, rows, contract.unresolved_parts))
    return rows[0]


def _probe(
    probe_id: str,
    question: str,
    text: str,
    expected: bool,
    *,
    subject: str | None = None,
    source: dict[str, Any] | None = None,
    kind: str = "sentence",
    source_field: str | None = None,
) -> dict[str, Any]:
    obligation = _obligation(question, subject=subject)
    proof = local_proof_for_obligation(
        obligation,
        _unit(text, kind=kind, source_field=source_field),
        source=source or {},
    )
    return {
        "id": probe_id,
        "question": question,
        "subject": obligation.subject,
        "relation": obligation.relation,
        "text": text,
        "expected": expected,
        "actual": proof.valid,
        "passed": proof.valid is expected,
        "reason": proof.reason,
        "scores": {
            "subject": proof.subject_score,
            "relation": proof.relation_score,
            "value": proof.value_score,
            "completeness": proof.completeness_score,
        },
    }


def main() -> int:
    condition_question = "What happens when the preview plan is stale?"
    blocking_question = "Under which conditions is cleanup blocked?"
    requirements_question = "What does the two-cell smoke procedure require?"
    comparison_question = "How does evidence selection differ from question planning?"
    tools_question = "What are the three public Docs MCP tools and when do I use each one?"
    premise_question = "Why does clear-index always delete remote Qdrant collections?"
    location_question = "Where is the project answer contract documented?"

    probes = [
        _probe(
            "condition_local_positive",
            condition_question,
            "When the preview plan is stale, the runtime rebuilds the plan before continuing.",
            True,
        ),
        _probe(
            "condition_cross_clause_negative",
            condition_question,
            "The preview plan is stale. Another cache then rebuilds itself.",
            False,
            kind="unit_group",
        ),
        _probe(
            "blocking_local_positive",
            blocking_question,
            "Cleanup is blocked when an index writer is active.",
            True,
        ),
        _probe(
            "blocking_cross_clause_negative",
            blocking_question,
            "Cleanup is described here. If a cache is stale, another service blocks requests.",
            False,
            kind="unit_group",
        ),
        _probe(
            "requirements_local_positive",
            requirements_question,
            "The two-cell smoke procedure requires a preflight, one canary, exactly two cells, no retries, an event audit, and verification.",
            True,
        ),
        _probe(
            "requirements_cross_clause_negative",
            requirements_question,
            "The two-cell smoke procedure is documented here. Another workflow requires a preflight, canary, exactly two cells, audit, and verification.",
            False,
            kind="unit_group",
        ),
        _probe(
            "comparison_local_positive",
            comparison_question,
            "Evidence selection chooses proof-bearing candidates, whereas question planning converts user wording into obligations.",
            True,
        ),
        _probe(
            "comparison_same_behavior_negative",
            comparison_question,
            "Evidence selection returns candidates. Question planning returns candidates.",
            False,
            kind="unit_group",
        ),
        _probe(
            "public_tool_local_usage_positive",
            tools_question,
            "Use `get_docs_context` when you need a bounded project-doc answer from Docs MCP.",
            True,
            subject="get_docs_context",
        ),
        _probe(
            "public_tool_unrelated_usage_negative",
            tools_question,
            "`get_docs_context` is a Docs MCP public tool. Use `prepare_docs` for synchronization.",
            False,
            subject="get_docs_context",
            kind="unit_group",
        ),
        _probe(
            "premise_bare_restatement_negative",
            premise_question,
            "`clear-index` always deletes remote Qdrant collections.",
            False,
        ),
        _probe(
            "premise_correction_positive",
            premise_question,
            "`clear-index` never deletes remote Qdrant collections.",
            True,
        ),
        _probe(
            "premise_cross_clause_negative",
            premise_question,
            "`clear-index` is documented here. Another tool never deletes remote Qdrant collections.",
            False,
            kind="unit_group",
        ),
        _probe(
            "location_source_field_positive",
            location_question,
            "docs/project-answer-contract.md",
            True,
            source_field="path_or_url",
            source={
                "path": "docs/project-answer-contract.md",
                "title": "Project answer contract",
                "authority": "source_of_truth",
            },
        ),
        _probe(
            "location_prose_path_negative",
            location_question,
            "The project answer contract is in docs/project-answer-contract.md.",
            False,
            source={"title": "Project answer contract", "authority": "source_of_truth"},
        ),
    ]

    failures = [row for row in probes if not row["passed"]]
    report = {
        "schema_version": "docatlas-proof-probe-v1",
        "total": len(probes),
        "passed": len(probes) - len(failures),
        "failed": len(failures),
        "failures": failures,
        "results": probes,
    }
    Path("question-proof-probe-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("QUESTION_PROOF_PROBE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
