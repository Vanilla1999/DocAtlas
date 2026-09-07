from __future__ import annotations

from copy import deepcopy
import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.recovery import build_recovery_diagnosis
from docmancer.docs.application.model_visible_projection import (
    validate_model_visible_projection,
)


def _host_lookup_context_retrieval() -> dict:
    queries = [{
        "query_id": "query-original",
        "text": "Help me understand this project.",
        "origin": "original",
        "coverage_required": False,
    }]
    sources = []
    for index, topic in enumerate(
        ("purpose", "architecture", "data flow", "development", "testing"),
        start=1,
    ):
        query_id = f"query-lookup-{index}"
        query_text = f"project {topic} documentation"
        queries.append({
            "query_id": query_id,
            "text": query_text,
            "origin": "host_lookup",
            "coverage_required": False,
        })
        sources.append({
            "source_class": "project_doc",
            "path": f"docs/topic-{index}.md",
            "heading_path": topic.title(),
            "content": f"Project {topic} documentation gives a focused newcomer explanation.",
            "project_identity": "git:example/project",
            "authority": "source_of_truth",
            "doc_scope": "project",
            "lifecycle_status": "active",
            "freshness": "current",
            "index_freshness": "synchronized",
            "risk_flags": [],
            "retrieval_query_ids": [query_id],
            "retrieval_query_matches": {
                query_id: {
                    "qualified": True,
                    "mode": "and",
                    "query_text": query_text,
                },
            },
        })
    return {
        "context_pack": sources,
        "documentation_query_plan": {
            "query_ids": [item["query_id"] for item in queries],
            "required_query_ids": [],
            "queries": queries,
        },
    }


def test_projection_failure_is_not_reported_as_parser_uncertainty():
    for pack, reason in (([], "no_candidates"), ([{"content": "unrelated"}], "evidence_rejected")):
        diagnosis = build_recovery_diagnosis(
            "Tell me everything mysterious", None,
            projection={"status": "insufficient_evidence", "context_available": False},
            retrieval={"context_pack": pack},
        )
        assert diagnosis["reason_code"] == reason
        assert diagnosis["origin"] != "parsing"


def test_docs_context_keeps_distinct_host_lookup_sources_until_source_limit():
    projection, snapshot = project_docs_context(
        retrieval=_host_lookup_context_retrieval(),
    )

    assert projection["kind"] == "docs_context"
    assert projection["answer_supported"] is False
    assert projection["edit_ready"] is False
    assert len(projection["sources"]) == 3
    assert projection["covered_query_ids"] == [
        "query-lookup-1", "query-lookup-2", "query-lookup-3",
    ]
    assert projection["missing_query_ids"] == [
        "query-original", "query-lookup-4", "query-lookup-5",
    ]
    assert projection["estimated_tokens"] <= 800
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800,
    ) == []


def test_docs_context_host_lookup_selection_is_not_a_global_latch():
    projection, _snapshot = project_docs_context(
        retrieval=_host_lookup_context_retrieval(), max_tokens=2_000,
    )

    assert len(projection["sources"]) == 3
    assert projection["covered_query_ids"] == [
        "query-lookup-1", "query-lookup-2", "query-lookup-3",
    ]
    assert projection["estimated_tokens"] <= 800


def test_docs_context_compacts_snippets_before_sacrificing_lookup_coverage():
    retrieval = _host_lookup_context_retrieval()
    for index, source in enumerate(retrieval["context_pack"], start=1):
        source["content"] = (
            "General background information for a new contributor. " * 20
            + source["content"]
            + " Additional implementation background for maintainers. " * 20
            + f" Stable topic marker {index}."
        )

    projection, snapshot = project_docs_context(retrieval=retrieval)

    assert len(projection["sources"]) == 3
    assert projection["covered_query_ids"] == [
        "query-lookup-1", "query-lookup-2", "query-lookup-3",
    ]
    assert all(len(source["snippet"]) >= 40 for source in projection["sources"])
    assert projection["estimated_tokens"] <= 800
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800,
    ) == []


