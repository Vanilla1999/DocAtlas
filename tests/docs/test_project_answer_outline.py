from __future__ import annotations

from docmancer.docs.application.project_answer_outline import build_project_answer_outline
from docmancer.docs.domain.project_query_intent import classify_project_query_intent


def test_answer_outline_recommends_reading_order():
    intent = classify_project_query_intent("What is the architecture and project structure?")
    outline = build_project_answer_outline(
        question="What is the architecture and project structure?",
        intent=intent,
        context_pack=[
            {"path": "README.md", "title": "Docmancer", "heading_path": "What you get", "freshness": "current", "content": "overview"},
            {"path": "wiki/Architecture.md", "title": "Architecture", "heading_path": "Architecture > Indexing", "freshness": "current", "content": "pipeline"},
            {"path": "CONTRIBUTING.md", "title": "Contributing", "heading_path": "Project structure", "freshness": "current", "content": "docmancer/core"},
        ],
    )

    assert outline["query_intent"] == "architecture"
    assert outline["coverage"]["architecture"] is True
    assert outline["coverage"]["project_structure"] is True
    assert outline["recommended_reading_order"][0]["path"] == "README.md"
