from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


def test_comparison_lookup_keeps_relation_semantics_in_cross_side_probe():
    question = "How do alpha documentation and beta documentation differ in retrieval scope and provenance?"
    plan = build_documentation_query_plan(
        question, requirements=build_requirements(question, profile="project_docs_answer")
    )
    relation = [q.text.casefold() for q in plan.queries if q.query_id.startswith("query-relation-")]
    assert len(relation) <= 4
    assert any(
        "alpha documentation beta documentation" in q
        and "different" in q and "separate" in q
        for q in relation
    )
    # Search vocabulary is relation-only; it must not inject a domain answer.
    assert not any(word in " ".join(relation) for word in ("manifest", "lockfile", "repository-owned"))


def test_slash_comparison_keeps_relation_and_plain_cross_side_hypotheses():
    question = "How do alpha documentation and beta/gamma documentation differ in retrieval scope and provenance?"
    plan = build_documentation_query_plan(
        question, requirements=build_requirements(question, profile="project_docs_answer")
    )
    relation = [q.text.casefold() for q in plan.queries if q.query_id.startswith("query-relation-")]
    assert len(relation) <= 4
    assert "alpha documentation beta documentation different separate" in relation
    assert "alpha documentation gamma documentation" in relation
