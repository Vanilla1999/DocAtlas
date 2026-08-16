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


def _bounded(value: Any, limit: int = MAX_CONTRACT_TEXT) -> str:
    return " ".join(str(value or "").split())[:limit]


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().replace("ё", "е")).strip()


def _span(question: str, value: str) -> tuple[int | None, int | None, str | None]:
    if not value:
        return None, None, None
    match = re.search(re.escape(value), question, re.I)
    if match is None:
        return None, None, None
    return match.start(), match.end(), question[match.start():match.end()]


def _technical_terms(question: str) -> tuple[TechnicalTerm, ...]:
    return extract_technical_terms(question)


def _technical_term_for_value(
    value: str,
    terms: tuple[TechnicalTerm, ...],
    *,
    preferred_kind: TechnicalTermKind | None = None,
) -> TechnicalTerm | None:
    normalized = _normal(value).strip("`\"'")
    for term in terms:
        aliases = {_normal(alias).strip("`\"'") for alias in term.aliases}
        if normalized in aliases or normalized == _normal(term.raw):
            return coerce_technical_term(term.raw, preferred_kind) if preferred_kind else term
    if preferred_kind and value.strip():
        return coerce_technical_term(value, preferred_kind)
    return None


def _subject_fields(
    subject: str,
    term: TechnicalTerm | None,
) -> dict[str, Any]:
    if term is None:
        return {}
    return {
        "subject_kind": term.kind,
        "subject_aliases": term.aliases,
    }


def _clean_phrase(value: str) -> str:
    cleaned = _bounded(str(value or "").strip(" ?!.,:`\"'"))
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.I)
    return cleaned


def _effect_relation(value: str) -> str:
    normalized = _normal(value)
    return "preserve" if normalized in {"preserve", "keep", "retain"} else "delete"


@dataclass(frozen=True, slots=True)
class ProofObligation:
    obligation_id: str
    kind: ObligationKind
    subject: str
    attribute: str | None = None
    relation: str | None = None
    target: str | None = None
    value_kind: ValueKind = "text"
    expected_value: str | None = None
    item_kind: str | None = None
    cardinality: int | None = None
    response_mode: ResponseMode = "value"
    subject_kind: TechnicalTermKind | None = None
    subject_aliases: tuple[str, ...] = ()
    context: str | None = None
    mandatory: bool = True
    query_span_start: int | None = None
    query_span_end: int | None = None
    query_span_text: str | None = None
    lifecycle_intent: LifecycleIntent = "current"

    def __post_init__(self) -> None:
        if not self.obligation_id or len(self.obligation_id) > 240:
            raise ValueError("invalid project answer obligation id")
        if not self.subject or len(self.subject) > MAX_CONTRACT_TEXT:
            raise ValueError("project answer obligation requires a bounded subject")
        if self.cardinality is not None and not 1 <= self.cardinality <= 32:
            raise ValueError("project answer obligation cardinality is invalid")
        if self.response_mode not in {
            "value", "count", "names", "count_and_names", "call", "path", "workflow", "purpose",
        }:
            raise ValueError("project answer obligation response mode is invalid")
        if self.subject_kind is not None and self.subject_kind not in {
            "cli_command", "cli_flag", "env_var", "config_key", "code_symbol", "plain_term",
        }:
            raise ValueError("project answer subject kind is invalid")
        if len(self.subject_aliases) > 8:
            raise ValueError("project answer subject aliases exceed bounds")
        object.__setattr__(self, "subject_aliases", tuple(dict.fromkeys(
            _bounded(value) for value in self.subject_aliases if _bounded(value)
        )))
        for field_name in ("attribute", "relation", "target", "expected_value", "item_kind", "context"):
            value = getattr(self, field_name)
            if value is not None and (not str(value).strip() or len(str(value)) > MAX_CONTRACT_TEXT):
                raise ValueError(f"invalid project answer obligation {field_name}")
        if self.query_span_start is not None or self.query_span_end is not None:
            if (
                self.query_span_start is None or self.query_span_end is None
                or self.query_span_start < 0 or self.query_span_end <= self.query_span_start
                or not self.query_span_text
            ):
                raise ValueError("invalid project answer obligation query span")

    @property
    def canonical_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.subject_kind is None:
            payload.pop("subject_kind", None)
        if not self.subject_aliases:
            payload.pop("subject_aliases", None)
        if self.context is None:
            payload.pop("context", None)
        return payload


