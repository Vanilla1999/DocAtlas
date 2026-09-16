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


def test_permission_summary_beats_single_conditional_example():
    question = "When is an agent allowed to call sync_catalog?"
    single_case = _candidate(
        "If the local catalog is stale, call sync_catalog with the returned plan."
    )
    summary_rule = _candidate(
        "Agents call sync_catalog only when it is returned as next_action, or when "
        "a user explicitly requests a refresh."
    )

    ranked = sorted(
        [single_case, summary_rule],
        key=lambda item: _candidate_admission_priority(question, item),
    )

    assert ranked[0] is summary_rule


def test_permission_caveat_beats_redundant_returned_action_example():
    question = "When is an agent allowed to call sync_catalog?"
    redundant = "If the server returns sync_catalog as next_action, call the returned action."
    caveat = "Network access is opt-in. Ask the user before using sync_catalog to fetch data."

    assert _relation_request_priority(question, caveat) > _relation_request_priority(
        question, redundant,
    )


def test_insufficient_evidence_action_prefers_procedural_span_over_state_definition():
    question = "What should the agent do if lookup_context returns insufficient evidence?"
    state_only = (
        "lookup_context returns `insufficient_evidence` when no safe context is available."
    )
    procedural = (
        "If the result is `insufficient_evidence`, do not claim support. "
        "Follow the bounded recovery path before continuing."
    )

    assert _relation_request_priority(question, procedural) > _relation_request_priority(
        question, state_only,
    )


def test_medium_complete_source_is_available_without_widening_long_windows():
    from docmancer.docs.domain.context_windows import _projection_limits

    # Keep enough room for one complete procedural atom (for example a job
    # polling/retry paragraph) without making long architecture sections a
    # universal projection window.
    medium = "x" * 644
    long = "x" * 955

    assert _projection_limits(medium) == (160, 320, 520, 644)
    assert _projection_limits(long) == (160, 320, 520)


def test_decision_question_prefers_mechanism_over_state_taxonomy():
    question = "How does the service decide which documentation version should be used?"
    mechanism = "Project metadata is inspected to choose the exact documentation version."
    taxonomy = "A version binding can be exact, declared-only, or unbound."

    assert _relation_request_priority(question, mechanism) > _relation_request_priority(
        question, taxonomy,
    )


def test_same_atom_forward_continuation_inherits_only_canonical_probe_qualification():
    from docmancer.core.models import RetrievedChunk
    from docmancer.docs.application._project_docs_service_part03 import (
        _qualify_same_atom_continuations,
    )

    common = {
        "parent_logical_id": "parent-1", "atom_id": "atom-1",
        "project_identity": "project:test", "source_class": "project_file",
    }
    first = RetrievedChunk(
        source="docs/workflow.md", chunk_index=1, text="If evidence is insufficient, continue ", score=2,
        metadata={**common, "stable_chunk_id": "child-1", "char_span": [10, 48],
                  "retrieval_query_matches": {"query-intent-1": {"qualified": True, "relation": "host_lookup"}},
                  "retrieval_query_ids": ("query-intent-1",)},
    )
    second = RetrievedChunk(
        source="docs/workflow.md", chunk_index=2, text="locally and stop before unsafe edits.", score=1,
        metadata={**common, "stable_chunk_id": "child-2", "char_span": [48, 84],
                  "retrieval_query_matches": {"query-intent-1": {"qualified": False}},
                  "retrieval_query_ids": ()},
    )
    unrelated = RetrievedChunk(
        source="docs/workflow.md", chunk_index=3, text="Unrelated next atom.", score=.5,
        metadata={**common, "atom_id": "atom-2", "stable_chunk_id": "child-3", "char_span": [84, 105],
                  "retrieval_query_matches": {"query-intent-1": {"qualified": False}},
                  "retrieval_query_ids": ()},
    )

    rows = _qualify_same_atom_continuations([first, second, unrelated], "query-intent-1")
    trace = rows[1].metadata["retrieval_query_matches"]["query-intent-1"]
    assert trace["qualified"] is True
    assert trace["qualification_route"] == "same_atom_continuation"
    assert trace["coverage_kind"] == "derived"
    assert rows[2].metadata["retrieval_query_ids"] == ()


def test_same_atom_continuation_beats_unrelated_supplemental_candidate():
    from docmancer.docs.application.context_candidate_ranking import _facet_aware_candidates

    continuation = {
        "path": "docs/workflow.md", "snippet": "continue locally; stop before unsafe edits",
        "retrieval_query_matches": {"query-intent-1": {
            "qualified": True, "qualification_route": "same_atom_continuation",
        }},
    }
    unrelated = {
        "path": "docs/examples.md", "snippet": "general project documentation examples",
        "retrieval_query_matches": {"query-intent-1": {"qualified": True}},
    }
    ranked = _facet_aware_candidates(
        [unrelated, continuation],
        query_text={"query-original": "What should the agent do if evidence is insufficient?",
                    "query-intent-1": "insufficient evidence documentation workflow"},
        required_query_ids={"query-original"}, canonical_query_ids={"query-intent-1"},
    )
    assert ranked[0] is continuation


