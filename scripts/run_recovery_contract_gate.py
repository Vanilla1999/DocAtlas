#!/usr/bin/env python3
"""Current recovery contract with named, independently checkable outcomes.

The original treasure question and document bytes remain regression inputs.
Natural-language parsing no longer synthesizes retry questions. Empty retrieval,
source eligibility, operational consent and authoritative conflict are separate
states; useful source context never grants answer or edit authority.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import tempfile
import traceback
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docmancer.docs.application.evidence_selection import (
    build_requirements, project_docs_selection_config, select_evidence,
)
from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.application._docs_context_projection_core import project_docs_context as project_context_core
from docmancer.docs.application.recovery import build_recovery_diagnosis, recovery_action
from docmancer.docs.interfaces.mcp.recovery_projection import _attach_recovery_diagnosis
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.retrieval.query_planning import extract_document_locator
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.project_context_quality.capture_public_context import capture_public_call
from eval.agent_developer_v1.structural_filename_controls import run_structural_filename_controls
from eval.agent_developer_v1.fts_literal_controls import run_fts_literal_controls
from eval.agent_developer_v1.ordinary_body_controls import run_ordinary_body_controls

REPORT_SCHEMA = "recovery-contract-v2"
TARGET_MODULES = (
    "docmancer.docs.application.recovery", "docmancer.docs.application.proofability",
    "docmancer.docs.interfaces.mcp.recovery_projection", "docmancer.docs.application._project_docs_service_part03",
    "docmancer.docs.application.source_reference_evidence", "docmancer.docs.application.reference_query_tagging",
    "docmancer.docs.application._docs_context_projection_core", "docmancer.docs.domain.project_doc_ranking",
    "docmancer.docs.domain.literal_context_admission",
    "docmancer.docs.domain.query_reference_binding",
    "eval.agent_developer_v1.structural_filename_controls",
    "docmancer.core._sqlite_store_part03", "eval.agent_developer_v1.fts_literal_controls",
    "docmancer.docs.domain.original_body_discovery", "docmancer.docs.domain.ordinary_body_context",
    "docmancer.docs.interfaces.mcp.context_tools", "eval.agent_developer_v1.ordinary_body_controls",
)
TREASURE = (
    "What is the documented contract for adaptive treasure gem trip sampling across positions 1,2,3, "
    "including 200 completed probes per position, meet_type=6 counters, gold encounter handling, "
    "checkpoint persistence, winner selection, and ambiguous mutation handling?"
)
TREASURE_PATH = "docs/ADAPTIVE_TREASURE_CONTRACT.md"
TREASURE_SOURCE = """# Adaptive Treasure Contract

## Scope
Adaptive treasure trip sampling covers positions 1,2,3.

## Sampling
Each position uses 200 completed probes.

## Counters
meet_type uses value 6 for gem counters.

## Persistence
checkpoint persistence stores completed progress.

## Selection
winner selection chooses the sampled position.

## Recovery
ambiguous mutation handling stops before state mutation.

## Safety
gold encounter handling preserves the gold target.
"""
ARCHITECTURE_SOURCE = "# Architecture\n\nThe project keeps domain contracts under docs/.\n"
CATALOG_SOURCE = """schema_version: 1
documents:
  - path: docs/ADAPTIVE_TREASURE_CONTRACT.md
    role: development
    scope: project
    description: Adaptive treasure source-of-truth contract.
    authority: source_of_truth
    status: active
    impact: track
  - path: ARCHITECTURE.md
    role: project_architecture
    scope: project
    description: High-level project architecture.
    authority: source_of_truth
    status: active
    impact: track
"""


class ContractFailure(AssertionError):
    """Only an explicit oracle guard can constitute an intended mutation kill."""


def _require(condition: Any, guard: str, detail: Any = None) -> None:
    if not condition:
        raise ContractFailure(guard, detail)


def _decision(question: str, candidates: list[dict], *, profile: str = "project_docs_answer"):
    requirements = build_requirements(question, profile=profile)
    # Historical selector input for the tiny diagnostic examples. Public DTO
    # acceptance below has no token ceiling.
    return select_evidence(candidates, question=question,
                           config=project_docs_selection_config(800), requirements=requirements)


def _no_authority(diagnosis: dict[str, Any]) -> None:
    _require(diagnosis.get("documentation_supported") is False, "recovery_no_documentation_authority", diagnosis)
    _require(diagnosis.get("investigation_allowed") is True, "recovery_investigation_allowed", diagnosis)
    _require(not diagnosis.get("suggested_questions"), "recovery_no_synthesized_questions", diagnosis)


@contextmanager
def _service():
    with tempfile.TemporaryDirectory(prefix="docatlas-recovery-") as temporary:
        root = Path(temporary)
        project = root / "project"
        (project / "docs").mkdir(parents=True)
        (project / TREASURE_PATH).write_text(TREASURE_SOURCE, encoding="utf-8")
        (project / "ARCHITECTURE.md").write_text(ARCHITECTURE_SOURCE, encoding="utf-8")
        (project / "docatlas.project-docs.yaml").write_text(CATALOG_SOURCE, encoding="utf-8")
        with isolated_service(root / "state") as (service, config):
            ingest = index_project(service, config, project)
            _require(ingest["indexed_paths"] == sorted([TREASURE_PATH, "ARCHITECTURE.md"]),
                     "recovery_fixture_indexed_members", ingest)
            yield service, project


def _observed_public_call(service: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Observe a real delivery veto as well as the authoritative projector."""
    delivery_inputs = []
    original = context_tools._explicit_delivery_block
    def observe(retrieval, **kwargs):
        delivery_inputs.append(deepcopy(retrieval))
        return original(retrieval, **kwargs)
    with patch.object(context_tools, "_explicit_delivery_block", observe):
        capture = capture_public_call(service, request)
    capture["delivery_inputs"] = delivery_inputs
    return capture