@dataclass(frozen=True, slots=True)
class ProjectAnswerContract:
    question_hash: str
    retrieval_hints: tuple[str, ...]
    concept_queries: tuple[str, ...]
    subjects: tuple[str, ...]
    proof_obligations: tuple[ProofObligation, ...]
    lifecycle_intent: LifecycleIntent = "current"
    schema_version: str = PROJECT_ANSWER_CONTRACT_SCHEMA
    input_limits: tuple[str, ...] = ()
    parse_trace: tuple[str, ...] = ()
    unresolved_parts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        hints = tuple(dict.fromkeys(_bounded(value) for value in self.retrieval_hints if _bounded(value)))
        concepts = tuple(dict.fromkeys(_bounded(value, 320) for value in self.concept_queries if _bounded(value, 320)))
        subjects = tuple(dict.fromkeys(_bounded(value) for value in self.subjects if _bounded(value)))
        obligations_by_id: dict[str, ProofObligation] = {}
        for obligation in self.proof_obligations:
            previous = obligations_by_id.setdefault(obligation.obligation_id, obligation)
            if previous != obligation:
                raise ValueError(f"conflicting project answer obligation id: {obligation.obligation_id}")
        if len(hints) > MAX_RETRIEVAL_HINTS or len(concepts) > MAX_CONCEPT_QUERIES:
            raise ValueError("project answer retrieval contract exceeds bounds")
        if len(subjects) > MAX_SUBJECTS or len(obligations_by_id) > MAX_PROOF_OBLIGATIONS:
            raise ValueError("project answer proof contract exceeds bounds")
        object.__setattr__(self, "retrieval_hints", hints)
        object.__setattr__(self, "concept_queries", concepts)
        object.__setattr__(self, "subjects", subjects)
        object.__setattr__(self, "proof_obligations", tuple(sorted(obligations_by_id.values(), key=lambda item: item.obligation_id)))
        object.__setattr__(self, "input_limits", tuple(sorted(set(self.input_limits))))
        object.__setattr__(self, "parse_trace", tuple(dict.fromkeys(str(value)[:160] for value in self.parse_trace if str(value))))
        object.__setattr__(self, "unresolved_parts", tuple(dict.fromkeys(str(value)[:160] for value in self.unresolved_parts if str(value))))

    @property
    def hash_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "question_hash": self.question_hash,
            "retrieval_hints": list(self.retrieval_hints),
            "concept_queries": list(self.concept_queries),
            "subjects": list(self.subjects),
            "proof_obligations": [item.canonical_payload for item in self.proof_obligations],
            "lifecycle_intent": self.lifecycle_intent,
            "input_limits": list(self.input_limits),
        }
        if self.parse_trace:
            payload["parse_trace"] = list(self.parse_trace)
        if self.unresolved_parts:
            payload["unresolved_parts"] = list(self.unresolved_parts)
        return payload

    @property
    def contract_hash(self) -> str:
        return canonical_hash(self.hash_payload)


def lifecycle_intent_for_question(question: str) -> LifecycleIntent:
    historical = bool(_HISTORY_RE.search(question or ""))
    current = bool(_CURRENT_RE.search(question or ""))
    if historical and current:
        return "either"
    if historical:
        return "historical"
    return "current"


def _subjects(question: str) -> list[str]:
    subjects: list[str] = []
    for match in _TASK_RE.finditer(question):
        subjects.append(f"Task {match.group(1)}")
    for match in _IDENTIFIER_RE.finditer(question):
        value = next((group for group in match.groups() if group), "")
        if value:
            subjects.append(_bounded(value.strip("`")))
    for term in extract_exact_terms(question):
        subjects.append(_bounded(term.value.strip("`")))
    for match in _SEMANTIC_SUBJECT_RE.finditer(question):
        subjects.append(_bounded(match.group(0)))
    # Product/title-cased phrases are useful when no code-shaped identifier is present.
    for match in _PRODUCT_RE.finditer(question):
        value = _bounded(match.group(0))
        first = _normal(value).split(" ", 1)[0]
        if (
            _normal(value) not in {"what", "which", "how", "task", "status", "python"}
            and first not in _INTERROGATIVE_AUXILIARIES
        ):
            subjects.append(value)
    return list(dict.fromkeys(value for value in subjects if value))[:MAX_SUBJECTS]


def _best_subject(question: str, subjects: list[str], *, fallback: str) -> str:
    if subjects:
        # Prefer task identity and exact/code-shaped terms over interrogative title words.
        ranked = sorted(subjects, key=lambda value: (
            0 if value.casefold().startswith("task ") else 1,
            0 if re.search(r"[_:.]|[a-z][A-Z]", value) else 1,
            question.casefold().find(value.casefold()) if value.casefold() in question.casefold() else 10_000,
            -len(value),
        ))
        return ranked[0]
    return fallback


def _cardinality(question: str) -> int | None:
    match = re.search(r"\b(?:exactly|ровно)?\s*(\d{1,2})\b", question, re.I)
    if match:
        value = int(match.group(1))
        return value if 1 <= value <= 32 else None
    normalized = _normal(question)
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", normalized):
            return value
    return None


