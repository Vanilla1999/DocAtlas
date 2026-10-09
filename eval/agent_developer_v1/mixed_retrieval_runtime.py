"""Actual public retrieval of frozen P1.5 facts with explicit source bindings."""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from pathlib import Path
from unittest.mock import patch

from eval.agent_developer_v1.current_retrieval_runtime import candidate_hash_material, project_identity
from eval.agent_developer_v1.finite_http_fixture import (
    FrozenHttpInput, finite_target, index_state, prepare_external_sources, read_stored_children,
)

# These host bindings are a reviewed interpretation of the original explicit
# source roles, not new query text or an inferred planner/answer contract.
REQUEST_BINDINGS = {
    "project_rule_prefers_canonical_policy": {"project": True},
    "project_rule_rejects_advisory_only": {"project": True},
    "implementation_fact_rejects_external_claim": {"project": True},
    "dependency_fact_prefers_dependency_docs": {"library": "python:tenacity@8.2.3:reference", "version": "8.2.3"},
    "dependency_fact_rejects_project_guess_only": {"library": "python:tenacity@8.2.3:reference", "version": "8.2.3"},
    "document_statement_binds_exact_path": {"project": True},
    "two_claims_require_two_allowed_roles": {
        "project": True, "library": "python:tenacity@8.2.3:reference", "version": "8.2.3",
    },
}
INFRASTRUCTURE_MEMBER = "FIXTURE_STATE.md"
INFRASTRUCTURE_TEXT = "This document provisions the isolated fixture store.\n"
LINEAGE_FIELDS = (
    "stable_chunk_id", "parent_logical_id", "generation_id", "source_identity",
    "source_content_hash", "display_content_hash", "display_text",
    "library_id", "canonical_id", "resolved_version", "docs_snapshot_exact",
    "project_identity", "authority", "scope", "doc_scope", "source_class",
    "char_start", "char_end", "byte_start", "byte_end", "line_start", "line_end",
)


def project_documents(case: dict) -> dict[str, str]:
    local = {row["source"]: row["text"] for row in case["candidates"]
             if row["source_class"] == "project_file"}
    # Cold storage requires an explicit member grant. In the advisory-only
    # negative this unrelated infrastructure member grants no question evidence.
    return local or {INFRASTRUCTURE_MEMBER: INFRASTRUCTURE_TEXT}


def expected_request(case: dict, identity: str) -> dict:
    binding = REQUEST_BINDINGS[case["id"]]
    return {
        "question": case["question"], "lookup_queries": [],
        "project_identity": identity if binding.get("project") else None,
        "scope": "project" if binding.get("project") else None,
        "library": binding.get("library"), "version": binding.get("version"),
    }


def capture_mixed_source_read(case: dict, workspace: Path) -> dict:
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from scripts.run_project_docs_self_host_gate import _call_with_snapshot
    from docmancer.docs.interfaces.mcp import context_tools
    from docmancer.core.product_identity import ensure_owned_home

    documents = project_documents(case)
    remote = {row["source"]: row["text"] for row in case["candidates"]
              if row["source_class"] != "project_file"}
    targets = [finite_target(row) for row in case["candidates"] if row["source_class"] != "project_file"]
    project = (workspace / "project").resolve()
    write_project(project, documents)
    identity = project_identity(project)
    binding = REQUEST_BINDINGS[case["id"]]
    arguments = {"question": case["question"]}
    if binding.get("project"):
        arguments.update(project_path=str(project), scope="project")
    for key in ("library", "version"):
        if key in binding:
            arguments[key] = binding[key]
    with isolated_service(workspace / "state") as (service, config):
        if targets:
            # Provision the selected fixture host before member preparation makes
            # it nonempty. The real initializer still rejects unowned contents.
            ensure_owned_home(service.member_storage_policy.app_home)
        project_preparation = index_project(service, config, project)
        actual = service.materialize()
        project_children = read_stored_children(actual.member_storage_policy.db_path)
        network = FrozenHttpInput(remote)
        with network.active():
            external = prepare_external_sources(actual, project, targets, workspace)
            before = index_state(actual, project, documents, external)
            calls, validations = [], []
            app = actual.unified_context
            retrieve = app.get_docs_context
            validate = context_tools.validate_model_visible_projection

            @wraps(retrieve)
            def observe(question_arg, **kwargs):
                project_path = kwargs.get("project_path")
                calls.append({
                    "question": question_arg, "scope": kwargs.get("scope"),
                    "project_identity": project_identity(project_path) if project_path else None,
                    "library": kwargs.get("library"), "version": kwargs.get("version"),
                    "lookup_queries": list(kwargs.get("lookup_queries") or ()),
                    "prepare_project_docs": kwargs.get("prepare_project_docs"),
                    "allow_network": kwargs.get("allow_network"),
                    "force_refresh": kwargs.get("force_refresh"),
                })
                return retrieve(question_arg, **kwargs)

            def observe_validation(payload, **kwargs):
                validations.append(True)
                return validate(payload, **kwargs)

            network.phase = "read"
            with (
                patch.object(app, "get_docs_context", observe),
                patch.object(context_tools, "validate_model_visible_projection", observe_validation),
            ):
                payload, snapshot = _call_with_snapshot(arguments, actual)
            after = index_state(actual, project, documents, external)
            payload = deepcopy(payload or {})
            diagnostics = payload.pop("diagnostics", {})
            bindings = {}
            for source in payload.get("sources") or ():
                if not isinstance(source, dict):
                    continue
                evidence_id = str(source.get("evidence_id") or "")
                bound = snapshot.get(evidence_id) or {}
                original = bound.get("source") or {}
                bindings[evidence_id] = {
                    "projected_source": deepcopy(bound.get("projected_source")),
                    "candidate_hash_material": candidate_hash_material(original),
                    "lineage": {key: deepcopy(original.get(key)) for key in LINEAGE_FIELDS if key in original},
                }
    return {
        "execution": "public_fixture_runtime", "error": None, "project_identity": identity,
        "request": expected_request(case, identity), "service_requests": calls,
        "observer_counts": {"retrieval_calls": len(calls), "validation_calls": len(validations)},
        "preparation": {
            "project": {key: project_preparation[key] for key in (
                "expected_paths", "indexed_paths", "excluded_or_failed_paths", "unexpected_paths")},
            "project_stored_children": project_children,
            "external": external,
        },
        "network_input": network.observation(),
        "state_before": before, "state_after": after,
        "public_payload": payload, "bindings": bindings,
        "pipeline_diagnostics": {key: deepcopy(diagnostics.get(key)) for key in (
            "stage_status", "planned_query_ids", "qualification_outcomes", "delivery_decision",
        ) if key in diagnostics},
    }
