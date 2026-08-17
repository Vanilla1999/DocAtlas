"""Bounded semantic contract for project-documentation answers.

The contract deliberately separates *retrieval hints* from *proof obligations*.
Hints may widen recall, but only a locally valid answer unit can discharge an
obligation.  The public MCP input surface remains unchanged; this module is an
internal, immutable boundary shared by query planning, evidence selection, and
projection validation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from docmancer.docs.domain.question_plan import QuestionPlan, compile_question_plan
from docmancer.docs.domain.technical_terms import (
    TechnicalTerm,
    TechnicalTermKind,
    coerce_technical_term,
    controlled_noun_forms,
    extract_technical_terms,
)
from docmancer.retrieval.contracts import canonical_hash
from docmancer.retrieval.query_planning import extract_exact_terms


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

_IDENTIFIER_RE = re.compile(
    r"`([^`\n]{2,120})`|\b([A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)+)\b"
    r"|\b([A-Za-z][A-Za-z0-9_]*_[A-Za-z0-9_]+)\b"
    r"|\b([A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+)\b"
)
_PRODUCT_RE = re.compile(r"\b[A-Z][A-Za-z0-9-]{2,}(?:\s+[A-Z][A-Za-z0-9-]{1,}){0,2}\b")
_TASK_RE = re.compile(r"\b(?:task|задач[аиу]?)[\s#_-]*(\d{1,4}[A-Za-z]?)\b", re.I)
_VERSION_QUESTION_RE = re.compile(
    r"\b(?:which|what|required|supported|minimum|target)\s+(?:python\s+)?version\b"
    r"|\b(?:python|runtime|language)\s+version\b"
    r"|\b(?:какая|какую|какой|требу(?:ется|емая)|поддержива(?:ется|емая))\s+верс(?:ия|ию|ии)\b",
    re.I,
)
_TIMEOUT_RE = re.compile(r"\b(?:timeout|deadline|time[- ]?out|тайм[- ]?аут|время\s+ожидания)\b", re.I)
_TOOL_RE = re.compile(r"\b(?:tools?|commands?|methods?|инструмент(?:ы|ов|а)?|команд(?:ы|а|ах)?)\b", re.I)
_PLURAL_TOOL_RE = re.compile(r"\b(?:tools|commands|methods|инструмент(?:ы|ов)|команд(?:ы|ах))\b", re.I)
_COMMAND_QUESTION_RE = re.compile(
    r"\b(?:which|what|какую|какой)\s+(?:single\s+)?(?:command|method|invocation|call|команд[ау]|метод)\b",
    re.I,
)
_USED_FOR_RE = re.compile(
    r"^\s*(?:what\s+is|what\s+are|что\s+такое)\s+(.+?)\s+used\s+for\s*[?!.]*$",
    re.I,
)
_FEATURE_CONTEXT_RE = re.compile(
    r"^\s*(?:what\s+is|explain|describe|что\s+такое|объясни)\s+"
    r"(?:the\s+)?(.+?)\s+feature\s+in\s+(.+?)\s*[?!.]*$",
    re.I,
)
_TERM_IN_CONTEXT_RE = re.compile(
    r"^\s*(?:what\s+is|explain|describe|что\s+такое|объясни)\s+"
    r"(.+?)\s+in\s+(.+?)\s*[?!.]*$",
    re.I,
)
_SUPPORTED_VALUES_RE = re.compile(
    r"^\s*(?:which|what|какие)\s+([A-Za-z][A-Za-z-]{1,80})\s+"
    r"(?:does|do|can|может)\s+(.+?)\s+(?:support|accept|allow|поддержива(?:ет|ют)|принима(?:ет|ют))\s*[?!.]*$",
    re.I,
)
_COORDINATED_EFFECT_RE = re.compile(
    r"^\s*(?:what\s+does|what\s+do|что\s+делает)\s+(.+?)\s+"
    r"(delete|remove|clear|purge|preserve|keep|retain)\s+and\s+"
    r"(delete|remove|clear|purge|preserve|keep|retain)\s*[?!.]*$",
    re.I,
)
_LOCATION_QUESTION_RE = re.compile(r"^\s*(?:where\s+is|where\s+are|где\s+находится|где)\b", re.I)
_INTERROGATIVE_AUXILIARIES = frozenset({
    "do", "does", "did", "is", "are", "was", "were", "can", "could",
    "should", "would", "will", "what", "which", "where", "when", "how", "why", "who",
})
_INVENTORY_RE = re.compile(
    r"\b(?:which|what|list|enumerate|expose[sd]?|provide[sd]?|available|public|how\s+many|exactly)\b"
    r"|\b(?:какие|перечисл|список|публичн|доступн|сколько|ровно)\b",
    re.I,
)
_STATUS_RE = re.compile(r"\b(?:status|state|accepted|completed|done|active|статус|состояни[ея]|готов[а-я]*)\b", re.I)
_DEFINITION_RE = re.compile(
    r"\b(?:what\s+is|define|meaning\s+of|describe\s+the\s+product|что\s+такое|определени[ея]|что\s+представляет)\b",
    re.I,
)
_BEHAVIOR_RE = re.compile(
    r"\b(?:what\s+does|what\s+do|what\s+did|how\s+does|how\s+do|how\s+did|report|return|handle|process|dispatch|route|use[sd]?|expose[sd]?)\b"
    r"|\b(?:что\s+делает|как\s+работает|возвращает|показывает|сообщает|обрабатывает|маршрутизирует)\b",
    re.I,
)
_USAGE_RE = re.compile(
    r"\b(?:when\s+(?:should|do|to|is)|when\s+is|use[sd]?|using|recommended)\b"
    r"|\b(?:когда|использова(?:ть|н|но)|применя(?:ть|ется)|рекомендуется)\b",
    re.I,
)
_WORKFLOW_RE = re.compile(
    r"\b(?:workflow|flow|sequence|steps?|after|then|lifecycle)\b"
    r"|\b(?:процесс|поток|последовательност|шаг(?:и|ов)?|после|затем|жизненн(?:ый|ого)\s+цикл)\b",
    re.I,
)
_EXPLAIN_RE = re.compile(r"\b(?:explain|describe|расскажи|объясни|опиши)\b", re.I)
_CONTRACT_FACT_RE = re.compile(
    r"\b(?:contract|rule|requirement|invariant|policy)\b"
    r"|\b(?:governs?|requires?|prescribes?|defines?)\b"
    r"|\b(?:контракт|правил[оа]|требовани[ея]|инвариант|политик[аи])\b",
    re.I,
)
_RECALL_MECHANISM_RE = re.compile(
    r"\bexact(?:[- ]term| match| query)?\b.*\b(?:recall|retrieve|retrieval|lookup|match)\b"
    r"|\b(?:recall|retrieve|retrieval|lookup|match)\b.*\bexact(?:[- ]term| match| query)?\b",
    re.I,
)
_AUTHORITY_INVARIANT_RE = re.compile(
    r"\b(?:authority|scope)\b.*\b(?:without|unchanged|preserv|widen|expand|broaden)"
    r"|\b(?:without|unchanged|preserv|widen|expand|broaden).*\b(?:authority|scope)\b",
    re.I,
)
_REQUEST_HANDLING_RE = re.compile(
    r"\b(?:handle|handling|process|processing|dispatch|route|routing)\b.*\brequest\b"
    r"|\brequest\b.*\b(?:handle|handling|process|processing|dispatch|route|routing)\b"
    r"|\b(?:обработ|маршрутиз|диспетчериз)[а-я]*\b.*\bзапрос[а-я]*\b"
    r"|\bзапрос[а-я]*\b.*\b(?:обработ|маршрутиз|диспетчериз)[а-я]*\b",
    re.I,
)
_ARCHITECTURE_RE = re.compile(r"\barchitecture\b|\bархитектур[а-я]*\b", re.I)
_RESPONSIVENESS_RE = re.compile(
    r"\b(?:responsive|responsiveness|non[- ]?blocking)\b|\bотзывчив[а-я]*\b",
    re.I,
)
_SEMANTIC_SUBJECT_RE = re.compile(
    r"\b(?:MCP\s+server|Docs\s+MCP|MCP\s+сервер|exact[- ]term\s+retrieval|authority\s+scope)\b",
    re.I,
)
_IMPLEMENT_RE = re.compile(
    r"\b(?:implement|implementation|wire|add\s+support|реализова(?:ть|н|но)|сделать|добавить)\b",
    re.I,
)
_DECLARATIVE_RELATION_RE = re.compile(
    r"^\s*([A-Za-zА-Яа-яЁё_][\w.-]*(?:\s+[A-Za-zА-Яа-яЁё_][\w.-]*){0,4})\s+"
    r"(owns?|uses?|requires?|supports?|provides?|validates?|enforces?|stores?|routes?|"
    r"владеет|использует|требует|поддерживает|предоставляет|проверяет|обеспечивает|хранит|маршрутизирует)\s+"
    r"(.{2,160}?)[?.!]?\s*$",
    re.I,
)
_COMPARE_RE = re.compile(
    r"\bcompare\s+(`?[A-Za-z_][A-Za-z0-9_]*`?)\s+(?:with|to|and)\s+(`?[A-Za-z_][A-Za-z0-9_]*`?)"
    r"|\b(`?[A-Za-z_][A-Za-z0-9_]*`?)\s+instead\s+of\s+(`?[A-Za-z_][A-Za-z0-9_]*`?)",
    re.I,
)
_HISTORY_RE = re.compile(
    r"\b(?:histor(?:y|ical)|previous|formerly|old|past|superseded|completed\s+(?:roadmap|task|incident|rollout|plan|policy|phase|project|document)|"
    r"истори(?:я|ческий|ческие)|раньше|предыдущ|закрыт(?:ая|ый|ое)|завершенн(?:ая|ый|ое))\b",
    re.I,
)
_CURRENT_RE = re.compile(
    r"\b(?:current|currently|active|now|today|latest|present|актуальн|текущ|сейчас|действующ)\b",
    re.I,
)
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
}
_STOP_HINTS = frozenset({
    "about", "answer", "does", "documentation", "explain", "from", "have", "help",
    "are", "does", "how", "into", "is", "of", "project", "question", "should", "that", "the", "this", "what",
    "when", "where", "which", "with", "про", "проект", "документация", "ответ", "как",
    "какой", "какая", "какие", "что", "когда", "нужно", "надо",
})




















































__all__ = [
    "LifecycleIntent", "ObligationKind", "PROJECT_ANSWER_CONTRACT_SCHEMA",
    "PROJECT_ANSWER_CONTRACT_SCHEMA_V2", "PROJECT_ANSWER_CONTRACT_SCHEMA_V4",
    "ProjectAnswerContract", "ProofObligation", "ResponseMode", "ValueKind",
    "build_project_answer_contract", "lifecycle_intent_for_question",
]

__all__=[n for n in globals() if not n.startswith('__')]
