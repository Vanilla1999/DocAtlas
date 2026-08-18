"""Implementation shard 1 for project_answer_contract."""
from __future__ import annotations

from ._project_answer_contract_shared import *  # noqa: F401,F403

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
    query_span_start: int | None = None,
    query_span_end: int | None = None,
) -> ProofObligation:
    explicit_span = query_span_start is not None or query_span_end is not None
    if explicit_span:
        if (
            query_span_start is None
            or query_span_end is None
            or query_span_start < 0
            or query_span_end <= query_span_start
            or query_span_end > len(question)
        ):
            raise ValueError("invalid explicit project answer query span")
        start, end = query_span_start, query_span_end
        raw = question[start:end]
    else:
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
            query_span_start=facet.query_span_start,
            query_span_end=facet.query_span_end,
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

__all__=['_bounded', '_normal', '_span', '_technical_terms', '_technical_term_for_value', '_subject_fields', '_clean_phrase', '_effect_relation', 'ProofObligation', 'ProjectAnswerContract', 'lifecycle_intent_for_question', '_subjects', '_best_subject', '_cardinality', '_obligation', '_retrieval_hints', '_concept_queries', '_explicit_subjects', '_append_relation_obligation', '_inventory_subject', '_command_operation', '_location_subject', '_compound_workflow_subjects', '_contract_from_question_plan']
