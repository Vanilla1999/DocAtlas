from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"expected source block not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def ensure_import(path: Path, marker: str, import_line: str) -> None:
    text = path.read_text(encoding="utf-8")
    if import_line in text:
        return
    if marker not in text:
        raise SystemExit(f"import marker not found in {path}")
    path.write_text(text.replace(marker, marker + import_line, 1), encoding="utf-8")


predicate = ROOT / "docmancer/docs/domain/source_search_handoff.py"
predicate.write_text(
    '''"""Fail-closed authorization for continuing through local repository evidence.

This contract never grants documentary support.  It only says that a coding
agent received one explicit, bounded, non-automatic handoff to inspect local
source/tests.  Every field is checked positively so unrelated lifecycle or
recovery actions cannot accidentally authorize editing.
"""
from __future__ import annotations

from typing import Any, Iterable


def is_safe_local_source_handoff(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("tool") != "code_search":
        return False
    if value.get("type") != "search_local_source":
        return False
    if value.get("handled_by") != "coding_agent":
        return False
    if value.get("requires_confirmation") is not False:
        return False
    if value.get("repeat_docs_context") is not False:
        return False
    if value.get("auto_execute") is not False:
        return False
    if value.get("hard_stop") is True:
        return False

    for key in ("query_terms", "suggested_doc_paths", "suggested_symbols"):
        rows = value.get(key)
        if isinstance(rows, (list, tuple)) and any(
            isinstance(item, str) and item.strip() for item in rows
        ):
            return True
    return False


def has_safe_local_source_handoff(values: Iterable[Any]) -> bool:
    return any(is_safe_local_source_handoff(value) for value in values)


__all__ = ["has_safe_local_source_handoff", "is_safe_local_source_handoff"]
''',
    encoding="utf-8",
)

answer = ROOT / "docmancer/docs/domain/answer_completeness.py"
ensure_import(
    answer,
    "from docmancer.docs.domain.project_doc_ranking import normalize_doc_path\n",
    "from docmancer.docs.domain.source_search_handoff import has_safe_local_source_handoff\n",
)
replace_once(
    answer,
    '        "edit_ready": status == "exact" or source_search_required,\n',
    '        "edit_ready": status == "exact" or has_safe_local_source_handoff(recommended_next_actions),\n',
)
replace_once(
    answer,
    '        "edit_ready": supported or bool(result["recommended_next_actions"]),\n',
    '        "edit_ready": supported or has_safe_local_source_handoff(result["recommended_next_actions"]),\n',
)
replace_once(
    answer,
    '        "repeat_docs_context": False,\n        "reason": "Selected docs are partial/navigational; exact story-specific terms are missing from source-backed snippets.",\n',
    '        "repeat_docs_context": False,\n        "auto_execute": False,\n        "reason": "Selected docs are partial/navigational; exact story-specific terms are missing from source-backed snippets.",\n',
)

projection = ROOT / "docmancer/docs/interfaces/mcp/recovery_projection.py"
ensure_import(
    projection,
    "from docmancer.docs.application.recovery import build_recovery_diagnosis, recovery_action\n",
    "from docmancer.docs.domain.source_search_handoff import is_safe_local_source_handoff\n",
)
replace_once(
    projection,
    '            "edit_ready": True,\n            "source_search_status": "required",\n',
    '            "edit_ready": is_safe_local_source_handoff(recovery),\n            "source_search_status": "required",\n',
)

test = ROOT / "tests/docs/test_source_search_edit_readiness.py"
test.write_text(
    '''from __future__ import annotations

from types import SimpleNamespace

import pytest

from docmancer.docs.domain import answer_completeness
from docmancer.docs.domain.source_search_handoff import (
    has_safe_local_source_handoff,
    is_safe_local_source_handoff,
)
from docmancer.docs.interfaces.mcp.recovery_projection import _annotate_recovery_handoff


def valid_action() -> dict:
    return {
        "tool": "code_search",
        "type": "search_local_source",
        "handled_by": "coding_agent",
        "requires_confirmation": False,
        "repeat_docs_context": False,
        "auto_execute": False,
        "query_terms": ["checkpoint persistence"],
    }


def test_exact_nonautomatic_local_source_handoff_is_edit_ready_without_granting_support():
    action = valid_action()
    assert is_safe_local_source_handoff(action) is True
    assert has_safe_local_source_handoff([action]) is True

    projection = {
        "documentation_supported": False,
        "hard_stop": False,
        "answer_supported": False,
        "estimated_tokens": 0,
    }
    _annotate_recovery_handoff(projection, action)
    assert projection["documentation_supported"] is False
    assert projection["answer_supported"] is False
    assert projection["disposition"] == "search_local_source"
    assert projection["edit_ready"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        {"tool": "prepare_docs"},
        {"type": "rephrase_question"},
        {"handled_by": "server"},
        {"requires_confirmation": True},
        {"repeat_docs_context": True},
        {"auto_execute": True},
        {"auto_execute": None},
        {"query_terms": []},
        {"query_terms": ["  "]},
        {"hard_stop": True},
    ],
)
def test_incomplete_or_unsafe_handoff_never_authorizes_edit(mutation):
    action = valid_action()
    action.update(mutation)
    assert is_safe_local_source_handoff(action) is False

    projection = {
        "documentation_supported": False,
        "hard_stop": False,
        "answer_supported": False,
        "estimated_tokens": 0,
    }
    _annotate_recovery_handoff(projection, action)
    assert projection["answer_supported"] is False
    assert projection["edit_ready"] is False


def test_arbitrary_recommended_action_does_not_authorize_legacy_completeness(monkeypatch):
    monkeypatch.setattr(
        answer_completeness,
        "evaluate_project_answer_completeness",
        lambda **_: {
            "answer_type": "unavailable",
            "answer_completeness": {},
            "recommended_next_actions": [
                {
                    "tool": "prepare_docs",
                    "type": "sync_project_docs",
                    "handled_by": "coding_agent",
                    "requires_confirmation": False,
                    "auto_execute": False,
                }
            ],
        },
    )
    support = SimpleNamespace(
        answer_supported=False,
        mandatory_coverage=0.0,
        mandatory_requirement_ids=(),
    )
    result = answer_completeness.derive_project_answer_completeness(
        question="How is the project configured?",
        context_pack=[],
        answer_available=False,
        intent=SimpleNamespace(),
        support_decision=support,
        assigned_requirement_ids=[],
    )
    assert result["answer_completeness"]["edit_ready"] is False
    assert result["answer_completeness"]["canonical_support"]["answer_supported"] is False


def test_generated_story_source_action_is_explicit_and_safe():
    action = answer_completeness._source_search_action(
        missing_terms=["checkpoint persistence"],
        context_pack=[{"path": "docs/contract.md"}],
    )
    assert action["auto_execute"] is False
    assert is_safe_local_source_handoff(action) is True
''',
    encoding="utf-8",
)

# Remove every temporary carrier from both materializer attempts.  The active
# workflow can keep running after its checked-out file is deleted.
for relative in (
    "scripts/materialize_source_search_hardening.py",
    ".github/workflows/materialize-source-search-hardening.yml",
):
    (ROOT / relative).unlink(missing_ok=True)
