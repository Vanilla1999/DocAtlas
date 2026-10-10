"""Remaining producer fidelity, with acquired fixtures and real qualification."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
from types import SimpleNamespace

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.joint_context_selection import packet_alternatives
from docmancer.docs.application.model_visible_projection import (
    _refresh_estimate, bound_insufficient_projection, project_insufficient,
    validate_model_visible_projection,
)
from docmancer.docs.application.reference_query_tagging import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.interfaces.mcp.context_tools import (
    _bounded_project_operational_diagnostics, _bounded_recovery_action,
    handle_context_tool,
)
from docmancer.docs.interfaces.mcp.recovery_projection import _bound_recoverable_insufficient_projection
from tests.docs.test_docs_lossless_context_projection import fixture, source_text, QUESTION


def reference_seed(kind="list"):
    from docmancer.docs.domain.query_reference_binding import CatalogSource, ScopeKey, resolve_references
    from docmancer.docs.application._docs_context_projection_core import project_docs_context as core
    retrieval, rows = fixture(kind)
    seed = "protocol validation rules preserve records."
    block = source_text(kind, large=True)
    raw = "# Protocol\n\n" + seed + "\n\n" + block + "\n"
    start, end = raw.index(seed), raw.index(seed) + len(seed)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    identity = CatalogSource("fixture-protocol", ScopeKey("offline-context", "4.0", "fixture-generation"), rows[0]["path"], digest)
    plan = asdict(resolve_references(QUESTION, catalog=(identity,), scope=identity.scope, catalog_complete=True))
    row = {**rows[0], "content": seed, "display_text": seed, "char_start": start, "char_end": end,
           "line_start": 3, "line_end": 3, "display_content_hash": hashlib.sha256(seed.encode()).hexdigest(),
           "generation_id": "fixture-generation", "_source_snapshot_sha256": "sha256:" + digest,
           "project_doc_content_hash": "sha256:" + digest, "_source_catalog_hash": "fixture-catalog",
           "_reference_root_plan": plan,
           "_reference_plans": {QUESTION: plan}, "_reference_evidence": {
               "schema_version": 1, "source": asdict(identity), "project_doc_content_hash": "sha256:" + digest,
               "char_start": start, "char_end": end, "text": seed, "raw_document": raw, "owner": None}}
    chunk = RetrievedChunk(source=row["path"], chunk_index=0, text=seed, score=1, metadata=row)
    tagged = _tag_retrieval_query([chunk], "query-original", QUESTION,
                                 build_documentation_query_plan(QUESTION).queries[0],
                                 expected_project_identity="offline-context")[0]
    assert tagged.metadata["retrieval_query_matches"]["query-original"]["qualified"] is True
    retrieval["context_pack"] = [dict(tagged.metadata)]
    payload, snapshot = core(retrieval=retrieval)
    assert payload.get("sources") and validate_model_visible_projection(payload, snapshot=snapshot) == []
    assert all(block not in s["snippet"] for s in payload["sources"])
    return retrieval, payload, snapshot, block


@pytest.mark.parametrize("kind", ["list", "table", "code"])
def test_direct_query_block_keeps_long_unit_and_existing_seed(kind):
    from docmancer.docs.application.query_block_context import select_query_block_context
    retrieval, payload, snapshot, block = reference_seed(kind)
    out, bindings = select_query_block_context(payload, snapshot, retrieval, max_tokens=1)
    assert any(block in s["snippet"] for s in out["sources"])
    assert any(payload["sources"][0]["snippet"] in s["snippet"] for s in out["sources"])
    assert validate_model_visible_projection(out, snapshot=bindings) == []
    assert out["estimated_tokens"] > 800
    for key in ("covered_query_ids", "missing_query_ids", "answer_supported", "edit_ready"):
        assert out[key] == payload[key]


@pytest.mark.parametrize("attack", ["digest", "scope", "forbidden_tail"])
def test_long_query_block_positive_then_reference_or_policy_rejection(attack):
    from docmancer.docs.application.query_block_context import select_query_block_context
    retrieval, payload, snapshot, block = reference_seed()
    positive, bound = select_query_block_context(payload, snapshot, deepcopy(retrieval), max_tokens=1)
    assert any(block in s["snippet"] for s in positive["sources"])
    assert validate_model_visible_projection(positive, snapshot=bound) == []
    damaged = deepcopy(snapshot)
    original = damaged[payload["sources"][0]["evidence_id"]]["source"]
    if attack == "digest": original["_reference_evidence"]["source"]["content_sha256"] = "0" * 64
    elif attack == "scope": original["_reference_evidence"]["source"]["scope"]["snapshot_id"] = "foreign"
    else:
        for trace in original["retrieval_query_matches"].values():
            trace["forbidden_evidence_terms"] = ["exact-value-0-69"]
    out, _ = select_query_block_context(payload, damaged, deepcopy(retrieval), max_tokens=1)
    assert not any(block in s["snippet"] for s in out["sources"])


def test_direct_block_recovery_keeps_quotes_and_bounded_unread_range():
    from docmancer.docs.application.query_block_recovery import select_query_block_recovery
    from docmancer.docs.application.source_continuation import SourceContinuationReader
    retrieval, payload, snapshot, _ = reference_seed()
    retrieval["_source_continuation_project_root"] = "/private/fixture"
    out, bindings = select_query_block_recovery(payload, snapshot, retrieval, max_tokens=1)
    assert out["sources"] == payload["sources"]
    assert len(out["read_next"]) == 1
    target = out["read_next"][0]
    assert target["line_end"] - target["line_start"] + 1 <= SourceContinuationReader.max_lines
    assert target["snapshot_sha256"] == snapshot[payload["sources"][0]["evidence_id"]]["source"]["_source_snapshot_sha256"]
    assert validate_model_visible_projection(out, snapshot=bindings) == []
    veto = deepcopy(snapshot)
    veto[payload["sources"][0]["evidence_id"]]["source"]["_reference_evidence"]["raw_document"] += "tampered"
    rejected, _ = select_query_block_recovery(payload, veto, retrieval, max_tokens=1)
    assert not rejected["read_next"] and rejected["sources"] == payload["sources"]


def acquired(kind="list", count=4):
    from docmancer.docs.domain.query_reference_binding import CatalogSource, ScopeKey, resolve_references
    retrieval, originals = fixture(kind, large=True)
    query = retrieval["documentation_query_plan"]["queries"][0]
    rows = []
    for index in range(count):
        text = source_text(kind, large=True).replace("field_0_", f"field_{index}_").replace(
            "exact-value-0-", f"exact-value-{index}-")
        row = {**deepcopy(originals[0]), "path": f"docs/rules-{index}.md",
               "stable_chunk_id": f"rules-{index}", "parent_logical_id": f"rules-{index}",
               "content": text, "display_text": text, "token_estimate": 2000,
               "display_content_hash": hashlib.sha256(text.encode()).hexdigest()}
        identity = CatalogSource(f"fixture-rules-{index}", ScopeKey("offline-context", "4.0", "fixture-generation"),
                                 row["path"], hashlib.sha256(text.encode()).hexdigest())
        root = asdict(resolve_references(QUESTION, catalog=(identity,), scope=identity.scope, catalog_complete=True))
        row.update(line_start=1, line_end=len(text.splitlines()), generation_id="fixture-generation",
                   _reference_root_plan=root, _reference_plans={QUESTION: root}, _reference_evidence={
                       "schema_version": 1, "source": asdict(identity), "char_start": 0,
                       "char_end": len(text), "text": text, "raw_document": text, "owner": None})
        chunk = RetrievedChunk(source=row["path"], chunk_index=0, text=text, score=1, metadata=row)
        tagged = _tag_retrieval_query([chunk], query["query_id"], query["text"],
                                     build_documentation_query_plan(QUESTION).queries[0],
                                     expected_project_identity="offline-context")[0]
        assert tagged.metadata["retrieval_query_matches"]["query-original"]["qualified"] is True
        rows.append(dict(tagged.metadata))
    retrieval["context_pack"] = rows
    assert all(q["origin"] != "host_lookup" for q in retrieval["documentation_query_plan"]["queries"])
    return retrieval, rows


def assert_quotes(payload, snapshot, rows):
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert {s["snippet"] for s in payload["sources"]} == {r["content"] for r in rows}
    assert {s["path_or_url"] for s in payload["sources"]} == {r["path"] for r in rows}
    assert payload["covered_query_ids"] == ["query-original"]
    for public in payload["sources"]:
        assert snapshot[public["evidence_id"]]["projected_source"] == public


def admitted_packet(retrieval, rows):
    """Joint producer input: combine independently admitted, validated seeds.

    This does not claim core novelty admits same-direction rows jointly. That
    distinct admission policy is deliberately not changed by output-cap removal.
    """
    payload, snapshot = None, {}
    sources = []
    for row in rows:
        one = deepcopy(retrieval)
        one["context_pack"] = [row]
        p, bound = project_docs_context(retrieval=one)
        assert_quotes(p, bound, [row])
        payload = p
        sources.extend(p["sources"])
        snapshot.update(bound)
    from docmancer.docs.application._docs_context_payload import _payload
    from docmancer.docs.application.context_selection import context_selection_decision
    normalized = [{**public, "retrieval_query_matches": snapshot[public["evidence_id"]]["source"]["retrieval_query_matches"]}
                  for public in sources]
    plan = retrieval["documentation_query_plan"]
    decision = context_selection_decision(normalized, tuple(plan["public_query_ids"]))
    payload = _payload(normalized, decision=decision, query_plan=plan)
    assert_quotes(payload, snapshot, rows)
    return payload, snapshot


@pytest.mark.parametrize("kind", ["list", "table", "code"])
def test_default_direct_question_and_joint_keep_four_long_units(kind):
    retrieval, rows = acquired(kind)
    payload, snapshot = admitted_packet(retrieval, rows)
    assert_quotes(payload, snapshot, rows)
    assert payload["estimated_tokens"] > 800
    alternatives = list(packet_alternatives(payload, snapshot, retrieval, max_tokens=1))
    assert alternatives  # former source/fit gates rejected even the baseline
    for candidate, bindings, _, _, _ in alternatives:
        assert_quotes(candidate, bindings, rows)
        assert all("exact-value-" in s["snippet"] and "-69" in s["snippet"] for s in candidate["sources"])


def test_cartesian_work_is_bounded_and_does_not_discard_baseline(monkeypatch):
    from docmancer.docs.application import joint_context_selection as joint
    retrieval, rows = acquired(count=8)
    payload, snapshot = admitted_packet(retrieval, rows)
    assert_quotes(payload, snapshot, rows)
    original_options, original_finish = joint.source_options, joint._finish
    calls = []
    def options(*args):
        choices, intro = original_options(*args)
        return choices * 3, intro
    def finish(*args):
        calls.append(1)
        return original_finish(*args)
    monkeypatch.setattr(joint, "source_options", options)
    monkeypatch.setattr(joint, "_finish", finish)
    before = deepcopy((payload, snapshot))
    candidates = list(joint.packet_alternatives(payload, snapshot, retrieval, max_tokens=1))
    assert candidates and len(calls) == 180
    assert (payload, snapshot) == before
    assert_quotes(candidates[0][0], candidates[0][1], rows)


@pytest.mark.parametrize("producer,limit", [("context", 2), ("recovery", 3)])
def test_four_sources_remain_eligible_without_widening_optional_scan_work(monkeypatch, producer, limit):
    from docmancer.docs.application import query_block_context, query_block_recovery
    retrieval, rows = acquired()
    payload, snapshot = admitted_packet(retrieval, rows)
    module = query_block_context if producer == "context" else query_block_recovery
    original = module.ranked_blocks
    calls = []
    def ranked(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(module, "ranked_blocks", ranked)
    retrieval["_source_continuation_project_root"] = "/private/fixture"
    select = module.select_query_block_context if producer == "context" else module.select_query_block_recovery
    out, bindings = select(payload, snapshot, retrieval, max_tokens=1)
    assert len(calls) == limit
    assert_quotes(out, bindings, rows)
    assert not out["read_next"]  # full visible units have no unread gap


@pytest.mark.parametrize("attack", ["hash", "path", "span", "answer_flag"])
def test_long_valid_joint_packet_still_rejects_tampered_binding(attack):
    retrieval, rows = acquired()
    payload, snapshot = admitted_packet(retrieval, rows)
    assert_quotes(payload, snapshot, rows)
    source = payload["sources"][0]
    if attack == "hash": source["content_sha256"] = "0" * 64
    elif attack == "path": source["path_or_url"] = "docs/foreign.md"
    elif attack == "span": source["line_end"] += 1
    else: payload["answer_supported"] = True
    _refresh_estimate(payload)
    assert validate_model_visible_projection(payload, snapshot=snapshot)
    assert list(packet_alternatives(payload, snapshot, retrieval, max_tokens=1)) == []


def recovery_fixture():
    action = {"tool": "prepare_docs", "type": "sync_project_docs",
              "arguments_patch": {"action": "sync_project_docs", "project_path": "/private/fixture"},
              "requires_confirmation": True, "confirmation_reason": "consent checkpoint " * 80,
              "observations": [f"module-{i}: manual consent required" for i in range(12)],
              "auto_execute": False}
    missing = [(f"missing-{i}: " + "exact requirement " * 30).strip() for i in range(12)]
    modules = [{"module_path": f"packages/module-{i}/" + "nested/" * 20,
                "module_name": (f"Module {i}: " + "full descriptive name " * 10).strip(),
                "module_type": "component"} for i in range(12)]
    return missing, action, modules


@pytest.mark.parametrize("budget", [1, 256, 800])
def test_missing_modules_and_consent_survive_failure_producers(budget):
    missing, action, modules = recovery_fixture()
    payload = project_insufficient(kind="docs_context", missing=missing,
                                  recommended_next_action=action, max_tokens=budget)
    assert payload["missing"] == missing
    assert payload["recommended_next_action"] == action
    payload.update(operational_reason_code="module_ambiguous", module_candidates=modules)
    before = deepcopy(payload)
    bound_insufficient_projection(payload, max_tokens=budget)
    _bound_recoverable_insufficient_projection(payload, max_tokens=budget)
    assert {k: v for k, v in payload.items() if k != "estimated_tokens"} == {
        k: v for k, v in before.items() if k != "estimated_tokens"}
    assert payload["estimated_tokens"] > 800


def test_context_tool_retains_complete_recovery_metadata_but_not_auto_execution():
    _, action, modules = recovery_fixture()
    diagnostics = _bounded_project_operational_diagnostics({"lanes": {"project": {
        "reason_code": "module_ambiguous", "module_candidates": modules}}})
    assert diagnostics["module_candidates"] == modules
    action.update(auto_execute=True, decision_options=[{"label": "option " * 80,
                  "details": {"nested": {"tail": f"value-{i}"}}} for i in range(12)])
    delivered = _bounded_recovery_action({"next_action": action})
    assert delivered["decision_options"] == action["decision_options"]
    assert delivered["confirmation_reason"] == action["confirmation_reason"]
    assert delivered["observations"] == action["observations"]
    assert delivered["auto_execute"] is False
    assert _bounded_recovery_action({"next_action": {"tool": "shell", "command": "untrusted"}}) is None
    assert _bounded_project_operational_diagnostics({"lanes": {"project": {
        "reason_code": "unrelated", "module_candidates": modules}}}) == {}


@pytest.mark.parametrize("blocked", [False, "confirmation", "delivery"])
def test_default_public_handler_direct_question_fidelity_and_veto(blocked):
    retrieval, rows = acquired("code")
    retrieval.update(mode_selected="project", status="success")
    if blocked == "confirmation": retrieval.update(requires_confirmation=True, status="confirmation_required")
    if blocked == "delivery": retrieval["delivery_decision"] = {"deliverable": False, "reason_code": "catalog_invalid"}
    calls = []
    def get_docs_context(question, **kwargs):
        assert question == QUESTION and kwargs["lookup_queries"] == ()
        calls.append(kwargs)
        return deepcopy(retrieval)
    service = SimpleNamespace(get_docs_context=get_docs_context)
    payload = handle_context_tool("get_docs_context", {"question": QUESTION, "project_path": "/private/fixture"}, service)
    assert len(calls) == 1
    if blocked:
        assert not payload.get("sources") and payload["status"] == "insufficient_evidence"
        assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    else:
        assert payload["kind"] == "docs_context" and len(payload["sources"]) == 1
        assert payload["sources"][0]["snippet"] == rows[0]["content"]
        assert payload["estimated_tokens"] > 800


@pytest.mark.parametrize("qualified", [True, False])
def test_project_packing_retains_qualified_windows_without_expanding_search(tmp_path, qualified):
    from docmancer.docs.application.project_docs_service import ProjectDocsService
    retrieval, rows = acquired("list")
    root = tmp_path / "project"
    root.mkdir()
    identity = ProjectDocsService._repository_identity(root)
    chunks = []
    for i, row in enumerate(rows):
        text = row["content"] if qualified else f"unrelated ledger checksum {i}"
        metadata = {**row, "project_identity": identity, "source_class": "project_file",
                    "content": text, "display_text": text, "token_estimate": 2000,
                    "retrieval_query_matches": {}, "retrieval_query_ids": [],
                    "display_content_hash": hashlib.sha256(text.encode()).hexdigest()}
        for key in ("_reference_evidence", "_reference_root_plan", "_reference_plans", "generation_id"):
            metadata.pop(key, None)  # lightweight acquired fixture, no snapshot store
        chunks.append(RetrievedChunk(source=row["path"], chunk_index=i, text=text, score=1, metadata=metadata))
    calls = []
    def query(text, **kwargs):
        calls.append((text, kwargs))
        return deepcopy(chunks)
    agent = SimpleNamespace(query=query, config=SimpleNamespace(query=SimpleNamespace(default_limit=1)))
    service = ProjectDocsService(SimpleNamespace(_agent_instance=lambda: agent))
    selected = service.query_project_docs(str(root), QUESTION, tokens=1, limit=1)
    assert len(calls) == 2  # original and authoritative; no optional rescue search
    assert [kw["limit"] for _, kw in calls] == [1, 20]
    assert all(text == QUESTION and kw["budget"] == 1 for text, kw in calls)
    assert len(selected) == (4 if qualified else 0)
    if qualified:
        assert {c.text for c in selected} == {r["content"] for r in rows}
        assert all(c.metadata["retrieval_query_matches"]["query-original"]["qualified"] for c in selected)


@pytest.mark.parametrize("attack", ["project", "hash", "crop"])
def test_need_variants_keep_long_list_without_wiring_new_admission(attack):
    from docmancer.docs.application.need_context_projection import iter_need_context_variants
    from docmancer.docs.application.source_dependency_preparation import compact_dependency_record
    from tests.docs.test_evidence_set_disposition import context_case
    question = "List four ways to enable strict mode, including field, annotation, config and validation call."
    introductions = ["Pass strict=True to the validation call.", "Set strict=True on a field.",
                     "Use a strict type annotation.", "Use strict mode config."]
    items = ["* " + intro + " " + " ".join(
        f"Record {i}_{j} preserves exact-value-{i}-{j} without coercion." for j in range(22))
        for i, intro in enumerate(introductions)]
    body = "# Strict mode\n\nStrict mode can be enabled in these ways:\n\n" + "\n".join(items) + "\n"
    _, args = context_case(question, body)
    candidate = {**args["candidate"], "path": "Guide.md", "content": body,
                 "line_start": 1, "line_end": len(body.splitlines()),
                 "_evidence_sets": [compact_dependency_record(b) for b in args["bundles"]]}
    kwargs = dict(query_plan={"original_question": question, "public_query_ids": ["query-original"]},
                  expected_project_identity="project", max_tokens=1, diagnostics={})
    positive = list(iter_need_context_variants([candidate], **kwargs))
    assert positive, kwargs["diagnostics"]
    whole_list = body[body.index("Strict mode can"):].strip()
    assert any(whole_list in variant["snippet"] for _, variant, _, _ in positive)
    assert all(not variant["retrieval_query_ids"] and not variant["retrieval_query_matches"]
               for _, variant, _, _ in positive)
    damaged = deepcopy(candidate)
    if attack == "project": damaged["project_identity"] = "foreign"
    elif attack == "hash": damaged["_reference_evidence"]["source"]["content_sha256"] = "0" * 64
    else:
        cropped = body[:body.index("* Use strict mode config.")]
        damaged["_reference_evidence"].update(text=cropped, char_end=len(cropped))
        damaged.update(content=cropped, snippet=cropped)
    rejected = list(iter_need_context_variants([damaged], **kwargs))
    if attack == "crop":
        assert not any(whole_list in variant["snippet"] for _, variant, _, _ in rejected)
        assert all(not variant["retrieval_query_ids"] and not variant["retrieval_query_matches"]
                   for _, variant, _, _ in rejected)
    else:
        assert not rejected


def test_recovery_diagnostic_keeps_question_tail_and_all_accepted_fragments():
    from docmancer.docs.application.recovery import build_recovery_diagnosis, recovery_action
    question = "Explain storage behavior " + "for independently validated records " * 30 + "only after explicit user consent."
    diagnosis = build_recovery_diagnosis(question, None, projection={}, retrieval={})
    assert diagnosis["problem_spans"] == [question]
    assert diagnosis["documentation_supported"] is False
    action = recovery_action(diagnosis)
    assert action["query_terms"] == [question]
    fragments = [f"requirement-{i}: " + "full observed diagnostic context " * 15 for i in range(12)]
    supplied = {"disposition": "search_local_source", "recognized_spans": fragments}
    assert recovery_action(supplied)["query_terms"] == fragments
    assert recovery_action(supplied)["auto_execute"] is False
    assert recovery_action({**supplied, "hard_stop": True}) is None
    assert recovery_action({**supplied, "disposition": "rephrase_question"}) is None
