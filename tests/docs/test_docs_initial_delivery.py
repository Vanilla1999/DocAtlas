"""Lower-layer canonical delivery controls, not public retrieval or real stdio."""
from copy import deepcopy
import hashlib
import json

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application._model_visible_docs_support import _docs_source, _snapshot_entry, _source_digest
from docmancer.docs.application.context_selection import context_selection_decision
from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import (
    _refresh_estimate, canonical_projection_bytes, docs_context_budget_tokens,
    project_docs_answer, validate_model_visible_projection,
)
from docmancer.docs.application.reference_query_tagging import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.interfaces.host_context import EvidenceDeliveryError, SourceReadController, extract_tool_payload
from docmancer.docs.interfaces.mcp.output_contract import compact_mcp_payload
from eval.task_level.one_call_agent_loop import validate_docatlas_result


QUESTION = "protocol validation rules"


def original(text, index):
    return {
        "path": f"docs/protocol-{index}.md", "source_class": "project_doc",
        "heading_path": f"Protocol {index} validation rules", "content": text,
        "snippet": text, "display_text": text, "project_identity": "offline-protocols",
        "authority": "source_of_truth", "doc_scope": "project", "version": "4.0",
        "lifecycle_status": "active", "freshness": "current", "index_freshness": "synchronized",
        "stable_chunk_id": f"protocol-{index}", "parent_logical_id": f"parent-{index}",
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "char_start": 0, "char_end": len(text), "line_start": 1, "line_end": len(text.splitlines()),
    }


def small_context():
    raw = original("Protocol validation rules require exact field bindings.", 0)
    payload, snapshot = project_docs_context(retrieval={
        "context_pack": [raw], "project_identity": raw["project_identity"],
        "documentation_query_plan": build_documentation_query_plan(QUESTION).as_payload(),
    })
    assert payload["sources"] and payload["context_available"]
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert validate_docatlas_result(payload) == []
    return payload


def large_context(kind="docs_context"):
    """Materialize admitted in-memory sources without the held selector/projector.

    Actual literal qualification and canonical source/snapshot helpers are used;
    this does not certify server acquisition or the capped full projection path.
    """
    small_context()
    plan = build_documentation_query_plan(QUESTION)
    lookup = plan.queries[0]
    rows, snapshot = [], {}
    for index in range(4):
        lines = [f"Protocol {index} validation rules:", "```python", f"def validate_protocol_{index}(record):"]
        for field in range(100):
            lines.extend([
                f'    if record["binding_{index}_{field}"] != "protocol-{index}-value-{field}":',
                f'        raise ValueError("protocol {index}: invalid binding {field}")',
            ])
        lines.extend([f'    return record["binding_{index}_99"]', "```"])
        text = "\n".join(lines)
        raw = original(text, index)
        chunk = RetrievedChunk(source=raw["path"], chunk_index=0, text=text, score=1, metadata=raw)
        tagged = _tag_retrieval_query([chunk], lookup.query_id, lookup.text, lookup=lookup,
                                      expected_project_identity=raw["project_identity"])[0]
        raw = dict(tagged.metadata)
        assert raw["retrieval_query_matches"][lookup.query_id]["qualified"] is True
        row = _docs_source(raw)
        assert row is not None and row["snippet"] == text
        assert row["content_sha256"] == _source_digest(raw)
        if kind == "docs_context":
            row.update(project_identity=raw["project_identity"], authority=raw["authority"],
                       scope=raw["doc_scope"], line_start=raw["line_start"], line_end=raw["line_end"])
        snapshot[row["evidence_id"]] = _snapshot_entry(raw, row)
        rows.append({**row, "retrieval_query_matches": raw["retrieval_query_matches"],
                     "retrieval_query_ids": raw["retrieval_query_ids"]})
    if kind == "docs_context":
        decision = context_selection_decision(rows, (lookup.query_id,))
        payload = _payload(rows, decision=decision, query_plan=plan.as_payload())
    else:
        payload, _ = project_docs_answer(question=QUESTION, retrieval={
            "context_pack": [original("Protocol validation rules require exact bindings.", 0)],
        })
        assert payload["sources"]
        payload["sources"] = [snapshot[row["evidence_id"]]["projected_source"] for row in rows]
        _refresh_estimate(payload)
    assert len(payload["sources"]) == 4
    assert len({row["path_or_url"] for row in payload["sources"]}) == 4
    assert len(canonical_projection_bytes(payload)) > 32_000
    assert docs_context_budget_tokens(payload) > 800
    for row in payload["sources"]:
        bound = snapshot[row["evidence_id"]]
        assert row == bound["projected_source"]
        assert row["snippet"] == bound["source"]["content"]
        assert row["content_sha256"] == _source_digest(bound["source"])
    return payload


