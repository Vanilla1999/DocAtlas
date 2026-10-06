"""Shared DTO types, bounds and literal parsing; no question-to-answer tables."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from docmancer.docs.domain.question_plan import QuestionPlan
from docmancer.docs.domain.technical_terms import (
    TechnicalTerm, TechnicalTermKind, coerce_technical_term, extract_technical_terms,
)
from docmancer.docs.domain.canonical import canonical_hash
from docmancer.docs.domain.query_terms import documentation_exact_terms as extract_exact_terms


PROJECT_ANSWER_CONTRACT_SCHEMA = "project-answer-contract-v3"
PROJECT_ANSWER_CONTRACT_SCHEMA_V4 = "project-answer-contract-v4"
PROJECT_ANSWER_CONTRACT_SCHEMA_V2 = "project-answer-contract-v2"
MAX_RETRIEVAL_HINTS = 24
MAX_CONCEPT_QUERIES = 4
MAX_PROOF_OBLIGATIONS = 12
MAX_SUBJECTS = 12
MAX_CONTRACT_TEXT = 160

ObligationKind = Literal[
    "definition", "attribute", "inventory", "status", "relation",
    "comparison", "behavior", "usage", "workflow", "exact_fact",
    "command", "location", "purpose", "effect",
]
ValueKind = Literal[
    "text", "version_range", "number", "duration", "identifier_list",
    "status", "boolean", "path", "code", "call_expression",
]
ResponseMode = Literal[
    "value", "count", "names", "count_and_names", "call", "path", "workflow", "purpose",
]
LifecycleIntent = Literal["current", "historical", "either"]

# Technical source-spelling extraction for the compatibility helper only.
_IDENTIFIER_RE = re.compile(
    r"`([^`\n]{2,120})`|\b([A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)+)\b"
    r"|\b([A-Za-z][A-Za-z0-9_]*_[A-Za-z0-9_]+)\b"
    r"|\b([A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+)\b"
)

# General numeric parsing is retained, not used to synthesize an obligation or
# expected answer. The historical helper still enforces the cardinality bound.
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
}


__all__ = [name for name in globals() if not name.startswith('__')]
