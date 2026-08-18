"""Focused local-proof probes for semantic QuestionPlan facets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


def unit(text: str, *, kind: str = "sentence", source_field: str | None = None) -> AnswerUnit:
    return AnswerUnit(
        unit_id=hashlib.sha256((kind + "\0" + text).encode()).hexdigest()[:16],
        kind=kind,
        text=text,
        char_start=None if source_field else 0,
        char_end=None if source_field else len(text),
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        proposition=True,
        source_field=source_field,
    )


def obligation(question: str, subject: str | None = None):
    contract = build_project_answer_contract(question)
    rows = [row for row in contract.proof_obligations if subject is None or row.subject == subject]
    if len(rows) != 1:
        raise AssertionError((question, subject, rows, contract.unresolved_parts))
    return rows[0]


def check(
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
    row = obligation(question, subject)
    proof = local_proof_for_obligation(
        row,
        unit(text, kind=kind, source_field=source_field),
        source=source or {},
    )
    return {
        "id": probe_id,
        "question": question,
        "subject": row.subject,
        "relation": row.relation,
        "expected": expected,
        "actual": proof.valid,
        "passed": proof.valid is expected,
        "reason": proof.reason,
        "text": text,
    }


def main() -> int:
    condition = "What happens when the preview plan is stale?"
    blocking = "Under which conditions is cleanup blocked?"
    requirements = "What does the two-cell smoke procedure require?"
    comparison = "How does evidence selection differ from question planning?"
    tools = "What are the three public Docs MCP tools and when do I use each one?"
    premise = "Why does clear-index always delete remote Qdrant collections?"
    location = "Where is the project answer contract documented?"

    probes = [
        check("condition_local_positive", condition,
              "When the preview plan is stale, the runtime rebuilds the plan before continuing.", True),
        check("condition_cross_clause_negative", condition,
              "The preview plan is stale. Another cache then rebuilds itself.", False, kind="unit_group"),
        check("blocking_local_positive", blocking,
              "Cleanup is blocked when an index writer is active.", True),
        check("blocking_cross_clause_negative", blocking,
              "Cleanup is described here. If a cache is stale, another service blocks requests.", False,
              kind="unit_group"),
        check("requirements_local_positive", requirements,
              "The two-cell smoke procedure requires a preflight, one canary, exactly two cells, no retries, an event audit, and verification.", True),
        check("requirements_cross_clause_negative", requirements,
              "The two-cell smoke procedure is documented here. Another workflow requires a preflight, canary, exactly two cells, audit, and verification.", False,
              kind="unit_group"),
        check("comparison_local_positive", comparison,
              "Evidence selection chooses proof-bearing candidates, whereas question planning converts user wording into obligations.", True),
        check("comparison_same_behavior_negative", comparison,
              "Evidence selection returns candidates. Question planning returns candidates.", False,
              kind="unit_group"),
        check("public_tool_local_usage_positive", tools,
              "Use `get_docs_context` when you need a bounded project-doc answer from Docs MCP.", True,
              subject="get_docs_context"),
        check("public_tool_unrelated_usage_negative", tools,
              "`get_docs_context` is a Docs MCP public tool. Use `prepare_docs` for synchronization.", False,
              subject="get_docs_context", kind="unit_group"),
        check("premise_bare_restatement_negative", premise,
              "`clear-index` always deletes remote Qdrant collections.", False),
        check("premise_correction_positive", premise,
              "`clear-index` never deletes remote Qdrant collections.", True),
        check("premise_cross_clause_negative", premise,
              "`clear-index` is documented here. Another tool never deletes remote Qdrant collections.", False,
              kind="unit_group"),
        check("location_source_field_positive", location,
              "docs/project-answer-contract.md", True,
              source_field="path_or_url",
              source={"path": "docs/project-answer-contract.md", "title": "Project answer contract", "authority": "source_of_truth"}),
        check("location_prose_path_negative", location,
              "The project answer contract is in docs/project-answer-contract.md.", False,
              source={"title": "Project answer contract", "authority": "source_of_truth"}),
    ]
    failures = [row for row in probes if not row["passed"]]
    report = {
        "schema_version": "docatlas-proof-probe-v2",
        "total": len(probes),
        "passed": len(probes) - len(failures),
        "failed": len(failures),
        "failures": failures,
        "results": probes,
    }
    Path("question-proof-probe-v2-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("QUESTION_PROOF_PROBE_V2=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