def _failure_diagnostics(case_id: str, detail: Any) -> dict[str, Any]:
    """Summarize an existing failed capture; no body bytes or extra calls."""
    def fields(value, keys):
        return {key: value[key] for key in keys if key in value} if isinstance(value, dict) else {}
    def rows(value):
        return value[:16] if isinstance(value, (list, tuple)) else ()
    def window(value):
        if not isinstance(value, dict):
            return {}
        text = next((value[key] for key in ("snippet", "display_text", "content") if isinstance(value.get(key), str)), "")
        return {**fields(value, ("evidence_id", "stable_chunk_id", "path_or_url", "path", "source_id", "generation_id")),
                "window_sha256": hashlib.sha256(text.encode()).hexdigest(), "window_characters": len(text),
                "original_trace": fields((value.get("retrieval_query_matches") or {}).get("query-original"),
                    ("qualified", "qualification_reason", "matched_terms", "match_ratio", "admission_only"))}
    capture = detail.get("capture", detail) if isinstance(detail, dict) else {}
    capture = capture if isinstance(capture, dict) else {}
    payload = capture.get("public_payload") or {}
    attempts = []
    for attempt in rows(capture.get("projection_attempts")):
        before, after = attempt.get("before_projection") or {}, attempt.get("after_projection") or {}
        diagnostics = (after.get("retrieval_diagnostics") or {}).get("docs_context_projection") or {}
        projected = attempt.get("projected_payload") or {}
        attempts.append({
            "input": fields(before, ("status", "reason_code", "requires_confirmation", "confirmation_reason")),
            "delivery": fields(before.get("delivery_decision"), ("deliverable", "reason_code")),
            "input_candidate_count": len(before.get("context_pack") or ()),
            "input_candidates": [window(row) for row in rows(before.get("context_pack"))],
            "projected": fields(projected, ("kind", "status", "reason_code", "context_available", "covered_query_ids", "missing_query_ids")),
            "projected_sources": [window(row) for row in rows(projected.get("sources"))],
            "admissions": [fields(row, ("reason", "query_id", "qualification_reason", "coverage_credit",
                                        "generation_id", "source_id", "path"))
                           for row in rows(diagnostics.get("literal_context_admissions"))],
            "rejections": [fields(row, ("reason", "reason_code", "evidence_id", "path", "query_id"))
                           for row in rows(diagnostics.get("projection_rejections"))],
            "snapshot_ids": sorted((attempt.get("snapshot") or {}).keys()),
            "snapshot_sources": [window(row.get("source")) for row in rows(list((attempt.get("snapshot") or {}).values()))],
        })
    return {
        "case": case_id, "capture_present": bool(capture.get("projection_attempts")),
        "fixture": fields(detail, ("positive_case_index", "read_index", "expected_body_sha256", "expected_path", "literal")),
        "request": fields(capture.get("request"), ("question", "project_path", "scope")),
        "public": fields(payload, ("kind", "status", "reason_code", "context_available",
                                   "answer_supported", "answer_available", "edit_ready", "covered_query_ids", "missing_query_ids")),
        "public_error": fields(payload.get("error"), ("reason_code", "exception_type", "retryable", "where")),
        "public_source_count": len(payload.get("sources") or ()),
        "public_sources": [window(row) for row in rows(payload.get("sources"))],
        "projection_attempt_count": len(capture.get("projection_attempts") or ()),
        "projection_attempts": attempts,
        "delivery_inputs": [fields(row, ("status", "reason_code", "requires_confirmation", "confirmation_reason"))
                            for row in rows(capture.get("delivery_inputs"))],
    }

def _assert_public_context(payload: dict[str, Any], project: Path, *, fact_guard: str,
                           capture: dict[str, Any] | None = None) -> None:
    detail = {"payload": payload, "capture": capture} if capture is not None else payload
    _require(payload.get("status") == "ok" and payload.get("kind") == "docs_context",
             fact_guard, detail)
    _require(payload.get("context_available") is True, fact_guard, detail)
    sources = payload.get("sources") or []
    _require(any("meet_type uses value 6 for gem counters." in row.get("snippet", "")
                 for row in sources), fact_guard, detail)
    _require(all(payload.get(key) is False for key in ("answer_supported", "answer_available", "edit_ready")),
             "recovery_context_no_answer_or_edit_authority", payload)
    identity = "local:" + hashlib.sha256(str(project.resolve()).encode()).hexdigest()
    for source in sources:
        _require(source.get("path_or_url") == TREASURE_PATH, "recovery_exact_source_path", source)
        text = source.get("snippet")
        _require(isinstance(text, str) and bool(text) and text in TREASURE_SOURCE,
                 "recovery_source_byte_fidelity", source)
        _require(source.get("project_identity") == identity and source.get("scope") == "project",
                 "recovery_source_scope_binding", source)
        _require(bool(re.fullmatch(r"[0-9a-f]{64}", source.get("content_sha256", ""))),
                 "recovery_source_hash_format", source)


def retrieval_miss() -> None:
    diagnosis = build_recovery_diagnosis(TREASURE, _decision(TREASURE, []))
    _require(diagnosis.get("origin") == "retrieval" and diagnosis.get("reason_code") == "retrieval_miss",
             "recovery_no_candidates_is_retrieval", diagnosis)
    _require("no_candidate_evidence" in diagnosis.get("detail_reasons", []),
             "recovery_empty_candidate_reason", diagnosis)
    _no_authority(diagnosis)
    _require(diagnosis.get("hard_stop") is False and diagnosis.get("disposition") == "search_local_source",
             "recovery_empty_candidates_allow_investigation", diagnosis)
    action = recovery_action(diagnosis, project_path="/repo", scope="project")
    _require(isinstance(action, dict) and action.get("tool") == "code_search",
             "recovery_local_source_handoff", action)
    _require(action.get("auto_execute") is False, "recovery_handoff_not_automatic", action)
    _require(action.get("repeat_docs_context") is False, "recovery_no_docs_retry_loop", action)
    _require(action.get("handled_by") == "coding_agent", "recovery_host_owns_search", action)


def original_fragments() -> None:
    # Preserve the original 100 nonce inputs; this is an invariance regression,
    # not evidence that another 100 different recovery contracts exist.
    questions = [TREASURE, *(f"What is the zxqv{index} contract for adaptive treasure sampling?"
                              for index in range(100))]
    for question in questions:
        diagnosis = build_recovery_diagnosis(question, _decision(question, []))
        _require(diagnosis.get("problem_spans") == [question], "recovery_original_diagnostic_fragments", diagnosis)
        _no_authority(diagnosis)
        _require(diagnosis.get("origin") == "retrieval" and diagnosis.get("hard_stop") is False,
                 "recovery_unknown_modifier_not_a_hard_stop", diagnosis)
        for fragment in diagnosis.get("recognized_spans") or []:
            _require(str(fragment).casefold() in question.casefold(), "recovery_no_invented_domain_tokens", diagnosis)


