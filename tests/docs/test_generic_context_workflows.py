"""Real local indexing through the public handler, without evaluator gold inputs."""
import pytest
from pprint import pformat

from eval.evidence_quality_v2.runtime import index_project, isolated_service
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.docs.interfaces.mcp import context_tools


@pytest.mark.parametrize("topic,question,lookups,facts", [
    ("commands", "How do I set up Lumen, ingest local files, and query the index?",
     ["Lumen setup", "Lumen ingest local files", "Lumen query index"],
     ["Run `lumen setup` to create the configuration and database.",
      "Run `lumen ingest ./notes` to index local files.",
      'Run `lumen query "topic"` to search the index.']),
    ("contributing", "What should I read before contributing to Lumen, and which tests should I run?",
     ["Lumen contributor reading", "Lumen contributor tests"],
     ["Lumen contributor reading starts with README.md and design.md.",
      "Lumen contributor tests run with `pytest tests/` before review."]),
    ("catalog", "How does Lumen use its documentation catalog, and what happens when the catalog is invalid?",
     ["Lumen documentation catalog ownership", "Lumen invalid catalog behavior"],
     ["The Lumen documentation catalog declares document ownership and authority.",
      "An invalid Lumen catalog blocks retrieval until the catalog is repaired; ownership is never guessed."]),
])
def test_generic_workflow_facts_survive_real_index(tmp_path, monkeypatch, topic, question, lookups, facts):
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Lumen\n\nLumen indexes local documentation.\n")
    (project / f"{topic}.md").write_text(
        f"# Lumen {topic}\n\n" + "\n\n".join(f"## Step {index}\n\n{fact}" for index, fact in enumerate(facts, 1)) + "\n")
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\ndocuments:\n" + "".join(
            f"  - path: {path}\n    role: runbook\n    scope: project\n"
            "    description: Lumen local workflow.\n    authority: source_of_truth\n"
            "    status: active\n    impact: track\n"
            for path in ("README.md", f"{topic}.md")))
    with isolated_service(tmp_path / "state") as (service, config):
        preparation = index_project(service, config, project)
        assert preparation["expected_paths"] == sorted(("README.md", f"{topic}.md"))
        assert preparation["indexed_paths"] == preparation["expected_paths"]
        assert preparation["excluded_or_failed_paths"] == []
        assert preparation["unexpected_paths"] == []
        observed = {}
        project_context = context_tools.project_docs_context
        def capture(**kwargs):
            observed["candidates"] = [(row.get("path"), row.get("content"), row.get("retrieval_query_matches"))
                                      for row in kwargs["retrieval"].get("context_pack", [])]
            return project_context(**kwargs)
        monkeypatch.setattr(context_tools, "project_docs_context", capture)
        payload = call_docs_tool_payload("get_docs_context", {
            "question": question, "lookup_queries": lookups, "project_path": str(project), "scope": "project",
        }, service)
        visible = "\n".join(source["snippet"] for source in payload.get("sources", [])
                            if source["path_or_url"] == f"{topic}.md")
        assert all(fact in visible for fact in facts), pformat({"missing": [fact for fact in facts if fact not in visible], "payload": payload, "observed": observed})
        assert payload["answer_supported"] is False and payload["edit_ready"] is False


