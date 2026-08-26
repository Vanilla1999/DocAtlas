from __future__ import annotations

import pytest

from docmancer.docs.domain.mutation_intent import (
    build_mutation_intent,
    evaluate_mutation_readiness,
    resolve_mutation_targets,
)
from docmancer.docs.domain.patch_request_plan import build_patch_request_plan


def test_acceptance_symbols_are_not_mutation_targets() -> None:
    plan = build_patch_request_plan(
        "Update FooService so that BarDecision is returned."
    )

    assert [target.value for target in plan.mutation_targets] == ["FooService"]
    assert plan.acceptance_conditions
    assert not plan.unresolved_parts


def test_unknown_operation_tail_fails_closed() -> None:
    plan = build_patch_request_plan(
        "Fix BrowserPermissionGate and delete everything."
    )

    assert plan.operation == "modify"
    assert [target.value for target in plan.mutation_targets] == [
        "BrowserPermissionGate"
    ]
    assert any(part.startswith("unresolved_patch_clause:") for part in plan.unresolved_parts)


@pytest.mark.parametrize(
    "question",
    [
        "Fix the permission architecture.",
        "Make browser and sync consistent.",
        "Update the relevant files.",
        "Исправь связанные модули.",
    ],
)
def test_implicit_target_requests_never_authorize_mutation(question: str) -> None:
    plan = build_patch_request_plan(question)
    intent = build_mutation_intent(question)

    assert not plan.mutation_targets
    assert not intent.requested_targets
    assert intent.operation == "none"


def test_reviewed_polite_wrapper_is_explicitly_supported() -> None:
    plan = build_patch_request_plan("Please fix BrowserPermissionGate.")

    assert plan.operation == "modify"
    assert [target.value for target in plan.mutation_targets] == [
        "BrowserPermissionGate"
    ]
    assert not plan.unresolved_parts


def test_mutation_and_preserve_overlap_fails_closed_instead_of_raising() -> None:
    plan = build_patch_request_plan(
        "Fix FooService without changing FooService."
    )

    assert plan.operation == "modify"
    assert "target_polarity_conflict:FooService" in plan.unresolved_parts


def test_target_limit_overflow_is_reported_without_silent_truncation() -> None:
    targets = ", ".join(f"Target{index}Service" for index in range(13))
    plan = build_patch_request_plan(f"Fix {targets}.")

    assert plan.mutation_targets == ()
    assert "input_limit:mutation_targets" in plan.unresolved_parts


def test_question_limit_reaches_mutation_intent_without_losing_trailing_constraints() -> None:
    question = "Fix FooService." + " " * 4_000 + "without changing CriticalService."

    intent = build_mutation_intent(question)

    assert intent.operation == "none"
    assert intent.request_plan is not None
    assert "input_limit:question" in intent.request_plan.unresolved_parts
    assert not evaluate_mutation_readiness(intent).ready


def test_backtick_quoted_path_remains_a_path_target() -> None:
    plan = build_patch_request_plan("Fix `src/foo.py`.")

    assert [(item.value, item.kind) for item in plan.mutation_targets] == [
        ("src/foo.py", "path")
    ]
    assert not plan.unresolved_parts


def test_unsupported_surface_cannot_use_legacy_symbol_fallback() -> None:
    plan = build_patch_request_plan("Kindly fix BrowserPermissionGate.")
    intent = build_mutation_intent("Kindly fix BrowserPermissionGate.")

    assert plan.operation == "none"
    assert not plan.mutation_targets
    assert intent.operation == "none"
    assert not intent.requested_targets


@pytest.mark.parametrize(
    ("question", "operation", "targets", "destination", "parent"),
    [
        ("Delete src/obsolete.py.", "delete", ["src/obsolete.py"], None, None),
        ("Rename OldService to NewService.", "rename", ["OldService"], "NewService", None),
        (
            "Create lib/permission/new_gate.dart in lib/permission/module.dart.",
            "create", [], "lib/permission/new_gate.dart", "lib/permission/module.dart",
        ),
    ],
)
def test_reviewed_operation_surfaces_preserve_target_roles_and_spans(
    question: str,
    operation: str,
    targets: list[str],
    destination: str | None,
    parent: str | None,
) -> None:
    plan = build_patch_request_plan(question)

    assert plan.operation == operation
    assert [target.value for target in plan.mutation_targets] == targets
    assert (plan.destination.value if plan.destination else None) == destination
    assert (plan.parent_context.value if plan.parent_context else None) == parent
    assert not plan.unresolved_parts
    for target in (*plan.mutation_targets, plan.destination, plan.parent_context):
        if target is None:
            continue
        assert question[target.query_span_start:target.query_span_end].strip("`") == target.value


def test_create_without_reviewed_parent_context_fails_closed() -> None:
    plan = build_patch_request_plan("Create lib/permission/new_gate.dart.")
    intent = build_mutation_intent("Create lib/permission/new_gate.dart.")

    assert plan.destination is not None
    assert "create_parent_not_requested" in plan.unresolved_parts
    assert not evaluate_mutation_readiness(intent).ready