def operational_precedence() -> None:
    action = {
        "type": "prepare_docs", "tool": "prepare_docs", "requires_confirmation": True,
        "confirmation_reason": "network_fetch", "auto_execute": False,
        "arguments_patch": {"action": "prefetch_project_dependency_docs", "project_path": "/repo"},
    }
    original = {"next_action": action, "next_actions": [action], "requires_confirmation": True}
    snapshot = deepcopy(original)
    preserved = _attach_recovery_diagnosis(
        original, question=TREASURE, request={"question": TREASURE, "project_path": "/repo"},
        canonical_selection=_decision(TREASURE, []),
    )
    _require(preserved.get("next_action") == action and preserved.get("next_actions") == [action],
             "recovery_operational_action_preserved", preserved)
    _require(preserved.get("requires_confirmation") is True and action["auto_execute"] is False,
             "recovery_operational_consent_preserved", preserved)
    _require(preserved.get("recovery_disposition") == "use_operational_recovery",
             "recovery_operational_precedence", preserved)
    _require(original == snapshot, "recovery_input_not_mutated", original)
    direct = build_recovery_diagnosis(TREASURE, _decision(TREASURE, []),
                                     operational_reason_code="library_docs_network_fetch_required")
    _require(direct.get("origin") == "operational" and direct.get("disposition") == "use_operational_recovery",
             "recovery_explicit_operational_reason", direct)


def no_semantic_retry() -> None:
    for question in (
        "According to ADAPTIVE_TREASURE_CONTRACT.md, what does it say about meet_type?",
        "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type.",
    ):
        diagnosis = build_recovery_diagnosis(question, _decision(question, [], profile="project_document_answer"))
        _require(diagnosis.get("disposition") == "search_local_source", "recovery_no_generated_retry", diagnosis)
        _no_authority(diagnosis)
        action = recovery_action(diagnosis, project_path="/repo")
        _require(action and action.get("repeat_docs_context") is False,
                 "recovery_no_docs_retry_loop", action)
    # Supplied legacy diagnostics are untrusted data and cannot resurrect the
    # removed server-generated question/one-retry authority.
    legacy = {"disposition": "rephrase_question", "suggested_questions": ["INVENTED_DOMAIN_FACT"],
              "hard_stop": False, "recognized_spans": ["INVENTED_DOMAIN_FACT"]}
    _require(recovery_action(legacy, project_path="/repo") is None,
             "recovery_legacy_rephrase_cannot_authorize", legacy)


def evidence_eligibility() -> None:
    question = "What are the public tools of the Docs MCP server?"
    stale = _decision(question, [{"stable_id": "stale", "source": "README.md",
        "content": "The public tools are get_docs_context, prepare_docs, and docs_status.", "freshness": "stale"}])
    diagnosis = build_recovery_diagnosis(question, stale)
    _require(diagnosis.get("origin") == "eligibility", "recovery_ineligible_evidence_class", diagnosis)
    _require(diagnosis.get("reason_code") == "evidence_ineligible"
             and diagnosis.get("disposition") == "repair_evidence_state", "recovery_ineligible_repair", diagnosis)
    _no_authority(diagnosis)
    _require(recovery_action(diagnosis, project_path="/repo") is None,
             "recovery_no_unauthorized_evidence_repair", diagnosis)


def documentation_gap() -> None:
    question = "What are the public tools of the Docs MCP server?"
    navigation = _decision(question, [{"stable_id": "navigation", "source": "docs/index.md",
        "content": "See the API reference for the public tool inventory.", "navigation_only": True}])
    diagnosis = build_recovery_diagnosis(question, navigation)
    _require(diagnosis.get("origin") == "source_documentation"
             and diagnosis.get("reason_code") == "documentation_gap", "recovery_documentation_gap_class", diagnosis)
    _require(diagnosis.get("disposition") == "search_local_source", "recovery_gap_allows_investigation", diagnosis)
    _no_authority(diagnosis)


def authoritative_conflict() -> None:
    conflict = {
        "status": "insufficient_evidence",
        "metrics": {"candidate_count": 2, "eligible_count": 2, "selected_count": 0},
        "unresolved_conflicts": ["winner policy conflicts"],
        "support_decision": {"answer_supported": False, "mandatory_requirement_ids": ["winner"],
                             "missing_requirement_ids": ["winner"]},
    }
    question = "What is the winner policy?"
    diagnosis = build_recovery_diagnosis(question, conflict)
    _require(diagnosis.get("origin") == "conflict", "recovery_conflict_class", diagnosis)
    _require(diagnosis.get("hard_stop") is True, "recovery_authoritative_conflict_stops", diagnosis)
    _require(diagnosis.get("disposition") == "resolve_authoritative_conflict",
             "recovery_conflict_disposition", diagnosis)
    _require(recovery_action(diagnosis, project_path="/repo") is None, "recovery_conflict_has_no_action", diagnosis)
    _no_authority(diagnosis)
    operational = {"tool": "prepare_docs", "requires_confirmation": True,
                   "arguments_patch": {"action": "prefetch_project_dependency_docs", "project_path": "/repo"}}
    payload = {"next_action": operational, "next_actions": [operational],
               "recommended_next_action": operational, "requires_confirmation": True,
               "operational_reason_code": "library_docs_network_fetch_required"}
    before = deepcopy(payload)
    attached = _attach_recovery_diagnosis(payload, question=question,
        request={"question": question, "project_path": "/repo"}, canonical_selection=conflict)
    _require(attached.get("hard_stop") is True and not attached.get("next_action")
             and not attached.get("next_actions") and not attached.get("recommended_next_action"),
             "recovery_conflict_suppresses_actions", attached)
    _require(payload == before, "recovery_conflict_input_not_mutated", payload)


def projection_states() -> None:
    decision = _decision(TREASURE, [])
    cases = (
        ({"context_pack": []}, "retrieval", "no_candidates"),
        ({"context_pack": [{"retrieval_query_matches": {}}]}, "eligibility", "evidence_rejected"),
        ({"context_pack": [{"retrieval_query_matches": {"query-original": {"qualified": True}}}]},
         "selection", "visible_evidence_lost"),
    )
    for retrieval, origin, reason in cases:
        diagnosis = build_recovery_diagnosis(TREASURE, decision,
                                            projection={"context_available": False}, retrieval=retrieval)
        _require(diagnosis.get("origin") == origin and diagnosis.get("reason_code") == reason,
                 "recovery_projection_state_class", diagnosis)
        _no_authority(diagnosis)
    available = build_recovery_diagnosis(TREASURE, decision, projection={"context_available": True},
                                        retrieval={"context_pack": [{"content": "known source context"}]})
    _require(available == {}, "recovery_not_added_to_available_context", available)


