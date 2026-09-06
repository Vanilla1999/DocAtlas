"""Real local indexing through the public handler, without evaluator gold inputs."""
import pytest
from pprint import pformat

from tests.docs.test_question_frame_paraphrase_e2e import _service
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
    service = _service(tmp_path, monkeypatch)
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"
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
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800


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


@pytest.mark.parametrize("identity", ["git:example/lumen", "git:example/foreign"])
def test_disjoint_action_witnesses_keep_identity_and_residue(identity):
    from copy import deepcopy
    from docmancer.docs.application.docs_context_projection import project_docs_context
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection

    facts = ("Load records using `lumen put`.", "Scan entries using `lumen seek`.")
    content = facts[0] + "\n\n" + "Unrelated background details. " * 40 + "\n\n" + facts[1]
    queries = [("query-original", "Explain the undisclosed retention guarantee.", "original"),
               ("query-lookup-1", "How do I load records?", "host_lookup"),
               ("query-lookup-2", "How can I scan entries?", "host_lookup")]
    source = {
        "source_class": "project_doc", "project_identity": identity,
        "path": "docs/actions.md", "title": "Actions", "line_start": 1,
        "authority": "source_of_truth", "lifecycle_status": "active",
        "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
        "doc_scope": "project", "content": content,
        "retrieval_query_matches": {
            query_id: {"query_text": text, "query_terms": terms, "lexical_score": 1.0}
            for (query_id, text, _), terms in zip(queries[1:], (["load", "records"], ["scan", "entries"]))
        },
    }
    payload, snapshot = project_docs_context(retrieval={
        "project_identity": "git:example/lumen", "context_pack": [source],
        "documentation_query_plan": {
            "original_question": queries[0][1], "unresolved_parts": ["retention guarantee"],
            "queries": [{"query_id": query_id, "text": text, "origin": origin}
                        for query_id, text, origin in queries],
        },
    })
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert payload["answer_supported"] is False
    if identity != "git:example/lumen":
        assert not payload.get("sources")
        return
    assert len(payload["sources"]) == 2
    assert all(any(fact in row["snippet"] for row in payload["sources"]) for fact in facts)
    assert len({row["evidence_id"] for row in payload["sources"]}) == 2
    assert payload["missing_query_ids"] == ["query-original"]
    assert payload["query_coverage"] == "partial"
    for row in payload["sources"]:
        assert row["snippet"] in content
        assert row["line_start"] == 1 + content[:content.index(row["snippet"])].count("\n")
    tampered = deepcopy(payload)
    tampered["sources"][1]["evidence_id"] = payload["sources"][0]["evidence_id"]
    assert validate_model_visible_projection(tampered, snapshot=snapshot, max_tokens=800)
    clipped = deepcopy(payload)
    clipped["sources"][1]["snippet"] = "Scan"
    assert validate_model_visible_projection(clipped, snapshot=snapshot, max_tokens=800)


@pytest.mark.parametrize("visible_action", [True, False])
def test_procedural_lookup_prefers_visible_action_not_parent_text(visible_action):
    from docmancer.docs.application.docs_context_projection import project_docs_context

    base = {
        "source_class": "project_doc", "project_identity": "git:example/lumen",
        "authority": "source_of_truth", "lifecycle_status": "active",
        "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
        "doc_scope": "project", "title": "Rotate logs",
    }
    overview = "The rotate logs operation is described in the storage overview."
    instruction = "Rotate logs using `lumen cycle`."
    sources = [{**base, "path": path, "content": text,
                "retrieval_query_matches": {"query-lookup-1": {
                    "query_text": "How should I rotate logs?", "query_terms": ["rotate", "logs"],
                    "lexical_score": score}}}
               for path, text, score in (("docs/overview.md", overview, 100.0),
                                         ("docs/action.md", instruction if visible_action else overview, 1.0))]
    sources[1]["parent_content"] = instruction
    payload, _ = project_docs_context(retrieval={
        "context_pack": sources,
        "documentation_query_plan": {"queries": [{
            "query_id": "query-lookup-1", "text": "How should I rotate logs?", "origin": "host_lookup",
        }]},
    })
    assert payload["sources"][0]["path_or_url"] == ("docs/action.md" if visible_action else "docs/overview.md")


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
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800


@pytest.mark.parametrize("term,text,exact,expected", [
    ("rotating", "rotating logs", False, True),
    ("loading", "load records", False, True),
    ("indexed", "index records", False, True),
    ("loading", "load records", True, False),
    ("indexed", "index records", True, False),
    ("loading", "preload records", False, False),
    ("loading", "loadshed records", False, False),
    ("thing", "th records", False, False),
])
def test_visible_inflections_preserve_exactness_and_boundaries(term, text, exact, expected):
    from docmancer.docs.domain.evidence_qualification import _visible_term_present

    assert _visible_term_present(term, text, exact=exact) is expected


def test_catalog_live_invalid_behavior(monkeypatch):
    from eval.project_context_quality_v2_protocol import load_cases, validate_corpus, evaluate_case
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    validate_corpus()
    case = next(row for row in load_cases() if row["id"] == "v2-natural-catalog")
    captured = []
    project_context = context_tools.project_docs_context

    def observe(**kwargs):
        captured.append(kwargs["retrieval"])
        return project_context(**kwargs)

    monkeypatch.setattr(context_tools, "project_docs_context", observe)
    result = run(cases=(LiveCase(
        question=case["question"], relevant_paths=(),
        lookup_queries=tuple(case["lookup_queries"]), case_id=case["id"],
    ),), negative_cases=())
    payload = result["results"][0]["payload"]
    verdict = evaluate_case(case, payload)
    candidate = next(row for row in captured[-1]["context_pack"]
                     if "without pruning the existing index" in row["content"])
    assert candidate["retrieval_query_matches"]["query-lookup-2"]["qualified"] is True
    assert all(row["met"] for row in verdict["obligations"]), verdict["obligations"]
    assert verdict["semantic_useful"] is True and all(verdict["hard_gates"].values())
    assert verdict["false_full_coverage"] is False
    assert payload["diagnostics"]["observer_counts"] == {"retrieval_calls": 1, "validation_calls": 1}
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800