def _obligation(
    *, question: str, index: int, kind: ObligationKind, subject: str,
    attribute: str | None = None, relation: str | None = None,
    target: str | None = None, value_kind: ValueKind = "text",
    expected_value: str | None = None, item_kind: str | None = None,
    cardinality: int | None = None, response_mode: ResponseMode = "value",
    subject_kind: TechnicalTermKind | None = None,
    subject_aliases: tuple[str, ...] = (), context: str | None = None,
    lifecycle_intent: LifecycleIntent,
    span_value: str | None = None,
) -> ProofObligation:
    start, end, raw = _span(question, span_value or subject)
    identity_payload: dict[str, Any] = {
        "kind": kind, "subject": _normal(subject), "attribute": attribute,
        "relation": relation, "target": _normal(target or ""), "value_kind": value_kind,
        "expected_value": expected_value, "item_kind": item_kind, "cardinality": cardinality,
        "response_mode": response_mode,
    }
    if subject_kind is not None:
        identity_payload["subject_kind"] = subject_kind
    if subject_aliases:
        identity_payload["subject_aliases"] = list(subject_aliases)
    if context:
        identity_payload["context"] = _normal(context)
    identity = canonical_hash(identity_payload)[:16]
    return ProofObligation(
        obligation_id=f"project_answer:{index}:{kind}:{identity}",
        kind=kind,
        subject=_bounded(subject),
        attribute=_bounded(attribute) if attribute else None,
        relation=_bounded(relation) if relation else None,
        target=_bounded(target) if target else None,
        value_kind=value_kind,
        expected_value=_bounded(expected_value) if expected_value else None,
        item_kind=_bounded(item_kind) if item_kind else None,
        cardinality=cardinality,
        response_mode=response_mode,
        subject_kind=subject_kind,
        subject_aliases=subject_aliases,
        context=_bounded(context) if context else None,
        query_span_start=start,
        query_span_end=end,
        query_span_text=raw,
        lifecycle_intent=lifecycle_intent,
    )


def _retrieval_hints(
    question: str,
    subjects: list[str],
    technical_terms: tuple[TechnicalTerm, ...] = (),
) -> tuple[str, ...]:
    hints: list[str] = [*subjects]
    for term in technical_terms:
        hints.extend(term.aliases)
    hints.extend(term.value for term in extract_exact_terms(question))
    for token in re.findall(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_+-]{2,}", question):
        normalized = _normal(token)
        if normalized not in _STOP_HINTS:
            hints.append(token)
    return tuple(dict.fromkeys(_bounded(value) for value in hints if _bounded(value)))[:MAX_RETRIEVAL_HINTS]


def _concept_queries(question: str, hints: tuple[str, ...], obligations: list[ProofObligation]) -> tuple[str, ...]:
    values: list[str] = []
    semantic_aliases = {
        "public_tools": "public tools inventory",
        "public_tool": "public tool command",
        "invocation": "command call action",
        "sequence": "workflow steps process",
        "location": "document path location",
        "contract_fact": "requirement rule contract",
        "purpose": "purpose used for controls overrides acknowledges",
        "delete": "delete remove clear purge derived state",
        "preserve": "preserve keep retain without deleting",
        "scope": "supported scopes values project-local global",
    }
    for obligation in obligations:
        parts = [
            obligation.subject,
            semantic_aliases.get(str(obligation.attribute), obligation.attribute),
            semantic_aliases.get(str(obligation.relation), obligation.relation),
            obligation.target,
            semantic_aliases.get(str(obligation.item_kind), obligation.item_kind),
            obligation.context,
        ]
        concept = " ".join(part for part in parts if part)
        if concept:
            values.append(concept)
    hint_norm = {_normal(value) for value in hints}
    residue = " ".join(
        token for token in re.findall(r"[\w+-]+", question, re.UNICODE)
        if _normal(token) not in _STOP_HINTS and _normal(token) not in hint_norm
    )
    if residue:
        values.append(residue)
    return tuple(dict.fromkeys(_bounded(value, 320) for value in values if _bounded(value, 320)))[:MAX_CONCEPT_QUERIES]


def _explicit_subjects(question: str, subjects: list[str]) -> list[str]:
    """Return bounded user-named entities, excluding generic query vocabulary."""

    excluded = {
        "python", "version", "status", "request", "provider", "workflow",
        "architecture", "authority", "scope", "timeout", "deadline",
    }
    values = [
        value for value in subjects
        if _normal(value) not in excluded
        and (
            re.search(r"[-_:.]|[a-z][A-Z]", value)
            or " " in value
            or value.casefold().startswith("task ")
        )
    ]
    return list(dict.fromkeys(values))[:MAX_SUBJECTS]


