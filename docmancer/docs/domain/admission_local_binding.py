"""Bounded default-property bindings over current answer-unit bytes, without I/O.

This is a deliberately small grammar, not page-level subject co-occurrence.
Unknown question forms are left to the existing strict qualification path.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .answer_units import AnswerUnit, extract_answer_units, best_local_proof, _DURATION_RE
from .technical_tokens import technical_term_pattern
from .project_answer_contract import ProofObligation

_WORD = r"[A-Za-z][A-Za-z0-9_-]*"


def default_property(query: Mapping[str, Any]) -> str | None:
    """Keep compound properties; stop only at grammatical clause boundaries."""
    question = str(query.get("text") or "")
    match = re.search(r"\bdefault\s+(.+)", question, re.I)
    if match is None:
        return None
    phrase = re.split(
        r"[,;:?!]|\b(?:of|for|is|are|when|if|which|rather)\b", match[1],
        maxsplit=1, flags=re.I,
    )[0].strip(" .")
    # A measurement descriptor after an already duration-valued property does
    # not rename that property ("timeout duration", "retry delay duration").
    # Do not strip "duration" from properties such as "lease duration".
    phrase = re.sub(r"\b(timeout|delay)\s+duration$", r"\1", phrase, flags=re.I)
    words = phrase.split()
    if any(word.casefold() in {"and", "or", "и", "или"} for word in words):
        return None  # uncompiled compound properties are not a single witness
    if not 1 <= len(words) <= 4 or any(re.fullmatch(_WORD, w) is None for w in words):
        return None
    return " ".join(words)


def _subject_pattern(subject: str) -> str:
    return technical_term_pattern(subject, exact=True)


def _property_pattern(attribute: str, *, plural: bool = False) -> str:
    words = attribute.split()
    parts = [re.escape(word) for word in words]
    if plural and not words[-1].endswith("s"):
        parts[-1] += "s?"
    return r"(?<![\w-])" + r"\s+".join(parts) + r"(?![\w-])"


def _assignment(attribute: str, subject: str | None) -> str:
    prop = _property_pattern(attribute)
    name = _subject_pattern(subject) if subject else ""
    # An anonymous assignment is allowed only with a raw owning heading.
    if name:
        owner = rf"(?:{name}(?:['’]s)?\s+(?:the\s+)?default\s+{prop}|(?:the\s+)?default\s+{prop}\s+(?:of|for)\s+{name})"
    else:
        owner = rf"(?:the\s+)?default\s+{prop}"
    return rf"^\s*{owner}\s*(?:is\b|=|:)\s*(?P<value>\S.*)$"


def _single_clause(text: str) -> bool:
    # Do not let an unrelated second clause provide the value to the first.
    return not re.search(r"[;\n]|[.!?]\s+\S|\b(?:but|whereas|while|and)\b", text, re.I)


_STATE = re.compile(r"\b(?:when|if)\s+([\w -]{1,80}?)\s+is\s+(not\s+enabled|disabled|enabled)\b", re.I)


def _condition(text: str) -> tuple[str, str] | None:
    match = _STATE.search(text)
    if match is None:
        return None
    entity = " ".join(match[1].casefold().split())
    state = " ".join(match[2].casefold().split())
    return entity, "disabled" if state == "not enabled" else state


def _conditioned_clause(text: str, required: tuple[str, str] | None) -> str | None:
    condition = _condition(text)
    if condition != required:
        return None
    if condition is not None:
        match = _STATE.match(text)
        if match is None or not text[match.end():].lstrip().startswith(","):
            return None
        text = text[match.end():].lstrip()[1:].lstrip()
    if re.search(r"\b(?:when|if|unless|except|only|provided)\b", text, re.I):
        return None
    return text


def _value_is_local(match: re.Match[str] | None, attribute: str) -> bool:
    if match is None:
        return False
    value = match["value"].rstrip(" .")
    if re.search(r"\b(?:timeout|duration|delay)\b", attribute, re.I):
        duration = _DURATION_RE.match(value)
        return bool(duration and value[duration.end():].strip() in {"", "of inactivity"})
    # A scalar text/number value, not a clause that happens to mention a number.
    return re.fullmatch(r"(?:`[^`\n]+`|[\w.-]+)", value) is not None and value.casefold() not in {
        "unknown", "undocumented", "unspecified", "unavailable", "undefined",
    }


def _discourse_value_is_local(answer: str, attribute: str) -> bool:
    """A linked default value or timeout action, not arbitrary following prose."""
    value = re.match(
        r"(?:the|its)\s+default\s+(?:behavior|behaviour|value|setting)\s+is\s+(?P<value>.+)$",
        " ".join(answer.split()), re.I,
    )
    if _value_is_local(value, attribute):
        return True
    if value is None or not re.search(r"\btimeout\b", attribute, re.I):
        return False
    # Explicit timeout action. Its literal comes from the body; no expected
    # exception name, library identity or answer value is supplied by the query.
    action = re.fullmatch(
        r"to\s+(?:raise|throw)\s+(?:(?:a|an)\s+)?`[^`\n]+`\s+after\s+(?P<duration>.+)",
        value["value"].rstrip(" ."), re.I,
    )
    if action is None:
        return False
    duration = _DURATION_RE.match(action["duration"])
    return bool(duration and action["duration"][duration.end():].strip() in {
        "", "of inactivity", "of network inactivity",
    })


def bound_default_units(
    query: Mapping[str, Any], text: str,
) -> tuple[AnswerUnit, ...] | None:
    """Return current subject/property-bound units; None means unknown grammar.

    Subject authority never comes from a title/path/verified=True dictionary.
    Raw heading and narrow, explicit anaphoric discourse are local dependencies.
    Value/default proof is still supplied by the existing ProofObligation helper.
    """
    subject = str(query.get("need_subject") or "").strip()
    attribute = default_property(query)
    if not subject or not attribute:
        return None
    direct = re.compile(_assignment(attribute, subject), re.I)
    anonymous = re.compile(_assignment(attribute, None), re.I)
    question = str(query.get("text") or "")
    required = _condition(question)
    condition_match = _STATE.search(question)
    if condition_match is not None and question[condition_match.end():].strip(" ?.!"):
        return None  # do not discard an unparsed applicability constraint
    if required is None and re.search(r"\b(?:when|if|unless|except|only|provided)\b", str(query.get("text") or ""), re.I):
        return None  # unsupported condition is not a new typed permission
    found: list[AnswerUnit] = []
    for unit in extract_answer_units(text, include_soft_wrapped_prose=True):
        if not unit.proposition:
            continue
        body = unit.text.strip()
        if unit.kind in {"sentence", "paragraph_sentence", "key_value"}:
            # Soft wrapping is layout, not a second proposition.
            line = _conditioned_clause(" ".join(body.split()), required)
            if line and _single_clause(line) and _value_is_local(direct.search(line), attribute):
                found.append(unit)
        elif unit.kind == "heading_context":
            heading, _, content = body.partition("\n")
            owner = heading.lstrip("#").strip().strip("`")
            content = _conditioned_clause(" ".join(content.split()), required)
            if (owner.casefold() == subject.casefold() and content and _single_clause(content)
                    and _value_is_local(anonymous.search(content) or direct.search(content), attribute)):
                found.append(unit)
        elif unit.kind == "unit_group":
            # A single explicit property-setting clause followed immediately by
            # its default behavior. No heading/other owner/conjunction can lend
            # its identity or value through this limited anaphora production.
            if required is not None:
                continue
            discourse_attribute = re.sub(r"\s+(?:behavior|behaviour)$", "", attribute, flags=re.I)
            context = re.match(
                rf"^\s*{_subject_pattern(subject)}\s+"
                rf"(?:(?:is|are)\s+(?:careful|configured|designed|intended)\s+to\s+)?"
                rf"(?:enforces?|uses?|sets?|configures?)\s+"
                rf"{_property_pattern(discourse_attribute, plural=True)}"
                rf"(?:\s+everywhere)?(?:\s+by\s+default)?\.\s+"
                rf"(?P<answer>(?:the|its)\s+default\s+(?:behavior|behaviour|value|setting)\s+is\s+.+)$",
                " ".join(body.split()), re.I,
            )
            if (context is not None and _single_clause(" ".join(context["answer"].split()))
                    and _discourse_value_is_local(context["answer"], attribute)):
                found.append(unit)
    return tuple(found)


def default_local_witness(query: Mapping[str, Any], text: str
                          ) -> tuple[bool | None, tuple[tuple[int, int], ...]]:
    """Reuse the existing value/default primitive only after local binding."""
    units = bound_default_units(query, text)
    if units is None:
        return None, ()
    attribute = default_property(query) or ""
    value_kind = "duration" if re.search(r"\b(?:timeout|duration|delay)\b", attribute, re.I) else "text"
    obligation = ProofObligation(
        obligation_id=str(query.get("query_id") or "retrieval-need"),
        kind="exact_fact", subject=str(query.get("need_subject") or ""),
        attribute="default", value_kind=value_kind, mandatory=False,
    )
    # Subject/title/path metadata is deliberately unavailable to this primitive.
    match = best_local_proof(obligation, units)
    if match is None:
        return False, ()
    unit = match[0]
    if unit.char_start is None or unit.char_end is None:
        return False, ()
    return True, ((unit.char_start, unit.char_end),)


__all__ = ["bound_default_units", "default_property", "default_local_witness"]
