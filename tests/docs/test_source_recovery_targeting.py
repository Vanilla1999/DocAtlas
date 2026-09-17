"""Read-only regression probes against existing recovery selection.

Production imports are real; only document bytes are provided by an in-memory
read gateway. These do not establish an end-to-end retrieval success rate.
"""
from copy import deepcopy
from hashlib import sha256

import pytest

from docmancer.docs.application.context_selection import visible_assignments
from docmancer.docs.application.source_continuation import (
    SourceContinuationReader, SourceReference, prepare_docs_context_read_next,
)
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens


class BytesGateway:
    def __init__(self, raw):
        self.raw = raw
        self.reads = 0

    def authorize(self, reference):
        return None

    def read_snapshot(self, reference):
        self.reads += 1
        return self.raw


def fixture(witness_line, *, selected):
    lines = [f"Background line {index}." for index in range(1, 101)]
    witness = "Only after the review completes may the operation proceed."
    lines[witness_line - 1] = witness
    text = "\n".join(lines) + "\n"
    source = {
        "stable_id": "source-1", "source_class": "project_doc",
        "path": "docs/operation.md", "project_identity": "project:fixture",
        "content": text, "line_start": 1, "line_end": 100,
        "authority": "source_of_truth", "doc_scope": "project",
        "_source_snapshot_sha256": "sha256:" + sha256(text.encode()).hexdigest(),
        "_source_catalog_hash": "sha256:" + sha256(b"catalog").hexdigest(),
    }
    start = text.index(witness)
    assignment = {
        "requirement_id": "missing-rule", "evidence_id": "source-1",
        "projected_content_hash": sha256(witness.encode()).hexdigest(),
        "unit_char_start": start, "unit_char_end": start + len(witness),
    }
    assert visible_assignments(source, {
        "snippet": text.rstrip("\n"), "line_start": 1, "line_end": 100,
    }, [assignment]) == (assignment,)
    projected = {
        "evidence_id": "visible-1", "path_or_url": source["path"],
        "snippet": "\n".join(lines[75:78]), "line_start": 76, "line_end": 78,
    }
    payload = {
        "kind": "docs_context", "context_quality": {
            "status": "partial", "reasons": ["requested_part_missing"],
        }, "sources": [projected] if selected else [{
            "evidence_id": "primary-other", "path_or_url": "docs/overview.md",
            "snippet": "The operation has a separate review rule.",
            "line_start": 1, "line_end": 1,
        }], "edit_ready": False,
    }
    snapshot = {"visible-1": {"source": source}} if selected else {}
    retrieval = {
        "context_pack": [source], "selection_decision": {"assignments": [assignment]},
        "documentation_query_plan": {"_component_coverage": {
            "missing_component_ids": ["missing-rule"],
        }},
        "retrieval_diagnostics": {"docs_context_projection": {"projection_rejections":
            [] if selected else [{
                "candidate_id": "source-1", "reason": "token_budget",
                "component_ids": ["missing-rule"],
            }],
        }},
    }
    return source, witness, payload, snapshot, retrieval


@pytest.mark.parametrize("witness_line,selected", [(76, False), (10, True)])
def test_read_next_targets_verified_missing_witness(witness_line, selected):
    source, witness, payload, snapshot, retrieval = fixture(witness_line, selected=selected)
    before = deepcopy((payload, snapshot, retrieval))
    target, bound = prepare_docs_context_read_next(payload, snapshot, retrieval, root="/repo")
    assert (payload, snapshot, retrieval) == before
    assert target is not None and bound is source
    gateway = BytesGateway(source["content"].encode())
    reader = SourceContinuationReader(gateway)
    reference = SourceReference(
        "/repo", source["project_identity"], source["path"],
        source["_source_snapshot_sha256"], source["_source_catalog_hash"],
        "source_of_truth", "project", None, 100,
    )
    uri = reader.issue_range(reference, line_start=target["line_start"],
                             line_end=target["line_end"], uri=target["source_uri"])
    assert uri and gateway.reads == 0
    result = reader.read(uri)
    assert result["status"] in {"complete", "truncated"}
    assert docs_context_budget_tokens(result) <= 600
    assert result["line_end"] - result["line_start"] + 1 <= 40
    assert witness in result["snippet"], (
        f"Known missing witness at line {witness_line}; "
        f"target={target['line_start']}..{target['line_end']}, "
        f"read={result['line_start']}..{result['line_end']}"
    )


def test_checked_packet_does_not_schedule_recovery():
    _, _, payload, snapshot, retrieval = fixture(76, selected=False)
    payload["context_quality"] = {"status": "checked", "reasons": []}
    assert prepare_docs_context_read_next(payload, snapshot, retrieval, root="/repo") == (None, None)


def test_verified_missing_ranges_uses_assignment_offsets():
    from docmancer.docs.application.source_recovery_ranges import verified_missing_ranges
    source, _, _, _, retrieval = fixture(76, selected=False)
    assignments = tuple(retrieval["selection_decision"]["assignments"])
    assert verified_missing_ranges(source, assignments, frozenset({"missing-rule"})) == (("missing-rule", 76, 76),)


