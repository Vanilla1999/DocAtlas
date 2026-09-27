"""Keep a command/option/value together as a bounded retrieval-only probe."""
from copy import deepcopy

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.reference_query_tagging import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import (
    build_documentation_query_plan, technical_anchors,
)


def literal_lookup(question, literal):
    plan = build_documentation_query_plan(question)
    matching = [q for q in plan.queries if q.origin == "exact_anchor"
                and q.text == f"`{literal}`"]
    assert len(matching) == 1, "The exact command's option value was lost in planning"
    lookup = matching[0]
    assert not lookup.coverage_required
    assert lookup.relation == "exact_anchor"
    assert lookup.public_parent_query_id == "query-original"
    assert plan.original_question == question
    assert len([q for q in plan.queries if q.origin == "exact_anchor"]) <= 12
    return lookup


@pytest.mark.parametrize("literal", [
    "archive-tool --format json", "cache-store --zone remote",
    "backup-tool --copies 3", "archive-tool --format=json",
])
def test_plan_keeps_literal_command_option_value(literal):
    literal_lookup(f"Объясни поведение {literal} без изменения файлов?", literal)


@pytest.mark.parametrize("body,expected", [
    ("Use archive-tool --format json to preserve the manifest.", True),
    ("Use archive-tool --format text to preserve the manifest.", False),
    ("archive-tool is described here; json is used by another tool --format text.", False),
    ("# archive-tool --format json\n\nUnrelated prose follows.", False),
    ("[archive-tool --format json](https://example.invalid/ref)", False),
    ("Use other-tool --format json to preserve the manifest.", False),
    ("Use archive-tool --format jsonl to preserve the manifest.", False),
])
def test_literal_probe_requires_same_visible_command_not_bag_of_tokens(body, expected):
    lookup = literal_lookup("Объясни archive-tool --format json?", "archive-tool --format json")
    chunk = RetrievedChunk(source="docs/reference.md", chunk_index=0, text=body, score=7,
        metadata={"source_class": "project_doc", "project_identity": "repo",
                  "title": "archive-tool --format json"})
    before = deepcopy(chunk)
    out = _tag_retrieval_query([chunk], lookup.query_id, lookup.text, lookup,
                              expected_project_identity="repo")[0]
    assert out.metadata["retrieval_query_matches"][lookup.query_id]["qualified"] is expected
    assert "query-original" not in out.metadata["retrieval_query_ids"]
    assert chunk == before
    assert out.score == chunk.score


@pytest.mark.parametrize("metadata", [
    {"project_identity": "foreign"}, {"stale": True},
    {"lifecycle_status": "deprecated"}, {"risk_flags": ["unsafe"]},
])
def test_command_literal_never_bypasses_source_policy(metadata):
    lookup = literal_lookup("Объясни archive-tool --format json?", "archive-tool --format json")
    chunk = RetrievedChunk(source="docs/reference.md", chunk_index=0,
        text="Use archive-tool --format json to preserve the manifest.", score=7,
        metadata={"source_class": "project_doc", "project_identity": "repo", **metadata})
    out = _tag_retrieval_query([chunk], lookup.query_id, lookup.text, lookup,
                              expected_project_identity="repo")[0]
    assert out.metadata["retrieval_query_matches"][lookup.query_id]["qualified"] is False


@pytest.mark.parametrize("question", [
    "Does --verbose delete files?", "Explain cache-store --verbose and its output.",
    "Explain cache-store --dry-run?", "Explain ordinary prose with no command.",
    "Explain cache-store\n--zone remote?",
])
def test_ambiguous_or_boolean_options_do_not_invent_values(question):
    assert not any(q.text.startswith("`") and " --" in q.text
                   for q in build_documentation_query_plan(question).queries
                   if q.origin == "exact_anchor")


def test_literal_probe_budget_is_bounded():
    question = " ".join(f"cache-tool --zone r{i}" for i in range(20))
    anchors = technical_anchors(question)
    assert len(anchors) <= 12
    plan = build_documentation_query_plan(question)
    assert sum(q.origin == "exact_anchor" for q in plan.queries) <= 12


def test_original_question_retains_negation():
    question = "Почему archive-tool --format json не удаляет manifest?"
    literal_lookup(question, "archive-tool --format json")
    assert build_documentation_query_plan(question).queries[0].text == question