def test_docs_context_compacts_long_sources_with_generated_facet_diagnostics():
    retrieval = _host_lookup_context_retrieval()
    for index, source in enumerate(retrieval["context_pack"], start=1):
        source["content"] = (
            f"Project topic {index} documentation " * 80
            + f"Stable newcomer conclusion for topic {index}."
        )
    retrieval["documentation_query_plan"]["public_query_ids"] = [
        "query-original", *(f"query-lookup-{index}" for index in range(1, 6)),
    ]
    for index in range(1, 5):
        retrieval["documentation_query_plan"]["queries"].append({
            "query_id": f"query-intent-{index}",
            "text": f"Generated diagnostic facet question {index}",
            "origin": "canonical_intent",
            "coverage_required": False,
            "facet_id": f"intent-context:facet-{index}",
        })

    projection, snapshot = project_docs_context(retrieval=retrieval)

    assert len(projection["sources"]) >= 2
    assert len(set(projection["covered_query_ids"])) >= 2
    assert not any(
        query_id.startswith("query-intent-")
        for query_id in projection["missing_query_ids"]
    )
    assert projection["estimated_tokens"] <= 800
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800,
    ) == []


def test_docs_context_rejects_match_found_only_in_hidden_retrieval_metadata():
    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    source["content"] = "This visible paragraph discusses an unrelated release note."
    source["retrieval_query_matches"]["query-lookup-1"].update({
        "query_terms": ["project", "purpose", "documentation"],
        "field_matches": {
            "title": [],
            "body": [],
            "retrieval_text": ["project", "purpose", "documentation"],
        },
    })
    retrieval["context_pack"] = [source]

    projection, _snapshot = project_docs_context(retrieval=retrieval)

    assert projection["status"] == "insufficient_evidence"
    assert projection["context_available"] is False


def test_multiple_lookups_try_320_before_rejecting_exact_witness():
    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    source["content"] = "ALPHA_KEY " + "neutral " * 25 + "OMEGA_KEY enables storage."
    source["line_start"] = 10
    trace = source["retrieval_query_matches"]["query-lookup-1"]
    trace.update(query_text="ALPHA_KEY OMEGA_KEY", query_terms=["ALPHA_KEY", "OMEGA_KEY"],
                 exact_terms=["ALPHA_KEY", "OMEGA_KEY"])
    retrieval["documentation_query_plan"]["queries"][1]["text"] = trace["query_text"]
    retrieval["context_pack"] = [source]
    projection, snapshot = project_docs_context(retrieval=retrieval)
    assert "query-lookup-1" in projection.get("covered_query_ids", [])
    assert "OMEGA_KEY" in projection["sources"][0]["snippet"]
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_long_markdown_table_projection_keeps_matching_row_complete():
    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    target_row = "| request-flow | MCP input reaches qualified source selection |"
    source["content"] = (
        "| Stage | Behavior |\n| --- | --- |\n"
        + "".join(f"| background-{index} | unrelated operational detail |\n" for index in range(20))
        + target_row
        + "\n"
        + "".join(f"| appendix-{index} | unrelated maintenance detail |\n" for index in range(20))
    )
    trace = source["retrieval_query_matches"]["query-lookup-1"]
    trace.update(
        query_text="request-flow qualified source selection",
        query_terms=["request-flow", "qualified", "source", "selection"],
        exact_terms=["request-flow"],
    )
    retrieval["documentation_query_plan"]["queries"][1]["text"] = trace["query_text"]
    retrieval["context_pack"] = [source]

    projection, snapshot = project_docs_context(retrieval=retrieval)

    assert target_row in projection["sources"][0]["snippet"]
    assert projection["sources"][0]["snippet"].count("request-flow") == 1
    assert validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=800,
    ) == []


