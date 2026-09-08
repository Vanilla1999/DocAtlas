from pathlib import Path
from types import SimpleNamespace

import pytest

from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.project_docs_catalog import read_project_docs_catalog


def _chunk(path, content, score, *, authority="supporting", matches=None, **fields):
    return SimpleNamespace(
        path=path, heading_path="Reference", content=content, score=score,
        authority=authority,
        metadata={} if matches is None else {"retrieval_query_matches": matches},
        **fields,
    )


def _rank(chunks, question, **kwargs):
    return rerank_project_doc_chunks(
        chunks, question=question, intent=classify_project_query_intent(question),
        **kwargs,
    )


@pytest.mark.parametrize(
    ("question", "role", "content"),
    [
        ("How do I install the project locally?", "runbook",
         "Install locally with pip install -e . and verify with doc-atlas --help."),
        ("How do I run the project tests?", "development",
         "Run the provider-free tests with pytest tests and exclude live markers."),
        ("What is the project architecture?", "project_architecture",
         "The architecture separates domain rules, application services, and infrastructure adapters."),
        ("How does the Docs MCP server work?", "api_contract",
         "The Docs MCP server exposes get_docs_context, prepare_docs, and docs_status over stdio."),
    ],
    ids=["installation", "testing", "architecture", "docs-mcp"],
)
def test_substantive_supporting_source_beats_less_relevant_same_role_authority(
    question, role, content,
):
    substantive = _chunk("handbook/usage.md", content, 0.8, catalog_role=role)
    unrelated = _chunk(
        "handbook/other.md", "Logo colors are blue and white.", 0.7,
        authority="source_of_truth", catalog_role=role,
    )

    ranked = _rank([unrelated, substantive], question, limit=1)

    assert ranked[0].path == substantive.path


@pytest.mark.parametrize("query_id", ["query-original", "query-path-1", "query-anchor-1", "query-lookup-1"])
def test_failed_qualification_cannot_be_rescued_by_boosts_or_backfill(query_id):
    rejected = _chunk(
        "README.md", "Only a routing description matched.", 100.0,
        authority="source_of_truth", matches={query_id: {"qualified": False}},
    )
    substantive = _chunk(
        "handbook/usage.md", "Install with pip install -e .", 0.1,
        matches={"query-original": {"qualified": True}},
    )

    ranked = _rank([rejected, substantive], "How do I install the project?", limit=3)

    assert [chunk.path for chunk in ranked] == [substantive.path]


def test_qualified_host_lookup_has_no_unconditional_multiplier():
    direct = _chunk(
        "handbook/direct.md", "Installation setup instructions.", 0.8,
        matches={"query-original": {"qualified": True}},
    )
    host = _chunk(
        "handbook/host.md", "Installation setup instructions.", 0.2,
        matches={"query-lookup-1": {"qualified": True}},
    )

    ranked = _rank([host, direct], "How do I install the project?")

    assert ranked[0].path == direct.path
    assert ranked[1].metadata["project_ranking"]["final_score"] == 0.2


def test_authority_breaks_equal_relevance_ties():
    chunks = [
        _chunk("handbook/support.md", "Installation instructions.", 0.8),
        _chunk("handbook/current.md", "Installation instructions.", 0.8,
               authority="source_of_truth"),
    ]
    assert _rank(chunks, "How do I install the project?")[0].path == chunks[1].path


@pytest.mark.parametrize(
    ("question", "expect_packs"),
    [
        ("How does the Docs MCP server work?", False),
        ("Compare Docs MCP and MCP Packs", True),
    ],
)
def test_packs_requires_comparison_or_packs_intent(question, expect_packs):
    packs = _chunk("handbook/actions.md", "Run packs-serve for action packs.", 100.0)
    docs = _chunk("handbook/docs.md", "Run docs-serve for the documentation server.", 0.1)

    ranked = _rank([packs, docs], question, limit=3)

    assert (packs.path in [chunk.path for chunk in ranked]) is expect_packs
    assert docs.path in [chunk.path for chunk in ranked]


@pytest.mark.parametrize("status", ["completed", "superseded"])
def test_history_stays_eligible_only_when_explicitly_requested(status):
    old = _chunk("handbook/old.md", "Prior architecture decision.", 100.0,
                 lifecycle_status=status)
    active = _chunk("handbook/current.md", "Current architecture.", 0.1,
                    lifecycle_status="active")
    stale = _chunk("handbook/stale.md", "Prior architecture decision.", 1000.0,
                   lifecycle_status=status, stale=True)

    assert [chunk.path for chunk in _rank(
        [old, active, stale], "What is the current architecture?",
    )] == [active.path]
    assert [chunk.path for chunk in _rank(
        [old, active, stale], "What is the historical architecture decision?",
    )] == [old.path]


