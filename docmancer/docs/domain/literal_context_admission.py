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
from .query_reference_binding import QueryMention, query_mentions
from .query_terms import documentation_query_terms, query_constraint_roles
from .technical_tokens import technical_term_pattern


def _closed_context_literal(question: str) -> QueryMention | None:
    """Recognize only a completely consumed request for one literal's context.

    This does not resolve the mention, infer its source role or qualify the
    original question. Identity, behavior and requirements forms only select
    context; they do not prove an answer or derive a requirement. Extra
    conditions, modifiers and clauses remain rejected.
    """
    for mention in query_mentions(question):
        if mention.explicit or mention.syntax_role != "unresolved" or not mention.text.isidentifier():
            continue
        before, after = question[:mention.start], question[mention.end:]
        closed = (
            re.fullmatch(r"\s*what[ \t]+does[ \t]+", before, re.I) is not None
            and re.fullmatch(r"[ \t]+(?:do|require)\?\s*", after, re.I) is not None
        ) or (
            re.fullmatch(r"\s*(?:what[ \t]+is|which[ \t]+conditions[ \t]+are[ \t]+required[ \t]+by)[ \t]+",
                         before, re.I) is not None
            and re.fullmatch(r"\?\s*", after) is not None
        )
        if closed:
            return mention
    return None


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
    occurrences = []
    for binding in qualification.trace.get("reference_bindings") or ():
        mention = symbols.get(binding.get("mention_id"))
        if mention is not None and binding.get("role") == "symbol_identity" and binding.get("field") == "body":
            occurrences.append((mention, binding, re.I))
    # A closed context request can name a previously unresolved bare literal.
    # Bind its exact spelling directly to the already validated current window;
    # no reference role or original-query trace is modified.
    closed_literal = _closed_context_literal(question)
    visible_span = qualification.trace.get("reference_visible_span")
    if (closed_literal is not None and isinstance(visible_span, (list, tuple))
        and len(visible_span) == 2 and all(type(value) is int for value in visible_span)
        and visible_span[1] - visible_span[0] == len(evidence_text)):
        pattern = technical_term_pattern(closed_literal.text, exact=True)
        for match in re.finditer(pattern, evidence_text):
            occurrences.append((closed_literal, {
                "char_start": visible_span[0] + match.start(),
                "char_end": visible_span[0] + match.end(),
            }, 0))
    units = _relation_units(evidence_text)
    witnesses = []
    for mention, binding, match_flags in occurrences:
        pattern = technical_term_pattern(mention.text, exact=True)
        # Removing every occurrence of the literal must leave actual body
        # content (a value, code, or prose), not an identifier-only label/list.
        substantive = any(
            re.search(pattern, unit, match_flags)
            and re.search(r"[^\W_]", re.sub(pattern, "", unit, flags=match_flags))
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