def test_independent_exact_partial_context_is_not_globally_discarded():
    retrieval = _host_lookup_context_retrieval()
    plan = retrieval["documentation_query_plan"]
    plan["original_question"] = "Explain exact ALPHA_KEY and MISSING_KEY"
    plan["required_query_ids"] = ["query-original"]
    plan["queries"] = [
        {"query_id": "query-original", "text": plan["original_question"], "origin": "original"},
        {"query_id": "query-anchor-1", "text": "ALPHA_KEY", "origin": "exact_anchor"},
        {"query_id": "query-anchor-2", "text": "MISSING_KEY", "origin": "exact_anchor"},
    ]
    source = retrieval["context_pack"][0]
    source["content"] = "ALPHA_KEY enables durable storage."
    source["retrieval_query_matches"] = {
        "query-anchor-1": {"qualified": True, "query_text": "ALPHA_KEY", "exact_terms": ["ALPHA_KEY"]},
    }
    retrieval["context_pack"] = [source]
    projection, snapshot = project_docs_context(retrieval=retrieval)
    assert projection["context_available"] is True
    assert projection["covered_query_ids"] == ["query-anchor-1"]
    assert "query-anchor-2" in projection["missing_query_ids"]
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_second_lookup_does_not_remove_first_lookup_witness():
    from copy import deepcopy

    retrieval = _host_lookup_context_retrieval()
    retrieval["context_pack"] = retrieval["context_pack"][:2]
    source = retrieval["context_pack"][0]
    source["content"] = "ALPHA_KEY " + "neutral " * 25 + "OMEGA_KEY enables storage."
    source["retrieval_query_matches"]["query-lookup-1"].update(
        query_text="ALPHA_KEY OMEGA_KEY", exact_terms=["ALPHA_KEY", "OMEGA_KEY"],
    )
    retrieval["documentation_query_plan"]["queries"][1]["text"] = "ALPHA_KEY OMEGA_KEY"
    single = deepcopy(retrieval)
    single["context_pack"] = single["context_pack"][:1]
    single["documentation_query_plan"]["queries"] = single["documentation_query_plan"]["queries"][:2]
    first, _ = project_docs_context(retrieval=single)
    compound, snapshot = project_docs_context(retrieval=retrieval)
    assert set(first["covered_query_ids"]) <= set(compound["covered_query_ids"])
    assert "query-lookup-2" in compound["covered_query_ids"]
    assert validate_model_visible_projection(compound, snapshot=snapshot, max_tokens=800) == []


def test_expansion_preserves_each_previously_selected_witness():
    from docmancer.docs.application.docs_context_projection import _expand_selected_snippets

    source = {
        "evidence_id": "witness", "snippet": "ALPHA_KEY is enabled.",
        "retrieval_query_matches": {
            "query-lookup-1": {"qualified": True, "query_text": "ALPHA_KEY", "exact_terms": ["ALPHA_KEY"]},
        },
    }
    expanded = _expand_selected_snippets(
        [source], projection_inputs={"witness": (
            "ALPHA_KEY is enabled.\n\n" + "Other unrelated background notes " * 30,
            ("unrelated background notes",), 1,
        )},
        query_plan={"queries": [{"query_id": "query-lookup-1", "text": "ALPHA_KEY"}]},
        public_query_ids=("query-lookup-1",), max_tokens=800,
    )
    assert expanded[0]["retrieval_query_matches"]["query-lookup-1"]["qualified"] is True
    assert "ALPHA_KEY" in expanded[0]["snippet"]


def test_recovery_uses_actual_projection_budget_rejection():
    retrieval = _host_lookup_context_retrieval()
    # A compact payload no longer carries redundant prose instructions; use a
    # budget below the minimum source envelope rather than the old 256 boundary.
    projection, _ = project_docs_context(retrieval=retrieval, max_tokens=200)
    assert projection["context_available"] is False
    diagnosis = build_recovery_diagnosis("Uncertain project overview", None,
                                         projection=projection, retrieval=retrieval)
    assert diagnosis["reason_code"] == "bounded_selection_failed"


