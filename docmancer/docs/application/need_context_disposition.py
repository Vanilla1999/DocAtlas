"""Separate current-source eligibility, topical context, and local need proof.

This module performs no I/O. A prepared structural bundle proposes provenance;
its dataclass, routing IDs, scores and previously recorded decisions are not proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal, Mapping

from docmancer.docs.domain.admission_grammar import parse_admission_frame
from docmancer.docs.domain.admission_relations import _PREFIX_CONDITION, _phrase
from docmancer.docs.domain.admission_grammar import _STATES
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.evidence_set_types import EvidenceSet, SourceKey
from docmancer.docs.domain.evidence_set_validation import validate_evidence_set
from docmancer.docs.domain.need_contracts import NeedContract, compile_need_contracts
from docmancer.docs.domain.query_reference_binding import ReferencePlan
from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles
from docmancer.docs.domain.source_dependency_graph import digest
from docmancer.docs.domain.technical_tokens import technical_term_pattern


@dataclass(frozen=True, slots=True)
class ContextDisposition:
    state: Literal['blocked', 'retrieval_only', 'supported']
    need_id: str
    reason: str
    set_id: str | None = None


# These refusals concern semantic evidence/relevance only, never a source guard.
_CONTEXT_REASONS = frozenset({'visible_fields', 'insufficient_visible_match',
    'unverified_legacy_semantics', 'missing_local_demand', 'verified_local_demand'})


def _probe(contract: NeedContract) -> dict[str, Any]:
    need = contract.need
    text = ' '.join(part for part in (need.context, need.query_span_text) if part)
    roles = query_constraint_roles(text)
    return {'query_text': text, 'query_origin': 'retrieval_need',
        'query_terms': list(documentation_query_terms(text)),
        'exact_terms': list(dict.fromkeys((*roles.hard_exact, *need.hard_exact))),
        'bound_subjects': list(roles.bound_subjects),
        'need_subject': need.subject, 'need_relation': need.relation,
        'need_context': need.context}


def _applicable_context(contract: NeedContract, question: str, body: str) -> bool:
    """Unknown conditions do not become permissions from similar words."""
    if not contract.constraint_spans:
        return True
    frame = parse_admission_frame(contract.need.query_span_text)
    constraints = {slot.role: slot for slot in frame.constraints} if frame else {}
    if {'condition_subject', 'condition_state'} <= constraints.keys():
        # Require the actual local prefix, not a state somewhere else on a page.
        required_entity = constraints['condition_subject'].text
        required_state = constraints['condition_state'].canonical
        for block in re.split(r'\n\s*\n', body):
            match = _PREFIX_CONDITION.match(' '.join(block.split()))
            if (match and re.fullmatch(_phrase(required_entity), match['entity'], re.I)
                    and _STATES.get(match['state'].casefold()) == required_state):
                remainder = ' '.join(block.split())[match.end():]
                clause = re.split(r'(?<=[.!?])\s+|;\s*', remainder, maxsplit=1)[0]
                subject = contract.need.subject
                if subject and re.search(technical_term_pattern(subject, exact=True), clause, re.I):
                    return True
        return False
    # The composed precedence form asks about conflicting sources, not a state
    # of a named feature. It can receive topic context but is not proven here.
    if contract.need.relation == 'precedence':
        text = ' '.join(question[s.start:s.end] for s in contract.constraint_spans)
        return bool(re.search(r'\bdefine\s+different\b', text, re.I)
                    and not re.search(r'\b(?:not|only|unless|except|without)\b', text, re.I))
    return False


def _witness_is_visible(spans, bundle: EvidenceSet, offset: int, raw: str) -> bool:
    """Do not borrow a matched clause outside the proposed original members."""
    members = sorted((ref.start, ref.end) for ref in bundle.member_spans)
    for a, b in spans:
        left, end = offset + a, offset + b
        for start, stop in members:
            if stop <= left or start >= end:
                continue
            if start > left and raw[left:start].strip('\r\n'):
                return False
            left = max(left, min(stop, end))
        if left < end and raw[left:end].strip('\r\n'):
            return False
    return bool(spans)


def classify_need_context(
    contract: NeedContract, *, reference_plan: ReferencePlan,
    candidate: Mapping[str, Any], bundles: tuple[EvidenceSet, ...],
    prepared_sources: Mapping[SourceKey, Mapping[str, Any]],
) -> ContextDisposition:
    """Recompute each verdict from the actual request and prepared source bytes.

    `supported` is deliberately limited to existing typed local proofs with all
    dependencies visible. The complete-set/relational extensions must provide
    their own checked witnesses; neither structural closure nor lexical support
    is promoted into entailment here.
    """
    def blocked(reason: str) -> ContextDisposition:
        return ContextDisposition('blocked', contract.need.need_id, reason)

    current_contracts = compile_need_contracts(reference_plan.question, reference_plan)
    if contract not in current_contracts:
        return blocked('need_contract_mismatch')
    if candidate.get('_reference_root_plan') != asdict(reference_plan):
        return blocked('reference_plan_mismatch')
    evidence = candidate.get('_reference_evidence')
    if not isinstance(evidence, Mapping):
        return blocked('source_not_prepared')
    identity = evidence.get('source') or {}
    key = SourceKey(reference_plan.scope, str(identity.get('document_id') or ''),
        str(identity.get('canonical_path') or ''), str(identity.get('content_sha256') or ''))
    record = prepared_sources.get(key)
    if not isinstance(record, Mapping) or record.get('source') != identity:
        return blocked('source_identity_mismatch')
    raw = record.get('raw_document')
    if (not isinstance(raw, str) or raw != evidence.get('raw_document')
            or digest(raw) != key.document_sha256):
        return blocked('source_span_mismatch')
    body = str(candidate.get('snippet') or '')
    probe = _probe(contract)
    checked = qualify_evidence(probe, query_id=contract.need.need_id,
        visible_text=body, evidence_text=body, candidate=candidate,
        catalog_role=str(candidate.get('catalog_role') or ''),
        expected_project_identity=reference_plan.scope.project_id,
        lifecycle_intent=candidate.get('_lifecycle_intent', 'current'))
    if checked.reason not in _CONTEXT_REASONS:
        return blocked(checked.reason)
    if checked.trace.get('missing_exact_terms') or checked.trace.get('missing_bound_subjects'):
        return blocked('missing_exact_or_subject')
    # Preserve literal obligations also when prepare_reference_probe rebuilt a
    # body-only search plan. A supplied typed contract cannot weaken identities.
    if any(not re.search(technical_term_pattern(term, exact=True), body, re.I)
           for term in contract.need.hard_exact):
        return blocked('missing_exact_terms')
    if not _applicable_context(contract, reference_plan.question, body):
        return blocked('condition_support_unavailable')
    visible = checked.trace.get('reference_visible_span')
    if (not isinstance(visible, (list, tuple)) or len(visible) != 2
            or any(type(x) is not int for x in visible)):
        return blocked('source_window_mismatch')

    visible_bundles = []
    for bundle in bundles:
        errors = validate_evidence_set(bundle, current_contracts, prepared_sources)
        if errors:
            return blocked(errors[0])
        if (bundle.member_spans and all(ref.source == key and
                visible[0] <= ref.start < ref.end <= visible[1]
                for ref in bundle.member_spans)):
            visible_bundles.append(bundle)
    if contract.interpretation == 'supported' and contract.requirement == 'scalar':
        for bundle in visible_bundles:
            start = min(ref.start for ref in bundle.member_spans)
            end = max(ref.end for ref in bundle.member_spans)
            local = raw[start:end]
            qualification = qualify_evidence(probe, query_id=contract.need.need_id,
                visible_text=local, evidence_text=local,
                candidate={**candidate, 'char_span': [start, end], 'snippet': local},
                catalog_role=str(candidate.get('catalog_role') or ''),
                expected_project_identity=reference_plan.scope.project_id,
                lifecycle_intent=candidate.get('_lifecycle_intent', 'current'))
            if (qualification.qualified and qualification.trace.get('admission_route') == 'typed_local'
                    and _witness_is_visible(qualification.trace.get('need_witness_spans') or (),
                                            bundle, start, raw)):
                return ContextDisposition('supported', contract.need.need_id,
                    'current_local_witness', bundle.set_id)
    # Same two-distinct-body-terms floor as existing context_hint_policy. No
    # global lexical threshold is lowered and no heading/name-only rescue exists.
    body_terms = {str(term).casefold() for term in checked.trace.get('body_matched_terms') or ()}
    if len(body_terms - {''}) < 2:
        return blocked('insufficient_topic_context')
    return ContextDisposition('retrieval_only', contract.need.need_id,
                              'current_topic_without_complete_proof')