def _append_relation_obligation(
    obligations: list[ProofObligation], *, question: str, subject: str,
    relation: str, lifecycle: LifecycleIntent, span_value: str,
) -> None:
    obligations.append(_obligation(
        question=question,
        index=len(obligations),
        kind="relation",
        subject=subject,
        relation=relation,
        value_kind="text",
        lifecycle_intent=lifecycle,
        span_value=span_value,
    ))



def _inventory_subject(question: str, subjects: list[str]) -> str:
    explicit = re.search(
        r"\b((?:[A-Z][A-Za-z0-9-]*\s+)?MCP)(?:\s+server)?\b",
        question,
    )
    if explicit is not None:
        value = _bounded(explicit.group(1))
        if value.casefold() != "mcp":
            return value
    if re.search(r"\bDocAtlas\b", question, re.I):
        return "Docs MCP"
    return _best_subject(
        question,
        [value for value in subjects if not _TOOL_RE.fullmatch(value)],
        fallback="Docs MCP",
    )

def _command_operation(question: str) -> str:
    exact = [term.value.strip("`") for term in extract_exact_terms(question)]
    identifiers = [
        value for value in exact
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
        and value.casefold() not in {"docatlas", "doc_atlas", "docmancer"}
    ]
    if identifiers:
        return identifiers[-1]
    normalized = _normal(question)
    aliases = (
        (r"\bsync(?:hronize)?\s+project\s+docs?\b", "sync_project_docs"),
        (r"\brefresh\s+library\s+docs?\b", "refresh_library_docs"),
        (r"\bprefetch\s+library\s+docs?\b", "prefetch_library_docs"),
        (r"\bclear\s+(?:the\s+)?index\b", "clear_index"),
    )
    for pattern, value in aliases:
        if re.search(pattern, normalized, re.I):
            return value
    tail = re.search(r"\bto\s+([A-Za-z_][A-Za-z0-9_]*(?:\s+[A-Za-z_][A-Za-z0-9_]*){0,3})", question, re.I)
    return _bounded(tail.group(1).replace(" ", "_")) if tail else "requested operation"


def _location_subject(question: str, subjects: list[str]) -> str:
    tail = _LOCATION_QUESTION_RE.sub("", question, count=1).strip(" ?!.,:")
    tail = re.sub(r"^(?:the|a|an)\s+", "", tail, flags=re.I)
    tail = re.sub(r"\bDocAtlas\b\s*", "", tail, flags=re.I).strip()
    return _bounded(tail) or _best_subject(question, subjects, fallback="document")


def _compound_workflow_subjects(question: str) -> tuple[str | None, str | None]:
    explicit = []
    for term in extract_exact_terms(question):
        value = term.value.strip("`")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            explicit.append(value)
    for match in _IDENTIFIER_RE.finditer(question):
        value = next((group for group in match.groups() if group), "").strip("`")
        if value and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            explicit.append(value)
    explicit = list(dict.fromkeys(explicit))
    if len(explicit) >= 2:
        return explicit[0], explicit[1]
    return (explicit[0], None) if explicit else (None, None)


def _contract_from_question_plan(
    question: str,
    plan: QuestionPlan,
    *,
    lifecycle: LifecycleIntent,
    input_limits: tuple[str, ...],
) -> ProjectAnswerContract:
    obligations: list[ProofObligation] = []
    subjects: list[str] = []
    technical_terms: list[TechnicalTerm] = []
    for facet in plan.facets:
        if facet.subject and facet.subject not in subjects:
            subjects.append(facet.subject)
        if facet.subject_kind is not None:
            technical_terms.append(coerce_technical_term(
                facet.subject, facet.subject_kind, context=question,
            ))
        obligations.append(_obligation(
            question=question,
            index=len(obligations),
            kind=facet.kind,  # type: ignore[arg-type]
            subject=facet.subject,
            attribute=facet.attribute,
            relation=facet.relation,
            target=facet.target,
            value_kind=facet.value_kind,  # type: ignore[arg-type]
            expected_value=facet.expected_value,
            item_kind=facet.item_kind,
            response_mode=facet.response_mode,  # type: ignore[arg-type]
            subject_kind=facet.subject_kind,
            subject_aliases=facet.subject_aliases,
            context=facet.context,
            lifecycle_intent=lifecycle,
            span_value=facet.span_text or facet.subject,
        ))
    hints = _retrieval_hints(question, subjects, tuple(technical_terms))
    concepts = _concept_queries(question, hints, obligations)
    return ProjectAnswerContract(
        question_hash=canonical_hash(question),
        retrieval_hints=hints,
        concept_queries=concepts,
        subjects=tuple(subjects),
        proof_obligations=tuple(obligations),
        lifecycle_intent=lifecycle,
        schema_version=PROJECT_ANSWER_CONTRACT_SCHEMA_V4,
        input_limits=input_limits,
        parse_trace=plan.parse_trace,
        unresolved_parts=plan.unresolved_parts,
    )