@pytest.mark.parametrize("kind", ["docs_answer", "docs_context"], ids=["answer", "context"])
@pytest.mark.parametrize("fallback", [False, True], ids=["structured", "text"])
def test_large_canonical_docs_reach_terminal_channel_unchanged(kind, fallback):
    import mcp.types as types
    from docmancer.mcp.docs_server import _mcp_tool_result
    payload = large_context(kind)
    before = deepcopy(payload)
    assert compact_mcp_payload(payload) is payload
    wire = _mcp_tool_result(types, payload, text_fallback=fallback)
    assert extract_tool_payload(wire, structured_supported=not fallback) == before
    assert payload == before
    assert 'return record["binding_3_99"]' in payload["sources"][-1]["snippet"]
    if fallback:
        assert wire.structuredContent is None
    else:
        assert wire.structuredContent == payload
        assert wire.content[0].text == "Structured DocAtlas result attached in structuredContent."


def test_large_initial_docs_pass_host_validation_without_automatic_reads():
    payload = large_context()
    assert validate_docatlas_result(payload) == []
    calls = []
    controller = SourceReadController(payload, requested_facts={"remaining": "Which rule follows?"},
                                      read_resource=lambda uri: calls.append(uri))
    assert calls == [] and controller.results == []
    assert controller.read("docatlas://source/" + "a" * 24, missing_fact_id="remaining")["reason_code"] == "unknown_or_repeated_source"
    assert calls == []


@pytest.mark.parametrize("change,message", [
    ("answer_supported", "cannot certify"), ("answer_available", "cannot certify"),
    ("edit_ready", "cannot certify"), ("answer_policy", "cite_only"),
    ("estimate", "estimated_tokens"), ("bool_estimate", "estimated_tokens"),
    ("hash", "content_sha256"), ("duplicate", "duplicate evidence_id"),
    ("empty_text", "attributed source text"), ("unknown", "unexpected"),
], ids=["answer_supported", "answer_available", "edit_ready", "answer_policy", "estimate",
        "bool_estimate", "hash", "duplicate", "empty_text", "unknown"])
def test_initial_host_security_checks_remain_field_specific(change, message):
    payload = large_context()
    if change in {"answer_supported", "answer_available", "edit_ready"}:
        payload[change] = True
    elif change == "answer_policy":
        payload[change] = "generate"
    elif change == "hash":
        payload["sources"][0]["content_sha256"] = "not-a-hash"
    elif change == "duplicate":
        payload["sources"].append(deepcopy(payload["sources"][0]))
    elif change == "empty_text":
        payload["sources"][0]["snippet"] = ""
    elif change == "unknown":
        payload["allow_edit"] = True
    _refresh_estimate(payload)
    if change == "estimate":
        payload["estimated_tokens"] += 1
    elif change == "bool_estimate":
        payload["estimated_tokens"] = True
    assert any(message in error for error in validate_docatlas_result(payload))


def read_context():
    payload = large_context()
    target = {"source_uri": "docatlas://source/" + "a" * 24,
              "path": payload["sources"][0]["path_or_url"], "project_identity": "offline-protocols",
              "snapshot_sha256": "sha256:" + "f" * 64,
              "line_start": 300, "line_end": 350, "reason": "inspect_source_context"}
    payload["read_next"] = [target]
    _refresh_estimate(payload)
    return payload, target


def read_result(target):
    return {"status": "truncated", "path": target["path"], "project_identity": target["project_identity"],
            "content_sha256": target["snapshot_sha256"], "line_start": 300, "line_end": 300,
            "snippet": "The next rule requires an independent signed binding.",
            "continuation": "docatlas://source/" + "b" * 24}


