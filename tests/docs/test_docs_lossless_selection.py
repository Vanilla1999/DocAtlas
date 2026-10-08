"""Offline acquired-window retention controls; no retrieval or source reads."""
from dataclasses import dataclass, replace
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from time import monotonic
from types import SimpleNamespace

import pytest

from docmancer.docs.application import evidence_selection as selector
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.application._library_docs_service_shared import (
    _bounded_library_evidence_chunks, _clean_library_section, _postprocess_library_chunks,
)
from docmancer.docs.application._library_docs_service_part03 import _indexed_library_source
from docmancer.docs.application.library_docs_service import LibraryDocsApplicationService
from docmancer.docs.application._unified_context_service_part02 import _UnifiedDocsContextServicePart02
from docmancer.docs.domain.policies import is_stale
from docmancer.docs.registry import LibraryRecord


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
    assert not decision.support_decision.answer_supported
    assert len(decision.assignments) == len(items)
    for candidate in decision.selected_candidates:
        assignment = next(row for row in decision.assignments if row.evidence_id == candidate.stable_id)
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


def test_optional_selection_config_preserves_explicit_bounds_and_validation():
    for factory in (selector.docs_selection_config, selector.library_docs_selection_config, selector.project_docs_selection_config):
        config = factory(800)
        assert config.marginal_utility_threshold == 100
        for name in ("target_tokens", "hard_tokens", "max_candidates", "max_sources", "max_items_per_source", "max_documents", "max_spans", "wrapper_reserve_tokens"):
            assert getattr(config, name) is None
        for name in ("max_candidates", "max_sources", "max_items_per_source", "max_documents", "max_spans"):
            assert getattr(replace(config, **{name: 1}), name) == 1
            for value in (0, -1):
                with pytest.raises(ValueError):
                    replace(config, **{name: value})
        for change in ({"target_tokens": 1}, {"hard_tokens": 1}, {"target_tokens": 2, "hard_tokens": 1}, {"target_tokens": 0, "hard_tokens": 1}, {"marginal_utility_threshold": None}, {"result_kind": "other"}, {"profile": "other"}, {"near_duplicate_threshold": -1}, {"near_duplicate_threshold": 1001}):
            with pytest.raises(ValueError):
                replace(config, **change)
        assert replace(config, target_tokens=650, hard_tokens=800).hard_tokens == 800
    patch = selector.patch_selection_config()
    for name in ("target_tokens", "hard_tokens", "max_candidates", "max_sources", "max_items_per_source", "max_documents", "max_spans", "wrapper_reserve_tokens", "marginal_utility_threshold"):
        assert getattr(patch, name) is None
        with pytest.raises(ValueError):
            replace(patch, **{name: 1})

    candidates, omitted = selector.normalize_candidates([_row(0, "Consent is required before delivery.")], result_kind="docs_answer")
    assert not omitted
    mandatory = replace(candidates[0], covered_requirement_ids=frozenset({"present"}), fit_token_estimate=1000)
    bounded = replace(selector.docs_selection_config(800), target_tokens=650, hard_tokens=800)
    selected, missing, _ = selector._reserve_and_select([mandatory], {"present"}, bounded)
    assert selected == [] and "mandatory_evidence_does_not_fit" in missing
    source_candidates = [replace(candidates[0], stable_id=f"s-{index}", source_identity=f"source-{index}", covered_requirement_ids=frozenset(), token_estimate=1, fit_token_estimate=1) for index in range(2)]
    selected, _, omitted = selector._reserve_and_select(source_candidates, set(), replace(bounded, max_sources=1))
    assert len(selected) == 1 and any(row.reason_code == "source_cap" for row in omitted)
    items = [_row(index, f"Route {index} requires consent.") for index in range(2)]
    requirements = EvidenceRequirementSet(tuple(EvidenceRequirement(f"source-{index}", "evidence_path", row["path"]) for index, row in enumerate(items)))
    decision = selector.select_evidence(items, question="", config=replace(selector.docs_selection_config(800), max_documents=1, max_spans=1), requirements=requirements)
    assert len(decision.selected_candidates) == 2
    assert "bounded_evidence_not_materializable" in decision.missing_requirements