def build_project_answer_contract(question: str) -> ProjectAnswerContract:
    """Build a bounded deterministic answer contract from the public question."""

    source_question = str(question or "")
    raw_question = source_question[:4_000]
    input_limits: list[str] = ["question"] if len(source_question) > 4_000 else []
    lifecycle = lifecycle_intent_for_question(raw_question)
    question_plan = compile_question_plan(raw_question)
    if question_plan.handled:
        return _contract_from_question_plan(
            raw_question, question_plan, lifecycle=lifecycle,
            input_limits=tuple(input_limits),
        )
    technical_terms = _technical_terms(raw_question)
    subjects = _subjects(raw_question)
    obligations: list[ProofObligation] = []

    declarative = _DECLARATIVE_RELATION_RE.match(raw_question)
    if declarative and not re.match(r"^(?:what|which|how|when|where|why|who|что|как|когда|где|почему)\b", raw_question, re.I):
        subject, relation, target = (
            _bounded(declarative.group(1)),
            _bounded(declarative.group(2)),
            _bounded(declarative.group(3).strip(" ?!.,:")),
        )
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="relation",
            subject=subject, relation=relation, target=target, value_kind="text",
            lifecycle_intent=lifecycle, span_value=declarative.group(0).strip(),
        ))

    if _IMPLEMENT_RE.search(raw_question):
        exact_values = [term.value.strip("`") for term in extract_exact_terms(raw_question)]
        implementation_subjects = exact_values or _explicit_subjects(raw_question, subjects)
        for subject in implementation_subjects[:4]:
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="exact_fact",
                subject=subject, relation="implementation", value_kind="code",
                lifecycle_intent=lifecycle,
                span_value=subject if subject.casefold() in raw_question.casefold() else _IMPLEMENT_RE.search(raw_question).group(0),
            ))

    comparison = _COMPARE_RE.search(raw_question)
    if comparison:
        left = (comparison.group(1) or comparison.group(3) or "").strip("`")
        right = (comparison.group(2) or comparison.group(4) or "").strip("`")
        if left and right:
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="comparison",
                subject=left, target=right, relation="contrast", value_kind="text",
                lifecycle_intent=lifecycle, span_value=comparison.group(0),
            ))

    task_match = _TASK_RE.search(raw_question)
    if task_match and _STATUS_RE.search(raw_question):
        task = f"Task {task_match.group(1)}"
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="status",
            subject=task, attribute="status", value_kind="status",
            lifecycle_intent=lifecycle, span_value=task_match.group(0),
        ))

    if _VERSION_QUESTION_RE.search(raw_question):
        subject = _best_subject(
            raw_question,
            [value for value in subjects if value.casefold() not in {"python", "version"}],
            fallback="project",
        )
        attribute = "python_version" if re.search(r"\bpython\b", raw_question, re.I) else "version"
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="attribute",
            subject=subject, attribute=attribute, value_kind="version_range",
            lifecycle_intent=lifecycle, span_value=_VERSION_QUESTION_RE.search(raw_question).group(0),
        ))

    if _TIMEOUT_RE.search(raw_question):
        timeout_match = _TIMEOUT_RE.search(raw_question)
        subject_candidates = [
            value for value in subjects
            if value.casefold() not in {"timeout", "deadline", "request", "provider"}
        ]
        subject = _best_subject(raw_question, subject_candidates, fallback="request")
        # Preserve a nearby provider/request qualifier as part of the subject.
        local = raw_question[max(0, timeout_match.start() - 80):timeout_match.end() + 80]
        qualifier = re.search(r"\b([A-Za-z_][A-Za-z0-9_.-]*(?:\s+(?:provider|request))|provider\s+request|request)\b", local, re.I)
        if qualifier and subject == "request":
            subject = qualifier.group(1)
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="attribute",
            subject=subject, attribute="timeout", value_kind="duration",
            lifecycle_intent=lifecycle, span_value=timeout_match.group(0),
        ))

    used_for = _USED_FOR_RE.match(raw_question)
    if used_for and not obligations:
        raw_subject = _clean_phrase(used_for.group(1))
        term = _technical_term_for_value(raw_subject, technical_terms)
        subject = term.raw if term is not None else raw_subject
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="purpose",
            subject=subject, relation="purpose", value_kind="text", response_mode="purpose",
            lifecycle_intent=lifecycle, span_value=used_for.group(1),
            **_subject_fields(subject, term),
        ))

    feature_context = _FEATURE_CONTEXT_RE.match(raw_question)
    if feature_context and not obligations:
        raw_subject = _clean_phrase(feature_context.group(1))
        context = _clean_phrase(feature_context.group(2))
        term = _technical_term_for_value(raw_subject, technical_terms)
        subject = term.raw if term is not None else raw_subject
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="purpose",
            subject=subject, relation="purpose", context=context, value_kind="text", response_mode="purpose",
            lifecycle_intent=lifecycle, span_value=feature_context.group(1),
            **_subject_fields(subject, term),
        ))

    term_in_context = _TERM_IN_CONTEXT_RE.match(raw_question)
    if term_in_context and not obligations:
        raw_subject = _clean_phrase(term_in_context.group(1))
        context = _clean_phrase(term_in_context.group(2))
        context_term = _technical_term_for_value(context, technical_terms)
        preferred_kind: TechnicalTermKind | None = None
        if context_term is not None and context_term.kind == "cli_command" and re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]{2,120}", raw_subject,
        ):
            preferred_kind = "cli_flag"
        term = _technical_term_for_value(
            raw_subject, technical_terms, preferred_kind=preferred_kind,
        )
        if (
            term is not None
            and context_term is not None
            and context_term.kind == "cli_command"
        ):
            subject = term.raw
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="purpose",
                subject=subject, relation="purpose", context=context, value_kind="text", response_mode="purpose",
                lifecycle_intent=lifecycle, span_value=term_in_context.group(1),
                **_subject_fields(subject, term),
            ))

    supported_values = _SUPPORTED_VALUES_RE.match(raw_question)
    if supported_values and not obligations:
        raw_attribute = _clean_phrase(supported_values.group(1))
        forms = controlled_noun_forms(raw_attribute)
        attribute = next((value for value in forms if value != raw_attribute.casefold()), raw_attribute.casefold())
        raw_subject = _clean_phrase(supported_values.group(2))
        term = _technical_term_for_value(raw_subject, technical_terms)
        subject = term.raw if term is not None else raw_subject
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="inventory",
            subject=subject, attribute=attribute, item_kind=attribute,
            value_kind="identifier_list", response_mode="names",
            lifecycle_intent=lifecycle, span_value=supported_values.group(1),
            **_subject_fields(subject, term),
        ))

    coordinated_effect = _COORDINATED_EFFECT_RE.match(raw_question)
    if coordinated_effect and not obligations:
        raw_subject = _clean_phrase(coordinated_effect.group(1))
        term = _technical_term_for_value(raw_subject, technical_terms)
        subject = term.raw if term is not None else raw_subject
        for raw_relation in (coordinated_effect.group(2), coordinated_effect.group(3)):
            relation = _effect_relation(raw_relation)
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="effect",
                subject=subject, relation=relation, value_kind="text",
                lifecycle_intent=lifecycle, span_value=raw_relation,
                **_subject_fields(subject, term),
            ))

    command_question = _COMMAND_QUESTION_RE.search(raw_question)
    if command_question:
        operation = _command_operation(raw_question)
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="command",
            subject=operation, relation="invocation", value_kind="call_expression",
            expected_value=operation if operation != "requested operation" else None,
            response_mode="call", lifecycle_intent=lifecycle,
            span_value=command_question.group(0),
        ))

    inventory_noun = _PLURAL_TOOL_RE.search(raw_question)
    surface_inventory = re.search(r"\b(?:tool(?:s)?(?:[- ]\w+){0,5}\s+surface|three[- ]tool(?:[- ]\w+){0,5}\s+surface|public(?:[- ]\w+){0,5}\s+surface)\b", raw_question, re.I)
    if not command_question and (inventory_noun or surface_inventory) and _INVENTORY_RE.search(raw_question):
        tool_match = inventory_noun or surface_inventory
        subject = _inventory_subject(raw_question, subjects)
        count_requested = bool(re.search(r"\bhow\s+many\b|\bсколько\b", raw_question, re.I))
        names_requested = bool(re.search(
            r"\b(?:what\s+are|which|list|enumerate|surface)\b|\b(?:какие|перечисл|список)\b",
            raw_question, re.I,
        ))
        response_mode: ResponseMode = (
            "count_and_names" if count_requested and names_requested else
            "count" if count_requested else "names"
        )
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="inventory",
            subject=subject, attribute="public_tools",
            value_kind="number" if response_mode == "count" else "identifier_list",
            item_kind="public_tool", cardinality=_cardinality(raw_question),
            response_mode=response_mode, lifecycle_intent=lifecycle, span_value=tool_match.group(0),
        ))

    location_question = _LOCATION_QUESTION_RE.search(raw_question)
    if location_question:
        subject = _location_subject(raw_question, subjects)
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="location",
            subject=subject, relation="location", value_kind="path", response_mode="path",
            lifecycle_intent=lifecycle, span_value=location_question.group(0),
        ))

    special_relations: list[tuple[str, str, str]] = []
    if _RECALL_MECHANISM_RE.search(raw_question):
        special_relations.append(("exact-term retrieval", "recall_mechanism", _RECALL_MECHANISM_RE.search(raw_question).group(0)))
    if _AUTHORITY_INVARIANT_RE.search(raw_question):
        special_relations.append(("authority scope", "authority_invariant", _AUTHORITY_INVARIANT_RE.search(raw_question).group(0)))
    if _REQUEST_HANDLING_RE.search(raw_question):
        special_relations.append(("MCP server", "request_handling", _REQUEST_HANDLING_RE.search(raw_question).group(0)))
    if _ARCHITECTURE_RE.search(raw_question):
        special_relations.append(("MCP server", "architecture", _ARCHITECTURE_RE.search(raw_question).group(0)))
    if _RESPONSIVENESS_RE.search(raw_question):
        special_relations.append(("MCP server", "responsiveness", _RESPONSIVENESS_RE.search(raw_question).group(0)))
    for subject, relation, span_value in special_relations:
        _append_relation_obligation(
            obligations, question=raw_question, subject=subject,
            relation=relation, lifecycle=lifecycle, span_value=span_value,
        )

    definition = _DEFINITION_RE.search(raw_question)
    if definition and not _ARCHITECTURE_RE.search(raw_question) and not obligations:
        tail = raw_question[definition.end():].strip(" ?!.,:")
        subject = _best_subject(raw_question, subjects, fallback=_bounded(tail) or "project")
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="definition",
            subject=subject, value_kind="text", lifecycle_intent=lifecycle,
            span_value=subject if subject.casefold() in raw_question.casefold() else definition.group(0),
        ))

    explicit_subjects = _explicit_subjects(raw_question, subjects)
    if not obligations and _CONTRACT_FACT_RE.search(raw_question):
        # Contract questions commonly name several schema/symbol identities but
        # do not use a classic "what is" or "what does" frame. Turn each named
        # identity into a proposition-bearing exact-fact obligation instead of
        # treating the names themselves as proof. A topical contract subject
        # keeps the governing rule sentence visible as its own local witness.
        contract_subjects: list[str] = []
        if re.search(r"\bpresentation(?:-only)?\b|\bпредставлен", raw_question, re.I):
            contract_subjects.append("presentation")
        if re.search(r"\bvectors?\b|\bвектор", raw_question, re.I):
            contract_subjects.append("vectors")
        elif re.search(r"\bembeddings?\b|\bэмбед", raw_question, re.I):
            contract_subjects.append("embeddings")
        contract_subjects.extend(explicit_subjects)
        if not contract_subjects:
            contract_match = re.search(
                r"(?:phase\s+[0-9.]+\s+)?([A-Za-zА-Яа-яЁё][\w-]{2,})"
                r"(?:\s+[A-Za-zА-Яа-яЁё][\w-]{2,}){0,2}\s+"
                r"(?:contract|rule|requirement|invariant|policy)",
                raw_question,
                re.I,
            )
            if contract_match:
                contract_subjects.append(contract_match.group(1))
        for subject in list(dict.fromkeys(contract_subjects))[:4]:
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="exact_fact",
                subject=subject, relation="contract_fact", value_kind="text",
                lifecycle_intent=lifecycle,
                span_value=subject if subject.casefold() in raw_question.casefold() else _CONTRACT_FACT_RE.search(raw_question).group(0),
            ))

    workflow = _WORKFLOW_RE.search(raw_question)
    compound_subject, compound_target = _compound_workflow_subjects(raw_question)
    workflow_requested = bool(
        workflow
        or (
            re.search(r"\bhow\s+does\b|\bкак\s+работает\b", raw_question, re.I)
            and compound_subject and compound_target
        )
    )
    if workflow_requested and not any(item.kind in {"comparison", "inventory", "command", "location"} for item in obligations):
        subject = compound_subject or _best_subject(raw_question, subjects, fallback="workflow")
        obligations.append(_obligation(
            question=raw_question, index=len(obligations), kind="workflow",
            subject=subject, target=compound_target, relation="sequence", value_kind="text",
            response_mode="workflow", lifecycle_intent=lifecycle,
            span_value=(workflow.group(0) if workflow else subject),
        ))

    behavior = _BEHAVIOR_RE.search(raw_question)
    behavior_requested = bool(behavior or (_EXPLAIN_RE.search(raw_question) and explicit_subjects))
    if behavior_requested and not any(
        item.kind in {
            "attribute", "status", "inventory", "comparison", "relation", "exact_fact",
            "command", "location", "workflow", "purpose", "effect",
        }
        for item in obligations
    ):
        behavior_subjects = explicit_subjects or [_best_subject(raw_question, subjects, fallback="project")]
        for subject in behavior_subjects:
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="behavior",
                subject=subject, relation="behavior", value_kind="text",
                lifecycle_intent=lifecycle,
                span_value=subject if subject.casefold() in raw_question.casefold() else (behavior.group(0) if behavior else _EXPLAIN_RE.search(raw_question).group(0)),
            ))

    usage = _USAGE_RE.search(raw_question)
    usage_requested = bool(usage and re.search(
        r"\b(?:when|should|recommended|using)\b|\b(?:когда|следует|рекомендуется|используя)\b",
        raw_question,
        re.I,
    ))
    if usage_requested:
        usage_subjects = explicit_subjects or [_best_subject(raw_question, subjects, fallback="project")]
        for subject in usage_subjects:
            obligations.append(_obligation(
                question=raw_question, index=len(obligations), kind="usage",
                subject=subject, relation="usage", value_kind="text",
                lifecycle_intent=lifecycle,
                span_value=subject if subject.casefold() in raw_question.casefold() else usage.group(0),
            ))

    # De-duplicate semantic aliases while retaining the earliest query provenance.
    unique: dict[tuple[Any, ...], ProofObligation] = {}
    for obligation in obligations:
        key = (
            obligation.kind, _normal(obligation.subject), obligation.attribute,
            obligation.relation, _normal(obligation.target or ""), obligation.value_kind,
            obligation.expected_value, obligation.item_kind, obligation.cardinality,
            obligation.response_mode, obligation.subject_kind, obligation.subject_aliases,
            _normal(obligation.context or ""),
        )
        unique.setdefault(key, obligation)
    obligations = list(unique.values())[:MAX_PROOF_OBLIGATIONS]
    synthetic_subjects = {"project", "request", "workflow", "requested operation", "the"}
    unresolved_synthetic = tuple(sorted({
        obligation.subject
        for obligation in obligations
        if _normal(obligation.subject) in synthetic_subjects
        and (not subjects or _normal(obligation.subject) == "requested operation")
    }))
    if unresolved_synthetic:
        safe_subjects = [value for value in subjects if _normal(value) not in synthetic_subjects]
        hints = _retrieval_hints(raw_question, safe_subjects, technical_terms)
        return ProjectAnswerContract(
            question_hash=canonical_hash(raw_question),
            retrieval_hints=hints,
            concept_queries=(),
            subjects=tuple(safe_subjects),
            proof_obligations=(),
            lifecycle_intent=lifecycle,
            schema_version=PROJECT_ANSWER_CONTRACT_SCHEMA_V4,
            input_limits=tuple(input_limits),
            parse_trace=("fail_closed:synthetic_subject",),
            unresolved_parts=tuple(
                "unresolved_requested_operation" if value == "requested operation"
                else "unresolved_query_subject"
                for value in unresolved_synthetic
            ),
        )
    uses_v3 = any(
        obligation.kind in {"purpose", "effect"}
        or obligation.subject_kind is not None
        or obligation.context is not None
        or (obligation.kind == "inventory" and obligation.item_kind not in {None, "public_tool"})
        for obligation in obligations
    )
    contract_subjects = list(subjects)
    if uses_v3:
        contract_subjects.extend(term.raw for term in technical_terms)
        contract_subjects = list(dict.fromkeys(contract_subjects))[:MAX_SUBJECTS]
    hints = _retrieval_hints(
        raw_question,
        contract_subjects,
        technical_terms if uses_v3 else (),
    )
    concepts = _concept_queries(raw_question, hints, obligations)
    return ProjectAnswerContract(
        question_hash=canonical_hash(raw_question),
        retrieval_hints=hints,
        concept_queries=concepts,
        subjects=tuple(contract_subjects[:MAX_SUBJECTS]),
        proof_obligations=tuple(obligations),
        lifecycle_intent=lifecycle,
        schema_version=(
            PROJECT_ANSWER_CONTRACT_SCHEMA
            if uses_v3 else PROJECT_ANSWER_CONTRACT_SCHEMA_V2
        ),
        input_limits=tuple(input_limits),
    )


__all__ = [
    "LifecycleIntent", "ObligationKind", "PROJECT_ANSWER_CONTRACT_SCHEMA",
    "PROJECT_ANSWER_CONTRACT_SCHEMA_V2", "PROJECT_ANSWER_CONTRACT_SCHEMA_V4",
    "ProjectAnswerContract", "ProofObligation", "ResponseMode", "ValueKind",
    "build_project_answer_contract", "lifecycle_intent_for_question",
]