@pytest.mark.parametrize("field,value", [
    ("evidence_id", "different-source"),
    ("projected_content_hash", "0" * 64),
    ("unit_char_start", True),
    ("unit_char_end", 10**9),
])
def test_invalid_assignment_is_not_a_targeted_witness(field, value):
    from docmancer.docs.application.source_recovery_ranges import verified_missing_ranges
    source, _, _, _, retrieval = fixture(76, selected=False)
    original = retrieval["selection_decision"]["assignments"][0]
    corrupted = {**original, field: value}
    assert verified_missing_ranges(source, (corrupted,), frozenset({"missing-rule"})) == ()


def test_repeated_text_uses_assignment_occurrence():
    from docmancer.docs.application.source_recovery_ranges import verified_missing_ranges
    source, witness, _, _, retrieval = fixture(76, selected=False)
    lines = source["content"].splitlines()
    lines[9] = witness
    text = "\n".join(lines) + "\n"
    source = {**source, "content": text, "_source_snapshot_sha256": "sha256:" + sha256(text.encode()).hexdigest()}
    start = text.rindex(witness)
    assignment = {**retrieval["selection_decision"]["assignments"][0], "unit_char_start": start, "unit_char_end": start + len(witness)}
    assert verified_missing_ranges(source, (assignment,), frozenset({"missing-rule"})) == (("missing-rule", 76, 76),)


def test_public_handler_registers_targeted_missing_witness_and_controller_reads_it():
    from docmancer.docs.interfaces.host_context import SourceReadController
    from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool

    witness = "Only after the review completes may the operation proceed."
    direct = "The export operation preserves original identifiers."
    lines = ["```python"]
    lines.extend(f"# background {index}" for index in range(1, 94))
    lines.append(witness)
    lines.extend(f"# background {index}" for index in range(95, 180))
    lines.append("```")
    long_source = "\n".join(lines)

    def candidate(path, content, query_id, stable_id):
        return {
            "stable_id": stable_id, "source_class": "project_doc", "path": path,
            "heading_path": "Recovery", "content": content,
            "project_identity": "project:recovery", "line_start": 1,
            "line_end": 1 + content.count("\n"), "authority": "source_of_truth",
            "doc_scope": "project", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
            "_source_snapshot_sha256": "sha256:" + sha256(content.encode()).hexdigest(),
            "_source_catalog_hash": "sha256:" + sha256(("catalog:" + path).encode()).hexdigest(),
            "retrieval_query_ids": [query_id],
            "retrieval_query_matches": {query_id: {
                "qualified": True, "mode": "and",
                "query_text": "export identifiers" if query_id == "query-original" else "complete runnable example",
            }},
        }

    direct_candidate = candidate("docs/direct.md", direct, "query-original", "direct")
    missing_candidate = candidate("docs/example.md", long_source, "query-example", "source-example")
    start = long_source.index(witness)
    assignment = {
        "requirement_id": "missing-rule", "evidence_id": "source-example",
        "projected_content_hash": sha256(witness.encode()).hexdigest(),
        "unit_char_start": start, "unit_char_end": start + len(witness),
    }
    raw = {
        "status": "success", "mode_selected": "project", "project_identity": "project:recovery",
        "context_pack": [direct_candidate, missing_candidate],
        "selection_decision": {"assignments": [assignment]},
        "documentation_query_plan": {
            "original_question": "How does export preserve identifiers and what review rule applies?",
            "query_ids": ["query-original", "query-example"],
            "required_query_ids": ["query-original", "query-example"],
            "public_query_ids": ["query-original", "query-example"],
            "queries": [
                {"query_id": "query-original", "text": "export identifiers", "origin": "original"},
                {"query_id": "query-example", "text": "complete runnable example", "origin": "host_lookup"},
            ],
            "_component_contract": [{"component_id": "missing-rule"}],
            "component_scope_complete": True,
        },
        "retrieval_diagnostics": {},
    }

    class MappingGateway:
        def __init__(self):
            self.reads = 0
            self.payloads = {"docs/direct.md": direct.encode(), "docs/example.md": long_source.encode()}
        def authorize(self, reference):
            return None
        def read_snapshot(self, reference):
            self.reads += 1
            return self.payloads[reference.path]

    class ContextApp:
        def __init__(self, retrieval, source_reader):
            self.raw = retrieval
            self.source_reader = source_reader
            self.unified_context = self
        def get_docs_context(self, *args, **kwargs):
            return deepcopy(self.raw)

    gateway = MappingGateway()
    reader = SourceContinuationReader(gateway)
    payload = handle_context_tool("get_docs_context", {
        "question": raw["documentation_query_plan"]["original_question"],
        "project_path": "/repo", "scope": "all",
    }, ContextApp(raw, reader))

    assert gateway.reads == 0
    assert payload["context_quality"]["status"] == "partial"
    assert len(payload["read_next"]) == 1
    target = payload["read_next"][0]
    assert target["path"] == "docs/example.md"
    assert target["line_start"] == target["line_end"] == 95
    assert target["reason"] == "requested_part_missing"
    assert docs_context_budget_tokens(payload) <= 800

    controller = SourceReadController(
        payload,
        requested_facts={"missing-rule": "What review rule applies to the operation?"},
        read_resource=reader.read,
    )
    accepted = controller.read(target["source_uri"], missing_fact_id="missing-rule")
    assert accepted["status"] in {"complete", "truncated"}
    assert witness in accepted["snippet"]
    assert gateway.reads == 1
