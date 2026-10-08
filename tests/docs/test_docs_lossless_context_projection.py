"""Acquired in-memory core-context fidelity; no current-file/catalog proof."""
from copy import deepcopy
import hashlib

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._docs_context_projection_core import project_docs_context
from docmancer.docs.application.model_visible_projection import (
    _refresh_estimate, _source_digest, validate_model_visible_projection,
)
from docmancer.docs.application.reference_query_tagging import _tag_retrieval_query
from docmancer.docs.domain.context_budget import ContextBudget
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


QUESTION = "protocol validation rules"


def source_text(kind, index=0, *, large=False):
    subject = "protocol" if index == 0 else f"binding_{index}"
    count = 70 if large else 1
    if kind == "list":
        return "\n".join(
            f"- {subject} validation rules: field_{index}_{n} must equal exact-value-{index}-{n}; reject other values."
            for n in range(count)
        )
    if kind == "table":
        return "\n".join([
            "| Validation subject | Field | Required value |", "| --- | --- | --- |",
            *(f"| {subject} validation rules | field_{index}_{n} | exact-value-{index}-{n} |" for n in range(count)),
        ])
    return "\n".join([
        "```python", f"# {subject} validation rules", f"def validate_{subject}(record):",
        *(f'    assert record["field_{index}_{n}"] == "exact-value-{index}-{n}"' for n in range(count)),
        f'    return record["field_{index}_{count - 1}"]', "```",
    ])


def fixture(kind="code", *, large=False, four=False, partial=False):
    plan = build_documentation_query_plan(
        QUESTION, lookup_queries=tuple(f"binding_{i} validation rules" for i in range(1, 4)) if four else (),
    )
    if partial:
        plan = build_documentation_query_plan(QUESTION, lookup_queries=("unavailable ledger checksum",))
    rows = []
    for index in range(4 if four else 1):
        text = source_text(kind, index, large=large)
        row = {
            "path": f"docs/validation-{index}.md", "source_class": "project_doc",
            "heading_path": "Validation contract", "content": text, "display_text": text,
            "project_identity": "offline-context", "version": "4.0", "version_binding": "4.0",
            "authority": "source_of_truth", "doc_scope": "project", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
            "stable_chunk_id": f"validation-{index}", "parent_logical_id": f"contract-{index}",
            "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
            "char_start": 0, "char_end": len(text), "line_start": 10,
            "line_end": 9 + len(text.splitlines()),
        }
        lookup = plan.queries[index]
        chunk = RetrievedChunk(source=row["path"], chunk_index=0, text=text, score=1, metadata=row)
        tagged = _tag_retrieval_query([chunk], lookup.query_id, lookup.text, lookup=lookup,
                                      expected_project_identity="offline-context")[0]
        assert tagged.metadata["retrieval_query_matches"][lookup.query_id]["qualified"] is True
        rows.append(dict(tagged.metadata))
    return {"context_pack": rows, "project_identity": "offline-context",
            "documentation_query_plan": plan.as_payload()}, rows


def positive(kind="code"):
    retrieval, rows = fixture(kind)
    payload, snapshot = project_docs_context(retrieval=retrieval)
    assert payload.get("sources") and snapshot
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []
    assert payload["sources"][0]["snippet"] == rows[0]["content"]
    return payload, snapshot


def assert_bound(payload, snapshot, rows):
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert {row["snippet"] for row in payload["sources"]} == {row["content"] for row in rows}
    assert {row["path_or_url"] for row in payload["sources"]} == {row["path"] for row in rows}
    assert set(snapshot) == {row["evidence_id"] for row in payload["sources"]}
    for row in payload["sources"]:
        original = next(item for item in rows if item["path"] == row["path_or_url"])
        bound = snapshot[row["evidence_id"]]
        assert bound["projected_source"] == row
        assert row["content_sha256"] == _source_digest(bound["source"])
        assert row["version_binding"] == "4.0"
        assert (row["line_start"], row["line_end"]) == (original["line_start"], original["line_end"])


@pytest.mark.parametrize("kind", ["list", "table", "code"])
@pytest.mark.parametrize("budget", [256, 800], ids=["legacy-256", "legacy-800"])
def test_long_structural_unit_keeps_exact_tail_and_bound_span(kind, budget):
    positive(kind)
    retrieval, rows = fixture(kind, large=True)
    before = deepcopy(rows)
    payload, snapshot = project_docs_context(retrieval=retrieval, max_tokens=budget)
    assert payload.get("sources"), retrieval["retrieval_diagnostics"]
    assert_bound(payload, snapshot, rows)
    assert payload["estimated_tokens"] > 800
    assert "exact-value-0-69" in payload["sources"][0]["snippet"]
    assert rows == before


