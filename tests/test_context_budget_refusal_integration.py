"""A final context budget must retain the real public source-delivery veto.

One preparation and two public context calls after an unsynchronised edit.
The original optics source/question/update are reused. Cap 150 is fixed from
the previously archived stale DTO (155 UTF-8 quarter units), before this
regression is executed. It exercises compaction of a real operational refusal,
not a fabricated internal payload. No model or source-resource calls.
"""
from __future__ import annotations

from eval.evidence_quality_v2 import runtime
from tests.test_prepared_retrieval_integration import (
    ADMISSION_ENV, CAP_ENV, PARENTS_ENV, WIDE_CAP,
    OPTICS_DOCUMENTS, OPTICS_QUESTION, UPDATED_ISSUE,
    _context, _database_state, _file_state, _packet_proxy, state_root,
)


REFUSAL_CAP = 150


def test_final_budget_preserves_stale_source_denial_and_confirmation(
    tmp_path, monkeypatch, state_root, record_property,
):
    """1 prepare, 2 contexts, 0 source reads, 0 model calls."""
    project = tmp_path / "project"
    runtime.write_project(project, OPTICS_DOCUMENTS)
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        env.setenv(PARENTS_ENV, "1")
        inventory = runtime.index_project(service, config, project)
        before = _database_state(inventory)
        (project / "docs/issue.md").write_text(UPDATED_ISSUE, encoding="utf-8")
        edited_files = _file_state(project)
        env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
        env.setenv(CAP_ENV, str(WIDE_CAP))
        wide = _context(service, project, OPTICS_QUESTION)
        assert wide.get("kind") == "docs_context", wide
        assert not wide.get("sources"), wide
        assert wide.get("requires_confirmation") is True, wide
        assert (wide.get("delivery_decision") or {}).get("deliverable") is False, wide
        assert wide.get("confirmation_reason"), wide
        assert REFUSAL_CAP < _packet_proxy(wide) <= WIDE_CAP
        env.setenv(CAP_ENV, str(REFUSAL_CAP))
        bounded = _context(service, project, OPTICS_QUESTION)
        record_property("wide_refusal_utf8_quarter_proxy", _packet_proxy(wide))
        record_property("bounded_refusal_utf8_quarter_proxy", _packet_proxy(bounded))
        assert bounded.get("kind") == "docs_context", bounded
        assert _packet_proxy(bounded) <= REFUSAL_CAP, bounded
        assert not bounded.get("sources") and not bounded.get("read_next"), bounded
        for key in ("context_available", "answer_supported", "answer_available", "edit_ready"):
            assert wide.get(key) is False and bounded.get(key) is False, (key, bounded)
        for key in (
            "status", "reason_code", "support_status", "requires_confirmation",
            "confirmation_reason", "delivery_decision", "operational_status", "context_quality",
        ):
            assert bounded.get(key) == wide.get(key), (key, wide, bounded)
        assert _database_state(inventory) == before
        assert _file_state(project) == edited_files
