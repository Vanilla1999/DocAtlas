"""Optional retrieval preferences, never evidence eligibility or answer proof."""
from __future__ import annotations
import re
from typing import Any
from docmancer.docs.domain.project_retrieval_intent import _specific_contract_request, _tokens


def fallback_context_query_ids(plan: dict[str, Any], retrieval: dict[str, Any], eligible_ids: set[str]) -> set[str]:
    """Admit literal query hints only for otherwise empty, unresolved broad reads.

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
            or any(q.get('origin') in {'exact_anchor', 'exact_path', 'host_lookup'} for q in queries)):
        return set()
    if any(key in eligible_ids and value.get('qualified') is True
           for source in retrieval.get('context_pack') or ()
           for key, value in (source.get('retrieval_query_matches') or {}).items() if isinstance(value, dict)):
        return set()
    return {str(q['query_id']) for q in queries
            if q.get('origin') == 'retrieval_hint' and q.get('query_id')
            and len(str(q.get('text') or '').strip()) >= 4
            and re.search(r'(?<!\w)' + re.escape(str(q['text']).strip()) + r'(?!\w)', question, re.I)}


def has_context_hint_support(source: dict[str, Any]) -> bool:
    """A lone subject/name hit cannot rescue an otherwise unqualified question.

    Use the existing body-only lexical facts, recomputed by the projector, not
    filename/heading matches or repeated spelling variants of the same token.
    This is a conservative preference floor; it never certifies the question.
    """
    trace = (source.get("retrieval_query_matches") or {}).get("query-original") or {}
    terms = {str(term).strip().casefold() for term in trace.get("body_matched_terms") or ()}
    return len(terms - {""}) >= 2
