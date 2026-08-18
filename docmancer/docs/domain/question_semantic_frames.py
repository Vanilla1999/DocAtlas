"""Reusable bounded semantic frames for QuestionPlan v5.

The matchers in this module only recognize complete question surfaces. They
never create proof obligations; QuestionPlan owns that translation.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from docmancer.docs.domain.question_frame_core import clean_phrase, semantic_tail_is_safe


@dataclass(frozen=True, slots=True)
class ComparisonFrame:
    left: str
    right: str


@dataclass(frozen=True, slots=True)
class LocationFrame:
    subject: str


@dataclass(frozen=True, slots=True)
class ConditionFrame:
    subject: str
    condition: str | None
    relation: str


@dataclass(frozen=True, slots=True)
class PremiseFrame:
    subject: str
    target: str
    relation: str
    expected_value: str | None = None


def _entity(value: str) -> str:
    value = clean_phrase(value).strip("`\"'")
    return value[:160] if semantic_tail_is_safe(value, allow_initial_request_head=True) else ""


def match_comparison_frame(question: str) -> ComparisonFrame | None:
    q = clean_phrase(question)
    patterns = (
        r"how\s+does\s+(.+?)\s+differ\s+from\s+(.+)",
        r"compare\s+(.+?)\s+(?:with|to|and)\s+(.+)",
        r"чем\s+(.+?)\s+отличается\s+от\s+(.+)",
        r"сравни\s+(.+?)\s+(?:с|и)\s+(.+)",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, q, re.I)
        if match is None:
            continue
        left, right = _entity(match.group(1)), _entity(match.group(2))
        if left and right and left.casefold() != right.casefold():
            return ComparisonFrame(left, right)
    return None


def match_location_frame(question: str) -> LocationFrame | None:
    q = clean_phrase(question)
    patterns = (
        r"where\s+is\s+(.+?)\s+documented",
        r"which\s+file\s+(?:documents|describes|defines)\s+(.+)",
        r"where\s+can\s+i\s+find\s+(.+)",
        r"где\s+документирован[аоы]?\s+(.+)",
        r"в\s+каком\s+файле\s+(?:описан[аоы]?|определен[аоы]?)\s+(.+)",
        r"где\s+(?:можно\s+)?найти\s+(.+)",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, q, re.I)
        if match is not None:
            subject = _entity(match.group(1))
            if subject:
                return LocationFrame(subject)
    return None


def match_condition_frame(question: str) -> ConditionFrame | None:
    q = clean_phrase(question)

    match = re.fullmatch(r"what\s+happens\s+(?:when|if)\s+(.+)", q, re.I)
    if match is not None:
        condition = _entity(match.group(1))
        subject_match = re.fullmatch(
            r"(?:the\s+)?(.+?)\s+(?:is|becomes|gets)\s+([A-Za-z0-9_.-]+)", condition, re.I
        )
        if condition and subject_match is not None:
            subject = _entity(subject_match.group(1))
            if subject:
                return ConditionFrame(subject, condition, "conditional_outcome")

    match = re.fullmatch(r"can\s+(.+?)\s+run\s+while\s+(.+)", q, re.I)
    if match is not None:
        subject, condition = _entity(match.group(1)), _entity(match.group(2))
        if subject and condition:
            return ConditionFrame(subject, condition, "conditional_outcome")

    match = re.fullmatch(r"under\s+which\s+conditions\s+is\s+(.+?)\s+blocked", q, re.I)
    if match is not None:
        subject = _entity(match.group(1))
        if subject:
            return ConditionFrame(subject, None, "blocking_conditions")

    match = re.fullmatch(r"что\s+происходит[, ]+(?:когда|если)\s+(.+)", q, re.I)
    if match is not None:
        condition = _entity(match.group(1))
        subject_match = re.fullmatch(r"(.+?)\s+(?:устарел[ао]?|недоступен|активен|заблокирован)", condition, re.I)
        if condition and subject_match is not None:
            subject = _entity(subject_match.group(1))
            if subject:
                return ConditionFrame(subject, condition, "conditional_outcome")

    match = re.fullmatch(r"можно\s+ли\s+запустить\s+(.+?)[, ]+пока\s+(.+)", q, re.I)
    if match is not None:
        subject, condition = _entity(match.group(1)), _entity(match.group(2))
        if subject and condition:
            return ConditionFrame(subject, condition, "conditional_outcome")

    match = re.fullmatch(r"при\s+каких\s+условиях\s+(.+?)\s+блокируется", q, re.I)
    if match is not None:
        subject = _entity(match.group(1))
        if subject:
            return ConditionFrame(subject, None, "blocking_conditions")
    return None


def match_premise_frame(question: str) -> PremiseFrame | None:
    q = clean_phrase(question)

    match = re.fullmatch(
        r"why\s+does\s+(.+?)\s+(always|never)\s+"
        r"(delete|remove|preserve|retry|bypass)\s+(.+)",
        q,
        re.I,
    )
    if match is not None:
        subject = _entity(match.group(1))
        target = _entity(f"{match.group(3)} {match.group(4)}")
        if subject and target:
            return PremiseFrame(subject, target, "premise_check", match.group(2).casefold())

    match = re.fullmatch(r"why\s+are\s+there\s+(\d{1,2}|one|two|three|four|five)\s+(.+)", q, re.I)
    if match is not None:
        target = _entity(match.group(2))
        if target:
            return PremiseFrame("Docs MCP", target, "premise_cardinality", match.group(1).casefold())

    match = re.fullmatch(
        r"почему\s+(.+?)\s+(всегда|никогда)\s+"
        r"(удаляет|сохраняет|повторяет|обходит)\s+(.+)",
        q,
        re.I,
    )
    if match is not None:
        subject = _entity(match.group(1))
        target = _entity(f"{match.group(3)} {match.group(4)}")
        if subject and target:
            expected = "always" if match.group(2).casefold() == "всегда" else "never"
            return PremiseFrame(subject, target, "premise_check", expected)
    return None


__all__ = [
    "ComparisonFrame", "ConditionFrame", "LocationFrame", "PremiseFrame",
    "match_comparison_frame", "match_condition_frame", "match_location_frame",
    "match_premise_frame",
]
