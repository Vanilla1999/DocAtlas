"""In-memory answer projection/binding controls; no public acquisition claims."""
from copy import deepcopy
from dataclasses import replace
import hashlib

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.evidence_selection import (
    docs_selection_config, library_docs_selection_config, project_docs_selection_config, select_evidence,
)
from docmancer.docs.application.model_visible_projection import (
    _refresh_estimate, _source_digest, estimate_projection_tokens,
    project_docs_answer, validate_model_visible_projection,
)
from docmancer.docs.application.reference_query_tagging import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


QUESTION = "protocol validation rules"
CONFIGS = {"generic": docs_selection_config, "project_docs_answer": project_docs_selection_config,
           "library_docs_answer": library_docs_selection_config}


def admitted_rows(*, large=False):
    plan = build_documentation_query_plan(QUESTION)
    lookup = plan.queries[0]
    rows = []
    for index in range(4 if large else 1):
        if large:
            lines = [f"Protocol {index} validation rules:", "```python", f"def validate_protocol_{index}(record):"]
            for field in range(100):
                lines.extend([
                    f'    if record["binding_{index}_{field}"] != "protocol-{index}-value-{field}":',
                    f'        raise ValueError("protocol {index}: invalid binding {field}")',
                ])
            lines.extend([f'    return record["binding_{index}_99"]', "```"])
            text = "\n".join(lines)
        else:
            text = "Protocol validation rules require exact field bindings."
        row = {
            "path": f"docs/protocol-{index}.md", "source_class": "project_doc",
            "heading_path": f"Protocol {index} validation rules", "content": text,
            "snippet": text, "display_text": text, "project_identity": "offline-protocols",
            "module_id": "protocol-module", "authority": "source_of_truth", "doc_scope": "project",
            "version": "4.0", "resolved_version": "4.0", "docs_exactness": "exact_version",
            "lifecycle_status": "active", "freshness": "current", "index_freshness": "synchronized",
            "stable_chunk_id": f"protocol-{index}", "parent_logical_id": f"parent-{index}",
            "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
            "char_start": 0, "char_end": len(text), "line_start": 1, "line_end": len(text.splitlines()),
        }
        chunk = RetrievedChunk(source=row["path"], chunk_index=0, text=text, score=1, metadata=row)
        tagged = _tag_retrieval_query([chunk], lookup.query_id, lookup.text, lookup=lookup,
                                      expected_project_identity=row["project_identity"])[0]
        assert tagged.metadata["retrieval_query_matches"][lookup.query_id]["qualified"] is True
        rows.append(dict(tagged.metadata))
    return rows


def selected(rows, profile="generic"):
    retrieval = {
        "status": "success", "context_pack": rows, "selection_profile": profile,
        "project_identity": "offline-protocols", "module_id": "protocol-module",
        "requested_version": "4.0", "docs_exactness": "exact_version",
        "required_evidence_paths": [row["path"] for row in rows],
    }
    decision = select_evidence(rows, question=QUESTION, config=CONFIGS[profile](800),
                               project_identity=retrieval["project_identity"], module_id=retrieval["module_id"],
                               exact_version="4.0", required_evidence_paths=retrieval["required_evidence_paths"])
    assert {candidate.path_or_url for candidate in decision.selected_candidates} == set(retrieval["required_evidence_paths"])
    return retrieval, decision


def small_projection(profile="generic"):
    retrieval, decision = selected(admitted_rows(), profile)
    payload, snapshot = project_docs_answer(question=QUESTION, retrieval=retrieval, canonical_selection=decision)
    assert payload["sources"] and snapshot
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert payload["sources"][0]["snippet"] == retrieval["context_pack"][0]["content"]
    return payload, snapshot


@pytest.mark.parametrize("profile", list(CONFIGS))
@pytest.mark.parametrize("budget", [1, 800], ids=["legacy-one", "legacy-800"])
def test_large_answer_retains_four_distinct_sources_and_late_facts(profile, budget):
    small_projection(profile)
    rows = admitted_rows(large=True)
    retrieval, decision = selected(rows, profile)
    before = deepcopy(rows)
    payload, snapshot = project_docs_answer(question=QUESTION, retrieval=retrieval, canonical_selection=decision,
                                           max_tokens=budget)
    assert payload["kind"] == "docs_answer" and len(payload["sources"]) == 4
    assert payload["estimated_tokens"] > 800
    assert {row["snippet"] for row in payload["sources"]} == {row["content"] for row in rows}
    assert {row["path_or_url"] for row in payload["sources"]} == set(retrieval["required_evidence_paths"])
    assert any('return record["binding_3_99"]' in row["snippet"] for row in payload["sources"])
    assert set(snapshot) == {row["evidence_id"] for row in payload["sources"]}
    for row in payload["sources"]:
        bound = snapshot[row["evidence_id"]]
        assert row == bound["projected_source"]
        assert row["content_sha256"] == _source_digest(bound["source"])
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert payload["estimated_tokens"] == estimate_projection_tokens(payload)
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=budget) == []
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []
    assert rows == before


