"""Compose independently admitted project quotes with an eligible library packet."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ._model_visible_docs_support import _snapshot_entry
from .evidence_candidates import (
    normalized_source, resolved_version, source_path, version_binding, version_rank,
)
from .project_docs_member_transaction import local_project_identity
from .evidence_models import EvidenceRequirementSet


def _is_library_snapshot_source(source: Any) -> bool:
    """Require a literal library class; every present carrier must agree."""
    if not isinstance(source, dict):
        return False
    metadata = source.get("metadata", {})
    if not isinstance(metadata, dict):
        return False
    classes = [carrier["source_class"] for carrier in (source, metadata)
               if "source_class" in carrier]
    return bool(classes) and all(type(value) is str and value == "library_doc" for value in classes)


def _current_project_contract(
    question: str, retrieval: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], EvidenceRequirementSet] | None:
    from .model_visible_projection import _normalize_projection_requirements

    contract = retrieval.get("project_context_contract")
    request = retrieval.get("_mixed_project_request")
    plan = retrieval.get("documentation_query_plan")
    if not all(isinstance(value, dict) for value in (contract, request, plan)):
        return None
    scope = contract.get("read_scope")
    required_scope = {
        "schema_version", "query", "project_path", "project_identity",
        "requested_scope", "requested_module", "requested_module_path",
        "doc_scope", "module_path", "evidence_path",
    }
    if not isinstance(scope, dict) or not required_scope <= scope.keys():
        return None
    if type(scope["schema_version"]) is not int or scope["schema_version"] != 1:
        return None
    if set(request) != {"project_path", "scope", "module", "module_path"}:
        return None
    if (
        not isinstance(request["project_path"], str) or not request["project_path"]
        or contract.get("request_project_path") != request["project_path"]
        or not question or contract.get("question") != question
        or scope["query"] != question or plan.get("original_question") != question
        or retrieval.get("question") != question
    ):
        return None
    for requested, current in (
        ("requested_scope", "scope"), ("requested_module", "module"),
        ("requested_module_path", "module_path"),
    ):
        if scope[requested] != request[current]:
            return None
    if request["scope"] not in {None, "project", "module", "all"}:
        return None
    for value in (request["module"], request["module_path"]):
        if value is not None and not isinstance(value, str):
            return None
    for value in (scope["module_path"], scope["evidence_path"]):
        if value is not None and (not isinstance(value, str) or not value):
            return None
    if scope["doc_scope"] not in {None, "project", "module"}:
        return None
    # Check the reader's resolved filter without resolving names from candidates.
    expected_scope = "module" if scope["module_path"] else (
        None if request["scope"] == "all" else request["scope"]
    )
    if scope["doc_scope"] != expected_scope:
        return None
    if bool(request["module"] or request["module_path"]) != bool(scope["module_path"]):
        return None
    root = scope["project_path"]
    if not isinstance(root, str) or not root or contract.get("project_path") != root:
        return None
    requested_root = Path(request["project_path"])
    # A relative or aliased root needs independent resolution, which this pure
    # projector cannot invent. Preserve the existing library packet in that case.
    if not requested_root.is_absolute() or ".." in requested_root.parts or str(requested_root) != root:
        return None
    if str(Path(root)) != root or local_project_identity(Path(root)) != scope["project_identity"]:
        return None
    for packet in (retrieval, contract):
        delivery = packet.get("delivery_decision")
        if (
            packet.get("status") not in {"success", "partial_success"}
            or packet.get("requires_confirmation") is not False
            or not isinstance(delivery, dict) or delivery.get("deliverable") is not True
        ):
            return None
    if (
        # no_results describes the control view; retained windows have separate delivery proof.
        contract.get("project_docs_status") not in {"success", "partial_success", "no_results"}
        or contract.get("project_docs_requires_confirmation") is not False
        or not isinstance(contract.get("unresolved_conflicts"), (list, tuple))
        or contract["unresolved_conflicts"]
    ):
        return None
    requirements = _normalize_projection_requirements(contract.get("requirements"))
    if requirements is None:
        return None
    return contract, scope, requirements


def _in_project_scope(
    item: dict[str, Any], scope: dict[str, Any], requirements: EvidenceRequirementSet,
) -> bool:
    if (
        item.get("source_class") != "project_doc"
        or item.get("project_identity") != scope["project_identity"]
        or scope["doc_scope"] is not None and item.get("doc_scope") != scope["doc_scope"]
        or scope["module_path"] is not None and item.get("module_path") != scope["module_path"]
        or scope["evidence_path"] is not None and item.get("path") != scope["evidence_path"]
    ):
        return False
    path_requirements = []
    for row in requirements:
        if not row.mandatory:
            continue
        kind, value = row.kind, row.value
        if kind in {"evidence_path", "project_identity", "module_id", "exact_version", "exact_snapshot"}:
            if row.qualifiers:
                return False
        if kind == "evidence_path":
            path_requirements.append(normalized_source(value))
        elif kind == "project_identity" and item.get("project_identity") != value:
            return False
        elif kind == "module_id" and item.get("module_id") != value:
            return False
        elif kind == "exact_version" and (
            resolved_version(item) != value or version_rank(version_binding(item)) != 0
        ):
            return False
        elif kind == "exact_snapshot" and (
            value != "true" or item.get("docs_snapshot_exact") is not True
        ):
            return False
    path = normalized_source(source_path(item))
    return not path_requirements or any(
        path == wanted or path.endswith("/" + wanted) for wanted in path_requirements
    )


def retain_mixed_project_context(
    *, question: str, retrieval: dict[str, Any], payload: dict[str, Any],
    snapshot: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Atomically retain current project context; never grant answer or edit proof."""
    if (
        retrieval.get("mode_selected") != "mixed" or payload.get("status") != "ok"
        or payload.get("kind") != "docs_answer" or payload.get("retrieval_only") is not True
        or payload.get("context_available") is not True
    ):
        return payload, snapshot
    from .docs_context_projection import project_docs_context
    from .model_visible_projection import (
        DOCS_SOURCE_FIELDS, _refresh_estimate, validate_model_visible_projection,
    )

    try:
        binding = _current_project_contract(question, retrieval)
        if binding is None:
            return payload, snapshot
        contract, scope, requirements = binding
        combined = deepcopy(payload)
        combined_snapshot = deepcopy(snapshot)
        _refresh_estimate(combined)
        if validate_model_visible_projection(combined, snapshot=combined_snapshot):
            return payload, snapshot
        source_ids = [source["evidence_id"] for source in combined["sources"]]
        if len(source_ids) != len(set(source_ids)) or not any(
            _is_library_snapshot_source(combined_snapshot[key].get("source"))
            for key in source_ids
        ):
            return payload, snapshot
        items = retrieval.get("context_pack")
        if not isinstance(items, (list, tuple)):
            return payload, snapshot
        project_items = [
            deepcopy(item) for item in items
            if isinstance(item, dict) and _in_project_scope(item, scope, requirements)
        ]
        if not project_items:
            return payload, snapshot
        # Reuse current member/raw-window admission; no retrieval or continuation IO.
        project, project_snapshot = project_docs_context(retrieval={
            "question": question,
            "documentation_query_plan": deepcopy(retrieval["documentation_query_plan"]),
            "context_pack": project_items,
            "project_identity": scope["project_identity"],
            "requirements": asdict(requirements),
            "status": contract["status"],
            "requires_confirmation": contract["requires_confirmation"],
            "delivery_decision": deepcopy(contract["delivery_decision"]),
        })
        if (
            project.get("kind") != "docs_context" or project.get("status") != "ok"
            or project.get("context_available") is not True
            or validate_model_visible_projection(project, snapshot=project_snapshot)
        ):
            return payload, snapshot
        for source in project["sources"]:
            # Convert the validated public shape, retaining its exact raw snapshot.
            projected = {key: source[key] for key in sorted(DOCS_SOURCE_FIELDS)}
            evidence_id = projected["evidence_id"]
            original = project_snapshot[evidence_id]["source"]
            if evidence_id in combined_snapshot:
                if (
                    combined_snapshot[evidence_id].get("projected_source") != projected
                    or combined_snapshot[evidence_id].get("source") != original
                ):
                    return payload, snapshot
                continue
            combined["sources"].append(projected)
            combined_snapshot[evidence_id] = _snapshot_entry(original, projected)
        _refresh_estimate(combined)
        if validate_model_visible_projection(combined, snapshot=combined_snapshot):
            return payload, snapshot
        return combined, combined_snapshot
    except (ValueError, TypeError, AttributeError, KeyError):
        # Malformed project proof cannot mutate the already admitted library packet.
        return payload, snapshot
