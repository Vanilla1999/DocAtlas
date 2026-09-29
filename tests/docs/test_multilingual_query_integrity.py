"""M1 — query integrity: original question, raw literals, hint ≠ coverage.

These are invariant tests: they verify that the real query planner and
extraction functions preserve the original question text and raw literal
spans without normalising them.  They also check that optional mixed-script
hints are bounded, literal, and never claim original-query coverage.

No production code is changed unless a test reveals a concrete bug.
"""
from __future__ import annotations

from docmancer.docs.domain.query_reference_binding import query_mentions
from docmancer.docs.domain.query_script_runs import mixed_script_phrases
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


# ---------------------------------------------------------------------------
# 1. query_mentions preserves raw spans (including significant whitespace)
# ---------------------------------------------------------------------------
def test_query_mentions_preserves_raw_literal_spans():
    question = 'Чем отличаются ` /-S` и `/-S`, `--no-force` и `--force`?'
    mentions = query_mentions(question)
    values = [question[m.start:m.end] for m in mentions]
    assert values == [" /-S", "/-S", "--no-force", "--force"]
    assert all(m.text == question[m.start:m.end] for m in mentions)


# ---------------------------------------------------------------------------
# 2. build_documentation_query_plan preserves the original question verbatim
# ---------------------------------------------------------------------------
def test_plan_preserves_original_question_verbatim():
    question = "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"
    plan = build_documentation_query_plan(question)
    assert plan.original_question == question
    assert plan.queries[0].query_id == "query-original"
    assert plan.queries[0].text == question.strip()
    assert plan.queries[0].origin == "original"


def test_plan_preserves_original_question_with_literals():
    question = 'Чем отличаются ` /-S` и `/-S`, `--no-force` и `--force`?'
    plan = build_documentation_query_plan(question)
    assert plan.original_question == question
    assert plan.queries[0].text == question.strip()


# ---------------------------------------------------------------------------
# 3. Mixed-script hints: literal, bounded, never coverage
# ---------------------------------------------------------------------------
def test_mixed_script_hints_are_literal_substrings():
    question = "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"
    hints = mixed_script_phrases(question)
    assert hints == ("boolean option",)
    for hint in hints:
        assert hint in question


def test_mixed_script_hints_bounded_to_two():
    question = (
        "Как работает resource cache и boolean option, "
        "а также force flag в terminal window?"
    )
    hints = mixed_script_phrases(question)
    assert len(hints) <= 2
    for hint in hints:
        assert hint in question


def test_mixed_script_hints_empty_for_pure_russian():
    question = "Как записать только отрицательное имя логического параметра?"
    hints = mixed_script_phrases(question)
    assert hints == ()


def test_hint_queries_never_claim_original_coverage():
    """retrieval_hint queries must have coverage_required=False and no parent."""
    question = "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"
    plan = build_documentation_query_plan(question)
    hint_queries = [q for q in plan.queries if q.origin == "retrieval_hint"]
    assert hint_queries, "expected at least one retrieval_hint query"
    for q in hint_queries:
        assert q.coverage_required is False
        assert q.public_parent_query_id is None


def test_hint_query_text_is_literal_substring_not_translation():
    """Hint text must occur verbatim in the original question."""
    question = "Как работает resource cache, сохраняя ограничения?"
    plan = build_documentation_query_plan(question)
    hint_queries = [q for q in plan.queries if q.origin == "retrieval_hint"]
    assert hint_queries
    for q in hint_queries:
        assert q.text in question


# ---------------------------------------------------------------------------
# 4. Negation and condition pairs: different queries, different facts
# ---------------------------------------------------------------------------
def test_negation_pair_produces_distinct_anchor_queries():
    """--no-force and --force must appear as separate anchors, not merged."""
    question = "What happens to --no-force when I declare only the --force option?"
    plan = build_documentation_query_plan(question)
    anchor_texts = [q.text for q in plan.queries if q.origin == "exact_anchor"]
    assert "--no-force" in anchor_texts
    assert "--force" in anchor_texts
    assert "--no-force" != "--force"


def test_condition_question_preserves_full_question():
    question = "Does raising typer.Exit() itself imply an error, and what is its default exit code?"
    plan = build_documentation_query_plan(question)
    assert plan.original_question == question
    assert plan.queries[0].text == question.strip()


# ---------------------------------------------------------------------------
# 5. Normalised retrieval terms may casefold; raw spans must not be lost
# ---------------------------------------------------------------------------
def test_exact_terms_normalise_but_mentions_preserve_raw():
    """documentation_exact_terms may normalise (casefold), but query_mentions
    must preserve the raw span.  Consumers needing exact syntax must read
    raw spans from query_mentions, not from normalised exact terms."""
    from docmancer.docs.domain.query_terms import documentation_exact_terms

    question = 'Чем отличаются ` /-S` и `/-S`, `--no-force` и `--force`?'
    mentions = query_mentions(question)
    mention_values = [question[m.start:m.end] for m in mentions]

    # The two /-S variants are distinct in raw spans
    assert mention_values.count(" /-S") == 1
    assert mention_values.count("/-S") == 1

    # exact_terms may normalise — that is acceptable for retrieval
    exact = [t.value for t in documentation_exact_terms(question)]
    # But raw distinction is preserved by mentions, not by exact_terms
    assert " /-S" in mention_values
    assert "/-S" in mention_values
