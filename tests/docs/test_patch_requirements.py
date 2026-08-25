from __future__ import annotations

from docmancer.docs.application.evidence_requirements import build_patch_evidence_requirements
from docmancer.docs.domain.patch_request_plan import build_patch_request_plan
from docmancer.docs.domain.patch_requirements import build_patch_requirements


def test_patch_requirements_keep_identity_behavior_and_preserve_roles_separate() -> None:
    plan = build_patch_request_plan(
        "Fix partial permission handling across BrowserPermissionGate and "
        "PermissionService without changing permission_result.freezed.dart."
    )

    requirements = build_patch_requirements(plan)
    assert {requirement.kind for requirement in requirements} == {
        "target_declaration",
        "preserve_declaration",
        "behavioral_contract",
        "cross_module_invariant",
        "preserve_constraint",
        "generated_file_constraint",
    }
    preserve = next(
        requirement for requirement in requirements
        if requirement.kind == "preserve_constraint"
    )
    assert preserve.provenance == "user_request"
    assert preserve.query_span_start is not None
    assert preserve.query_span_end is not None


def test_patch_evidence_requirements_do_not_compile_question_plan_obligations() -> None:
    plan = build_patch_request_plan("Fix BrowserPermissionGate.")
    requirements = build_patch_evidence_requirements(plan)

    assert [requirement.query_extraction_kind for requirement in requirements] == [
        "target_declaration"
    ]
    assert all(
        requirement.public_provenance == "patch_request_plan"
        for requirement in requirements
    )
    assert all(requirement.kind != "proof_obligation" for requirement in requirements)


def test_acceptance_conditions_are_mandatory_validation_requirements() -> None:
    plan = build_patch_request_plan(
        "Update FooService so that BarDecision is returned."
    )

    requirement = next(
        item for item in build_patch_requirements(plan)
        if item.kind == "validation_requirement"
    )

    assert requirement.value == "BarDecision is returned"
    assert requirement.mandatory is True
    assert requirement.provenance == "user_request"
    assert requirement.query_span_start is not None
    assert requirement.query_span_end is not None
    assert any(
        item.query_extraction_kind == "validation_requirement"
        for item in build_patch_evidence_requirements(plan)
    )


def test_coordinated_multi_target_behavior_requires_cross_module_proof() -> None:
    coordinated = build_patch_request_plan(
        "Fix partial permission handling in BrowserPermissionGate and PermissionService."
    )
    targets_only = build_patch_request_plan(
        "Update BrowserPermissionGate and PermissionService."
    )

    assert any(
        item.kind == "cross_module_invariant"
        for item in build_patch_requirements(coordinated)
    )
    assert not any(
        item.kind == "cross_module_invariant"
        for item in build_patch_requirements(targets_only)
    )
