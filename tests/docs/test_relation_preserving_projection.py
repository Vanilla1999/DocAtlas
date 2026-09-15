from types import SimpleNamespace

from docmancer.docs.application._project_docs_service_part03 import (
    _candidate_admission_priority,
)
from docmancer.docs.application.context_candidate_ranking import (
    _relation_request_priority,
)
from docmancer.docs.application.docs_context_projection import (
    _retains_visible_sources,
)


def _candidate(text: str, *, qualified: bool = True):
    return SimpleNamespace(
        text=text,
        metadata={"retrieval_query_ids": ("query-original",) if qualified else ()},
    )


def test_condition_bearing_permission_rule_survives_bounded_admission():
    question = "When is an agent allowed to call sync_catalog?"
    topical = _candidate("The sync_catalog command updates the local catalog.")
    conditional = _candidate(
        "When the catalog is stale and the workspace is clean, the response may call "
        "sync_catalog with the returned plan."
    )

    ranked = sorted(
        [topical, conditional],
        key=lambda item: _candidate_admission_priority(question, item),
    )

    assert ranked[0] is conditional


def test_unqualified_condition_does_not_jump_qualified_evidence():
    question = "When is an agent allowed to call sync_catalog?"
    qualified = _candidate("sync_catalog is a lifecycle action.")
    unqualified = _candidate(
        "When a catalog is stale, call sync_catalog.", qualified=False,
    )

    ranked = sorted(
        [unqualified, qualified],
        key=lambda item: _candidate_admission_priority(question, item),
    )

    assert ranked[0] is qualified


def test_balanced_sibling_relation_beats_one_sided_topical_span():
    question = (
        "Which repository documents are the source of truth, and which storage "
        "artifacts are only derived indexes?"
    )
    one_sided = (
        "Storage artifacts include derived indexes, extracted artifacts, and caches "
        "for repository files."
    )
    balanced = (
        "Repository documents remain the source of truth. Storage data are derived "
        "indexes that can be rebuilt."
    )

    assert _relation_request_priority(question, balanced) > _relation_request_priority(
        question, one_sided,
    )


def test_explicit_alternative_list_prefers_span_retaining_all_user_terms():
    question = "How is a binding classified as exact, declared-only, or unbound?"
    partial = "A declared-only binding can later become unbound."
    complete = "Bindings are classified as exact, declared-only, or unbound."

    assert _relation_request_priority(question, complete) > _relation_request_priority(
        question, partial,
    )


def test_read_next_compaction_cannot_shrink_existing_visible_evidence():
    previous = {
        "sources": [{"evidence_id": "e1", "snippet": "condition and required outcome"}],
    }
    shorter = {
        "sources": [{"evidence_id": "e1", "snippet": "required outcome"}],
    }
    superset = {
        "sources": [{"evidence_id": "e1", "snippet": "condition and required outcome plus detail"}],
    }

    assert _retains_visible_sources(previous, shorter) is False
    assert _retains_visible_sources(previous, superset) is True