def test_unknown_exact_original_claim_fails_closed_without_erasing_independent_source():
    retrieval = _host_lookup_context_retrieval()
    retrieval["context_pack"] = retrieval["context_pack"][:1]
    source = retrieval["context_pack"][0]
    source["retrieval_query_matches"]["query-original"] = {
        "qualified": True, "query_text": "Explain project purpose documentation UNKNOWN_KEY",
    }
    retrieval["documentation_query_plan"]["queries"][0]["text"] = "Explain project purpose documentation UNKNOWN_KEY"
    projection, _ = project_docs_context(retrieval=retrieval)
    assert projection["context_available"] is True
    assert "query-original" not in projection["covered_query_ids"]
    assert "query-lookup-1" in projection["covered_query_ids"]


def test_smaller_qualified_variant_fits_when_best_coverage_variant_does_not():
    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    source["content"] = (
        "ALPHA_KEY " + "neutral " * 25 + "OMEGA_KEY enables storage. "
        + "ordinary " * 20 + "SIGMA_KEY enables caching."
    )
    source["line_start"] = 7
    source["retrieval_query_matches"] = {}
    for index, terms in enumerate((
        ["ALPHA_KEY", "OMEGA_KEY"], ["ALPHA_KEY", "OMEGA_KEY", "SIGMA_KEY"],
    ), start=1):
        text = " ".join(terms)
        source["retrieval_query_matches"][f"query-lookup-{index}"] = {
            "qualified": True, "query_text": text, "exact_terms": terms,
        }
        retrieval["documentation_query_plan"]["queries"][index]["text"] = text
    retrieval["context_pack"] = [source]
    full, _ = project_docs_context(retrieval=retrieval)
    # Exercise the actual serialization boundary, not a stale fixed cost that
    # depended on the removed prose instruction in docs_context.
    budget = full["estimated_tokens"] - 1
    bounded, snapshot = project_docs_context(retrieval=retrieval, max_tokens=budget)
    assert full["covered_query_ids"] == ["query-lookup-1", "query-lookup-2"]
    assert full["estimated_tokens"] > budget
    assert bounded["covered_query_ids"] == ["query-lookup-1"]
    snippet = bounded["sources"][0]["snippet"]
    assert 160 < len(snippet) <= 320
    assert snippet in source["content"]
    assert bounded["estimated_tokens"] <= budget
    assert validate_model_visible_projection(bounded, snapshot=snapshot, max_tokens=budget) == []


def test_duplicate_evidence_never_joins_noncontiguous_fragments():
    from copy import deepcopy

    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    source.update(content="ALPHA_KEY enables storage.\n\n" + "Neutral background. " * 60
                  + "\n\nSIGMA_KEY enables caching.", line_start=10, stable_id="same-source")
    source["retrieval_query_matches"] = {
        "query-lookup-1": {"qualified": True, "query_text": "ALPHA_KEY", "exact_terms": ["ALPHA_KEY"]},
    }
    duplicate = deepcopy(source)
    duplicate["retrieval_query_matches"] = {
        "query-lookup-2": {"qualified": True, "query_text": "SIGMA_KEY", "exact_terms": ["SIGMA_KEY"]},
    }
    retrieval["context_pack"] = [source, duplicate]
    for index, text in enumerate(("ALPHA_KEY", "SIGMA_KEY"), start=1):
        retrieval["documentation_query_plan"]["queries"][index]["text"] = text
    projection, snapshot = project_docs_context(retrieval=retrieval)
    assert projection["covered_query_ids"] == ["query-lookup-1"]
    assert all(item["snippet"] in source["content"] for item in projection["sources"])
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_complete_320_code_fence_survives_multiple_lookups():
    retrieval = _host_lookup_context_retrieval()
    source = retrieval["context_pack"][0]
    source["content"] = "```python\nALPHA_KEY = '" + "x" * 200 + "'\n```"
    source["retrieval_query_matches"] = {
        "query-lookup-1": {"qualified": True, "query_text": "ALPHA_KEY", "exact_terms": ["ALPHA_KEY"]},
    }
    retrieval["documentation_query_plan"]["queries"][1]["text"] = "ALPHA_KEY"
    retrieval["context_pack"] = [source]
    projection, snapshot = project_docs_context(retrieval=retrieval)
    assert projection["sources"][0]["snippet"] == source["content"]
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_recovery_reports_rejected_evidence_from_actual_projection():
    for change in ({"project_identity": "git:foreign/project"}, {"freshness": "stale"},
                   {"risk_flags": ["instruction_risk"]}, {"content": "Unrelated material only."}):
        retrieval = _host_lookup_context_retrieval()
        retrieval["project_identity"] = "git:example/project"
        retrieval["context_pack"] = retrieval["context_pack"][:1]
        retrieval["context_pack"][0].update(change)
        projection, snapshot = project_docs_context(retrieval=retrieval)
        assert projection["context_available"] is False
        assert snapshot == {}
        diagnosis = build_recovery_diagnosis("Uncertain project overview", None,
                                             projection=projection, retrieval=retrieval)
        assert diagnosis["reason_code"] == "evidence_rejected"


