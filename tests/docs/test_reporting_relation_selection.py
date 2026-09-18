from docmancer.docs.application.context_candidate_ranking import (
    _facet_aware_candidates,
    _relation_request_priority,
)


def _candidate(path: str, snippet: str, *, authority: str):
    question = (
        "How does Lumen report dropped records when a bounded export "
        "cannot include everything?"
    )
    return {
        "path": path,
        "path_or_url": path,
        "snippet": snippet,
        "content": snippet,
        "authority": authority,
        "retrieval_query_matches": {
            "query-original": {
                "qualified": True,
                "query_text": question,
                "query_origin": "original",
                "relation": "direct",
                "match_ratio": 0.58,
                "lexical_score": 10.0,
                "mode": "or_fallback",
            },
        },
        "retrieval_query_ids": ["query-original"],
    }


def test_reporting_relation_prefers_requested_target_not_unrelated_report():
    question = (
        "How does Lumen report dropped records when a bounded export "
        "cannot include everything?"
    )
    direct = (
        "When the export is truncated, `dropped_counts` reports dropped records "
        "to the caller."
    )
    topical = (
        "Lumen handles bounded exports and validates their configuration. "
        "Invalid roots are reported as warnings."
    )

    assert _relation_request_priority(question, direct) > _relation_request_priority(
        question, topical
    )


def test_reporting_relation_breaks_authority_tie_without_creating_qualification():
    question = (
        "How does Lumen report dropped records when a bounded export "
        "cannot include everything?"
    )
    direct = _candidate(
        "docs/response-contract.md",
        "When the export is truncated, `dropped_counts` reports dropped records "
        "to the caller.",
        authority="supporting",
    )
    topical = _candidate(
        "docs/runbook.md",
        "Lumen handles bounded exports and validates their configuration. "
        "Invalid roots are reported as warnings.",
        authority="source_of_truth",
    )

    ranked = _facet_aware_candidates(
        [topical, direct],
        query_text={"query-original": question},
        required_query_ids={"query-original"},
    )

    assert ranked[0]["path"] == "docs/response-contract.md"
    assert ranked[0]["retrieval_query_matches"]["query-original"]["qualified"] is True


def test_reporting_relation_does_not_reward_report_verb_without_requested_target():
    question = "How does Lumen report dropped records?"
    unrelated = "Lumen reports startup warnings to the operator."
    assert _relation_request_priority(question, unrelated) == (0.0,) * 9