def test_mixed_large_bound_lanes_preserve_child_support_and_exact_gaps():
    def _make_lane(identity, missing=False):
        items = []
        for index in range(4):
            routes = ",".join(f'{{"route":"/{identity}/{index}/{route}","handler":"dispatch_{route}","timeout":{route + 1}}}' for route in range(24))
            text = f"const route_contract_{index} = '[{routes}]';"
            items.append(_row(index, text))
        requirements = EvidenceRequirementSet(tuple(EvidenceRequirement(f"fact-{index}", "required_fact", row["display_text"]) for index, row in enumerate(items)) + ((EvidenceRequirement("absent", "required_fact", "Unavailable regional deployment contract."),) if missing else ()))
        return selector.select_evidence(items, question="", config=selector.patch_selection_config(), requirements=requirements)

    project, library = _make_lane("project"), _make_lane("library")
    for child in (project, library):
        assert child.support_decision.answer_supported
        assert len(child.selected_candidates) == len(child.assignments) == 4
        assert not selector.validate_evidence_sufficiency(child, result_kind="patch_context")
    entries = [("project", "project-fixture", project), ("library", "library-fixture", library)]
    mixed = selector.aggregate_mixed_selection(entries)
    decision = mixed.selection_decision
    assert decision.support_decision.answer_supported
    assert len(decision.selected_candidates) == len(decision.assignments) == 8
    assert decision.metrics["selected_spans"] > 6
    assert decision.metrics["selected_documents"] > 3
    assert decision.metrics["projected_total_tokens"] > 800
    assert not decision.missing_requirements
    for lane in mixed.lanes:
        prefix = lane.qualifier + ":"
        for original in lane.decision.selected_candidates:
            retained = next(row for row in decision.selected_candidates if row.stable_id == prefix + original.stable_id)
            assert retained.display_text == original.display_text
            assert retained.content_sha256 == original.content_sha256
            assert retained.path_or_url == original.path_or_url
            assert (retained.char_start, retained.char_end) == (original.char_start, original.char_end)
        for original in lane.decision.assignments:
            assert replace(original, requirement_id=prefix + original.requirement_id, evidence_id=prefix + original.evidence_id) in decision.assignments
    assert len({row.stable_id for row in decision.selected_candidates}) == 8
    reversed_mixed = selector.aggregate_mixed_selection(reversed(entries))
    assert mixed.child_decision_hash == reversed_mixed.child_decision_hash
    assert mixed.child_assignment_hash == reversed_mixed.child_assignment_hash
    assert decision.selection_hash == reversed_mixed.selection_decision.selection_hash
    incomplete = _make_lane("library", missing=True)
    assert not incomplete.support_decision.answer_supported
    partial = selector.aggregate_mixed_selection([entries[0], ("library", "library-fixture", incomplete)])
    assert not partial.selection_decision.support_decision.answer_supported
    assert partial.selection_decision.support_decision.reason_code == "mixed_support_incomplete"
    assert len(partial.selection_decision.selected_candidates) == 8
    library_lane = next(row for row in partial.lanes if row.lane == "library")
    assert library_lane.qualifier + ":absent" in partial.selection_decision.missing_requirements
    assert partial.child_decision_hash != mixed.child_decision_hash
    assert partial.child_assignment_hash == mixed.child_assignment_hash
    context_item = _row(0, "Delivery requires consent.")
    context_requirements = EvidenceRequirementSet((EvidenceRequirement("source", "evidence_path", context_item["path"]),))
    context_only = selector.select_evidence([context_item], question="", config=selector.docs_selection_config(800), requirements=context_requirements)
    assert context_only.selected_candidates and context_only.assignments
    assert context_only.missing_requirements == ("unsupported_answer_authorization:context_only",)
    context_mixed = selector.aggregate_mixed_selection([entries[0], ("library", "context-fixture", context_only)])
    context_lane = next(row for row in context_mixed.lanes if row.lane == "library")
    assert not context_mixed.selection_decision.support_decision.answer_supported
    assert context_lane.qualifier + ":unsupported_answer_authorization:context_only" in context_mixed.selection_decision.missing_requirements


_LIBRARY_ROOT = "https://docs.example/library/1"


def _library_window(stable, text, *, source=None):
    source = source or _LIBRARY_ROOT + "/delivery"
    digest = hashlib.sha256(text.encode()).hexdigest()
    return _Chunk(text, source, {
        "stable_chunk_id": stable, "parent_logical_id": source,
        "source_identity": source, "source_content_hash": digest,
        "generation_id": "fixture-generation", "library_id": "fixture-library",
        "canonical_id": "fixture-library", "ecosystem": "fixture",
        "source_type": "web", "version": "1", "resolved_version": "1",
        "docs_snapshot_exact": True, "docset_root": _LIBRARY_ROOT,
        "content_hash": digest, "char_span": [0, len(text)],
        "byte_span": [0, len(text.encode())], "line_span": [1, len(text.splitlines())],
        "title": stable, "_indexed_source": {"forged_reserved_carrier": True},
    })


def _bind_library_fixture_pages(windows):
    """Fixture author binds each child to exact bytes of its finite full page."""
    for source in {row.source for row in windows}:
        children = [row for row in windows if row.source == source]
        page = "\n\n".join(row.text for row in children)
        prefix = ""
        for row in children:
            row.metadata.update({
                "source_content_hash": hashlib.sha256(page.encode()).hexdigest(),
                "char_span": [len(prefix), len(prefix) + len(row.text)],
                "byte_span": [len(prefix.encode()), len(prefix.encode()) + len(row.text.encode())],
                "line_span": [prefix.count("\n") + 1, prefix.count("\n") + len(row.text.splitlines())],
            })
            assert page[len(prefix):len(prefix) + len(row.text)] == row.text
            prefix += row.text + "\n\n"


