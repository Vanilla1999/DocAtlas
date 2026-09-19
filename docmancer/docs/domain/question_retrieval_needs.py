"""Question-derived retrieval needs; never answer values or proof authorization."""
from __future__ import annotations

from dataclasses import dataclass
import re

from docmancer.docs.domain.question_frame_core import split_question_clause_spans
from docmancer.docs.domain.question_semantic_frames import match_comparison_frame
from docmancer.docs.domain.query_terms import documentation_technical_anchors, query_constraint_roles

@dataclass(frozen=True, slots=True)
class RetrievalNeed:
    need_id: str
    query_span_start: int
    query_span_end: int
    query_span_text: str
    subject: str
    relation: str
    context: str
    hard_exact: tuple[str, ...]


def _need_relation(text: str) -> str:
    value = " ".join(text.casefold().strip(" ?!.,:").split())
    if value == "why" or value.startswith("why "):
        return "reason"
    if re.search(r"\bdefault\b", value):
        return "default"
    if re.search(r"\bexception\b|\braises?\b|\braised\b", value):
        return "exception"
    if value.startswith("how "):
        return "mechanism"
    if re.search(r"\brequired\b|\brequirement\b", value):
        return "requirement"
    if re.search(r"\bconfiguration\b|\bconfigured\b", value):
        return "configuration"
    if re.search(r"\bbehavior\b|\bbehaviour\b|\bhappens?\b", value):
        return "behavior"
    if re.match(r"^(?:can|is|are|should|does|do)\b", value):
        return "restriction"
    return "requested_part"


_RELATION_NOUNS = frozenset({
    "behavior", "behaviour", "configuration", "default", "escape", "exception",
    "hatch", "reason", "requirement", "result", "value",
})


def _need_subject(text: str) -> str:
    # Prefer explicit grammatical subjects before lexical/technical anchors.
    # This covers lowercase actors and hyphenated settings that are not exact
    # technical identities by themselves.
    embedded_actor = re.match(
        r"\s*which\b.+?\bdoes\s+([A-Za-z][A-Za-z0-9_.-]{1,80})\b", text, re.I,
    )
    if embedded_actor is not None:
        candidate = embedded_actor.group(1)
        if candidate.casefold() not in _RELATION_NOUNS:
            return candidate
    happens_to = re.match(
        r"\s*what\s+happens?\s+to\s+(?:the\s+)?([A-Za-z][A-Za-z0-9_.-]{1,80})\b",
        text, re.I,
    )
    if happens_to is not None:
        candidate = happens_to.group(1)
        if candidate.casefold() not in _RELATION_NOUNS:
            return candidate
    # An elided clause such as "and what is the default?" has no new subject;
    # it inherits the prior concrete subject instead of treating "default" as one.
    match = re.match(
        r"\s*(?:how\s+does|what\s+is|what\s+does|can|is|are|does|do)\s+"
        r"(?:the\s+)?([A-Za-z][A-Za-z0-9_.-]{1,80})\b",
        text,
        re.I,
    )
    if match is not None:
        candidate = match.group(1)
        if candidate.casefold() not in {
            "a", "an", "the", "this", "that", "which", "what", *_RELATION_NOUNS,
        }:
            return candidate
    anchors = documentation_technical_anchors(text)
    return anchors[0] if anchors and anchors[0].casefold() not in _RELATION_NOUNS else ""


def _locate_need_span(question: str, text: str, *, start: int = 0) -> tuple[int, int]:
    match = re.search(re.escape(text), question[start:], re.I)
    if match is None:
        return start, min(len(question), start + len(text))
    return start + match.start(), start + match.end()


def retrieval_needs(question: str) -> tuple[RetrievalNeed, ...]:
    """Return bounded question-derived retrieval needs without answer values."""
    raw = str(question or "")
    if not raw.strip():
        return ()

    comparison = match_comparison_frame(raw)
    if comparison is not None:
        needs: list[RetrievalNeed] = []
        cursor = 0
        for index, subject in enumerate((comparison.left, comparison.right), start=1):
            start, end = _locate_need_span(raw, subject, start=cursor)
            cursor = end
            span_text = raw[start:end]
            needs.append(RetrievalNeed(
                need_id=f"need-{index}",
                query_span_start=start,
                query_span_end=end,
                query_span_text=span_text,
                subject=subject,
                relation="comparison_side",
                context=comparison.context or "",
                hard_exact=query_constraint_roles(span_text).hard_exact,
            ))
        return tuple(needs)

    clauses = split_question_clause_spans(raw)
    if not clauses:
        return ()

    shared_context = ""
    working = list(clauses)
    if len(working) > 1 and re.match(r"\s*(?:if|when|unless)\b", working[0].text, re.I):
        shared_context = working.pop(0).text.strip(" ,")

    if not working:
        return ()

    explicit_subjects = [_need_subject(clause.text) for clause in working]
    shared_subject = next((value for value in explicit_subjects if value), "")

    # One unsplit clause is one need at most. This deliberately avoids treating
    # ordinary "and"/"or" inside names or predicates as mandatory facets.
    needs: list[RetrievalNeed] = []
    for index, clause in enumerate(working, start=1):
        explicit_subject = explicit_subjects[index - 1]
        subject = explicit_subject or shared_subject
        relation = _need_relation(clause.text)
        if relation == "requested_part" and len(working) == 1:
            # Keep a single bounded need only when a subject is actually visible;
            # otherwise the existing root/unresolved path remains authoritative.
            if not subject:
                continue
        context_parts = [shared_context] if shared_context else []
        if not explicit_subject and index > 1:
            # Elided dependent clauses ("which exception?", "what is the default?")
            # inherit the nearest earlier clause that named the shared subject.
            for previous_index in range(index - 2, -1, -1):
                if explicit_subjects[previous_index]:
                    context_parts.append(working[previous_index].text.strip(" ,"))
                    break
        context = " ".join(dict.fromkeys(value for value in context_parts if value))
        span_text = clause.text
        roles = query_constraint_roles(" ".join(value for value in (context, span_text) if value))
        needs.append(RetrievalNeed(
            need_id=f"need-{index}",
            query_span_start=clause.start,
            query_span_end=clause.end,
            query_span_text=span_text,
            subject=subject,
            relation=relation,
            context=context,
            hard_exact=roles.hard_exact,
        ))
    return tuple(needs)


__all__ = ["RetrievalNeed", "retrieval_needs"]
