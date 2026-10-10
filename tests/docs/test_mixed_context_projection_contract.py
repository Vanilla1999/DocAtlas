"""One native mixed-delivery contract; internal fault iterations are not pytest cases."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from functools import wraps
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from docmancer.core.product_identity import ensure_owned_home
from docmancer.core.member_read_store import MemberReadStore
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application import mixed_context_projection, _docs_context_projection_core
from docmancer.docs.application.model_visible_projection import (
    _refresh_estimate, project_docs_answer, validate_model_visible_projection,
)
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.agent_developer_v1.finite_http_fixture import (
    FrozenHttpInput, index_state, prepare_external_sources, read_stored_children,
)
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project


def test_mixed_context_preserves_current_same_call_source_bindings(tmp_path):
    question = "Explain LedgerCursor and RemoteDelayRule."
    version = "2.7.1"
    library_id = "python:clear-pulse-fixture@2.7.1:reference"
    library_url = "https://docs.clearpulse.test/2.7.1/reference.txt"
    robots_url = "https://docs.clearpulse.test/robots.txt"
    library_body = "RemoteDelayRule pauses for four milliseconds before a renewal."
    documents = {
        "manual/project-ledger.md": "λ checkpoint. LedgerCursor retains two unfinished batches.",
        "packages/alpha/ledger.md": "μ alpha. LedgerCursor retains three sealed batches.",
        "packages/beta/ledger.md": "ν beta. LedgerCursor retains seven pending batches.",
    }
    foreign_documents = {
        "manual/project-ledger.md": "ξ remote. LedgerCursor retains nine unfinished ledgers.",
    }
    module_paths = {
        "packages/alpha/ledger.md": "packages/alpha",
        "packages/beta/ledger.md": "packages/beta",
    }
    source_fields = {"evidence_id", "path_or_url", "section", "snippet",
                     "version_binding", "content_sha256"}
    receipts, replay_labels = [], []

    def require(condition, guard, detail=None):
        if not condition:
            if detail is not None:
                print("MIXED_CONTRACT_FAILURE " + json.dumps(
                    {"guard": guard, "detail": detail}, ensure_ascii=False, sort_keys=True, default=str))
            raise AssertionError(guard)

    def digest(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def root_identity(root):
        return "local:" + digest(str(root))

    def prepare(project, bodies, service, config, modules=None):
        write_project(project, bodies)
        entries = []
        for path in sorted(bodies):
            entry = {
                "path": path, "role": "other", "scope": "module" if path in (modules or {}) else "project",
                "description": "Independent mixed context fixture.",
                "authority": "source_of_truth", "status": "active", "impact": "track",
            }
            if path in (modules or {}):
                entry["module_path"] = modules[path]
            entries.append(entry)
        (project / "docatlas.project-docs.yaml").write_text(json.dumps({
            "schema_version": 1, "code_files": [], "roots": [], "documents": entries,
        }, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        prepared = index_project(service, config, project)
        require(prepared["expected_paths"] == prepared["indexed_paths"] == sorted(bodies)
                and not prepared["excluded_or_failed_paths"] and not prepared["unexpected_paths"],
                "critical_mixed_finite_preparation", prepared)
        return prepared

    def native(arguments, service, project, bodies, external):
        before = index_state(service, project, bodies, external)
        actual = service.materialize(read_only_startup=True) if hasattr(service, "_cold") else service
        app = actual.unified_context
        retrieve, project_answer = app.get_docs_context, context_tools.project_docs_answer
        retain, validate = mixed_context_projection.retain_mixed_project_context, context_tools.validate_model_visible_projection
        raw_results, requests, projector_inputs, composition_inputs, snapshots = [], [], [], [], []

        @wraps(retrieve)
        def observe_retrieval(*args, **kwargs):
            result = retrieve(*args, **kwargs)
            requests.append({"args": args, "kwargs": deepcopy(kwargs)})
            raw_results.append(asdict(result))
            return result

        @wraps(project_answer)
        def observe_projector(*args, **kwargs):
            projector_inputs.append({
                "question": kwargs["question"], "retrieval": deepcopy(kwargs["retrieval"]),
                "canonical_selection": kwargs.get("canonical_selection"),
            })
            return project_answer(*args, **kwargs)

        @wraps(retain)
        def observe_composition(**kwargs):
            composition_inputs.append(deepcopy(kwargs))
            return retain(**kwargs)

        @wraps(validate)
        def observe_validation(payload, *, snapshot, **kwargs):
            snapshots.append(deepcopy(snapshot))
            return validate(payload, snapshot=snapshot, **kwargs)

        with (patch.object(app, "get_docs_context", observe_retrieval),
              patch.object(context_tools, "project_docs_answer", observe_projector),
              patch.object(mixed_context_projection, "retain_mixed_project_context", observe_composition),
              patch.object(context_tools, "validate_model_visible_projection", observe_validation)):
            payload = call_docs_tool_payload("get_docs_context", arguments, actual)
        require(index_state(actual, project, bodies, external) == before,
                "critical_mixed_read_only", {"request": arguments})
        require(len(raw_results) == len(requests) == len(snapshots) == 1
                and requests[0]["args"] == (question,)
                and requests[0]["kwargs"].get("lookup_queries") == ()
                and all(requests[0]["kwargs"].get(key) is False for key in (
                    "allow_network", "prepare_project_docs", "force_refresh", "prefetch_auto",
                )), "critical_mixed_single_native_call", {
                    "request": arguments, "retrievals": len(raw_results), "validations": len(snapshots),
                    "status": payload.get("status"), "error": payload.get("error"),
                })
        require(not validate_model_visible_projection(payload, snapshot=snapshots[0]),
                "critical_mixed_public_snapshot")
        receipt = {
            "payload": payload, "snapshot": snapshots[0], "raw": raw_results[0],
            "projector_inputs": projector_inputs, "composition_inputs": composition_inputs,
        }
        receipts.append(receipt)
        return receipt

    def no_authority(payload):
        require(all(payload.get(key) is False for key in (
            "answer_supported", "answer_available", "edit_ready",
        )) and not payload.get("selected_evidence_ids") and not payload.get("satisfied_requirement_ids")
                and not payload.get("answer_evidence_ids") and not payload.get("answer"),
                "critical_mixed_no_authority")
        if payload.get("kind") == "docs_answer" and payload.get("status") == "ok":
            require(payload.get("retrieval_only") is True and payload.get("answer_policy") == "cite_only"
                    and payload.get("mandatory_coverage") == payload.get("evidence_coverage") == 0.0,
                    "critical_mixed_no_query_credit")

    def plain_packet(payload):
        return {key: value for key, value in payload.items() if key != "estimated_tokens"}

    def lineage_values(source, field, aliases=()):
        metadata = source.get("metadata", {})
        require(isinstance(metadata, dict), "critical_mixed_lineage_shape")
        return [carrier[key] for carrier in (source, metadata)
                for key in (field, *aliases) if key in carrier]

    def check_source(visible, bound, child, expected_body, expected_project=None, expected_module=None):
        require(set(visible) == source_fields and visible == bound["projected_source"],
                "critical_mixed_same_call_snapshot")
        original = bound["source"]
        material = {
            "path": original.get("path") or original.get("source") or original.get("url") or original.get("source_url"),
            "section": original.get("heading_path") or original.get("title"),
            "content": original.get("content") or original.get("display_text"),
            "snippet": original.get("snippet") or original.get("code"),
            "version": original.get("version_binding") or original.get("version") or original.get("requested_version"),
        }
        require(visible["content_sha256"] == digest(json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
            "critical_mixed_raw_hash")
        require(child["display_text"] == expected_body
                and child["display_content_hash"] == child["source_content_hash"] == digest(expected_body)
                and (child["char_start"], child["char_end"]) == (0, len(expected_body))
                and (child["byte_start"], child["byte_end"]) == (0, len(expected_body.encode("utf-8")))
                and (child["line_start"], child["line_end"]) == (1, 1),
                "critical_mixed_committed_full_bytes")
        aliases = {"display_content_hash": ("content_hash",)}
        for key in ("stable_chunk_id", "parent_logical_id", "generation_id", "source_identity",
                    "source_content_hash", "display_text", "display_content_hash"):
            values = lineage_values(original, key, aliases.get(key, ()))
            require(values and all(type(value) is type(child[key]) and value == child[key] for value in values),
                    "critical_mixed_committed_child", {"field": key, "path": child["path"]})
        for dimension in ("char", "byte", "line"):
            expected = [child[dimension + "_start"], child[dimension + "_end"]]
            pairs = []
            for carrier in (original, original.get("metadata", {})):
                start, end = dimension + "_start", dimension + "_end"
                if start in carrier or end in carrier:
                    require(start in carrier and end in carrier, "critical_mixed_lineage_shape")
                    pairs.append([carrier[start], carrier[end]])
                if dimension + "_span" in carrier:
                    pairs.append(carrier[dimension + "_span"])
            require(pairs and all(isinstance(pair, (list, tuple)) and len(pair) == 2
                    and all(type(value) is int for value in pair) and list(pair) == expected for pair in pairs),
                    "critical_mixed_raw_spans", {"path": child["path"], "dimension": dimension})
        if expected_project is not None:
            require(original["source_class"] == "project_doc" and child["source_class"] == "project_file"
                    and original["project_identity"] == child["project_identity"] == root_identity(expected_project)
                    and original["doc_scope"] == child["doc_scope"] == ("module" if expected_module else "project")
                    and original["authority"] == child["authority"] == "source_of_truth"
                    and original.get("module_path") == expected_module,
                    "critical_mixed_project_owner")
            trace = original["retrieval_query_matches"]["query-original"]
            require(trace["query_text"] == question and trace["qualified"] is False
                    and trace["qualification_reason"] == "insufficient_visible_match",
                    "critical_mixed_no_query_credit")
        else:
            require(child["library_id"] == library_id and child["resolved_version"] == version,
                    "critical_mixed_exact_library")
            for field, expected, synonyms in (
                ("source_class", "library_doc", ()), ("doc_scope", "library", ()),
                ("library_id", library_id, ()), ("canonical_id", library_id, ()),
                ("resolved_version", version, ("version",)),
            ):
                values = lineage_values(original, field, synonyms)
                require(values and all(value == expected for value in values), "critical_mixed_exact_library")
            values = lineage_values(original, "docs_snapshot_exact")
            require(values and all(type(value) in (bool, int) and value == 1 for value in values)
                    and type(child["docs_snapshot_exact"]) is int and child["docs_snapshot_exact"] == 1,
                    "critical_mixed_exact_library")

    def healthy(receipt, project, path, body, child_rows, library_child, *, module=None):
        raw, payload, snapshot = receipt["raw"], receipt["payload"], receipt["snapshot"]
        contract = raw.get("project_context_contract") or {}
        expected_scope = {
            "schema_version": 1, "query": question, "project_path": str(project),
            "project_identity": root_identity(project), "requested_scope": "module" if module else "project",
            "requested_module": None, "requested_module_path": module,
            "doc_scope": "module" if module else "project", "module_path": module, "evidence_path": None,
        }
        require(contract.get("read_scope") == expected_scope,
                "critical_mixed_scope_producer", {"expected": expected_scope, "actual": contract.get("read_scope")})
        sources = payload.get("sources") or []
        require(payload.get("status") == "ok" and payload.get("kind") == "docs_answer"
                and payload.get("context_available") is True and len(sources) == 2
                and {frozenset(lineage_values(snapshot[row["evidence_id"]]["source"], "source_class"))
                     for row in sources} == {frozenset({"project_doc"}), frozenset({"library_doc"})},
                "critical_mixed_both_lanes", {
                    "status": payload.get("status"), "paths": [row.get("path_or_url") for row in sources],
                    "error": payload.get("error"),
                })
        require({row["path_or_url"]: row["snippet"] for row in sources} == {
            path: body, library_url: library_body,
        }, "critical_mixed_full_fact")
        no_authority(payload)
        require(len(receipt["projector_inputs"]) == len(receipt["composition_inputs"]) == 1,
                "critical_mixed_authoritative_hook")
        incoming = receipt["composition_inputs"][0]
        require(len(incoming["payload"]["sources"]) == 1
                and incoming["payload"]["sources"][0]["path_or_url"] == library_url
                and incoming["payload"]["sources"][0]["snippet"] == library_body,
                "critical_mixed_observed_library_packet")
        for row in sources:
            bound = snapshot[row["evidence_id"]]
            children = [child for child in (child_rows if row["path_or_url"] == path else [library_child])
                        if child["path"] == row["path_or_url"]]
            require(len(children) == 1, "critical_mixed_unique_child")
            check_source(row, bound, children[0], body if row["path_or_url"] == path else library_body,
                         project if row["path_or_url"] == path else None, module)
        return receipt["projector_inputs"][0], incoming

    def deny_io(*_args, **_kwargs):
        raise AssertionError("critical_mixed_projection_cannot_retrieve")

    def replay(input_packet, incoming, label, alter, *, blocked=False, guard="critical_mixed_project_guard"):
        arguments = deepcopy(input_packet)
        alter(arguments["retrieval"])
        preserved = deepcopy(arguments["retrieval"])
        with (patch.object(RetrievalDispatcher, "run", deny_io),
              patch.object(SQLiteStore, "_connect", deny_io),
              patch.object(MemberReadStore, "_connect", deny_io),
              patch.object(_docs_context_projection_core, "attach_source_continuation_locators", deny_io)):
            result, snapshot = project_docs_answer(**arguments)
        require(arguments["retrieval"] == preserved, "critical_mixed_replay_input_immutable")
        require(not validate_model_visible_projection(result, snapshot=snapshot),
                "critical_mixed_replay_snapshot")
        no_authority(result)
        if blocked:
            require(not result.get("sources") and not snapshot, guard, {"control": label})
        else:
            require(plain_packet(result) == plain_packet(incoming["payload"])
                    and snapshot == incoming["snapshot"], guard, {"control": label})
        replay_labels.append(label)

    # Capture a real current foreign source before opening the independent main host.
    foreign = (tmp_path / "foreign-project").resolve()
    with isolated_service(tmp_path / "foreign-state") as (service, config):
        prepare(foreign, foreign_documents, service, config)
        foreign_read = native({"question": question, "project_path": str(foreign), "scope": "project"},
                              service, foreign, foreign_documents, {"records": []})
        require(any(row.get("snippet") == foreign_documents["manual/project-ledger.md"]
                    for row in foreign_read["payload"].get("sources", [])),
                "critical_mixed_foreign_control_healthy")
        foreign_items = [deepcopy(item) for item in foreign_read["raw"]["context_pack"]
                         if item.get("source_class") == "project_doc"]
        require(foreign_items and all(item["project_identity"] == root_identity(foreign)
                                     for item in foreign_items), "critical_mixed_foreign_control_healthy")

    project = (tmp_path / "project").resolve()
    with isolated_service(tmp_path / "state") as (service, config):
        ensure_owned_home(service.member_storage_policy.app_home)
        prepared = prepare(project, documents, service, config, module_paths)
        actual = service.materialize()
        children = read_stored_children(actual.member_storage_policy.db_path)
        target = {
            "id": "mixed-contract-exact-library",
            "identity": {"kind": "package", "ecosystem": "python", "name": "clear-pulse-fixture"},
            "version": {"policy": "exact", "requested": version},
            "source": {"type": "reference", "url": library_url, "format": "direct-text",
                       "authority": "official_project", "version_binding": "exact"},
            "scope": {"coverage": "bounded", "seed_urls": [library_url, robots_url],
                      "allowed_domains": ["docs.clearpulse.test"],
                      "path_prefixes": ["/2.7.1/reference.txt", "/robots.txt"], "max_pages": 2},
        }
        network = FrozenHttpInput({library_url: library_body})
        with network.active():
            external = prepare_external_sources(actual, project, [target], tmp_path)
            require(len(external["records"]) == 1, "critical_mixed_exact_preparation")
            record = external["records"][0]
            require(record["library_id"] == library_id and record["name"] == "clear-pulse-fixture"
                    and record["ecosystem"] == "python" and record["version"] == record["resolved_version"] == version
                    and record["docs_url"] == library_url and record["docs_snapshot_exact"] is True
                    and {row["path"] for row in record["stored_children"]} == {library_url, robots_url},
                    "critical_mixed_exact_preparation", record)
            library_children = [row for row in record["stored_children"] if row["path"] == library_url]
            require(len(library_children) == 1, "critical_mixed_unique_child")
            network.phase = "read"
            base_request = {"question": question, "project_path": str(project), "scope": "project",
                            "library": library_id, "version": version}
            project_read = native(base_request, actual, project, documents, external)
            project_input, project_incoming = healthy(
                project_read, project, "manual/project-ledger.md", documents["manual/project-ledger.md"],
                children, library_children[0])
            module_reads = {}
            for module in ("packages/alpha", "packages/beta"):
                receipt = native({**base_request, "scope": "module", "module_path": module},
                                 actual, project, documents, external)
                module_reads[module] = healthy(
                    receipt, project, module + "/ledger.md", documents[module + "/ledger.md"],
                    children, library_children[0], module=module)

            def replace_project(raw, replacements):
                raw["context_pack"] = [
                    item for item in raw["context_pack"] if item.get("source_class") != "project_doc"
                ] + deepcopy(replacements)

            def foreign_root(raw):
                replace_project(raw, foreign_items)
                contract = raw["project_context_contract"]
                contract["project_path"] = str(foreign)
                contract["read_scope"].update(project_path=str(foreign), project_identity=root_identity(foreign))

            replay(project_input, project_incoming, "foreign_current_source", foreign_root,
                   guard="critical_mixed_request_root")
            alpha_input, alpha_incoming = module_reads["packages/alpha"]
            beta_input, _ = module_reads["packages/beta"]
            beta_items = [item for item in beta_input["retrieval"]["context_pack"]
                          if item.get("source_class") == "project_doc"]
            require(beta_items and all(item["module_path"] == "packages/beta" for item in beta_items),
                    "critical_mixed_module_control_healthy")
            replay(alpha_input, alpha_incoming, "other_real_module",
                   lambda raw: replace_project(raw, beta_items), guard="critical_mixed_resolved_module")

            def spurious_module(raw):
                replace_project(raw, [item for item in alpha_input["retrieval"]["context_pack"]
                                      if item.get("source_class") == "project_doc"])
                raw["project_context_contract"]["read_scope"].update(
                    doc_scope="module", module_path="packages/alpha")
            replay(project_input, project_incoming, "unrequested_module", spurious_module)

            for label, change in (
                ("missing_contract", lambda raw: raw.pop("project_context_contract")),
                ("missing_scope", lambda raw: raw["project_context_contract"].pop("read_scope")),
                ("boolean_schema", lambda raw: raw["project_context_contract"]["read_scope"].update(schema_version=True)),
                ("changed_scope_query", lambda raw: raw["project_context_contract"]["read_scope"].update(query="Different question.")),
                ("changed_request_scope", lambda raw: raw["_mixed_project_request"].update(scope="all")),
                ("changed_module_request", lambda raw: raw["_mixed_project_request"].update(module_path="packages/beta")),
                ("relative_request_root", lambda raw: (
                    raw["_mixed_project_request"].update(project_path="project"),
                    raw["project_context_contract"].update(request_project_path="project"))),
                ("wrong_evidence_path", lambda raw: raw["project_context_contract"]["read_scope"].update(evidence_path="manual/absent.md")),
                ("project_confirmation", lambda raw: raw["project_context_contract"].update(requires_confirmation=True)),
                ("nested_confirmation", lambda raw: raw["project_context_contract"].update(project_docs_requires_confirmation=True)),
                ("project_delivery", lambda raw: raw["project_context_contract"].update(delivery_decision={"deliverable": False})),
                ("integer_delivery", lambda raw: raw["project_context_contract"].update(delivery_decision={"deliverable": 1})),
                ("missing_conflicts", lambda raw: raw["project_context_contract"].pop("unresolved_conflicts")),
                ("unresolved_conflicts", lambda raw: raw["project_context_contract"].update(unresolved_conflicts=[{"id": "conflict"}])),
                ("stale_project_status", lambda raw: raw["project_context_contract"].update(project_docs_status="stale")),
            ):
                replay(project_input, project_incoming, label, change)

            for fault in ("identity", "catalog", "file_hash", "generation", "stale", "raw_document", "missing_reference"):
                def corrupt(raw, fault=fault):
                    for item in raw["context_pack"]:
                        if item.get("source_class") != "project_doc":
                            continue
                        if fault == "identity":
                            item["project_identity"] = "foreign-project"
                        elif fault == "catalog":
                            item["_source_catalog_hash"] = "sha256:" + "0" * 64
                        elif fault == "file_hash":
                            item["_source_snapshot_sha256"] = "sha256:" + "0" * 64
                        elif fault == "generation":
                            item["generation_id"] = "foreign-generation"
                        elif fault == "stale":
                            item["freshness"] = "stale"
                        elif fault == "raw_document":
                            item["_reference_evidence"]["raw_document"] += "\nUncommitted tail."
                        else:
                            item.pop("_reference_evidence")
                replay(project_input, project_incoming, "source_" + fault, corrupt)

            for label, change in (
                ("global_confirmation", lambda raw: raw.update(requires_confirmation=True)),
                ("global_delivery", lambda raw: raw.update(delivery_decision={"deliverable": False})),
                ("different_exact_library_version", lambda raw: raw.update(
                    docs_exactness="exact", requested_version="2.7.2", resolved_version="2.7.2")),
            ):
                replay(project_input, project_incoming, label, change, blocked=True,
                       guard="critical_mixed_library_veto")

            # Keep the real bound library quote while varying only its class carrier.
            # All cases use the same current producer request and project witness.
            carrier_labels = []
            absent = object()
            for label, top_class, nested_class, malformed_metadata, include_project in (
                ("metadata_only", absent, "library_doc", absent, True),
                ("top_only", "library_doc", absent, absent, True),
                ("both_agree", "library_doc", "library_doc", absent, True),
                ("missing_both", absent, absent, absent, False),
                ("top_none", None, "library_doc", absent, False),
                ("nested_none", "library_doc", None, absent, False),
                ("top_conflict", "project_doc", "library_doc", absent, False),
                ("nested_conflict", "library_doc", "project_doc", absent, False),
                ("boolean_class", True, "library_doc", absent, False),
                ("empty_class", "library_doc", "", absent, False),
                ("metadata_none", "library_doc", absent, None, False),
                ("metadata_false", "library_doc", absent, False, False),
                ("metadata_integer", "library_doc", absent, 1, False),
                ("metadata_list", "library_doc", absent, [], False),
                ("metadata_string", "library_doc", absent, "library_doc", False),
            ):
                carrier = deepcopy(project_incoming)
                library_source_id = carrier["payload"]["sources"][0]["evidence_id"]
                original = carrier["snapshot"][library_source_id]["source"]
                if top_class is absent:
                    original.pop("source_class", None)
                else:
                    original["source_class"] = top_class
                if malformed_metadata is absent:
                    if nested_class is absent:
                        original["metadata"].pop("source_class", None)
                    else:
                        original["metadata"]["source_class"] = nested_class
                else:
                    original["metadata"] = malformed_metadata
                # The observed hook input precedes the projector's final estimate.
                # Mirror the helper's preparation before validating this detached packet.
                _refresh_estimate(carrier["payload"])
                carrier_errors = validate_model_visible_projection(
                    carrier["payload"], snapshot=carrier["snapshot"])
                require(not carrier_errors, "critical_mixed_class_control_healthy",
                        {"control": label, "validation_errors": carrier_errors})
                unchanged = deepcopy(carrier)
                with (patch.object(RetrievalDispatcher, "run", deny_io),
                      patch.object(SQLiteStore, "_connect", deny_io),
                      patch.object(MemberReadStore, "_connect", deny_io),
                      patch.object(_docs_context_projection_core, "attach_source_continuation_locators", deny_io)):
                    result, snapshot = mixed_context_projection.retain_mixed_project_context(**carrier)
                require(carrier == unchanged, "critical_mixed_replay_input_immutable", {"control": label})
                if include_project:
                    expected_snapshot = deepcopy(project_read["snapshot"])
                    expected_snapshot[library_source_id] = deepcopy(carrier["snapshot"][library_source_id])
                    require(plain_packet(result) == plain_packet(project_read["payload"])
                            and snapshot == expected_snapshot,
                            "critical_mixed_library_class_carrier", {"control": label})
                else:
                    require(plain_packet(result) == plain_packet(carrier["payload"])
                            and snapshot == carrier["snapshot"],
                            "critical_mixed_library_class_guard", {"control": label})
                require(not validate_model_visible_projection(result, snapshot=snapshot),
                        "critical_mixed_replay_snapshot", {"control": label})
                no_authority(result)
                carrier_labels.append(label)

            # A collision is between two valid source bindings, not a forged body.
            collision = deepcopy(project_incoming)
            project_id = next(row["evidence_id"] for row in project_read["payload"]["sources"]
                              if row["path_or_url"] == "manual/project-ledger.md")
            visible = collision["payload"]["sources"][0]
            original_id = visible["evidence_id"]
            bound = collision["snapshot"].pop(original_id)
            visible["evidence_id"] = project_id
            bound["evidence_id"] = bound["projected_source"]["evidence_id"] = project_id
            collision["snapshot"][project_id] = bound
            _refresh_estimate(collision["payload"])
            require(not validate_model_visible_projection(collision["payload"], snapshot=collision["snapshot"]),
                    "critical_mixed_collision_control_healthy")
            with patch.object(RetrievalDispatcher, "run", deny_io):
                result, snapshot = mixed_context_projection.retain_mixed_project_context(**collision)
            require(plain_packet(result) == plain_packet(collision["payload"])
                    and snapshot == collision["snapshot"], "critical_mixed_id_collision")
            require(not validate_model_visible_projection(result, snapshot=snapshot),
                    "critical_mixed_collision_snapshot")
            no_authority(result)
            require(all(event["phase"] == "preparation" for event in network.observation()["events"]),
                    "critical_mixed_read_cannot_network")
            require(prepared["generation_id"] == actual.member_storage_policy.generation(),
                    "critical_mixed_read_only")
    require(len(receipts) == 4 and len(replay_labels) == 28 and len(carrier_labels) == 15,
            "critical_mixed_control_roster", {"native_reads": len(receipts), "replays": len(replay_labels),
                                             "class_carrier_controls": len(carrier_labels)})
