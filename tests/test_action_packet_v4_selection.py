"""Offline v4 selection contract tests; no provider or corpus access."""
from dataclasses import asdict, replace
import hashlib
import inspect
from pathlib import Path

import pytest

from docmancer.docs.application import evidence_selection as selector
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.domain.answer_units import extract_answer_units


def row(index, text=None, **overrides):
    text = text or f"const setting_{index} = 'value_{index}';"
    item = {
        "stable_chunk_id": f"child-{index}",
        "parent_logical_id": "shared-parent",
        "path": f"src/config_{index}.py",
        "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "char_start": 100,
        "char_end": 100 + len(text),
        "line_start": 3,
        "line_end": 3 + text.count("\n"),
        "retrieval_rank": index + 1,
        "score": 0.8,
    }
    item.update(overrides)
    return item


def select(items, **kwargs):
    return selector.select_evidence(
        items, question=kwargs.pop("question", ""),
        config=selector.patch_selection_config(), **kwargs,
    )


def test_imports_use_worktree():
    assert Path(selector.__file__).resolve().parents[3] == Path(__file__).resolve().parents[1]


def test_patch_config_has_no_budget_or_count_sentinel():
    assert not inspect.signature(selector.patch_selection_config).parameters
    config = selector.patch_selection_config()
    for name in (
        "target_tokens", "hard_tokens", "wrapper_reserve_tokens", "max_candidates",
        "max_sources", "max_items_per_source", "max_documents", "max_spans",
        "marginal_utility_threshold",
    ):
        assert getattr(config, name) is None
        with pytest.raises(ValueError):
            replace(config, **{name: 10**9})
    with pytest.raises(TypeError):
        selector.patch_selection_config(2000)
    with pytest.raises(ValueError):
        replace(selector.docs_selection_config(800), hard_tokens=None)


def test_unique_necessary_witnesses_exceed_all_old_caps():
    items = [
        row(index, f"const setting_{index} = '{index}:" + "данные_契約_" * 16 + "';",
            path=f"src/config_{index // 8}.py")
        for index in range(72)
    ]
    requirements = EvidenceRequirementSet(tuple(
        EvidenceRequirement(f"fact-{index}", "required_fact", item["display_text"])
        for index, item in enumerate(items)
    ))
    decision = select(items, requirements=requirements)
    assert decision.status == "ok"
    assert len(decision.selected_candidates) == len(decision.assignments) == 72
    assert decision.metrics["selected_sources"] == 9
    assert decision.metrics["projected_total_tokens"] > 2000
    assert decision.metrics["hard_tokens"] is None
    assert decision.metrics["wrapper_reserve_tokens"] is None
    assert not decision.omissions
    assert not selector.validate_evidence_sufficiency(decision, result_kind="patch_context")
    by_id = {candidate.stable_id: candidate for candidate in decision.selected_candidates}
    for assignment in decision.assignments:
        candidate = by_id[assignment.evidence_id]
        requirement = next(item for item in requirements if item.requirement_id == assignment.requirement_id)
        assert selector.validate_assignment_binding(requirement, candidate, assignment)
        assert candidate.display_text == candidate.original["display_text"]
        assert candidate.content_sha256 == hashlib.sha256(candidate.display_text.encode("utf-8")).hexdigest()
    reversed_decision = select(reversed(items), requirements=requirements)
    assert decision.selection_hash == reversed_decision.selection_hash
    assert decision.selected_candidates == reversed_decision.selected_candidates


def test_patch_preserves_entire_long_window_and_partial_relevance():
    text = "\n".join(f"const setting_{index} = 'value_{index}';" for index in range(400))
    path = "src/" + "契約_данные_" * 100 + ".py"
    stable = "child-" + "契約_" * 100
    section = "section " + "данные_" * 100
    decision = select([row(0, text, path=path, stable_chunk_id=stable, title=section)])
    assert len(decision.selected_candidates) == 1
    candidate = decision.selected_candidates[0]
    assert candidate.display_text == candidate.projected_text == text
    assert candidate.char_end == 100 + len(text)
    assert (candidate.path_or_url, candidate.stable_id, candidate.section) == (path, stable, section)
    assert decision.metrics["selected_tokens"] > 2000
    assert decision.status == "insufficient_evidence"
    assert "visible_content_assignment_required" in decision.missing_requirements
    assert not selector.validate_evidence_sufficiency(decision, result_kind="patch_context")


