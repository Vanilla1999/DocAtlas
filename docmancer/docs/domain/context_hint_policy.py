"""Optional retrieval preferences, never evidence eligibility or answer proof."""
from __future__ import annotations
import re
from typing import Any
from docmancer.docs.domain.project_retrieval_intent import _specific_contract_request, _tokens
from docmancer.docs.domain.evidence_qualification import qualify_evidence, evidence_policy_rejection_reason


def fallback_context_query_ids(plan: dict[str, Any], retrieval: dict[str, Any], eligible_ids: set[str]) -> set[str]:
    """Offer partial alternatives for unresolved broad reads.

    Keep exact-source/API and structured-proof requests on their existing paths.
    The projector still rechecks every candidate's scope/identity/freshness and
    each visible body. These ids never derive original-question coverage.
    """
    queries = plan.get('queries') or ()
    question = str(plan.get('original_question') or '')
    # Reuse the existing normative-premise policy, not the broad parser verdict.
    if _specific_contract_request(_tokens(question)):
        return set()
    if (retrieval.get('hard_stop') or not plan.get('broad_context_only')
            or plan.get('_component_contract') or plan.get('explicit_paths')
            or any(q.get('origin') == 'exact_path' for q in queries)):
        return set()
    # A qualified full window may not survive projection into the DTO budget.
    # Keep partial alternatives available until admission; the projector retries
    # them only if the primary packet is empty, without promoting hint coverage.
    return {str(q['query_id']) for q in queries
            if q.get('origin') in {'retrieval_hint', 'lexical_topic'} and q.get('query_id')
            and len(str(q.get('text') or '').strip()) >= 4
            and re.search(r'(?<!\w)' + re.escape(str(q['text']).strip()) + r'(?!\w)', question, re.I)}


def has_context_hint_support(source: dict[str, Any], *, question: str = '') -> bool:
    """A lone subject/name hit cannot rescue an otherwise unqualified question.

    Use the existing body-only lexical facts, recomputed by the projector, not
    filename/heading matches or repeated spelling variants of the same token.
    This is a conservative preference floor; it never certifies the question.
    """
    trace = (source.get("retrieval_query_matches") or {}).get("query-original") or {}
    if not trace and question:
        # A candidate discovered only by a hint has no original-query trace.
        # Recompute body facts for this preference without adding query coverage
        # or weakening the independent policy/qualification admission checks.
        body = str(source.get('snippet') or '')
        trace = qualify_evidence({'query_text': question}, query_id='query-original',
            visible_text=body, evidence_text=body).trace
    terms = {str(term).strip().casefold() for term in trace.get("body_matched_terms") or ()}
    return len(terms - {""}) >= 2


def preserves_unresolved_context_candidate(
    source: dict[str, Any], *, query_plan: dict[str, Any], expected_project_identity: str,
    lifecycle_intent: str = 'current',
) -> bool:
    """Retain a topical candidate for public admission, not answer qualification.

    Only unresolved broad requests use this preference. Recompute body matches:
    cached retrieval traces do not establish relevance. Public projection still
    owns source qualification, visible windows, attribution and the DTO budget.
    """
    if not query_plan.get('unresolved_parts'):
        return False
    plan = {**query_plan, 'broad_context_only': True}
    if not fallback_context_query_ids(plan, {}, set()):
        return False
    body = str(source.get('content') or '')
    if evidence_policy_rejection_reason({}, visible_text=body, candidate=source,
            expected_project_identity=expected_project_identity,
            lifecycle_intent=lifecycle_intent) is not None:
        return False
    return has_context_hint_support({'snippet': body},
        question=str(query_plan.get('original_question') or ''))
