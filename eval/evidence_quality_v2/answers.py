"""Claim-to-citation review, separate from both retrieval score and hash validity.

The claim list is an evaluator annotation of an actual answer, not a required
host output format. Unrecognized assertions are queued, never silently certified.
"""
from __future__ import annotations
from collections import Counter
from eval.evidence_quality_v2.semantic import assess_context


def assess_answer(case, payload, registry, answer, *, valid_evidence_ids):
    context = assess_context(case, payload, registry)
    if answer.get('operational_error'):
        return dict(context_sufficiency=context['context_sufficiency'], outcome='operational_error', support_ratio=None)
    assertions = answer.get('assertions') or []
    if not assertions:
        outcome = 'unjustified_refusal' if context['context_sufficiency'] == 'sufficient' else 'refusal'
        return dict(context_sufficiency=context['context_sufficiency'], outcome=outcome,
                    support_ratio=None, mandatory_complete=False, answered=False)
    known = {c['id']: c for c in [*case['required_claims'], *case.get('optional_claims', [])]}
    sources = {s['evidence_id']: s for s in payload.get('sources', [])}
    rows = []
    for assertion in assertions:
        cid = assertion.get('claim_id')
        ids = assertion.get('evidence_ids') or []
        invalid = [x for x in ids if x not in sources or x not in valid_evidence_ids]
        if cid not in known:
            status = 'needs_review'
        elif assertion.get('stance', 'asserted') != 'asserted':
            status = 'unsupported'
        elif not ids or invalid:
            status = 'unsupported'
        else:
            scoped = dict(case, required_claims=[known[cid]], optional_claims=[])
            assessment = assess_context(scoped, {'sources': [sources[x] for x in ids]}, registry)
            status = assessment['claims'][cid]['status']
            status = 'unsupported' if status in ('missing', 'contradicted') else status
        rows.append(dict(claim_id=cid, status=status, invalid_citations=invalid))
    supported = {r['claim_id'] for r in rows if r['status'] == 'supported'}
    complete = {c['id'] for c in case['required_claims']} <= supported
    statuses = {r['status'] for r in rows}
    if 'unsupported' in statuses:
        outcome = 'unsupported_claim'
    elif 'needs_review' in statuses:
        outcome = 'needs_review'
    elif complete:
        outcome = 'supported_full'
    elif answer.get('explicit_gap'):
        outcome = 'supported_partial'
    else:
        outcome = 'incomplete_without_disclosure'
    return dict(context_sufficiency=context['context_sufficiency'], outcome=outcome,
                assertions=rows, mandatory_complete=complete, answered=True,
                support_ratio=sum(r['status'] == 'supported' for r in rows)/len(rows),
                invalid_or_irrelevant_citations=sum(r['status'] == 'unsupported' for r in rows),
                unreviewed_additional_claims=sum(r['status'] == 'needs_review' for r in rows))


def context_answer_matrix(reports):
    counts = Counter((r['context_sufficiency'], r['outcome']) for r in reports)
    return [{'context_sufficiency': k[0], 'answer_outcome': k[1], 'count': v}
            for k, v in sorted(counts.items())]
