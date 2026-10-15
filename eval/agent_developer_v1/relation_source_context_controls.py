"""Four native frozen-input controls for current source-context semantics.

The original relation compiler is not called by this helper.  A lexical quote
can be context without proving the requested relation or authorizing an answer.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from functools import wraps
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from docmancer.docs.application import reference_query_tagging
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.project_context_quality.capture_public_context import capture_public_call


_ARCHIVE_SHA256 = "34620c11c83e58dad640b4ee56711830de9ab3ba18ca0c64e88e6f26ffea2809"
_INPUT_SHA256 = "391e69055fb006e82ac1109a0d1ce1e89c1cbce02651bc37cd4cb756a224477c"
_PRIVATE_FIELDS = ("raw_document", "_admission_demands", "need_witness_spans", "_reference_evidence")


def _digest(value):
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _require(condition, guard, detail=None):
    if not condition:
        if detail is not None:
            print("RELATION_SOURCE_CONTEXT_FAILURE " + json.dumps(
                {"guard": guard, "detail": detail}, ensure_ascii=False, sort_keys=True))
        raise AssertionError(guard)


def _frozen_inputs():
    history = Path(__file__).resolve().parents[1] / "task_level" / "contract_history"
    archive = (history / "admission_relation_compiler_inputs.py.txt").read_bytes()
    data = json.loads((history / "admission_relation_live_source_inputs.json").read_text(encoding="utf-8"))
    rows = data["frozen_inputs"]
    matrix = [[row[key] for key in ("id", "family", "question", "body", "current_outcome")] for row in rows]
    encoded = json.dumps(matrix, ensure_ascii=False, separators=(",", ":"))
    _require(_digest(archive) == _ARCHIVE_SHA256 and _digest(encoded) == _INPUT_SHA256,
             "critical_relation_frozen_source_inputs")
    return rows


def _no_answer_authority(payload, *, strict):
    flags = ("answer_supported", "answer_available", "edit_ready")
    _require(all(payload.get(key) is False if strict else payload.get(key) is not True for key in flags)
             and not any(payload.get(key) for key in ("answer", "answer_evidence_ids", "edit_plan", "mutation")),
             "critical_relation_public_no_answer_authority")


def run_relation_source_context_controls(workspace: Path):
    """Append four real public reads to the existing, unchanged privacy control."""
    rows = _frozen_inputs()
    receipts = []
    for row in rows:
        case = workspace / row["id"]
        project = (case / "project").resolve()
        question, body = row["question"], row["body"]
        _require(_digest(question) == row["question_sha256"]
                 and _digest(body) == row["body_sha256"]
                 and len(body.encode("utf-8")) == row["body_utf8_bytes"],
                 "critical_relation_frozen_source_inputs")
        write_project(project, {"Guide.md": body})
        request = {"project_path": str(project), "question": question, "scope": "project"}
        with isolated_service(case / "state") as (service, config):
            prepared = index_project(service, config, project)
            _require(prepared["expected_paths"] == prepared["indexed_paths"] == ["Guide.md"]
                     and not prepared["excluded_or_failed_paths"] and not prepared["unexpected_paths"],
                     "critical_relation_native_finite_preparation")
            policy, generation = service.member_storage_policy, prepared["generation_id"]
            identity = "local:" + _digest(str(project))
            with closing(policy.connect()) as connection:
                children = [dict(item) for item in connection.execute(
                    "SELECT c.*, p.source_content_hash AS committed_source_content_hash "
                    "FROM retrieval_children c JOIN retrieval_parents p "
                    "ON p.generation_id = c.generation_id AND p.logical_id = c.parent_logical_id "
                    "WHERE c.generation_id = ?", (generation,))]
            _require(len(children) == 1, "critical_relation_native_whole_child", {"case": row["id"]})
            child = children[0]
            _require(child["source_path"] == "Guide.md" and child["display_text"] == body
                     and child["committed_source_content_hash"] == child["display_content_hash"] == _digest(body)
                     and child["project_identity"] == identity and child["source_class"] == "project_file"
                     and child["doc_scope"] == "project" and child["generation_id"] == generation
                     and child["char_start"] == child["byte_start"] == 0
                     and child["char_end"] == len(body) and child["byte_end"] == len(body.encode("utf-8"))
                     and child["line_start"] == 1 and child["line_end"] == len(body.splitlines()),
                     "critical_relation_native_committed_bytes", {"case": row["id"]})

            def state():
                return {
                    "storage": {str(path.relative_to(policy.app_home)):
                                _digest(path.read_bytes()) if path.is_file() else None
                                for path in policy.app_home.rglob("*")},
                    "generation": policy.generation(),
                    "catalog": _digest((project / "docatlas.project-docs.yaml").read_bytes()),
                    "document": _digest((project / "Guide.md").read_bytes()),
                }

            before = state()
            actual = service.materialize(read_only_startup=True)
            get_member, dispatch = actual.get_project_docs, RetrievalDispatcher.run
            qualify = reference_query_tagging.qualify_evidence
            member_calls, dispatch_calls, qualifications = [], [], []
            member_active = False

            @wraps(get_member)
            def observe_member(*args, **kwargs):
                nonlocal member_active
                member_active = True
                member_calls.append((deepcopy(args), deepcopy(kwargs)))
                try:
                    return get_member(*args, **kwargs)
                finally:
                    member_active = False

            @wraps(dispatch)
            def observe_dispatch(owner, query, *args, **kwargs):
                result = dispatch(owner, query, *args, **kwargs)
                dispatch_calls.append({"question": query, "args": deepcopy(args), "kwargs": deepcopy(kwargs),
                                       "chunks": deepcopy(result.chunks)})
                return result

            @wraps(qualify)
            def observe_qualification(probe, **kwargs):
                result = qualify(probe, **kwargs)
                if member_active:
                    qualifications.append(deepcopy({"probe": probe, "arguments": kwargs, "result": result}))
                return result

            with (patch.object(actual, "get_project_docs", observe_member),
                  patch.object(RetrievalDispatcher, "run", observe_dispatch),
                  patch.object(reference_query_tagging, "qualify_evidence", observe_qualification)):
                capture = capture_public_call(actual, request)
            public = capture["public_payload"]
            attempts = capture["projection_attempts"]
            # Observe actual producer output before a later validator can hide an
            # unauthorized answer by turning the final public packet into an error.
            for attempt in attempts:
                _no_answer_authority(attempt["projected_payload"],
                                     strict=row["current_outcome"] == "context_only")
            state_equal = state() == before
            _require(state_equal and capture["request"] == request and len(member_calls) == 1,
                     "critical_relation_native_single_read_state", {"case": row["id"]})
            _require([item["question"] for item in dispatch_calls] == [question, question]
                     and all(not item["args"] and item["kwargs"].get("limit") == 20
                             and item["kwargs"].get("mode") == "lexical"
                             and item["kwargs"].get("expand") == "none" for item in dispatch_calls),
                     "critical_relation_no_generated_acquisition", {"case": row["id"]})
            for item in dispatch_calls:
                filters = item["kwargs"]["filters"]
                _require(filters["project_identity"] == identity and filters["project_path"] == str(project)
                         and filters["source_class"] == "project_file" and filters["doc_scope"] == "project"
                         and len(item["chunks"]) == 1,
                         "critical_relation_native_acquired_source", {"case": row["id"]})
                acquired = item["chunks"][0]
                _require(acquired.text == body and acquired.source == str(project / "Guide.md")
                         and acquired.metadata["stable_chunk_id"] == child["stable_chunk_id"]
                         and acquired.metadata["generation_id"] == generation,
                         "critical_relation_native_acquired_source", {"case": row["id"]})

            # This nonempty receipt is mandatory even for a correctly empty
            # public result.  An empty fixture cannot kill the metadata fault.
            _require(bool(qualifications), "critical_relation_native_qualification_observed",
                     {"case": row["id"], "public_status": public.get("status")})
            for observed in qualifications:
                args, probe, result = observed["arguments"], observed["probe"], observed["result"]
                candidate = args["candidate"]
                reference = candidate.get("_reference_evidence") or {}
                source_binding = reference.get("source") or {}
                contract = args["authoritative_query"]
                _require(args["query_id"] == "query-original" and probe["query_text"] == question
                         and probe["query_origin"] == "original" and probe["relation"] == "direct"
                         and contract["query_id"] == "query-original" and contract["text"] == question
                         and contract["origin"] == "original" and contract["relation"] == "direct"
                         and not contract.get("public_parent_query_id")
                         and args["evidence_text"] == body
                         and args["expected_project_identity"] == candidate["project_identity"] == identity
                         and candidate["stable_chunk_id"] == child["stable_chunk_id"]
                         and candidate["generation_id"] == generation
                         and candidate["source_class"] == "project_file" and candidate["doc_scope"] == "project"
                         and reference.get("text") == reference.get("raw_document") == body
                         and reference.get("char_start") == 0 and reference.get("char_end") == len(body)
                         and source_binding.get("document_id") == child["source_identity"]
                         and source_binding.get("canonical_path") == "Guide.md"
                         and source_binding.get("content_sha256") == _digest(body)
                         and source_binding.get("scope") == {
                             "project_id": identity, "version": "", "snapshot_id": generation}
                         and reference.get("project_doc_content_hash") == "sha256:" + _digest(body)
                         and reference.get("member_binding") == {
                             "doc_scope": "project", "module_path": "",
                             "catalog_entry_hash": prepared["documents"][0]["catalog_entry_hash"]},
                         "critical_relation_native_qualification_binding", {"case": row["id"]})
                _require(not any(result.trace.get(key) for key in (
                    "need_local_witness", "admission_route", "matched_need_ids", "need_witness_spans",
                    "public_parent_query_id", "derived_from_query_id", "derived_from_query_ids",
                )), "critical_relation_no_generated_semantic_credit", {"case": row["id"]})

            if row["current_outcome"] == "metadata_only_rejected":
                _require(all(item["result"].qualified is False
                             and item["result"].reason == "metadata_only_evidence"
                             and item["result"].covered_query_ids == ()
                             and item["result"].coverage_kind is None for item in qualifications),
                         "critical_relation_metadata_cannot_supply_body")
                _require(not public.get("sources") and public.get("context_available") is False
                         and public.get("status") in {"blocked", "insufficient_evidence"}
                         and not public.get("covered_query_ids"),
                         "critical_relation_metadata_public_veto",
                         {"status": public.get("status"), "source_count": len(public.get("sources") or [])})
                _no_answer_authority(public, strict=False)
            else:
                _require(all(item["result"].qualified is True and item["result"].reason == "visible_fields"
                             and item["result"].covered_query_ids == ("query-original",)
                             and item["result"].coverage_kind == "direct"
                             and item["result"].trace.get("context_only") is True for item in qualifications),
                         "critical_relation_original_body_context", {"case": row["id"]})
                _require(public.get("kind") == "docs_context" and public.get("status") == "ok"
                         and public.get("context_available") is True and len(public.get("sources") or []) == 1
                         and public.get("answer_policy") == "cite_only"
                         and public.get("support_status") == "retrieval_only"
                         and public.get("coverage_policy") == "retrieval_attribution_only",
                         "critical_relation_public_context", {"case": row["id"], "status": public.get("status")})
                _no_answer_authority(public, strict=True)
                _require(bool(attempts), "critical_relation_native_projection_snapshot")
                source = public["sources"][0]
                entry = attempts[-1]["snapshot"].get(source["evidence_id"]) or {}
                original = entry.get("source") or {}
                projected_source = entry.get("projected_source") or {}
                _require({key: value for key, value in projected_source.items() if key != "source_uri"}
                         == {key: value for key, value in source.items() if key != "source_uri"}
                         and source["path_or_url"] == "Guide.md" and source["snippet"] == body
                         and source["project_identity"] == identity and source["scope"] == "project"
                         and source["line_start"] == child["line_start"] and source["line_end"] == child["line_end"]
                         and original.get("content") == original.get("display_text") == body
                         and original.get("source_content_hash") == _digest(body)
                         and original.get("_source_snapshot_sha256") == "sha256:" + _digest(body)
                         and original.get("_source_catalog_hash") == prepared["documents"][0]["catalog_entry_hash"]
                         and original.get("project_identity") == identity and original.get("doc_scope") == "project"
                         and original.get("source_class") == "project_doc" and original.get("generation_id") == generation
                         and all(original.get(field) == child[field] for field in (
                             "stable_chunk_id", "parent_logical_id", "source_identity", "display_content_hash",
                             "char_start", "char_end", "byte_start", "byte_end", "line_start", "line_end"))
                         and original.get("instruction_trust") == "untrusted_data"
                         and original.get("content_boundary", {}).get("executable_policy") is False,
                         "critical_relation_full_current_source_quote", {"case": row["id"]})
                if "source_uri" in source:
                    uri = source["source_uri"]
                    _require(isinstance(uri, str) and bool(uri)
                             and uri == projected_source.get("source_uri") == entry.get("source_uri")
                             and actual.source_reader.has_reference(uri),
                             "critical_relation_public_source_uri_binding")
                if row["id"] == "callable_wrong_role":
                    _require(rows[0]["body"] not in source["snippet"],
                             "critical_relation_wrong_role_does_not_prove_target")

            for attempt in attempts:
                errors = validate_model_visible_projection(attempt["projected_payload"], snapshot=attempt["snapshot"])
                _require(not errors, "critical_relation_native_projection_valid", errors)
            _require(all(field not in json.dumps(public, ensure_ascii=False) for field in _PRIVATE_FIELDS),
                     "critical_relation_no_private_public_fields")
            receipts.append({
                "case": row["id"], "question_sha256": _digest(question), "body_sha256": _digest(body),
                "generation": generation, "stable_chunk_id": child["stable_chunk_id"],
                "char_span": [child["char_start"], child["char_end"]],
                "line_span": [child["line_start"], child["line_end"]],
                "member_calls": len(member_calls), "dispatch_calls": len(dispatch_calls),
                "native_qualification_count": len(qualifications),
                "qualification_outcomes": sorted({item["result"].reason for item in qualifications}),
                "qualified": sorted({item["result"].qualified for item in qualifications}),
                "public_status": public.get("status"), "public_source_count": len(public.get("sources") or []),
                "projection_attempts": len(attempts), "state_equal": state_equal,
            })
    print("RELATION_SOURCE_CONTEXT_RECEIPT " + json.dumps(
        {"input_sha256": _INPUT_SHA256, "native_public_reads": len(receipts), "cases": receipts},
        ensure_ascii=False, sort_keys=True))
