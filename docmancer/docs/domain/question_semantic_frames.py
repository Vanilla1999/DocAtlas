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


@dataclass(frozen=True, slots=True)
class DecisionFrame:
    decision_kind: str
    subject: str
    action: str


@dataclass(frozen=True, slots=True)
class ArgumentValueFrame:
    argument: str
    actor: str
    callee: str


@dataclass(frozen=True, slots=True)
class ContractScopeFrame:
    contract: str
    subject: str
    condition: str


@dataclass(frozen=True, slots=True)
class PurposeBehaviorFrame:
    subject: str
    purpose: str


@dataclass(frozen=True, slots=True)
class BeforeBehaviorFrame:
    subject: str
    action: str


def _entity(value: str) -> str:
    value = clean_phrase(value).strip("`\"'")
    return value[:160] if semantic_tail_is_safe(value, allow_initial_request_head=True) else ""


def match_comparison_frame(question: str) -> ComparisonFrame | None:
    q = clean_phrase(question)
    patterns = (
        r"how\s+does\s+(.+?)\s+differ\s+from\s+(.+)",
        r"what\s+is\s+the\s+difference\s+between\s+(.+?)\s+and\s+(.+)",
        r"(.+?)\s+vs\.?\s+(.+?)[,:]?\s+what\s+differs",
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
        r"where\s+is\s+(.+?)\s+(?:defined|configured)",
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
            r"(?:the\s+)?(.+?)\s+(?:is|becomes|gets)\s+([A-Za-z0-9_.-]+)"
            r"(?:\s+and\s+.+)?",
            condition,
            re.I,
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

    match = re.fullmatch(r"is\s+(.+?)\s+allowed\s+while\s+(.+)", q, re.I)
    if match is not None:
        subject, condition = _entity(match.group(1)), _entity(match.group(2))
        if subject and condition:
            return ConditionFrame(subject, condition, "conditional_outcome")

    match = re.fullmatch(r"when\s+is\s+(.+?)\s+blocked", q, re.I)
    if match is not None:
        subject = _entity(match.group(1))
        if subject:
            return ConditionFrame(subject, None, "blocking_conditions")

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

    match = re.fullmatch(
        r"why\s+are\s+there\s+"
        r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"((?:(?:public\s+)?docs\s+mcp\s+tools?)|(?:docs\s+mcp\s+public\s+tools?))",
        q,
        re.I,
    )
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


def match_decision_frame(question: str) -> DecisionFrame | None:
    match = re.fullmatch(r"which\s+([A-Za-z_][\w.]*)\s+permits\s+(.+?)\s+to\s+(.+)", clean_phrase(question), re.I)
    if match is None:
        return None
    kind, subject, action = (_entity(match.group(i)) for i in range(1, 4))
    return DecisionFrame(kind, subject, action) if kind and subject and action else None


def match_argument_value_frame(question: str) -> ArgumentValueFrame | None:
    match = re.fullmatch(
        r"what\s+([A-Za-z_][\w.]*)\s+value\s+must\s+(.+?)\s+pass\s+to\s+([A-Za-z_][\w.]*)",
        clean_phrase(question), re.I,
    )
    if match is None:
        return None
    argument, actor, callee = (_entity(match.group(i)) for i in range(1, 4))
    return ArgumentValueFrame(argument, actor, callee) if argument and actor and callee else None


def match_contract_scope_frame(question: str) -> ContractScopeFrame | None:
    match = re.fullmatch(
        r"what\s+(?:project\s+)?(.+?\s+contract)\s+applies\s+to\s+(.+?)\s+when\s+(.+)",
        clean_phrase(question), re.I,
    )
    if match is None:
        return None
    contract = _entity(match.group(1))
    contract_words = contract.casefold().split()
    if (
        not 2 <= len(contract_words) <= 5
        or contract_words[-1] != "contract"
        or contract_words[0] in {"what", "which", "project", "system", "generic"}
    ):
        return None
    subject = clean_phrase(match.group(2))
    if re.fullmatch(r"[A-Za-z][\w.-]*(?:\s*,\s*[A-Za-z][\w.-]*)*(?:,?\s+and\s+[A-Za-z][\w.-]*)?", subject, re.I) is None:
        return None
    condition = _entity(match.group(3))
    return ContractScopeFrame(contract, subject, condition) if subject and condition else None


def match_purpose_behavior_frame(question: str) -> PurposeBehaviorFrame | None:
    q = clean_phrase(question)
    match = re.fullmatch(r"what\s+does\s+(.+?)\s+do\s+to\s+(.+)", q, re.I)
    if match is None:
        match = re.fullmatch(r"how\s+does\s+(.+?)\s+determine\s+(.+)", q, re.I)
    if match is None:
        return None
    subject, purpose = _entity(match.group(1)), _entity(match.group(2))
    return PurposeBehaviorFrame(subject, purpose) if subject and purpose else None


def match_before_behavior_frame(question: str) -> BeforeBehaviorFrame | None:
    match = re.fullmatch(r"what\s+does\s+(.+?)\s+do\s+before\s+(.+)", clean_phrase(question), re.I)
    if match is None:
        return None
    subject, action = _entity(match.group(1)), _entity(match.group(2))
    return BeforeBehaviorFrame(subject, action) if subject and action else None


__all__ = [
    "ArgumentValueFrame", "BeforeBehaviorFrame", "ComparisonFrame", "ConditionFrame",
    "ContractScopeFrame", "DecisionFrame", "LocationFrame", "PremiseFrame", "PurposeBehaviorFrame",
    "match_argument_value_frame", "match_before_behavior_frame", "match_contract_scope_frame",
    "match_comparison_frame", "match_condition_frame", "match_location_frame",
    "match_decision_frame", "match_premise_frame", "match_purpose_behavior_frame",
]