def test_first_session_live_query(monkeypatch):
    from copy import deepcopy
    from eval.project_context_quality_v2_protocol import load_cases, validate_corpus, evaluate_case
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    validate_corpus()
    case = next(row for row in load_cases() if row["id"] == "v2-natural-first-session")
    captured = []
    project_context = context_tools.project_docs_context

    def observe(**kwargs):
        captured.append(deepcopy(kwargs["retrieval"]))
        return project_context(**kwargs)

    monkeypatch.setattr(context_tools, "project_docs_context", observe)
    result = run(cases=(LiveCase(
        question=case["question"], relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]), case_id=case["id"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    candidate = next(row for row in captured[-1]["context_pack"]
                     if row["path"] == "wiki/Commands.md" and 'doc-atlas query "<text>"' in row["content"])
    assert candidate["path"] == "wiki/Commands.md"
    assert candidate["retrieval_query_matches"]["query-lookup-3"]["qualified"] is True
    assert 'doc-atlas query "<text>"' in candidate["content"]
    assert payload["diagnostics"]["observer_counts"] == {"retrieval_calls": 1, "validation_calls": 1}
    assert next(row for row in verdict["obligations"] if row["id"] == "query")["met"], "missing query witness in first-session public payload"
    assert verdict["semantic_useful"] is True
    assert all(verdict["hard_gates"].values())
    assert verdict["false_full_coverage"] is False




def test_contributor_live_reading_and_tests():
    from eval.project_context_quality_v2_protocol import load_cases, validate_corpus, evaluate_case
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    validate_corpus()
    case = next(row for row in load_cases() if row["id"] == "v2-natural-contributor")
    result = run(cases=(LiveCase(
        question=case["question"], relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]), case_id=case["id"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    assert payload["diagnostics"]["observer_counts"] == {"retrieval_calls": 1, "validation_calls": 1}
    assert all(row["met"] for row in verdict["obligations"]), verdict["obligations"]
    assert verdict["semantic_useful"] is True and all(verdict["hard_gates"].values())
    assert verdict["false_full_coverage"] is False
    assert payload["answer_supported"] is False and payload["edit_ready"] is False


@pytest.mark.parametrize("case_id", [
    "v2-natural-offline", "v2-paraphrase-local-trial",
])
def test_remaining_live_workflow_witnesses(case_id, monkeypatch):
    import hashlib
    from eval.project_context_quality_v2_protocol import load_cases, validate_corpus, evaluate_case
    from scripts.run_project_docs_self_host_gate import LiveCase, run
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection

    validate_corpus()
    case = next(row for row in load_cases() if row["id"] == case_id)
    captured = {}
    project_context = context_tools.project_docs_context

    def observe(**kwargs):
        payload, snapshot = project_context(**kwargs)
        captured.update(payload=payload, snapshot=snapshot)
        return payload, snapshot

    monkeypatch.setattr(context_tools, "project_docs_context", observe)
    result = run(cases=(LiveCase(
        question=case["question"], relevant_paths=(), scope=case["scope"],
        lookup_queries=tuple(case["lookup_queries"]), case_id=case["id"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    assert payload["diagnostics"]["observer_counts"] == {"retrieval_calls": 1, "validation_calls": 1}
    assert all(row["met"] for row in verdict["obligations"]), verdict["obligations"]
    assert verdict["semantic_useful"] is True and all(verdict["hard_gates"].values())
    assert verdict["false_full_coverage"] is False
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert validate_model_visible_projection(
        captured["payload"], snapshot=captured["snapshot"], max_tokens=800,
    ) == []
    for source in payload["sources"]:
        original = captured["snapshot"][source["evidence_id"]]["source"]
        assert original["stable_chunk_id"] and original["parent_logical_id"]
        assert original["path"] == source["path_or_url"]
        assert original["project_identity"] == source["project_identity"]
        text = original["content"]
        assert hashlib.sha256(text.encode()).hexdigest() == original["display_content_hash"]
        assert original["char_end"] - original["char_start"] == len(text)
        start = text.index(source["snippet"])
        assert source["line_start"] == original["line_start"] + text[:start].count("\n")
        assert source["line_end"] == source["line_start"] + source["snippet"].count("\n")




@pytest.mark.parametrize("query", ['"rather than"', '`rather than`', "rather than", "rather than?"])
def test_literal_or_connector_only_query_is_not_erased(tmp_path, query):
    from tests.test_sqlite_ranking_truth import _store, _doc

    store = _store(tmp_path, [_doc("usage.md", "Usage", "Use rather than for a contrast.")])
    results = store.query(query, limit=4, budget=2000)
    assert results and "rather than" in results[0].text


def test_contrast_missing_exact_subject_remains_unqualified(tmp_path):
    from tests.test_sqlite_ranking_truth import _store, _doc
    from docmancer.docs.domain.evidence_qualification import qualify_evidence

    store = _store(tmp_path, [_doc("other.md", "Ownership", "Gadgets own the records.")])
    result = store.query("Does WidgetStore own records rather than gadgets?", limit=4, budget=2000)[0]
    trace = result.metadata["lexical_match"]
    assert "widgetstore" in trace["missing_exact_terms"]
    assert not qualify_evidence(trace, query_id="q", visible_text=result.text).qualified


def test_real_architecture_boundary_enters_candidates_without_borrowed_coverage(monkeypatch):
    from docmancer.docs.application import _project_docs_service_part03 as retrieval
    from eval.project_context_quality_v2_protocol import load_cases, evaluate_case
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    case = next(c for c in load_cases() if c["id"] == "v2-natural-architecture")
    captured = []
    tag = retrieval._tag_retrieval_query

    def observe(chunks, *args, **kwargs):
        result = tag(chunks, *args, **kwargs)
        if args[0] == "query-lookup-3":
            captured.extend(result)
        return result

    monkeypatch.setattr(retrieval, "_tag_retrieval_query", observe)
    result = run(cases=(LiveCase(
        question=case["question"], relevant_paths=(), scope=case["scope"],
        lookup_queries=tuple(case["lookup_queries"]), case_id=case["id"],
    ),), negative_cases=())
    candidates = [c for c in captured if "SQLite owns persistence and" in c.text]
    assert candidates, "real infrastructure boundary was lost before qualification"
    candidate = candidates[0]
    assert candidate.metadata["project_doc_path"] == "docs/modules/project-context-retrieval.md"
    trace = candidate.metadata["retrieval_query_matches"]["query-lookup-3"]
    assert trace["query_text"] == case["lookup_queries"][2]
    assert trace["qualified"] is False
    assert trace["matched_terms"] == ["evidence", "qualification"]
    assert "rather" in trace["query_terms"] and "than" in trace["query_terms"]
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    assert all(verdict["hard_gates"].values()) and not verdict["false_full_coverage"]
    assert not payload["answer_supported"] and not payload["edit_ready"]