def test_projection_keeps_structurally_derived_same_atom_continuation_without_public_coverage():
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source

    source = {
        "path_or_url": "docs/workflow.md", "section": "Workflow",
        "snippet": "source/tests while keeping the claim unproved; stop before unsafe edits.",
        "retrieval_query_matches": {"query-intent-1": {
            "qualified": True, "relation": "host_lookup",
            "qualification_route": "same_atom_continuation", "coverage_kind": "derived",
            "coverage_kinds": ["derived"], "query_text": "insufficient evidence workflow",
        }},
        "retrieval_query_ids": ["query-intent-1"],
        "_independent_query_plan": {"queries": [{
            "query_id": "query-intent-1", "text": "insufficient evidence workflow",
            "origin": "canonical_intent",
        }]},
    }
    visible = _requalify_visible_source(source, query_text={
        "query-original": "What should the agent do if evidence is insufficient?",
        "query-intent-1": "insufficient evidence workflow",
    })
    assert visible["retrieval_query_matches"]["query-intent-1"]["qualified"] is True
    assert "query-original" not in visible["retrieval_query_ids"]


def test_same_atom_continuation_reassembles_verbatim_without_joining_next_atom():
    from docmancer.core.models import RetrievedChunk
    from docmancer.docs.application._project_docs_service_part03 import (
        _merge_same_atom_continuations,
    )
    common = {"parent_logical_id": "p", "atom_id": "a", "char_span": [0, 6],
              "retrieval_query_matches": {"q": {"qualified": True}},
              "retrieval_query_ids": ("q",), "stable_chunk_id": "c1"}
    lead = RetrievedChunk(source="docs/a.md", chunk_index=1, text="hello ", score=2, metadata=common)
    cont = RetrievedChunk(source="docs/a.md", chunk_index=2, text="world", score=1, metadata={
        **common, "char_span": [6, 11], "stable_chunk_id": "c2",
        "retrieval_query_matches": {"q": {"qualified": True, "qualification_route": "same_atom_continuation"}},
    })
    other = RetrievedChunk(source="docs/a.md", chunk_index=3, text="!other", score=.5, metadata={
        **common, "atom_id": "b", "char_span": [11, 17], "stable_chunk_id": "c3",
    })
    rows = _merge_same_atom_continuations([lead, cont, other], "q")
    assert [row.text for row in rows] == ["hello world", "!other"]
    assert rows[0].metadata["char_span"] == [0, 11]
    assert rows[0].metadata["reassembled_from_stable_chunk_ids"] == ["c1", "c2"]


def test_colon_leadin_keeps_complete_list_items_with_continuation_sentences():
    from docmancer.docs.domain.context_windows import _focused_snippet

    text = (
        "The resolver chooses an exact artifact version from project metadata:\n\n"
        "- **channel file** — selects an SDK channel. Determines SDK docs.\n"
        "- **lock file** — extracts pinned dependency versions. Used as exact package docs versions.\n"
        "- **manifest** — records declared dependency constraints.\n"
    )
    snippet, _, _ = _focused_snippet(
        text,
        ("How does the resolver choose the dependency version from a lock file?",),
        limit=520,
    )
    assert "channel file" in snippet
    assert "Determines SDK docs" in snippet
    assert "lock file" in snippet
    assert "Used as exact package docs versions" in snippet
    assert "manifest" in snippet


def test_optional_canonical_candidate_prefers_stronger_visible_match_over_source_prior():
    from docmancer.docs.application.context_candidate_ranking import _facet_aware_candidates

    stronger = {
        "path": "docs/architecture.md", "snippet": "dependency version resolution from project lockfile",
        "catalog_role": "project_architecture", "project_ranking": {"final_score": 1.0},
        "retrieval_query_matches": {"query-intent-1": {
            "qualified": True, "match_ratio": 0.8, "lexical_score": 8.0,
        }},
    }
    weaker = {
        "path": "docs/overview.md", "snippet": "dependency version evidence from a lockfile",
        "catalog_role": "overview", "project_ranking": {"final_score": 9.0},
        "retrieval_query_matches": {"query-intent-1": {
            "qualified": True, "match_ratio": 0.6, "lexical_score": 20.0,
        }},
    }
    ranked = _facet_aware_candidates(
        [weaker, stronger], query_text={
            "query-original": "Как система выбирает версию зависимости?",
            "query-intent-1": "dependency version resolution project lockfile",
        }, required_query_ids={"query-original"}, canonical_query_ids={"query-intent-1"},
    )
    assert ranked[0] is stronger
