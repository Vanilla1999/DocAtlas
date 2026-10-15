"""Explicit legacy frame DTOs; natural-language matchers fail closed."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComparisonFrame:
    left: str
    right: str
    context: str | None = None


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
    return ""


def match_comparison_frame(question: str) -> ComparisonFrame | None:
    return None


def match_location_frame(question: str) -> LocationFrame | None:
    return None


def match_condition_frame(question: str) -> ConditionFrame | None:
    return None


def match_premise_frame(question: str) -> PremiseFrame | None:
    return None


def match_decision_frame(question: str) -> DecisionFrame | None:
    return None


def match_argument_value_frame(question: str) -> ArgumentValueFrame | None:
    return None


def match_contract_scope_frame(question: str) -> ContractScopeFrame | None:
    return None


def match_purpose_behavior_frame(question: str) -> PurposeBehaviorFrame | None:
    return None


def match_before_behavior_frame(question: str) -> BeforeBehaviorFrame | None:
    return None


__all__ = [
    "ArgumentValueFrame", "BeforeBehaviorFrame", "ComparisonFrame", "ConditionFrame",
    "ContractScopeFrame", "DecisionFrame", "LocationFrame", "PremiseFrame", "PurposeBehaviorFrame",
    "match_argument_value_frame", "match_before_behavior_frame", "match_contract_scope_frame",
    "match_comparison_frame", "match_condition_frame", "match_location_frame",
    "match_decision_frame", "match_premise_frame", "match_purpose_behavior_frame",
]
