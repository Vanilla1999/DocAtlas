from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

import docmancer.docs.domain.answer_completeness as completeness_module
from docmancer.docs.domain.answer_completeness import (
    derive_project_answer_completeness,
    evaluate_project_answer_completeness,
)
from docmancer.docs.domain.recovery_handoff import (
    has_safe_local_source_handoff,
    is_safe_local_source_handoff,
)
from docmancer.docs.interfaces.mcp.recovery_projection import (
    _annotate_recovery_handoff,
)


def _safe_action() -> dict[str, object]:
    return {
        "tool": "code_search",
        "type": "search_local_source",
        "handled_by": "coding_agent",
        "requires_confirmation": False,
        "repeat_docs_context": False,
        "auto_execute": False,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tool", "prepare_docs"),
        ("type", "rephrase_question"),
        ("handled_by", "docatlas"),
        ("requires_confirmation", True),
        ("repeat_docs_context", True),
        ("auto_execute", True),
        ("auto_execute", None),
    ],
)
def test_safe_source_handoff_fails_closed_for_incomplete_or_unsafe_fields(
    field: str,
    value: object,
) -> None:
    action = _safe_action()
    if value is None:
        action.pop(field)
    else:
        action[field] = value

    assert is_safe_local_source_handoff(action) is False
    assert has_safe_local_source_handoff([action]) is False


def test_safe_source_handoff_accepts_only_complete_nonautomatic_code_search() -> None:
    action = _safe_action()

    assert is_safe_local_source_handoff(action) is True
    assert has_safe_local_source_handoff([{"tool": "prepare_docs"}, action]) is True


def test_story_gap_emits_safe_source_handoff_and_allows_local_edit_workflow() -> None:
    result = evaluate_project_answer_completeness(
        question="How should takeAPicture recovery be implemented?",
        context_pack=[],
        answer_available=False,
        intent=SimpleNamespace(wants_code_symbols=True, wants_how_to=True, broad=False),
    )

    action = result["recommended_next_actions"][0]
    assert is_safe_local_source_handoff(action) is True
    assert result["answer_completeness"]["source_search_required"] is True
    assert result["answer_completeness"]["edit_ready"] is True


def test_derive_does_not_authorize_an_arbitrary_recommended_action(monkeypatch) -> None:
    unsafe_result = {
        "answer_type": "partial",
        "answer_completeness": {
            "status": "partial",
            "answer_type": "partial",
            "coverage_score": 0.0,
        },
        "recommended_next_actions": [
            {
                "tool": "prepare_docs",
                "type": "sync_project_docs",
                "requires_confirmation": False,
            }
        ],
    }
    monkeypatch.setattr(
        completeness_module,
        "evaluate_project_answer_completeness",
        lambda **_: deepcopy(unsafe_result),
    )

    result = derive_project_answer_completeness(
        question="How should recovery work?",
        context_pack=[],
        answer_available=False,
        intent=SimpleNamespace(),
        support_decision=SimpleNamespace(
            answer_supported=False,
            mandatory_coverage=0.0,
            mandatory_requirement_ids=(),
        ),
        assigned_requirement_ids=[],
    )

    assert result["answer_completeness"]["edit_ready"] is False


def test_projection_does_not_authorize_partial_code_search_shape() -> None:
    projection = {"hard_stop": False}
    action = _safe_action()
    action.pop("auto_execute")

    _annotate_recovery_handoff(projection, action, edit_authorized=True)

    assert projection.get("edit_ready") is not True


def test_projection_authorizes_complete_safe_source_handoff() -> None:
    projection = {"hard_stop": False}

    _annotate_recovery_handoff(
        projection, _safe_action(), edit_authorized=True
    )

    assert projection["disposition"] == "search_local_source"
    assert projection["edit_ready"] is True
    assert projection["source_search_status"] == "required"

    investigation_only = {"hard_stop": False}
    _annotate_recovery_handoff(investigation_only, _safe_action())
    assert investigation_only["disposition"] == "search_local_source"
    assert investigation_only["edit_ready"] is False
    assert investigation_only["source_search_status"] == "required"


def test_authoritative_hard_stop_cannot_be_bypassed_by_source_handoff() -> None:
    projection = {"hard_stop": True}

    _annotate_recovery_handoff(
        projection, _safe_action(), edit_authorized=True
    )

    assert projection["disposition"] == "resolve_authoritative_conflict"
    assert projection["edit_ready"] is False
    assert projection["source_search_status"] == "blocked"
