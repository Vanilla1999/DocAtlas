"""Versioned ordinary partial lexical context; never whole-query qualification.

Only a contiguous original-query span can identify a source clause. The general
English function-word categories below are not topic aliases or inferred roles.
Case folding matches literal words; no stemming, synonyms or generated query is
used. Every delivered window still needs a private same-call native receipt.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .evidence_qualification import _relation_units
from .original_body_discovery import original_body_discovery_binding
from .query_reference_binding import query_mentions
from .query_terms import documentation_technical_anchors, query_constraint_roles


# English question words, auxiliaries, determiners, personal pronouns, basic
# connectors/prepositions. Temporal, conditional and negative content words
# (before, after, until, unless, without, not, never, only, ...) stay meaningful.
_FUNCTION_WORDS = frozenset("""
what which who whom whose where when why how
am are is was were be been being do does did have has had
can could may might must shall should will would
a an the this that these those
i me my mine we us our ours you your yours he him his she her hers
it its they them their theirs
and or but of for to from in on at by with as about
""".split())
_WORD = re.compile(r"(?<!\w)[^\W\d_]+(?:[-'][^\W\d_]+)*(?!\w)")
# Conservative lexical clause boundaries, not a semantic parse. Do not join
# sentences, punctuation-delimited clauses, list cells or coordinating clauses.
_BOUNDARY = re.compile(r"[.!?;:,|–—]+|(?<!\w)-|-(?!\w)|\b(?:and|but|or|yet|whereas|although|though)\b", re.I)


def _clauses(text: str):
    cursor = 0
    for boundary in _BOUNDARY.finditer(text):
        yield cursor, text[cursor:boundary.start()]
        cursor = boundary.end()
    yield cursor, text[cursor:]


def _content_words(text: str):
    return [match for match in _WORD.finditer(text) if match[0].casefold() not in _FUNCTION_WORDS]


def _prose_clauses(body: str):
    paragraph_start = 0
    for boundary in re.finditer(r"(?:\r?\n)[ \t]*(?:\r?\n)|\Z", body):
        unit_start = paragraph_start
        unit = body[unit_start:boundary.start()]
        paragraph_start = boundary.end()
        normalized = " ".join(unit.split())
        # The complete raw paragraph must be plain substantive prose. A heading,
        # link, table/list label or code fence cannot supply phrase evidence.
        # Whitespace wrapping and inline emphasis preserve the same raw tokens.
        if not normalized or _relation_units(unit) != (normalized,):
            continue
        for clause_start, clause in _clauses(unit):
            if clause.strip():
                yield unit_start + clause_start, clause


def ordinary_body_context_witness(
    *, question: str, evidence_text: str, candidate: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return one exact lexical witness, without resolving the whole question.

    A query content word between the two endpoints cannot be omitted. Source
    insertions are allowed inside one clause. At least two distinct content
    words and substantive content outside the matched words exclude a repeated
    label. This intentionally does not certify every ordinary modifier outside
    the chosen span; the full query remains missing and all authority false.
    """
    # Unsupported literal syntax is a strict-lane boundary, not a token to
    # discard. In particular digits/operators/quotes cannot disappear between
    # two words and turn "pressure 7 packets" into a pressure/packets witness.
    if (any(not (char.isalpha() or char.isspace() or char in ".?!,;:-–—") for char in question)
        or re.search(r"(?<![^\W\d_])-|-(?![^\W\d_])", question)
        or query_mentions(question) or documentation_technical_anchors(question)
        or query_constraint_roles(question).hard_exact):
        return None
    binding = original_body_discovery_binding(
        question=question, body=evidence_text, candidate=candidate,
    )
    if binding is None:
        return None
    evidence = candidate["_reference_evidence"]
    window_start = evidence["char_start"]
    choices = []
    for query_offset, query_clause in _clauses(question):
        query_words = _content_words(query_clause)
        for source_offset, source_clause in _prose_clauses(evidence_text):
            source_words = _content_words(source_clause)
            for first in range(len(query_words) - 1):
                matched = []
                cursor = first
                for source_word in source_words:
                    if source_word[0].casefold() == query_words[cursor][0].casefold():
                        matched.append((query_words[cursor], source_word))
                        cursor += 1
                        if cursor == len(query_words):
                            break
                values = {query_word[0].casefold() for query_word, _ in matched}
                if (len(values) < 2
                    or not any(word[0].casefold() not in values for word in source_words)):
                    continue
                query_start = query_offset + matched[0][0].start()
                query_end = query_offset + matched[-1][0].end()
                source_start = window_start + source_offset + matched[0][1].start()
                source_end = window_start + source_offset + matched[-1][1].end()
                witness = {
                    "kind": "ordinary_body_clause_context_v1",
                    "text": question[query_start:query_end],
                    "query_char_start": query_start, "query_char_end": query_end,
                    "char_start": source_start, "char_end": source_end,
                    "clause_char_start": window_start + source_offset,
                    "clause_char_end": window_start + source_offset + len(source_clause),
                    "native_discovery_binding_sha256": binding,
                    "content_tokens": [{
                        "query_char_start": query_offset + query_word.start(),
                        "query_char_end": query_offset + query_word.end(),
                        "char_start": window_start + source_offset + source_word.start(),
                        "char_end": window_start + source_offset + source_word.end(),
                    } for query_word, source_word in matched],
                }
                choices.append(((-len(matched), query_start, source_start), witness))
    return min(choices, key=lambda choice: choice[0])[1] if choices else None
