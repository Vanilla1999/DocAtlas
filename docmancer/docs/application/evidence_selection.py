"""Deterministic, provider-free minimal evidence selection.

The selector owns evidence eligibility and fitting.  Formatters receive only a
validated whole-item subset and remain responsible for serialization safety,
not for deciding which source facts are important.
"""
from __future__ import annotations

import hashlib
import itertools
import math
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable, Literal, Mapping, Sequence

from docmancer.retrieval.contracts import canonical_hash
from docmancer.retrieval.query_planning import extract_exact_terms


SELECTOR_SCHEMA_VERSION = "budget-aware-evidence-selector-v2"
MAX_SELECTOR_CANDIDATES = 20
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(r"[\w.+:/-]+", re.UNICODE)
_PATCH_FACT_RE = re.compile(
    r"\b(?:must|shall|required|requires?|never|forbidden|prohibited|"
    r"pytest|compileall|cargo\s+(?:test|check|build)|npm\s+(?:test|run)|"
    r"dart\s+(?:test|analyze)|go\s+test|make\s+test)\b",
    re.IGNORECASE,
)
_ALLOWED_REQUIREMENT_PROVENANCE = frozenset({
    "query_exact_term",
    "public_task_contract",
    "required_evidence_paths",
    "required_target_paths",
    "exact_dependency_binding",
    "canonical_policy_requirement",
    "disclosed_authority_version_conflict",
})

OmissionReason = Literal[
    "wrong_version", "unknown_version", "forbidden_source", "outside_scope",
    "stale", "instruction_risk", "invalid_identity", "navigation_only",
    "authority_conflict", "exact_duplicate", "overlap_duplicate",
    "near_duplicate", "source_cap", "zero_marginal_utility", "budget",
    "dominated", "candidate_cap",
]


def _estimated_tokens(value: str) -> int:
    return max(1, math.ceil(len(value.encode("utf-8")) / 4))


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
    return _text(
        item.get("display_text")
        or item.get("code")
        or item.get("snippet")
        or item.get("content")
    )


def _projected_text(item: Mapping[str, Any], display_text: str, result_kind: str) -> str:
    if result_kind == "docs_answer":
        return display_text
    snippet = _text(item.get("snippet"))
    fact_material = str(item.get("content") or display_text)
    fact_lines = [line.strip() for line in fact_material.splitlines() if _PATCH_FACT_RE.search(line)]
    symbols = " ".join(_symbols(item))
    parts = [part for part in [snippet, *fact_lines, symbols, _source_path(item)] if part]
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
    if normalized in {"exact", "exact_version", "version_exact", "exact_version_indexed"}:
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
    schema_version: str = SELECTOR_SCHEMA_VERSION
    max_candidates: int = MAX_SELECTOR_CANDIDATES
    max_sources: int = 3
    max_items_per_source: int = 2
    near_duplicate_threshold: int = 850
    overlap_threshold: int = 800
    marginal_utility_threshold: int = 80
    shingle_size: int = 5
    wrapper_reserve_tokens: int = 120
    cache_enabled: bool = False

    def __post_init__(self) -> None:
        if self.result_kind not in {"docs_answer", "patch_context"}:
            raise ValueError("unsupported evidence result kind")
        if not 1 <= self.target_tokens <= self.hard_tokens:
            raise ValueError("selector token budgets are invalid")
        if not 1 <= self.max_candidates <= MAX_SELECTOR_CANDIDATES:
            raise ValueError("selector candidate limit is invalid")
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
    requirements: tuple[EvidenceRequirement, ...] = field(default=(), compare=False, repr=False)

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
            "requirements_hash": canonical_hash([asdict(item) for item in self.requirements]),
            "candidate_trace_hash": self.candidate_trace_hash,
            "selection_hash": self.selection_hash,
        }


def docs_selection_config(max_tokens: int) -> SelectionConfig:
    hard = min(800, max(256, int(max_tokens)))
    return SelectionConfig(
        result_kind="docs_answer", target_tokens=min(650, hard), hard_tokens=hard,
        max_sources=3, max_items_per_source=2, wrapper_reserve_tokens=120,
        marginal_utility_threshold=100,
    )


