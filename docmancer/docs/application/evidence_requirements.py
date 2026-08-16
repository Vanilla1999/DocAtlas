"""Canonical evidence-requirement construction.

Question parsing and public contract normalization live here so selection
orchestration receives one immutable ``EvidenceRequirementSet``.
"""
from __future__ import annotations

import itertools
import json
import re
from dataclasses import replace
from typing import Any, Iterable, Literal, Mapping, Sequence

from docmancer.docs.application.evidence_candidates import normalized_source as _normalized_source
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.domain.project_answer_contract import ProofObligation, ProjectAnswerContract, build_project_answer_contract
from docmancer.retrieval.contracts import canonical_hash
from docmancer.retrieval.query_planning import extract_exact_terms

MAX_REQUIREMENT_IDENTIFIERS = 12
MAX_REQUIREMENT_PATHS = 12
MAX_PUBLIC_REQUIREMENTS = 12
MAX_CODE_GROUPS = 6
_COMPARISON_IDENTIFIER = r"(?<![a-z0-9_`])(`?[a-z][a-z0-9_]*`?)(?![a-z0-9_`])"
_LOWERCASE_COMPARISON_RE = re.compile(
    rf"{_COMPARISON_IDENTIFIER}\s+instead\s+of\s+{_COMPARISON_IDENTIFIER}", re.IGNORECASE,
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
_ALLOWED_REQUIREMENT_PROVENANCE = frozenset({
    "query_exact_term", "public_task_contract", "required_evidence_paths",
    "required_target_paths", "exact_dependency_binding", "selector_scope_requirement",
    "canonical_policy_requirement", "disclosed_authority_version_conflict",
})

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
        if (
            requirement.query_span_start is not None
            and requirement.query_span_end is not None
            and requirement.query_span_text
        ):
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
        requirement.obligation_kind,
        requirement.subject,
        requirement.attribute,
        requirement.relation,
        requirement.obligation_target,
        requirement.value_kind,
        requirement.expected_value,
        requirement.item_kind,
        requirement.cardinality,
        requirement.response_mode if requirement.response_mode != "value" else None,
        requirement.subject_kind,
        requirement.subject_aliases,
        requirement.context,
        requirement.lifecycle_intent,
    )


def _requirement_from_obligation(obligation: ProofObligation) -> EvidenceRequirement:
    return EvidenceRequirement(
        requirement_id=obligation.obligation_id,
        kind="proof_obligation",
        value=" ".join(filter(None, (
            obligation.subject,
            obligation.attribute,
            obligation.relation,
            obligation.target,
            obligation.item_kind,
        ))),
        mandatory=obligation.mandatory,
        public_provenance="query_exact_term",
        query_extraction_kind=f"typed_{obligation.kind}",
        query_span_start=obligation.query_span_start,
        query_span_end=obligation.query_span_end,
        query_span_text=obligation.query_span_text,
        obligation_kind=obligation.kind,
        subject=obligation.subject,
        attribute=obligation.attribute,
        relation=obligation.relation,
        obligation_target=obligation.target,
        value_kind=obligation.value_kind,
        expected_value=obligation.expected_value,
        item_kind=obligation.item_kind,
        cardinality=obligation.cardinality,
        response_mode=obligation.response_mode,
        subject_kind=obligation.subject_kind,
        subject_aliases=obligation.subject_aliases,
        context=obligation.context,
        lifecycle_intent=obligation.lifecycle_intent,
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
    # Materialize caller-provided iterables once.  Several stages inspect the
    # same public evidence contract (construction, safety gating and hashing);
    # consuming a generator in only one of them would make authorization depend
    # on iterator state.
    required_evidence_paths = tuple(required_evidence_paths)
    required_target_paths = tuple(required_target_paths)
    public_requirements = tuple(public_requirements)

    requirements: list[EvidenceRequirement] = []
    input_limits: set[str] = set()
    answer_contract: ProjectAnswerContract | None = None
    for index, term in enumerate(extract_exact_terms(question)):
        requirements.append(EvidenceRequirement(
            requirement_id=f"query_exact:{index}:{term.normalized_value}",
            kind="exact_term", value=term.value,
            mandatory=term.kind != "path" and profile != "project_docs_answer",
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
            kind="exact_term", value=value,
            mandatory=profile != "project_docs_answer",
            public_provenance="query_exact_term",
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
        answer_contract = build_project_answer_contract(question)
        for obligation in answer_contract.proof_obligations:
            typed = _requirement_from_obligation(obligation)
            unique[typed.requirement_id] = typed
        # A parse failure must fail closed when the natural-language question
        # is the only authority for what needs proving.  If the caller supplied
        # an explicit public evidence contract, however, that independent
        # contract is already the authorization boundary; keep parser
        # diagnostics in ``unresolved_parts`` but do not manufacture an extra
        # mandatory unsupported-query requirement that would override the
        # caller's concrete obligations.
        explicit_support_contract = bool(public_requirements or required_evidence_paths)
        if answer_contract.unresolved_parts and not explicit_support_contract:
            for index, reason in enumerate(answer_contract.unresolved_parts):
                unique[f"unresolved:{index}:{reason}"] = EvidenceRequirement(
                    requirement_id=f"unresolved:{index}:{reason}",
                    kind="unsupported_query", value=reason,
                    public_provenance="query_exact_term",
                    query_extraction_kind=reason,
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
        retrieval_hints=answer_contract.retrieval_hints if answer_contract else (),
        concept_queries=answer_contract.concept_queries if answer_contract else (),
        answer_contract_hash=answer_contract.contract_hash if answer_contract else None,
        lifecycle_intent=answer_contract.lifecycle_intent if answer_contract else "current",
        parse_trace=answer_contract.parse_trace if answer_contract else (),
        unresolved_parts=answer_contract.unresolved_parts if answer_contract else (),
    )



__all__ = ["build_requirements"]