def exact_document_recovery() -> dict[str, Any]:
    question = "In docs/ADAPTIVE_TREASURE_CONTRACT.md, summarize meet_type."
    _require(extract_document_locator(question) == TREASURE_PATH, "recovery_exact_locator_grammar")
    requirements = build_requirements(question, required_evidence_paths=(TREASURE_PATH,),
                                      profile="project_document_answer")
    mandatory = [item for item in requirements if item.mandatory]
    _require(any(item.kind == "evidence_path" and item.value == TREASURE_PATH for item in mandatory),
             "recovery_explicit_document_scope", mandatory)
    _require(any(item.kind == "exact_term" and item.value == "meet_type" for item in mandatory),
             "recovery_original_exact_anchor", mandatory)
    _require(not any(item.kind == "exact_term" and "adaptive_treasure_contract.md" in item.value.casefold()
                     for item in mandatory), "recovery_path_not_invented_topic", mandatory)
    with _service() as (service, project):
        original_query = service.project_docs.query_project_docs
        store = service._read_agent_instance().store
        original_full_scan = store.list_sections_for_embedding
        generation = service.member_storage_policy.generation()
        service.project_docs.query_project_docs = lambda *args, **kwargs: []
        def forbidden_scan(*args, **kwargs):
            raise RuntimeError("exact-document fallback enumerated the active generation")
        store.list_sections_for_embedding = forbidden_scan
        try:
            capture = _observed_public_call(service, {
                "question": question, "project_path": str(project), "scope": "project",
            })
            payload = capture["public_payload"]
        finally:
            service.project_docs.query_project_docs = original_query
            store.list_sections_for_embedding = original_full_scan
        _assert_public_context(payload, project, fact_guard="recovery_exact_document_source_fact", capture=capture)
        _require(service.member_storage_policy.generation() == generation, "recovery_read_does_not_mutate_members")
        _require((project / TREASURE_PATH).read_text(encoding="utf-8") == TREASURE_SOURCE,
                 "recovery_read_does_not_mutate_source")
        return {"full_dto_tokens": estimate_projection_tokens(payload),
                "full_dto_utf8_bytes": len(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                      separators=(",", ":")).encode())}


def literal_anchor_context() -> dict[str, Any]:
    with _service() as (service, project):
        request = {
            "question": TREASURE, "project_path": str(project), "scope": "project",
        }
        capture = _observed_public_call(service, request)
        payload = capture["public_payload"]
        _assert_public_context(payload, project, fact_guard="recovery_original_question_source_fact", capture=capture)
        _require(payload.get("investigation_allowed") is True, "recovery_context_allows_investigation", payload)
        attempts = capture["projection_attempts"]
        _require(len(attempts) == 1, "recovery_literal_single_public_projection", capture)
        attempt = attempts[0]
        admissions = (attempt["after_projection"].get("retrieval_diagnostics") or {}).get(
            "docs_context_projection", {}).get("literal_context_admissions") or []
        _require(admissions and all(row.get("coverage_credit") is False for row in admissions),
                 "recovery_literal_admission_observed", attempt)
        _require(payload.get("query_coverage") == "partial"
                 and "query-original" not in payload.get("covered_query_ids", [])
                 and "query-original" in payload.get("missing_query_ids", []),
                 "recovery_partial_no_query_credit", payload)
        _require(not validate_model_visible_projection(attempt["projected_payload"], snapshot=attempt["snapshot"]),
                 "recovery_literal_snapshot_validator", attempt)
        # Independently bind each delivered quote to the actual immutable source
        # bytes, rather than accepting a plausible-looking hexadecimal hash.
        for source in payload["sources"]:
            bound = attempt["snapshot"][source["evidence_id"]]
            original = bound["source"]
            evidence = original["_reference_evidence"]
            _require(evidence["raw_document"] == TREASURE_SOURCE
                     and evidence["source"]["content_sha256"] == hashlib.sha256(TREASURE_SOURCE.encode()).hexdigest()
                     and TREASURE_SOURCE[evidence["char_start"]:evidence["char_end"]] == evidence["text"],
                     "recovery_literal_actual_source_binding", evidence)
            _require({key: value for key, value in source.items() if key != "source_uri"}
                     == {key: value for key, value in bound["projected_source"].items() if key != "source_uri"},
                     "recovery_literal_visible_snapshot_binding", source)
        _literal_context_replay_controls(attempt["before_projection"])
        _literal_context_state_controls(service, project, request)
        # Cost is evidence, not a pass/fail ceiling. Source facts and guards above
        # decide acceptance; trimming their meaning to reach 800 cannot pass.
        return {"full_dto_tokens": estimate_projection_tokens(payload),
                "full_dto_utf8_bytes": len(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                      separators=(",", ":")).encode()),
                "literal_context_admissions": admissions,
                "replay_controls": 13, "confirmed_source_changes": 5,
                "catalog_revocations": 1}


def _literal_context_replay_controls(retrieval: dict[str, Any]) -> None:
    """Replay the admission core on real inputs; no forged flag grants trust.

    Full public delivery and current-file/catalog changes are exercised by the
    neighbouring calls. These transformations isolate the immutable-source
    admission from the facade's independent inspection/recovery targets.
    """
    _require(bool(retrieval.get("context_pack")), "recovery_literal_controls_have_candidates")
    for change in ("project", "scope", "catalog", "file_hash", "generation", "stale",
                   "window", "body", "raw_document", "missing_reference", "forged_admission"):
        altered = deepcopy(retrieval)
        for source in altered["context_pack"]:
            if change == "project":
                source["project_identity"] = "foreign-project"
            elif change == "scope":
                source.update(doc_scope="module", module_path="foreign-module")
            elif change == "catalog":
                source["_source_catalog_hash"] = "sha256:" + "0" * 64
            elif change == "file_hash":
                source["_source_snapshot_sha256"] = "sha256:" + "0" * 64
            elif change == "generation":
                source["generation_id"] = "foreign-generation"
            elif change == "stale":
                source["freshness"] = "stale"
            elif change == "window":
                source["char_start"] += 1
            elif change in {"body", "forged_admission"}:
                source.update(content="meet_type uses value 9 for gem counters.",
                              display_text="meet_type uses value 9 for gem counters.")
                if change == "forged_admission":
                    source.update(qualified=True, context_eligible=True,
                                  literal_context_admission={"coverage_credit": False})
                    source["retrieval_query_matches"] = {"query-original": {
                        "qualified": True, "literal_context_admission": {"coverage_credit": False},
                        "query_text": TREASURE, "query_origin": "original", "relation": "direct",
                    }}
            elif change == "raw_document":
                source["_reference_evidence"]["raw_document"] += "\nForged snapshot tail.\n"
            elif change == "missing_reference":
                source.pop("_reference_evidence", None)
        result, snapshot = project_context_core(retrieval=altered)
        _require(not result.get("context_available") and not result.get("sources") and not snapshot,
                 "recovery_literal_snapshot_binding", {"change": change, "payload": result})
        _require(not validate_model_visible_projection(result, snapshot=snapshot),
                 "recovery_literal_negative_projection_valid", {"change": change, "payload": result})
    for control in ({"requires_confirmation": True},
                    {"delivery_decision": {"deliverable": False, "reason_code": "source_access_revoked"}}):
        result, snapshot = project_context_core(retrieval={**deepcopy(retrieval), **control})
        _require(not result.get("sources") and not snapshot,
                 "recovery_literal_operational_veto", {"control": control, "payload": result})