def patch_selection_config(max_tokens: int) -> SelectionConfig:
    hard = min(2000, max(256, int(max_tokens)))
    return SelectionConfig(
        result_kind="patch_context", target_tokens=min(1200, hard), hard_tokens=hard,
        max_sources=12, max_items_per_source=3, wrapper_reserve_tokens=min(300, hard // 3),
        marginal_utility_threshold=160,
    )


def build_requirements(
    question: str,
    *,
    required_evidence_paths: Iterable[str] = (),
    required_target_paths: Iterable[str] = (),
    public_requirements: Iterable[Mapping[str, Any] | str] = (),
    exact_version: str | None = None,
) -> tuple[EvidenceRequirement, ...]:
    requirements: list[EvidenceRequirement] = []
    for index, term in enumerate(extract_exact_terms(question)):
        requirements.append(EvidenceRequirement(
            requirement_id=f"query_exact:{index}:{term.normalized_value}",
            kind="exact_term", value=term.value, public_provenance="query_exact_term",
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
    for index, value in enumerate(identifier_values):
        requirements.append(EvidenceRequirement(
            requirement_id=f"query_symbol:{index}:{value.casefold()}",
            kind="exact_term", value=value, public_provenance="query_exact_term",
        ))
    for kind, paths, provenance in (
        ("evidence_path", required_evidence_paths, "required_evidence_paths"),
        ("target_path", required_target_paths, "required_target_paths"),
    ):
        for index, path in enumerate(paths):
            value = str(path).strip()
            if value:
                requirements.append(EvidenceRequirement(
                    requirement_id=f"{kind}:{index}:{_normalized_source(value)}",
                    kind=kind, value=value, public_provenance=provenance,
                    source_path=value if kind == "evidence_path" else None,
                    target_path=value if kind == "target_path" else None,
                ))
    if exact_version:
        requirements.append(EvidenceRequirement(
            requirement_id=f"exact_version:{exact_version}", kind="exact_version",
            value=str(exact_version), public_provenance="exact_dependency_binding",
            version_binding=str(exact_version),
        ))
    for index, raw in enumerate(public_requirements):
        if isinstance(raw, Mapping):
            value = str(raw.get("value") or raw.get("text") or "").strip()
            kind = str(raw.get("kind") or "required_fact")
            mandatory = raw.get("mandatory") is not False
            provenance = str(raw.get("public_provenance") or "public_task_contract")
        else:
            value, kind, mandatory, provenance = str(raw).strip(), "required_fact", True, "public_task_contract"
        if value:
            if provenance not in _ALLOWED_REQUIREMENT_PROVENANCE:
                raise ValueError(f"unsupported evidence requirement provenance: {provenance}")
            requirements.append(EvidenceRequirement(
                requirement_id=f"public:{index}:{canonical_hash(value)[:12]}",
                kind=kind, value=value, mandatory=mandatory, public_provenance=provenance,
            ))
    unique = {item.requirement_id: item for item in requirements}
    return tuple(unique[key] for key in sorted(unique))


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
                + (88 if result_kind == "patch_context" else 0)
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
            authority=_authority(item), source_class=str(item.get("source_class") or ""),
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
    requirements: Sequence[EvidenceRequirement] | None = None,
    required_evidence_paths: Iterable[str] = (),
    required_target_paths: Iterable[str] = (),
    public_requirements: Iterable[Mapping[str, Any] | str] = (),
    exact_version: str | None = None,
    project_identity: str | None = None,
    module_id: str | None = None,
) -> SelectionDecision:
    materialized_items = [dict(item) for item in items if isinstance(item, Mapping)]
    requirements = tuple(requirements or build_requirements(
        question,
        required_evidence_paths=required_evidence_paths,
        required_target_paths=required_target_paths,
        public_requirements=public_requirements,
        exact_version=exact_version,
    ))
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
        project_identity=project_identity, module_id=module_id,
        result_kind=config.result_kind,
    )
    omissions.extend(hard_omissions)
    requirements = _with_canonical_policy_requirements(requirements, eligible, config.result_kind)
    covered = [_with_coverage(candidate, requirements) for candidate in eligible]
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
    missing.update(critical_failures)
    missing.update(f"stable_identity_collision:{value}" for value in identity_collisions)
    if config.result_kind == "docs_answer" and selected and all(item.navigation_only for item in selected):
        missing.add("factual_source_evidence")
    status: Literal["ok", "insufficient_evidence"] = (
        "ok" if selected and not missing and not conflicts else "insufficient_evidence"
    )
    selected = sorted(selected, key=lambda item: (
        0 if item.covered_requirement_ids & mandatory else 1,
        *_candidate_preference(item),
    ))
    selected_tokens = sum(item.token_estimate for item in selected)
    metrics = {
        "candidate_count": len(raw_candidates),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "selected_sources": len({_normalized_source(item.source_identity) for item in selected}),
        "selected_tokens": selected_tokens,
        "wrapper_reserve_tokens": config.wrapper_reserve_tokens,
        "projected_total_tokens": selected_tokens + config.wrapper_reserve_tokens,
        "hard_tokens": config.hard_tokens,
        "mandatory_requirements": len(mandatory),
        "mandatory_covered": len(mandatory & set().union(*(
            item.covered_requirement_ids for item in selected
        ))) if selected else 0,
        "mandatory_coverage_millis": int(
            len(mandatory & set().union(*(item.covered_requirement_ids for item in selected)))
            * 1000 / max(1, len(mandatory))
        ) if selected else 0,
        "requirements_hash": canonical_hash([asdict(item) for item in requirements]),
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
    selection_hash = canonical_hash({
        "schema_version": SELECTOR_SCHEMA_VERSION,
        "config_hash": config.config_hash,
        "eligibility_contract_hash": eligibility_contract_hash,
        "candidate_trace_hash": candidate_trace_hash,
        "requirements": [asdict(item) for item in requirements],
        "selected": [_selected_identity(item) for item in selected],
        "omissions": [asdict(item) for item in sorted_omissions],
        "missing": sorted(missing), "conflicts": sorted(conflicts),
    })
    return SelectionDecision(
        status=status, selected_candidates=tuple(selected), omissions=sorted_omissions,
        missing_requirements=tuple(sorted(missing)), unresolved_conflicts=tuple(sorted(conflicts)),
        metrics=metrics, selector_config_hash=config.config_hash,
        eligibility_contract_hash=eligibility_contract_hash,
        candidate_trace_hash=candidate_trace_hash, selection_hash=selection_hash,
        requirements=requirements,
    )


def validate_evidence_sufficiency(
    decision: SelectionDecision,
    requirements: Sequence[EvidenceRequirement] = (),
    *,
    result_kind: str | None = None,
) -> list[str]:
    errors: list[str] = []
    requirements = tuple(requirements or decision.requirements)
    mandatory = {item.requirement_id for item in requirements if item.mandatory}
    covered = set().union(*(item.covered_requirement_ids for item in decision.selected_candidates)) if decision.selected_candidates else set()
    if decision.status == "ok" and not decision.selected_candidates:
        errors.append("successful selection requires evidence")
    if decision.status == "ok" and mandatory - covered:
        errors.append("successful selection is missing mandatory requirements")
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
        "requirements": [asdict(item) for item in requirements],
        "selected": [_selected_identity(item) for item in decision.selected_candidates],
        "omissions": [asdict(item) for item in decision.omissions],
        "missing": list(decision.missing_requirements),
        "conflicts": list(decision.unresolved_conflicts),
    })
    if expected != decision.selection_hash:
        errors.append("selection hash does not match the decision")
    return errors


