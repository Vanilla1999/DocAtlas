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


def _closed_count_context(question: str) -> tuple[QueryMention, str, int, int] | None:
    """Keep a complete count frame and its opaque phrase; infer no quantity."""
    for mention in query_mentions(question):
        if mention.explicit or mention.syntax_role != "unresolved" or not mention.text.isidentifier():
            continue
        prefix = re.fullmatch(
            r"\s*how[ \t]+many[ \t]+(?P<phrase>\w+(?:[ \t]+\w+)*)[ \t]+does[ \t]+",
            question[:mention.start], re.I,
        )
        if (prefix is not None and not re.search(r"\bdoes\b", prefix["phrase"], re.I)
            and re.fullmatch(r"[ \t]+allow\?\s*", question[mention.end:], re.I) is not None):
            return mention, prefix["phrase"], prefix.start("phrase"), prefix.end("phrase")
    return None


def _count_context_witness(
    evidence_text: str, window_start: int, count_context: tuple[QueryMention, str, int, int],
) -> dict[str, Any] | None:
    """Require two distinct raw literals in one substantive current body unit."""
    mention, phrase, query_start, query_end = count_context
    paragraph_start = 0
    for boundary in re.finditer(r"(?:\r?\n)[ \t]*(?:\r?\n)|\Z", evidence_text):
        unit_start = paragraph_start
        unit_text = evidence_text[unit_start:boundary.start()]
        paragraph_start = boundary.end()
        normalized = " ".join(unit_text.split())
        # Structural normalization only validates this entire paragraph.
        # Raw offsets never come from its whitespace-normalized output;
        # headings, links and Markdown labels cannot supply a body pair.
        if not normalized or _relation_units(unit_text) != (normalized,):
            continue
        phrase_match = re.search(technical_term_pattern(phrase, exact=True), unit_text)
        if phrase_match is None:
            continue
        remaining = re.sub(technical_term_pattern(mention.text, exact=True), "", unit_text)
        remaining = re.sub(technical_term_pattern(phrase, exact=True), "", remaining)
        if not re.search(r"[^\W_]", remaining):
            continue
        for identifier_match in re.finditer(technical_term_pattern(mention.text, exact=True), unit_text):
            if not (phrase_match.end() <= identifier_match.start()
                    or identifier_match.end() <= phrase_match.start()):
                continue
            offset = window_start + unit_start
            return {
                "mention_id": mention.mention_id, "text": mention.text,
                "char_start": offset + identifier_match.start(), "char_end": offset + identifier_match.end(),
                "query_char_start": mention.start, "query_char_end": mention.end,
                "kind": "literal_count_context",
                "literal_phrase": {
                    "text": phrase, "query_char_start": query_start, "query_char_end": query_end,
                    "char_start": offset + phrase_match.start(), "char_end": offset + phrase_match.end(),
                },
            }
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
    count_context = _closed_count_context(question)
    if (count_context is not None and isinstance(visible_span, (list, tuple))
        and len(visible_span) == 2 and all(type(value) is int for value in visible_span)
        and visible_span[1] - visible_span[0] == len(evidence_text)):
        count_witness = _count_context_witness(evidence_text, visible_span[0], count_context)
        if count_witness is not None:
            witnesses.append(count_witness)
    if not witnesses:
        return None
    return {
        "reason": "literal_symbol_body_context", "query_id": "query-original",
        "qualification_reason": qualification.reason, "coverage_credit": False,
        "project_identity": scope["project_id"], "generation_id": scope["snapshot_id"],
        "source_id": identity.get("document_id"), "path": identity.get("canonical_path"),
        "body_witnesses": witnesses,
    }