def _literal_context_state_controls(service: Any, project: Path, request: dict[str, Any]) -> None:
    """Confirmed source changes preserve literal facts and remove lost evidence."""
    for name, text in (
        ("heading_only", "# meet_type\n\nUnrelated orchard fruit details.\n"),
        ("identifier_only", "# Counters\n\n- meet_type\n"),
        ("link_only", "# Counters\n\n[meet_type](https://example.invalid/reference)\n"),
        ("identifier_prefix", "# Counters\n\nmeet_type_cached uses value 6 for gem counters.\n"),
    ):
        (project / TREASURE_PATH).write_text(text, encoding="utf-8")
        index_project(service, service.config, project)
        result = call_docs_tool_payload("get_docs_context", request, service)
        _require(not result.get("context_available") and not result.get("sources"),
                 "recovery_literal_body_admission_safety", {"change": name, "payload": result})
    changed = TREASURE_SOURCE.replace("meet_type uses value 6", "meet_type uses value 9")
    (project / TREASURE_PATH).write_text(changed, encoding="utf-8")
    index_project(service, service.config, project)
    result = call_docs_tool_payload("get_docs_context", request, service)
    _require(result.get("context_available") is True and any(
        "meet_type uses value 9 for gem counters." in row.get("snippet", "") for row in result.get("sources", [])
    ) and all("meet_type uses value 6" not in row.get("snippet", "") for row in result.get("sources", [])),
             "recovery_literal_source_change_visible", result)
    _require(all(result.get(key) is False for key in ("answer_supported", "answer_available", "edit_ready")),
             "recovery_context_no_answer_or_edit_authority", result)
    # Removing membership must revoke the old quote even while the source bytes
    # and the previously committed stored member still physically exist.
    catalog = CATALOG_SOURCE[:CATALOG_SOURCE.index("  - path: docs/")] + CATALOG_SOURCE[CATALOG_SOURCE.index("  - path: ARCHITECTURE.md"):]
    (project / "docatlas.project-docs.yaml").write_text(catalog, encoding="utf-8")
    result = call_docs_tool_payload("get_docs_context", request, service)
    _require(not result.get("sources"), "recovery_literal_catalog_revocation", result)


def original_discovery_attribution() -> dict[str, Any]:
    """A real original hit survives lookups; lookup hits cannot invent that hit."""
    from docmancer.retrieval.dispatch import RetrievalDispatcher

    question = "Storage persists records"
    lookups = ["Compression reduces record size", "Journal recovers committed state"]
    path = "docs/storage.md"
    text = ("# Storage\n\nStorage persists records on disk. Compression reduces record size. "
            "Journal recovers committed state.\n")
    with tempfile.TemporaryDirectory(prefix="docatlas-original-discovery-") as temporary:
        root = Path(temporary)
        project = root / "project"
        write_project(project, {path: text})
        with isolated_service(root / "state") as (service, config):
            index_project(service, config, project)
            request = {"question": question, "project_path": str(project), "scope": "project"}

            def checked_call(arguments: dict[str, Any]) -> dict[str, Any]:
                capture = _observed_public_call(service, arguments)
                payload = capture["public_payload"]
                _require(payload.get("status") == "ok" and payload.get("context_available") is True
                         and any("Storage persists records on disk." in source.get("snippet", "")
                                 for source in payload.get("sources", [])),
                         "retrieval_original_discovery_source_fact", capture)
                _require(all(payload.get(key) is False for key in (
                    "answer_supported", "answer_available", "edit_ready",
                )), "retrieval_discovery_never_authorizes_answer", payload)
                _require(all(source.get("path_or_url") == path and source.get("snippet", "") in text
                             for source in payload["sources"]), "retrieval_discovery_exact_source_bytes", payload)
                _require(len(capture["projection_attempts"]) == 1,
                         "retrieval_discovery_one_public_projection", capture)
                attempt = capture["projection_attempts"][0]
                _require(not validate_model_visible_projection(attempt["projected_payload"], snapshot=attempt["snapshot"]),
                         "retrieval_discovery_valid_snapshot", attempt)
                return payload

            original = checked_call(request)
            _require("query-original" in original.get("covered_query_ids", []),
                     "retrieval_original_coverage_survives_lookups", original)
            combined_request = {**request, "lookup_queries": lookups}
            combined = checked_call(combined_request)
            _require(set(combined.get("covered_query_ids", [])) == {
                "query-original", "query-lookup-1", "query-lookup-2",
            }, "retrieval_original_coverage_survives_lookups", combined)

            real_run = RetrievalDispatcher.run
            withheld = []
            def lookup_only_dispatch(dispatcher, query, *args, **kwargs):
                result = real_run(dispatcher, query, *args, **kwargs)
                if query == question:
                    withheld.append(len(result.chunks))
                    return replace(result, chunks=[])
                # A source may claim it was returned for the original. Only
                # the host's actual acquisition ledger can establish that fact.
                chunks = [chunk.model_copy(update={"metadata": {
                    **(chunk.metadata or {}), "original_discovery": True,
                    "retrieval_query_ids": ["query-original"],
                    "retrieval_query_matches": {"query-original": {
                        "query_text": question, "query_origin": "original", "relation": "direct",
                        "qualified": True, "admission_only": False, "lexical_score": 999,
                    }},
                }}) for chunk in result.chunks]
                return replace(result, chunks=chunks)
            with patch.object(RetrievalDispatcher, "run", lookup_only_dispatch):
                lookup_only = checked_call(combined_request)
            _require(withheld and any(withheld), "retrieval_control_withheld_real_original_hits", withheld)
            _require(set(lookup_only.get("covered_query_ids", [])) == {"query-lookup-1", "query-lookup-2"}
                     and "query-original" in lookup_only.get("missing_query_ids", [])
                     and lookup_only.get("query_coverage") == "partial",
                     "retrieval_lookup_cannot_mint_original_discovery", lookup_only)
            _require((project / path).read_text(encoding="utf-8") == text,
                     "retrieval_discovery_read_preserves_source")
            return {"original_covered_ids": original["covered_query_ids"],
                    "combined_covered_ids": combined["covered_query_ids"],
                    "lookup_only_covered_ids": lookup_only["covered_query_ids"],
                    "withheld_original_acquisitions": len(withheld),
                    "full_dto_tokens": estimate_projection_tokens(combined)}


