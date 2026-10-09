"""Admit a current literal body fragment without granting query coverage.

This is deliberately narrower than lexical question qualification. A syntactic
symbol from the unchanged original question may identify useful source context
even when one section cannot match the whole question. The current immutable
member, body occurrence and source window must all be independently checked.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .evidence_qualification import _relation_units, qualify_evidence
from .query_reference_binding import query_mentions
from .query_terms import documentation_query_terms, query_constraint_roles
from .technical_tokens import technical_term_pattern


def admit_original_literal_context(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
    expected_project_identity: str | None = None, lifecycle_intent: str = "current",
) -> dict[str, Any] | None:
    """Recompute a read-only admission; incoming scores/flags confer no trust.

    A title, path, link-only occurrence, repeated bare name, or unrelated body
    cannot establish this route. It returns source-bound diagnostic spans only;
    the caller must retain the failed full-question qualification and missing ID.
    """
    root = candidate.get("_reference_root_plan")
    evidence = candidate.get("_reference_evidence")
    if (not isinstance(root, dict) or root.get("question") != question
        or root.get("catalog_complete") is not True or not isinstance(evidence, dict)):
        return None
    identity = evidence.get("source")
    if not isinstance(identity, dict):
        return None
    scope = identity.get("scope")
    member = evidence.get("member_binding")
    if not isinstance(scope, dict) or not isinstance(member, dict):
        return None
    if (candidate.get("source_class") not in {"project_file", "project_doc"}
        or not scope.get("project_id") or not scope.get("snapshot_id") or not identity.get("document_id")
        or not member.get("catalog_entry_hash")):
        return None
    if (str(candidate.get("doc_scope") or "project") != member.get("doc_scope")
        or str(candidate.get("module_path") or "") != member.get("module_path")):
        return None
    catalog_hashes = [candidate.get(key) for key in (
        "project_doc_catalog_entry_hash", "_source_catalog_hash",
    ) if candidate.get(key)]
    if not catalog_hashes or any(value != member["catalog_entry_hash"] for value in catalog_hashes):
        return None
    roles = query_constraint_roles(question)
    query = {"query_id": "query-original", "text": question,
             "origin": "original", "relation": "direct"}
    qualification = qualify_evidence({
        "query_text": question, "query_origin": "original", "relation": "direct",
        "query_terms": list(documentation_query_terms(question)),
        "exact_terms": list(roles.hard_exact), "bound_subjects": list(roles.bound_subjects),
    }, query_id="query-original", visible_text=evidence_text, evidence_text=evidence_text,
        candidate=candidate, expected_project_identity=expected_project_identity or scope["project_id"],
        catalog_role=str(candidate.get("catalog_role") or candidate.get("project_doc_reason") or ""),
        lifecycle_intent=lifecycle_intent, authoritative_query=query)
    # The canonical qualifier rechecks raw-document SHA, body/window/owner,
    # project/generation and lifecycle. Any such rejection is not a relevance
    # fallback. Qualified windows retain the existing qualification path.
    if qualification.qualified or qualification.reason != "insufficient_visible_match":
        return None
    symbols = {mention.mention_id: mention for mention in query_mentions(question)
               if mention.explicit and mention.syntax_role == "symbol_identity"}
    units = _relation_units(evidence_text)
    witnesses = []
    for binding in qualification.trace.get("reference_bindings") or ():
        mention = symbols.get(binding.get("mention_id"))
        if mention is None or binding.get("role") != "symbol_identity" or binding.get("field") != "body":
            continue
        pattern = technical_term_pattern(mention.text, exact=True)
        # Removing every occurrence of the literal must leave actual body
        # content (a value, code, or prose), not an identifier-only label/list.
        substantive = any(
            re.search(pattern, unit, re.I)
            and re.search(r"[^\W_]", re.sub(pattern, "", unit, flags=re.I))
            for unit in units
        )
        if substantive:
            witnesses.append({"mention_id": mention.mention_id, "text": mention.text,
                              "char_start": binding["char_start"], "char_end": binding["char_end"]})
    if not witnesses:
        return None
    return {
        "reason": "literal_symbol_body_context", "query_id": "query-original",
        "qualification_reason": qualification.reason, "coverage_credit": False,
        "project_identity": scope["project_id"], "generation_id": scope["snapshot_id"],
        "source_id": identity.get("document_id"), "path": identity.get("canonical_path"),
        "body_witnesses": witnesses,
    }
