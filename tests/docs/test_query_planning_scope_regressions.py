"""Explicit retrieval/requirement coverage, not NL inference or semantic entailment."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest
import yaml

from docmancer.docs.application.action_packet import (
    build_action_packet, evidence_identity_for_item, refresh_action_packet_estimate,
    validate_action_packet,
)
from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.application.model_visible_projection import (
    project_patch_context, validate_model_visible_projection,
)
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.domain.canonical import canonical_hash
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.mutation_intent import (
    MutationIntentContract, RequestedTarget, build_mutation_intent, resolve_mutation_targets,
)
from docmancer.docs.domain.patch_request_plan import build_patch_request_plan
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.project_retrieval_intent import project_retrieval_disposition
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import create_local_mcp_service
from docmancer.mcp.docs_server import call_docs_tool_payload


def _source(text, *, path="docs/api.md", source_class="project_doc"):
    return {
        "path": path, "source_class": source_class, "doc_scope": "project",
        "project_identity": "project:scope-unit", "authority": "canonical",
        "freshness": "current", "content": text, "display_text": text,
        "stable_chunk_id": path, "parent_logical_id": path + ":parent",
        "char_start": 100, "char_end": 100 + len(text),
        "line_start": 7, "line_end": 7 + text.count("\n"),
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
    }


def _packet(question, sources, facts, *, paths=(), mutation=None):
    before = deepcopy((sources, facts))
    requirements = build_requirements(
        question, public_requirements=facts, required_evidence_paths=paths,
        representation_bounded=False,
    )
    plan = build_documentation_query_plan(question, requirements=requirements).as_payload()
    assert plan["original_question"] == question
    assert [(row["text"], row["origin"]) for row in plan["queries"]] == [(question, "original")]
    assert not plan["_component_contract"]
    assert plan["component_scope_complete"] is False
    identity = build_project_answer_contract(question)
    assert identity.question_hash == canonical_hash(question)
    assert not identity.proof_obligations and not identity.retrieval_hints
    packet = build_action_packet(
        question=question, context_pack=sources, public_requirements=facts,
        required_evidence_paths=paths, project_identity="project:scope-unit",
        mutation_intent_contract=mutation,
    )
    assert (sources, facts) == before
    assert validate_action_packet(packet, evidence_items=sources, mutation_intent_contract=mutation) == []
    projected, snapshot = project_patch_context(packet=packet, evidence_items=sources)
    assert validate_model_visible_projection(projected, snapshot=snapshot) == []
    assert projected["result"] == packet["result"]
    assert projected.get("sources", []) == packet.get("sources", [])
    assert projected.get("requirements", []) == packet.get("requirements", [])
    assert packet["edit_ready"] is projected["edit_ready"] is False
    assert "answer_supported" not in projected  # v4 has no answer-certification field.
    for fact in facts:
        requirement = next(row for row in packet["requirements"] if row["value"] == fact)
        assert requirement["mandatory"] is True
        assert requirement["public_provenance"] == "public_task_contract"
    return packet, projected, snapshot


def _missing_fact(packet, fact):
    requirement = next(row for row in packet["requirements"] if row["value"] == fact)
    assert requirement["requirement_id"] in packet["missing"]
    assert not any(row["requirement_id"] == requirement["requirement_id"]
                   for row in packet.get("assignments", []))
    assert packet["completeness"] != "complete"


def _witness(packet, sources, fact):
    requirement = next(row for row in packet["requirements"] if row["value"] == fact)
    assignment = next(row for row in packet["assignments"]
                      if row["requirement_id"] == requirement["requirement_id"])
    original = next(row for row in sources if row["path"] == assignment["path"])
    text = original["content"]
    start, end = assignment["unit_char_start"], assignment["unit_char_end"]
    assert text[start:end] == fact
    assert assignment["char_start"] == original["char_start"] + start
    assert assignment["char_end"] == original["char_start"] + end
    assert assignment["line_start"] == original["line_start"] + text[:start].count("\n")
    assert assignment["line_end"] == assignment["line_start"] + fact.count("\n")
    assert assignment["unit_content_hash"] == hashlib.sha256(fact.encode()).hexdigest()
    assert assignment["projected_content_hash"] == assignment["unit_content_hash"]
    assert assignment["unit_id"] and assignment["unit_kind"]
    visible = next(row for row in packet["sources"] if row["path"] == original["path"])
    assert visible["text"] == text
    assert visible["content_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert visible["instruction_trust"] == "untrusted_data"
    return assignment


def _negative_and_positive(question, mention, fact, *, path="docs/api.md", paths=()):
    negative, _, _ = _packet(question, [_source(mention, path=path)], [fact], paths=paths)
    assert negative["result"] == "data"  # A missing fact is not a transport failure.
    _missing_fact(negative, fact)
    sources = [_source("# Contract\n\n" + fact, path=path)]
    positive, _, _ = _packet(question, sources, [fact], paths=paths)
    assert positive["result"] == "data" and positive["completeness"] == "complete"
    _witness(positive, sources, fact)
    return positive, sources


@pytest.mark.parametrize("tool", ["get_docs_context", "lookup_context", "read_evidence"])
@pytest.mark.parametrize("verb", ["сделать", "предпринять"])
def test_next_action_preserves_question_without_implementation_authority(tool, verb):
    question = f"Что должен {verb} агент, если {tool} вернул недостаточно данных?"
    assert not build_patch_request_plan(question).mutation_targets
    assert build_mutation_intent(question).operation == "none"
    _negative_and_positive(
        question, f"The implementation of {tool} is in the adapter. {tool} retrieves evidence.",
        f"If {tool} returns insufficient evidence, the agent must inspect the returned recovery action.",
    )


@pytest.mark.parametrize("tail", [
    "if the cache contains an unknown tenant",
    "unless the reader has refreshed its credentials",
    "without discarding an incomplete result",
    "only when the source is unavailable",
    "after an interrupted request",
    "under an unknown operating mode",
])
def test_subject_match_does_not_satisfy_explicit_conditional_requirement(tail):
    question = f"What does lookup_context do {tail}?"
    fact = f"lookup_context must retain source identity {tail}."
    _negative_and_positive(question, "lookup_context retrieves documentation from the local index.", fact)
    assert build_project_answer_contract(question).question_hash != canonical_hash("What does lookup_context do?")


def test_english_next_action_retains_explicit_required_response():
    question = "What should the agent do next if lookup_context returns insufficient evidence?"
    _negative_and_positive(
        question, "lookup_context retrieves documentation from the local index.",
        "If lookup_context returns insufficient evidence, inspect its explicit recovery action before retrying.",
    )


def test_explicit_command_statement_survives_real_selection_and_projection():
    question = "Which command starts the Docs MCP server?"
    fact = "Start the local stdio server with `doc-atlas mcp docs-serve`."
    packet, sources = _negative_and_positive(question, "The Docs MCP server uses stdio transport.", fact)
    forged = deepcopy(packet)
    forged["sources"][0]["text"] = forged["sources"][0]["text"].replace("docs-serve", "docs-other")
    forged["sources"][0]["content_sha256"] = hashlib.sha256(forged["sources"][0]["text"].encode()).hexdigest()
    refresh_action_packet_estimate(forged)
    assert validate_action_packet(forged, evidence_items=sources)


def test_only_typed_explicit_implementation_targets_resolve_without_edit_permission():
    question = "Implement lookup_context"
    assert build_patch_request_plan(question).operation == "none"
    assert not build_patch_request_plan(question).mutation_targets
    assert build_mutation_intent(question).operation == "none"
    code = "def lookup_context():\n    return 'source-bound context'"
    sources = [_source(code, path="src/lookup.py", source_class="source_evidence")]
    sources[0]["symbols"] = ["lookup_context"]
    plain, _, _ = _packet(question, sources, [])
    assert plain["result"] == "data" and "mutation_intent" not in plain
    requested = MutationIntentContract("modify", "source", (
        RequestedTarget("src/lookup.py", "path", -1, -1, provenance="explicit_task_contract"),
    ))
    resolved = resolve_mutation_targets(
        requested, sources, evidence_id_for_item=lambda row: evidence_identity_for_item(row)[0],
    )
    assert len(resolved.resolved_targets) == 1
    assert resolved.resolved_targets[0].path == "src/lookup.py"
    assert resolved.resolved_targets[0].exists is True
    packet, _, _ = _packet(question, sources, [], mutation=resolved)
    assert packet["completeness"] == "complete"
    assert packet["mutation_intent"]["requested_targets"][0]["provenance"] == "explicit_task_contract"
    absent = MutationIntentContract("modify", "source", (
        RequestedTarget("src/missing.py", "path", -1, -1, provenance="explicit_task_contract"),
    ))
    unresolved = resolve_mutation_targets(
        absent, sources, evidence_id_for_item=lambda row: evidence_identity_for_item(row)[0],
    )
    assert not unresolved.resolved_targets
    partial, _, _ = _packet(question, sources, [], mutation=unresolved)
    _missing_fact(partial, "src/missing.py")
    forged = deepcopy(packet)
    forged["edit_ready"] = True
    refresh_action_packet_estimate(forged)
    assert validate_action_packet(forged, evidence_items=sources, mutation_intent_contract=resolved)


@pytest.mark.parametrize("tool", ["get_docs_context", "lookup_context"])
def test_lifecycle_keywords_do_not_satisfy_explicit_offline_constraint(tool):
    question = f"In offline mode, will {tool} fetch missing documentation from the network, or must missing evidence require an explicit lifecycle action?"
    _negative_and_positive(
        question, f"{tool} retrieves documentation. The {tool} lifecycle uses prepare, inspect, and retry steps.",
        f"In offline mode, {tool} must not fetch missing documentation; an explicit lifecycle action is required.",
    )


def test_file_definition_does_not_satisfy_explicit_default_setting():
    _negative_and_positive(
        "What is the default cache budget in app.settings?",
        "app.settings is the application configuration file.",
        "The default cache budget in app.settings is 256 entries.",
    )


def test_explicit_public_inventory_has_exact_full_statement_witness():
    _negative_and_positive(
        "Which three public tools does the Docs MCP server expose?",
        "The Docs MCP server exposes documentation tools.",
        "The three Docs MCP public tools are `get_docs_context`, `prepare_docs`, and `docs_status`.",
    )


@pytest.mark.parametrize("question,path,fact,mention", [
    ("Where is the DocAtlas execution roadmap?", "docs/roadmap.md",
     "The DocAtlas execution roadmap is maintained in docs/roadmap.md.",
     "The DocAtlas execution roadmap describes implementation milestones."),
    ("How many connection retries does SocketPolicy allow?", "docs/retries.md",
     "SocketPolicy allows at most two connection retries.",
     "SocketPolicy delegates connection retries to the transport."),
])
def test_explicit_location_and_number_requirements_keep_conditional_scope(question, path, fact, mention):
    _negative_and_positive(question, mention, fact, path=path, paths=(path,))
    wrong_path = [_source(fact, path="docs/other.md")]
    scoped, _, _ = _packet(question, wrong_path, [fact], paths=(path,))
    _witness(scoped, wrong_path, fact)
    _missing_fact(scoped, path)  # Correct bytes in a different file do not cover the requested path.
    for tail in (" if the source is missing", " after an unknown operation"):
        conditional = question.rstrip("?") + tail + "?"
        base = [_source("# Contract\n\n" + fact, path=path)]
        condition_fact = f"The documented constraint{tail} is to stop and report unavailable evidence."
        partial, _, _ = _packet(conditional, base, [fact, condition_fact], paths=(path,))
        _witness(partial, base, fact)
        _missing_fact(partial, condition_fact)
        complete_sources = [*base, _source(condition_fact, path="docs/recovery.md")]
        complete, _, _ = _packet(conditional, complete_sources, [fact, condition_fact], paths=(path,))
        assert complete["completeness"] == "complete"
        _witness(complete, complete_sources, condition_fact)


def test_legacy_fail_closed_adapter_does_not_block_real_qualified_context(tmp_path, monkeypatch):
    question = "Does guide.md prove the source ownership contract?"
    assert project_retrieval_disposition(question) == "fail_closed"
    root = tmp_path / "project"
    root.mkdir()
    text = "# Source ownership\n\nguide.md defines the source ownership contract: source bytes remain repository-local.\n"
    (root / "guide.md").write_text(text)
    catalog = root / "docatlas.project-docs.yaml"
    catalog.write_text(yaml.safe_dump({"schema_version": 1, "code_files": [], "documents": [
        {"path": "guide.md", "role": "overview", "scope": "project", "description": "Source ownership contract."},
    ]}))
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "app-home"))
    monkeypatch.delenv("DOCATLAS_INDEX_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    service = create_local_mcp_service()
    assert not service.member_storage_policy.app_home.exists()
    entry, = read_project_docs_catalog(root).entries
    prepared = call_docs_tool_payload("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(root), "mutation": {
            "operation": "sync_project_docs", "confirm": True,
            "storage_path": str(service.member_storage_policy.db_path),
            "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
            "expected_generation_id": None,
            "documents": [{"path": "guide.md", "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                           "catalog_entry_hash": catalog_entry_hash(entry)}],
        },
    }, service)
    assert prepared.get("status") == "success", prepared
    request = {"question": question, "project_path": str(root), "scope": "project"}
    before = deepcopy(request)
    snapshots = []
    original_projection = context_tools.project_docs_context

    def observe_projection(*args, **kwargs):
        projected, snapshot = original_projection(*args, **kwargs)
        assert validate_model_visible_projection(projected, snapshot=snapshot, max_tokens=800) == []
        snapshots.append(snapshot)
        return projected, snapshot

    monkeypatch.setattr(context_tools, "project_docs_context", observe_projection)
    payload = call_docs_tool_payload("get_docs_context", request, service)
    assert request == before
    assert payload["status"] == "ok", payload
    assert snapshots
    assert {row["path_or_url"] for row in payload["sources"]} == {"guide.md"}
    for source in payload["sources"]:
        assert "source ownership contract" in source["snippet"]
        assert source["snippet"] in text
        raw = snapshots[-1][source["evidence_id"]]["source"]
        # Docs-mode digest binds the source envelope, unlike the v4 window hash.
        material = {
            "path": raw.get("path") or raw.get("source") or raw.get("url") or raw.get("source_url"),
            "section": raw.get("heading_path") or raw.get("title"),
            "content": raw.get("content") or raw.get("display_text"),
            "snippet": raw.get("snippet") or raw.get("code"),
            "version": raw.get("version_binding") or raw.get("version") or raw.get("requested_version"),
        }
        digest = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()
        assert source["content_sha256"] == digest
        assert source["line_start"] == 1 and source["line_end"] == 3
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert len(payload["sources"]) <= 3 and payload["estimated_tokens"] <= 800
    assert service.member_storage_policy.generation() == prepared["metrics"]["generation_id"]