def closed_literal_context() -> dict[str, Any]:
    """Real source reads keep closed literal context, never inferred conditions."""
    fts = run_fts_literal_controls(_require, _observed_public_call)
    source_path = "docs/literal-context.md"
    bodies = {
        "OrdersDraftStore": "OrdersDraftStore stores draft orders as JSON records keyed by order id before upload.",
        "PaymentOutbox": "PaymentOutbox writes pending payment events until confirmation.",
        "RelayBufferCell": "RelayBufferCell preserves opaque λ bytes before upload.",
        "DispatchInvariant": "DispatchInvariant rejects records missing an id or a currency.",
    }
    positives, negatives, read_checks = [], [], 0
    with tempfile.TemporaryDirectory(prefix="docatlas-closed-context-") as temporary:
        root = Path(temporary)
        project = root / "project"
        write_project(project, {source_path: bodies["OrdersDraftStore"]})
        with isolated_service(root / "state") as (service, config):
            index_project(service, config, project)
            policy = service.member_storage_policy

            def state():
                return {
                    "generation": policy.generation(),
                    "store_sha256": hashlib.sha256(policy.db_path.read_bytes()).hexdigest(),
                    "document_sha256": hashlib.sha256((project / source_path).read_bytes()).hexdigest(),
                    "catalog_sha256": hashlib.sha256((project / "docatlas.project-docs.yaml").read_bytes()).hexdigest(),
                }

            def read(question):
                nonlocal read_checks
                before = state()
                capture = _observed_public_call(service, {
                    "question": question, "project_path": str(project), "scope": "project",
                })
                after = state()
                if after != before:
                    print("RECOVERY_READ_STATE " + json.dumps({
                        "case": "closed_literal_context", "read_number": read_checks + 1,
                        "question": question, "source_path": source_path,
                        "differences": [{"field": key, "before": before[key], "after": after[key]}
                                        for key in before if before[key] != after[key]],
                    }, ensure_ascii=False, sort_keys=True))
                _require(after == before, "recovery_closed_context_is_read_only", capture)
                read_checks += 1
                return capture

            def indexed_body(text):
                (project / source_path).write_text(text, encoding="utf-8")
                prepared = index_project(service, config, project)
                _require(prepared["indexed_paths"] == [source_path]
                         and not prepared["excluded_or_failed_paths"] and not prepared["unexpected_paths"],
                         "recovery_closed_fixture_exact_members", prepared)

            def context(question, literal, body, *, count_phrase=None, explain=False):
                capture = read(question)
                payload = capture["public_payload"]
                _require(payload.get("status") == "ok" and payload.get("kind") == "docs_context"
                         and payload.get("context_available") is True
                         and any(source.get("snippet") == body for source in payload.get("sources", [])),
                         "recovery_count_literal_source_fact" if count_phrase is not None
                         else "recovery_explain_literal_source_fact" if explain
                         else "recovery_closed_literal_source_fact", {
                             "capture": capture, "positive_case_index": len(positives) + 1,
                             "read_index": read_checks, "expected_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                             "expected_path": source_path, "literal": literal,
                         })
                _require(all(payload.get(key) is False for key in (
                    "answer_supported", "answer_available", "edit_ready",
                )), "recovery_closed_no_answer_or_edit", payload)
                _require(payload.get("query_coverage") == "partial"
                         and "query-original" not in payload.get("covered_query_ids", [])
                         and "query-original" in payload.get("missing_query_ids", []),
                         "recovery_closed_no_query_credit", payload)
                _require(len(capture["projection_attempts"]) == 1,
                         "recovery_closed_single_projection", capture)
                attempt = capture["projection_attempts"][0]
                _require(not validate_model_visible_projection(
                    attempt["projected_payload"], snapshot=attempt["snapshot"],
                ), "recovery_closed_snapshot_validator", attempt)
                for source in payload["sources"]:
                    _require(source.get("path_or_url") == source_path
                             and isinstance(source.get("snippet"), str) and source["snippet"] in body,
                             "recovery_closed_source_bytes", source)
                    bound = attempt["snapshot"][source["evidence_id"]]
                    original = bound["source"]
                    evidence = original["_reference_evidence"]
                    trace = original["retrieval_query_matches"]["query-original"]
                    _require(evidence["raw_document"] == body
                             and evidence["source"]["content_sha256"] == hashlib.sha256(body.encode()).hexdigest()
                             and body[evidence["char_start"]:evidence["char_end"]] == evidence["text"],
                             "recovery_closed_current_body_binding", evidence)
                    _require(trace.get("query_text") == question and trace.get("qualified") is False
                             and trace.get("qualification_reason") == "insufficient_visible_match",
                             "recovery_closed_original_stays_unverified", trace)
                    reference, = [row for row in original["_reference_root_plan"]["references"]
                                   if row["mention"]["text"] == literal]
                    _require(reference["role"] == "unresolved" and reference["state"] == "unresolved"
                             and reference["mention"]["explicit"] is False,
                             "recovery_closed_no_reference_role_grant", reference)
                    _require({key: value for key, value in source.items() if key != "source_uri"}
                             == {key: value for key, value in bound["projected_source"].items() if key != "source_uri"},
                             "recovery_closed_visible_snapshot_binding", source)
                admissions = (attempt["after_projection"].get("retrieval_diagnostics") or {}).get(
                    "docs_context_projection", {}).get("literal_context_admissions") or []
                _require(admissions and all(admission.get("coverage_credit") is False for admission in admissions)
                         and any(witness["text"] == literal for admission in admissions
                                 for witness in admission.get("body_witnesses", [])),
                         "recovery_closed_literal_admission_observed", admissions)
                if explain:
                    expected = {
                        "text": literal, "char_start": body.index(literal),
                        "char_end": body.index(literal) + len(literal),
                        "query_char_start": question.index(literal),
                        "query_char_end": question.index(literal) + len(literal),
                        "kind": "literal_explain_context",
                    }
                    actual_witnesses = [
                        witness for admission in admissions
                        for witness in admission.get("body_witnesses", [])
                    ]
                    _require(bool(actual_witnesses) and all(
                        all(witness.get(key) == value for key, value in expected.items())
                        for witness in actual_witnesses
                    ), "recovery_explain_exact_raw_spans", {"expected": expected, "actual": admissions})
                if count_phrase is not None:
                    expected_pair = {
                        "text": literal, "char_start": body.index(literal),
                        "char_end": body.index(literal) + len(literal),
                        "query_char_start": question.index(literal),
                        "query_char_end": question.index(literal) + len(literal),
                        "kind": "literal_count_context",
                        "literal_phrase": {
                            "text": count_phrase, "char_start": body.index(count_phrase),
                            "char_end": body.index(count_phrase) + len(count_phrase),
                            "query_char_start": question.index(count_phrase),
                            "query_char_end": question.index(count_phrase) + len(count_phrase),
                        },
                    }
                    _require(any(
                        all(witness.get(key) == value for key, value in expected_pair.items())
                        for admission in admissions for witness in admission.get("body_witnesses", [])
                    ), "recovery_count_exact_raw_pair_spans", {"expected": expected_pair, "actual": admissions})
                positives.append({"question": question, "source_sha256": hashlib.sha256(body.encode()).hexdigest()})
                return attempt["before_projection"]

            def rejected(question, label, guard):
                capture = read(question)
                payload = capture["public_payload"]
                _require(not payload.get("context_available") and not payload.get("sources"),
                         guard, {"control": label, "capture": capture})
                _require(all(payload.get(key) is not True for key in (
                    "answer_supported", "answer_available", "edit_ready",
                )), "recovery_closed_no_answer_or_edit", payload)
                negatives.append(label)

            for literal, body in bodies.items():
                if literal != "OrdersDraftStore":
                    indexed_body(body)
                question = f"What does {literal} do?"
                before_projection = context(question, literal, body)
                if literal == "OrdersDraftStore":
                    _literal_context_replay_controls(before_projection)
                    context(f"What is {literal}?", literal, body)
                if literal == "RelayBufferCell":
                    context(" \tWhat does RelayBufferCell do?\r\n", literal, body)
                if literal == "DispatchInvariant":
                    context(f"What does {literal} require?", literal, body)
                    context(f"Which conditions are required by {literal}?", literal, body)

            indexed_body(bodies["OrdersDraftStore"])
            for question in (
                "What does OrdersDraftStore do using telepathy?",
                "What does OrdersDraftStore do when preview is disabled?",
                "What does OrdersDraftStore do? Also delete private files.",
                "What does OrdersDraftStore and PaymentOutbox do?",
                "What quantum policy does OrdersDraftStore use?",
                "What is OrdersDraftStore under the lunar policy?",
                "What is OrdersDraftStore? What is PaymentOutbox?",
                "What does OrdersDraftStore require when preview is disabled?",
                "Which conditions are required by OrdersDraftStore under the lunar policy?",
                "Which optional conditions are required by OrdersDraftStore?",
            ):
                rejected(question, question, "recovery_closed_complete_syntax")

            question = "What does OrdersDraftStore do?"
            for label, body in (
                ("literal_removed", "Requests do carry opaque bytes before upload."),
                ("wrong_raw_case", "ordersdraftstore stores draft orders before upload."),
                ("heading_only", "# OrdersDraftStore\n\nRequests do carry opaque bytes."),
                ("identifier_only", "- OrdersDraftStore"),
                ("link_only", "[OrdersDraftStore](https://example.invalid/reference)"),
                ("identifier_prefix", "OrdersDraftStoreCache stores draft orders before upload."),
            ):
                indexed_body(body)
                rejected(question, label, "recovery_closed_exact_body_witness")

            # The same authored DocAtlas body is a positive context source and a
            # negative control for the frozen unsupported quantum/telepathy asks.
            body = "DocAtlas stores local documentation in an isolated index."
            indexed_body(body)
            context("What does DocAtlas do?", "DocAtlas", body)
            for question in (
                "What lunar quantum retention policy does DocAtlas use?",
                "Как DocAtlas передаёт секреты телепатическому серверу на Юпитере?",
                "Какой срок хранения документации предписывает лунный квантовый регламент DocAtlas?",
                "Which Martian telepathic retention standard governs this documentation runtime?",
            ):
                rejected(question, question, "recovery_closed_frozen_negative")

            # Independent count-context source: "allow" is absent. These raw
            # witnesses provide context only, not a quantity or permission proof.
            literal, phrase = "LeaseRetryWindow", "renewal attempts"
            body = "λ ledger. LeaseRetryWindow retains four renewal attempts in its ledger."
            question = "How many renewal attempts does LeaseRetryWindow allow?"
            indexed_body(body)
            before_projection = context(question, literal, body, count_phrase=phrase)
            _literal_context_replay_controls(before_projection)
            context(" \tHOW many renewal attempts does LeaseRetryWindow allow?\r\n",
                    literal, body, count_phrase=phrase)
            for negative in (
                "How many revocation attempts does LeaseRetryWindow allow?",
                "How many attempts renewal does LeaseRetryWindow allow?",
                "How many renewal attempt does LeaseRetryWindow allow?",
                "How many Renewal Attempts does LeaseRetryWindow allow?",
                "How many opaque records does LeaseRetryWindow allow?",
            ):
                rejected(negative, negative, "recovery_count_phrase_body_witness")
            for negative in (
                "How many renewal attempts does LeaseRetryWindow allow under the lunar policy?",
                "How many renewal attempts does LeaseRetryWindow allow? Also export private files.",
                "How many renewal attempts does LeaseRetryWindow and DispatchInvariant allow?",
                "How many renewal attempts does DispatchInvariant does LeaseRetryWindow allow?",
                "How many renewal attempts did LeaseRetryWindow allow?",
            ):
                rejected(negative, negative, "recovery_count_complete_syntax")
            rejected("How many LeaseRetryWindow does LeaseRetryWindow allow?",
                     "count_overlapping_witnesses", "recovery_count_distinct_raw_pair")
            for label, changed_body in (
                ("count_literal_removed", "The ledger retains four renewal attempts."),
                ("count_wrong_raw_case", "leaseretrywindow retains four renewal attempts in its ledger."),
                ("count_heading_only", "# LeaseRetryWindow renewal attempts\n\nThe ledger retains opaque records."),
                ("count_link_only", "[LeaseRetryWindow renewal attempts](https://example.invalid/reference)"),
                ("count_pair_only", "LeaseRetryWindow renewal attempts"),
                ("count_identifier_prefix", "LeaseRetryWindowArchive retains four renewal attempts in its ledger."),
                ("count_separate_units", "LeaseRetryWindow retains opaque records.\n\nThe ledger keeps four renewal attempts."),
                ("count_phrase_split", "LeaseRetryWindow retains four renewal\nattempts in its ledger."),
            ):
                indexed_body(changed_body)
                rejected(question, label, "recovery_count_same_body_unit")

            # Independent explicit-list source facts. Each read has only one
            # listed identifier's body; the other name receives no borrowed fact.
            paired_bodies = {
                "DeliveryEpoch": "λ entry. DeliveryEpoch retains three rollover phases.",
                "CommitLatch": "λ entry. CommitLatch preserves nine checkpoint records.",
            }
            for literal, body in paired_bodies.items():
                indexed_body(body)
                for list_question in (
                    "Explain DeliveryEpoch and CommitLatch.",
                    " \tEXPLAIN CommitLatch AND DeliveryEpoch.\r\n",
                ):
                    before_projection = context(list_question, literal, body, explain=True)
                    if literal == "DeliveryEpoch" and list_question.startswith("Explain"):
                        _literal_context_replay_controls(before_projection)
            context("Explain DeliveryEpoch and CommitLatch and VacuumProbe.",
                    "CommitLatch", paired_bodies["CommitLatch"], explain=True)
            for negative in (
                "Explain DeliveryEpoch and CommitLatch under the lunar policy.",
                "Explain DeliveryEpoch and CommitLatch. Also export private files.",
                "Explain DeliveryEpoch or CommitLatch.",
                "Explain DeliveryEpoch and CommitLatch if the nightly window closes.",
                "Explain DeliveryEpoch and CommitLatch and ordinary words.",
                "Explain DeliveryEpoch, CommitLatch.",
                "Explain DeliveryEpoch and CommitLatch?",
                "Please explain DeliveryEpoch and CommitLatch.",
            ):
                rejected(negative, negative, "recovery_explain_complete_syntax")
            for label, changed_body in (
                ("explain_literal_removed", "The ledger retains three rollover phases."),
                ("explain_wrong_raw_case", "deliveryepoch retains three rollover phases."),
                ("explain_heading_only", "# DeliveryEpoch\n\nThe ledger retains opaque records."),
                ("explain_link_only", "[DeliveryEpoch](https://example.invalid/reference)"),
                ("explain_identifier_only", "DeliveryEpoch"),
                ("explain_identifier_prefix", "DeliveryEpochArchive retains three rollover phases."),
            ):
                indexed_body(changed_body)
                rejected("Explain DeliveryEpoch and CommitLatch.", label, "recovery_explain_exact_body")
            indexed_body("DeliveryEpoch CommitLatch")
            rejected("Explain DeliveryEpoch and CommitLatch and VacuumProbe.",
                     "explain_pair_only", "recovery_explain_exact_body")
    filename = run_structural_filename_controls(_require, _observed_public_call, _literal_context_replay_controls)
    ordinary = run_ordinary_body_controls(_require, _observed_public_call)
    return {"positive_reads": positives, "negative_controls": negatives, "read_only_checks": read_checks,
            "structural_filename": filename, "fts_literal": fts, "ordinary_body": ordinary}


