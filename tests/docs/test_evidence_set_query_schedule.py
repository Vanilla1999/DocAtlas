"""Explicit scheduling preserves budgets, raw literals and no-I/O boundaries."""
from pathlib import Path
import pytest

from docmancer.docs.application.need_query_schedule import scheduled_plan
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup, DocumentationQueryPlan, build_documentation_query_plan


@pytest.mark.parametrize("limit", [-1, 13, 100, True])
def test_explicit_budget_cannot_exceed_twelve_or_be_negative(limit):
    with pytest.raises(ValueError):
        scheduled_plan(build_documentation_query_plan("query"), optional_limit=limit)


def test_zero_optional_slots_means_no_hidden_request():
    _, rows = scheduled_plan(build_documentation_query_plan("query", lookup_queries=("topic",)), optional_limit=0)
    assert rows == ()


def test_explicit_source_and_user_lookups_keep_priority():
    plan = build_documentation_query_plan("引用 `ALPHA_KEY`", explicit_path="Guide.md", lookup_queries=("cross-site calls", "引用"))
    _, rows = scheduled_plan(plan, optional_limit=3)
    assert [r.origin for r in rows] == ["exact_path", "host_lookup", "host_lookup"]


def test_identical_search_text_is_deduplicated_but_code_case_is_not():
    question = "Explain client dispatch."
    root = DocumentationLookup("query-original", question, "original")
    extra = tuple(DocumentationLookup(f"query-lookup-{i}", x, "host_lookup", False, relation="host_lookup")
                  for i, x in enumerate(("Foo.run", "Foo.run", "foo.run", question)))
    _, rows = scheduled_plan(DocumentationQueryPlan(question, (root, *extra)))
    assert [row.text for row in rows] == ["Foo.run", "foo.run"]


def test_quoted_space_and_punctuation_are_not_normalized():
    plan = build_documentation_query_plan("Explain ` /--disabled`.")
    _, rows = scheduled_plan(plan)
    assert any(row.text == " /--disabled" for row in rows)


def test_search_proposal_cannot_read_evaluation_answers(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("query scheduler attempted I/O")
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    plan = build_documentation_query_plan("文書", lookup_queries=("引用",))
    _, rows = scheduled_plan(plan)
    assert [row.text for row in rows] == ["引用"]


def test_no_optional_proposals_means_no_generated_work():
    _, rows = scheduled_plan(build_documentation_query_plan("Name four types of timeout"))
    assert rows == ()


def test_reapplying_scheduler_does_not_multiply_slots_or_change_question():
    plan = build_documentation_query_plan("  文書\n", lookup_queries=("引用", "预算"))
    first, rows = scheduled_plan(plan)
    second, again = scheduled_plan(first)
    assert (second, again) == (first, rows)
    assert first.original_question == "  文書\n"
    assert first.component_contract == plan.component_contract


def test_forged_inferred_focus_never_enters_explicit_schedule():
    root = DocumentationLookup("query-original", "query", "original")
    forged = DocumentationLookup("query-focus-1", "invented answer", "retrieval_hint", False, relation="host_lookup")
    _, rows = scheduled_plan(DocumentationQueryPlan("query", (root, forged)))
    assert rows == ()


def test_no_hidden_per_need_allowance():
    root = DocumentationLookup("query-original", "query", "original")
    extras = tuple(DocumentationLookup(f"query-lookup-{i}", f"topic-{i}", "host_lookup", False, relation="host_lookup") for i in range(30))
    _, rows = scheduled_plan(DocumentationQueryPlan("query", (root, *extras)))
    assert len(rows) == 12
