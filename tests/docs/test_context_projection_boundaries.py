"""Projection must keep source-local text intact without inventing answer proof."""
from __future__ import annotations

import pytest

from docmancer.docs.application.docs_context_projection import (
    _focused_snippet,
    project_docs_context,
)
from docmancer.docs.application.model_visible_projection import (
    validate_model_visible_projection,
)
from tests.docs.test_docs_context_compound_projection import _host_lookup_context_retrieval


def test_path_only_projection_uses_the_current_exact_topic_guard():
    retrieval = _host_lookup_context_retrieval()
    question = "In docs/settings.md, explain ALPHA_KEY."
    plan = retrieval["documentation_query_plan"]
    plan.update(original_question=question, explicit_paths=["docs/settings.md"],
                required_query_ids=[], public_query_ids=["query-original", "query-path-1"],
                queries=[
                    {"query_id": "query-original", "text": question, "origin": "original"},
                    {"query_id": "query-path-1", "text": "docs/settings.md", "origin": "exact_path"},
                ])
    source = retrieval["context_pack"][0]
    source.update(path="docs/settings.md", content="ALPHA_KEY enables durable storage.",
                  line_start=11, retrieval_query_matches={}, retrieval_query_ids=[])
    retrieval["context_pack"] = [source]
    result, snapshot = project_docs_context(retrieval=retrieval)
    assert result["context_available"] is True
    assert result["sources"][0]["snippet"] == source["content"]
    assert result["covered_query_ids"] == ["query-path-1"]
    assert result["answer_supported"] is False
    assert result["edit_ready"] is False
    assert validate_model_visible_projection(result, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("limit", [160, 320, 520])
def test_table_windows_never_start_or_end_inside_a_row(limit):
    rows = ["| Stage | Operation |", "| --- | --- |"] + [
        f"| stage-{i} | gateway accepts a bounded request and sends candidates to the next stage; "
        "untrusted input must never authorize edits |" for i in range(14)
    ]
    text = "  \n" + "\n".join(rows) + "\n  "
    snippet, start, end = _focused_snippet(text, ("gateway bounded candidates",), limit=limit)
    assert snippet
    assert text[start:end] == snippet
    assert len(snippet) <= limit
    assert all(line in rows for line in snippet.splitlines())


def test_oversized_table_row_does_not_drop_its_restriction():
    row = "| gateway | " + "bounded request " * 35 + "; never authorize edits |"
    text = "| Stage | Rule |\n| --- | --- |\n" + row
    snippet, start, end = _focused_snippet(text, ("gateway bounded request",), limit=160)
    assert row in snippet or "gateway" not in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


@pytest.mark.parametrize("limit", [160, 320, 520])
def test_prose_window_does_not_start_in_the_middle_of_a_word(limit):
    text = "Prefix " * 25 + "ALPHA_KEY " + "configuration " * 70
    snippet, start, end = _focused_snippet(text, ("ALPHA_KEY configuration",), limit=limit)
    assert text[start:end] == snippet
    assert len(snippet) <= limit
    assert not start or text[start - 1].isspace()
    assert end == len(text) or text[end].isspace()


def test_stronger_explicit_lookup_precedes_generated_alias_bonus():
    retrieval = _host_lookup_context_retrieval()
    plan = retrieval["documentation_query_plan"]
    plan.update(original_question="Explain the processing path.",
                public_query_ids=["query-original", "query-lookup-1"],
                required_query_ids=[], queries=[
                    {"query_id": "query-original", "text": "Explain the processing path.", "origin": "original"},
                    {"query_id": "query-lookup-1", "text": "gateway request candidates selection", "origin": "host_lookup"},
                    {"query_id": "query-intent-1", "text": "internal policy", "origin": "canonical_intent"},
                ])
    strong, weak = retrieval["context_pack"][:2]
    strong.update(path="docs/strong.md", content="The gateway handles request candidates.",
                  retrieval_query_matches={"query-lookup-1": {"query_text": "gateway request candidates selection"}})
    weak.update(path="docs/weak.md", content="Internal policy describes the gateway request.",
                retrieval_query_matches={
                    "query-lookup-1": {"query_text": "gateway request candidates selection"},
                    "query-intent-1": {"query_text": "internal policy"},
                })
    retrieval["context_pack"] = [weak, strong]
    result, snapshot = project_docs_context(retrieval=retrieval)
    assert result["sources"][0]["path_or_url"] == "docs/strong.md"
    assert "query-original" not in result["covered_query_ids"]
    assert "query-intent-1" not in result["covered_query_ids"]
    assert result["answer_supported"] is False
    assert validate_model_visible_projection(result, snapshot=snapshot, max_tokens=800) == []


def test_table_focus_prefers_the_row_matching_the_whole_lookup():
    target = "| wire | documentation transport boundary accepts requests |"
    text = ("| Area | Responsibility |\n| --- | --- |\n"
            "| introduction | documentation overview |\n"
            + "\n".join(f"| area-{i} | unrelated processing step |" for i in range(9))
            + "\n" + target + "\n"
            + "\n".join(f"| appendix-{i} | unrelated appendix |" for i in range(9)))
    snippet, start, end = _focused_snippet(text, ("documentation transport boundary",), limit=160)
    assert target in snippet
    assert text[start:end] == snippet
    assert len(snippet) <= 160


def test_snippet_expansion_cannot_replace_an_already_visible_fact():
    from docmancer.docs.application.docs_context_projection import _expand_selected_snippets

    retained = "ALPHA_KEY requires a disk backup."
    raw = ("ALPHA_KEY uses memory buffers to process incoming requests.\n\n"
           + "Unrelated background explanation. " * 25 + "\n\n" + retained)
    source = _host_lookup_context_retrieval()["context_pack"][0]
    source.update(evidence_id="ev-retained", path_or_url=source["path"], snippet=retained,
                  retrieval_query_matches={"query-lookup-1": {
                      "query_text": "ALPHA_KEY", "query_terms": ["ALPHA_KEY"],
                      "exact_terms": ["ALPHA_KEY"], "qualified": True,
                  }})
    expanded = _expand_selected_snippets([source],
        projection_inputs={"ev-retained": (raw, ("ALPHA_KEY",), 1)},
        query_plan={"queries": [{"query_id": "query-lookup-1", "text": "ALPHA_KEY"}]},
        public_query_ids=("query-lookup-1",), max_tokens=800)
    assert retained in expanded[0]["snippet"]
    assert expanded[0]["snippet"] in raw


def test_complete_qualified_variant_precedes_mid_sentence_prefix():
    from docmancer.docs.application.docs_context_projection import _qualified_fragments

    raw = (
        "# Cleanup\n\n"
        "`clear-index` removes derived index state while preserving project\n"
        "sources, configuration, and unrelated files; it never\n"
        "silently widens the cleanup scope. The command is preview-only\n"
        "unless `--apply` is supplied.\n"
    )
    query = "Does clearing derived storage preserve source files and configuration?"
    source = {
        "evidence_id": "ev-cleanup",
        "path_or_url": "docs/cleanup.md",
        "snippet": raw,
        "project_identity": "git:example/project",
        "authority": "source_of_truth",
        "scope": "project",
        "catalog_role": "runbook",
        "retrieval_query_ids": ["query-lookup-2"],
        "retrieval_query_matches": {"query-lookup-2": {
            "query_text": query,
            "query_terms": ["clearing", "derived", "storage", "preserve", "source", "files", "configuration"],
            "qualified": True,
        }},
        "_qualification_candidate": {
            "source_class": "project_doc",
            "project_identity": "git:example/project",
            "freshness": "current",
            "index_freshness": "synchronized",
            "risk_flags": [],
            "lifecycle_status": "active",
        },
        "_expected_project_identity": "git:example/project",
        "_lifecycle_intent": "current",
    }
    variants = _qualified_fragments(
        source,
        raw_snippet=raw,
        query_ids={"query-lookup-2"},
        query_text={"query-lookup-2": query},
        source_line_start=1,
    )
    assert variants
    assert "silently widens the cleanup scope." in variants[0]["snippet"]
    assert variants[0]["snippet"] in raw


def test_frozen_cache_reset_keeps_preview_and_preserve_in_visible_context():
    from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    case = next(row for row in load_cases() if row["id"] == "v2-paraphrase-cache-reset")
    result = run(cases=(LiveCase(
        case_id=case["id"],
        question=case["question"],
        relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]),
        scope=case["scope"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    assert all(row["met"] for row in verdict["obligations"]), verdict["obligations"]
    assert verdict["semantic_useful"] is True
    assert verdict["false_full_coverage"] is False
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800


def test_frozen_architecture_infrastructure_boundary_enters_retrieval_candidates(monkeypatch):
    from docmancer.docs.application import _project_docs_service_part03 as retrieval
    from eval.project_context_quality_v2_protocol import load_cases
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    case = next(row for row in load_cases() if row["id"] == "v2-natural-architecture")
    captured = []
    tag = retrieval._tag_retrieval_query

    def observe(chunks, *args, **kwargs):
        result = tag(chunks, *args, **kwargs)
        if args and args[0] == "query-lookup-3":
            captured.extend(result)
        return result

    monkeypatch.setattr(retrieval, "_tag_retrieval_query", observe)
    run(cases=(LiveCase(
        case_id=case["id"], question=case["question"], relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]), scope=case["scope"],
    ),), negative_cases=())

    candidates = [
        chunk for chunk in captured
        if (chunk.metadata or {}).get("project_doc_path") == "docs/modules/project-context-retrieval.md"
        and "SQLite owns persistence and candidate generation" in chunk.text
    ]
    assert candidates, "the real infrastructure-boundary witness was lost before projection"
    trace = candidates[0].metadata["retrieval_query_matches"]["query-lookup-3"]
    assert trace["qualified"] is True


def test_frozen_request_flow_prefers_project_context_module_witnesses():
    from eval.project_context_quality_v2_protocol import evaluate_case, load_cases
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    case = next(row for row in load_cases() if row["id"] == "v2-natural-request-flow")
    result = run(cases=(LiveCase(
        case_id=case["id"], question=case["question"], relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]), scope=case["scope"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    assert "docs/modules/project-context-retrieval.md" in {
        source["path_or_url"] for source in payload["sources"]
    }
    assert all(row["met"] for row in verdict["obligations"]), verdict["obligations"]
    assert verdict["semantic_useful"] is True
    assert verdict["false_full_coverage"] is False
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800
