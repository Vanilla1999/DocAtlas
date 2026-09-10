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


def test_stale_health_live_status_sync_and_removal(monkeypatch):
    from eval.project_context_quality_v2_protocol import load_cases, validate_corpus, evaluate_case, _witness_visible
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    validate_corpus()
    case = next(row for row in load_cases() if row["id"] == "v2-natural-stale-health")
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
    health = next(row for row in captured[-1]["context_pack"]
                  if row["path"] == "README.md" and "Explicit health, freshness" in row["content"])
    # Keep both frozen obligations in one qualified candidate; do not require
    # a particular pre-chunking paragraph or Markdown emphasis presentation.
    sync_obligations = [item for item in case["obligations"] if item["id"] in {"sync", "stale"}]
    assert len(sync_obligations) == 2
    sync = next(row for row in captured[-1]["context_pack"]
                if row["path"] == "docs/project-docs-mcp-workflow.md"
                and all(any(
                    witness["path"] == row["path"]
                    and _witness_visible(witness["text"], row["content"])
                    for witness in obligation["accepted_witnesses"]
                ) for obligation in sync_obligations))
    assert health["retrieval_query_matches"]["query-lookup-1"]["qualified"] is True
    assert sync["retrieval_query_matches"]["query-lookup-2"]["qualified"] is True
    assert all(verdict["hard_gates"].values())
    assert verdict["false_full_coverage"] is False
    assert payload["diagnostics"]["observer_counts"] == {"retrieval_calls": 1, "validation_calls": 1}
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert "query-original" in payload["missing_query_ids"]
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800
    assert all(row["met"] for row in verdict["obligations"]), pformat({
        "obligations": verdict["obligations"], "sources": payload["sources"],
        "pre_projection_health_qualified": True, "pre_projection_sync_qualified": True,
    })
    assert verdict["semantic_useful"] is True


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


