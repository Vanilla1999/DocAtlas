"""New dictionary-exit contract tests; legacy recall gates remain untouched."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from types import SimpleNamespace

import pytest

from docmancer.core.config import DocmancerConfig, QueryRouter
from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application.need_query_schedule import (
    requirement_search_probes, schedule_need_queries, scheduled_plan,
)
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.lifecycle_policy import lifecycle_allows, lifecycle_intent
from docmancer.docs.domain.project_doc_ranking import (
    project_source_taxonomy, rerank_project_doc_chunks, source_lane_allowed,
    source_requirement_boost, source_weight_for_intent,
)
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
from docmancer.docs.domain.query_terms import documentation_query_terms
from docmancer.docs.domain.question_component_rewrite import rewrite_component
from docmancer.docs.domain.question_surface_normalization import normalize_question_surface
from docmancer.docs.domain.retrieval_routing import route_initial_stages
from docmancer.docs.domain.snippets import infer_snippet_query_intent, _infer_language
from docmancer.docs.domain.technical_terms import controlled_noun_forms, coerce_technical_term
from docmancer.docs.domain.tool_selection import select_public_docs_tool, normalize_public_docs_action
from docmancer.mcp.search import _tokens
from docmancer.retrieval.dispatch import HybridRetrievalError, RetrievalDispatcher
from docmancer.retrieval.query_planning import build_query_plan, metadata_matches_filters






















def test_sqlite_removes_topic_features_but_keeps_identity_filters(tmp_path):
    store = SQLiteStore(tmp_path / "index.db", tmp_path / "extracted")
    store.add_documents([
        Document(source="docs/a.md", content="# Configure widget\n\nconfigure widget",
            metadata={"project_identity": "repo", "title": "Configure widget"}),
        Document(source="docs/b.md", content="# Terms and Conditions\n\nconfigure widget",
            metadata={"project_identity": "other", "title": "Terms and Conditions"}),
    ], recreate=True)
    results = store.query("configure widget", filters={"project_identity": "repo"}, limit=5, budget=128)
    assert results
    assert {chunk.source for chunk in results} == {"docs/a.md"}
    removed = {"task_action_title_boost", "boilerplate_title_penalty", "project_rule_authority_boost",
        "non_legal_query_legal_source_penalty"}
    assert all(not removed & set(chunk.metadata["ranking"]["feature_contributions"]) for chunk in results)





