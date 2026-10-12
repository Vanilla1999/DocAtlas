"""Admit a current literal body fragment without granting query coverage.

This is deliberately narrower than lexical question qualification. A syntactic
symbol from the unchanged original question may identify useful source context
even when one section cannot match the whole question. The current immutable
member, body occurrence and source window must all be independently checked.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from docmancer.core.structured_chunking import _atom_spans, parse_markdown_parents

from .context_blocks import source_block_alternatives
from .evidence_qualification import _relation_units, qualify_evidence
from .original_body_discovery import original_body_discovery_binding
from .query_reference_binding import QueryMention, query_mentions, document_statement_mentions
from .query_terms import documentation_query_terms, query_constraint_roles
from .technical_tokens import technical_term_pattern
from .ordinary_body_context import (
    body_request_constraint_rejection,
    ordinary_body_context_witness,
    policy_valid_original_candidate_witness,
    source_valid_original_candidate_witness,
)


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


def _closed_pair_context(question: str) -> tuple[QueryMention, ...]:
    """Consume one context request for two unresolved, distinct raw names."""
    mentions = query_mentions(question)
    if (len(mentions) != 2 or any(
        mention.explicit or mention.syntax_role != "unresolved" or not mention.text.isidentifier()
        for mention in mentions
    ) or mentions[0].text == mentions[1].text):
        return ()
    left, right = mentions
    if (re.fullmatch(r"\s*how[ \t]+does[ \t]+", question[:left.start], re.I) is None
        or re.fullmatch(r"[ \t]+differ[ \t]+from[ \t]+", question[left.end:right.start], re.I) is None
        or re.fullmatch(r"\?\s*", question[right.end:]) is None):
        return ()
    return mentions


def _pair_context_witnesses(
    evidence_text: str, window_start: int, mentions: tuple[QueryMention, ...],
) -> list[dict[str, Any]]:
    """Bind both complete identifiers inside one unchanged plain paragraph."""
    if len(mentions) != 2 or mentions[0].text == mentions[1].text:
        return []
    # Qualified spellings cannot lend their identifier segment to a bare name.
    patterns = [r"(?<![\w.:/\\-])" + re.escape(mention.text) + r"(?![\w/\\-]|\.\w|::)"
                for mention in mentions]
    paragraph_start = 0
    for boundary in re.finditer(r"(?:\r?\n)[ \t]*(?:\r?\n)|\Z", evidence_text):
        unit_start = paragraph_start
        unit_text = evidence_text[unit_start:boundary.start()]
        paragraph_start = boundary.end()
        normalized = " ".join(unit_text.split())
        if (not normalized or _relation_units(unit_text) != (normalized,)
            or any(re.match(r"^(?:[ \t]*>| {4}|\t)", line) for line in unit_text.splitlines())):
            continue
        paired = []
        remaining = unit_text
        for mention, pattern in zip(mentions, patterns):
            matches = list(re.finditer(pattern, unit_text))
            if matches:
                paired.append((mention, matches[0]))
            remaining = re.sub(pattern, "", remaining)
        if len(paired) != 2 or not re.search(r"[^\W_]", remaining):
            continue
        offset = window_start + unit_start
        return [{
            "mention_id": mention.mention_id, "text": mention.text,
            "char_start": offset + match.start(), "char_end": offset + match.end(),
            "query_char_start": mention.start, "query_char_end": mention.end,
            "kind": "literal_pair_context",
            "paragraph_char_start": offset, "paragraph_char_end": offset + len(unit_text),
        } for mention, match in paired]
    return []


def _closed_explain_literals(question: str) -> tuple[QueryMention, ...]:
    """Consume the entire explicit identifier list before admitting any body."""
    frame = re.match(r"\s*explain[ \t]+", question, re.I)
    if frame is None:
        return ()
    mentions = {mention.start: mention for mention in query_mentions(question)
                if not mention.explicit and mention.syntax_role == "unresolved"
                and mention.text.isidentifier()}
    selected = []
    cursor = frame.end()
    while True:
        mention = mentions.get(cursor)
        if mention is None:
            return ()
        selected.append(mention)
        cursor = mention.end
        separator = re.match(r"[ \t]+and[ \t]+", question[cursor:], re.I)
        if separator is None:
            break
        cursor += separator.end()
    if re.fullmatch(r"\.\s*", question[cursor:]) is None:
        return ()
    return tuple(selected)


def _explain_context_witnesses(
    evidence_text: str, window_start: int, mentions: tuple[QueryMention, ...],
) -> list[dict[str, Any]]:
    """Return raw body occurrences only for the identifiers present here."""
    witnesses = []
    paragraph_start = 0
    for boundary in re.finditer(r"(?:\r?\n)[ \t]*(?:\r?\n)|\Z", evidence_text):
        unit_start = paragraph_start
        unit_text = evidence_text[unit_start:boundary.start()]
        paragraph_start = boundary.end()
        normalized = " ".join(unit_text.split())
        if not normalized or _relation_units(unit_text) != (normalized,):
            continue
        remaining = unit_text
        for mention in mentions:
            remaining = re.sub(technical_term_pattern(mention.text, exact=True), "", remaining)
        if not re.search(r"[^\W_]", remaining):
            continue
        for mention in mentions:
            pattern = technical_term_pattern(mention.text, exact=True)
            for match in re.finditer(pattern, unit_text):
                witnesses.append({
                    "mention_id": mention.mention_id, "text": mention.text,
                    "char_start": window_start + unit_start + match.start(),
                    "char_end": window_start + unit_start + match.end(),
                    "query_char_start": mention.start, "query_char_end": mention.end,
                    "kind": "literal_explain_context",
                })
    return witnesses


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



def _checked_raw_body_window(
    evidence_text: str, candidate: Mapping[str, Any], evidence: Mapping[str, Any],
    visible_span: Any,
) -> dict[str, int] | None:
    """Translate the canonical trimmed span back to the unchanged source bytes.

    The qualifier has already checked current owner, snapshot and unique visible
    occurrence. Outer whitespace may not widen the current candidate window or
    attest text that is absent from the immutable document.
    """
    if (not isinstance(visible_span, (list, tuple)) or len(visible_span) != 2
        or any(type(value) is not int for value in visible_span)
        or not evidence_text.strip()
        or visible_span[1] - visible_span[0] != len(evidence_text.strip())):
        return None
    start = visible_span[0] - (len(evidence_text) - len(evidence_text.lstrip()))
    end = start + len(evidence_text)
    span = ((candidate["char_start"], candidate["char_end"])
            if "char_start" in candidate and "char_end" in candidate
            else candidate.get("char_span") or ())
    raw = evidence.get("raw_document")
    reference_start, reference_end = evidence.get("char_start"), evidence.get("char_end")
    if (not isinstance(raw, str)
        or type(reference_start) is not int or type(reference_end) is not int
        or not isinstance(span, (list, tuple)) or len(span) != 2
        or any(type(value) is not int for value in span)
        or not 0 <= reference_start <= span[0] <= start < end <= span[1] <= reference_end <= len(raw)
        or raw[start:end] != evidence_text
        or raw[reference_start:reference_end] != evidence.get("text")):
        return None
    return {
        "char_start": start, "char_end": end,
        "byte_start": len(raw[:start].encode("utf-8")), "byte_end": len(raw[:end].encode("utf-8")),
        "line_start": raw[:start].count("\n") + 1, "line_end": raw[:end - 1].count("\n") + 1,
    }

def _checked_original_candidate(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
    expected_project_identity: str | None = None, lifecycle_intent: str = "current",
) -> tuple | None:
    """Share canonical source/request qualification, without changing its result."""
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
    return qualification, evidence, identity, scope


def admit_original_literal_context(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
    expected_project_identity: str | None = None, lifecycle_intent: str = "current",
) -> dict[str, Any] | None:
    """Recompute a read-only admission; incoming scores/flags confer no trust.

    A title, path or link-only occurrence cannot establish this route. By default
    unrelated body and repeated bare names cannot establish it either. The
    isolated host experiment additionally permits source-valid body candidates
    with unassessed relevance, never query or answer authority. It returns
    source-bound diagnostic spans only; the caller must retain the failed
    full-question qualification and missing ID.
    """
    checked = _checked_original_candidate(
        question=question, evidence_text=evidence_text, candidate=candidate,
        expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,
    )
    if checked is None:
        return None
    qualification, evidence, identity, scope = checked
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
    body_window = _checked_raw_body_window(evidence_text, candidate, evidence, visible_span)
    if closed_literal is not None and body_window is not None:
        pattern = technical_term_pattern(closed_literal.text, exact=True)
        for match in re.finditer(pattern, evidence_text):
            occurrences.append((closed_literal, {
                "char_start": body_window["char_start"] + match.start(),
                "char_end": body_window["char_start"] + match.end(),
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
    explain_literals = _closed_explain_literals(question)
    if explain_literals and body_window is not None:
        witnesses.extend(_explain_context_witnesses(evidence_text, body_window["char_start"], explain_literals))
    count_context = _closed_count_context(question)
    if count_context is not None and body_window is not None:
        count_witness = _count_context_witness(evidence_text, body_window["char_start"], count_context)
        if count_witness is not None:
            witnesses.append(count_witness)
    pair_context = _closed_pair_context(question)
    if pair_context and body_window is not None:
        witnesses.extend(_pair_context_witnesses(evidence_text, body_window["char_start"], pair_context))
    statement_context = document_statement_mentions(question)
    if statement_context is not None and body_window is not None:
        locator, target = statement_context
        # A path is supplied only by the canonical qualifier's fresh full-catalog
        # recheck. The bare body target stays unresolved and gains no query role.
        source_bound = any(
            binding.get("mention_id") == locator.mention_id
            and binding.get("role") == "source_locator" and binding.get("field") == "path"
            and binding.get("syntax") == "structural_filename"
            and all(binding.get(key) == value for key, value in identity.items())
            for binding in qualification.trace.get("reference_bindings") or ()
        )
        if source_bound:
            for witness in _explain_context_witnesses(evidence_text, body_window["char_start"], (target,)):
                witnesses.append({
                    **witness, "kind": "literal_document_statement_context",
                    "source_mention_id": locator.mention_id,
                    "source_query_char_start": locator.start, "source_query_char_end": locator.end,
                })
    reason = "literal_symbol_body_context"
    if witnesses and body_window is None:
        return None
    if not witnesses:
        # A low lexical ratio and absent exact terms share one qualification
        # reason. General partial context cannot bypass an explicit identity.
        if qualification.trace.get("missing_exact_terms") or body_window is None:
            return None
        ordinary = ordinary_body_context_witness(
            question=question, evidence_text=evidence_text, candidate=candidate,
        )
        if ordinary is None:
            ordinary = source_valid_original_candidate_witness(
                question=question, evidence_text=evidence_text, candidate=candidate,
            )
        if ordinary is None:
            ordinary = policy_valid_original_candidate_witness(
                question=question, evidence_text=evidence_text, candidate=candidate,
            )
        if ordinary is None:
            return None
        witnesses = [ordinary]
        reason = ordinary["kind"]
    return {
        "reason": reason, "query_id": "query-original",
        "qualification_reason": qualification.reason, "coverage_credit": False,
        "project_identity": scope["project_id"], "generation_id": scope["snapshot_id"],
        "source_id": identity.get("document_id"), "path": identity.get("canonical_path"),
        "body_witnesses": witnesses,
        **({"body_window": body_window} if body_window is not None else {}),
    }


def _trimmed_span(raw: str, start: int, end: int) -> tuple[int, int]:
    while start < end and raw[start].isspace():
        start += 1
    while end > start and raw[end - 1].isspace():
        end -= 1
    return start, end


def _checked_context_derivation(
    *, raw: str, document_id: str, seed_span: tuple[int, int],
    visible_span: tuple[int, int], derivation: str | None,
) -> str | None:
    """Validate structural provenance, never infer semantic contribution.

    Contained spans preserve the existing canonical-unit projection path. New
    supplements are limited to the existing document-intro or colon lead-in
    dependencies; an arbitrary nearby/query-ranked block is not such an edge.
    """
    seed_start, seed_end = _trimmed_span(raw, *seed_span)
    start, end = _trimmed_span(raw, *visible_span)
    if derivation is None:
        return "native" if (start, end) == (seed_start, seed_end) else None
    if derivation == "contained_span":
        return derivation if seed_span[0] <= start < end <= seed_span[1] else None
    if derivation == "containing_span":
        if not start <= seed_start < seed_end <= end:
            return None
        if (start, end) == (seed_start, seed_end):
            return derivation
        parents = parse_markdown_parents(raw, document_id)
        if len(parents) > 4096:
            return None
        owners = [parent for parent in parents
                  if parent.char_start <= start < end <= parent.char_end]
        if len(owners) != 1:
            return None
        owner = owners[0]
        if _trimmed_span(raw, owner.char_start, owner.char_end) == (start, end):
            return derivation
        alternatives = source_block_alternatives(raw[owner.char_start:owner.char_end])
        if (start - owner.char_start, end - owner.char_start) in alternatives.spans:
            return derivation
        atoms = [atom for atom in _atom_spans(raw, owner.char_start, owner.char_end)
                 if atom.atom_type != "whitespace" and atom.start < seed_end and seed_start < atom.end]
        if atoms and _trimmed_span(raw, min(seed_start, atoms[0].start), max(seed_end, atoms[-1].end)) == (start, end):
            return derivation
        return None
    if derivation != "supplementary_block" or not (end <= seed_start or seed_end <= start):
        return None
    parents = parse_markdown_parents(raw, document_id)
    if not parents or len(parents) > 4096:
        return None
    seed_owners = [parent for parent in parents
                   if parent.char_start <= seed_start < seed_end <= parent.char_end]
    if len(seed_owners) != 1:
        return None
    owner = seed_owners[0]
    first = parents[0]
    if (first.char_start == 0 and first.logical_id != owner.logical_id and first.level == 1
        and len(owner.heading_path) > len(first.heading_path)
        and owner.heading_path[:len(first.heading_path)] == first.heading_path):
        intro = next((atom for atom in _atom_spans(raw, first.char_start, first.char_end)
                      if atom.atom_type not in {"heading", "whitespace"}
                      and raw[atom.start:atom.end].strip()), None)
        if (intro is not None and intro.atom_type == "prose"
            and _trimmed_span(raw, intro.start, intro.end) == (start, end)):
            return "document_intro"
    atoms = [atom for atom in _atom_spans(raw, owner.char_start, owner.char_end)
             if atom.atom_type != "whitespace" and raw[atom.start:atom.end].strip()]
    for lead, following in zip(atoms, atoms[1:]):
        if (lead.atom_type == "prose" and following.atom_type in {"code", "list", "table"}
            and raw[lead.start:lead.end].rstrip().endswith(":")
            and _trimmed_span(raw, lead.start, lead.end) == (start, end)
            and following.start <= seed_start < seed_end <= following.end):
            return "structured_block_lead_in"
    return None


def recheck_source_valid_candidate(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
    native_candidate: Mapping[str, Any] | None = None, derivation: str | None = None,
    expected_project_identity: str | None = None, lifecycle_intent: str = "current",
    rejection_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Recheck an experimental packet entry against a live canonical native seed.

    C retains the original application-owned native candidate before projection
    changes its span. Both it and the final candidate are freshly checked. The
    result describes native/derived provenance and the surviving existing or
    unassessed route; it grants no new qualification, coverage or edit authority.
    Serialized results cannot replace the current native receipt or raw source.
    Existing qualified/literal routes keep their own request constraints: the
    broad route's missing-exact/unresolved-name guard must not tighten them.
    """
    if rejection_diagnostics is not None:
        rejection_diagnostics.clear()

    def reject(axis: str, reason: str):
        if rejection_diagnostics is not None:
            rejection_diagnostics.update(axis=axis, reason=reason)
        return None

    def qualification_axis(reason: str) -> str:
        if ("locator" in reason or reason.startswith("structural_source_") or reason in {
            "query_contract_mismatch", "nonliteral_retrieval_lane", "missing_bound_subject",
            "missing_visible_exact_path", "missing_visible_query_terms", "unsupported_relation_qualification",
        }):
            return "request_constraints"
        return "source_admissible"

    seed = native_candidate if native_candidate is not None else candidate
    seed_evidence = seed.get("_reference_evidence")
    if not isinstance(seed_evidence, dict) or not isinstance(seed_evidence.get("text"), str):
        return reject("source_admissible", "missing_native_source_reference")
    seed_text = seed_evidence["text"]
    native_binding = original_body_discovery_binding(question=question, body=seed_text, candidate=seed)
    if native_binding is None:
        return reject("source_admissible", "missing_current_native_discovery")
    seed_checked = _checked_original_candidate(
        question=question, evidence_text=seed_text, candidate=seed,
        expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,
    )
    if seed_checked is None:
        return reject("source_admissible", "native_source_binding_rejected")
    seed_qualification = seed_checked[0]
    seed_admission = None
    if not seed_qualification.qualified:
        if seed_qualification.reason != "insufficient_visible_match":
            return reject(qualification_axis(seed_qualification.reason), seed_qualification.reason)
        seed_admission = admit_original_literal_context(
            question=question, evidence_text=seed_text, candidate=seed,
            expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,
        )
        if seed_admission is None:
            if seed_qualification.trace.get("missing_exact_terms"):
                return reject("request_constraints", "missing_exact_terms")
            name_reason = body_request_constraint_rejection(question=question, evidence_text=seed_text, candidate=seed)
            return reject("request_constraints" if name_reason else "contribution", name_reason or "native_admission_rejected")
    checked = _checked_original_candidate(
        question=question, evidence_text=evidence_text, candidate=candidate,
        expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,
    )
    if checked is None:
        return reject("source_admissible", "source_binding_rejected")
    qualification, evidence, identity, scope = checked
    if (candidate.get("_reference_root_plan") != seed.get("_reference_root_plan")
        or any(evidence.get(key) != seed_evidence.get(key) for key in (
            "source", "member_binding", "project_doc_content_hash", "raw_document",
        ))):
        return reject("source_admissible", "derived_source_mismatch")
    if not qualification.qualified and qualification.reason != "insufficient_visible_match":
        return reject(qualification_axis(qualification.reason), qualification.reason)
    window = _checked_raw_body_window(
        evidence_text, candidate, evidence, qualification.trace.get("reference_visible_span"),
    )
    if window is None:
        return reject("source_admissible", "raw_visible_span_mismatch")
    raw = evidence["raw_document"]
    seed_span = (seed_evidence["char_start"], seed_evidence["char_end"])
    visible_span = (window["char_start"], window["char_end"])
    edge = _checked_context_derivation(
        raw=raw, document_id=identity["document_id"], seed_span=seed_span,
        visible_span=visible_span, derivation=derivation,
    )
    # A separately acquired block may keep its own native provenance. A seed
    # merely in the same file must not authorize that otherwise unrelated span.
    own_binding = original_body_discovery_binding(
        question=question, body=evidence_text, candidate=candidate,
    )
    if edge is None and derivation == "supplementary_block" and own_binding is not None:
        edge, native_binding = "native", own_binding
    if edge is None:
        return reject("source_admissible", "unverified_structural_derivation")
    route = "existing_qualified" if qualification.qualified else None
    admission = None
    if route is None:
        admission = admit_original_literal_context(
            question=question, evidence_text=evidence_text, candidate=candidate,
            expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,
        )
        # Keeping every original body byte also preserves its checked literal
        # witnesses. Do not tighten a special partial-identity route by applying
        # the new broad branch's blanket missing-exact guard to this superset.
        seed_start, seed_end = _trimmed_span(raw, *seed_span)
        seed_retained = window["char_start"] <= seed_start < seed_end <= window["char_end"]
        if (admission is None and seed_admission is not None and seed_retained
            and edge in {"native", "containing_span"}):
            admission = seed_admission
        if admission is not None:
            route = ("source_valid_unassessed" if admission["reason"] == "source_valid_original_candidate_v1"
                     else "existing_literal")
    if route is None:
        if qualification.trace.get("missing_exact_terms"):
            return reject("request_constraints", "missing_exact_terms")
        name_reason = body_request_constraint_rejection(question=question, evidence_text=evidence_text, candidate=candidate)
        if name_reason is not None:
            return reject("request_constraints", name_reason)
        # Normalize only the already verified visible occurrence. Its new span
        # receives no native receipt; the witness rechecks the original seed.
        visible_candidate = {**candidate, **window, "_reference_evidence": {
            **evidence, "char_start": window["char_start"], "char_end": window["char_end"], "text": evidence_text,
        }}
        witness = source_valid_original_candidate_witness(
            question=question, evidence_text=evidence_text, candidate=visible_candidate, native_candidate=seed,
        )
        if witness is None:
            return reject("contribution", "no_admitted_body_route")
        route = "source_valid_unassessed"
    return {
        "schema_version": 1, "route": route, "derivation": edge,
        "native_discovery_binding_sha256": native_binding,
        "native_span": (list((evidence["char_start"], evidence["char_end"]))
                        if own_binding is not None and native_binding == own_binding else list(seed_span)),
        "body_window": window,
        "project_identity": scope["project_id"], "generation_id": scope["snapshot_id"],
        "source_id": identity["document_id"], "source_sha256": identity["content_sha256"],
        "qualification_reason": qualification.reason, "coverage_credit": False,
        "relevance_unassessed": True,
    }
