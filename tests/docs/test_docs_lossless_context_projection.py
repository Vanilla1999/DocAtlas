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

