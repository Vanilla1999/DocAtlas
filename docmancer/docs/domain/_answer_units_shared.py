"""Structural answer-unit grammar; compatibility patterns confer no meaning."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable, Mapping

from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.question_plan_proof import (
    behavior_proof as planned_behavior_proof,
    usage_proof as planned_usage_proof,
    workflow_proof as planned_workflow_proof,
)
from docmancer.docs.domain.governance_value_proof import (
    relation_proof as planned_relation_proof,
)
from docmancer.docs.domain.technical_terms import (
    TechnicalTerm,
    canonical_technical_term,
    coerce_technical_term,
    controlled_noun_forms,
    technical_term_present,
    technical_term_spans,
    term_sequence_present,
    term_sequence_spans,
)


ANSWER_UNIT_SCHEMA = "answer-unit-v2"
MAX_ANSWER_UNITS = 64
MAX_ANSWER_UNIT_CHARS = 1_500

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(\S.*)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
_KEY_VALUE_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?[`\"']?([A-Za-zА-Яа-яЁё_][\w .:/-]{0,80})[`\"']?\s*[:=]\s*(\S.{0,1000})$"
)
_UNBOUNDED_KEY_VALUE_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?[`\"']?([A-Za-zА-Яа-яЁё_][\w .:/-]*)[`\"']?\s*[:=]\s*(\S.*)$"
)
_CODE_DECL_RE = re.compile(
    r"^\s*(?:class|def|async\s+def|function|interface|enum|type|const|let|var|final|"
    r"public|private|protected|static|fun|data\s+class|struct|trait|impl|fn|package|module|"
    r"[A-Za-z_][A-Za-z0-9_]*\s*=)\b.*$",
    re.I,
)
# Dotted identifiers/versions remain intact: punctuation is a boundary only
# before whitespace/end. These patterns segment source, never certify meaning.
_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)")
_PARAGRAPH_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.S)
_IDENTIFIER_RE = re.compile(r"`([^`\n]{2,120})`|\b([A-Za-z_][A-Za-z0-9_.:-]{2,})\b")

# Negative ABI only: every unknown prose input retains the veto uniformly.
_NEGATION_RE = re.compile(r"")

# Keep existing exported symbols/imports without keeping NL detectors. In
# particular admission_local_binding imports _DURATION_RE; it must fail closed
# until its caller/typed-duration contract is audited separately.
_VERSION_VALUE_RE = re.compile(r"(?!)")
_DURATION_RE = re.compile(r"(?!)")
_USAGE_RE = re.compile(r"(?!)")
_CONTRAST_RE = re.compile(r"(?!)")
_TOOL_WORD_RE = re.compile(r"(?!)")
_TOOL_INVENTORY_ANCHOR_RE = re.compile(r"(?!)")
_EXPLICIT_COUNT_RE = re.compile(r"(?!)")
_PURPOSE_RE = re.compile(r"(?!)")
_PURPOSE_COPULA_RE = re.compile(r"(?!)")
_DELETE_PREDICATE_RE = re.compile(r"(?!)")
_PRESERVE_PREDICATE_RE = re.compile(r"(?!)")
_NEGATED_DELETE_RE = re.compile(r"(?!)")
_ARCH_COMPONENT_RE = re.compile(r"(?!)")
_ARCH_RELATION_RE = re.compile(r"(?!)")
_NUMBER_WORD_VALUES = {}


__all__ = [n for n in globals() if not n.startswith('__')]
