"""Offline acquired-window retention controls; no retrieval or source reads."""
from dataclasses import dataclass, replace
import hashlib

from docmancer.docs.application import evidence_selection as selector
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.application._library_docs_service_shared import (
    _bounded_library_evidence_chunks, _postprocess_library_chunks,
)
from docmancer.docs.application._library_docs_service_part03 import _indexed_library_source


def _row(index, text):
    return {
        "stable_chunk_id": f"window-{index}", "parent_logical_id": f"document-{index}",
        "path": f"docs/contract-{index}.md", "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "char_start": 0, "char_end": len(text), "line_start": 1,
        "line_end": len(text.splitlines()), "retrieval_rank": index + 1,
    }


def test_long_mandatory_acquired_window_is_not_rejected_for_fit():
    text = "\n".join(
        f"route_{index:03d} = handler_{index:03d}; timeout_{index:03d} = {index + 1}"
        for index in range(100)
    ) + "\nException: route_099 must not retry an opted-out recipient."
    item = _row(0, text)
    requirements = EvidenceRequirementSet((EvidenceRequirement("source", "evidence_path", item["path"]),))
    decision = selector.select_evidence(
        [item], question="", config=selector.docs_selection_config(800), requirements=requirements,
    )
    assert decision.metrics["eligible_count"] == 1
    assert [candidate.display_text for candidate in decision.selected_candidates] == [text]
    assert not {"budget", "candidate_cap", "source_cap"} & {row.reason_code for row in decision.omissions}


def test_all_distinct_required_acquired_documents_survive_candidate_and_span_caps():
    items = [_row(index, f"route_{index} requires approval_{index} before deployment.") for index in range(27)]
    requirements = EvidenceRequirementSet(tuple(
        EvidenceRequirement(f"source-{index}", "evidence_path", item["path"])
        for index, item in enumerate(items)
    ))
    decision = selector.select_evidence(
        items, question="", config=selector.docs_selection_config(800), requirements=requirements,
    )
    assert decision.metrics["eligible_count"] == len(items)
    assert {candidate.stable_id for candidate in decision.selected_candidates} == {item["stable_chunk_id"] for item in items}
    assert decision.missing_requirements == ("unsupported_answer_authorization:context_only",)
    assert decision.status == "insufficient_evidence"
    assert len(decision.assignments) == len(items)
    for candidate in decision.selected_candidates:
        assignment = next(row for row in decision.assignments if row.evidence_id == candidate.evidence_id)
        requirement = next(row for row in requirements if row.requirement_id == assignment.requirement_id)
        assert selector.validate_assignment_binding(requirement, candidate, assignment)


def test_partial_mandatory_selection_keeps_large_bound_window_and_exact_gap():
    text = "\n".join(f"route_{index} = handler_{index}" for index in range(150))
    candidates, omissions = selector.normalize_candidates([_row(0, text)], result_kind="docs_answer")
    assert not omissions
    candidate = replace(candidates[0], covered_requirement_ids=frozenset({"present"}))
    selected, missing, omissions = selector._reserve_and_select(
        [candidate], {"present", "absent"}, selector.docs_selection_config(800),
    )
    assert selected == [candidate]
    assert missing == {"absent"}
    assert not omissions


@dataclass
class _Chunk:
    text: str
    source: str
    metadata: dict

    def model_copy(self, *, update):
        return replace(self, **update)


def test_library_large_original_window_keeps_real_indexed_carrier():
    text = "\n".join(f"route_{index} = handler_{index}" for index in range(150))
    digest = hashlib.sha256(text.encode()).hexdigest()
    metadata = {
        "stable_chunk_id": "child", "parent_logical_id": "parent",
        "source_identity": "origin", "source_content_hash": digest,
        "generation_id": "generation", "library_id": "library",
        "content_hash": digest, "char_span": [0, len(text)],
        "byte_span": [0, len(text.encode())], "line_span": [1, len(text.splitlines())],
        "resolved_version": "1", "docs_snapshot_exact": True,
    }
    chunk = _Chunk(text, "https://docs.example/contract", metadata)
    carrier = _indexed_library_source(chunk.source, text, metadata)
    assert carrier is not None
    kept, _ = _bounded_library_evidence_chunks(
        [chunk], requirements=EvidenceRequirementSet((EvidenceRequirement("source", "evidence_path", chunk.source),)),
        max_tokens=800,
    )
    assert kept == [chunk]
    assert kept[0] is chunk
    assert _indexed_library_source(kept[0].source, kept[0].text, kept[0].metadata) == carrier
    assert _indexed_library_source(chunk.source, text, dict(metadata, content_hash="0" * 64)) is None
    assert _indexed_library_source(chunk.source, text, dict(metadata, char_span=[0, len(text) - 1])) is None
    assert _indexed_library_source(chunk.source, text, dict(metadata, source_excerpt=True)) is None


def test_library_late_same_source_condition_is_not_a_diversity_drop():
    source = "https://docs.example/contract"
    chunks = [
        _Chunk("Delivery requires recipient consent.", source, {"stable_chunk_id": "consent"}),
        _Chunk("Delivery retries twice for temporary errors.", source, {"stable_chunk_id": "retry"}),
        _Chunk("Delivery must not retry when the recipient opts out.", source, {"stable_chunk_id": "exception"}),
        _Chunk("Delivery requires recipient consent.", "https://other.example/contract", {"stable_chunk_id": "other"}),
    ]
    kept, diagnostics = _postprocess_library_chunks(chunks, "delivery")
    assert {(chunk.source, chunk.metadata["stable_chunk_id"], chunk.text) for chunk in kept} == {
        (chunk.source, chunk.metadata["stable_chunk_id"], chunk.text) for chunk in chunks
    }
    assert diagnostics["chunks_dropped_for_diversity"] == 0


def test_docs_retention_preserves_hash_and_stale_rejections():
    valid = _row(0, "Delivery requires recipient consent.")
    requirements = EvidenceRequirementSet((EvidenceRequirement("source", "evidence_path", valid["path"]),))
    config = selector.docs_selection_config(800)
    baseline = selector.select_evidence([valid], question="", config=config, requirements=requirements)
    assert len(baseline.selected_candidates) == len(baseline.assignments) == 1
    for change, reason in (({"display_content_hash": "0" * 64}, "invalid_identity"), ({"freshness": "stale"}, "stale")):
        denied = selector.select_evidence([dict(valid, **change)], question="", config=config, requirements=requirements)
        assert not denied.selected_candidates
        assert not denied.assignments
        assert reason in {row.reason_code for row in denied.omissions}