@pytest.mark.parametrize("kind", ["list", "table", "code"])
def test_four_distinct_qualified_lanes_survive_without_source_fit_gate(kind):
    positive(kind)
    retrieval, rows = fixture(kind, large=True, four=True)
    payload, snapshot = project_docs_context(retrieval=retrieval)
    assert len(payload.get("sources", [])) == 4, retrieval["retrieval_diagnostics"]
    assert_bound(payload, snapshot, rows)
    assert payload["estimated_tokens"] > 800
    assert set(payload["covered_query_ids"]) == {"query-original", "query-lookup-1", "query-lookup-2", "query-lookup-3"}
    assert payload["missing_query_ids"] == []


@pytest.mark.parametrize("large", [False, True], ids=["short", "long"])
def test_qualified_partial_keeps_quote_without_absence_or_answer_certification(large):
    positive()
    retrieval, rows = fixture(large=large, partial=True)
    payload, snapshot = project_docs_context(retrieval=retrieval)
    assert payload.get("sources"), retrieval["retrieval_diagnostics"]
    assert_bound(payload, snapshot, rows)
    assert payload["covered_query_ids"] == ["query-original"]
    assert payload["missing_query_ids"] == ["query-lookup-1"]
    assert payload["query_coverage"] == "partial"


@pytest.mark.parametrize("change", ["project", "missing_project", "stale", "index", "lifecycle", "empty_path", "path_limit", "version_limit"])
def test_current_source_policy_and_identity_bounds_still_reject(change):
    positive()
    retrieval, rows = fixture()
    changes = {"project": ("project_identity", "foreign"), "missing_project": ("project_identity", ""),
               "stale": ("freshness", "stale"), "index": ("index_freshness", "stale"),
               "lifecycle": ("lifecycle_status", "deprecated"), "empty_path": ("path", ""),
               "path_limit": ("path", "p" * 501), "version_limit": ("version_binding", "v" * 101)}
    key, value = changes[change]
    rows[0][key] = value
    payload, snapshot = project_docs_context(retrieval=retrieval)
    assert not payload.get("sources") and not snapshot
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []


@pytest.mark.parametrize("change", ["confirmation", "delivery_block", "question_limit", "query_conflict", "unqualified"])
def test_veto_and_literal_plan_boundaries_do_not_become_fit_exemptions(change):
    positive()
    retrieval, rows = fixture()
    if change == "confirmation":
        retrieval.update(requires_confirmation=True, status="confirmation_required")
    elif change == "delivery_block":
        retrieval["delivery_decision"] = {"deliverable": False, "reason_code": "catalog_invalid"}
    elif change == "question_limit":
        retrieval["documentation_query_plan"]["original_question"] = "q" * 4_001
    elif change == "query_conflict":
        retrieval["documentation_query_plan"]["queries"][0]["text"] = "foreign ledger checksum"
    else:
        text = "Unrelated ledger checksum description."
        rows[0].update(content=text, display_text=text, display_content_hash=hashlib.sha256(text.encode()).hexdigest())
    payload, snapshot = project_docs_context(retrieval=retrieval)
    assert not payload.get("sources") and not snapshot
    if change == "question_limit":
        assert payload["status"] == "insufficient_evidence"
        assert payload["reason_code"] == "request_input_limit_exceeded"
        assert payload.get("edit_ready", False) is False
        assert payload.get("answer_supported", False) is payload.get("answer_available", False) is False
        # The existing core adds reason_code after the failure estimate refresh.
        # Preserve this diagnostic; do not repair an unassigned refusal contract.
        assert validate_model_visible_projection(payload, snapshot=snapshot) == ["projection estimate mismatch"]
    else:
        assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
        assert validate_model_visible_projection(payload, snapshot=snapshot) == []


@pytest.mark.parametrize("change", ["snippet", "span", "hash", "path", "version", "raw_version", "answer_flag"])
def test_real_valid_context_keeps_canonical_snapshot_tamper_rejection(change):
    payload, snapshot = positive()
    row = payload["sources"][0]
    if change == "snippet":
        row["snippet"] += "\nForged validation rule."
    elif change == "span":
        row["line_end"] += 1
    elif change == "hash":
        row["content_sha256"] = "0" * 64
    elif change == "path":
        row["path_or_url"] = "docs/foreign.md"
    elif change == "version":
        row["version_binding"] = "9.0"
    elif change == "raw_version":
        snapshot[row["evidence_id"]]["source"]["version_binding"] = "9.0"
    else:
        payload["answer_supported"] = True
    _refresh_estimate(payload)
    assert validate_model_visible_projection(payload, snapshot=snapshot)


def test_context_budget_uses_explicit_optional_output_limits():
    budget = ContextBudget()
    assert budget.max_sources is None and budget.max_tokens is None
    assert budget.bounded_tokens() is None
    assert budget.bounded_tokens(1200) == 1200
    assert ContextBudget(max_sources=None, max_tokens=None) == budget
    bounded = ContextBudget(max_sources=4, max_tokens=900)
    assert bounded.bounded_tokens(1200) == 900
    assert bounded.bounded_tokens() == 900
    for kwargs in ({"max_sources": 0}, {"max_tokens": 0}):
        with pytest.raises(ValueError):
            ContextBudget(**kwargs)