@pytest.mark.parametrize(
    ("question", "evidence", "expected_missing"),
    [
        (
            "Delete src/obsolete.py.",
            [{"path": "src/obsolete.py", "source_class": "code_graph"}],
            (),
        ),
        (
            "Rename OldService to NewService.",
            [
                {"path": "src/old_service.py", "symbols": ["OldService"], "source_class": "code_graph"},
                {"path": "src/new_service.py", "symbols": ["NewService"], "source_class": "code_graph"},
            ],
            ("rename_destination_collision",),
        ),
        (
            "Create lib/permission/new_gate.dart in lib/permission/module.dart.",
            [
                {"path": "lib/permission/module.dart", "source_class": "code_graph"},
                {
                    "path": "repo-map",
                    "source_class": "repo_map",
                    "collision_free_targets": ["lib/permission/new_gate.dart"],
                },
            ],
            (),
        ),
    ],
)
def test_operation_readiness_requires_operation_specific_witnesses(
    question: str,
    evidence: list[dict[str, object]],
    expected_missing: tuple[str, ...],
) -> None:
    intent = build_mutation_intent(question)
    resolved = resolve_mutation_targets(
        intent,
        evidence,
        evidence_id_for_item=lambda item: f"ev:{item['path']}",
    )
    readiness = evaluate_mutation_readiness(resolved)

    assert tuple(
        item for item in readiness.missing if item in expected_missing
    ) == expected_missing
    assert readiness.ready is not bool(expected_missing)


def test_create_requires_requested_parent_and_explicit_collision_witness() -> None:
    intent = build_mutation_intent(
        "Create lib/permission/new_gate.dart in lib/permission/module.dart."
    )
    sibling_only = resolve_mutation_targets(
        intent,
        [{"path": "lib/permission/existing.dart", "source_class": "code_graph"}],
        evidence_id_for_item=lambda item: f"ev:{item['path']}",
    )

    assert set(evaluate_mutation_readiness(sibling_only).missing) >= {
        "create_parent_or_module_not_resolved",
        "create_destination_not_verified",
    }


def test_create_existing_destination_is_a_collision() -> None:
    intent = build_mutation_intent(
        "Create lib/permission/new_gate.dart in lib/permission/module.dart."
    )
    resolved = resolve_mutation_targets(
        intent,
        [
            {"path": "lib/permission/module.dart", "source_class": "code_graph"},
            {"path": "lib/permission/new_gate.dart", "source_class": "code_graph"},
        ],
        evidence_id_for_item=lambda item: f"ev:{item['path']}",
    )

    assert "create_target_collision" in evaluate_mutation_readiness(resolved).missing


def test_rename_requires_explicit_collision_free_destination_witness() -> None:
    intent = build_mutation_intent("Rename OldService to NewService.")
    resolved = resolve_mutation_targets(
        intent,
        [{"path": "src/old.py", "symbols": ["OldService"], "source_class": "code_graph"}],
        evidence_id_for_item=lambda item: f"ev:{item['path']}",
    )

    assert "rename_destination_not_verified" in evaluate_mutation_readiness(resolved).missing


def test_project_docs_cannot_resolve_source_symbol_filename_alias() -> None:
    intent = build_mutation_intent("Fix BrowserPermissionGate.")
    resolved = resolve_mutation_targets(
        intent,
        [{"path": "src/browser_permission_gate.py", "source_class": "project_doc"}],
        evidence_id_for_item=lambda item: f"ev:{item['path']}",
    )

    assert not resolved.resolved_targets
    assert "mutation_target_not_resolved" in evaluate_mutation_readiness(resolved).missing


def test_project_docs_cannot_resolve_preserve_targets() -> None:
    intent = build_mutation_intent("Fix FooService without changing BarService.")
    resolved = resolve_mutation_targets(
        intent,
        [
            {"path": "src/foo_service.py", "symbols": ["FooService"], "source_class": "code_graph"},
            {"path": "docs/bar.md", "symbols": ["BarService"], "source_class": "project_doc"},
        ],
        evidence_id_for_item=lambda item: f"ev:{item['path']}",
    )

    assert not resolved.preserved_targets
    assert "preserve_target_not_resolved" in evaluate_mutation_readiness(resolved).missing


@pytest.mark.parametrize(
    ("english", "russian"),
    [
        (
            "Fix partial permission handling in BrowserPermissionGate and PermissionService.",
            "Исправь обработку частичных разрешений в BrowserPermissionGate и PermissionService.",
        ),
        (
            "Update FooService so that BarDecision is returned.",
            "Обнови FooService, чтобы возвращался BarDecision.",
        ),
        (
            "Refactor FooService without changing generated_result.g.dart.",
            "Отрефактори FooService без изменения generated_result.g.dart.",
        ),
        (
            "Fix FooService; do not change generated_result.g.dart.",
            "Исправь FooService; не изменяй generated_result.g.dart.",
        ),
    ],
)
def test_reviewed_russian_surfaces_share_the_canonical_patch_model(
    english: str,
    russian: str,
) -> None:
    en = build_patch_request_plan(english)
    ru = build_patch_request_plan(russian)

    assert ru.language == "ru"
    assert ru.operation == en.operation == "modify"
    assert [(item.value, item.kind, item.role) for item in ru.mutation_targets] == [
        (item.value, item.kind, item.role) for item in en.mutation_targets
    ]
    assert [(item.value, item.kind, item.role) for item in ru.preserve_targets] == [
        (item.value, item.kind, item.role) for item in en.preserve_targets
    ]
    assert len(ru.behavioral_requirements) == len(en.behavioral_requirements)
    assert len(ru.acceptance_conditions) == len(en.acceptance_conditions)
    assert not ru.unresolved_parts
    assert ru.surface_id.replace(":ru", ":en") == en.surface_id


def test_unreviewed_russian_patch_tail_fails_closed() -> None:
    plan = build_patch_request_plan(
        "Исправь FooService и затем удали всё."
    )

    assert [target.value for target in plan.mutation_targets] == ["FooService"]
    assert any(
        part.startswith("unresolved_patch_clause:")
        for part in plan.unresolved_parts
    )
