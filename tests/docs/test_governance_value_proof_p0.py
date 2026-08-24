from __future__ import annotations

from docmancer.docs.application.evidence_selection import (
    build_requirements,
    project_docs_selection_config,
    select_evidence,
)
from tests.docs._shared_test_evidence_selection import _candidate


QUESTION = (
    "What project rules govern the shared browser and scan Android permission "
    "preflight on Android 13+, including policy ownership, notification "
    "permission, deferred background location, and the pinned "
    "permission_handler version?"
)


def _requirements():
    return build_requirements(QUESTION, profile="project_docs_answer")


def _select(candidates):
    requirements = _requirements()
    return select_evidence(
        candidates,
        question=QUESTION,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )


def _substantive_candidates(*, authority: str = "official"):
    return [
        _candidate(
            "scope",
            "Browser and scan use the same Android permission preflight policy.",
            source="docs/permission-policy.md",
            authority=authority,
        ),
        _candidate(
            "ownership",
            "PermissionService owns platform permission policy for browser/scan preflight.",
            source="docs/permission-policy.md",
            authority=authority,
        ),
        _candidate(
            "notification",
            "Android 13 requires notification permission before browser or scan startup.",
            source="docs/permission-policy.md",
            authority=authority,
        ),
        _candidate(
            "location",
            "Background location remains deferred from browser/scan preflight.",
            source="docs/permission-policy.md",
            authority=authority,
        ),
        _candidate(
            "pin",
            "The pinned permission_handler version is 11.4.0.",
            source="pubspec.lock",
            authority=authority,
        ),
    ]


def test_governance_question_plan_uses_typed_value_relations():
    requirements = _requirements()
    obligations = [item for item in requirements if item.kind == "proof_obligation"]
    assert len(obligations) == 5
    by_relation = {item.relation: item for item in obligations}
    assert set(by_relation) == {
        "governed_scope",
        "governance_ownership",
        "governance_requirement",
        "governance_state",
        "governance_version",
    }
    assert by_relation["governance_version"].value_kind == "version_range"
    assert by_relation["governance_state"].expected_value == "deferred"
    assert all(item.response_mode == "value" for item in obligations)


def test_permission_scope_is_not_overclassified_as_a_requirement():
    requirements = build_requirements(
        "What project rules govern auth policy, including permission scope and logging policy?",
        profile="project_docs_answer",
    )
    obligation = next(
        item for item in requirements
        if item.kind == "proof_obligation" and item.subject == "permission scope"
    )
    assert obligation.relation == "governance_facet"


def test_navigation_summary_cannot_prove_governance_values():
    navigation = [
        _candidate(
            "scope-nav",
            "Shared browser and scan Android permission preflight policy is documented in ARCHITECTURE.md.",
            source="README.md",
        ),
        _candidate(
            "ownership-nav",
            "Policy ownership is documented in ARCHITECTURE.md.",
            source="README.md",
        ),
        _candidate(
            "notification-nav",
            "Notification permission requirements are documented in permission-notifications.md.",
            source="README.md",
        ),
        _candidate(
            "location-nav",
            "Background location policy is documented in permission-notifications.md.",
            source="README.md",
        ),
        _candidate(
            "version-nav",
            "The permission_handler version pin is recorded in pubspec.lock.",
            source="README.md",
        ),
    ]
    decision = _select(navigation)

    assert decision.support_decision.answer_supported is False
    assert decision.support_decision.mandatory_coverage < 1.0
    assert decision.support_decision.missing_requirement_ids
    assert len(decision.assignments) < 5


def test_one_readme_navigation_paragraph_cannot_claim_full_coverage():
    summary = _candidate(
        "readme-summary",
        (
            "The shared browser and scan Android permission preflight policy is documented in "
            "ARCHITECTURE.md. Policy ownership is explained in the architecture guide. "
            "Notification permission requirements and background location policy are documented "
            "in permission-notifications.md. The permission_handler version pin is recorded in "
            "pubspec.lock."
        ),
        source="README.md",
    )
    decision = _select([summary])

    assert decision.support_decision.answer_supported is False
    assert decision.support_decision.mandatory_coverage < 1.0
    assert decision.status == "insufficient_evidence"


def test_supporting_overview_cannot_authorize_project_governance_even_with_values():
    decision = _select(_substantive_candidates(authority="supporting"))

    assert decision.support_decision.answer_supported is False
    assert decision.support_decision.mandatory_coverage < 1.0
    assert decision.support_decision.missing_requirement_ids


def test_canonical_substantive_governance_values_remain_supported():
    decision = _select(_substantive_candidates())

    assert decision.support_decision.answer_supported is True
    assert decision.support_decision.mandatory_coverage == 1.0
    assert decision.support_decision.missing_requirement_ids == ()
    assert len(decision.assignments) == 5


def test_version_location_statement_requires_the_actual_version_value():
    missing_value = _candidate(
        "version-location",
        "The permission_handler version pin is recorded in pubspec.lock.",
        source="pubspec.lock",
    )
    with_value = _candidate(
        "version-value",
        "The pinned permission_handler version is 11.4.0 in pubspec.lock.",
        source="pubspec.lock",
    )
    requirements = _requirements()
    version_requirement = next(
        item for item in requirements if item.relation == "governance_version"
    )

    missing = select_evidence(
        [missing_value],
        question=QUESTION,
        config=project_docs_selection_config(800),
        requirements=type(requirements)((version_requirement,)),
    )
    present = select_evidence(
        [with_value],
        question=QUESTION,
        config=project_docs_selection_config(800),
        requirements=type(requirements)((version_requirement,)),
    )

    assert missing.support_decision.answer_supported is False
    assert present.support_decision.answer_supported is True
