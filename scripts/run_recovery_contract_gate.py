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
from eval.evidence_quality_v2.runtime import index_project, isolated_service
from eval.project_context_quality.capture_public_context import capture_public_call

REPORT_SCHEMA = "recovery-contract-v2"
TARGET_MODULES = (
    "docmancer.docs.application.recovery",
    "docmancer.docs.application.proofability",
    "docmancer.docs.interfaces.mcp.recovery_projection",
    "docmancer.docs.application._project_docs_service_part03",
    "docmancer.docs.application.source_reference_evidence",
    "docmancer.docs.application.reference_query_tagging",
    "docmancer.docs.application._docs_context_projection_core",
    "docmancer.docs.domain.project_doc_ranking",
    "docmancer.docs.domain.literal_context_admission",
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
        store = service.project_docs._agent_instance().store
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
