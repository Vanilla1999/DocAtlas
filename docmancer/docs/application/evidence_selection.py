"""Deterministic, provider-free minimal evidence selection.

The selector owns evidence eligibility and fitting.  Formatters receive only a
validated whole-item subset and remain responsible for serialization safety,
not for deciding which source facts are important.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable, Literal, Mapping, Sequence, overload

from docmancer.retrieval.contracts import canonical_hash
from docmancer.retrieval.query_planning import extract_exact_terms


SELECTOR_SCHEMA_VERSION = "budget-aware-evidence-selector-v5"
MAX_SELECTOR_CANDIDATES = 20
MAX_VISIBLE_DOCUMENTS = 3
MAX_VISIBLE_SPANS = 6
MAX_MIXED_VISIBLE_TOKENS = 800
MIXED_WRAPPER_RESERVE_TOKENS = 120
MAX_REQUIREMENT_IDENTIFIERS = 12
MAX_REQUIREMENT_PATHS = 12
MAX_PUBLIC_REQUIREMENTS = 12
MAX_CODE_GROUPS = 6
DOCS_SERIALIZATION_RESERVE_TOKENS = 350
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(r"[\w.+:/-]+", re.UNICODE)
_COMPARISON_IDENTIFIER = r"(?<![a-z0-9_`])(`?[a-z][a-z0-9_]*`?)(?![a-z0-9_`])"
_LOWERCASE_COMPARISON_RE = re.compile(
    rf"{_COMPARISON_IDENTIFIER}\s+instead\s+of\s+{_COMPARISON_IDENTIFIER}",
    re.IGNORECASE,
)
_COMPARE_WITH_RE = re.compile(
    rf"\bcompare\s+{_COMPARISON_IDENTIFIER}\s+with\s+{_COMPARISON_IDENTIFIER}", re.IGNORECASE,
)
_COMPARING_AND_RE = re.compile(
    rf"\bcomparing\s+{_COMPARISON_IDENTIFIER}\s+and\s+{_COMPARISON_IDENTIFIER}", re.IGNORECASE,
)
_RESULT_ACCESS_RE = re.compile(r"\b(?:obtain|get|retrieve)\s+(?:its|the)\s+result\b", re.IGNORECASE)
_PASSIVE_RESULT_ACCESS_RE = re.compile(
    r"\b(?:the\s+)?(?:scheduled\s+task\s+)?result\s+is\s+obtained\b", re.IGNORECASE,
)
_CODE_REQUEST_RE = re.compile(
    r"\b(?:show|write|give|provide|need)\s+(?:an?\s+)?(?:code|example|snippet)\b"
    r"|\b(?:code|example|snippet)\s+(?:for|that|showing)\b",
    re.IGNORECASE,
)
_PATCH_FACT_RE = re.compile(
    r"\b(?:must|shall|required|requires?|never|cannot|may\s+not|forbidden|prohibited|"
    r"is\s+reserved\s+for|only\s+(?:after|before|when|if)|is\s+allowed\s+only|"
    r"pytest|compileall|cargo\s+(?:test|check|build)|npm\s+(?:test|run)|"
    r"dart\s+(?:test|analyze)|go\s+test|make\s+test)\b",
    re.IGNORECASE,
)
_LEGAL_INTENT_TERMS = frozenset({
    "agreement", "arbitration", "conditions", "copyright", "disclaimer",
    "dmca", "eula", "governing", "indemnification", "jurisdiction", "legal",
    "liability", "license", "privacy", "terms", "warranties", "waiver",
})
_ALLOWED_REQUIREMENT_PROVENANCE = frozenset({
    "query_exact_term",
    "public_task_contract",
    "required_evidence_paths",
    "required_target_paths",
    "exact_dependency_binding",
    "selector_scope_requirement",
    "canonical_policy_requirement",
    "disclosed_authority_version_conflict",
})

OmissionReason = Literal[
    "wrong_version", "unknown_version", "forbidden_source", "outside_scope",
    "stale", "instruction_risk", "invalid_identity", "navigation_only",
    "query_identifier_conflict", "query_intent_mismatch",
    "authority_conflict", "exact_duplicate", "overlap_duplicate",
    "near_duplicate", "source_cap", "zero_marginal_utility", "budget",
    "dominated", "candidate_cap",
]
ProofRole = Literal[
    "generic_fact", "document_identity", "target_identity", "document_statement",
    "project_rule", "implementation_fact", "dependency_fact",
]
EvidenceQualifier = Literal[
    "proposed", "not_implemented", "confirmation_required", "negated",
    "conditional", "deprecated",
]
_PROOF_ROLES = frozenset({
    "generic_fact", "document_identity", "target_identity", "document_statement",
    "project_rule", "implementation_fact", "dependency_fact",
})
_EVIDENCE_QUALIFIERS = frozenset({
    "proposed", "not_implemented", "confirmation_required", "negated",
    "conditional", "deprecated",
})
_QUALIFIER_PATTERNS = {
    "proposed": re.compile(r"\bpropos(?:ed|al)\b", re.I),
    "not_implemented": re.compile(r"\bnot\s+(?:yet\s+)?implemented\b", re.I),
    "confirmation_required": re.compile(r"\b(?:confirmation|required approval)\s+(?:is\s+)?required\b", re.I),
    "negated": re.compile(r"\b(?:not|never|no|cannot|must not)\b", re.I),
    "conditional": re.compile(r"\b(?:if|when|unless|only after|only before)\b", re.I),
    "deprecated": re.compile(r"\bdeprecated\b", re.I),
}


def _observed_qualifiers(text: str) -> tuple[EvidenceQualifier, ...]:
    return tuple(sorted(
        qualifier
        for qualifier, pattern in _QUALIFIER_PATTERNS.items()
        if pattern.search(text)
    ))


def _estimated_tokens(value: str) -> int:
    return max(1, math.ceil(len(value.encode("utf-8")) / 4))


def _docs_answer_candidate_tokens(
    *, stable_id: str, path: str, section: str, projected: str,
    version_binding: str,
) -> int:
    source_row = {
        "evidence_id": stable_id,
        "path_or_url": path,
        "section": section,
        "snippet": projected,
        "version_binding": version_binding,
        "content_sha256": "0" * 64,
    }
    serialized_source = json.dumps(
        source_row, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    # A docs answer exposes both the cited source row and its extractive text.
    return _estimated_tokens(serialized_source) + _estimated_tokens(projected)


def _positive_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return parsed if parsed > 0 else default


def _normalized_source(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").rstrip("/").casefold()


def requirement_value_visible(value: str, text: str) -> bool:
    """Match exact query terms, including a bounded CamelCase→snake_case alias."""

    wanted = str(value or "").strip()
    haystack = str(text or "")
    if not wanted:
        return False
    if re.search(rf"(?<![\w]){re.escape(wanted)}(?![\w])", haystack, re.I):
        return True
    if not (
        re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", wanted)
        and any(char.isupper() for char in wanted[1:])
        and any(char.islower() for char in wanted)
    ):
        return False
    acronym_split = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", wanted)
    snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", acronym_split).casefold()
    return bool(re.search(rf"(?<![\w]){re.escape(snake_case)}(?![\w])", haystack, re.I))


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("code") or value.get("content") or value.get("text")
    return str(value or "").strip()


def _source_path(item: Mapping[str, Any]) -> str:
    value = item.get("source_url") or item.get("url") or item.get("path") or item.get("source") or ""
    if isinstance(value, Mapping):
        value = value.get("path") or value.get("source") or value.get("url") or ""
    return str(value).strip()


def _section(item: Mapping[str, Any]) -> str:
    value = item.get("heading_path") or item.get("title") or item.get("section") or "document"
    if isinstance(value, Mapping):
        value = value.get("heading_path") or value.get("title") or "document"
    if isinstance(value, (list, tuple)):
        return " > ".join(str(part) for part in value)
    return str(value)


def _display_text(item: Mapping[str, Any]) -> str:
    value = item.get("display_text") or item.get("code") or item.get("snippet") or item.get("content")
    if isinstance(value, Mapping):
        value = value.get("code") or value.get("content") or value.get("text")
    return str(value or "")


def _projected_text(item: Mapping[str, Any], display_text: str, result_kind: str) -> str:
    if result_kind == "docs_answer":
        return display_text
    snippet = _text(item.get("snippet"))
    fact_material = str(item.get("content") or display_text)
    fact_lines = [line.strip() for line in fact_material.splitlines() if _PATCH_FACT_RE.search(line)]
    identity_terms = list(dict.fromkeys(
        match.group(0)
        for line in fact_material.splitlines()
        for match in re.finditer(
            r"(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]+"
            r"|\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b",
            line,
        )
    ))[:32]
    symbols = " ".join(_symbols(item))
    parts = [
        part
        for part in [
            snippet,
            *fact_lines,
            *identity_terms,
            symbols,
            _source_path(item),
        ]
        if part
    ]
    return "\n".join(dict.fromkeys(parts)) or display_text


def _symbols(item: Mapping[str, Any]) -> tuple[str, ...]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
    values: list[Any] = []
    for source in (item, metadata):
        for key in ("symbols", "matched_symbols", "symbol_names", "symbol"):
            value = source.get(key)
            values.extend(value if isinstance(value, (list, tuple, set)) else [value] if value else [])
    names = [value.get("name") if isinstance(value, Mapping) else value for value in values]
    return tuple(dict.fromkeys(str(value) for value in names if str(value or "").strip()))


def _authority(item: Mapping[str, Any]) -> str:
    values = {
        str(item.get("authority") or "").casefold(),
        str(item.get("repository_authority") or "").casefold(),
        str(item.get("_packet_authority") or "").casefold(),
    }
    return "canonical" if values & {
        "canonical", "source_of_truth", "explicit_agent_policy", "primary",
        "official", "project_owned", "project_rule",
    } else "supporting"


def _version_binding(item: Mapping[str, Any]) -> str:
    return str(
        item.get("docs_exactness")
        or item.get("version_binding")
        or item.get("resolved_version")
        or item.get("version")
        or "not_applicable"
    ).strip()


def _resolved_version(item: Mapping[str, Any]) -> str:
    return str(item.get("resolved_version") or item.get("version") or item.get("requested_version") or "").strip()


def _version_rank(value: str) -> int:
    normalized = value.casefold().replace("-", "_")
    if normalized in {
        "exact", "exact_snapshot", "exact_version", "exact_version_indexed",
        "exact_version_url", "version_exact",
    }:
        return 0
    if normalized in {"", "unknown", "latest", "unversioned", "not_applicable"} or "fallback" in normalized:
        return 2
    return 1


def _risk_flags(item: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[Any] = []
    for key in ("instruction_risk_flags", "risk_flags"):
        value = item.get(key)
        values.extend(value if isinstance(value, (list, tuple, set)) else [value] if value else [])
    return tuple(sorted(str(value) for value in values if value))


def _span(item: Mapping[str, Any], name: str) -> tuple[int | None, int | None]:
    start, end = item.get(f"{name}_start"), item.get(f"{name}_end")
    packed = item.get(f"{name}_span")
    if (start is None or end is None) and isinstance(packed, (list, tuple)) and len(packed) == 2:
        start, end = packed
    try:
        return (int(start), int(end)) if start is not None and end is not None else (None, None)
    except (TypeError, ValueError):
        return None, None


def _span_was_supplied(item: Mapping[str, Any], name: str) -> bool:
    return any(key in item for key in (f"{name}_start", f"{name}_end", f"{name}_span"))


def _identity_aliases(item: Mapping[str, Any], path: str) -> tuple[str, ...]:
    values = (
        item.get("source_identity"), path, item.get("source"), item.get("path"),
        item.get("url"), item.get("source_url"), item.get("canonical_id"),
        item.get("library_id"), item.get("library"),
    )
    return tuple(sorted({key for value in values if (key := _normalized_source(value))}))


@dataclass(frozen=True, slots=True)
class SelectionConfig:
    result_kind: Literal["docs_answer", "patch_context"]
    target_tokens: int
    hard_tokens: int
    profile: Literal["generic", "library_docs_answer", "project_document_answer", "project_docs_answer"] = "generic"
    schema_version: str = SELECTOR_SCHEMA_VERSION
    max_candidates: int = MAX_SELECTOR_CANDIDATES
    max_sources: int = 3
    max_items_per_source: int = 2
    max_documents: int = MAX_VISIBLE_DOCUMENTS
    max_spans: int = MAX_VISIBLE_SPANS
    near_duplicate_threshold: int = 850
    overlap_threshold: int = 800
    marginal_utility_threshold: int = 80
    shingle_size: int = 5
    wrapper_reserve_tokens: int = 120
    cache_enabled: bool = False

    def __post_init__(self) -> None:
        if self.result_kind not in {"docs_answer", "patch_context"}:
            raise ValueError("unsupported evidence result kind")
        if self.profile not in {"generic", "library_docs_answer", "project_document_answer", "project_docs_answer"}:
            raise ValueError("unsupported evidence selection profile")
        if not 1 <= self.target_tokens <= self.hard_tokens:
            raise ValueError("selector token budgets are invalid")
        if not 1 <= self.max_candidates <= MAX_SELECTOR_CANDIDATES:
            raise ValueError("selector candidate limit is invalid")
        if self.max_sources < 1 or self.max_items_per_source < 1:
            raise ValueError("selector source limits are invalid")
        if self.max_documents < 1 or self.max_spans < 1:
            raise ValueError("selector document/span limits are invalid")
        if not 0 <= self.near_duplicate_threshold <= 1000:
            raise ValueError("near duplicate threshold is invalid")

    @property
    def config_hash(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    requirement_id: str
    kind: str
    value: str
    mandatory: bool = True
    public_provenance: str = "public_task_contract"
    source_path: str | None = None
    target_path: str | None = None
    version_binding: str | None = None
    # Hash-bound provenance from the pure query analyser; it does not alter
    # selection semantics.
    query_extraction_kind: str | None = None
    query_span_start: int | None = None
    query_span_end: int | None = None
    query_span_text: str | None = None
    proof_role: ProofRole = "generic_fact"
    qualifiers: tuple[EvidenceQualifier, ...] = ()

    def __post_init__(self) -> None:
        if self.proof_role not in _PROOF_ROLES:
            raise ValueError(f"unsupported evidence proof role: {self.proof_role}")
        qualifiers = tuple(sorted(set(self.qualifiers)))
        unknown = set(qualifiers) - _EVIDENCE_QUALIFIERS
        if unknown:
            raise ValueError(f"unsupported evidence qualifiers: {', '.join(sorted(unknown))}")
        object.__setattr__(self, "qualifiers", qualifiers)


@dataclass(frozen=True, slots=True)
class EvidenceRequirementSet(Sequence[EvidenceRequirement]):
    """Canonical immutable requirements owned by evidence selection.

    Entity and facet fields reserve the canonical contract surface for later
    analysis. They intentionally have no selection semantics in this phase.
    """

    requirements: tuple[EvidenceRequirement, ...] = ()
    required_entities: tuple[str, ...] = ()
    required_facets: tuple[str, ...] = ()
    query_extraction_provenance: tuple[tuple[str, str, str], ...] = ()
    query_requirement_spans: tuple[tuple[str, int, int, str], ...] = ()

    def __post_init__(self) -> None:
        requirements_by_id: dict[str, EvidenceRequirement] = {}
        for item in self.requirements:
            existing = requirements_by_id.get(item.requirement_id)
            if existing is not None and existing != item:
                raise ValueError(f"conflicting evidence requirement ID: {item.requirement_id}")
            requirements_by_id[item.requirement_id] = item
        canonical_requirements = tuple(sorted(
            requirements_by_id.values(), key=lambda item: item.requirement_id,
        ))
        entities = tuple(sorted({str(value).strip() for value in self.required_entities if str(value).strip()}))
        facets = tuple(sorted({str(value).strip() for value in self.required_facets if str(value).strip()}))
        provenance = tuple(sorted({
            (item.requirement_id, item.query_extraction_kind, item.value.casefold())
            for item in canonical_requirements
            if item.public_provenance == "query_exact_term" and item.query_extraction_kind
        }))
        if self.query_extraction_provenance:
            provenance = tuple(sorted({
                (str(requirement_id), str(kind), str(value).casefold())
                for requirement_id, kind, value in self.query_extraction_provenance
            }))
        spans = tuple(sorted({
            (item.requirement_id, item.query_span_start, item.query_span_end, item.query_span_text)
            for item in canonical_requirements
            if item.query_span_start is not None
            and item.query_span_end is not None
            and item.query_span_text is not None
        }))
        if self.query_requirement_spans:
            spans = tuple(sorted({
                (str(requirement_id), int(start), int(end), str(text))
                for requirement_id, start, end, text in self.query_requirement_spans
                if int(start) >= 0 and int(end) > int(start) and str(text)
            }))
        object.__setattr__(self, "requirements", canonical_requirements)
        object.__setattr__(self, "required_entities", entities)
        object.__setattr__(self, "required_facets", facets)
        object.__setattr__(self, "query_extraction_provenance", provenance)
        object.__setattr__(self, "query_requirement_spans", spans)

    def __len__(self) -> int:
        return len(self.requirements)

    @overload
    def __getitem__(self, index: int) -> EvidenceRequirement: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[EvidenceRequirement, ...]: ...

    def __getitem__(self, index: int | slice) -> EvidenceRequirement | tuple[EvidenceRequirement, ...]:
        return self.requirements[index]

    @property
    def hash_payload(self) -> dict[str, Any]:
        return {
            "requirements": [asdict(item) for item in self.requirements],
            "required_entities": list(self.required_entities),
            "required_facets": list(self.required_facets),
            "query_extraction_provenance": [list(item) for item in self.query_extraction_provenance],
            "query_requirement_spans": [list(item) for item in self.query_requirement_spans],
        }

    @property
    def requirements_hash(self) -> str:
        return canonical_hash(self.hash_payload)


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    stable_id: str
    evidence_id: str
    hydration_id: int | None
    identity_kind: str
    source_identity: str
    identity_aliases: tuple[str, ...]
    path_or_url: str
    section: str
    parent_logical_id: str
    content_sha256: str
    display_text: str
    projected_text: str
    token_estimate: int
    fit_token_estimate: int
    reported_token_estimate: int | None
    char_start: int | None
    char_end: int | None
    line_start: int | None
    line_end: int | None
    retrieval_rank: int
    component_ranks: tuple[tuple[str, int], ...]
    relevance_millis: int
    authority: str
    source_class: str
    version_binding: str
    resolved_version: str
    docs_snapshot_exact: bool | None
    project_identity: str
    module_id: str
    doc_scope: str
    symbols: tuple[str, ...]
    exact_terms: tuple[str, ...]
    instruction_risk_flags: tuple[str, ...]
    freshness: str
    navigation_only: bool
    covered_requirement_ids: frozenset[str] = frozenset()
    original: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Omission:
    stable_id: str
    reason_code: OmissionReason
    representative_stable_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceAssignment:
    requirement_id: str
    evidence_id: str
    path: str
    char_start: int | None
    char_end: int | None
    line_start: int | None
    line_end: int | None
    projected_content_hash: str
    proof_role: ProofRole
    qualifiers: tuple[EvidenceQualifier, ...]


@dataclass(frozen=True, slots=True)
class SupportDecision:
    """Immutable public support verdict produced only by ``select_evidence``."""

    answer_supported: bool
    support_status: Literal["supported", "insufficient_evidence"]
    reason_code: str | None
    missing_requirement_ids: tuple[str, ...]
    satisfied_requirement_ids: tuple[str, ...]
    mandatory_requirement_ids: tuple[str, ...]
    mandatory_coverage: float
    selected_evidence_ids: tuple[str, ...]
    requirements_hash: str
    selector_config_hash: str
    eligibility_contract_hash: str
    candidate_trace_hash: str
    selection_hash: str
    assignment_hash: str
    decision_hash: str
    requirements: EvidenceRequirementSet = field(compare=False, repr=False)

    @property
    def answer_available(self) -> bool:
        return self.answer_supported

    def as_payload(self) -> dict[str, Any]:
        return {
            "answer_supported": self.answer_supported,
            "answer_available": self.answer_supported,
            "support_status": self.support_status,
            "decision": self.support_status,
            "reason_code": self.reason_code,
            "missing_requirement_ids": list(self.missing_requirement_ids),
            "satisfied_requirement_ids": list(self.satisfied_requirement_ids),
            "mandatory_requirement_ids": list(self.mandatory_requirement_ids),
            "mandatory_coverage": self.mandatory_coverage,
            "evidence_coverage": self.mandatory_coverage,
            "selected_evidence_ids": list(self.selected_evidence_ids),
            "requirements_hash": self.requirements_hash,
            "selector_config_hash": self.selector_config_hash,
            "eligibility_contract_hash": self.eligibility_contract_hash,
            "candidate_trace_hash": self.candidate_trace_hash,
            "selection_hash": self.selection_hash,
            "assignment_hash": self.assignment_hash,
            "decision_hash": self.decision_hash,
        }

    def with_insufficient_reason_code(self, reason_code: str) -> "SupportDecision":
        """Return an insufficient verdict with one audited runtime reason."""

        if self.answer_supported or self.support_status != "insufficient_evidence":
            raise ValueError("only an insufficient support decision can carry an insufficiency reason")
        if not reason_code:
            raise ValueError("an insufficiency reason code is required")

        payload = {
            "answer_supported": self.answer_supported,
            "support_status": self.support_status,
            "reason_code": reason_code,
            "missing_requirement_ids": self.missing_requirement_ids,
            "satisfied_requirement_ids": self.satisfied_requirement_ids,
            "mandatory_requirement_ids": self.mandatory_requirement_ids,
            "mandatory_coverage": self.mandatory_coverage,
            "selected_evidence_ids": self.selected_evidence_ids,
            "requirements_hash": self.requirements_hash,
            "selector_config_hash": self.selector_config_hash,
            "eligibility_contract_hash": self.eligibility_contract_hash,
            "candidate_trace_hash": self.candidate_trace_hash,
            "selection_hash": self.selection_hash,
            "assignment_hash": self.assignment_hash,
        }
        return replace(
            self,
            reason_code=str(reason_code),
            decision_hash=canonical_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class SelectionDecision:
    status: Literal["ok", "insufficient_evidence"]
    selected_candidates: tuple[EvidenceCandidate, ...]
    omissions: tuple[Omission, ...]
    missing_requirements: tuple[str, ...]
    unresolved_conflicts: tuple[str, ...]
    metrics: Mapping[str, Any]
    selector_config_hash: str
    eligibility_contract_hash: str
    candidate_trace_hash: str
    selection_hash: str
    assignments: tuple[EvidenceAssignment, ...]
    support_decision: SupportDecision
    requirements: EvidenceRequirementSet = field(
        default_factory=EvidenceRequirementSet, compare=False, repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.requirements, EvidenceRequirementSet):
            object.__setattr__(self, "requirements", EvidenceRequirementSet(tuple(self.requirements)))

    @property
    def selected_items(self) -> list[dict[str, Any]]:
        return [dict(candidate.original) for candidate in self.selected_candidates]

    def audit_manifest(self) -> dict[str, Any]:
        return {
            "schema_version": SELECTOR_SCHEMA_VERSION,
            "status": self.status,
            "selected_stable_ids": [item.stable_id for item in self.selected_candidates],
            "omissions": [
                {
                    "stable_id": item.stable_id,
                    "reason_code": item.reason_code,
                    "representative_stable_id": item.representative_stable_id,
                }
                for item in self.omissions
            ],
            "omission_counts": _count_reasons(self.omissions),
            "missing_requirements": list(self.missing_requirements),
            "unresolved_conflicts": list(self.unresolved_conflicts),
            "metrics": dict(self.metrics),
            "selector_config_hash": self.selector_config_hash,
            "eligibility_contract_hash": self.eligibility_contract_hash,
            "requirements_hash": self.requirements.requirements_hash,
            "candidate_trace_hash": self.candidate_trace_hash,
            "selection_hash": self.selection_hash,
            "assignments": [asdict(item) for item in self.assignments],
            "assignment_hash": self.support_decision.assignment_hash,
            "support_decision": self.support_decision.as_payload(),
        }


@dataclass(frozen=True, slots=True)
class MixedSelectionLane:
    lane: Literal["project", "library"]
    identity: str
    decision: SelectionDecision

    @property
    def qualifier(self) -> str:
        return f"{self.lane}:{self.identity}"


@dataclass(frozen=True, slots=True)
class AggregateMixedSelectionDecision:
    """Canonical mixed-lane decision with collision-safe child identities."""

    lanes: tuple[MixedSelectionLane, ...]
    selection_decision: SelectionDecision
    child_decision_hash: str
    child_assignment_hash: str

    @property
    def requirements(self) -> EvidenceRequirementSet:
        return self.selection_decision.requirements

    @property
    def selected_candidates(self) -> tuple[EvidenceCandidate, ...]:
        return self.selection_decision.selected_candidates

    @property
    def assignments(self) -> tuple[EvidenceAssignment, ...]:
        return self.selection_decision.assignments

    @property
    def support_decision(self) -> SupportDecision:
        return self.selection_decision.support_decision

    def audit_manifest(self) -> dict[str, Any]:
        return {
            **self.selection_decision.audit_manifest(),
            "mixed_lanes": [
                {
                    "lane": lane.lane,
                    "identity": lane.identity,
                    "decision_hash": lane.decision.support_decision.decision_hash,
                    "assignment_hash": lane.decision.support_decision.assignment_hash,
                }
                for lane in self.lanes
            ],
            "child_decision_hash": self.child_decision_hash,
            "child_assignment_hash": self.child_assignment_hash,
        }


def aggregate_mixed_selection(
    entries: Iterable[tuple[Literal["project", "library"], str, SelectionDecision]],
) -> AggregateMixedSelectionDecision:
    """Combine canonical lane decisions without allowing cross-lane ID aliasing."""

    lanes = tuple(sorted(
        (MixedSelectionLane(lane, str(identity), decision) for lane, identity, decision in entries),
        key=lambda item: (item.lane, item.identity),
    ))
    if len(lanes) < 2:
        raise ValueError("mixed selection requires at least two lane decisions")

    requirements: list[EvidenceRequirement] = []
    candidates: list[EvidenceCandidate] = []
    assignments: list[EvidenceAssignment] = []
    missing: list[str] = []
    conflicts: list[str] = []
    omissions: list[Omission] = []
    for lane in lanes:
        prefix = lane.qualifier + ":"
        requirements.extend(
            replace(requirement, requirement_id=prefix + requirement.requirement_id)
            for requirement in lane.decision.requirements
        )
        candidates.extend(
            replace(
                candidate,
                stable_id=prefix + candidate.stable_id,
                evidence_id=prefix + candidate.evidence_id,
                covered_requirement_ids=frozenset(
                    prefix + requirement_id
                    for requirement_id in candidate.covered_requirement_ids
                ),
            )
            for candidate in lane.decision.selected_candidates
        )
        assignments.extend(
            replace(
                assignment,
                requirement_id=prefix + assignment.requirement_id,
                evidence_id=prefix + assignment.evidence_id,
            )
            for assignment in lane.decision.assignments
        )
        missing.extend(prefix + value for value in lane.decision.missing_requirements)
        conflicts.extend(prefix + value for value in lane.decision.unresolved_conflicts)
        omissions.extend(
            replace(
                omission,
                stable_id=prefix + omission.stable_id,
                representative_stable_id=(
                    prefix + omission.representative_stable_id
                    if omission.representative_stable_id else None
                ),
            )
            for omission in lane.decision.omissions
        )

    requirement_set = EvidenceRequirementSet(tuple(requirements))
    mandatory_ids = tuple(item.requirement_id for item in requirement_set if item.mandatory)
    satisfied_ids = tuple(sorted({item.requirement_id for item in assignments}))
    missing_ids = tuple(sorted(set(mandatory_ids) - set(satisfied_ids)))
    selected_ids = tuple(sorted({item.evidence_id for item in assignments}))
    child_decision_hash = canonical_hash([
        (lane.lane, lane.identity, lane.decision.support_decision.decision_hash)
        for lane in lanes
    ])
    child_assignment_hash = canonical_hash([
        (lane.lane, lane.identity, lane.decision.support_decision.assignment_hash)
        for lane in lanes
    ])
    assignment_hash = canonical_hash({
        "assignments": [asdict(item) for item in assignments],
        "child_assignment_hash": child_assignment_hash,
    })
    selected_documents = {_normalized_source(item.source_identity) for item in candidates}
    selected_tokens = sum(item.token_estimate for item in candidates)
    bounded_materialization_failed = (
        len(selected_documents) > MAX_VISIBLE_DOCUMENTS
        or len(candidates) > MAX_VISIBLE_SPANS
        or selected_tokens + MIXED_WRAPPER_RESERVE_TOKENS > MAX_MIXED_VISIBLE_TOKENS
    )
    if bounded_materialization_failed:
        missing_ids = tuple(sorted({*missing_ids, "bounded_evidence_not_materializable"}))
        missing.append("bounded_evidence_not_materializable")
    supported = (
        not bounded_materialization_failed
        and all(lane.decision.support_decision.answer_supported for lane in lanes)
    )
    base = {
        "answer_supported": supported,
        "support_status": "supported" if supported else "insufficient_evidence",
        "reason_code": (
            None if supported else
            "bounded_evidence_not_materializable" if bounded_materialization_failed else
            "mixed_support_incomplete"
        ),
        "missing_requirement_ids": missing_ids,
        "satisfied_requirement_ids": satisfied_ids,
        "mandatory_requirement_ids": mandatory_ids,
        "mandatory_coverage": (
            len(set(satisfied_ids) & set(mandatory_ids)) / len(mandatory_ids)
            if mandatory_ids else 1.0
        ),
        "selected_evidence_ids": selected_ids,
        "requirements_hash": requirement_set.requirements_hash,
        "selector_config_hash": canonical_hash([lane.decision.selector_config_hash for lane in lanes]),
        "eligibility_contract_hash": canonical_hash([lane.decision.eligibility_contract_hash for lane in lanes]),
        "candidate_trace_hash": canonical_hash([lane.decision.candidate_trace_hash for lane in lanes]),
        "selection_hash": canonical_hash({
            "children": child_decision_hash,
            "selected_evidence_ids": selected_ids,
        }),
        "assignment_hash": assignment_hash,
    }
    support = SupportDecision(
        **base,
        decision_hash=canonical_hash({**base, "child_decision_hash": child_decision_hash}),
        requirements=requirement_set,
    )
    decision = SelectionDecision(
        status="ok" if supported else "insufficient_evidence",
        selected_candidates=tuple(candidates), omissions=tuple(omissions),
        missing_requirements=tuple(missing), unresolved_conflicts=tuple(conflicts),
        metrics={
            "lane_count": len(lanes),
            "selected_documents": len(selected_documents),
            "selected_spans": len(candidates),
            "selected_tokens": selected_tokens,
            "projected_total_tokens": selected_tokens + MIXED_WRAPPER_RESERVE_TOKENS,
            "max_documents": MAX_VISIBLE_DOCUMENTS,
            "max_spans": MAX_VISIBLE_SPANS,
            "hard_tokens": MAX_MIXED_VISIBLE_TOKENS,
        },
        selector_config_hash=support.selector_config_hash,
        eligibility_contract_hash=support.eligibility_contract_hash,
        candidate_trace_hash=support.candidate_trace_hash,
        selection_hash=support.selection_hash, assignments=tuple(assignments),
        support_decision=support, requirements=requirement_set,
    )
    return AggregateMixedSelectionDecision(
        lanes=lanes, selection_decision=decision,
        child_decision_hash=child_decision_hash,
        child_assignment_hash=child_assignment_hash,
    )


def docs_selection_config(max_tokens: int) -> SelectionConfig:
    hard = min(800, max(256, int(max_tokens)))
    return SelectionConfig(
        result_kind="docs_answer", target_tokens=min(650, hard), hard_tokens=hard,
        max_sources=3, max_items_per_source=2,
        max_documents=MAX_VISIBLE_DOCUMENTS, max_spans=MAX_VISIBLE_SPANS,
        wrapper_reserve_tokens=120,
        marginal_utility_threshold=100,
    )


def library_docs_selection_config(max_tokens: int) -> SelectionConfig:
    return replace(docs_selection_config(max_tokens), profile="library_docs_answer")


def project_docs_selection_config(max_tokens: int) -> SelectionConfig:
    return replace(docs_selection_config(max_tokens), profile="project_docs_answer")


def patch_selection_config(max_tokens: int) -> SelectionConfig:
    hard = min(2000, max(256, int(max_tokens)))
    return SelectionConfig(
        result_kind="patch_context", target_tokens=min(1200, hard), hard_tokens=hard,
        max_sources=12, max_items_per_source=3, wrapper_reserve_tokens=min(300, hard // 3),
        marginal_utility_threshold=160,
    )


def _extract_requirement_entities_and_facets(question: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    entities: set[str] = set()
    facets: set[str] = set()
    comparison_entities: list[str] = []
    for pattern in (_LOWERCASE_COMPARISON_RE, _COMPARE_WITH_RE, _COMPARING_AND_RE):
        for match in pattern.finditer(question):
            left, right = (match.group(1).strip("`").casefold(), match.group(2).strip("`").casefold())
            entities.update((left, right))
            comparison_entities.append(left)
            facets.add(f"comparison:{left}:{right}")
    for match in itertools.chain(_RESULT_ACCESS_RE.finditer(question), _PASSIVE_RESULT_ACCESS_RE.finditer(question)):
        if comparison_entities:
            facets.add(f"result_access:{comparison_entities[-1]}:{match.group(0).casefold()}")
    return tuple(sorted(entities)), tuple(sorted(facets))


def _project_answer_facets(question: str, entities: Sequence[str]) -> tuple[str, ...]:
    """Derive small, auditable answer facets for common documentation questions."""

    normalized = question.casefold()
    facets: set[str] = set()
    if "exact" in normalized and re.search(r"\b(?:recall|retrieve|retrieval)\b", normalized):
        facets.add("recall_mechanism")
    if re.search(r"\b(?:authority|scope)\b", normalized) and re.search(r"\b(?:widen|expand|broaden|without)\b", normalized):
        facets.add("authority_invariant")
    if re.search(r"\b(?:handle|handling|process|processing|dispatch|route)\b", normalized) and re.search(
        r"\brequest\b|\bзапрос", normalized,
    ):
        facets.add("request_handling")
    if re.search(r"\barchitecture\b|\bархитектур", normalized):
        facets.add("architecture")
    if re.search(r"\b(?:responsive|responsiveness|non-blocking|nonblocking)\b|\bотзывчив", normalized):
        facets.add("responsiveness")
    facet_entities = tuple(value for value in entities if value)
    if not facet_entities:
        return tuple(sorted(facets))
    if re.search(
        r"\bwhat\s+(?:does|do|is|are)\b|\b(?:report|return|provide|show)\b"
        r"|\b(?:что\s+(?:возвращает|показывает|сообщает)|возвращает|показывает|сообщает)\b",
        normalized,
    ):
        facets.update(f"behavior:{entity}" for entity in facet_entities)
    if re.search(
        r"\bwhen\s+(?:should|do|to)\b|\bwhen\s+is\b|\buse\b"
        r"|\bкогда\b|\bиспользова(?:ть|н|но)\b|\bприменя(?:ть|ется)\b",
        normalized,
    ):
        facets.update(f"usage:{entity}" for entity in facet_entities)
    if re.search(
        r"\bworkflow\b|\bafter\b|\bthen\b|\bsteps?\b|\bsequence\b"
        r"|\bпроцесс\b|\bпосле\b|\bзатем\b|\bшаг(?:и|ов)?\b|\bпоследовательност(?:ь|и)\b",
        normalized,
    ):
        facets.update(f"workflow:{entity}" for entity in facet_entities)
    return tuple(sorted(facets))


def _comparison_query_span(question: str, left: str, right: str) -> tuple[int, int] | None:
    for pattern in (_LOWERCASE_COMPARISON_RE, _COMPARE_WITH_RE, _COMPARING_AND_RE):
        for match in pattern.finditer(question):
            matched_values = (match.group(1).strip("`").casefold(), match.group(2).strip("`").casefold())
            if matched_values == (left, right):
                return match.start(1), match.end(2)
    return None


def _with_query_requirement_spans(
    question: str,
    requirements: tuple[EvidenceRequirement, ...],
) -> tuple[EvidenceRequirement, ...]:
    folded = question.casefold()
    spanned: list[EvidenceRequirement] = []
    for requirement in requirements:
        if requirement.public_provenance != "query_exact_term":
            spanned.append(requirement)
            continue
        value = requirement.value.casefold()
        if requirement.kind == "facet":
            _, _, detail = value.partition(":")
            if value.startswith("comparison:"):
                left, _, right = detail.partition(":")
                comparison_span = _comparison_query_span(question, left, right)
                start, end = comparison_span if comparison_span is not None else (-1, -1)
            else:
                _, _, phrase = detail.partition(":")
                start, end = folded.find(phrase), -1
                if start >= 0:
                    end = start + len(phrase)
        else:
            start, end = folded.find(value), -1
            if start >= 0:
                end = start + len(value)
        spanned.append(replace(
            requirement,
            query_span_start=start if start >= 0 else None,
            query_span_end=end if end > start else None,
            query_span_text=question[start:end] if start >= 0 and end > start else None,
        ))
    return tuple(spanned)


def _semantic_requirement_key(requirement: EvidenceRequirement) -> tuple[Any, ...]:
    """Return the proof obligation identity, independent of extraction alias."""

    return (
        requirement.kind,
        requirement.value.casefold(),
        requirement.mandatory,
        requirement.proof_role,
        requirement.qualifiers,
        requirement.source_path,
        requirement.target_path,
        requirement.version_binding,
    )


def build_requirements(
    question: str,
    *,
    required_evidence_paths: Iterable[str] = (),
    required_target_paths: Iterable[str] = (),
    public_requirements: Iterable[Mapping[str, Any] | str] = (),
    exact_version: str | None = None,
    exact_snapshot_required: bool = False,
    project_identity: str | None = None,
    module_id: str | None = None,
    profile: Literal["generic", "library_docs_answer", "project_document_answer", "project_docs_answer"] = "generic",
    library_requirement_contract: Mapping[str, Iterable[str]] | None = None,
) -> EvidenceRequirementSet:
    requirements: list[EvidenceRequirement] = []
    input_limits: set[str] = set()
    for index, term in enumerate(extract_exact_terms(question)):
        requirements.append(EvidenceRequirement(
            requirement_id=f"query_exact:{index}:{term.normalized_value}",
            kind="exact_term", value=term.value, mandatory=term.kind != "path",
            public_provenance="query_exact_term",
            query_extraction_kind=term.kind,
            proof_role="document_statement" if profile == "project_document_answer" else "generic_fact",
        ))
    existing_exact_values = {
        item.value.casefold() for item in requirements if item.kind == "exact_term"
    }
    identifier_values = sorted({
        token
        for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_]\w*)*\b", question)
        if (
            "_" in token or "." in token or "::" in token
            or (any(char.isupper() for char in token[1:]) and any(char.islower() for char in token))
        )
        and token.casefold() not in existing_exact_values
    }, key=str.casefold)
    if len(identifier_values) > MAX_REQUIREMENT_IDENTIFIERS:
        input_limits.add("identifiers")
        identifier_values = identifier_values[:MAX_REQUIREMENT_IDENTIFIERS]
    for index, value in enumerate(identifier_values):
        requirements.append(EvidenceRequirement(
            requirement_id=f"query_symbol:{index}:{value.casefold()}",
            kind="exact_term", value=value, public_provenance="query_exact_term",
            query_extraction_kind="identifier",
            proof_role="document_statement" if profile == "project_document_answer" else "generic_fact",
        ))
    for kind, paths, provenance in (
        ("evidence_path", required_evidence_paths, "required_evidence_paths"),
        ("target_path", required_target_paths, "required_target_paths"),
    ):
        normalized_paths = sorted(
            {str(path).strip() for path in paths if str(path).strip()},
            key=lambda value: (_normalized_source(value), value),
        )
        if len(normalized_paths) > MAX_REQUIREMENT_PATHS:
            input_limits.add("paths")
            normalized_paths = normalized_paths[:MAX_REQUIREMENT_PATHS]
        for index, value in enumerate(normalized_paths):
            requirements.append(EvidenceRequirement(
                requirement_id=f"{kind}:{index}:{_normalized_source(value)}",
                kind=kind, value=value, public_provenance=provenance,
                source_path=value if kind == "evidence_path" else None,
                target_path=value if kind == "target_path" else None,
                proof_role="document_identity" if kind == "evidence_path" else "target_identity",
            ))
    if exact_version:
        requirements.append(EvidenceRequirement(
            requirement_id=f"exact_version:{exact_version}", kind="exact_version",
            value=str(exact_version), public_provenance="exact_dependency_binding",
            version_binding=str(exact_version),
        ))
    for kind, value in (
        ("exact_snapshot", "true" if exact_snapshot_required else ""),
        ("project_identity", project_identity or ""),
        ("module_id", module_id or ""),
    ):
        if str(value).strip():
            requirements.append(EvidenceRequirement(
                requirement_id=f"{kind}:{str(value).strip()}",
                kind=kind,
                value=str(value).strip(),
                public_provenance="selector_scope_requirement",
            ))
    sorted_public_requirements = sorted(public_requirements, key=canonical_hash)
    if len(sorted_public_requirements) > MAX_PUBLIC_REQUIREMENTS:
        input_limits.add("public_requirements")
        sorted_public_requirements = sorted_public_requirements[:MAX_PUBLIC_REQUIREMENTS]
    for index, raw in enumerate(sorted_public_requirements):
        if isinstance(raw, Mapping):
            value = str(raw.get("value") or raw.get("text") or "").strip()
            kind = str(raw.get("kind") or "required_fact")
            mandatory = raw.get("mandatory") is not False
            provenance = str(raw.get("public_provenance") or "public_task_contract")
            proof_role = str(raw.get("proof_role") or "generic_fact")
            raw_qualifiers = raw.get("qualifiers") or ()
            qualifiers = tuple(str(item) for item in raw_qualifiers) if isinstance(raw_qualifiers, (list, tuple, set)) else (str(raw_qualifiers),)
        else:
            value, kind, mandatory, provenance = str(raw).strip(), "required_fact", True, "public_task_contract"
            proof_role, qualifiers = "generic_fact", ()
        if value:
            if provenance not in _ALLOWED_REQUIREMENT_PROVENANCE:
                raise ValueError(f"unsupported evidence requirement provenance: {provenance}")
            requirements.append(EvidenceRequirement(
                requirement_id=f"public:{index}:{canonical_hash(value)[:12]}",
                kind=kind, value=value, mandatory=mandatory, public_provenance=provenance,
                proof_role=proof_role, qualifiers=qualifiers,
            ))
    unique: dict[str, EvidenceRequirement] = {}
    for item in requirements:
        existing = unique.get(item.requirement_id)
        if existing is not None and existing != item:
            raise ValueError(f"conflicting evidence requirement ID: {item.requirement_id}")
        unique[item.requirement_id] = item
    entities, facets = _extract_requirement_entities_and_facets(question)
    if profile == "project_document_answer" and not any(
        item.mandatory and item.kind not in {"evidence_path", "target_path"}
        for item in unique.values()
    ):
        unique["document_content_requirement"] = EvidenceRequirement(
            requirement_id="document_content_requirement",
            kind="unsupported_query",
            value="",
            public_provenance="query_exact_term",
            query_extraction_kind="no_canonical_document_content_requirement",
            proof_role="document_statement",
        )
    if profile == "library_docs_answer":
        comparison_intent = bool(re.search(r"\b(?:compare|comparing|comparison|instead|versus|vs\.?|difference)\b", question, re.IGNORECASE))
        raw_contract = library_requirement_contract or {}
        contract = raw_contract if comparison_intent else {}
        contract_entities = tuple(sorted({str(value).casefold() for value in contract.get("entities", ()) if str(value).strip()}))
        entities = tuple(sorted(set(entities) | set(contract_entities)))
        if len(contract_entities) == 2:
            for facet in contract.get("facets", ()):
                if str(facet) == "comparison":
                    facets = tuple(sorted(set(facets) | {f"comparison:{contract_entities[0]}:{contract_entities[1]}"}))
                if str(facet) == "result_access":
                    facets = tuple(sorted(set(facets) | {f"result_access:{contract_entities[0]}:contract"}))
        for entity in entities:
            unique[f"entity:{entity}"] = EvidenceRequirement(
                requirement_id=f"entity:{entity}", kind="entity", value=entity,
                public_provenance="query_exact_term", query_extraction_kind="lowercase_comparison_anchor",
            )
        for facet in facets:
            unique[f"facet:{facet}"] = EvidenceRequirement(
                requirement_id=f"facet:{facet}", kind="facet", value=facet,
                public_provenance="query_exact_term", query_extraction_kind="answer_facet",
            )
        raw_groups = (raw_contract.get("code_groups") or ()) if _CODE_REQUEST_RE.search(question) else ()
        if not raw_groups and _CODE_REQUEST_RE.search(question) and raw_contract.get("required_code_group"):
            raw_groups = (raw_contract["required_code_group"],)
        if len(raw_groups) > MAX_CODE_GROUPS:
            input_limits.add("code_groups")
            raw_groups = raw_groups[:MAX_CODE_GROUPS]
        for index, raw_group in enumerate(raw_groups):
            fragments = tuple(
                str(value).strip() for value in raw_group
                if str(value).strip()
            ) if isinstance(raw_group, (list, tuple, set)) else ()
            if not fragments:
                continue
            encoded_group = json.dumps(
                sorted(set(fragments), key=str.casefold),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            unique[f"code_group:{index}:{canonical_hash(encoded_group)[:12]}"] = EvidenceRequirement(
                requirement_id=f"code_group:{index}:{canonical_hash(encoded_group)[:12]}",
                kind="code_group",
                value=encoded_group,
                public_provenance="public_task_contract",
            )
        if not entities and not facets and re.search(r"[\u0400-\u04ff]", question):
            unique["library_query_coverage"] = EvidenceRequirement(
                requirement_id="library_query_coverage", kind="unsupported_query", value="",
                public_provenance="query_exact_term", query_extraction_kind="no_canonical_library_requirement",
            )
    if profile == "project_docs_answer":
        # A generic retrieval hit is not a proof of an answer. Bind the
        # project question's explicit terms into the canonical contract.
        from docmancer.docs.domain.answer_completeness import (
            extract_project_answer_requirements,
            extract_query_relevance_terms,
        )

        semantic_terms = extract_project_answer_requirements(question)
        semantic_terms = tuple(dict.fromkeys((*semantic_terms, *re.findall(
            r"\b(?:mcp\s+server|mcp\s+сервер|architecture|архитектура|workflow|процесс|protocol|протокол)\b",
            question,
            re.IGNORECASE,
        ))))
        if (
            not semantic_terms
            and not any(item.mandatory for item in unique.values())
            and not entities
            and not facets
            and not _project_answer_facets(question, ())
        ):
            semantic_terms = extract_query_relevance_terms(question)
        for index, term in enumerate(semantic_terms):
            unique[f"project_term:{index}:{term.casefold()}"] = EvidenceRequirement(
                requirement_id=f"project_term:{index}:{term.casefold()}",
                kind="exact_term", value=term, public_provenance="query_exact_term",
                query_extraction_kind="project_answer_term",
            )
        facet_entities = tuple(
            term for term in semantic_terms
            if re.search(r"[_:.]|[a-z][A-Z]", term)
        )
        for facet in _project_answer_facets(question, facet_entities):
            unique[f"facet:{facet}"] = EvidenceRequirement(
                requirement_id=f"facet:{facet}", kind="facet", value=facet,
                public_provenance="query_exact_term", query_extraction_kind="project_answer_facet",
            )
        # Project answers need the same relational proof as library answers;
        # selecting two named terms alone does not establish a comparison.
        for entity in entities:
            unique[f"entity:{entity}"] = EvidenceRequirement(
                requirement_id=f"entity:{entity}", kind="entity", value=entity,
                public_provenance="query_exact_term", query_extraction_kind="comparison_anchor",
            )
        for facet in facets:
            unique[f"facet:{facet}"] = EvidenceRequirement(
                requirement_id=f"facet:{facet}", kind="facet", value=facet,
                public_provenance="query_exact_term", query_extraction_kind="comparison_facet",
            )
        if not any(item.mandatory for item in unique.values()):
            unique["project_answer_requirement"] = EvidenceRequirement(
                requirement_id="project_answer_requirement", kind="unsupported_query", value="",
                public_provenance="query_exact_term",
                query_extraction_kind="no_project_answer_requirement",
            )
    for category in sorted(input_limits):
        # Preserve a deterministic fail-closed reason without accepting an
        # unbounded input set into the selector/audit contract.
        unique[f"input_limit:{category}"] = EvidenceRequirement(
            requirement_id=f"input_limit:{category}",
            kind="unsupported_query",
            value=category,
            public_provenance="selector_scope_requirement",
            query_extraction_kind="input_limit_exceeded",
        )
    canonical_by_obligation: dict[tuple[Any, ...], EvidenceRequirement] = {}
    extraction_provenance: list[tuple[str, str, str]] = []
    for requirement in unique.values():
        key = _semantic_requirement_key(requirement)
        canonical = canonical_by_obligation.get(key)
        # Query extractors can discover the same exact obligation through a
        # symbol and a project-answer term. Keep both audit provenance records
        # but select and score the obligation only once.
        if (
            canonical is not None
            and canonical.public_provenance == requirement.public_provenance == "query_exact_term"
        ):
            if requirement.query_extraction_kind:
                extraction_provenance.append((
                    canonical.requirement_id,
                    requirement.query_extraction_kind,
                    requirement.value.casefold(),
                ))
            continue
        canonical_by_obligation.setdefault(key, requirement)
    canonical_requirements = _with_query_requirement_spans(
        question, tuple(sorted(canonical_by_obligation.values(), key=lambda item: item.requirement_id))
    )
    extraction_provenance.extend(
        (item.requirement_id, item.query_extraction_kind, item.value.casefold())
        for item in canonical_requirements
        if item.public_provenance == "query_exact_term" and item.query_extraction_kind
    )
    return EvidenceRequirementSet(
        canonical_requirements,
        required_entities=entities,
        required_facets=facets,
        query_extraction_provenance=tuple(extraction_provenance),
    )


def normalize_candidates(
    items: Iterable[Mapping[str, Any]],
    *,
    result_kind: Literal["docs_answer", "patch_context"],
) -> tuple[list[EvidenceCandidate], list[Omission]]:
    candidates: list[EvidenceCandidate] = []
    omissions: list[Omission] = []
    for rank, raw in enumerate(items, start=1):
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        path, section, display = _source_path(item), _section(item), _display_text(item)
        digest = hashlib.sha256(display.encode("utf-8")).hexdigest()
        metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
        child_stable = str(
            item.get("stable_chunk_id")
            or item.get("stable_child_id")
            or metadata.get("stable_chunk_id")
            or ""
        )
        stable = child_stable or str(item.get("stable_id") or "")
        identity_kind = "stable_child" if child_stable else "legacy"
        source_class = str(item.get("source_class") or "")
        scoped_host_policy = (
            path.startswith("host-policy://")
            and bool(
                item.get("scope_verified")
                or metadata.get("scope_verified")
            )
            and str(
                item.get("repository_authority") or ""
            ).strip().casefold() == "explicit_agent_policy"
            and str(
                item.get("instruction_trust") or ""
            ).strip().casefold() == "scoped_agent_policy"
        )
        indexed_project_doc = source_class in {
            "project_doc", "project_file"
        } and bool(metadata) and not scoped_host_policy
        if indexed_project_doc and not child_stable:
            omissions.append(Omission(f"invalid:{rank}", "invalid_identity"))
            continue
        if not stable and path and display:
            stable = "legacy:" + canonical_hash({
                "path": path,
                "section": section,
                "content": digest,
                # Legacy retrieval rows do not expose Task 40 child identity.
                # Preserve distinct code-graph aliases that share prose.
                "symbols": sorted(_symbols(item)),
            })[:40]
        char_start, char_end = _span(item, "char")
        line_start, line_end = _span(item, "line")
        invalid_span = (
            (_span_was_supplied(item, "char") and (char_start is None or char_end is None))
            or (_span_was_supplied(item, "line") and (line_start is None or line_end is None))
            or (char_start is None) != (char_end is None)
            or (char_start is not None and (char_start < 0 or char_end <= char_start))
            or (line_start is None) != (line_end is None)
            or (line_start is not None and (line_start < 0 or line_end < line_start))
        )
        expected_hash = str(item.get("display_content_hash") or "").casefold()
        missing_parent = identity_kind == "stable_child" and not str(
            item.get("parent_logical_id") or metadata.get("parent_logical_id") or ""
        ).strip()
        invalid_hash = (identity_kind == "stable_child" and not expected_hash) or bool(expected_hash) and (
            _HEX_SHA256.fullmatch(expected_hash) is None or expected_hash != digest
        )
        if not path or not display or not stable or invalid_span or missing_parent or invalid_hash:
            omissions.append(Omission(stable or f"invalid:{rank}", "invalid_identity"))
            continue
        score = next((value for value in (
            item.get("score"), item.get("relevance_score"), metadata.get("score"), metadata.get("relevance_score")
        ) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))), 0.0)
        projected = _projected_text(item, display, result_kind)
        reported = item.get("token_estimate") or metadata.get("token_estimate")
        trace = metadata.get("retrieval_trace") if isinstance(metadata.get("retrieval_trace"), Mapping) else {}
        component_values = item.get("component_ranks") or trace.get("component_ranks") or {}
        component_ranks = tuple(sorted(
            (str(name), int(value))
            for name, value in component_values.items()
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
        )) if isinstance(component_values, Mapping) else ()
        exact_values = item.get("exact_terms") or metadata.get("exact_terms") or ()
        if isinstance(exact_values, str):
            exact_values = (exact_values,)
        candidates.append(EvidenceCandidate(
            stable_id=stable,
            evidence_id=str(item.get("evidence_id") or ""),
            hydration_id=(
                int(item.get("hydration_id"))
                if isinstance(item.get("hydration_id"), int) and not isinstance(item.get("hydration_id"), bool)
                else int(item.get("section_id"))
                if isinstance(item.get("section_id"), int) and not isinstance(item.get("section_id"), bool)
                else None
            ),
            identity_kind=identity_kind,
            source_identity=str(item.get("source_identity") or path),
            identity_aliases=_identity_aliases(item, path),
            path_or_url=path,
            section=section,
            parent_logical_id=str(item.get("parent_logical_id") or metadata.get("parent_logical_id") or ""),
            content_sha256=digest,
            display_text=display,
            projected_text=projected,
            # Patch evidence is rendered into cited source, target and guidance
            # objects. Reserve their structural cost here so selection cannot
            # hand the formatter a bundle that only fits as raw chunk text.
            token_estimate=(
                _estimated_tokens(projected)
                if result_kind == "docs_answer"
                else _estimated_tokens(projected) + 88
            ),
            fit_token_estimate=(
                _docs_answer_candidate_tokens(
                    stable_id=stable,
                    path=path,
                    section=section,
                    projected=projected,
                    version_binding=_version_binding(item),
                )
                if result_kind == "docs_answer"
                else _estimated_tokens(projected) + 88
            ),
            reported_token_estimate=int(reported) if isinstance(reported, int) and not isinstance(reported, bool) else None,
            char_start=char_start, char_end=char_end, line_start=line_start, line_end=line_end,
            # Absence of an explicit retrieval rank must not make selection
            # depend on the caller's iteration order.
            retrieval_rank=_positive_int(
                item.get("retrieval_rank") if item.get("retrieval_rank") is not None else item.get("rank"),
                default=10_000,
            ),
            component_ranks=component_ranks,
            relevance_millis=int(round(float(score) * 1000)),
            authority=_authority(item),
            source_class=str(
                item.get("source_class")
                or (
                    "legal"
                    if str(item.get("authority") or "").casefold() == "legal"
                    else ""
                )
            ),
            version_binding=_version_binding(item),
            resolved_version=_resolved_version(item),
            docs_snapshot_exact=(item.get("docs_snapshot_exact") if isinstance(item.get("docs_snapshot_exact"), bool) else None),
            project_identity=str(item.get("project_identity") or ""),
            module_id=str(item.get("module_id") or ""), doc_scope=str(item.get("doc_scope") or ""),
            symbols=_symbols(item),
            exact_terms=tuple(sorted({str(value) for value in exact_values if str(value).strip()})),
            instruction_risk_flags=_risk_flags(item),
            freshness=str(item.get("freshness") or "current"),
            navigation_only=bool(item.get("navigation_only")) or str(item.get("answer_type") or "") in {
                "navigation_only", "partial_navigational",
            },
            original=item,
        ))
    return candidates, omissions


def select_evidence(
    items: Iterable[Mapping[str, Any]],
    *,
    question: str,
    config: SelectionConfig,
    trust_contract: Mapping[str, Any] | None = None,
    requirements: EvidenceRequirementSet | Sequence[EvidenceRequirement] | None = None,
    required_evidence_paths: Iterable[str] = (),
    required_target_paths: Iterable[str] = (),
    public_requirements: Iterable[Mapping[str, Any] | str] = (),
    library_requirement_contract: Mapping[str, Iterable[str]] | None = None,
    exact_version: str | None = None,
    project_identity: str | None = None,
    module_id: str | None = None,
) -> SelectionDecision:
    materialized_items = [dict(item) for item in items if isinstance(item, Mapping)]
    requirements = (
        requirements if isinstance(requirements, EvidenceRequirementSet) else
        EvidenceRequirementSet(tuple(requirements)) if requirements else
        build_requirements(
            question,
            required_evidence_paths=required_evidence_paths,
            required_target_paths=required_target_paths,
            public_requirements=public_requirements,
            library_requirement_contract=library_requirement_contract,
            exact_version=exact_version,
            project_identity=project_identity,
            module_id=module_id,
            profile=config.profile,
        )
    )
    canonical_project_identity = _scope_requirement_value(requirements, "project_identity")
    canonical_module_id = _scope_requirement_value(requirements, "module_id")
    if isinstance(requirements, EvidenceRequirementSet):
        if project_identity and canonical_project_identity != project_identity:
            raise ValueError("canonical requirements must contain the requested project identity")
        if module_id and canonical_module_id != module_id:
            raise ValueError("canonical requirements must contain the requested module id")
    invalid_provenance = sorted({
        item.public_provenance
        for item in requirements
        if item.public_provenance not in _ALLOWED_REQUIREMENT_PROVENANCE
    })
    if invalid_provenance:
        raise ValueError(
            "unsupported evidence requirement provenance: " + ", ".join(invalid_provenance)
        )
    raw_candidates, omissions = normalize_candidates(
        materialized_items, result_kind=config.result_kind
    )
    eligibility_contract_hash = canonical_hash({
        "trust_contract": _canonical_contract_value(trust_contract or {}),
        "project_identity": project_identity,
        "module_id": module_id,
        "result_kind": config.result_kind,
    })
    identity_bindings: dict[str, tuple[Any, ...]] = {}
    identity_collisions: set[str] = set()
    for candidate in raw_candidates:
        binding = (
            candidate.identity_kind,
            candidate.source_identity,
            candidate.parent_logical_id,
            candidate.content_sha256,
            candidate.symbols,
            candidate.exact_terms,
        )
        previous = identity_bindings.setdefault(candidate.stable_id, binding)
        if previous != binding:
            identity_collisions.add(candidate.stable_id)
    if identity_collisions:
        raw_candidates = [
            candidate for candidate in raw_candidates
            if candidate.stable_id not in identity_collisions
        ]
        omissions.extend(
            Omission(stable_id, "invalid_identity")
            for stable_id in sorted(identity_collisions)
        )
    candidate_trace_hash = canonical_hash([
        {
            "stable_id": item.stable_id,
            "identity_kind": item.identity_kind,
            "content_sha256": item.content_sha256,
            "source_identity": item.source_identity,
            "identity_aliases": list(item.identity_aliases),
            "hydration_id": item.hydration_id,
            "rank": item.retrieval_rank,
            "component_ranks": list(item.component_ranks),
            "relevance_millis": item.relevance_millis,
            "authority": item.authority,
            "source_class": item.source_class,
            "version_binding": item.version_binding,
            "resolved_version": item.resolved_version,
            "docs_snapshot_exact": item.docs_snapshot_exact,
            "project_identity": item.project_identity,
            "module_id": item.module_id,
            "doc_scope": item.doc_scope,
            "symbols": list(item.symbols),
            "exact_terms": list(item.exact_terms),
            "instruction_risk_flags": list(item.instruction_risk_flags),
            "freshness": item.freshness,
            "navigation_only": item.navigation_only,
            "token_estimate": item.token_estimate,
        }
        for item in sorted(raw_candidates, key=lambda row: (
            row.stable_id, row.content_sha256, row.retrieval_rank, row.component_ranks,
        ))
    ] + [{
        "input_trace": sorted(
            (_raw_candidate_binding(item) for item in materialized_items),
            key=canonical_hash,
        ),
        "normalization_omissions": sorted(
            (
                {
                    "stable_id": omission.stable_id,
                    "reason_code": omission.reason_code,
                    "representative_stable_id": omission.representative_stable_id,
                }
                for omission in omissions
            ),
            key=canonical_hash,
        ),
    }])
    eligible, hard_omissions, critical_failures = _eligible_candidates(
        raw_candidates, trust_contract or {}, requirements,
        project_identity=canonical_project_identity, module_id=canonical_module_id,
        result_kind=config.result_kind, question=question,
    )
    omissions.extend(hard_omissions)
    policy_requirements = _with_canonical_policy_requirements(requirements, eligible, config.result_kind)
    if policy_requirements != requirements.requirements:
        requirements = EvidenceRequirementSet(policy_requirements)
    covered = [
        _with_coverage(
            candidate,
            requirements,
            factual_only=(
                config.profile == "project_docs_answer"
                and not any(item.proof_role == "document_statement" for item in requirements)
            ),
        )
        for candidate in eligible
    ]
    mandatory_ids = {item.requirement_id for item in requirements if item.mandatory}
    ordered = sorted(covered, key=lambda candidate: (
        0 if candidate.covered_requirement_ids & mandatory_ids else 1,
        *_candidate_preference(candidate),
    ))
    if len(ordered) > config.max_candidates:
        for candidate in ordered[config.max_candidates:]:
            omissions.append(Omission(candidate.stable_id, "candidate_cap"))
        ordered = ordered[:config.max_candidates]
    deduped, dedupe_omissions = _deduplicate(ordered, config, requirements)
    omissions.extend(dedupe_omissions)
    conflicts = _authority_conflicts(deduped)
    mandatory = {item.requirement_id for item in requirements if item.mandatory}
    selected, missing, selection_omissions = _reserve_and_select(deduped, mandatory, config)
    omissions.extend(selection_omissions)
    selected_documents = {_normalized_source(item.source_identity) for item in selected}
    bounded_materialization_failed = config.result_kind == "docs_answer" and (
        len(selected) > config.max_spans or len(selected_documents) > config.max_documents
    )
    if bounded_materialization_failed:
        missing.add("bounded_evidence_not_materializable")
    missing.update(critical_failures)
    missing.update(f"stable_identity_collision:{value}" for value in identity_collisions)
    if config.result_kind == "docs_answer" and selected and all(item.navigation_only for item in selected):
        missing.add("factual_source_evidence")
    if config.profile == "project_docs_answer" and not mandatory:
        missing.add("project_answer_requirement")
    status: Literal["ok", "insufficient_evidence"] = (
        "ok" if selected and not missing and not conflicts else "insufficient_evidence"
    )
    selected = sorted(selected, key=lambda item: (
        0 if item.covered_requirement_ids & mandatory else 1,
        *_candidate_preference(item),
    ))
    selected_tokens = sum(item.token_estimate for item in selected)
    selected_fit_tokens = sum(item.fit_token_estimate for item in selected)
    metrics = {
        "candidate_count": len(raw_candidates),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "selected_sources": len({_normalized_source(item.source_identity) for item in selected}),
        "selected_documents": len(selected_documents),
        "max_documents": config.max_documents,
        "max_spans": config.max_spans,
        "selected_tokens": selected_tokens,
        "wrapper_reserve_tokens": config.wrapper_reserve_tokens,
        "projected_total_tokens": selected_tokens + config.wrapper_reserve_tokens,
        "serialized_projected_tokens": (
            selected_fit_tokens + DOCS_SERIALIZATION_RESERVE_TOKENS
            if config.result_kind == "docs_answer"
            else selected_tokens + config.wrapper_reserve_tokens
        ),
        "hard_tokens": config.hard_tokens,
        "mandatory_requirements": len(mandatory),
        "mandatory_covered": len(mandatory & set().union(*(
            item.covered_requirement_ids for item in selected
        ))) if selected else 0,
        "mandatory_coverage_millis": int(
            len(mandatory & set().union(*(item.covered_requirement_ids for item in selected)))
            * 1000 / max(1, len(mandatory))
        ) if selected else 0,
        "requirements_hash": requirements.requirements_hash,
        "omission_counts": _count_reasons(omissions),
        "selected_parents": len({item.parent_logical_id for item in selected if item.parent_logical_id}),
        "selected_children": sum(item.identity_kind == "stable_child" for item in selected),
        "required_facts_per_1000_tokens_millis": int(
            len(set().union(*(item.covered_requirement_ids for item in selected)) if selected else set())
            * 1_000_000 / max(1, selected_tokens)
        ),
        "redundant_visible_token_ratio_millis": _redundant_token_ratio_millis(selected, config),
        "cache": "disabled" if not config.cache_enabled else "miss",
        "selected_feature_trace": _selected_feature_trace(selected, mandatory),
        "candidate_to_selected_ratio_millis": int(len(raw_candidates) * 1000 / max(1, len(selected))),
        "reported_token_mismatches": sum(
            1 for item in raw_candidates
            if item.reported_token_estimate is not None
            and item.reported_token_estimate != _estimated_tokens(item.projected_text)
        ),
    }
    sorted_omissions = tuple(sorted(
        omissions,
        key=lambda item: (
            item.stable_id, item.reason_code, item.representative_stable_id or ""
        ),
    ))
    assignments = tuple(
        EvidenceAssignment(
            requirement_id=requirement.requirement_id,
            evidence_id=candidate.stable_id,
            path=candidate.path_or_url,
            char_start=candidate.char_start,
            char_end=candidate.char_end,
            line_start=candidate.line_start,
            line_end=candidate.line_end,
            projected_content_hash=hashlib.sha256(
                candidate.projected_text.encode("utf-8")
            ).hexdigest(),
            proof_role=requirement.proof_role,
            qualifiers=requirement.qualifiers or _observed_qualifiers(candidate.projected_text),
        )
        for requirement in sorted(
            (item for item in requirements if item.requirement_id in mandatory),
            key=lambda item: item.requirement_id,
        )
        for candidate in [next(
            (
                item for item in sorted(selected, key=lambda item: item.stable_id)
                if requirement.requirement_id in item.covered_requirement_ids
            ),
            None,
        )]
        if candidate is not None
    )
    assigned_requirement_ids = {item.requirement_id for item in assignments}
    missing.update(mandatory - assigned_requirement_ids)
    if status == "ok" and mandatory - assigned_requirement_ids:
        status = "insufficient_evidence"
    assignment_hash = canonical_hash([asdict(item) for item in assignments])
    selection_hash = canonical_hash({
        "schema_version": SELECTOR_SCHEMA_VERSION,
        "config_hash": config.config_hash,
        "eligibility_contract_hash": eligibility_contract_hash,
        "candidate_trace_hash": candidate_trace_hash,
        "requirements": requirements.hash_payload,
        "selected": [_selected_identity(item) for item in selected],
        "assignments": [asdict(item) for item in assignments],
        "omissions": [asdict(item) for item in sorted_omissions],
        "missing": sorted(missing), "conflicts": sorted(conflicts),
    })
    covered_ids = (
        set().union(*(item.covered_requirement_ids for item in selected))
        if selected else set()
    )
    covered_mandatory = mandatory & covered_ids
    mandatory_coverage = (
        len(covered_mandatory) / len(mandatory)
        if mandatory else (1.0 if selected else 0.0)
    )
    public_missing = tuple(sorted(missing))
    public_satisfied = tuple(sorted(covered_ids))
    public_mandatory = tuple(sorted(mandatory))
    reason_code = (
        None if status == "ok" else
        "bounded_evidence_not_materializable" if bounded_materialization_failed else
        "authority_conflict" if conflicts else
        "required_evidence_missing" if missing else
        "no_eligible_evidence"
    )
    support_payload = {
        "answer_supported": status == "ok",
        "support_status": "supported" if status == "ok" else "insufficient_evidence",
        "reason_code": reason_code,
        "missing_requirement_ids": public_missing,
        "satisfied_requirement_ids": public_satisfied,
        "mandatory_requirement_ids": public_mandatory,
        "mandatory_coverage": mandatory_coverage,
        "selected_evidence_ids": tuple(item.stable_id for item in selected),
        "requirements_hash": requirements.requirements_hash,
        "selector_config_hash": config.config_hash,
        "eligibility_contract_hash": eligibility_contract_hash,
        "candidate_trace_hash": candidate_trace_hash,
        "selection_hash": selection_hash,
        "assignment_hash": assignment_hash,
    }
    support_decision = SupportDecision(
        **support_payload,
        decision_hash=canonical_hash(support_payload),
        requirements=requirements,
    )
    return SelectionDecision(
        status=status, selected_candidates=tuple(selected), omissions=sorted_omissions,
        missing_requirements=tuple(sorted(missing)), unresolved_conflicts=tuple(sorted(conflicts)),
        metrics=metrics, selector_config_hash=config.config_hash,
        eligibility_contract_hash=eligibility_contract_hash,
        candidate_trace_hash=candidate_trace_hash, selection_hash=selection_hash,
        assignments=assignments, support_decision=support_decision, requirements=requirements,
    )


def validate_evidence_sufficiency(
    decision: SelectionDecision,
    requirements: EvidenceRequirementSet | Sequence[EvidenceRequirement] = (),
    *,
    result_kind: str | None = None,
) -> list[str]:
    errors: list[str] = []
    requirements = (
        requirements if isinstance(requirements, EvidenceRequirementSet) else
        EvidenceRequirementSet(tuple(requirements)) if requirements else
        decision.requirements
    )
    mandatory = {item.requirement_id for item in requirements if item.mandatory}
    covered = set().union(*(item.covered_requirement_ids for item in decision.selected_candidates)) if decision.selected_candidates else set()
    if decision.status == "ok" and not decision.selected_candidates:
        errors.append("successful selection requires evidence")
    if decision.status == "ok" and mandatory - covered:
        errors.append("successful selection is missing mandatory requirements")
    assigned = {item.requirement_id for item in decision.assignments}
    if decision.status == "ok" and mandatory - assigned:
        errors.append("successful selection is missing mandatory assignments")
    if decision.status == "ok" and (decision.missing_requirements or decision.unresolved_conflicts):
        errors.append("successful selection cannot contain unresolved requirements or conflicts")
    if len({item.stable_id for item in decision.selected_candidates}) != len(decision.selected_candidates):
        errors.append("selected stable IDs must be unique")
    if len({(item.stable_id, item.content_sha256) for item in decision.selected_candidates}) != len(decision.selected_candidates):
        errors.append("selected stable identity bindings must be unique")
    if decision.metrics.get("projected_total_tokens", 0) > decision.metrics.get("hard_tokens", 0):
        errors.append("selected whole-item bundle exceeds the hard token budget")
    if result_kind == "docs_answer" and decision.status == "ok" and all(
        item.navigation_only for item in decision.selected_candidates
    ):
        errors.append("successful docs selection requires factual evidence")
    if result_kind == "patch_context" and decision.status == "ok" and not any(
        item.symbols or _PATCH_FACT_RE.search(item.display_text)
        for item in decision.selected_candidates
    ):
        errors.append("successful patch selection requires actionable cited evidence")
    expected = canonical_hash({
        "schema_version": SELECTOR_SCHEMA_VERSION,
        "config_hash": decision.selector_config_hash,
        "eligibility_contract_hash": decision.eligibility_contract_hash,
        "candidate_trace_hash": decision.candidate_trace_hash,
        "requirements": requirements.hash_payload,
        "selected": [_selected_identity(item) for item in decision.selected_candidates],
        "assignments": [asdict(item) for item in decision.assignments],
        "omissions": [asdict(item) for item in decision.omissions],
        "missing": list(decision.missing_requirements),
        "conflicts": list(decision.unresolved_conflicts),
    })
    if expected != decision.selection_hash:
        errors.append("selection hash does not match the decision")
    return errors


def _scope_requirement_value(
    requirements: Sequence[EvidenceRequirement], kind: str,
) -> str | None:
    values = {item.value for item in requirements if item.kind == kind and item.mandatory}
    if len(values) > 1:
        raise ValueError(f"canonical requirements contain conflicting {kind} scope")
    return next(iter(values), None)


def _eligible_candidates(
    candidates: Sequence[EvidenceCandidate],
    trust_contract: Mapping[str, Any],
    requirements: Sequence[EvidenceRequirement],
    *,
    project_identity: str | None,
    module_id: str | None,
    result_kind: str,
    question: str,
) -> tuple[list[EvidenceCandidate], list[Omission], set[str]]:
    forbidden = _trust_source_keys(trust_contract, "rejected") | _trust_source_keys(trust_contract, "risky")
    exact_versions = {item.value for item in requirements if item.kind == "exact_version" and item.mandatory}
    canonical_policy_required = any(
        item.kind == "canonical_policy" and item.mandatory for item in requirements
    )
    legal_intent = bool(
        set(_TOKEN_RE.findall(question.casefold())).intersection(_LEGAL_INTENT_TERMS)
    )
    query_identifiers = _query_identifier_values(requirements)
    eligible: list[EvidenceCandidate] = []
    omissions: list[Omission] = []
    critical: set[str] = set()
    for candidate in candidates:
        reason: OmissionReason | None = None
        if set(candidate.identity_aliases) & forbidden:
            reason = "forbidden_source"
        elif candidate.freshness.casefold() == "stale":
            reason = "stale"
            if candidate.authority == "canonical":
                critical.add("stale_canonical_evidence")
        elif candidate.instruction_risk_flags:
            reason = "instruction_risk"
            if candidate.authority == "canonical":
                critical.add("risky_canonical_evidence")
        elif canonical_policy_required and candidate.source_class.casefold() in {
            "generated", "changelog", "research", "community", "mirror",
        }:
            reason = "outside_scope"
        elif project_identity and candidate.project_identity != project_identity:
            reason = "outside_scope"
        elif module_id and candidate.module_id != module_id:
            reason = "outside_scope"
        elif exact_versions and _version_rank(candidate.version_binding) == 2:
            reason = "unknown_version"
        elif exact_versions and candidate.resolved_version not in exact_versions:
            reason = "wrong_version"
        elif result_kind == "docs_answer" and candidate.navigation_only:
            reason = "navigation_only"
        elif (
            candidate.source_class.casefold() == "legal"
            and not legal_intent
        ):
            reason = "query_intent_mismatch"
        elif _query_identifier_conflict(candidate, query_identifiers):
            reason = "query_identifier_conflict"
        if reason:
            omissions.append(Omission(candidate.stable_id, reason))
        else:
            eligible.append(candidate)
    return eligible, omissions, critical


def _query_identifier_conflict(
    candidate: EvidenceCandidate,
    query_identifiers: Sequence[str],
) -> bool:
    """Reject prefix lookalikes without excluding unrelated supporting evidence."""

    haystack = "\n".join((candidate.display_text, *candidate.symbols)).casefold()
    for value in query_identifiers:
        exact_match = False
        prefix_match = False
        start = haystack.find(value)
        while start >= 0:
            before = haystack[start - 1] if start else ""
            after_index = start + len(value)
            after = haystack[after_index] if after_index < len(haystack) else ""
            if not (before == "_" or before.isalnum()):
                if after == "_" or after.isalnum():
                    prefix_match = True
                else:
                    exact_match = True
                    break
            start = haystack.find(value, start + 1)
        if prefix_match and not exact_match:
            return True
    return False


def _query_identifier_values(
    requirements: Sequence[EvidenceRequirement],
) -> tuple[str, ...]:
    return tuple(
        requirement.value.casefold()
        for requirement in requirements
        if requirement.public_provenance == "query_exact_term"
        and (
            "_" in requirement.value
            or "." in requirement.value
            or "::" in requirement.value
            or (
                any(char.isupper() for char in requirement.value[1:])
                and any(char.islower() for char in requirement.value)
            )
        )
    )


def _trust_source_keys(contract: Mapping[str, Any], field: str) -> set[str]:
    sources = contract.get("sources") if isinstance(contract.get("sources"), Mapping) else {}
    aliases = [field, f"{field}_sources"]
    values: list[Any] = []
    for key in aliases:
        for raw in (contract.get(key), sources.get(key)):
            values.extend(raw if isinstance(raw, list) else [raw] if raw else [])
    return {
        _normalized_source(
            value.get("source") or value.get("path") or value.get("url")
            or value.get("canonical_id") or value.get("library_id") or ""
            if isinstance(value, Mapping) else value
        )
        for value in values
        if _normalized_source(
            value.get("source") or value.get("path") or value.get("url")
            or value.get("canonical_id") or value.get("library_id") or ""
            if isinstance(value, Mapping) else value
        )
    }


def _facet_requirement_matches(value: str, haystack: str) -> bool:
    kind, _, detail = value.partition(":")
    if kind == "comparison":
        left, separator, right = detail.partition(":")
        return bool(
            separator
            and requirement_value_visible(left, haystack)
            and requirement_value_visible(right, haystack)
            and (
                re.search(r"\b(?:while|whereas|but|instead|compare|difference|versus|vs\.?|unlike|does\s+not)\b", haystack)
                or re.search(r"\breturns?\b.*\b(?:runs|collects|schedules)\b", haystack)
            )
        )
    if kind == "result_access":
        entity, separator, _ = detail.partition(":")
        return bool(
            separator
            and requirement_value_visible(entity, haystack)
            and "result" in haystack
            and re.search(r"\b(?:obtain|get|retrieve|await)\b", haystack)
        )
    if kind == "request_handling":
        return any(
            re.search(r"\brequest\b|\bзапрос", sentence)
            and re.search(r"\b(?:handles?|process(?:es|ing)?|dispatch(?:es|ing)?|routes?|validates?|forwards?)\b", sentence)
            and re.search(r"\b(?:handler|router|server|tool|transport|service|registry)\b", sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind == "architecture":
        component_pattern = (
            r"\b(?:server|handler|router|service|transport|registry|adapter|layer|module|"
            r"ui|application|domain|infrastructure)\b"
        )
        relation_pattern = (
            r"\b(?:routes?|dispatch(?:es)?|coordinates?|connects?|composes?|through|"
            r"состоит|связывает)\b|->"
        )
        return any(
            len(set(re.findall(component_pattern, sentence))) >= 2
            and re.search(relation_pattern, sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind == "responsiveness":
        return any(
            re.search(r"\b(?:non[- ]blocking|asynchronous|async|does\s+not\s+block)\b", sentence)
            and re.search(r"\b(?:worker|background|event\s+loop|queue|thread|task)\b", sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind in {"behavior", "usage", "workflow"}:
        patterns = {
            "behavior": r"\b(?:reports?|returns?|provides?|shows?|contains?|lists?|возвращает|показывает|сообщает|содержит|перечисляет)\b",
            "usage": r"\b(?:use|used|call|called|when|should|использовать|используется|применять|применяется|когда)\b",
            "workflow": r"\b(?:run|follow|then|after|before|retry|prepare|first|next|запустить|выполнить|затем|после|перед|повторить|сначала)\b",
        }
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack):
            if not requirement_value_visible(detail, sentence):
                continue
            if re.search(
                r"\b(?:does|do|did|is|are|was|were|should|must|can|could|would|will)\s+not\b"
                r"|\b(?:never|cannot|can't|mustn't|shouldn't)\b"
                r"|\b(?:не\s+следует|не\s+нужно|нельзя|никогда\s+не)\b",
                sentence,
            ):
                continue
            entity_pattern = re.escape(detail.casefold())
            marker_pattern = patterns[kind]
            if kind == "behavior":
                relational_match = re.search(
                    rf"{entity_pattern}(?:\W+\w+){{0,6}}?\W+{marker_pattern}", sentence,
                )
            else:
                relational_match = re.search(
                    rf"(?:{entity_pattern}(?:\W+\w+){{0,6}}?\W+{marker_pattern}"
                    rf"|{marker_pattern}(?:\W+\w+){{0,6}}?\W+{entity_pattern})",
                    sentence,
                )
            if kind == "workflow":
                markers = re.findall(marker_pattern, sentence)
                has_sequence = re.search(
                    r"\b(?:then|after|before|first|next|затем|после|перед|сначала)\b",
                    sentence,
                )
                relational_match = bool(relational_match and len(markers) >= 2 and has_sequence)
            if relational_match:
                return True
        return False
    if kind == "recall_mechanism":
        return bool(re.search(r"\b(?:exact[- ]term|exact match|exact query)\b", haystack) and re.search(
            r"\b(?:recall|retrieve|retrieval|match|lookup)\b", haystack,
        ))
    if kind == "authority_invariant":
        return bool(re.search(r"\b(?:authority|scope)\b", haystack) and re.search(
            r"\b(?:unchanged|preserv(?:e|es|ed)|without\s+(?:widening|expanding|broadening)|does\s+not\s+(?:widen|expand|broaden))\b",
            haystack,
        ))
    return False


def _code_group_fragments(value: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(
        str(fragment).strip()
        for fragment in decoded
        if str(fragment).strip()
    )


def _candidate_code_blocks(candidate: EvidenceCandidate) -> tuple[str, ...]:
    metadata = candidate.original.get("metadata")
    snippets = metadata.get("code_snippets") if isinstance(metadata, Mapping) else None
    if not isinstance(snippets, (list, tuple)):
        snippets = ()
    blocks = [
        str(item.get("code") or "").strip()
        for item in snippets or ()
        if isinstance(item, Mapping) and str(item.get("code") or "").strip()
    ]
    if blocks:
        return tuple(blocks)
    return tuple(match.group(1).strip() for match in re.finditer(
        r"```[^\n]*\n(.*?)```", candidate.display_text, re.DOTALL,
    ) if match.group(1).strip())


def _code_group_requirement_matches(value: str, candidate: EvidenceCandidate) -> bool:
    fragments = _code_group_fragments(value)
    return bool(fragments) and any(
        all(fragment.casefold() in block.casefold() for fragment in fragments)
        for block in _candidate_code_blocks(candidate)
    )


def requirement_probe_query(requirement: EvidenceRequirement) -> str | None:
    """Return a bounded lexical witness query for one canonical requirement."""

    if requirement.kind in {"exact_term", "entity"}:
        return requirement.value.strip() or None
    if requirement.kind == "facet":
        kind, _, detail = requirement.value.partition(":")
        if kind == "comparison":
            left, separator, right = detail.partition(":")
            return f"{left} {right}" if separator else None
        if kind == "result_access":
            entity, separator, _ = detail.partition(":")
            return f"{entity} result" if separator else None
    if requirement.kind == "code_group":
        fragments = _code_group_fragments(requirement.value)
        return " ".join(fragments) if fragments else None
    return None


def _with_coverage(
    candidate: EvidenceCandidate,
    requirements: Sequence[EvidenceRequirement],
    *,
    factual_only: bool,
) -> EvidenceCandidate:
    # Paths, headings, and symbols aid retrieval but cannot prove a factual
    # answer. Requirements must match model-visible source text.
    haystack = candidate.display_text.casefold() if factual_only else "\n".join([
        candidate.display_text, candidate.path_or_url, candidate.section,
        " ".join(candidate.symbols), candidate.version_binding, candidate.resolved_version,
    ]).casefold()
    stripped_display = candidate.display_text.strip()
    display_words = re.findall(r"\w+", stripped_display, re.UNICODE)
    incomplete_span = factual_only and bool(
        len(stripped_display) <= 80
        and "\n" not in stripped_display
        and (
            re.fullmatch(r"#{1,6}\s+\S.*", stripped_display) is not None
            or
            stripped_display.endswith(':')
            or (len(display_words) <= 2 and not re.search(r"[.!?;]", stripped_display))
        )
    )
    source = _normalized_source(candidate.path_or_url)
    covered: set[str] = set()
    for requirement in requirements:
        value = requirement.value.casefold()
        if requirement.kind == "canonical_policy":
            matches = candidate.stable_id == requirement.value
        elif requirement.kind in {"evidence_path", "target_path"}:
            wanted = _normalized_source(requirement.value)
            matches = source == wanted or source.endswith("/" + wanted) or wanted.endswith("/" + source)
        elif requirement.kind == "exact_version":
            matches = candidate.resolved_version.casefold() == value and _version_rank(candidate.version_binding) == 0
        elif requirement.kind == "exact_snapshot":
            matches = candidate.docs_snapshot_exact is True
        elif requirement.kind == "project_identity":
            matches = candidate.project_identity == requirement.value
        elif requirement.kind == "module_id":
            matches = candidate.module_id == requirement.value
        elif requirement.kind == "exact_term":
            matches = requirement_value_visible(requirement.value, haystack)
        elif requirement.kind == "entity":
            matches = requirement_value_visible(requirement.value, haystack)
        elif requirement.kind == "facet":
            matches = _facet_requirement_matches(requirement.value, haystack)
        elif requirement.kind == "code_group":
            matches = _code_group_requirement_matches(requirement.value, candidate)
        elif requirement.kind == "unsupported_query":
            matches = False
        else:
            matches = value in haystack
        if matches and incomplete_span and requirement.kind not in {"evidence_path", "target_path"}:
            matches = False
        if matches and requirement.proof_role == "document_statement":
            scoped_paths = {
                _normalized_source(item.value)
                for item in requirements
                if item.kind == "evidence_path"
            }
            matches = bool(scoped_paths) and source in scoped_paths
        if matches and requirement.proof_role == "implementation_fact":
            matches = candidate.source_class in {"source_snippet", "test", "project_file"}
        if matches and requirement.proof_role == "project_rule":
            matches = candidate.authority == "canonical" and candidate.source_class not in {
                "repo_map", "code_graph", "absent_in_source",
            }
        if matches and requirement.proof_role == "dependency_fact":
            matches = candidate.source_class not in {
                "repo_map", "code_graph", "absent_in_source", "project_file", "source_snippet", "test",
            } and _version_rank(candidate.version_binding) == 0
        if matches and requirement.qualifiers:
            matches = all(
                _QUALIFIER_PATTERNS[qualifier].search(candidate.projected_text)
                for qualifier in requirement.qualifiers
            )
        if matches:
            covered.add(requirement.requirement_id)
    return replace(candidate, covered_requirement_ids=frozenset(covered))


def _with_canonical_policy_requirements(
    requirements: Sequence[EvidenceRequirement],
    candidates: Sequence[EvidenceCandidate],
    result_kind: str,
) -> tuple[EvidenceRequirement, ...]:
    if result_kind != "patch_context":
        return tuple(requirements)
    additions = [
        EvidenceRequirement(
            requirement_id=f"canonical_policy:{candidate.stable_id}",
            kind="canonical_policy",
            value=candidate.stable_id,
            public_provenance="canonical_policy_requirement",
        )
        for candidate in candidates
        if candidate.authority == "canonical"
        and str(candidate.original.get("authority") or "").casefold() in {
            "source_of_truth", "project_rule", "explicit_agent_policy",
        }
        and _PATCH_FACT_RE.search(candidate.display_text)
    ]
    unique = {item.requirement_id: item for item in (*requirements, *additions)}
    return tuple(unique[key] for key in sorted(unique))


def _candidate_preference(candidate: EvidenceCandidate) -> tuple[Any, ...]:
    return (
        0 if candidate.authority == "canonical" else 1,
        _version_rank(candidate.version_binding),
        0 if candidate.docs_snapshot_exact is True else 1,
        -len(candidate.covered_requirement_ids),
        candidate.token_estimate,
        -candidate.relevance_millis,
        candidate.retrieval_rank,
        candidate.stable_id,
    )


def _deduplicate(
    candidates: Sequence[EvidenceCandidate],
    config: SelectionConfig,
    requirements: Sequence[EvidenceRequirement],
) -> tuple[list[EvidenceCandidate], list[Omission]]:
    selected: list[EvidenceCandidate] = []
    omissions: list[Omission] = []
    for candidate in candidates:
        duplicate: tuple[OmissionReason, EvidenceCandidate] | None = None
        for representative in selected:
            distinct_versions = bool(
                candidate.resolved_version
                and representative.resolved_version
                and candidate.resolved_version.casefold() != representative.resolved_version.casefold()
            )
            if distinct_versions:
                continue
            if _policy_polarity(candidate.display_text) != _policy_polarity(representative.display_text):
                continue
            has_new_symbols = bool(set(candidate.symbols) - set(representative.symbols))
            if candidate.stable_id == representative.stable_id or (
                candidate.parent_logical_id
                and candidate.parent_logical_id == representative.parent_logical_id
                and candidate.content_sha256 == representative.content_sha256
                and not has_new_symbols
            ):
                duplicate = "exact_duplicate", representative
                break
            if (
                _overlap_millis(candidate, representative) >= config.overlap_threshold
                and not (candidate.covered_requirement_ids - representative.covered_requirement_ids)
                and not has_new_symbols
            ):
                duplicate = "overlap_duplicate", representative
                break
            if (
                _normalized_source(candidate.source_identity) == _normalized_source(representative.source_identity)
                and _jaccard_millis(candidate.display_text, representative.display_text, config.shingle_size)
                >= config.near_duplicate_threshold
                and not (candidate.covered_requirement_ids - representative.covered_requirement_ids)
                and not has_new_symbols
            ):
                duplicate = "near_duplicate", representative
                break
        if duplicate:
            omissions.append(Omission(candidate.stable_id, duplicate[0], duplicate[1].stable_id))
        else:
            selected.append(candidate)
    return selected, omissions


def _selected_identity(candidate: EvidenceCandidate) -> dict[str, Any]:
    return {
        "stable_id": candidate.stable_id,
        "content_sha256": candidate.content_sha256,
        "source_identity": candidate.source_identity,
        "parent_logical_id": candidate.parent_logical_id,
        "projected_content_sha256": hashlib.sha256(
            candidate.projected_text.encode("utf-8")
        ).hexdigest(),
    }


def _raw_candidate_binding(item: Mapping[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
    display = _display_text(item)
    score = next((
        value for value in (
            item.get("score"), item.get("relevance_score"),
            metadata.get("score"), metadata.get("relevance_score"),
        )
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ), None)
    return {
        "stable_id": str(
            item.get("stable_chunk_id") or item.get("stable_child_id")
            or metadata.get("stable_chunk_id") or item.get("stable_id") or ""
        ),
        "path_or_url": _source_path(item),
        "parent_logical_id": str(
            item.get("parent_logical_id") or metadata.get("parent_logical_id") or ""
        ),
        "display_content_sha256": hashlib.sha256(display.encode("utf-8")).hexdigest(),
        "supplied_display_content_hash": str(item.get("display_content_hash") or ""),
        "retrieval_rank": _positive_int(
            item.get("retrieval_rank") if item.get("retrieval_rank") is not None else item.get("rank"),
            default=10_000,
        ),
        "relevance_millis": int(round(float(score) * 1000)) if score is not None else 0,
        "symbols": sorted(_symbols(item)),
        "exact_terms": sorted(
            str(value)
            for value in (
                item.get("exact_terms")
                if isinstance(item.get("exact_terms"), (list, tuple, set))
                else [item.get("exact_terms")] if item.get("exact_terms") else []
            )
        ),
        "project_identity": str(item.get("project_identity") or ""),
        "module_id": str(item.get("module_id") or ""),
        "doc_scope": str(item.get("doc_scope") or ""),
    }


def _canonical_contract_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_contract_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_canonical_contract_value(item) for item in value), key=canonical_hash
        )
    if isinstance(value, (list, tuple)):
        return [_canonical_contract_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _policy_polarity(value: str) -> str:
    lowered = value.casefold()
    if re.search(r"\b(?:must\s+not|do\s+not|never|forbidden|prohibited)\b", lowered):
        return "forbidden"
    if re.search(r"\b(?:must|required|shall)\b", lowered):
        return "required"
    return "neutral"


def _overlap_millis(left: EvidenceCandidate, right: EvidenceCandidate) -> int:
    if not left.parent_logical_id or left.parent_logical_id != right.parent_logical_id:
        return 0
    if None in {left.char_start, left.char_end, right.char_start, right.char_end}:
        return 0
    intersection = max(0, min(left.char_end, right.char_end) - max(left.char_start, right.char_start))
    denominator = min(left.char_end - left.char_start, right.char_end - right.char_start)
    return int(intersection * 1000 / denominator) if denominator > 0 else 0


def _shingles(value: str, size: int) -> set[tuple[str, ...]]:
    tokens = [token.casefold() for token in _TOKEN_RE.findall(" ".join(value.split()))]
    if not tokens:
        return set()
    if len(tokens) < size:
        return {tuple(tokens)}
    return {tuple(tokens[index:index + size]) for index in range(len(tokens) - size + 1)}


def _jaccard_millis(left: str, right: str, size: int) -> int:
    left_set, right_set = _shingles(left, size), _shingles(right, size)
    union = left_set | right_set
    return int(len(left_set & right_set) * 1000 / len(union)) if union else 0


def _reserve_and_select(
    candidates: Sequence[EvidenceCandidate],
    mandatory: set[str],
    config: SelectionConfig,
) -> tuple[list[EvidenceCandidate], set[str], list[Omission]]:
    fit_reserve = (
        DOCS_SERIALIZATION_RESERVE_TOKENS
        if config.result_kind == "docs_answer"
        else config.wrapper_reserve_tokens
    )
    available = max(1, config.hard_tokens - fit_reserve)
    selected: list[EvidenceCandidate] = []
    remaining = set(mandatory)
    pool = list(candidates)
    omissions: list[Omission] = []
    while remaining:
        options = [candidate for candidate in pool if candidate.covered_requirement_ids & remaining]
        if not options:
            break
        best = min(options, key=lambda candidate: (
            -len(candidate.covered_requirement_ids & remaining),
            0 if candidate.authority == "canonical" else 1,
            _version_rank(candidate.version_binding),
            0 if candidate.docs_snapshot_exact is True else 1,
            candidate.token_estimate,
            candidate.retrieval_rank,
            candidate.stable_id,
        ))
        selected.append(best)
        pool.remove(best)
        remaining -= best.covered_requirement_ids
    selected = _repair_mandatory_selection(selected, candidates, mandatory)
    covered_after_repair = set().union(*(
        item.covered_requirement_ids for item in selected
    )) if selected else set()
    remaining = mandatory - covered_after_repair
    selected_ids = {item.stable_id for item in selected}
    pool = [item for item in candidates if item.stable_id not in selected_ids]
    if sum(item.fit_token_estimate for item in selected) > available:
        remaining.add("mandatory_evidence_does_not_fit")
        for candidate in candidates:
            omissions.append(Omission(candidate.stable_id, "budget"))
        return [], remaining, omissions

    spent = sum(item.fit_token_estimate for item in selected)
    selected_sources = {_normalized_source(item.source_identity) for item in selected}
    source_counts: dict[str, int] = {}
    for item in selected:
        key = _normalized_source(item.source_identity)
        source_counts[key] = source_counts.get(key, 0) + 1
    selected_terms = _selection_terms(selected)
    if config.result_kind == "docs_answer" and mandatory and not remaining:
        omissions.extend(Omission(candidate.stable_id, "dominated") for candidate in pool)
        return selected, remaining, omissions
    while pool:
        scored: list[tuple[tuple[Any, ...], EvidenceCandidate, int]] = []
        selected_coverage = set().union(*(
            item.covered_requirement_ids for item in selected
        )) if selected else set()
        selected_symbols = {symbol for item in selected for symbol in item.symbols}
        selected_cost = sum(item.token_estimate for item in selected)
        for candidate in pool:
            if (
                candidate.covered_requirement_ids
                and candidate.covered_requirement_ids <= selected_coverage
                and candidate.token_estimate >= selected_cost
                and not (set(candidate.symbols) - selected_symbols)
            ):
                omissions.append(Omission(candidate.stable_id, "dominated"))
                continue
            source_key = _normalized_source(candidate.source_identity)
            is_mandatory = bool(candidate.covered_requirement_ids & mandatory)
            if not is_mandatory and source_key not in selected_sources and len(selected_sources) >= config.max_sources:
                continue
            if not is_mandatory and source_counts.get(source_key, 0) >= config.max_items_per_source:
                continue
            utility = _marginal_utility(candidate, selected_terms, set())
            ratio = int(utility * 100 / max(1, candidate.token_estimate))
            scored.append(((-ratio, -utility, *_candidate_preference(candidate)), candidate, ratio))
        omitted_ids = {item.stable_id for item in omissions}
        pool = [item for item in pool if item.stable_id not in omitted_ids]
        if not scored:
            break
        _, best, utility_ratio = min(scored, key=lambda row: row[0])
        pool.remove(best)
        source_key = _normalized_source(best.source_identity)
        if utility_ratio < config.marginal_utility_threshold:
            omissions.append(Omission(best.stable_id, "zero_marginal_utility"))
            continue
        if spent + best.fit_token_estimate > available:
            omissions.append(Omission(best.stable_id, "budget"))
            continue
        selected.append(best)
        spent += best.fit_token_estimate
        selected_sources.add(source_key)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        selected_terms = _selection_terms(selected)
        if spent >= min(available, config.target_tokens - config.wrapper_reserve_tokens):
            break
    selected_ids = {item.stable_id for item in selected}
    omitted_ids = {item.stable_id for item in omissions}
    for candidate in candidates:
        if candidate.stable_id in selected_ids or candidate.stable_id in omitted_ids:
            continue
        source_key = _normalized_source(candidate.source_identity)
        reason: OmissionReason = (
            "source_cap"
            if source_counts.get(source_key, 0) >= config.max_items_per_source
            or (source_key not in selected_sources and len(selected_sources) >= config.max_sources)
            else "dominated"
        )
        omissions.append(Omission(candidate.stable_id, reason))
    return selected, remaining, omissions


def _repair_mandatory_selection(
    selected: Sequence[EvidenceCandidate],
    candidates: Sequence[EvidenceCandidate],
    mandatory: set[str],
) -> list[EvidenceCandidate]:
    """One bounded 1/2-item replacement pass for a smaller complete cover."""

    if not selected or not mandatory:
        return list(selected)
    current = list(selected)
    current_ids = {item.stable_id for item in current}
    pool = [item for item in candidates if item.stable_id not in current_ids]

    def complete(rows: Sequence[EvidenceCandidate]) -> bool:
        coverage = set().union(*(item.covered_requirement_ids for item in rows)) if rows else set()
        return mandatory <= coverage

    def quality(rows: Sequence[EvidenceCandidate]) -> tuple[Any, ...]:
        return (
            sum(item.authority != "canonical" for item in rows),
            sum(_version_rank(item.version_binding) for item in rows),
            sum(item.token_estimate for item in rows),
            len(rows),
            tuple(sorted(item.stable_id for item in rows)),
        )

    best, best_quality = current, quality(current)
    removals = [combo for size in (1, 2) for combo in itertools.combinations(current, min(size, len(current)))]
    additions = [combo for size in (1, 2) for combo in itertools.combinations(pool, min(size, len(pool)))]
    for removed in removals:
        retained = [item for item in current if item not in removed]
        for added in additions:
            proposal = [*retained, *added]
            proposal_quality = quality(proposal)
            if complete(proposal) and proposal_quality < best_quality:
                best, best_quality = proposal, proposal_quality
    return best


def _selection_terms(candidates: Sequence[EvidenceCandidate]) -> set[str]:
    return {
        token.casefold()
        for candidate in candidates
        for token in _TOKEN_RE.findall(candidate.display_text)
        if len(token) > 2
    }


def _marginal_utility(candidate: EvidenceCandidate, selected_terms: set[str], mandatory: set[str]) -> int:
    terms = {token.casefold() for token in _TOKEN_RE.findall(candidate.display_text) if len(token) > 2}
    novelty = min(80, len(terms - selected_terms) * 4)
    return (
        len(candidate.covered_requirement_ids & mandatory) * 1000
        + len(candidate.covered_requirement_ids) * 180
        + (220 if candidate.authority == "canonical" else 40)
        + (120 if _version_rank(candidate.version_binding) == 0 else 20)
        + (80 if candidate.docs_snapshot_exact is True else 0)
        + (80 if candidate.projected_text.strip() else 0)
        + min(100, max(0, candidate.relevance_millis // 10))
        + (60 if candidate.symbols else 0)
        + novelty
        - (80 if candidate.navigation_only else 0)
    )


def _selected_feature_trace(
    candidates: Sequence[EvidenceCandidate], mandatory: set[str]
) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    prior_terms: set[str] = set()
    prior_sources: set[str] = set()
    prior_modules: set[str] = set()
    prior_symbols: set[str] = set()
    for candidate in candidates:
        terms = {token.casefold() for token in _TOKEN_RE.findall(candidate.display_text) if len(token) > 2}
        source = _normalized_source(candidate.source_identity)
        symbols = set(candidate.symbols)
        trace.append({
            "stable_id": candidate.stable_id,
            "retrieval_relevance": candidate.relevance_millis,
            "exact_term_coverage": len(candidate.covered_requirement_ids),
            "mandatory_requirement_coverage": len(candidate.covered_requirement_ids & mandatory),
            "authority": 1000 if candidate.authority == "canonical" else 250,
            "version_exactness": 1000 if _version_rank(candidate.version_binding) == 0 else 0,
            "usable_snippet": 1000 if candidate.projected_text.strip() else 0,
            "new_source_fact_terms": len(terms - prior_terms),
            "new_module_coverage": int(bool(candidate.module_id and candidate.module_id not in prior_modules)),
            "new_target_symbols": len(symbols - prior_symbols),
            "new_source": int(bool(source and source not in prior_sources)),
            "novelty_millis": int(len(terms - prior_terms) * 1000 / max(1, len(terms))),
            "token_cost": candidate.token_estimate,
            "expansion_cost": 0,
            "stale_risk": int(candidate.freshness.casefold() == "stale"),
            "generic_source_penalty": int(candidate.authority != "canonical"),
            "ambiguity_penalty": int(candidate.navigation_only),
        })
        prior_terms.update(terms)
        prior_sources.add(source)
        if candidate.module_id:
            prior_modules.add(candidate.module_id)
        prior_symbols.update(symbols)
    return trace


def _redundant_token_ratio_millis(
    candidates: Sequence[EvidenceCandidate], config: SelectionConfig
) -> int:
    redundant = 0
    accepted: list[EvidenceCandidate] = []
    for candidate in candidates:
        if any(
            _jaccard_millis(candidate.display_text, previous.display_text, config.shingle_size)
            >= config.near_duplicate_threshold
            for previous in accepted
        ):
            redundant += candidate.token_estimate
        accepted.append(candidate)
    total = sum(item.token_estimate for item in candidates)
    return int(redundant * 1000 / total) if total else 0


def _authority_conflicts(candidates: Sequence[EvidenceCandidate]) -> set[str]:
    required: dict[str, set[str]] = {}
    forbidden: dict[str, set[str]] = {}
    for candidate in candidates:
        if candidate.authority != "canonical":
            continue
        for line in candidate.display_text.splitlines():
            normalized = " ".join(re.findall(r"[\w]+", line.casefold()))
            if "must not" in line.casefold() or "never" in line.casefold() or "forbidden" in line.casefold():
                key = re.sub(r"\b(?:must|not|never|forbidden|be)\b", " ", normalized)
                forbidden.setdefault(" ".join(key.split()), set()).add(candidate.stable_id)
            elif "must" in line.casefold() or "required" in line.casefold():
                key = re.sub(r"\b(?:must|required|be)\b", " ", normalized)
                required.setdefault(" ".join(key.split()), set()).add(candidate.stable_id)
    return {
        key for key in required.keys() & forbidden.keys() if key
    }


def _count_reasons(omissions: Sequence[Omission]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for omission in omissions:
        counts[omission.reason_code] = counts.get(omission.reason_code, 0) + 1
    return dict(sorted(counts.items()))


__all__ = [
    "MAX_SELECTOR_CANDIDATES", "SELECTOR_SCHEMA_VERSION", "EvidenceCandidate",
    "EvidenceRequirement", "EvidenceRequirementSet", "Omission", "SelectionConfig", "SelectionDecision",
    "build_requirements", "docs_selection_config", "library_docs_selection_config", "project_docs_selection_config", "normalize_candidates",
    "patch_selection_config", "select_evidence", "validate_evidence_sufficiency",
]
