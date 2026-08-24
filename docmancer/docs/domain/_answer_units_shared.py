"""Bounded answer-unit extraction and typed local proof checks."""
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
_CODE_DECL_RE = re.compile(
    r"^\s*(?:class|def|async\s+def|function|interface|enum|type|const|let|var|final|"
    r"public|private|protected|static|fun|data\s+class|struct|trait|impl|fn|package|module|"
    r"[A-Za-z_][A-Za-z0-9_]*\s*=)\b.*$",
    re.I,
)
# Do not split dotted identifiers or versions (``mcp.server``, ``3.11``).
# A sentence boundary is punctuation followed by whitespace/end, not every dot.
_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)")
_PARAGRAPH_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.S)
_IDENTIFIER_RE = re.compile(r"`([^`\n]{2,120})`|\b([A-Za-z_][A-Za-z0-9_.:-]{2,})\b")
_VERSION_VALUE_RE = re.compile(
    r"(?<!\w)(?:[~^<>=!]{0,2}\s*)?v?\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z.-]+)?(?:\s*(?:\+|or\s+newer))?(?!\w)",
    re.I,
)
_DURATION_RE = re.compile(
    r"(?<!\w)\d+(?:\.\d+)?\s*(?:ms|msec|milliseconds?|s|sec|seconds?|m|min|minutes?|h|hours?|мс|сек(?:унд[а-я]*)?|мин(?:ут[а-я]*)?|час(?:а|ов)?)\b",
    re.I,
)
_STATUS_VALUE_RE = re.compile(
    r"\b(?:accepted|completed|done|active|in\s+progress|blocked|failed|cancelled|canceled|"
    r"ready|partial|inconclusive|superseded|deprecated|принят[а-я]*|завершен[а-я]*|готов[а-я]*|"
    r"активн[а-я]*|в\s+работе|заблокирован[а-я]*|отменен[а-я]*|неубедител[а-я]*)\b",
    re.I,
)
_COPULA_RE = re.compile(
    r"\b(?:is|are|means|refers\s+to|provides?|represents?|defines?|serves?\s+as|"
    r"это|является|представляет|означает|служит|предоставляет)\b",
    re.I,
)
_BEHAVIOR_RE = re.compile(
    r"\b(?:returns?|reports?|shows?|reads?|writes?|loads?|indexes?|retrieves?|selects?|"
    r"validates?|handles?|processes?|dispatches?|routes?|creates?|updates?|deletes?|use(?:s|d)?|exposes?|"
    r"invokes?|supplies?|calls?|replaces?|preserves?|keeps?|sets?|configures?|requires?|governs?|"
    r"возвращает|показывает|сообщает|читает|записывает|индексирует|извлекает|выбирает|"
    r"проверяет|обрабатывает|маршрутизирует|создает|обновляет|удаляет)\b",
    re.I,
)
_USAGE_RE = re.compile(
    r"\b(?:use[sd]?|using|should\s+be\s+used|when|recommended|reserved\s+for|"
    r"использ(?:овать|уется|ован)|применя(?:ть|ется)|когда|рекомендуется)\b",
    re.I,
)
_SEQUENCE_RE = re.compile(
    r"\b(?:first|then|next|after|before|finally|step\s*\d+|->|→|"
    r"сначала|затем|далее|после|перед|наконец|шаг\s*\d+)\b",
    re.I,
)
_CONTRAST_RE = re.compile(
    r"\b(?:whereas|while|unlike|instead\s+of|but|compared\s+with|versus|vs\.?|"
    r"тогда\s+как|в\s+отличие|вместо|но|по\s+сравнению)\b",
    re.I,
)
_TOOL_WORD_RE = re.compile(r"\b(?:tools?|commands?|methods?|инструмент(?:ы|ов|а)?|команд(?:ы|а|ах)?)\b", re.I)
_TOOL_INVENTORY_ANCHOR_RE = re.compile(
    r"\b(?:public\s+)?(?:tools|commands|methods|инструмент(?:ы|ов)|команд(?:ы|ах))\b"
    r"|\b(?:three|3)[- ]tool(?:[- ]\w+){0,5}\s+surface\b",
    re.I,
)
_EXPLICIT_COUNT_RE = re.compile(
    r"\b(?:exactly\s+)?(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять)\b",
    re.I,
)
_NEGATION_RE = re.compile(
    r"\b(?:does|do|did|is|are|was|were|should|must|can|could|would|will)\s+not\b"
    r"|\b(?:never|cannot|can't|mustn't|shouldn't)\b"
    r"|\b(?:не\s+следует|не\s+нужно|нельзя|никогда\s+не)\b",
    re.I,
)
_ACTION_RE = re.compile(
    r"(?<![\w-])(?:runs?|follows?|retries?|prepares?|calls?|validates?|dispatches?|routes?|processes?|loads?|reads?|writes?|"
    r"syncs?|synchronizes?|indexes?|reindexes?|discovers?|removes?|publishes?|activates?|creates?|updates?|deletes?|"
    r"preserves?|keeps?|retains?|overrides?|acknowledges?|"
    r"запустить|выполнить|повторить|подготовить|вызвать|проверить|обработать|"
    r"синхронизировать|индексировать|удалить|опубликовать)(?![\w-])",
    re.I,
)
_PURPOSE_RE = re.compile(
    r"\b(?:is\s+used\s+for|used\s+for|serves?\s+as|controls?|overrides?|"
    r"acknowledges?|allows?|enables?|selects?|specifies?|configures?|sets?|"
    r"предназначен[а-я]*\s+для|используется\s+для|переопределяет|управляет|разрешает)\b",
    re.I,
)
_PURPOSE_COPULA_RE = re.compile(
    r"\b(?:is|are|means|represents?|defines?)\b(?!\s+not\b)"
    r"(?=[^.;!?\n]{0,180}\b(?:staging\s+area|mechanism|facility|purpose|"
    r"used\s+(?:for|to|before)|responsible\s+for|so\s+that|so\b))",
    re.I,
)
_DELETE_PREDICATE_RE = re.compile(
    r"(?<![\w-])(?:deletes?|removes?|clears?|purges?|drops?|удаляет|очищает)(?![\w-])",
    re.I,
)
_PRESERVE_PREDICATE_RE = re.compile(
    r"(?<![\w-])(?:preserves?|keeps?|retains?|leaves?\s+intact|сохраняет|оставляет)(?![\w-])",
    re.I,
)
_NEGATED_DELETE_RE = re.compile(
    r"\b(?:without|not|never|does\s+not|do\s+not|will\s+not)\s+"
    r"(?:silently\s+)?(?:deleting|removing|clearing|purging|delete|remove|clear|purge)\b",
    re.I,
)
_ARCH_COMPONENT_RE = re.compile(
    r"\b(?:server|handler|router|service|transport|registry|adapter|layer|module|"
    r"ui|application|domain|infrastructure)\b",
    re.I,
)
_ARCH_RELATION_RE = re.compile(
    r"\b(?:routes?|dispatch(?:es)?|coordinates?|connects?|composes?|through|consists?|"
    r"состоит|связывает|маршрутизирует)\b|->|→",
    re.I,
)




































_NUMBER_WORD_VALUES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
}
















__all__ = [
    "ANSWER_UNIT_SCHEMA", "AnswerUnit", "LocalProof", "best_local_proof",
    "extract_answer_units", "local_proof_for_obligation",
]

__all__=[n for n in globals() if not n.startswith('__')]
