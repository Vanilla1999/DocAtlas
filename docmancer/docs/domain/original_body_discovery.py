"""Private same-call native body discovery for ordinary partial context.

This is an application receipt, not a capability against arbitrary Python code.
It prevents normal consumers from replaying serialized candidate metadata as a
completed original read. Qualification, immutable source and relevance checks
remain independent. No receipt or grant boolean is accepted from the wire.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


@dataclass
class _BodyRead:
    question: str
    project_path: str
    project_identity: str
    receipts: set[str] = field(default_factory=set)
    active: bool = True
    experiment_admission: str | None = None
    experiment_context_max_tokens: int | None = None


_BODY_READ: ContextVar[_BodyRead | None] = ContextVar("ordinary_original_body_read", default=None)


def original_body_read_scope(handler):
    """Scope the synchronous MCP handler, including its final projection.

    The async MCP entry awaits this whole handler in asyncio.to_thread. A fresh
    nested handler never inherits receipts; finally restores the outer scope.
    Deactivation also closes any copied context after the owning call returns.
    """
    @wraps(handler)
    def scoped(name, args, service):
        question = args.get("question") if isinstance(args.get("question"), str) else ""
        project_path = args.get("project_path")
        root = Path(project_path) if isinstance(project_path, str) and project_path else None
        eligible = (
            name == "get_docs_context" and bool(question.strip())
            and root is not None and root.is_absolute() and ".." not in root.parts
            and args.get("scope") in (None, "project")
            and not args.get("module") and not args.get("module_path")
            and not args.get("library") and not args.get("libraries")
            and not args.get("maintenance") and args.get("context_format") is None
        )
        # Same pure local-owner identity as the member contract, without a new
        # resolve/stat/read. Noncanonical/symlink aliases fail closed here; the
        # existing literal and qualified paths keep their established behavior.
        state = _BodyRead(question, project_path,
                          "local:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()) if eligible else None
        # Host-only, original-read experiment. Capture once for this invocation;
        # request/candidate metadata and later environment changes cannot opt in.
        # Explicit lookups retain the default admission contract.
        if state is not None and not args.get("lookup_queries"):
            mode = os.environ.get("DOCATLAS_EXPERIMENT_ADMISSION")
            if mode in {"policy_candidates_v1", "scalar_label_candidates_v3", "source_valid_candidates_v1"}:
                state.experiment_admission = mode
            # The common experimental packet cap is independent of admission.
            # Capture it once, including for the unchanged V3/default control.
            raw_cap = os.environ.get("DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS")
            if raw_cap is not None:
                value = raw_cap.strip()
                if not value.isascii() or not value.isdecimal() or int(value) <= 0:
                    raise ValueError("DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS must be a positive integer")
                state.experiment_context_max_tokens = int(value)
        token = _BODY_READ.set(state)
        try:
            return handler(name, args, service)
        finally:
            if state is not None:
                state.active = False
                state.receipts.clear()
            _BODY_READ.reset(token)
    return scoped


def policy_candidate_admission_active() -> bool:
    """Experimental host mode is usable only inside its live public read scope."""
    state = _BODY_READ.get()
    return bool(state is not None and state.active
                and state.experiment_admission in {"policy_candidates_v1", "scalar_label_candidates_v3"})


def scalar_label_candidate_admission_active() -> bool:
    """Only the separately captured V3 mode may use scalar-label fallback."""
    state = _BODY_READ.get()
    return bool(state is not None and state.active
                and state.experiment_admission == "scalar_label_candidates_v3")


def source_valid_candidate_admission_active() -> bool:
    """Only the captured host mode permits unassessed source-valid candidates."""
    state = _BODY_READ.get()
    return bool(state is not None and state.active
                and state.experiment_admission == "source_valid_candidates_v1")


def experimental_context_max_tokens() -> int | None:
    """Return the common host cap captured for this live original project read."""
    state = _BODY_READ.get()
    return state.experiment_context_max_tokens if state is not None and state.active else None


def _window_binding(*, question: str, body: str, candidate: Mapping[str, Any]) -> str | None:
    state = _BODY_READ.get()
    if state is None or not state.active or question != state.question:
        return None
    reference = candidate.get("_reference_evidence")
    root = candidate.get("_reference_root_plan")
    if (not isinstance(reference, dict) or type(reference.get("schema_version")) is not int
        or reference.get("schema_version") != 1 or not isinstance(root, dict)
        or root.get("question") != question or root.get("catalog_complete") is not True):
        return None
    source, member = reference.get("source"), reference.get("member_binding")
    if not isinstance(source, dict) or not isinstance(member, dict):
        return None
    scope = source.get("scope")
    if (not isinstance(scope, dict) or root.get("scope") != scope
        or any(not isinstance(source.get(key), str) or not source[key]
               for key in ("document_id", "canonical_path", "content_sha256"))
        or any(not isinstance(scope.get(key), str) or not scope[key]
               for key in ("project_id", "snapshot_id"))
        or not isinstance(scope.get("version"), str)
        or scope["project_id"] != state.project_identity):
        return None
    if (member.get("doc_scope") != "project" or member.get("module_path") != ""
        or not isinstance(member.get("catalog_entry_hash"), str) or not member["catalog_entry_hash"]
        or str(candidate.get("doc_scope") or "project") != "project"
        or str(candidate.get("module_path") or "") != ""
        or candidate.get("source_class") not in {"project_file", "project_doc"}
        or candidate.get("project_identity") != scope["project_id"]
        or candidate.get("generation_id") != scope["snapshot_id"]):
        return None
    hashes = [candidate.get(key) for key in (
        "project_doc_catalog_entry_hash", "_source_catalog_hash",
    ) if candidate.get(key)]
    if not hashes or any(value != member["catalog_entry_hash"] for value in hashes):
        return None
    start, end = reference.get("char_start"), reference.get("char_end")
    document = reference.get("raw_document")
    if (type(start) is not int or type(end) is not int or not isinstance(document, str)
        or not 0 <= start < end <= len(document) or document[start:end] != body
        or reference.get("text") != body
        or hashlib.sha256(document.encode("utf-8")).hexdigest() != source["content_sha256"]):
        return None
    file_hash = reference.get("project_doc_content_hash")
    if not isinstance(file_hash, str) or not file_hash:
        return None
    material = {
        "question": question, "request_project_path": state.project_path, "request_scope": "project",
        "source": {key: source[key] for key in ("document_id", "canonical_path", "content_sha256")},
        "scope": {key: scope[key] for key in ("project_id", "version", "snapshot_id")},
        "member": {key: member[key] for key in ("doc_scope", "module_path", "catalog_entry_hash")},
        "file_content_hash": file_hash, "window_span": [start, end],
        "window_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }
    return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def record_original_body_discovery(
    *, query: Mapping[str, Any], body: str, candidate: Mapping[str, Any],
) -> None:
    """Called only after the application's native read and fresh source prepare."""
    if (query.get("query_id") != "query-original" or query.get("origin") != "original"
        or query.get("relation") != "direct" or query.get("public_parent_query_id")
        or query.get("derived_from_query_id") or query.get("derived_from_query_ids")
        or any(query.get(key) for key in (
            "parent_exact_terms", "need_subject", "need_relation", "need_context",
            "component_rewrite_audit", "preferred_catalog_roles",
            "forbidden_catalog_roles", "forbidden_evidence_terms",
        ))):
        return
    key = _window_binding(question=query.get("text"), body=body, candidate=candidate)
    state = _BODY_READ.get()
    if key is not None and state is not None:
        state.receipts.add(key)