def _public_library_fixture(tmp_path, windows, complete):
    """Deterministic acquisition ports; real get_docs, guards, witness and adapter."""
    trace = {"primary": [], "probe": [], "registry_reads": [], "manifest_checks": [], "queried_members": [], "source_reads": 0}
    now = datetime.now(timezone.utc).isoformat()
    record = LibraryRecord(
        library_id="fixture-library", source_id="fixture-source", canonical_id="fixture-library",
        name="fixture-library", normalized_name="fixture-library", ecosystem="fixture", version="1",
        source_type="web", docs_url=_LIBRARY_ROOT, docs_url_template=None, aliases=[],
        status="available", added_at=now, last_checked_at=now, last_refreshed_at=now, last_error=None,
        requested_version="1", resolved_version="1", version_source="explicit", version_confidence="high",
        version_inferred=False, docs_url_resolved=_LIBRARY_ROOT, docs_snapshot_exact=True,
        target_spec={"source_manifest": {"schema_version": 2, "complete": complete, "truncated": False}},
    )

    def registry_get(library, ecosystem=None, version=None, source_type=None):
        trace["registry_reads"].append([library, ecosystem, version, source_type])
        assert library == record.library_id
        assert version in (None, "1") and source_type in (None, "web")
        return record

    def forbidden(*args, **kwargs):
        raise AssertionError("fixture prohibits mutations, refresh, providers and source reads")

    def query_library(requested_record, query, *, budget, filters, requirements):
        assert requested_record == record
        trace["primary"].append({"query": query, "budget": budget, "filters": dict(filters), "requirements_hash": requirements.requirements_hash})
        trace["queried_members"].append([row.metadata["stable_chunk_id"] for row in windows])
        return SimpleNamespace(chunks=deepcopy(windows), mode_used="fixture-lexical", candidate_counts={"fixture": len(windows)}, failures={}, query_plan_hash="fixture")

    def probe_library_requirements(requested_record, requirements, *, missing_requirement_ids, filters):
        assert requested_record == record
        trace["probe"].append({"missing_ids": list(missing_requirement_ids), "filters": dict(filters), "requirements_hash": requirements.requirements_hash})
        # The complete finite fixture has no additional member to acquire.
        return SimpleNamespace(status="ok", queried_requirement_ids=tuple(missing_requirement_ids), chunks=[], failure_count=0)

    def count_index_entries(requested_record):
        assert requested_record == record
        trace["manifest_checks"].append("count_index_entries")
        return len({row.source for row in windows}), len(windows)

    def manifest_coverage(requested_record, pages):
        assert requested_record == record
        trace["manifest_checks"].append(["manifest_coverage", pages])
        expected = sorted({row.source for row in windows})
        return expected, list(expected), [], [], {}

    # Avoid lifecycle/job startup, not source or proof validation. The actual
    # public read method and all of its source/carrier/witness checks run below.
    service = object.__new__(LibraryDocsApplicationService)
    facade = SimpleNamespace(
        registry=SimpleNamespace(get=registry_get, upsert=forbidden),
        config=SimpleNamespace(retrieval=SimpleNamespace(default_mode="lexical")),
        agent_gateway=SimpleNamespace(query_library=query_library, probe_library_requirements=probe_library_requirements),
        stale_after_days=30, _is_stale=lambda timestamp: is_stale(timestamp, stale_after_days=30),
        _is_flutter_library=lambda library: False,
        _index_config_for=lambda requested_record: SimpleNamespace(index=SimpleNamespace(db_path=str(tmp_path / "absent-fixture-index.db"))),
        refresh_docs=forbidden,
    )
    service.facade = facade
    service.registry_ops = SimpleNamespace(count_index_entries=count_index_entries, manifest_coverage=manifest_coverage, index_size_for=lambda requested_record: sum(len(row.text.encode()) for row in windows))
    facade._resolve_docs_source = service.resolve_docs_source
    return service, trace


def _public_library_run(tmp_path, windows, complete):
    service, trace = _public_library_fixture(tmp_path, windows, complete)
    start = monotonic()
    result = service.get_docs("fixture-library", topic="Delivery contract deployment_region", version="1", ecosystem="fixture", source_type="web")
    trace["elapsed_seconds"] = monotonic() - start
    adapted = _UnifiedDocsContextServicePart02._library_context_pack(None, result)
    return result, adapted, trace