def test_shared_parent_identical_bytes_and_overlapping_windows_are_not_duplicates():
    text = "const setting = 'enabled';"
    items = [row(0, text), row(1, text, path="src/config_0.py")]
    decision = select(items)
    assert len(decision.selected_candidates) == 2
    assert not decision.omissions
    repeat = select([items[0], dict(items[0])])
    assert len(repeat.selected_candidates) == 1
    assert [item.reason_code for item in repeat.omissions] == ["exact_duplicate"]


@pytest.mark.parametrize("change", [
    {"path": "other.py"}, {"title": "other section"},
    {"doc_scope": "other scope"}, {"module_id": "other module"},
    {"version_binding": "exact", "resolved_version": "2"},
    {"authority": "canonical"}, {"char_start": 200, "char_end": 226},
])
def test_same_stable_id_with_noninterchangeable_attribution_fails_closed(change):
    first = row(0)
    second = dict(first, **change)
    decision = select([first, second])
    assert not decision.selected_candidates
    assert "stable_identity_collision:child-0" in decision.missing_requirements
    assert "invalid_identity" in {item.reason_code for item in decision.omissions}


def test_exact_dedupe_requires_equivalent_coverage_and_attribution():
    candidates, _ = selector.normalize_candidates([row(0)], result_kind="patch_context")
    first = candidates[0]
    for second in (
        replace(first, covered_requirement_ids=frozenset({"different-proof"})),
        replace(first, authority="canonical"),
        replace(first, version_binding="exact", resolved_version="2"),
        replace(first, doc_scope="other"),
        replace(first, section="other"),
        replace(first, evidence_id="other"),
    ):
        kept, omitted = selector._deduplicate([first, second], selector.patch_selection_config(), ())
        assert len(kept) == 2
        assert not omitted


def test_explicit_paths_and_requirements_over_twelve_are_lossless():
    items = [row(index) for index in range(27)]
    paths = [item["path"] for item in items]
    facts = [item["display_text"] for item in items]
    decision = select(
        items, required_evidence_paths=iter(paths), required_target_paths=iter(paths),
        public_requirements=iter(facts),
    )
    for kind, expected in (("evidence_path", paths), ("target_path", paths), ("required_fact", facts)):
        assert {item.value for item in decision.requirements if item.kind == kind} == set(expected)
    assert not any(item.requirement_id.startswith("input_limit:") for item in decision.requirements)
    assert decision.status == "ok"
    assert len(decision.assignments) == 81
    assert not selector.validate_evidence_sufficiency(decision, result_kind="patch_context")
    docs = selector.build_requirements(
        "", required_evidence_paths=paths, required_target_paths=paths, public_requirements=facts,
    )
    for kind in ("evidence_path", "target_path", "required_fact"):
        assert sum(item.kind == kind for item in docs) == 12
    assert {item.value for item in docs if item.kind == "unsupported_query"} == {"paths", "public_requirements"}
    source_facts = selector.build_requirements(
        "", representation_bounded=False,
        public_requirements=(
            {"kind": "source_fact", "source_path": path, "scope": f"scope {index}",
             "requirement_id": f"source-fact-{index}"}
            for index, path in enumerate(paths)
        ),
    )
    assert len(source_facts) == 27
    assert {item.requirement_id for item in source_facts} == {f"source-fact-{index}" for index in range(27)}


def test_patch_keeps_existing_lexical_identifiers_without_count_clipping():
    names = [f"setting_{index:03d}" for index in range(30)]
    decision = select(
        [row(index, f"const {name} = 'value';") for index, name in enumerate(names)],
        question=" ".join(names),
    )
    assert {item.value for item in decision.requirements if item.kind == "exact_term"} == set(names)
    assert len(decision.assignments) == 30
    assert decision.status == "ok"