CASES = (
    ("retrieval_miss", retrieval_miss),
    ("original_fragments", original_fragments),
    ("operational_precedence", operational_precedence),
    ("no_semantic_retry", no_semantic_retry),
    ("evidence_eligibility", evidence_eligibility),
    ("documentation_gap", documentation_gap),
    ("authoritative_conflict", authoritative_conflict),
    ("projection_states", projection_states),
    ("exact_document_recovery", exact_document_recovery),
    ("literal_anchor_context", literal_anchor_context),
    ("original_discovery_attribution", original_discovery_attribution),
    ("closed_literal_context", closed_literal_context),
)


def _import_evidence() -> list[dict[str, str]]:
    rows = []
    for name in TARGET_MODULES:
        path = Path(importlib.import_module(name).__file__).resolve()
        if not path.is_relative_to(ROOT):
            raise RuntimeError(f"recovery gate imported a foreign module: {name}: {path}")
        rows.append({"module": name, "path": path.relative_to(ROOT).as_posix(),
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--case", choices=[name for name, _ in CASES])
    args = parser.parse_args(argv)
    report: dict[str, Any] = {"schema_version": REPORT_SCHEMA, "modules": _import_evidence(),
        "source_sha256": hashlib.sha256(TREASURE_SOURCE.encode()).hexdigest(),
        "question_sha256": hashlib.sha256(TREASURE.encode()).hexdigest(), "cases": []}
    for name, run in CASES:
        if args.case and name != args.case:
            continue
        row: dict[str, Any] = {"id": name}
        try:
            measurements = run()
        except ContractFailure as error:
            row.update(outcome="failure", guard=str(error.args[0]), detail=repr(error.args[1:]))
            try:
                diagnostic = _failure_diagnostics(name, error.args[1])
                print("RECOVERY_FAILURE " + json.dumps(diagnostic, ensure_ascii=False, sort_keys=True))
            except Exception as diagnostic_error:
                print("RECOVERY_FAILURE " + json.dumps({"case": name, "diagnostic_error": type(diagnostic_error).__name__}))
        except Exception as error:
            # AssertionError from production/setup is an error, never an oracle
            # kill. Only _require raises the dedicated ContractFailure above.
            row.update(outcome="error", error_type=type(error).__name__, message=str(error))
            traceback.print_exc()
        else:
            row.update(outcome="passed")
            if measurements:
                row["measurements"] = measurements
        report["cases"].append(row)
        print(f"{name}: {row['outcome']}" + (f" ({row['guard']})" if row.get("guard") else ""))
    report["counts"] = {outcome: sum(row["outcome"] == outcome for row in report["cases"])
                        for outcome in ("passed", "failure", "error")}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    failed = report["counts"]["failure"] or report["counts"]["error"]
    print(f"recovery contract gate: {'FAIL' if failed else 'PASS'} ({report['counts']})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
