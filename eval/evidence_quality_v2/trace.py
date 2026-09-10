"""First-loss attribution from explicitly complete, same-call observations."""
from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from typing import Any

STAGES = ("source", "index", "retrieval", "eligibility", "ranking", "selection", "projection")
LOSSES = ("source_gap", "ingest_failure", "retrieval_miss", "eligibility_rejection", "ranking_cap_loss", "budget_selection_loss", "projection_loss")


def classify_first_loss(observations: Mapping[str, Mapping], *, literal_visible: bool = True) -> dict:
    """No observation is not absence. Expanded visible evidence is authoritative.

    Presence is the external semantic witness assessment, not membership of an
    old expected path/ID. `complete=True` must mean the entire relevant stage was
    captured. It may not be inferred from a short bounded list or a green job.
    """
    final = observations.get("projection", {})
    if final.get("presence") == "present" and final.get("complete") is True:
        return {"category": "visible" if literal_visible else "evaluator_mismatch", "stage": "projection"}
    last_present = None
    for stage, label in zip(STAGES, LOSSES):
        observed = observations.get(stage, {})
        if observed.get("complete") is not True or observed.get("presence") not in {"present", "absent", "ambiguous"}:
            return {"category": "unobserved", "stage": stage, "last_present_stage": last_present}
        if observed["presence"] == "ambiguous":
            return {"category": "source_ambiguity" if stage == "source" else "unobserved", "stage": stage}
        if observed["presence"] == "absent":
            return {"category": label, "stage": stage, "last_present_stage": last_present}
        last_present = stage
    return {"category": "unobserved", "stage": "projection", "last_present_stage": last_present}


def bounded_completeness(returned: int, total: int | None) -> str:
    if type(returned) is not int or returned < 0 or (total is not None and (type(total) is not int or total < returned)):
        raise ValueError("inconsistent observation counts")
    if total is None:
        return "unobserved"
    return "complete" if returned == total else "truncated"


def span_identity(source: Mapping[str, Any]) -> str:
    """Do not confuse equal evidence IDs/hashes with equal source occurrences."""
    material = {key: source.get(key) for key in (
        "project_identity", "path_or_url", "version_binding", "line_start", "line_end", "char_start", "char_end")}
    material["snippet_sha256"] = hashlib.sha256(str(source.get("snippet") or "").encode()).hexdigest()
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def source_span(value: Any) -> dict:
    """Adapt actual stage values, not old index text joined by an evidence ID."""
    row = value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)
    metadata = row.get("metadata") or {}
    lines = metadata.get("line_span") or (None, None)
    chars = metadata.get("char_span") or (None, None)
    snippet = row.get("snippet") or row.get("content") or row.get("display_text") or row.get("text") or ""
    if isinstance(snippet, Mapping):
        snippet = snippet.get("code") or ""
    source = {
        "evidence_id": row.get("evidence_id") or row.get("stable_id") or row.get("stable_chunk_id") or metadata.get("stable_chunk_id"),
        "path_or_url": row.get("path_or_url") or row.get("source_path") or row.get("path") or metadata.get("project_doc_path") or metadata.get("source_path") or row.get("source"),
        "project_identity": row.get("project_identity") or metadata.get("project_identity"),
        "snippet": snippet,
        "version_binding": row.get("version_binding"),
        "line_start": row.get("line_start", lines[0]), "line_end": row.get("line_end", lines[1]),
        "char_start": row.get("char_start", chars[0]), "char_end": row.get("char_end", chars[1]),
        "authority": row.get("authority") or metadata.get("project_doc_authority"),
        "scope": row.get("scope") or row.get("doc_scope") or metadata.get("doc_scope"),
        "lifecycle": row.get("lifecycle_status") or metadata.get("lifecycle_status") or metadata.get("project_doc_lifecycle_status"),
        "retrieval_query_matches": row.get("retrieval_query_matches") or metadata.get("retrieval_query_matches") or {},
    }
    if not isinstance(source["path_or_url"], str):
        source["path_or_url"] = None
        source["non_source_record"] = True
    source["span_identity"] = span_identity(source)
    return source