def test_eligibility_identity_scope_version_and_freshness_guards_remain():
    items = [row(index, project_identity="project", module_id="module",
                 version_binding="exact", resolved_version="1") for index in range(7)]
    items[1]["freshness"] = "stale"
    items[2]["project_identity"] = "other"
    items[3]["module_id"] = "other"
    items[4]["resolved_version"] = "2"
    items[5]["version_binding"] = "unknown"
    items[6]["display_content_hash"] = "0" * 64
    decision = select(items, project_identity="project", module_id="module", exact_version="1")
    assert [item.stable_id for item in decision.selected_candidates] == ["child-0"]
    assert {item.reason_code for item in decision.omissions} == {
        "stale", "outside_scope", "wrong_version", "unknown_version", "invalid_identity",
    }
    conflict = select([row(0, "const setting_0_extra = 'disabled';")], question="setting_0")
    assert not conflict.selected_candidates
    assert "query_identifier_conflict" in {item.reason_code for item in conflict.omissions}


@pytest.mark.parametrize("factory,profile", [
    (selector.docs_selection_config, "generic"),
    (selector.library_docs_selection_config, "library_docs_answer"),
    (selector.project_docs_selection_config, "project_docs_answer"),
])
def test_docs_profiles_keep_original_representation_policy(factory, profile):
    config = factory(5000)
    assert asdict(config) == {
        "result_kind": "docs_answer", "target_tokens": 650, "hard_tokens": 800,
        "profile": profile, "schema_version": selector.SELECTOR_SCHEMA_VERSION,
        "max_candidates": 20, "max_sources": 3, "max_items_per_source": 2,
        "max_documents": 3, "max_spans": 6, "near_duplicate_threshold": 850,
        "overlap_threshold": 800, "marginal_utility_threshold": 100,
        "shingle_size": 5, "wrapper_reserve_tokens": 120, "cache_enabled": False,
    }
    decision = selector.select_evidence([row(index) for index in range(27)], question="", config=config)
    assert sum(item.reason_code == "candidate_cap" for item in decision.omissions) == 7
    assert len(decision.selected_candidates) <= 6
    assert decision.metrics["projected_total_tokens"] <= 800
    assert not selector.validate_evidence_sufficiency(decision, result_kind="docs_answer")


