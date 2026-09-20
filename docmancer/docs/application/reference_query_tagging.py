"""Pure tagging adapter for prepared source references and retrieval lanes."""
from __future__ import annotations
from typing import Any
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup
from docmancer.docs.domain.evidence_qualification import qualify_evidence, derived_parent_trace
from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles
from docmancer.docs.domain.project_doc_ranking import normalize_doc_path
from .context_selection import merge_query_matches
from .retrieval_need_support import apply_retrieval_need_witness

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
        trace = dict(metadata.get("lexical_match") or {})
        exact_path_match = bool(metadata.get("exact_path_match"))
        if query_id.startswith("query-path-") and query_text:
            candidate_path = str(
                metadata.get("project_doc_path")
                or metadata.get("path")
                or chunk.source
            )
            exact_path_match = (
                normalize_doc_path(candidate_path) == normalize_doc_path(query_text)
            )
        if exact_path_match and query_id.startswith("query-path-"):
            trace["mode"] = "exact_path"
        elif trace.get("mode") == "exact_path":
            trace.pop("mode")
        trace.setdefault("lexical_score", float(chunk.score))
        if query_text:
            if trace.get("query_text") != query_text:
                trace["query_terms"] = list(documentation_query_terms(query_text))
                roles = query_constraint_roles(query_text)
                trace.update(exact_terms=list(roles.hard_exact), bound_subjects=list(roles.bound_subjects),
                             retrieval_anchors=list(roles.retrieval_anchors))
            trace["query_text"] = query_text
        if lookup is not None:
            trace.update({
                "query_origin": lookup.origin,
                "relation": lookup.relation,
                "public_parent_query_id": lookup.public_parent_query_id,
                "preferred_catalog_roles": list(lookup.preferred_catalog_roles),
                "forbidden_catalog_roles": list(lookup.forbidden_catalog_roles),
                "forbidden_evidence_terms": list(lookup.forbidden_evidence_terms),
                "parent_exact_terms": list(lookup.parent_exact_terms),
                "need_subject": lookup.need_subject, "need_relation": lookup.need_relation, "need_context": lookup.need_context,
            })
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
        ).trace)
        trace = apply_retrieval_need_witness({**trace, "query_id": query_id, "text": query_text or ""}, trace, chunk.text,
            source={"verified_owner": trace.get("bound_subject_context"), "authority": metadata.get("authority"), "lifecycle_status": metadata.get("lifecycle_status")})
        matches = dict(metadata.get("retrieval_query_matches") or {})
        matches[query_id] = trace
        parent_trace = (
            derived_parent_trace(
                trace,
                source_query_id=query_id,
                parent_query_id=str(lookup.public_parent_query_id or ""),
            )
            if lookup is not None else None
        )
        if parent_trace is not None:
            matches = merge_query_matches(matches, {lookup.public_parent_query_id: parent_trace})
        qualified_ids = tuple(key for key, value in matches.items() if value.get("qualified") is True)
        metadata.update({
            "retrieval_query_matches": matches,
            "retrieval_query_ids": qualified_ids,
        })
        tagged.append(chunk.model_copy(update={"metadata": metadata}))
    return tagged
