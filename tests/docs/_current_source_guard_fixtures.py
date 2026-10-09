"""Authored fixture members and literal source oracles for boundary controls.

Setup uses the real public call and confirmed member transaction. Optional
lookups are explicit test inputs; they never replace the original question or
receive its coverage credit. Source bytes and public ranges remain independent
of internal semantic/answer labels.
"""
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.project_context_quality.capture_public_context import capture_public_call
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection


def capture_source_case(tmp_path, documents, question, *, lookups=(), scope="project"):
    project = tmp_path / "project"
    # write_project accepts this finite authored map, never discovered repo files.
    write_project(project, documents)
    request = {"project_path": str(project), "scope": scope, "question": question}
    if lookups:
        request["lookup_queries"] = list(lookups)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, project)
        capture = capture_public_call(service, request)
    assert capture["request"] == request
    capture["fixture_project"] = project
    assert_read_only_source_bytes(capture, documents)
    return capture


def assert_read_only_source_bytes(capture, documents):
    payload = capture["public_payload"]
    assert payload.get("kind") == "docs_context", payload
    assert all(payload.get(key) is False for key in (
        "answer_supported", "answer_available", "edit_ready")), payload
    for source in payload.get("sources") or ():
        assert source["path_or_url"] in documents
        raw = documents[source["path_or_url"]]
        start, end = source["line_start"], source["line_end"]
        assert type(start) is int and type(end) is int
        assert 1 <= start <= end <= len(raw.splitlines())
        assert source["snippet"] and source["snippet"] in "\n".join(raw.splitlines()[start - 1:end])
    # No fixed output-cost ceiling. Fidelity and authorization remain mandatory.
    for attempt in capture.get("projection_attempts") or ():
        assert validate_model_visible_projection(
            attempt["projected_payload"], snapshot=attempt["snapshot"], max_tokens=None,
        ) == []


def source_contains_fact(source, path, fact):
    """An original-input oracle over the returned visible row, never raw metadata."""
    return (source.get("path_or_url") == path
            and isinstance(source.get("snippet"), str) and fact in source["snippet"])


def assert_visible_fact(capture, path, fact):
    payload = capture["public_payload"]
    assert payload.get("status") == "ok" and payload.get("context_available") is True, payload
    assert payload.get("support_status") == "retrieval_only", payload
    rows = payload.get("sources") or ()
    assert any(source_contains_fact(row, path, fact) for row in rows), {
        "request": capture["request"], "expected_path": path, "expected_fact": fact,
        "response": capture["public_payload"],
    }


def source_binding(capture, path, fact):
    """Return an actual public source and its exact same-call private binding."""
    assert_visible_fact(capture, path, fact)
    attempts = capture.get("projection_attempts") or ()
    assert attempts, "A positive source guard requires a real public projection"
    for visible in capture["public_payload"].get("sources") or ():
        if not source_contains_fact(visible, path, fact):
            continue
        # The facade may register a capability after projection. Every other
        # visible identity, hash, byte/range and attribution field must match.
        delivered = {key: value for key, value in visible.items() if key != "source_uri"}
        for attempt in reversed(attempts):
            for row in attempt["projected_payload"].get("sources") or ():
                if {key: value for key, value in row.items() if key != "source_uri"} != delivered:
                    continue
                entry = attempt["snapshot"][row["evidence_id"]]
                bound = {key: value for key, value in entry["projected_source"].items() if key != "source_uri"}
                if bound == delivered:
                    return visible, entry["source"], attempt
    raise AssertionError("Delivered fact is not bound to the observed public projection")


def canonical_range(public, original, start, end, *, supplementary=True):
    """Exercise canonical range construction on a real prepared source binding."""
    from docmancer.core.structured_chunking import parse_markdown_parents
    from docmancer.docs.application.joint_context_candidates import _verified_document, _context_row
    raw = _verified_document(original, public)
    if raw is None:
        return None
    parents = parse_markdown_parents(raw, original["_reference_evidence"]["source"]["document_id"])
    parent = next((p for p in parents if p.char_start <= start < p.char_end), None)
    if parent is None:
        return None
    return _context_row(original, public, raw, parent, start, end, supplementary=supplementary)
