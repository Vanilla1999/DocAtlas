"""Real qualification/eligibility boundary controls; no model-quality claim.

No policy rejection is fabricated by constructing EvidenceQualification.
The high scorer is an explicit unit control, not a replacement model answer.
Run in the complete repository environment; not exercised by the unit-slice harness.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.application.evidence_models import EvidenceCandidate, EvidenceRequirement
from docmancer.docs.application._evidence_selection_part01 import _eligible_candidates
from experiments.crosslingual_relevance.context_rescue import apply_rescue, M2B_THRESHOLD
from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

QUESTION = "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"
TEXT = (
    "When you create a *CLI option* you can give only *CLI option* names to set "
    "the `False` value. You should use a space and a single `/` and pass the "
    "negative name after that."
)
PROBE = {
    "query_text": QUESTION,
    "query_terms": ["как", "записать", "только", "отрицательное", "имя",
                    "boolean", "option", "важен", "пробел"],
    "exact_terms": [], "bound_subjects": [], "query_origin": "original",
}


def _candidate(tmp_path, *, identity="local:allowed", name="allowed"):
    path = tmp_path / name / "docs" / "rule.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEXT, encoding="utf-8")
    return {
        "project_identity": identity, "source_class": "project_doc",
        "path": str(path), "path_or_url": "docs/rule.md", "snippet": path.read_text(),
        "_source_snapshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "line_start": 1, "line_end": 1,
    }


def _qualify_and_rescue(candidate, scorer):
    original = qualify_evidence(
        PROBE, query_id="q-test", visible_text=candidate["snippet"],
        evidence_text=candidate["snippet"], candidate=candidate,
        expected_project_identity="local:allowed",
    )
    result = apply_rescue(
        original, query_id="q-test", question=QUESTION,
        evidence_text=candidate["snippet"], source_identity=candidate["project_identity"],
        source_binding={k: candidate[k] for k in (
            "path", "_source_snapshot_sha256", "line_start", "line_end")},
        scorer=scorer,
    )
    return original, result


def _prove_admission(candidate, scorer):
    original, result = _qualify_and_rescue(candidate, scorer)
    assert original.reason == "insufficient_visible_match"
    assert not original.qualified
    assert result.qualified
    assert result.reason == "context_only_relevance"
    assert result.trace["admission_only"] is True
    assert result.trace["context_relevance_threshold"] == M2B_THRESHOLD == 0.7453
    assert result.covered_query_ids == ()
    return result


def test_foreign_candidate_with_the_actual_relevant_text_is_rejected(tmp_path):
    allowed = _candidate(tmp_path)
    foreign = _candidate(tmp_path, identity="local:foreign", name="foreign")
    assert foreign["snippet"] == TEXT == allowed["snippet"]
    assert foreign["path"] != allowed["path"]
    bounded = BoundedScorer(lambda _q, _t: 0.99)
    _prove_admission(allowed, bounded)
    before = len(bounded.events)
    original, result = _qualify_and_rescue(foreign, bounded)
    assert original.reason == result.reason == "wrong_project_identity"
    assert not result.qualified
    assert len(bounded.events) == before, "policy-rejected candidate reached the scorer"


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"stale": True}, "stale_evidence"),
    ({"index_freshness": "unsynchronized"}, "unsynchronized_index"),
    ({"risk_flags": ["instruction_injection"]}, "unsafe_evidence"),
])
def test_actual_policy_veto_still_wins_after_positive_rescue(tmp_path, overrides, reason):
    allowed = _candidate(tmp_path)
    bounded = BoundedScorer(lambda _q, _t: 0.99)
    _prove_admission(allowed, bounded)
    before = len(bounded.events)
    original, result = _qualify_and_rescue({**allowed, **overrides}, bounded)
    assert original.reason == result.reason == reason
    assert not result.qualified
    assert len(bounded.events) == before


def _selection_candidate(source, rescue):
    text = source["snippet"]
    digest = hashlib.sha256(text.encode()).hexdigest()
    return EvidenceCandidate(
        stable_id="allowed-v2", evidence_id="allowed-v2", hydration_id=None,
        identity_kind="project_doc", source_identity="docs/rule.md",
        identity_aliases=("docs/rule.md",), path_or_url="docs/rule.md",
        section="Rule", parent_logical_id="rule", content_sha256=digest,
        display_text=text, projected_text=text, token_estimate=60,
        fit_token_estimate=60, reported_token_estimate=None,
        char_start=0, char_end=len(text), line_start=1, line_end=1,
        retrieval_rank=1, component_ranks=(), relevance_millis=990,
        authority="canonical", source_class="project_doc", version_binding="exact",
        resolved_version="2.0", docs_snapshot_exact=True,
        project_identity="local:allowed", module_id="", doc_scope="project",
        symbols=(), exact_terms=(), instruction_risk_flags=(),
        freshness="current", navigation_only=False,
        original={**source, "retrieval_query_matches": {"q-test": dict(rescue.trace)}},
    )


def test_wrong_version_is_removed_by_real_eligibility_after_rescue(tmp_path):
    source = _candidate(tmp_path)
    rescued = _prove_admission(source, BoundedScorer(lambda _q, _t: 0.99))
    allowed = _selection_candidate(source, rescued)
    foreign_version = replace(allowed, stable_id="wrong-v1", evidence_id="wrong-v1",
                              resolved_version="1.0", relevance_millis=1000)
    requirements = (EvidenceRequirement("version", "exact_version", "2.0"),)
    eligible, omissions, _ = _eligible_candidates(
        [foreign_version, allowed], {}, requirements,
        project_identity="local:allowed", module_id=None,
        result_kind="docs_answer", question=QUESTION,
    )
    assert [c.stable_id for c in eligible] == [allowed.stable_id]
    assert [(o.stable_id, o.reason_code) for o in omissions] == [("wrong-v1", "wrong_version")]