def original_body_discovery_binding(
    *, question: str, body: str, candidate: Mapping[str, Any],
) -> str | None:
    """Require the exact current window from this original request's native read."""
    key = _window_binding(question=question, body=body, candidate=candidate)
    state = _BODY_READ.get()
    return key if key is not None and state is not None and key in state.receipts else None


def original_body_derivation_binding(
    *, question: str, body: str, candidate: Mapping[str, Any], native_candidate: Mapping[str, Any],
) -> str | None:
    """Recheck a derived window's native provenance, without minting a receipt.

    This checks only same-call/source/window identity. The admission caller must
    also recheck source policy, request constraints and the structural edge.
    An incoming seed dictionary works only while its exact native receipt lives.
    """
    native = native_candidate.get("_reference_evidence")
    derived = candidate.get("_reference_evidence")
    if not isinstance(native, dict) or not isinstance(derived, dict):
        return None
    native_body = native.get("text")
    if not isinstance(native_body, str):
        return None
    binding = original_body_discovery_binding(
        question=question, body=native_body, candidate=native_candidate,
    )
    if binding is None or _window_binding(question=question, body=body, candidate=candidate) is None:
        return None
    if (candidate.get("_reference_root_plan") != native_candidate.get("_reference_root_plan")
        or any(derived.get(key) != native.get(key) for key in (
            "source", "member_binding", "project_doc_content_hash", "raw_document",
        ))):
        return None
    return binding