@pytest.mark.parametrize(
    ("path", "authority", "status", "impact"),
    [
        ("docs/adr/0002-context-retrieval-vs-answer-proof.md",
         "historical", "superseded", "search_only"),
        ("docs/decisions/2026-08-22-defer-public-release-and-open-p1-harness.md",
         "source_of_truth", "active", "search_only"),
    ],
)
def test_repository_catalog_preserves_reviewed_decision_lifecycle(path, authority, status, impact):
    root = Path(__file__).resolve().parents[2]
    catalog = read_project_docs_catalog(root)
    assert catalog.present and catalog.valid, catalog.warnings
    entries = {entry.path: entry for entry in catalog.entries}
    assert path in entries
    entry = entries[path]
    assert (entry.role, entry.authority, entry.status, entry.impact) == (
        "adr", authority, status, impact,
    )


def _lookup_chunk(content, score, query_id, query_text, *, origin="host_lookup", **fields):
    trace = qualify_evidence(
        {"query_text": query_text, "query_origin": origin},
        query_id=query_id, visible_text=content, evidence_text=content,
    ).trace
    return _chunk("handbook/usage.md", content, score, matches={query_id: dict(trace)}, **fields)


@pytest.fixture
def competing_lookup_chunks():
    return [
        _lookup_chunk("Local installation verification uses a smoke command.", 0.9,
                      "query-lookup-1", "local installation verification"),
        _lookup_chunk("Local installation verification also checks the version.", 0.8,
                      "query-lookup-1", "local installation verification",
                      authority="source_of_truth"),
        _lookup_chunk("Provider-free testing uses pytest markers to exclude live tests.", 0.8,
                      "query-lookup-2", "provider-free testing markers"),
    ]


@pytest.mark.parametrize("limit", [2, 3])
def test_source_cap_preserves_distinct_public_lookup_before_repeated_coverage(
    competing_lookup_chunks, limit,
):
    ranked = _rank(competing_lookup_chunks, "What is the project architecture?", limit=limit)

    assert [chunk.content for chunk in ranked[:2]] == [
        competing_lookup_chunks[0].content, competing_lookup_chunks[2].content,
    ]
    assert len(ranked) <= limit


@pytest.mark.parametrize("origin", ["canonical_intent", "concept_alias", "retrieval_hint"])
def test_internal_alias_does_not_gain_public_lookup_diversity(competing_lookup_chunks, origin):
    last = competing_lookup_chunks[2]
    last.metadata["retrieval_query_matches"] = {
        "query-intent-1": dict(qualify_evidence(
            {"query_text": "provider-free testing markers", "query_origin": origin},
            query_id="query-intent-1", visible_text=last.content, evidence_text=last.content,
        ).trace),
    }

    ranked = _rank(competing_lookup_chunks, "What is the project architecture?", limit=2)

    assert [chunk.content for chunk in ranked] == [chunk.content for chunk in competing_lookup_chunks[:2]]


def test_new_public_lookup_can_relax_source_cap_without_exceeding_total_limit(competing_lookup_chunks):
    third = _lookup_chunk("Storage isolation keeps each project in its own database.", 0.7,
                          "query-lookup-3", "storage isolation database")
    other = _chunk("handbook/other.md", "Overview of the product.", 0.1)

    ranked = _rank([*competing_lookup_chunks, third, other],
                   "What is the project architecture?", limit=3)

    assert [chunk.content for chunk in ranked] == [
        competing_lookup_chunks[0].content, competing_lookup_chunks[2].content, third.content,
    ]
    assert ranked[2].metadata["project_ranking"]["diversity_relaxed"] is True


def test_exact_document_keeps_existing_source_cap_selection(competing_lookup_chunks):
    ranked = _rank(competing_lookup_chunks, "Explain handbook/usage.md", limit=2,
                   narrow_max_per_source=2)

    assert [chunk.content for chunk in ranked] == [chunk.content for chunk in competing_lookup_chunks[:2]]


def test_exact_anchor_preserves_independent_public_lookup_diversity():
    anchor = _lookup_chunk(
        "get_docs_context accepts a documentation question.", 1.0,
        "query-anchor-1", "get_docs_context", origin="exact_anchor",
    )
    lookups = [
        _lookup_chunk(f"Independent workflow facet {index} has visible evidence.", 0.9 - index / 10,
                      f"query-lookup-{index}", f"workflow facet {index} visible evidence")
        for index in range(1, 4)
    ]

    ranked = _rank([anchor, *lookups], "Trace get_docs_context workflow", limit=4)

    assert ranked[0].content == anchor.content
    assert {next(iter(chunk.metadata["retrieval_query_matches"])) for chunk in ranked[1:]} == {
        "query-lookup-1", "query-lookup-2", "query-lookup-3",
    }


def test_role_and_description_cannot_supply_public_lookup_evidence(competing_lookup_chunks):
    unrelated = _lookup_chunk(
        "The project supports a blue logo.", 100.0,
        "query-lookup-3", "project storage isolation database",
        authority="source_of_truth", catalog_role="project_architecture",
        description="Project storage isolation database architecture.",
    )
    assert unrelated.metadata["retrieval_query_matches"]["query-lookup-3"]["qualified"] is False

    ranked = _rank([unrelated, *competing_lookup_chunks], "What is the project architecture?", limit=3)

    assert unrelated.content not in [chunk.content for chunk in ranked]