def _alias_fragment_retrieval():
    retrieval = _host_lookup_context_retrieval()
    queries = [
        ("query-lookup-1", "amber bronze cobalt denim", "host_lookup"),
        ("query-lookup-2", "ember frost glacier hazel", "host_lookup"),
        ("query-intent-1", "alpha beta", "canonical_intent"),
        ("query-intent-2", "alpha", "canonical_intent"),
    ]
    retrieval["documentation_query_plan"] = {
        "required_query_ids": [], "public_query_ids": ["query-lookup-1", "query-lookup-2"],
        "queries": [{"query_id": key, "text": text, "origin": origin, "facet_id": key}
                    for key, text, origin in queries],
    }
    source = retrieval["context_pack"][0]
    source["content"] = (
        "alpha beta amber bronze.\n\n" + "Unrelated prose for background. " * 20
        + "\n\nThe amber bronze cobalt denim procedure combines ember frost glacier hazel for the complete operation."
    )
    source["retrieval_query_matches"] = {
        key: {"qualified": True, "query_text": text} for key, text, _ in queries
    }
    source["line_start"] = 1
    retrieval["context_pack"] = [source]
    return retrieval


def test_fragment_rank_prefers_public_coverage_over_generated_aliases():
    projection, snapshot = project_docs_context(retrieval=_alias_fragment_retrieval())
    assert projection["covered_query_ids"] == ["query-lookup-1", "query-lookup-2"]
    assert projection["sources"][0]["snippet"].startswith("The amber bronze")
    assert all(item["status"] == "missing" for item in projection["facets"]
               if item["id"].startswith("query-intent-"))
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_expansion_can_drop_optional_aliases_without_losing_public_witnesses():
    from docmancer.docs.application.docs_context_projection import _expand_selected_snippets, _requalify_visible_source

    retrieval = _alias_fragment_retrieval()
    raw = retrieval["context_pack"][0]
    queries = retrieval["documentation_query_plan"]["queries"]
    source = _requalify_visible_source({**raw, "evidence_id": "witness",
                                       "snippet": "alpha beta amber bronze."},
                                      query_text={q["query_id"]: q["text"] for q in queries})
    result = _expand_selected_snippets(
        [source], projection_inputs={"witness": (raw["content"], (queries[1]["text"],), 1)},
        query_plan=retrieval["documentation_query_plan"],
        public_query_ids=("query-lookup-1", "query-lookup-2"), max_tokens=800,
    )
    matches = result[0]["retrieval_query_matches"]
    assert matches["query-lookup-1"]["qualified"] is True
    assert matches["query-lookup-2"]["qualified"] is True
    assert matches["query-intent-1"]["qualified"] is False


