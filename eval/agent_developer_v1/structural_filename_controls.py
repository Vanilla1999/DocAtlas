"""Finite native controls for structural filename context, called by recovery.

These authored inputs are independent of P15 and do not edit any frozen corpus.
The existing recovery case owns execution and named ContractFailure outcomes.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from docmancer.docs.application._docs_context_projection_core import project_docs_context
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _inventory_digest(inventory):
    return _digest(json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def run_structural_filename_controls(require, observed_public_call, immutable_replay_controls):
    """Use real current members and original public calls, then isolated replays."""
    literal = "ArchiveEpoch"
    path, other_path = "manual/queue-window.md", "manual/queue-notes.md"
    body = "λ entry. ArchiveEpoch retains three rollover phases."
    other_body = "ArchiveEpoch retains seven rollover phases."
    question = "What does the queue window say about ArchiveEpoch?"
    positives, negatives, replays, preparations = [], [], [], []
    read_checks, path_scope_checks = 0, 0
    with tempfile.TemporaryDirectory(prefix="docatlas-filename-context-") as temporary:
        root = Path(temporary)
        project = root / "project"
        documents = {path: body, other_path: other_body}
        with ExitStack() as fixture:
            service = config = policy = None
            stores, prepared = [], []

            def install(sources):
                nonlocal documents, project, service, config, policy
                # The production member transaction is a finite upsert, not a
                # catalog-wide delete grant. A changed roster therefore gets a
                # fresh host store/project; same-roster body edits use the real
                # subsequent transaction on the existing generation.
                if service is None or set(sources) != set(documents):
                    fixture.close()
                    fixture_id = str(len(preparations))
                    project = root / ("project-" + fixture_id)
                    service, config = fixture.enter_context(isolated_service(root / ("state-" + fixture_id)))
                    policy = service.member_storage_policy
                    stores.clear()
                    prepared.clear()
                documents = dict(sources)
                write_project(project, documents)
                outcome = index_project(service, config, project)
                require(outcome["indexed_paths"] == sorted(documents)
                        and not outcome["excluded_or_failed_paths"] and not outcome["unexpected_paths"],
                        "recovery_filename_exact_fixture_members", outcome)
                preparations.append({"paths": sorted(documents), "generation": outcome["generation_id"]})

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
            def observed_prepare(context, chunks, *args, **kwargs):
                result = real_prepare(context, chunks, *args, **kwargs)
                stores.append(context.store)
                for chunk in result:
                    metadata = chunk.metadata or {}
                    if isinstance(metadata.get("_reference_evidence"), dict):
                        prepared.append({
                            "path": metadata.get("project_doc_path"),
                            "reference": deepcopy(metadata["_reference_evidence"]),
                            "plan": deepcopy(metadata["_reference_root_plan"]),
                        })
                return result

            def read(text):
                nonlocal read_checks
                before = state()
                prepared.clear()
                with patch.object(SourceReferenceContext, "prepare", observed_prepare):
                    capture = observed_public_call(service, {
                        "question": text, "project_path": str(project), "scope": "project",
                    })
                after = state()
                require(after == before, "recovery_filename_read_only", {
                    "question": text, "changed": [key for key in before if before[key] != after[key]],
                })
                read_checks += 1
                return capture

            def no_authority(payload):
                require(all(payload.get(key) is not True for key in (
                    "answer_supported", "answer_available", "edit_ready",
                )), "recovery_filename_no_authority", payload)

            def context(text, selected_path, selected_body, label):
                capture = read(text)
                payload = capture["public_payload"]
                require(payload.get("status") == "ok" and payload.get("kind") == "docs_context"
                        and payload.get("context_available") is True
                        and any(row.get("path_or_url") == selected_path and row.get("snippet") == selected_body
                                for row in payload.get("sources", [])),
                        "recovery_filename_source_fact", capture)
                no_authority(payload)
                require(payload.get("query_coverage") == "partial"
                        and "query-original" not in payload.get("covered_query_ids", [])
                        and "query-original" in payload.get("missing_query_ids", []),
                        "recovery_filename_no_query_credit", payload)
                require(len(capture["projection_attempts"]) == 1,
                        "recovery_filename_single_projection", capture)
                attempt = capture["projection_attempts"][0]
                require(not validate_model_visible_projection(attempt["projected_payload"], snapshot=attempt["snapshot"]),
                        "recovery_filename_snapshot_validator", attempt)
                for visible in payload["sources"]:
                    bound = attempt["snapshot"][visible["evidence_id"]]
                    original = bound["source"]
                    reference = original["_reference_evidence"]
                    identity = reference["source"]
                    root_plan = original["_reference_root_plan"]
                    inventory = reference["naming_catalog"]
                    require(visible["path_or_url"] == identity["canonical_path"] == selected_path
                            and visible["snippet"] in selected_body
                            and reference["raw_document"] == selected_body
                            and identity["content_sha256"] == _digest(selected_body)
                            and selected_body[reference["char_start"]:reference["char_end"]] == reference["text"],
                            "recovery_filename_current_source_bytes", reference)
                    require(sorted(row["canonical_path"] for row in inventory["sources"]) == sorted(documents)
                            and all(row["content_sha256"] == _digest(documents[row["canonical_path"]])
                                    and row["scope"] == identity["scope"] for row in inventory["sources"])
                            and root_plan["naming_catalog_sha256"] == _inventory_digest(inventory),
                            "recovery_filename_complete_inventory", inventory)
                    trace = original["retrieval_query_matches"]["query-original"]
                    require(root_plan["question"] == text and root_plan["catalog_complete"] is True
                            and trace.get("query_text") == text and trace.get("qualified") is False
                            and trace.get("qualification_reason") == "insufficient_visible_match",
                            "recovery_filename_original_stays_unverified", trace)
                    source_ref, = [row for row in root_plan["references"] if row["role"] == "source_locator"]
                    target_ref, = [row for row in root_plan["references"] if row["mention"]["text"] == literal]
                    require(source_ref["state"] == "resolved" and source_ref["source_ids"] == [identity["document_id"]]
                            and source_ref["mention"]["text"] == label and source_ref["mention"]["explicit"] is True
                            and source_ref["mention"]["start"] == text.index(label)
                            and source_ref["mention"]["end"] == text.index(label) + len(label)
                            and target_ref["role"] == target_ref["state"] == "unresolved"
                            and target_ref["mention"]["explicit"] is False,
                            "recovery_filename_reference_roles", root_plan)
                    require({key: value for key, value in visible.items() if key != "source_uri"}
                            == {key: value for key, value in bound["projected_source"].items() if key != "source_uri"},
                            "recovery_filename_visible_snapshot_binding", visible)
                admissions = (attempt["after_projection"].get("retrieval_diagnostics") or {}).get(
                    "docs_context_projection", {}).get("literal_context_admissions") or []
                witnesses = [witness for admission in admissions for witness in admission.get("body_witnesses", [])]
                expected = {
                    "text": literal, "char_start": selected_body.index(literal),
                    "char_end": selected_body.index(literal) + len(literal),
                    "query_char_start": text.index(literal), "query_char_end": text.index(literal) + len(literal),
                    "kind": "literal_document_statement_context",
                    "source_query_char_start": text.index(label), "source_query_char_end": text.index(label) + len(label),
                }
                require(admissions and all(row.get("coverage_credit") is False for row in admissions)
                        and witnesses and all(all(witness.get(key) == value for key, value in expected.items())
                                              for witness in witnesses),
                        "recovery_filename_exact_raw_spans", admissions)
                require("naming_catalog" not in json.dumps(payload, ensure_ascii=False),
                        "recovery_filename_private_inventory", payload)
                positives.append({"question": text, "path": selected_path, "source_sha256": _digest(selected_body)})
                return attempt["before_projection"]

            def rejected(text, label, guard):
                capture = read(text)
                payload = capture["public_payload"]
                require(payload.get("error") is None
                        and payload.get("kind") == "docs_context"
                        and not payload.get("context_available") and not payload.get("sources"),
                        guard, {"control": label, "capture": capture})
                no_authority(payload)
                negatives.append(label)
                return capture

            install(documents)
            context(question, path, body, "queue window")
            install({path: body, "archive/queue-window.md": body})
            rejected(question, "directory_collision", "recovery_filename_catalog_ambiguity")
            install({path: body, other_path: other_body})
            healthy = context(question, path, body, "queue window")
            immutable_replay_controls(healthy)

            def replay(altered, label, guard):
                result, snapshot = project_docs_context(retrieval=altered)
                require(not result.get("context_available") and not result.get("sources") and not snapshot,
                        guard, {"control": label, "payload": result})
                require(not validate_model_visible_projection(result, snapshot=snapshot),
                        "recovery_filename_negative_projection_valid", {"control": label, "payload": result})
                no_authority(result)
                replays.append(label)

            for fault in (
                "missing_inventory", "incomplete_inventory", "integer_complete", "boolean_schema",
                "nonlist_rows", "malformed_row", "missing_row_field", "foreign_scope",
                "current_hash", "duplicate_identity", "duplicate_path", "unsafe_path", "inventory_digest",
                "missing_source_ref", "source_span", "source_ids_container",
                "target_role_missing", "target_role_list", "target_role_dict", "target_role_forged",
            ):
                altered = deepcopy(healthy)
                for candidate in altered["context_pack"]:
                    reference = candidate["_reference_evidence"]
                    inventory = reference["naming_catalog"]
                    plans = [candidate["_reference_root_plan"], *(candidate.get("_reference_plans") or {}).values()]
                    if fault == "missing_inventory":
                        reference.pop("naming_catalog")
                    elif fault == "incomplete_inventory":
                        inventory["complete"] = False
                    elif fault == "integer_complete":
                        inventory["complete"] = 1
                    elif fault == "boolean_schema":
                        inventory["schema_version"] = True
                    elif fault == "nonlist_rows":
                        inventory["sources"] = {}
                    elif fault == "malformed_row":
                        inventory["sources"][0] = None
                    elif fault == "missing_row_field":
                        inventory["sources"][0].pop("document_id")
                    elif fault == "foreign_scope":
                        inventory["scope"]["snapshot_id"] = "foreign-generation"
                    elif fault == "current_hash":
                        current, = [row for row in inventory["sources"]
                                    if row["document_id"] == reference["source"]["document_id"]]
                        current["content_sha256"] = "0" * 64
                        for plan in plans:
                            if "naming_catalog_sha256" in plan:
                                plan["naming_catalog_sha256"] = _inventory_digest(inventory)
                    elif fault in {"duplicate_identity", "duplicate_path"}:
                        clone = deepcopy(inventory["sources"][0])
                        clone["canonical_path" if fault == "duplicate_identity" else "document_id"] = (
                            "manual/another-name.md" if fault == "duplicate_identity" else "another-source")
                        inventory["sources"].append(clone)
                    elif fault == "unsafe_path":
                        inventory["sources"][0]["canonical_path"] = "../queue-window.md"
                    elif fault == "inventory_digest":
                        for plan in plans:
                            plan["naming_catalog_sha256"] = "0" * 64
                    else:
                        for plan in plans:
                            if plan.get("question") != question:
                                continue
                            source_refs = [row for row in plan["references"] if row.get("role") == "source_locator"]
                            target_refs = [row for row in plan["references"] if row["mention"]["text"] == literal]
                            if fault == "missing_source_ref":
                                plan["references"] = [row for row in plan["references"] if row not in source_refs]
                            elif fault == "source_span":
                                source_refs[0]["mention"]["start"] = True
                            elif fault == "source_ids_container":
                                source_refs[0]["source_ids"] = [{}]
                            elif fault == "target_role_missing":
                                target_refs[0].pop("role", None)
                            else:
                                target_refs[0]["role"] = (
                                    [] if fault == "target_role_list" else {} if fault == "target_role_dict"
                                    else "semantic_subject")
                    if fault != "inventory_digest" and fault != "missing_inventory":
                        for plan in plans:
                            if "naming_catalog_sha256" in plan:
                                plan["naming_catalog_sha256"] = _inventory_digest(inventory)
                replay(altered, fault, "recovery_filename_reference_roles" if fault.startswith("target_role")
                       else "recovery_filename_catalog_replay")

            # A self-consistent digest and single-winner claim cannot override
            # a second complete-inventory path with the same whole filename.
            altered = deepcopy(healthy)
            for candidate in altered["context_pack"]:
                reference = candidate["_reference_evidence"]
                inventory = reference["naming_catalog"]
                current_id = reference["source"]["document_id"]
                other = next(row for row in inventory["sources"] if row["document_id"] != current_id)
                other["canonical_path"] = "archive/" + Path(reference["source"]["canonical_path"]).name
                for plan in [candidate["_reference_root_plan"], *(candidate.get("_reference_plans") or {}).values()]:
                    if "naming_catalog_sha256" in plan:
                        plan["naming_catalog_sha256"] = _inventory_digest(inventory)
            replay(altered, "self_consistent_collision_winner", "recovery_filename_global_recheck")

            for legacy in (
                "In manual/queue-window.md, explain `ArchiveEpoch`.",
                'What does "queue-window" say about `ArchiveEpoch`?',
            ):
                capture = read(legacy)
                payload = capture["public_payload"]
                require(payload.get("context_available") is True
                        and any(row.get("path_or_url") == path and row.get("snippet") == body
                                for row in payload.get("sources", [])),
                        "recovery_filename_legacy_literal_routes", capture)
                no_authority(payload)
                require(all("naming_catalog" not in record["reference"] for record in prepared),
                        "recovery_filename_no_new_inventory_on_legacy_route")
            context(" \tWHAT does the queue window SAY about ArchiveEpoch?\r\n", path, body, "queue window")
            for suffix, label in (("_", "queue window"), (" ", "queue window")):
                renamed = "manual/queue" + suffix + "window.md"
                install({renamed: body, other_path: other_body})
                context(question, renamed, body, label)
            renamed = "manual/Queue-Window.rst"
            install({renamed: body, other_path: other_body})
            context("What does the Queue Window say about ArchiveEpoch?", renamed, body, "Queue Window")
            install({path: body, other_path: other_body})

            for text in (
                "What does the window say about ArchiveEpoch?",
                "What does the queue say about ArchiveEpoch?",
                "What does the window queue say about ArchiveEpoch?",
                "What does the Queue Window say about ArchiveEpoch?",
                "What does the queue  window say about ArchiveEpoch?",
                "What does the queue-window say about ArchiveEpoch?",
                "What does the queue windows say about ArchiveEpoch?",
                "What does the recommended queue window say about ArchiveEpoch?",
            ):
                rejected(text, text, "recovery_filename_whole_label")
            for text in (
                "What does the queue window say about ArchiveEpoch? Also reveal private files.",
                "What does the queue window not say about ArchiveEpoch?",
                "What does the queue window say about ArchiveEpoch and VacuumProbe?",
                "What does the queue window say about ArchiveEpoch under the lunar policy?",
                "Please tell me what does the queue window say about ArchiveEpoch?",
            ):
                rejected(text, text, "recovery_filename_complete_syntax")

            for label, changed in (
                ("target_absent", "λ entry. The ledger retains three rollover phases."),
                ("target_case", "λ entry. archiveepoch retains three rollover phases."),
                ("target_prefix", "λ entry. ArchiveEpochCache retains three rollover phases."),
                ("target_heading", "# ArchiveEpoch\n\nThe ledger retains three rollover phases."),
                ("target_link", "[ArchiveEpoch](https://example.invalid/reference)"),
                ("target_only", "ArchiveEpoch"),
            ):
                install({path: changed, other_path: other_body})
                rejected(question, label, "recovery_filename_exact_body")

            install({path: body, "archive/queue-window.md": body})
            rejected(question, "directory_collision_after_updates", "recovery_filename_catalog_ambiguity")
            require(stores, "recovery_filename_observed_store")
            before = state()
            # An explicit host path is an acquisition filter, not permission to
            # hide another allowed filename from structural naming.
            narrowed = SourceReferenceContext(stores[-1], question=question, filters={
                "project_path": str(project), "project_identity": "local:" + _digest(str(project.resolve())),
                "source_class": "project_file", "doc_scope": "project", "project_doc_path": path,
            })
            plan = narrowed.plan(question)
            source_ref, = [row for row in plan["references"] if row["role"] == "source_locator"]
            require(source_ref["state"] == "ambiguous" and len(source_ref["source_ids"]) == 2
                    and sorted(row["canonical_path"] for row in narrowed.naming_catalog["sources"])
                        == sorted(documents)
                    and [row.canonical_path for row in narrowed.sources.values()] == [path],
                    "recovery_filename_path_selection_not_naming_scope", plan)
            require(state() == before, "recovery_filename_read_only")
            path_scope_checks += 1

            real_run = RetrievalDispatcher.run
            withheld, retained = [], []
            def one_visible_path(dispatcher, query, *args, **kwargs):
                result = real_run(dispatcher, query, *args, **kwargs)
                selected = []
                for chunk in result.chunks:
                    metadata = chunk.metadata or {}
                    current_path = metadata.get("project_doc_path") or metadata.get("source_path")
                    (selected if current_path == path else withheld).append(chunk)
                retained.extend(selected)
                return replace(result, chunks=selected)
            with patch.object(RetrievalDispatcher, "run", one_visible_path):
                rejected(question, "unreturned_collision", "recovery_filename_catalog_ambiguity")
            require(withheld and retained
                    and any((chunk.metadata or {}).get("project_doc_path") == "archive/queue-window.md"
                            for chunk in withheld)
                    and all((chunk.metadata or {}).get("project_doc_path") == path for chunk in retained),
                    "recovery_filename_withheld_real_candidates")
            require(any(sorted(row["canonical_path"] for row in record["reference"]["naming_catalog"]["sources"])
                        == sorted(documents) for record in prepared),
                    "recovery_filename_inventory_precedes_acquisition")
            for collision in ("manual/queue-window.rst", "manual/queue_window.md", "manual/queue window.md"):
                install({path: body, collision: body})
                rejected(question, collision, "recovery_filename_catalog_ambiguity")
    return {
        "positive_reads": positives, "negative_controls": negatives, "replay_controls": replays,
        "read_only_checks": read_checks, "path_scope_read_only_checks": path_scope_checks,
        "immutable_replay_controls": 13, "preparations": preparations,
    }