@pytest.mark.parametrize("change,reason", [
    ("oversize", "invalid_or_oversized_read"), ("gap", "source_binding_mismatch"),
    ("span", "source_binding_mismatch"), ("hash", "source_binding_mismatch"),
    ("path", "source_binding_mismatch"), ("project", "source_binding_mismatch"),
    ("overlap", "repeated_source_span"), ("text", "no_new_source_text"),
], ids=["oversize", "gap", "span", "hash", "path", "project", "overlap", "text"])
def test_large_initial_context_preserves_continuation_guards(change, reason):
    payload, target = read_context()
    valid = read_result(target)
    accepted = SourceReadController(payload, requested_facts={"rule": "Which rule follows?"}, read_resource=lambda _: valid)
    assert accepted.read(target["source_uri"], missing_fact_id="rule")["status"] == "truncated"
    broken = deepcopy(valid)
    if change == "oversize":
        broken["snippet"] = "\n".join(f"Additional rule {index} requires its own bound digest." for index in range(100))
        assert docs_context_budget_tokens(broken) > 600
    elif change == "gap":
        broken.update(line_start=301, line_end=301)
    elif change == "span":
        broken["line_end"] = 340
    elif change == "hash":
        broken["content_sha256"] = "sha256:" + "0" * 64
    elif change == "path":
        broken["path"] = "docs/foreign.md"
    elif change == "project":
        broken["project_identity"] = "foreign"
    elif change == "overlap":
        payload["sources"][0].update(line_start=300, line_end=300)
    else:
        broken["snippet"] = payload["sources"][0]["snippet"][:100]
        payload["sources"][0]["snippet"] = broken["snippet"]
    calls = []
    controller = SourceReadController(payload, requested_facts={"rule": "Which rule follows?"},
                                      read_resource=lambda uri: calls.append(uri) or broken)
    assert controller.read(target["source_uri"], missing_fact_id="rule")["reason_code"] == reason
    assert calls == [target["source_uri"]] and controller.results == []


def test_large_initial_context_keeps_two_attempts_and_requested_fact_limits():
    payload, target = read_context()
    calls = []
    def read(uri):
        calls.append(uri)
        result = read_result(target)
        if len(calls) == 2:
            result.update(line_start=301, line_end=301, snippet="A separate retry condition requires a new signature.",
                          continuation="docatlas://source/" + "c" * 24)
        return result
    controller = SourceReadController(payload, requested_facts={"rule": "Which rule follows?"}, read_resource=read)
    assert controller.read("docatlas://source/" + "d" * 24, missing_fact_id="rule")["reason_code"] == "unknown_or_repeated_source"
    assert calls == []
    first = controller.read(target["source_uri"], missing_fact_id="rule")
    assert controller.read(target["source_uri"], missing_fact_id="rule")["reason_code"] == "unknown_or_repeated_source"
    second = controller.read(first["continuation"], missing_fact_id="rule")
    assert controller.read(second["continuation"], missing_fact_id="rule")["reason_code"] == "read_budget_exhausted"
    assert len(calls) == 2 and len(controller.results) == 2 and controller.extra_tokens <= 1200
    for facts in ({str(i): "Next rule" for i in range(4)}, {"rule": ""}, {"rule": "q" * 501}):
        with pytest.raises(ValueError, match="requested facts"):
            SourceReadController(payload, requested_facts=facts, read_resource=read)
    with pytest.raises(ValueError):
        SourceReadController({**payload, "kind": "docs_answer"}, requested_facts={"rule": "Next rule"}, read_resource=read)
    assert len(calls) == 2


@pytest.mark.parametrize("change", ["error", "error_type", "malformed", "multiple", "conflict", "unsupported"])
def test_channel_security_rejects_invalid_delivery(change):
    payload = small_context()
    wire = {"structuredContent": payload, "content": [{"type": "text", "text": json.dumps(payload)}]}
    assert extract_tool_payload(wire) == payload
    if change == "error":
        wire["isError"] = True
    elif change == "error_type":
        wire["isError"] = 1
    elif change == "malformed":
        wire["structuredContent"] = []
    elif change == "multiple":
        wire["content"] *= 2
    elif change == "conflict":
        wire["content"][0]["text"] = json.dumps({**payload, "answer_supported": True})
    reason = {
        "error": "error_tool_result", "error_type": "invalid_tool_error_flag",
        "malformed": "malformed_structured_evidence", "multiple": "missing_or_ambiguous_evidence_channel",
        "conflict": "conflicting_evidence_channels", "unsupported": "structured_evidence_unsupported",
    }[change]
    with pytest.raises(EvidenceDeliveryError, match=reason):
        extract_tool_payload(wire, structured_supported=change != "unsupported")
