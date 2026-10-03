"""Isolated single read decision; no production imports this research module."""
from docmancer.docs.application.read_context_admission import ReadContextAdmission, local_topic_witness
from docmancer.docs.application.need_context_projection import _current_plan
from docmancer.docs.application.need_context_disposition import _applicable_context
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.source_window_eligibility import source_window_eligibility, prepare_source_probe
from docmancer.docs.domain.query_terms import query_constraint_roles, documentation_query_terms
from docmancer.docs.domain.evidence_qualification import _visible_term_present


def unified_read_admission(candidate, *, question, expected_project_identity,
                           lifecycle_intent='current'):
    def reject(reason):
        return ReadContextAdmission(False, reason)

    source = source_window_eligibility(candidate, question=question,
        expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent)
    if not source.eligible:
        return reject(source.reason)
    plan = _current_plan(candidate['_reference_root_plan'], question)
    if plan is None or plan.scope.project_id != expected_project_identity:
        return reject('reference_plan_mismatch')
    body = candidate['snippet']
    roles = query_constraint_roles(question)
    prepared, reason = prepare_source_probe(
        {'query_text': question, 'query_terms': list(documentation_query_terms(question)),
         'exact_terms': list(roles.hard_exact), 'bound_subjects': list(roles.bound_subjects)},
        visible_text=body, evidence_text=body, candidate=candidate,
        expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,
        catalog_role=str(candidate.get('catalog_role') or ''))
    if reason:
        return reject(reason)
    normalized = body.casefold()
    if any(not _visible_term_present(str(term).casefold(), normalized, exact=True)
           for term in prepared.get('exact_terms', ())):
        return reject('missing_exact_terms')
    owner = str(prepared.get('bound_subject_context') or '').casefold()
    if any(not _visible_term_present(str(term).casefold(), normalized, exact=True)
           and not _visible_term_present(str(term).casefold(), owner, exact=True)
           for term in prepared.get('bound_subjects', ())):
        return reject('missing_bound_subject')
    for contract in compile_need_contracts(question, plan):
        if contract.constraint_spans and not _applicable_context(contract, question, body):
            return reject('condition_support_unavailable')
    terms = {str(term).casefold() for term in prepared.get('query_terms', ())
             if _visible_term_present(str(term).casefold(), normalized,
                                      exact=term in prepared.get('exact_terms', ()))}
    if not local_topic_witness(body, question=question, terms=terms):
        return reject('no_local_topic_witness')
    return ReadContextAdmission(True, 'bound_local_topic_context')