@pytest.mark.parametrize("case_id", [
    "v2-natural-evidence-selection", "v2-natural-offline", "v2-paraphrase-local-trial",
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
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800
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


def test_contrast_connector_does_not_fill_candidate_window(tmp_path):
    from tests.test_sqlite_ranking_truth import _store, _doc

    documents = [_doc("boundary.md", "Ownership", "Widgets and gadgets have separate owners.")]
    documents.extend(_doc(f"background-{i}.md", "Background", f"Widgets gadgets terminology entry {i}.") for i in range(100))
    documents.extend(_doc(f"noise-{i}.md", "Rather than", f"Choose ink rather than graphite in example {i}.") for i in range(12))
    store = _store(tmp_path, documents)
    results = store.query("widgets rather than gadgets", limit=4, budget=2000)
    assert results
    assert all("Widgets" in item.text for item in results)
    assert all({"rather", "than"} <= set(item.metadata["lexical_match"]["query_terms"]) for item in results)


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


@pytest.mark.parametrize("limit", [320, 520])
def test_table_window_retains_trailing_row_restriction(limit):
    from docmancer.docs.application.docs_context_projection import _focused_snippet

    text = ("| Option | Description |\n|---|---|\n"
            + "| Background | General reference information. |\n" * 15
            + "| `--archive` | Archive records. Only after review; never delete originals. |\n")
    snippet, start, end = _focused_snippet(text, ("Archive records",), limit=limit)
    assert "Archive records. Only after review; never delete originals. |" in snippet
    assert snippet == text[start:end]
    assert len(snippet) <= limit


@pytest.mark.parametrize("gap_size", [8, 16, 24, 80])
def test_wider_windows_preserve_contiguous_witnesses_and_table_qualifiers(gap_size):
    from docmancer.docs.application.docs_context_projection import project_docs_context
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    from docmancer.docs.domain.context_windows import _projection_limits

    gap = "Background notes. " * gap_size
    content = ("| Tool | Purpose |\n|---|---|\n| `lumen_read` | "
               + "General context " * 8 + "Amber reports are available. |\n"
               + "| Notes | " + gap + "|\n"
               + "| `lumen_view` | Cobalt checks run only after review. Do not publish drafts. |")
    payload, snapshot = project_docs_context(retrieval={
        "context_pack": [{
            "source_class": "project_doc", "project_identity": "git:example/lumen",
            "path": "docs/actions.md", "title": "Actions", "line_start": 17,
            "authority": "source_of_truth", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
            "doc_scope": "project", "content": content,
            "retrieval_query_matches": {"query-lookup-1": {
                "query_text": "Amber cobalt", "query_terms": ["amber", "cobalt"],
                "lexical_score": 1.0,
            }},
        }],
        "documentation_query_plan": {"queries": [{
            "query_id": "query-lookup-1", "text": "Amber cobalt", "origin": "host_lookup",
        }]},
    })
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload.get("sources", [])) <= 3 and payload["estimated_tokens"] <= 800
    witnesses = [row for row in payload.get("sources", [])
                 if "Amber" in row["snippet"] and "Cobalt" in row["snippet"]]
    assert bool(witnesses) is (gap_size <= 16)
    for row in payload.get("sources", []):
        snippet = row["snippet"]
        assert snippet in content and len(snippet) <= max(_projection_limits(content))
        assert row["line_start"] == 17 + content[:content.index(snippet)].count("\n")
        assert row["line_end"] == row["line_start"] + snippet.count("\n")
        if "Cobalt" in snippet:
            assert "only after review. Do not publish drafts." in snippet
        if row in witnesses:
            assert gap in snippet


@pytest.mark.parametrize("directive,preferred", [
    ("Agent instructions use `lumen cycle` only after approval.", True),
    ("Call it with `lumen cycle` only after approval.", True),
    ("Agent instructions do not use `lumen cycle`.", False),
    ("Never run `lumen cycle`.", False),
    ("Don't run `lumen cycle`.", False),
    ("Agents may not use `lumen cycle`.", False),
    ("The `lumen cycle` command is mentioned in the overview.", False),
])
@pytest.mark.parametrize("generated_competitor", [False, True])
def test_procedural_command_survives_effect_list_competition(directive, preferred, generated_competitor):
    from docmancer.docs.application.docs_context_projection import project_docs_context
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection

    effects = "The operation removes obsolete records from edited files."
    question = ("Which commands should I run for obsolete records from edited files?" if generated_competitor
                else "How can I reconcile obsolete records with edited files?")
    sources = [{
        "source_class": "project_doc", "project_identity": "git:example/lumen",
        "path": "docs/actions.md", "title": "Actions", "line_start": line,
        "authority": "source_of_truth", "lifecycle_status": "active",
        "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
        "doc_scope": "project", "content": content,
        "retrieval_query_matches": {"query-lookup-1": {
            "query_text": question,
            "query_terms": ["reconcile", "obsolete", "records", "edited", "files"],
            "lexical_score": score,
        }},
    } for content, score, line in ((effects, 100.0, 5), (effects + "\n\n" + directive, 1.0, 20))]
    queries = [{"query_id": "query-lookup-1", "text": question, "origin": "host_lookup"}]
    if generated_competitor:
        sources[0]["retrieval_query_matches"]["query-intent-1"] = {
            "query_text": "obsolete records", "query_terms": ["obsolete", "records"], "lexical_score": 1.0,
        }
        queries.append({"query_id": "query-intent-1", "text": "obsolete records", "origin": "canonical_intent"})
    payload, snapshot = project_docs_context(retrieval={
        "context_pack": sources,
        "documentation_query_plan": {"queries": queries},
    })
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert payload["sources"][0]["line_start"] == (20 if preferred else 5)
    if preferred:
        assert effects in payload["sources"][0]["snippet"]
        assert directive in payload["sources"][0]["snippet"]


@pytest.mark.parametrize("complement", ["Cobalt delta.", "Amber cobalt."])
@pytest.mark.parametrize("identity", ["git:example/lumen", "git:example/foreign"])
@pytest.mark.parametrize("independent_question", [None, "azure indigo", "azure indigo violet"])
def test_partial_lookups_admit_only_novel_visible_terms_after_other_directions(complement, identity, independent_question):
    from docmancer.docs.application.docs_context_projection import project_docs_context
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection

    queries = [("query-lookup-1", "amber cobalt delta"), ("query-lookup-2", independent_question or "azure indigo")]
    candidates = [{
        "source_class": "project_doc", "project_identity": source_identity,
        "path": path, "title": "Notes", "line_start": 1, "content": text,
        "authority": "source_of_truth", "lifecycle_status": "active",
        "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
        "doc_scope": "project", "retrieval_query_matches": {query_id: {
            "query_text": question, "query_terms": question.split(), "lexical_score": score,
        }},
    } for path, text, (query_id, question), score, source_identity in (
        ("lead.md", "Amber cobalt.", queries[0], 100.0, "git:example/lumen"),
        ("duplicate.md", "Amber cobalt.", queries[0], 90.0, "git:example/lumen"),
        ("complement.md", complement, queries[0], 1.0, identity),
        ("independent.md", "Azure indigo.", queries[1], 1.0, "git:example/lumen"),
    )]
    payload, snapshot = project_docs_context(retrieval={
        "project_identity": "git:example/lumen", "context_pack": candidates,
        "documentation_query_plan": {"unresolved_parts": ["unverified semantics"], "queries": [{
            "query_id": "query-original", "text": "Explain the undisclosed retention guarantee.", "origin": "original",
        }, *[
            {"query_id": key, "text": text, "origin": "host_lookup"}
            for key, text in (queries if independent_question else queries[:1])
        ]]},
    })
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    paths = [source["path_or_url"] for source in payload["sources"]]
    expected = (["independent.md", "lead.md"] if independent_question == "azure indigo"
                else ["lead.md", "independent.md"])
    if not independent_question:
        expected = ["lead.md"]
    elif complement == "Cobalt delta." and identity == "git:example/lumen":
        expected.append("complement.md")
    assert paths == expected
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert payload["query_coverage"] != "full"
    assert len(paths) <= 3 and payload["estimated_tokens"] <= 800


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