def _eligible_candidates(
    candidates: Sequence[EvidenceCandidate],
    trust_contract: Mapping[str, Any],
    requirements: Sequence[EvidenceRequirement],
    *,
    project_identity: str | None,
    module_id: str | None,
    result_kind: str,
) -> tuple[list[EvidenceCandidate], list[Omission], set[str]]:
    forbidden = _trust_source_keys(trust_contract, "rejected") | _trust_source_keys(trust_contract, "risky")
    exact_versions = {item.value for item in requirements if item.kind == "exact_version" and item.mandatory}
    canonical_policy_required = any(
        item.kind == "canonical_policy" and item.mandatory for item in requirements
    )
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
        if reason:
            omissions.append(Omission(candidate.stable_id, reason))
        else:
            eligible.append(candidate)
    return eligible, omissions, critical


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


def _with_coverage(candidate: EvidenceCandidate, requirements: Sequence[EvidenceRequirement]) -> EvidenceCandidate:
    haystack = "\n".join([
        candidate.display_text, candidate.path_or_url, candidate.section,
        " ".join(candidate.symbols), candidate.version_binding, candidate.resolved_version,
    ]).casefold()
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
        elif requirement.kind == "exact_term":
            matches = bool(re.search(
                rf"(?<![\w]){re.escape(value)}(?![\w])", haystack
            ))
        else:
            matches = value in haystack
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
        -candidate.relevance_millis,
        candidate.retrieval_rank,
        candidate.token_estimate,
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
    available = max(1, config.hard_tokens - config.wrapper_reserve_tokens)
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
    if sum(item.token_estimate for item in selected) > available:
        remaining.add("mandatory_evidence_does_not_fit")
        for candidate in candidates:
            omissions.append(Omission(candidate.stable_id, "budget"))
        return [], remaining, omissions

    spent = sum(item.token_estimate for item in selected)
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
        if spent + best.token_estimate > available:
            omissions.append(Omission(best.stable_id, "budget"))
            continue
        selected.append(best)
        spent += best.token_estimate
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
    "EvidenceRequirement", "Omission", "SelectionConfig", "SelectionDecision",
    "build_requirements", "docs_selection_config", "normalize_candidates",
    "patch_selection_config", "select_evidence", "validate_evidence_sufficiency",
]
