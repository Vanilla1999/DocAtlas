"""Pure tagging adapter for prepared source references and retrieval lanes."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from typing import Any
from dataclasses import asdict
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.literal_context_admission import admit_original_literal_context
from .context_query_probes import literal_query_probe


def _discovery_window_key(chunk: Any) -> str:
    """Identify the actual acquired window, independently of claimed query tags."""
    metadata = chunk.metadata or {}
    reference = metadata.get("_reference_evidence")
    if not isinstance(reference, dict):
        reference = {}
    binding = {
        "source": str(chunk.source), "chunk_index": chunk.chunk_index,
        "content_sha256": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
        "source_identity": reference.get("source"),
        "member_binding": reference.get("member_binding"),
        "reference_span": [reference.get("char_start"), reference.get("char_end")],
        **{key: metadata.get(key) for key in (
            "stable_chunk_id", "project_identity", "generation_id", "source_class",
            "project_doc_path", "doc_scope", "module_path", "char_span",
        )},
    }
    return hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _record_query_discovery(
    records: dict[str, dict[str, dict[str, Any]]], chunks: Any,
    lookup: DocumentationLookup,
) -> None:
    """Record a completed application-owned acquisition; metadata is not a receipt.

    The ledger stays in the current service call and is never read from a source
    or a public request. A receipt records discovery, not relevance or authority.
    Every later admission still recomputes the canonical body qualification.
    """
    for chunk in chunks:
        matches = records.setdefault(_discovery_window_key(chunk), {})
        receipt = {"query": asdict(lookup), "lexical_score": float(chunk.score)}
        previous = matches.get(lookup.query_id)
        if previous is None or receipt["lexical_score"] > previous["lexical_score"]:
            matches[lookup.query_id] = deepcopy(receipt)


def _tag_retrieval_query(
    chunks: Any, query_id: str | None, query_text: str | None = None,
    lookup: DocumentationLookup | None = None,
    *, expected_project_identity: str | None = None,
    lifecycle_intent: str = "current",
) -> list[Any]:
    if not query_id:
        return list(chunks)
    tagged = []
    for chunk in chunks:
        metadata = dict(chunk.metadata or {})
        # The lookup DTO is the execution contract; lexical metadata is neither
        # the query text nor an authority to choose a public origin.
        authoritative = asdict(lookup) if lookup is not None else None
        trace = literal_query_probe(authoritative) if authoritative else {
            "query_text": query_text or "", "admission_only": True,
        }
        if authoritative and (query_id != lookup.query_id or (query_text is not None and query_text != lookup.text)):
            authoritative = None
            trace = {"query_text": query_text or "", "query_origin": "invalid"}
        trace.setdefault("lexical_score", float(chunk.score))
        heading_value = metadata.get("heading_path") or ""
        heading_path = " > ".join(map(str, heading_value)) if isinstance(heading_value, (list, tuple)) else str(heading_value)
        visible_text = "\n".join(str(value or "") for value in (
            metadata.get("project_doc_path") or chunk.source,
            metadata.get("title"), heading_path, chunk.text,
        ))
        trace = dict(qualify_evidence(
            trace, query_id=query_id, visible_text=visible_text,
            evidence_text=chunk.text,
            catalog_role=str(metadata.get("project_doc_reason") or ""),
            candidate=metadata,
            expected_project_identity=expected_project_identity,
            lifecycle_intent=lifecycle_intent,
            authoritative_query=authoritative,
        ).trace)
        if authoritative and query_id == "query-original" and trace.get("qualified") is not True:
            admission = admit_original_literal_context(
                question=lookup.text, evidence_text=chunk.text, candidate=metadata,
                expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,
            )
            if admission is not None:
                trace["literal_context_admission"] = admission
        matches = {
            key: {**value, "admission_only": True}
            for key, value in (metadata.get("retrieval_query_matches") or {}).items()
            if isinstance(value, dict)
        }
        matches[query_id] = trace
        qualified_ids = tuple(key for key, value in matches.items() if value.get("qualified") is True)
        metadata.update({
            "retrieval_query_matches": matches,
            "retrieval_query_ids": qualified_ids,
        })
        tagged.append(chunk.model_copy(update={"metadata": metadata}))
    return tagged
