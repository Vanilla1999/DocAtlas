from __future__ import annotations

from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.quality import internal_noise_score
from tests.docs.test_project_doc_ranking import fake_chunk


def test_fastapi_internal_todo_comment_demoted_for_how_to_query():
    intent = classify_project_query_intent("How to create a FastAPI application with routing and dependency injection?")
    clean = fake_chunk("docs/tutorial.md", "FastAPI tutorial", 0.5, "Create a FastAPI app with routing using FastAPI, app.get, Depends, dependency injection, routers, request handlers, startup configuration, and examples for users.")
    noisy = fake_chunk("docs/source.md", "Internal source", 0.9, "TODO: remove when discarding the openapi_prefix parameter. Starlette still has incorrect type specification for handlers. This internal implementation comment is not useful for normal application routing tutorials.")

    ranked = rerank_project_doc_chunks([noisy, clean], question="How to create a FastAPI application with routing and dependency injection?", intent=intent, limit=2)

    assert ranked[0].path == "docs/tutorial.md"


def test_internal_comment_allowed_for_source_internals_query():
    intent = classify_project_query_intent("What source internals mention TODO comments?")
    clean = fake_chunk("docs/tutorial.md", "FastAPI tutorial", 0.5, "Create a FastAPI app with routing using FastAPI and dependency injection for normal user facing application examples.")
    noisy = fake_chunk("docs/source.md", "Internal source", 0.9, "TODO: remove when discarding the openapi_prefix parameter. Starlette still has incorrect type specification for handlers. This internal implementation comment is useful when source internals are requested.")

    ranked = rerank_project_doc_chunks([noisy, clean], question="What source internals mention TODO comments?", intent=intent, limit=2)

    assert ranked[0].path == "docs/source.md"


def test_noise_score_detects_todo_and_type_ignore_patterns():
    assert internal_noise_score("TODO: fix\nvalue = x  # type: ignore") >= 0.5
