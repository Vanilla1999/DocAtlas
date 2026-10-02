"""Source-window eligibility is neither read relevance nor answer proof."""
from dataclasses import dataclass
from typing import Any, Mapping


def prepare_source_probe(probe, *, visible_text, evidence_text, candidate=None,
                         expected_project_identity=None, lifecycle_intent='current',
                         catalog_role='', forbidden_catalog_roles=(),
                         forbidden_evidence_terms=()):
    """Shared existing policy/reference checks; preserve qualification ordering."""
    from .evidence_qualification import evidence_policy_rejection_reason
    from .query_reference_binding import prepare_reference_probe
    reason = evidence_policy_rejection_reason(
        probe, visible_text=visible_text, candidate=candidate,
        expected_project_identity=expected_project_identity,
        lifecycle_intent=lifecycle_intent, catalog_role=catalog_role,
        forbidden_catalog_roles=forbidden_catalog_roles,
        forbidden_evidence_terms=forbidden_evidence_terms)
    if reason is not None:
        return dict(probe), reason
    return prepare_reference_probe(probe, candidate=candidate, evidence_text=evidence_text)


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    eligible: bool
    reason: str
    span: tuple[int, int] | None = None


def source_window_eligibility(candidate: Mapping[str, Any], *, question: str,
                              expected_project_identity: str | None,
                              lifecycle_intent: str = 'current') -> EligibilityDecision:
    from .source_dependency_graph import digest

    def reject(reason):
        return EligibilityDecision(False, reason)

    if not question or not expected_project_identity or candidate.get('source_class') != 'project_doc':
        return reject('missing_project_request')
    if candidate.get('instruction_risk_flags'):
        return reject('unsafe_evidence')
    root = candidate.get('_reference_root_plan')
    evidence = candidate.get('_reference_evidence')
    if not isinstance(root, dict) or not isinstance(evidence, dict):
        return reject('source_not_prepared')
    if root.get('question') != question:
        return reject('reference_plan_mismatch')
    raw = evidence.get('raw_document')
    identity = evidence.get('source')
    if (not isinstance(raw, str) or not isinstance(identity, dict)
            or digest(raw) != identity.get('content_sha256')):
        return reject('source_snapshot_mismatch')
    span = candidate.get('char_span')
    body = candidate.get('snippet')
    if (not isinstance(body, str) or not isinstance(span, (list, tuple))
            or len(span) != 2 or any(type(x) is not int for x in span)
            or not 0 <= span[0] < span[1] <= len(raw)
            or raw[span[0]:span[1]] != body):
        return reject('source_window_mismatch')
    # Use exact supplied offsets. Do not locate the snippet elsewhere in raw.
    trace, reason = prepare_source_probe(
        {'query_text': question}, visible_text=body, evidence_text=body,
        candidate={**candidate, 'char_start': span[0], 'char_end': span[1]},
        expected_project_identity=expected_project_identity,
        lifecycle_intent=lifecycle_intent,
        catalog_role=str(candidate.get('catalog_role') or ''))
    if reason is not None:
        return reject(reason)
    trimmed_start = span[0] + len(body) - len(body.lstrip())
    trimmed_end = span[1] - (len(body) - len(body.rstrip()))
    if trace.get('reference_visible_span') != [trimmed_start, trimmed_end]:
        return reject('source_window_mismatch')
    return EligibilityDecision(True, 'bound_source_window', tuple(span))