def test_long_exact_required_fact_has_lossless_hash_bound_witness():
    routes = ",".join(
        f'{{"route":"/contract/{index}","handler":"dispatch_{index}","timeout":{index + 1}}}'
        for index in range(90)
    )
    fact = f"const route_contract = '[{routes}]';"
    assert len(fact) > 1500
    requirement = EvidenceRequirement("route-contract", "required_fact", fact)
    decision = select([row(0, fact)], requirements=EvidenceRequirementSet((requirement,)))
    assert decision.status == "ok"
    candidate = decision.selected_candidates[0]
    assignment = decision.assignments[0]
    unit = selector.resolve_assignment_unit(candidate, assignment)
    assert unit.text == fact
    assert unit.char_end - unit.char_start == len(fact)
    assert unit.content_sha256 == assignment.unit_content_hash == hashlib.sha256(fact.encode()).hexdigest()
    assert assignment.char_start == 100
    assert assignment.char_end == 100 + len(fact)
    assert not selector.validate_evidence_sufficiency(decision, result_kind="patch_context")
    docs = extract_answer_units(fact)
    assert docs == extract_answer_units(fact, representation_bounded=True)
    assert len(docs) == 1 and len(docs[0].text) == 1500
    assert docs[0].text == fact[:1500]
    assert docs[0].char_end == 1500
    assert not selector.validate_assignment_binding(
        requirement, candidate, replace(assignment, unit_content_hash="0" * 64),
    )
    assert not selector.validate_assignment_binding(
        requirement, candidate, replace(assignment, unit_char_end=assignment.unit_char_end - 1),
    )
    forged = replace(unit, unit_id="unit-forged")
    assert not selector.validate_assignment_binding(
        requirement, replace(candidate, answer_units=(forged,)), replace(assignment, unit_id=forged.unit_id),
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        replace(unit, content_sha256="0" * 64)


@pytest.mark.parametrize("typed", [False, True])
def test_late_literal_after_sixty_four_units_is_assigned(typed):
    declarations = [f"config_{index:03d} = value_{index:03d}" for index in range(90)]
    fact = "late_config = enabled"
    text = "\n".join([*declarations, fact])
    requirement = (
        EvidenceRequirement(
            "late-literal", "proof_obligation", "late_config", obligation_kind="exact_fact",
            subject="late_config", subject_kind="config_key", value_kind="text", expected_value="enabled",
        ) if typed else EvidenceRequirement("late-literal", "required_fact", fact)
    )
    decision = select([row(0, text)], requirements=EvidenceRequirementSet((requirement,)))
    assert decision.status == "ok"
    candidate = decision.selected_candidates[0]
    assert len(candidate.answer_units) > 64
    assert candidate.answer_units_representation_bounded is False
    assignment = decision.assignments[0]
    unit = selector.resolve_assignment_unit(candidate, assignment)
    assert unit.text == fact
    assert assignment.char_start == 100 + text.index(fact)
    assert assignment.char_end == 100 + len(text)
    assert assignment.line_start == assignment.line_end == 93
    assert not selector.validate_evidence_sufficiency(decision, result_kind="patch_context")
    docs_candidates, _ = selector.normalize_candidates([row(0, text)], result_kind="docs_answer")
    docs = docs_candidates[0]
    assert docs.answer_units_representation_bounded is True
    assert len(docs.answer_units) == 64
    assert all(unit.text != fact for unit in docs.answer_units)
    assert docs.answer_units == extract_answer_units(
        text, source_fields={"path_or_url": docs.path_or_url, "section": docs.section},
    )


@pytest.mark.parametrize("soft_wrapped", [False, True])
def test_late_bullet_group_is_not_lost_to_run_representation_gates(soft_wrapped):
    runs = [f"- route_{index:03d}: dispatch_{index:03d}\n- retry_{index:03d}: {index + 1}" for index in range(14)]
    text = "\n".join(f"{run}\nseparator_{index:03d} = boundary" for index, run in enumerate(runs))
    units = extract_answer_units(
        text, include_soft_wrapped_prose=soft_wrapped, representation_bounded=False,
    )
    assert any(unit.kind == "unit_group" and unit.text == runs[-1] for unit in units)
    docs = extract_answer_units(text, include_soft_wrapped_prose=soft_wrapped)
    assert not any(unit.kind == "unit_group" and unit.text == runs[-1] for unit in docs)
    assert len(docs) <= 64
    requirement = EvidenceRequirement("late-route-and-retry", "required_fact", runs[-1])
    decision = select([row(0, text)], requirements=EvidenceRequirementSet((requirement,)))
    assert decision.status == "ok"
    assert not selector.validate_evidence_sufficiency(decision, result_kind="patch_context")


def test_patch_group_width_and_soft_wrapped_sentence_counts_have_no_representation_caps():
    bullets = "\n".join(f"- endpoint_{index:03d}: handler_{index:03d}" for index in range(9))
    units = extract_answer_units(bullets, include_soft_wrapped_prose=True, representation_bounded=False)
    assert any(unit.kind == "unit_group" and unit.text == bullets for unit in units)
    docs = extract_answer_units(bullets, include_soft_wrapped_prose=True)
    assert not any(unit.kind == "unit_group" and unit.text == bullets for unit in docs)
    paragraphs = "\n\n".join(
        f"Component {index} provides request\nvalidation for route {index}." for index in range(22)
    )
    units = extract_answer_units(paragraphs, include_soft_wrapped_prose=True, representation_bounded=False)
    docs = extract_answer_units(paragraphs, include_soft_wrapped_prose=True)
    assert sum(unit.kind == "paragraph_sentence" for unit in units) == 22
    assert sum(unit.kind == "paragraph_sentence" for unit in docs) == 16