@pytest.mark.parametrize("complete,batch", [(False, "single"), (True, "single"), (False, "mixed"), (True, "mixed")], ids=["incomplete-single", "complete-single", "incomplete-mixed", "complete-mixed"])
def test_public_library_retention_carrier_and_finite_acquisition_trace(tmp_path, record_property, complete, batch):
    long = "Delivery contract [¶]\n" + "\n".join(f"route_{index} = handler_{index}; timeout_{index} = {index + 1}" for index in range(100)) + "\nDelivery must not retry an opted-out recipient."
    windows = [_library_window("long", long)]
    if batch == "mixed":
        windows += [
            _library_window("consent", "Delivery requires recipient consent."),
            _library_window("retry", "Delivery retries twice for temporary errors."),
            _library_window("exception", "Delivery must not retry when the recipient opts out."),
            _library_window("other", "Delivery requires recipient consent.", source=_LIBRARY_ROOT + "/other"),
        ]
    _bind_library_fixture_pages(windows)
    result, adapted, trace = _public_library_run(tmp_path, windows, complete)
    record_property("library_acquisition_trace", json.dumps(trace, sort_keys=True))
    assert len(trace["primary"]) == 1
    assert trace["primary"][0]["query"] == "Delivery contract deployment_region"
    assert trace["primary"][0]["budget"] == 4000
    assert trace["primary"][0]["filters"] == {"library_id": "fixture-library", "resolved_version": "1", "exact_snapshot_required": True}
    assert trace["source_reads"] == 0
    assert trace["queried_members"] == [[row.metadata["stable_chunk_id"] for row in windows]]
    assert len(trace["probe"]) == int(complete)
    assert bool(any(isinstance(row, list) and row[0] == "manifest_coverage" for row in trace["manifest_checks"])) == complete
    assert len(result.results) == len(adapted) == len(windows)
    assert not result.support_decision.answer_supported
    missing_region_ids = {row.requirement_id for row in result.selection_decision.requirements if row.value == "deployment_region"}
    assert missing_region_ids
    assert missing_region_ids <= set(result.support_decision.missing_requirement_ids)
    for original in windows:
        retained = next(row for row in result.results if row.metadata["stable_chunk_id"] == original.metadata["stable_chunk_id"])
        carrier = retained.metadata["_indexed_source"]
        assert "forged_reserved_carrier" not in carrier
        assert carrier == _indexed_library_source(original.source, original.text, original.metadata)
        row = next(row for row in adapted if row["stable_chunk_id"] == original.metadata["stable_chunk_id"])
        assert row["display_text"] == original.text
        assert row["display_content_hash"] == original.metadata["content_hash"]
        assert row["source"] == original.source
        assert (row["char_start"], row["char_end"]) == tuple(original.metadata["char_span"])
        assert (row["byte_start"], row["byte_end"]) == tuple(original.metadata["byte_span"])
        assert (row["line_start"], row["line_end"]) == tuple(original.metadata["line_span"])
    retained_long = next(row for row in result.results if row.metadata["stable_chunk_id"] == "long")
    assert retained_long.content == _clean_library_section(long)
    assert "[¶]" not in retained_long.content


@pytest.mark.parametrize("attack", ["digest", "span", "excerpt", "duplicate", "source", "reserved_carrier_source"], ids=["digest", "span", "excerpt", "duplicate", "source", "reserved-carrier-source"])
def test_public_library_carrier_negatives_have_bound_positive(tmp_path, attack):
    original = _library_window("target", "Delivery requires recipient consent.")
    companion = _library_window("companion", "Delivery retries twice for temporary errors.", source=_LIBRARY_ROOT + "/companion")
    _bind_library_fixture_pages([original, companion])
    result, adapted, _ = _public_library_run(tmp_path, [original, companion], False)
    assert {row["stable_chunk_id"] for row in adapted} == {"target", "companion"}
    assert result.results and result.results[0].metadata.get("_indexed_source")
    if attack == "reserved_carrier_source":
        target = next(row for row in result.results if row.metadata["stable_chunk_id"] == "target")
        target.metadata["_indexed_source"]["source"] = _LIBRARY_ROOT + "/forged"
        denied = _UnifiedDocsContextServicePart02._library_context_pack(None, result)
    else:
        invalid = deepcopy(original)
        if attack == "digest":
            invalid.metadata["content_hash"] = "0" * 64
        elif attack == "span":
            invalid.metadata["char_span"][1] -= 1
        elif attack == "excerpt":
            invalid.metadata["source_excerpt"] = True
        elif attack == "source":
            invalid.source = "https://foreign.example/contract"
        windows = [invalid, companion]
        if attack == "duplicate":
            windows.insert(0, deepcopy(original))
        _, denied, _ = _public_library_run(tmp_path, windows, False)
    assert {row["stable_chunk_id"] for row in denied} == {"companion"}