def test_focused_intro_keeps_associated_complete_command():
    from docmancer.docs.application.docs_context_projection import _focused_snippet

    text = "Install the utility using the following command.\n\n```bash\nrunner add sample-tool\n```"
    snippet, start, end = _focused_snippet(text, ("install utility",), limit=160)
    assert snippet == text == text[start:end]
    smaller, _, _ = _focused_snippet(text, ("install utility",), limit=55)
    assert smaller == text.split("\n\n")[0]


def test_candidate_order_uses_accepted_visible_coverage_not_raw_matches():
    retrieval = _host_lookup_context_retrieval()
    terms = ("ALPHA_KEY", "BETA_KEY", "GAMMA_KEY")
    queries = [{"query_id": f"query-anchor-{index}", "text": term, "origin": "exact_anchor"}
               for index, term in enumerate(terms)]
    retrieval["documentation_query_plan"] = {"queries": queries, "required_query_ids": []}
    template = retrieval["context_pack"][0]
    sources = []
    for index, selected in enumerate((terms, terms[:1], terms[:1], terms[1:2], terms[2:])):
        source = deepcopy(template)
        source["path"] = f"docs/witness-{index}.md"
        source["content"] = ("\n\n" + "Unrelated background. " * 30 + "\n\n").join(
            f"{term} enables storage." for term in selected)
        source["retrieval_query_matches"] = {
            query["query_id"]: {"qualified": True, "query_text": query["text"], "exact_terms": [query["text"]]}
            for query in queries if query["text"] in selected
        }
        sources.append(source)
    retrieval["context_pack"] = sources
    projection, snapshot = project_docs_context(retrieval=retrieval)
    assert projection["covered_query_ids"] == [query["query_id"] for query in queries]
    assert len(projection["sources"]) == 3
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_three_novel_public_witnesses_can_share_one_document_path():
    retrieval = _host_lookup_context_retrieval()
    retrieval["context_pack"] = retrieval["context_pack"][:3]
    for source in retrieval["context_pack"]:
        source["path"] = "docs/guide.md"
    projection, snapshot = project_docs_context(retrieval=retrieval)
    assert projection["covered_query_ids"] == [f"query-lookup-{index}" for index in range(1, 4)]
    assert len(projection["sources"]) == 3
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("fence,closed", [("```", True), ("~~~", True), ("```", False)])
def test_oversized_code_fence_is_not_returned_as_a_broken_fragment(fence, closed):
    from docmancer.docs.application.docs_context_projection import _focused_snippet

    text = fence + "python\nALPHA_KEY = '" + "x" * 600 + "'\n" + (fence if closed else "")
    snippet, start, end = _focused_snippet(text, ("ALPHA_KEY",), limit=160)
    assert snippet == "" or snippet == text
    assert snippet == text[start:end]


def test_public_recovery_uses_same_call_projection_without_canonical_selection(monkeypatch):
    from docmancer.docs.interfaces.mcp import context_tools
    from tests.docs._shared_test_model_visible_projection import call_docs_tool_payload

    calls = []
    original = context_tools.project_docs_context

    def capture(**kwargs):
        result = original(**kwargs)
        calls.append(result)
        return result

    monkeypatch.setattr(context_tools, "project_docs_context", capture)

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "mode_selected": "project", "context_pack": [],
                "recovery_origin": "parsing", "recovery_reason_code": "question_parse_uncertain",
            }

    payload = call_docs_tool_payload("get_docs_context", {
        "question": "Tell me everything mysterious", "project_path": "/repo",
    }, Facade())
    assert len(calls) == 1
    assert calls[0][0]["context_available"] is False
    assert calls[0][1] == {}
    assert payload["recommended_next_action"]["reason"] == "no_candidates"
    assert payload["recommended_next_action"]["repeat_docs_context"] is False
    assert "question_parse_uncertain" not in str(payload)