@pytest.mark.parametrize("budget", [None, 1, 800], ids=["omitted", "legacy-one", "legacy-800"])
def test_validator_accepts_optional_budget_without_estimate_ceiling(budget):
    payload, snapshot = small_projection()
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=budget) == []


@pytest.mark.parametrize("change,message", [
    ("text", "source snippet does not match"), ("hash", "source hash does not match"),
    ("raw_crop", "internal snapshot hash does not match"), ("raw_digest", "internal snapshot hash does not match"),
    ("unbound", "evidence_id does not resolve"), ("missing_field", "source field is missing"),
    ("unknown_field", "source contains unknown fields"), ("estimate", "estimate mismatch"),
    ("bool_estimate", "estimate mismatch"), ("kind", "invalid projection kind"),
    ("status", "invalid projection status"), ("edit_ready", "must not authorize edits"),
    ("answer_supported", "must not authorize answers or edits"),
    ("answer_available", "must not authorize answers or edits"),
], ids=["text", "hash", "raw_crop", "raw_digest", "unbound", "missing_field", "unknown_field", "estimate",
        "bool_estimate", "kind", "status", "edit_ready", "answer_supported", "answer_available"])
def test_projection_forgeries_reach_existing_binding_guards(change, message):
    payload, snapshot = small_projection()
    row = payload["sources"][0]
    bound = snapshot[row["evidence_id"]]
    if change == "text":
        row["snippet"] = "Forged source bytes."
    elif change == "hash":
        row["content_sha256"] = "0" * 64
    elif change == "raw_crop":
        bound["source"]["content"] = bound["source"]["content"][:8]
    elif change == "raw_digest":
        bound["source"]["snippet"] = "Different bound quote."
    elif change == "unbound":
        row["evidence_id"] = "ev-not-issued"
    elif change == "missing_field":
        row.pop("version_binding")
    elif change == "unknown_field":
        row["allow_edit"] = True
    elif change in {"kind", "status"}:
        payload[change] = "forged"
    elif change in {"edit_ready", "answer_supported", "answer_available"}:
        payload[change] = True
    _refresh_estimate(payload)
    if change == "estimate":
        payload["estimated_tokens"] += 1
    elif change == "bool_estimate":
        payload["estimated_tokens"] = True
    errors = validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)
    assert any(message in error for error in errors), errors


@pytest.mark.parametrize("field,value", [
    ("freshness", "stale"), ("index_freshness", "stale"), ("lifecycle_status", "deprecated"),
    ("project_identity", "foreign"), ("module_id", "foreign"), ("resolved_version", "9.0"),
    ("path", "docs/foreign.md"), ("display_content_hash", "0" * 64),
], ids=["stale", "unsynchronized", "lifecycle", "project", "module", "version", "path", "hash"])
def test_cached_selection_rechecks_current_technical_scope(field, value):
    small_projection()
    retrieval, decision = selected(admitted_rows())
    candidate = decision.selected_candidates[0]
    cached = replace(decision, selected_candidates=(replace(candidate, original={**candidate.original, field: value}),))
    payload, snapshot = project_docs_answer(question=QUESTION, retrieval=retrieval, canonical_selection=cached)
    assert not payload.get("sources") and not snapshot
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("change", ["confirmation", "delivery_block", "question_limit", "malformed_requirements"])
def test_operational_vetoes_and_request_limits_remain_fail_closed(change):
    small_projection()
    retrieval, decision = selected(admitted_rows())
    question = QUESTION
    if change == "confirmation":
        retrieval.update(requires_confirmation=True, status="confirmation_required")
    elif change == "delivery_block":
        retrieval["delivery_decision"] = {"deliverable": False, "reason_code": "catalog_invalid"}
    elif change == "question_limit":
        question = "q" * 4_001
    else:
        retrieval["requirements"] = {"unexpected": "malformed contract"}
    payload, snapshot = project_docs_answer(question=question, retrieval=retrieval, canonical_selection=decision)
    assert not payload.get("sources") and not snapshot
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("change", ["span", "locator"])
def test_context_validation_keeps_existing_span_and_locator_binding(change):
    rows = admitted_rows()
    payload, snapshot = project_docs_context(retrieval={
        "context_pack": rows, "project_identity": "offline-protocols",
        "documentation_query_plan": build_documentation_query_plan(QUESTION).as_payload(),
    })
    assert payload["sources"] and validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    row = payload["sources"][0]
    if change == "span":
        row["line_end"] += 1
        message = "source line_end does not match"
    else:
        row["source_uri"] = "docatlas://source/" + "a" * 24
        message = "source locator does not match"
    _refresh_estimate(payload)
    errors = validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)
    assert any(message in error for error in errors), errors
