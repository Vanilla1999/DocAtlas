"""New-only dictionary exit checks; literal resolution is not topic inference."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib

import pytest

from docmancer.docs.application import context_candidate_ranking as ranking
from docmancer.docs.domain.query_reference_binding import (
    CatalogSource, ScopeKey, normalize_reference_path, prepare_reference_probe,
    query_mentions, reference_body_question, resolve_references,
)
from docmancer.docs.domain.question_retrieval_needs import _need_subject
from docmancer.docs.domain.evidence_qualification import qualify_evidence


SCOPE = ScopeKey("repo:literal", "v2", "snapshot:literal")


def catalog(path="docs/Guide.md", identity="guide", scope=SCOPE):
    return CatalogSource(identity, scope, path, "a" * 64)


def reference(question, rows, **kwargs):
    plan = resolve_references(question, catalog=rows, scope=SCOPE, **kwargs)
    return next(ref for ref in plan.references if ref.role == "source_locator")


@pytest.mark.parametrize("prefix", ["file", "document", "library", "constant", "in the", "according to", "в файле", "библиотека", "when does"])
def test_nl_context_does_not_assign_roles(prefix):
    mentions = query_mentions(f"{prefix} argon")
    assert not any(m.syntax_role in {"source_locator", "semantic_subject"} for m in mentions)
    assert _need_subject(f"{prefix} argon") == ""


@pytest.mark.parametrize("question", ["if one argon task fails", "what is its default", "when does argon run", "what does the constant argon return", "Как работает библиотека аргон?"])
def test_nl_actor_patterns_do_not_nominate_subjects(question):
    assert not any(m.syntax_role == "semantic_subject" for m in query_mentions(question))
    assert _need_subject(question) == ""


def test_literal_mentions_keep_sha_unicode_offsets_and_occurrences():
    question = 'Объясни `Client.send` и "Client.send" в docs/Памятка.md'
    mentions = query_mentions(question)
    digest = hashlib.sha256(question.encode()).hexdigest()
    assert len([m for m in mentions if m.text == "Client.send"]) == 2
    assert len({m.mention_id for m in mentions}) == len(mentions)
    assert all(question[m.start:m.end] == m.text and m.mention_id == f"{digest}:{m.start}:{m.end}" for m in mentions)
    assert next(m for m in mentions if m.text == "docs/Памятка.md").syntax_role == "source_locator"

    # Replay every selected original question; this is 19 pure calls, not a
    # representative sample. Frozen source files are data, never imported.
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    frozen = json.loads((root / "eval/task_level/contract_history/reference_role_inputs.json").read_text(encoding="utf-8"))
    assert frozen["protocol"] == "reference-role-original-inputs-v1"
    inputs = frozen["replay_inputs"]
    assert len(inputs) == 19
    encoded = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(encoded.encode("utf-8")).hexdigest() == "deef6debbad224f9f3bf0d146654f3b703c3748fc82345058697bd0f91373cf8"
    for archive_path, source_hash in (
        ("eval/task_level/contract_history/query_reference_roles.py.txt", "8109bda521861fcc4be5c3be57c42b9a4b63dc38eafbb088247fe60525082aa6"),
        ("eval/task_level/contract_history/reference_behavior_matrix.py.txt", "1c760ae7be2dffeab5b71a1ccdb30163fc2bb465045048bf235a6b2f227bebcf"),
    ):
        assert hashlib.sha256((root / archive_path).read_bytes()).hexdigest() == source_hash
    for record in inputs:
        raw_question = record["question"]
        raw_hash = hashlib.sha256(raw_question.encode("utf-8")).hexdigest()
        start, end = record["literal_span"]
        assert raw_hash == record["question_sha256"]
        assert raw_question[start:end] == record["literal"]
        current = query_mentions(raw_question)
        assert all(type(m.start) is int and type(m.end) is int
                   and type(m.explicit) is bool for m in current)
        expected = ((record["literal"], start, end, record["expected_role"],
                     record["expected_explicit"], f"{raw_hash}:{start}:{end}"),)
        actual = tuple((m.text, m.start, m.end, m.syntax_role, m.explicit, m.mention_id)
                       for m in current)
        guard = ("critical_reference_nl_context_keeps_quoted_symbol" if record["expected_explicit"]
                 else "critical_reference_nl_context_keeps_bare_unresolved")
        assert (actual == expected if record["occurrence_required"] else actual in ((), expected)), guard
        if record["expected_explicit"]:
            # Catalog nomination belongs to resolve_references. An explicit
            # backtick symbol remains a symbol even on an exact stem collision.
            plan = resolve_references(raw_question,
                catalog=[catalog("docs/ArgonGuide.md", "argon-guide")], scope=SCOPE)
            ref, = plan.references
            assert plan.question == raw_question and plan.scope == SCOPE
            assert ref.mention == current[0]
            if record["source_parameters"]["quote"] == "`":
                assert (ref.role, ref.state, ref.source_ids) == ("symbol_identity", "resolved", ())
            else:
                assert (ref.role, ref.state, ref.source_ids) == ("source_locator", "resolved", ("argon-guide",))


@pytest.mark.parametrize("literal", ["docs/Guide.md", r"docs\Guide.md", "./docs/Guide.md", "Guide.md", "GUIDE.MD", '"Guide"', '"GUIDE"'])
def test_catalog_path_basename_stem_casefold_are_literal_resolution(literal):
    ref = reference(f"{literal}?", [catalog()])
    assert (ref.state, ref.source_ids) == ("resolved", ("guide",))


def test_catalog_tiers_keep_case_priority_and_ambiguity():
    rows = [catalog("a/Guide.md", "upper"), catalog("b/guide.md", "lower")]
    assert reference("Guide.md", rows).source_ids == ("upper",)
    assert reference('"GUIDE"', rows).state == "ambiguous"
    assert reference('"GUIDE"', rows).source_ids == ("lower", "upper")
    assert reference("a/Guide.md", rows).source_ids == ("upper",)
    assert reference("c/Guide.md", rows).state == "missing"
    assert reference('"GUIDE"', rows) == reference('"GUIDE"', rows[::-1])


@pytest.mark.parametrize("key,value", [("project_id", "other"), ("version", "v1"), ("snapshot_id", "old")])
def test_catalog_scope_is_filtered_before_literal_matching(key, value):
    assert reference("Guide.md", [catalog(scope=replace(SCOPE, **{key: value}))]).state == "missing"


@pytest.mark.parametrize("literal", ["Guide.md", '"Guide"'])
def test_incomplete_catalog_cannot_certify_unique_literal(literal):
    ref = reference(literal, [catalog()], catalog_complete=False)
    assert ref.state == "unresolved" and ref.source_ids == ()


@pytest.mark.parametrize("field", ["project_id", "snapshot_id"])
def test_literal_source_requires_project_and_snapshot_identity(field):
    scope = replace(SCOPE, **{field: ""})
    plan = resolve_references("docs/Guide.md", catalog=[catalog(scope=scope)], scope=scope)
    ref = next(ref for ref in plan.references if ref.role == "source_locator")
    assert ref.state == "unresolved" and not ref.source_ids
    scope = replace(SCOPE, version="")
    assert resolve_references("docs/Guide.md", catalog=[catalog(scope=scope)], scope=scope).references[0].state == "resolved"


@pytest.mark.parametrize("literal", ["../Guide.md", "/Guide.md", "a/../Guide.md", "C:/Guide.md"])
def test_literal_paths_do_not_rebase_traversal_or_roots(literal):
    assert reference(literal, [catalog("Guide.md")]).state == "missing"
    assert normalize_reference_path(literal) == literal


def test_reference_body_is_original_question_even_with_bad_serialized_offsets():
    question = 'According to the file "Guide.md", what does `Client.send` do?'
    plan = asdict(resolve_references(question, catalog=[catalog()], scope=SCOPE))
    assert reference_body_question(plan) == question
    plan["references"][0]["mention"]["start"] = -1
    assert reference_body_question(plan) == question


def prepared_case(question="docs/Guide.md `Client.send`", raw="# Guide\n\nClient.send returns a value.\n", path="docs/Guide.md"):
    digest = hashlib.sha256(raw.encode()).hexdigest()
    row = replace(catalog(path), content_sha256=digest)
    plan = asdict(resolve_references(question, catalog=[row], scope=SCOPE))
    candidate = {
        "project_identity": SCOPE.project_id, "generation_id": SCOPE.snapshot_id,
        "resolved_version": SCOPE.version, "path": row.canonical_path,
        "source_content_hash": digest, "char_start": 0, "char_end": len(raw),
        "_reference_root_plan": plan, "_reference_plans": {question: plan},
        "_reference_evidence": {"schema_version": 1, "source": asdict(row),
            "char_start": 0, "char_end": len(raw), "text": raw, "raw_document": raw},
    }
    return {"query_text": question, "parent_exact_terms": ["guide.md", "client.send"]}, candidate, raw


def test_prepared_reference_retains_original_text_and_parent_constraints():
    probe, candidate, raw = prepared_case()
    result, reason = prepare_reference_probe(probe, candidate=candidate, evidence_text=raw)
    assert reason is None
    assert result["query_text"] == result["reference_body_query"] == probe["query_text"]
    assert result["parent_exact_terms"] == probe["parent_exact_terms"]
    assert {binding["field"] for binding in result["reference_bindings"]} == {"path", "body"}


@pytest.mark.parametrize("field,value,expected", [
    ("project_identity", "other", "reference_project_mismatch"),
    ("generation_id", "old", "reference_snapshot_mismatch"),
    ("resolved_version", "v1", "reference_version_mismatch"),
    ("path", "other.md", "reference_path_mismatch"),
    ("source_content_hash", "b" * 64, "reference_content_mismatch"),
    ("char_end", 1000, "reference_window_mismatch"),
])
def test_prepared_reference_identity_hash_and_window_guards(field, value, expected):
    probe, candidate, raw = prepared_case()
    candidate[field] = value
    assert prepare_reference_probe(probe, candidate=candidate, evidence_text=raw)[1] == expected


def test_prepared_reference_rejects_forged_mentions_and_nonunique_visible_text():
    probe, candidate, raw = prepared_case()
    candidate["_reference_root_plan"]["references"][0]["mention"]["mention_id"] = "forged"
    assert prepare_reference_probe(probe, candidate=candidate, evidence_text=raw)[1] == "reference_scope_mismatch"
    probe, candidate, raw = prepared_case()
    assert prepare_reference_probe(probe, candidate=candidate, evidence_text="e")[1] == "reference_body_mismatch"


@pytest.mark.parametrize("mutation,reason", [
    ("raw", "reference_raw_content_mismatch"),
    ("owner", "invalid_subject_owner"),
    ("window", "invalid_reference_window"),
    ("snapshot_hash", "reference_content_mismatch"),
    ("missing_plan", "missing_reference_plan"),
])
def test_prepared_reference_raw_owner_window_and_hash_domains_fail_closed(mutation, reason):
    probe, row, raw = prepared_case()
    evidence = row["_reference_evidence"]
    if mutation == "raw":
        evidence["raw_document"] += "forged"
    elif mutation == "owner":
        evidence["owner"] = {"text": "invented subject", "scope_start": 0, "scope_end": len(raw)}
    elif mutation == "window":
        evidence["char_end"] += 1
    elif mutation == "snapshot_hash":
        evidence["project_doc_content_hash"] = "b" * 64
        row["_source_snapshot_sha256"] = "c" * 64
    elif mutation == "missing_plan":
        row.pop("_reference_root_plan")
    assert prepare_reference_probe(probe, candidate=row, evidence_text=raw)[1] == reason


def qualify_prepared(probe, row, body):
    probe = {**probe, "query_origin": "original", "relation": "direct"}
    return qualify_evidence(probe, query_id="query-original", visible_text=body,
        evidence_text=body, candidate=row, expected_project_identity=SCOPE.project_id,
        authoritative_query={"query_id": "query-original", "origin": "original",
            "relation": "direct", "text": probe["query_text"]})


@pytest.mark.parametrize("locator", ["docs/Guide.md", '"Guide.md"', "`Guide.md`", '"Guide"'])
def test_verified_locator_is_not_body_exact_term_in_actual_qualification(locator):
    question = f"{locator} `Client.send` returns a value"
    probe, row, raw = prepared_case(question)
    probe.pop("parent_exact_terms")
    body = "Client.send returns a value."
    prepared, reason = prepare_reference_probe(probe, candidate=row, evidence_text=body)
    assert reason is None
    assert prepared["query_text"] == prepared["reference_body_query"] == question
    assert prepared["exact_terms"] == ["client.send"]
    result = qualify_prepared(prepared, row, body)
    assert result.qualified, result.trace
    assert result.trace["missing_exact_terms"] == []
    assert result.covered_query_ids == ("query-original",)
    assert {binding["field"] for binding in result.trace["reference_bindings"]} == {"path", "body"}


@pytest.mark.parametrize("question", [
    "Guide.md. `Client.send` returns a value",
    "Guide.md.\n`Client.send` returns a value",
    "`Client.send` returns a value in Guide.md.",
    "Guide.md, `Client.send` returns a value",
    "Guide.md; `Client.send` returns a value",
    "Guide.md? `Client.send` returns a value",
])
def test_terminal_filename_punctuation_prepares_and_qualifies_literal_body(question):
    probe, row, raw = prepared_case(question)
    probe.pop("parent_exact_terms")
    body = "Client.send returns a value."
    refs = row["_reference_root_plan"]["references"]
    locator = next(ref for ref in refs if ref["role"] == "source_locator")
    assert locator["mention"]["text"] == "Guide.md"
    assert locator["source_ids"] == ("guide",)
    prepared, reason = prepare_reference_probe(probe, candidate=row, evidence_text=body)
    assert reason is None and prepared["exact_terms"] == ["client.send"]
    assert prepared["query_text"] == prepared["reference_body_query"] == question
    result = qualify_prepared(prepared, row, body)
    assert result.qualified, result.trace
    assert result.trace["missing_exact_terms"] == []
    assert result.covered_query_ids == ("query-original",)
    assert any(binding["field"] == "path" for binding in result.trace["reference_bindings"])


def test_occurrence_mask_retains_same_spelling_separate_backtick_symbol():
    question = '"Guide" `Guide` returns a value'
    probe, row, raw = prepared_case(question)
    probe.pop("parent_exact_terms")
    prepared, reason = prepare_reference_probe(probe, candidate=row,
        evidence_text="Client.send returns a value.")
    assert reason is None and prepared["exact_terms"] == ["guide"]
    result = qualify_prepared(prepared, row, "Client.send returns a value.")
    assert not result.qualified and result.trace["missing_exact_terms"] == ["guide"]
    probe, row, raw = prepared_case(question, raw="Guide returns a value.")
    probe.pop("parent_exact_terms")
    assert qualify_prepared(probe, row, raw).qualified
    roles = [(ref["mention"]["text"], ref["role"]) for ref in row["_reference_root_plan"]["references"]]
    assert roles == [("Guide", "source_locator"), ("Guide", "symbol_identity")]


@pytest.mark.parametrize("field,value", [
    ("path", "docs/Other.md"), ("project_identity", "other"),
    ("generation_id", "old"), ("resolved_version", "v1"),
    ("source_content_hash", "b" * 64), ("char_end", 1000),
])
def test_actual_qualification_still_rejects_reference_identity_hash_and_window(field, value):
    probe, row, raw = prepared_case("docs/Guide.md `Client.send` returns a value")
    probe.pop("parent_exact_terms")
    body = "Client.send returns a value."
    assert qualify_prepared(probe, row, body).qualified
    row[field] = value
    result = qualify_prepared(probe, row, body)
    assert not result.qualified and result.covered_query_ids == ()


@pytest.mark.parametrize("literal", ["Guide.md.bak", "Guide.md-extra", '"Guide.md.bak"', "docs/Guide.md.bak", "docs/Guide.md-extra", "Guide.md.bak.", "Guide.md-extra.", "Guide.md.backup"])
def test_filename_suffix_must_be_complete_not_a_catalog_prefix(literal):
    plan = resolve_references(literal, catalog=[catalog("Guide.md")], scope=SCOPE)
    assert not any(ref.role == "source_locator" for ref in plan.references)
    assert not any(ref.source_ids for ref in plan.references)
    assert not any(mention.text == "Guide.md" for mention in query_mentions(literal))


@pytest.mark.parametrize("literal", ["Guide.md", '"Guide.md"'])
def test_complete_literal_filename_missing_or_wrong_catalog_stays_missing(literal):
    assert reference(literal, []).state == "missing"
    assert reference(literal, [catalog("Guide.md.bak")]).state == "missing"
    assert reference(literal, [catalog("Guide.md-extra")]).state == "missing"


@pytest.mark.parametrize("symbol", ["Client.send", "`Client.send`", '"Client.send"', "`Guide`"])
def test_explicit_symbol_catalog_collision_does_not_generate_source_locator(symbol):
    rows = [catalog("Client.send.md"), catalog("Guide.md", "other")]
    plan = resolve_references(symbol, catalog=rows, scope=SCOPE)
    assert plan.references and all(ref.role == "symbol_identity" and not ref.source_ids for ref in plan.references)


def test_explicit_document_path_and_colliding_symbol_are_independent_occurrences():
    question = "docs/Client.send.md Client.send `Client.send` returns a value"
    probe, row, raw = prepared_case(question, path="docs/Client.send.md")
    refs = row["_reference_root_plan"]["references"]
    assert [ref["role"] for ref in refs] == ["source_locator", "symbol_identity", "symbol_identity"]
    probe.pop("parent_exact_terms")
    result = qualify_prepared(probe, row, "Client.send returns a value.")
    assert result.qualified, result.trace
    assert result.trace["exact_terms"] == ["client.send"]


@pytest.mark.parametrize("question,snippet", [
    ("How does the system report errors?", "It reports errors."),
    ("Is a retrieval hit proof?", "A retrieval hit is not proof."),
    ("How does the system decide?", "Select the result."),
    ("What should I do on insufficient_evidence?", "Retry or ask for approval."),
    ("When is foo.Run allowed?", "foo.Run needs user approval."),
    ("What happens if the index is stale?", "It becomes stale."),
    ("Compare reading and writing", "Reading is different rather than the same."),
])
def test_removed_semantic_priority_slots_are_inert(question, snippet):
    assert ranking._relation_request_priority(question, snippet) == (0.0,) * 9
    assert ranking._condition_body_priority(question, snippet) == 0
    assert ranking._comparison_action_priority(question, snippet) == 0


def candidate(identity, text, query_id="query-original", **trace):
    return {"evidence_id": identity, "path": "docs/guide.md", "snippet": text,
        "retrieval_query_matches": {query_id: {"qualified": True, "lexical_score": 1.0,
            "match_ratio": 1.0, "query_text": "widget", **trace}}}


def test_action_language_has_no_rank_boost_and_rank_shape_is_preserved():
    action = candidate("action", "Run the widget.")
    plain = candidate("plain", "The widget exists.")
    query = {"query-original": "What should the widget do?"}
    left = ranking._context_rank(action, query, {"query-original"})
    right = ranking._context_rank(plain, query, {"query-original"})
    assert len(left) == 13 and left == right and left[:2] == (0.0, 0.0)
    assert ranking._facet_aware_candidates([plain, action], query_text=query,
        required_query_ids={"query-original"}) == [plain, action]


def test_lexical_assignment_and_continuation_rank_without_mutating_attribution():
    plain = candidate("plain", "widget")
    continuing = candidate("continuing", "widget", qualification_route="same_atom_continuation")
    query = {"query-original": "widget"}
    before = deepcopy([plain, continuing])
    assert ranking._facet_aware_candidates([plain, continuing], query_text=query,
        required_query_ids={"query-original"})[0] is continuing
    assert ranking._context_rank(plain, query, {"query-original"}, {"plain"})[3] == 1.0
    plain["retrieval_query_matches"]["query-original"]["lexical_score"] = 2.0
    assert ranking._context_rank(plain, query, {"query-original"})[8] == 2.0
    plain["retrieval_query_matches"]["query-original"]["lexical_score"] = 1.0
    assert [plain, continuing] == before


def test_admission_only_and_derived_traces_do_not_manufacture_full_matches():
    admission = candidate("admission", "widget", admission_only=True)
    derived = candidate("derived", "widget", coverage_kind="derived")
    direct = candidate("direct", "widget")
    assert ranking._fully_matched_query_ids([admission, derived]) == set()
    assert ranking._fully_matched_query_ids([direct]) == {"query-original"}
    assert ranking._context_rank(admission, {"query-original": "widget"}, {"query-original"})[2] == 0


def test_fallback_same_source_strict_body_superset_preserves_prefix(monkeypatch):
    monkeypatch.setattr(ranking, "_context_rank", lambda *args: (0.0,) * 13)
    short = candidate("short", "widget", query_id="fallback")
    long = candidate("long", "widget telescope", query_id="fallback")
    assert ranking._facet_aware_candidates([short, long],
        query_text={"query-original": "widget telescope"}, required_query_ids={"query-original"},
        fallback_query_ids={"fallback"}) == [long, short]


def test_semantic_component_witnesses_are_not_ranking_authority(monkeypatch):
    from docmancer.docs.application import context_selection
    def forbidden(*args, **kwargs):
        raise AssertionError("semantic certification must not rank candidates")
    monkeypatch.setattr(context_selection, "component_witnesses", forbidden)
    row = candidate("plain", "widget")
    assert ranking._facet_aware_candidates([row], query_text={"query-original": "widget"},
        required_query_ids={"query-original"}, obligations=(object(),),
        missing_component_ids={"component"}) == [row]
