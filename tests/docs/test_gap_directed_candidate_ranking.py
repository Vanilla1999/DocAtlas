"""Ranking regressions for action-shaped documentation questions."""
from docmancer.docs.application.context_candidate_ranking import _context_rank, _facet_aware_candidates


def _source(path: str, body: str, question: str, lexical: float):
    return {
        "path": path,
        "snippet": body,
        "content": body,
        "authority": "source_of_truth",
        "catalog_role": "runbook",
        "retrieval_query_matches": {
            "query-original": {
                "qualified": True,
                "match_ratio": 0.6,
                "lexical_score": lexical,
                "query_origin": "original",
                "query_text": question,
                "preferred_catalog_roles": [],
            }
        },
    }


def _rank(question: str, rows: list[dict], *, relation: str | None = None):
    query_text = {"query-original": question}
    canonical = set()
    if relation is not None:
        query_text["query-relation-1"] = relation
        canonical.add("query-relation-1")
    return _facet_aware_candidates(
        rows,
        query_text=query_text,
        required_query_ids={"query-original"},
        canonical_query_ids=canonical,
    )


def test_what_should_actor_do_prefers_visible_procedure_over_definition():
    question = (
        "What should an agent do before ingesting a documentation candidate "
        "when its authority, version binding, or scope is unclear?"
    )
    relation = "its authority, version binding, or scope is unclear"
    topical = _source(
        "docs/authority.md",
        "DocAtlas owns documentation authority, version binding, and scope boundaries for agent evidence.",
        question,
        30.0,
    )
    topical["retrieval_query_matches"]["query-relation-1"] = {
        "qualified": True,
        "match_ratio": 0.8,
        "lexical_score": 14.0,
        "query_origin": "canonical_intent",
        "query_text": relation,
        "preferred_catalog_roles": [],
    }
    procedure = _source(
        "docs/workflow.md",
        "If a candidate's authority, version binding, or scope is uncertain, call `prepare_docs`; "
        "review its evidence, ask for confirmation, validate the manifest, then prefetch it.",
        question,
        20.0,
    )
    assert _rank(question, [topical, procedure], relation=relation)[0] is procedure


def test_negated_action_question_does_not_gain_positive_procedure_bonus():
    question = "What should an agent not do before ingesting documentation?"
    positive = _source(
        "docs/workflow.md", "Call `prepare_docs` before ingesting documentation.", question, 20.0,
    )
    rank = _context_rank(
        positive, {"query-original": question}, {"query-original"},
    )
    assert rank[0] == 0.0


def test_non_action_question_keeps_lexical_ordering():
    question = "What is documentation authority?"
    definition = _source(
        "docs/authority.md", "Documentation authority defines which source is canonical.", question, 30.0,
    )
    procedure = _source(
        "docs/workflow.md", "Call `prepare_docs` when documentation needs inspection.", question, 20.0,
    )
    assert _rank(question, [definition, procedure])[0] is definition


def test_structured_procedure_snippet_keeps_action_priority_over_relation_only_candidate():
    question = (
        "What should an agent do before ingesting a documentation candidate "
        "when its authority, version binding, or scope is unclear?"
    )
    relation = "its authority, version binding, or scope is unclear"
    topical = _source(
        "docs/authority.md",
        "DocAtlas owns documentation authority, version binding, and scope boundaries for agent evidence.",
        question,
        30.0,
    )
    topical["retrieval_query_matches"]["query-relation-1"] = {
        "qualified": True,
        "match_ratio": 0.8,
        "lexical_score": 14.0,
        "query_origin": "canonical_intent",
        "query_text": relation,
        "preferred_catalog_roles": [],
    }
    procedure = _source(
        "SKILL.md",
        "placeholder",
        question,
        20.0,
    )
    procedure["snippet"] = {
        "code": (
            "If a candidate's authority, version binding, or scope is uncertain, "
            "call `prepare_docs`; review its evidence, ask for confirmation, "
            "validate the manifest, then prefetch it."
        )
    }
    procedure["content"] = procedure["snippet"]["code"]

    assert _rank(question, [topical, procedure], relation=relation)[0] is procedure
