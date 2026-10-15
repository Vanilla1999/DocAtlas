"""Native controls for ordinary partial body context, owned by recovery case 12.

Two P14 records stay byte-identical. Independent prose and counterfactuals test
the new lexical/source boundary; none grants original coverage or answer/edit
authority. Direct replays below are negative controls, never native positives.
"""
from __future__ import annotations

from contextlib import ExitStack
from contextvars import copy_context
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from docmancer.docs.application._docs_context_projection_core import project_docs_context
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.application import reference_query_tagging
from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project


_P14 = (
    ("alias_order_drafts", "How are order drafts stored before upload?", "packages/orders/README.md",
     "OrdersDraftStore stores draft orders as JSON records keyed by order id before upload.",
     "before upload", "before upload"),
    ("alias_project_retry_rule", "What is the project-wide rule for network retries?", "ARCHITECTURE.md",
     "ProjectRetryPolicy governs network submission retries and allows at most two retry attempts with bounded exponential backoff.",
     "network retries", "network submission retries"),
)
_QUESTION = "How does the archive retain pressure packets during calibration?"
_BODY = "The recorder preserves pressure telemetry packets inside a sealed envelope."
_FORMATTED = "λ Measurements preserve **pressure** telemetry\npackets inside a sealed envelope."
_PATH = "docs/telemetry.md"


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_ordinary_body_controls(require, observed_public_call):
    """Exercise the real finite service, then isolate replay and scope faults."""
    protocol = json.loads((Path(__file__).parents[0] / "paraphrase_protocol.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in protocol["cases"]}
    for case_id, question, path, body, _, _ in _P14:
        row = by_id[case_id]
        require((row["question"], row["candidate_source"], row["candidate_text"]) == (question, path, body)
                and row["require_discovery"] is True and row["require_support"] is False,
                "recovery_ordinary_frozen_p14_inputs", {"case": case_id})

    positives, negatives, preparations, boundary_checks = [], [], [], []
    native_reads, dispatched_queries, projection_replays = [], [], []
    read_checks = 0
    with tempfile.TemporaryDirectory(prefix="docatlas-ordinary-context-") as temporary:
        root = Path(temporary)
        project = root / "project"
        service = config = policy = None
        current_path = current_body = ""
        observed = []
        with ExitStack() as fixture:
            def install(path, body):
                nonlocal service, config, policy, current_path, current_body, project
                if service is None or path != current_path:
                    fixture.close()
                    identifier = str(len(preparations))
                    project = root / ("project-" + identifier)
                    service, config = fixture.enter_context(isolated_service(root / ("state-" + identifier)))
                    policy = service.member_storage_policy
                current_path, current_body = path, body
                write_project(project, {path: body})
                outcome = index_project(service, config, project)
                require(outcome["indexed_paths"] == [path]
                        and not outcome["excluded_or_failed_paths"] and not outcome["unexpected_paths"],
                        "recovery_ordinary_exact_fixture_member", outcome)
                preparations.append({"path": path, "source_sha256": _digest(body), "generation": outcome["generation_id"]})

            def state():
                return {
                    "generation": policy.generation(),
                    "storage": {item.relative_to(policy.db_path.parent).as_posix():
                                hashlib.sha256(item.read_bytes()).hexdigest()
                                for item in sorted(policy.db_path.parent.rglob("*")) if item.is_file()},
                    "project": {item.relative_to(project).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
                                for item in sorted(project.rglob("*")) if item.is_file()},
                }

            real_prepare = SourceReferenceContext.prepare
            def observe_prepare(context, chunks, *args, **kwargs):
                result = real_prepare(context, chunks, *args, **kwargs)
                query = args[0] if args else kwargs.get("query_text")
                for chunk in result:
                    reference = (chunk.metadata or {}).get("_reference_evidence")
                    if isinstance(reference, dict):
                        observed.append({
                            "query": query, "complete": context.complete,
                            "window_sha256": _digest(chunk.text),
                            "source": deepcopy(reference["source"]),
                            "span": [reference["char_start"], reference["char_end"]],
                        })
                return result

            def native_call(operation, question):
                nonlocal read_checks
                before = state()
                observed.clear()
                first_dispatch = len(dispatched_queries)
                actual_dispatch = RetrievalDispatcher.run
                def observe_dispatch(dispatcher, query, *args, **kwargs):
                    result = actual_dispatch(dispatcher, query, *args, **kwargs)
                    dispatched_queries.append({
                        "native_read_index": read_checks, "query_sha256": _digest(query),
                        "same_raw_original": query == question, "returned_chunks": len(result.chunks),
                    })
                    return result
                with patch.object(SourceReferenceContext, "prepare", observe_prepare), \
                     patch.object(RetrievalDispatcher, "run", observe_dispatch):
                    capture = operation()
                require(state() == before, "recovery_ordinary_read_only", capture)
                native_reads.append({
                    "question_sha256": _digest(question), "path": current_path,
                    "source_sha256": _digest(current_body),
                    "dispatched_queries": len(dispatched_queries) - first_dispatch,
                })
                read_checks += 1
                return capture

            def read(question, *, lookup_queries=None):
                request = {"question": question, "project_path": str(project), "scope": "project"}
                if lookup_queries is not None:
                    request["lookup_queries"] = lookup_queries
                return native_call(lambda: observed_public_call(service, request), question)

            def no_authority(payload):
                require(all(payload.get(key) is not True for key in (
                    "answer_supported", "answer_available", "edit_ready",
                )), "recovery_ordinary_no_authority", payload)

            def no_context(payload, label):
                require(payload.get("error") is None and payload.get("kind") == "docs_context"
                        and not payload.get("context_available") and not payload.get("sources"),
                        label, {"public_payload": payload})
                no_authority(payload)

            def check_context(capture, question, query_phrase, source_phrase, label):
                payload = capture["public_payload"]
                require(payload.get("status") == "ok" and payload.get("kind") == "docs_context"
                        and payload.get("context_available") is True
                        and any(row.get("path_or_url") == current_path and row.get("snippet") == current_body
                                for row in payload.get("sources", [])),
                        "recovery_ordinary_full_source_fact", {"case": label, "capture": capture})
                no_authority(payload)
                require(payload.get("covered_query_ids") == []
                        and payload.get("missing_query_ids") == ["query-original"]
                        and payload.get("query_coverage") == "partial",
                        "recovery_ordinary_no_original_credit", payload)
                require(len(capture["projection_attempts"]) == 1, "recovery_ordinary_single_projection", capture)
                attempt = capture["projection_attempts"][0]
                require(not validate_model_visible_projection(attempt["projected_payload"], snapshot=attempt["snapshot"]),
                        "recovery_ordinary_snapshot_validator", attempt)
                require(any(row["query"] == question and row["complete"] is True
                            and row["source"]["canonical_path"] == current_path
                            and row["source"]["content_sha256"] == _digest(current_body)
                            and row["window_sha256"] == _digest(current_body) for row in observed),
                        "recovery_ordinary_actual_original_body_discovery", observed)
                identity = "local:" + _digest(str(project.resolve()))
                for visible in payload["sources"]:
                    bound = attempt["snapshot"][visible["evidence_id"]]
                    source = bound["source"]
                    reference = source["_reference_evidence"]
                    require(visible["project_identity"] == identity and visible["scope"] == "project"
                            and visible["path_or_url"] == current_path and visible["snippet"] == current_body
                            and source["content"] == source["display_text"] == current_body
                            and reference["raw_document"] == reference["text"] == current_body
                            and reference["char_start"] == 0 and reference["char_end"] == len(current_body)
                            and reference["source"]["content_sha256"] == _digest(current_body)
                            and reference["source"]["scope"]["snapshot_id"] == policy.generation(),
                            "recovery_ordinary_current_whole_window", source)
                    trace = source["retrieval_query_matches"]["query-original"]
                    require(trace.get("query_text") == question and trace.get("query_origin") == "original"
                            and trace.get("qualified") is False
                            and trace.get("qualification_reason") == "insufficient_visible_match"
                            and source["_reference_root_plan"]["question"] == question
                            and source["_reference_root_plan"]["references"] == [],
                            "recovery_ordinary_original_stays_unverified", source)
                    require({key: value for key, value in visible.items() if key != "source_uri"}
                            == {key: value for key, value in bound["projected_source"].items() if key != "source_uri"},
                            "recovery_ordinary_visible_snapshot_binding", visible)
                admissions = (attempt["after_projection"].get("retrieval_diagnostics") or {}).get(
                    "docs_context_projection", {}).get("literal_context_admissions") or []
                expected = {
                    "kind": "ordinary_body_clause_context_v1", "text": query_phrase,
                    "query_char_start": question.index(query_phrase),
                    "query_char_end": question.index(query_phrase) + len(query_phrase),
                    "char_start": current_body.index(source_phrase),
                    "char_end": current_body.index(source_phrase) + len(source_phrase),
                }
                witnesses = [witness for admission in admissions for witness in admission.get("body_witnesses", [])]
                require(admissions and all(admission.get("reason") == "ordinary_body_clause_context_v1"
                                          and admission.get("coverage_credit") is False for admission in admissions)
                        and witnesses and all(all(witness.get(key) == value for key, value in expected.items())
                                              for witness in witnesses),
                        "recovery_ordinary_raw_phrase_spans", {"expected": expected, "admissions": admissions})
                for witness in witnesses:
                    require(len(witness["content_tokens"]) == 2
                            and witness["clause_char_start"] <= witness["char_start"] < witness["char_end"]
                            <= witness["clause_char_end"]
                            and len(witness["native_discovery_binding_sha256"]) == 64,
                            "recovery_ordinary_exact_token_pairs", witness)
                    for token in witness["content_tokens"]:
                        require(question[token["query_char_start"]:token["query_char_end"]].casefold()
                                == current_body[token["char_start"]:token["char_end"]].casefold(),
                                "recovery_ordinary_exact_token_pairs", witness)
                require("native_discovery_binding_sha256" not in json.dumps(payload, ensure_ascii=False),
                        "recovery_ordinary_receipt_not_a_wire_grant", payload)
                positives.append({"case": label, "question_sha256": _digest(question),
                                  "path": current_path, "source_sha256": _digest(current_body),
                                  "query_span": [expected["query_char_start"], expected["query_char_end"]],
                                  "source_span": [expected["char_start"], expected["char_end"]]})
                return deepcopy(attempt["before_projection"])

            for case_id, question, path, body, query_phrase, source_phrase in _P14:
                install(path, body)
                check_context(read(question), question, query_phrase, source_phrase, case_id)
            install(_PATH, _FORMATTED)
            formatted_question = " \t" + _QUESTION + "\r\n"
            check_context(read(formatted_question), formatted_question, "pressure packets",
                          "pressure** telemetry\npackets", "raw_whitespace_emphasis_unicode")
            install(_PATH, _BODY)
            healthy = check_context(read(_QUESTION), _QUESTION, "pressure packets",
                                    "pressure telemetry packets", "independent_prose")

            # All following public faults start from the healthy current member.
            # No incoming true flag or copied snapshot substitutes for discovery.
            with patch.object(reference_query_tagging, "record_original_body_discovery", lambda **kwargs: None):
                capture = read(_QUESTION)
            require(observed, "recovery_ordinary_no_receipt_still_acquired", observed)
            no_context(capture["public_payload"], "recovery_ordinary_native_receipt_required")
            boundary_checks.append("withheld_receipt")

            actual_app = service.materialize().unified_context
            foreign_calls = []
            def wrong_root_native(question, **kwargs):
                foreign_calls.append(kwargs.get("project_path"))
                kwargs["project_path"] = str(project)
                return actual_app.get_docs_context(question, **kwargs)
            wrong_root_service = SimpleNamespace(unified_context=SimpleNamespace(get_docs_context=wrong_root_native))
            wrong_root_request = {"question": _QUESTION, "project_path": str(root / "foreign-project"), "scope": "project"}
            wrong_root = native_call(lambda: context_tools.handle_context_tool(
                "get_docs_context", wrong_root_request, wrong_root_service), _QUESTION)
            require(foreign_calls == [wrong_root_request["project_path"]]
                    and observed and any(row["query"] == _QUESTION for row in observed),
                    "recovery_ordinary_foreign_root_has_actual_native_read", observed)
            no_context(wrong_root, "recovery_ordinary_request_owner_binding")
            boundary_checks.append("foreign_request_root_with_real_native_read")

            original_record = reference_query_tagging._record_current_body_discovery
            def incomplete_owner(context, chunk, query):
                with patch.object(context, "complete", False):
                    original_record(context, chunk, query)
            with patch.object(reference_query_tagging, "_record_current_body_discovery", incomplete_owner):
                capture = read(_QUESTION)
            require(observed and all(row["complete"] is True for row in observed),
                    "recovery_ordinary_incomplete_control_has_native_source", observed)
            no_context(capture["public_payload"], "recovery_ordinary_finite_receipt_owner")
            boundary_checks.append("incomplete_owning_context")

            real_projection = context_tools.project_docs_context
            def source_faults_projection(*args, **kwargs):
                # Eight independent operand faults share this one actual read.
                # Each starts from the untouched captured current candidate.
                for fault in ("owner", "generation", "member", "scope", "document_identity", "body", "window", "stale"):
                    retrieval = deepcopy(kwargs["retrieval"])
                    require(bool(retrieval.get("context_pack")), "recovery_ordinary_fault_has_healthy_candidates", fault)
                    for candidate in retrieval["context_pack"]:
                        reference = candidate["_reference_evidence"]
                        if fault == "owner":
                            retrieval["project_identity"] = candidate["project_identity"] = "foreign-project"
                            reference["source"]["scope"]["project_id"] = "foreign-project"
                        elif fault == "generation":
                            candidate["generation_id"] = reference["source"]["scope"]["snapshot_id"] = "foreign-generation"
                        elif fault == "member":
                            candidate["_source_catalog_hash"] = reference["member_binding"]["catalog_entry_hash"] = "sha256:" + "0" * 64
                        elif fault == "scope":
                            candidate.update(doc_scope="module", module_path="foreign-module")
                            reference["member_binding"].update(doc_scope="module", module_path="foreign-module")
                        elif fault == "document_identity":
                            reference["source"]["document_id"] = "foreign-document"
                        elif fault == "body":
                            changed = current_body.replace("sealed", "closed")
                            candidate.update(content=changed, display_text=changed,
                                             _source_snapshot_sha256="sha256:" + _digest(changed),
                                             source_content_hash=_digest(changed))
                            reference.update(raw_document=changed, text=changed,
                                             project_doc_content_hash="sha256:" + _digest(changed))
                            reference["source"]["content_sha256"] = _digest(changed)
                        elif fault == "window":
                            reference.update(char_start=1, text=current_body[1:])
                            candidate.update(char_start=1, content=current_body[1:], display_text=current_body[1:])
                        elif fault == "stale":
                            candidate.update(freshness="stale", index_freshness="unsynchronized")
                        for plan in (candidate["_reference_root_plan"], *(candidate.get("_reference_plans") or {}).values()):
                            plan["scope"] = deepcopy(reference["source"]["scope"])
                        candidate.update(qualified=True, context_eligible=True, original_discovery=True,
                                         literal_context_admission={"coverage_credit": False})
                    rejected, snapshot = real_projection(*args, **{**kwargs, "retrieval": retrieval})
                    no_context(rejected, "recovery_ordinary_current_receipt_binding")
                    require(not snapshot, "recovery_ordinary_current_receipt_binding", fault)
                    projection_replays.append("active_source_operand_" + fault)
                    boundary_checks.append(fault)
                return real_projection(*args, **kwargs)

            with patch.object(context_tools, "project_docs_context", source_faults_projection):
                capture = read(_QUESTION)
            check_context(capture, _QUESTION, "pressure packets", "pressure telemetry packets",
                          "current_operand_baseline_preserved")

            # A saved result is intentionally not a fresh native read.
            replay_calls = []
            def replay_result(question, **kwargs):
                replay_calls.append(question)
                return deepcopy(healthy)
            replay_service = SimpleNamespace(unified_context=SimpleNamespace(get_docs_context=replay_result))
            request = {"question": _QUESTION, "project_path": str(project), "scope": "project"}
            replayed = context_tools.handle_context_tool("get_docs_context", request, replay_service)
            require(replay_calls == [_QUESTION], "recovery_ordinary_replay_one_handler_call", replay_calls)
            no_context(replayed, "recovery_ordinary_public_replay_has_no_receipt")
            boundary_checks.append("public_result_replay")

            entered, nested, copied = False, [], []
            def nested_projection(*args, **kwargs):
                nonlocal entered
                if not entered:
                    entered = True
                    copied.append(copy_context())
                    try:
                        nested.append(context_tools.handle_context_tool("get_docs_context", request, replay_service))
                    finally:
                        entered = False
                return real_projection(*args, **kwargs)
            with patch.object(context_tools, "project_docs_context", nested_projection):
                capture = read(_QUESTION)
            require(len(nested) == len(copied) == 1 and len(capture["projection_attempts"]) == 2
                    and replay_calls == [_QUESTION, _QUESTION],
                    "recovery_ordinary_nested_call_exercised", capture)
            nested_attempt, outer_attempt = capture["projection_attempts"]
            no_context(nested[0], "recovery_ordinary_nested_scope_isolation")
            no_context(nested_attempt["projected_payload"], "recovery_ordinary_nested_scope_isolation")
            require(not nested_attempt["snapshot"], "recovery_ordinary_nested_scope_isolation", nested_attempt)
            # The observer also captures the nested negative before the outer
            # native projection. Ordinary reads still require exactly one.
            outer_capture = {**capture, "projection_attempts": [outer_attempt]}
            check_context(outer_capture, _QUESTION, "pressure packets", "pressure telemetry packets",
                          "outer_scope_restored")
            result, snapshot = copied[0].run(project_docs_context, retrieval=deepcopy(healthy))
            projection_replays.append("finished_copied_context")
            no_context(result, "recovery_ordinary_finished_context_is_closed")
            require(not snapshot, "recovery_ordinary_finished_context_is_closed", snapshot)
            boundary_checks.extend(("nested_scope_isolation", "copied_context_closed"))

            failed_contexts = []
            class ProjectionFixtureFailure(RuntimeError):
                pass
            def failing_projection(*args, **kwargs):
                failed_contexts.append(copy_context())
                raise ProjectionFixtureFailure("ordinary body scope cleanup control")
            with patch.object(context_tools, "project_docs_context", failing_projection):
                failed = read(_QUESTION)
            require(len(failed_contexts) == 1 and failed["public_payload"].get("error") is not None,
                    "recovery_ordinary_exception_control_exercised", failed)
            result, snapshot = failed_contexts[0].run(project_docs_context, retrieval=deepcopy(healthy))
            projection_replays.append("exception_copied_context")
            no_context(result, "recovery_ordinary_exception_scope_closed")
            require(not snapshot, "recovery_ordinary_exception_scope_closed", snapshot)
            boundary_checks.append("exception_scope_cleanup")

            real_dispatch = RetrievalDispatcher.run
            withheld = []
            def lookup_only(dispatcher, query, *args, **kwargs):
                result = real_dispatch(dispatcher, query, *args, **kwargs)
                if query == _QUESTION:
                    withheld.append(len(result.chunks))
                    return replace(result, chunks=[])
                return replace(result, chunks=[chunk.model_copy(update={"metadata": {
                    **(chunk.metadata or {}), "original_discovery": True,
                    "literal_context_admission": {"coverage_credit": False}, "context_eligible": True,
                }}) for chunk in result.chunks])
            with patch.object(RetrievalDispatcher, "run", lookup_only):
                capture = read(_QUESTION, lookup_queries=["pressure packets"])
            payload = capture["public_payload"]
            require(withheld and any(withheld), "recovery_ordinary_withheld_actual_original", withheld)
            require(payload.get("context_available") is True
                    and payload.get("covered_query_ids") == ["query-lookup-1"]
                    and "query-original" in payload.get("missing_query_ids", []),
                    "recovery_ordinary_lookup_cannot_mint_original", capture)
            no_authority(payload)
            for attempt in capture["projection_attempts"]:
                admissions = (attempt["after_projection"].get("retrieval_diagnostics") or {}).get(
                    "docs_context_projection", {}).get("literal_context_admissions") or []
                require(not any(row.get("reason") == "ordinary_body_clause_context_v1" for row in admissions),
                        "recovery_ordinary_lookup_cannot_mint_original", admissions)
            boundary_checks.append("lookup_only_no_original_receipt")

            for label, body in (
                ("one_content_term", "The recorder preserves pressure inside a sealed envelope."),
                ("split_sentence_wrong_subject", "The recorder observes pressure. The courier seals packets inside an envelope."),
                ("split_coordinator", "The recorder observes pressure but the courier seals packets."),
                ("reverse_order", "The recorder preserves packets under controlled pressure."),
                ("prefix_only", "The recorder preserves pressureless packetshapes inside a sealed envelope."),
                ("heading", "# pressure packets\n\nThe orchard contains several apple trees."),
                ("link", "[pressure packets](https://example.invalid/reference)\n\nThe orchard contains several apple trees."),
                ("table_header", "| pressure | packets |\n| --- | --- |\n| apples | pears |"),
                ("repeated_label", "pressure packets pressure packets"),
                ("function_words", "How does the recorder work with the samples in the envelope?"),
            ):
                install(_PATH, body)
                capture = read(_QUESTION)
                no_context(capture["public_payload"], "recovery_ordinary_body_clause_safety")
                negatives.append(label)
            install(_PATH, _BODY)
            for label, question in (
                ("content_word_gap", "How does the archive retain pressure lunar packets during calibration?"),
                ("strict_literal", "What lunar policy does TelemetryStore use for pressure packets?"),
                ("strict_quote", 'What does "lunar" require for pressure packets during calibration?'),
                ("numeric_literal", "How does the archive retain pressure 7 packets during calibration?"),
                ("comparison_operator", "What does pressure != packets mean in detailed retention settings?"),
                ("standalone_minus", "How does the archive retain pressure - packets during calibration?"),
            ):
                capture = read(question)
                no_context(capture["public_payload"], "recovery_ordinary_original_span_boundary")
                negatives.append(label)
            # Useful partial context says nothing about the unmatched modifier.
            install(_PATH, _P14[1][3])
            check_context(read("Which lunar policy controls network retries?"),
                          "Which lunar policy controls network retries?", "network retries",
                          "network submission retries", "ordinary_modifier_remains_uncovered")

    return {"positive_reads": positives, "negative_controls": negatives,
            "boundary_controls": boundary_checks, "read_only_checks": read_checks,
            "native_public_reads": native_reads, "native_query_dispatches": dispatched_queries,
            "work_counts": {
                "native_public_reads": len(native_reads), "native_query_dispatches": len(dispatched_queries),
                "saved_result_handler_replays": len(replay_calls),
                "active_source_operand_replays": sum(name.startswith("active_source_operand_") for name in projection_replays),
                "copied_context_projection_replays": sum(not name.startswith("active_source_operand_") for name in projection_replays),
                "explicit_fixture_preparations": len(preparations),
            }, "projection_replays": projection_replays, "preparations": preparations}
