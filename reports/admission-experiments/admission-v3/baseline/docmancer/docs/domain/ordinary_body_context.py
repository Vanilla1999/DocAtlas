"""Same-call literal partial context, without whole-question coverage.

Source eligibility and native discovery are necessary but never topical proof.
An unchanged query phrase, or a body-bound technical anchor with another literal
term, can identify useful context inside an acquired structural block. No query
rewrites, word dictionaries, stemming or answer/subject inference are used.
Common phrases can still be weak lexical matches; this route grants no answer
support or full-question coverage.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from docmancer.core.structured_chunking import _atom_spans

from .context_blocks import source_block_alternatives
from .original_body_discovery import original_body_discovery_binding, policy_candidate_admission_active
from .query_reference_binding import query_mentions
from .query_terms import documentation_technical_anchors
from .source_subject_binding import prepared_owner_rejection


_WORD = re.compile(r"(?<!\w)[^\W\d_]+(?:[-'][^\W\d_]+)*(?!\w)")
_TERM = re.compile(r"[\w.:/\\+-]+")
# Keep the existing conservative clause boundaries for phrase witnesses. This
# grammar only stops a phrase; it does not supply accepted words or query roles.
_BOUNDARY = re.compile(r"[.!?;:,|–—]+|(?<!\w)-|-(?!\w)|\b(?:and|but|or|yet|whereas|although|though)\b", re.I)
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_SETEXT_HEADING = re.compile(r"(?m)^ {0,3}\S[^\r\n]*\r?\n {0,3}(?:=+|-+)[ \t]*(?=\r?$)")
_NONBODY = re.compile(
    r"<!--.*?-->|!?\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])|https?://\S+"
    r"|^[ \t]*\[[^\]]+\]:[^\n]*|^ {0,3}(?:`{3,}|~{3,})[^\n]*",
    re.S | re.M,
)


def _clauses(text: str):
    cursor = 0
    for boundary in _BOUNDARY.finditer(text):
        yield cursor, text[cursor:boundary.start()]
        cursor = boundary.end()
    yield cursor, text[cursor:]


def _literal_terms(text: str):
    """Keep complete Unicode terms and their unchanged source coordinates."""
    for match in _TERM.finditer(text):
        # A final period/colon is sentence punctuation. Internal decimal or
        # identifier separators remain part of the same indivisible term.
        value = match[0].rstrip(".:")
        if value and any(char.isalnum() for char in value):
            yield value, match.start(), match.start() + len(value)


def _whole_word_spans(text: str):
    terms = [(start, end) for _, start, end in _literal_terms(text)]
    # Apostrophes remain part of one ordinary word. A slash, namespace or path
    # separator cannot lend the separate pieces of one term as phrase words.
    return {word.span() for word in _WORD.finditer(text) if not any(
        start < word.end() and word.start() < end
        and (start < word.start() or word.end() < end)
        for start, end in terms
    )}


def _masked_body(text: str) -> str:
    """Remove navigation/format markers without changing source coordinates."""
    return _NONBODY.sub(lambda match: "".join(
        char if char in "\r\n" else " " for char in match[0]
    ), text)


def _body_blocks(text: str):
    # Setext headings are prose-shaped to the child splitter. Blank their title
    # and underline only inside prose atoms, never in fenced code or list items.
    # Keep every original character offset unchanged for source-bound witnesses.
    masked = list(text)
    for atom in _atom_spans(text, 0, len(text)):
        if atom.atom_type != "prose":
            continue
        for heading in _SETEXT_HEADING.finditer(text, atom.start, atom.end):
            for index in range(heading.start(), heading.end()):
                if text[index] not in "\r\n":
                    masked[index] = " "
    body = "".join(masked)
    # Keep the smallest structural alternatives. A union of distinct list items
    # cannot lend two unrelated occurrences to a new topical witness.
    pending = None
    leaves = []
    for start, end in sorted(source_block_alternatives(text).spans,
                             key=lambda span: (span[0], -span[1])):
        if pending is not None and not (pending[0] <= start and end <= pending[1]):
            leaves.append(pending)
        pending = (start, end)
    if pending is not None:
        leaves.append(pending)
    for start, end in leaves:
        raw = text[start:end]
        lines = raw.splitlines(keepends=True)
        if len(lines) >= 2 and _TABLE_SEPARATOR.fullmatch(lines[1].strip()):
            # Column names cannot qualify unrelated data. Every witness is
            # contained in one body row; the delivered raw window keeps headers.
            offset = start + len(lines[0]) + len(lines[1])
            for line in lines[2:]:
                if "|" in line and not _TABLE_SEPARATOR.fullmatch(line.strip()):
                    yield offset, _masked_body(body[offset:offset + len(line)])
                offset += len(line)
        else:
            yield start, _masked_body(body[start:end])


def _phrase_witness(question: str, block: str, source_offset: int):
    choices = []
    query_word_spans = _whole_word_spans(question)
    source_word_spans = _whole_word_spans(block)
    for query_offset, query_clause in _clauses(question):
        query_words = [word for word in _WORD.finditer(query_clause)
                       if (query_offset + word.start(), query_offset + word.end()) in query_word_spans]
        for clause_offset, source_clause in _clauses(block):
            source_words = [word for word in _WORD.finditer(source_clause)
                            if (clause_offset + word.start(), clause_offset + word.end()) in source_word_spans]
            for first in range(len(query_words) - 1):
                matched = []
                cursor = first
                for source_word in source_words:
                    if source_word[0].casefold() == query_words[cursor][0].casefold():
                        matched.append((query_words[cursor], source_word))
                        cursor += 1
                        if cursor == len(query_words):
                            break
                # Keep a contiguous phrase from the unchanged query. Source
                # insertions are local to this clause; a missing query modifier
                # or a digit/operator between its words cannot disappear.
                anchors = {word[0].casefold() for word, _ in matched}
                if len(anchors) < 2 or any(
                    not query_clause[left.end():right.start()].isspace()
                    for (left, _), (right, _) in zip(matched, matched[1:])
                ):
                    continue
                if not any(word[0].casefold() not in anchors for word in source_words):
                    continue
                query_start = query_offset + matched[0][0].start()
                query_end = query_offset + matched[-1][0].end()
                origin = source_offset + clause_offset
                witness = {
                    "kind": "ordinary_body_clause_context_v1",
                    "text": question[query_start:query_end],
                    "query_char_start": query_start, "query_char_end": query_end,
                    "char_start": origin + matched[0][1].start(),
                    "char_end": origin + matched[-1][1].end(),
                    "clause_char_start": origin, "clause_char_end": origin + len(source_clause),
                    "content_tokens": [{
                        "query_char_start": query_offset + query_word.start(),
                        "query_char_end": query_offset + query_word.end(),
                        "char_start": origin + source_word.start(),
                        "char_end": origin + source_word.end(),
                    } for query_word, source_word in matched],
                }
                choices.append(((-len(anchors), query_start, origin), witness))
    return min(choices, key=lambda choice: choice[0])[1] if choices else None


def _technical_block_witness(question: str, block: str, source_offset: int):
    shaped = {value.casefold() for value in documentation_technical_anchors(question)}
    terms = {}
    for literal, start, end in _literal_terms(question):
        value = literal.casefold()
        technical = value in shaped or bool(re.search(r"\w[-_./:\\+]\w", value))
        terms.setdefault(value, (start, end, technical))
    source_terms = {}
    for literal, start, end in _literal_terms(block):
        source_terms.setdefault(literal.casefold(), (start, end))
    matched = []
    for value, (start, end, technical) in terms.items():
        # Each source term is whole: the namespace and member of one composed
        # identifier cannot be counted as two independent body anchors.
        occurrence = source_terms.get(value)
        if occurrence is not None:
            matched.append((value, start, end, *occurrence, technical))
    if len(matched) < 2 or not any(technical for _, _, _, _, _, technical in matched):
        return None
    # An identifier-only table/list is not a statement about that identifier.
    matched_values = {value for value, _, _, _, _, _ in matched}
    remainder = _TERM.sub(
        lambda match: "" if match[0].rstrip(".:").casefold() in matched_values else match[0], block,
    )
    if not re.search(r"[^\W_]", remainder):
        return None
    query_start = min(start for _, start, _, _, _, _ in matched)
    query_end = max(end for _, _, end, _, _, _ in matched)
    if re.search(r"!=|==|<=|>=|[<>]|(?<!\w)-(?!\w)", question[query_start:query_end]):
        return None
    return {
        "kind": "literal_body_block_context_v2",
        "text": question[query_start:query_end],
        "query_char_start": query_start, "query_char_end": query_end,
        "char_start": source_offset + min(start for _, _, _, start, _, _ in matched),
        "char_end": source_offset + max(end for _, _, _, _, end, _ in matched),
        "block_char_start": source_offset, "block_char_end": source_offset + len(block),
        "content_tokens": [{
            "query_char_start": query_start, "query_char_end": query_end,
            "char_start": source_offset + start, "char_end": source_offset + end,
        } for _, query_start, query_end, start, end, _ in matched],
    }


def _policy_valid_body_blocks(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
):
    """Share native receipt, owner and numeric constraints, not topical proof."""
    binding = original_body_discovery_binding(
        question=question, body=evidence_text, candidate=candidate,
    )
    if binding is None:
        return
    evidence = candidate["_reference_evidence"]
    if prepared_owner_rejection(evidence) is not None:
        return
    owner = evidence.get("owner")
    subject_text = (evidence["raw_document"][owner["scope_start"]:owner["scope_end"]]
                    if owner is not None else evidence_text)
    subject_terms = {value.casefold() for value, _, _ in _literal_terms(subject_text)}
    if any(
        not any(value == mention.text.casefold() or (
            value.partition("_")[0] == mention.text.casefold() and value.partition("_")[2]
        ) for value in subject_terms)
        for mention in query_mentions(question)
        if not mention.explicit and mention.syntax_role == "unresolved"
    ):
        return
    numeric_terms = {value for value, _, _ in _literal_terms(question)
                     if any(char.isdigit() for char in value)}
    for offset, block in _body_blocks(evidence_text):
        block_terms = {value for value, _, _ in _literal_terms(block)}
        if not numeric_terms <= block_terms:
            continue
        source_offset = evidence["char_start"] + offset
        yield binding, source_offset, block


def ordinary_body_context_witness(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Recompute a source-local relevance witness after canonical source checks.

    Unresolved names must occur in the current verified structural owner (or
    current body when it has no owner). A bare name may be the first underscore
    namespace segment; this is lexical context, never exact symbol identity or
    a subject relation. A separate body witness remains mandatory. The whole
    question and all answer/edit authority stay unverified.
    """
    for binding, source_offset, block in _policy_valid_body_blocks(
        question=question, evidence_text=evidence_text, candidate=candidate,
    ):
        witness = (_phrase_witness(question, block, source_offset)
                   or _technical_block_witness(question, block, source_offset))
        if witness is not None:
            return {**witness, "native_discovery_binding_sha256": binding}
    return None


def policy_valid_original_candidate_witness(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Experimental source-valid body candidate; relevance remains unassessed.

    Canonical source/window and hard-exact checks belong to the admission caller.
    The host mode does not mint a receipt or relax owner/numeric constraints.
    Structural body content is not support for the question's relation.
    """
    if not policy_candidate_admission_active():
        return None
    for binding, source_offset, block in _policy_valid_body_blocks(
        question=question, evidence_text=evidence_text, candidate=candidate,
    ):
        if not re.search(r"[^\W_]", block):
            continue
        end = source_offset + len(block)
        return {
            "kind": "policy_valid_original_candidate_v1",
            "relevance_unassessed": True,
            "text": candidate["_reference_evidence"]["raw_document"][source_offset:end],
            "char_start": source_offset, "char_end": end,
            "block_char_start": source_offset, "block_char_end": end,
            "native_discovery_binding_sha256": binding,
        }
    return None
