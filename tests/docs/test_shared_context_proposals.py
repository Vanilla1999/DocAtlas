"""Read proposals are shared across prefit/final without broad topical union."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from docmancer.docs.application.need_context_projection import preferred_context_variants
from docmancer.docs.application.read_context_admission import iter_prefit_context_variants, iter_read_context_variants
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from docmancer.docs.domain.query_terms import documentation_query_terms, documentation_exact_terms
from docmancer.docs.domain.evidence_qualification import _visible_term_present
from docmancer.retrieval.dispatch import RetrievalDispatcher
from tests.docs._reference_binding_fixtures import capture_reference_case


HERE = Path(__file__).resolve().parents[2] / 'eval/evidence_quality_v2'
QUESTION = 'Which page title wins when the navigation configuration and Markdown content define different titles?'
WITNESS = ('Note that if a title is defined for a page in the navigation, that title will be\n'
           'used throughout the site for that page and will override any title defined\n'
           'within the page itself.')


def plain_rank(query, chunks):
    terms = documentation_query_terms(query)
    exact = {t.normalized_value for t in documentation_exact_terms(query)}
    groups = {}
    for chunk in chunks:
        groups.setdefault(chunk.source, []).append(chunk)
    def key(chunk):
        body = chunk.text.casefold()
        return (sum(_visible_term_present(t, body, exact=True) for t in exact),
                sum(_visible_term_present(t, body, exact=t in exact) for t in terms))
    queues = {k: iter(sorted(v, key=key, reverse=True)) for k, v in groups.items()}
    return [next(queues[c.source]) for c in chunks]


def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(RetrievalDispatcher, '_rank_project_bodies_within_source', staticmethod(plain_rank))
    path = 'docs/user-guide/writing-your-docs.md'
    raw = (HERE / 'sources/mkdocs' / path).read_bytes()
    manifest = json.loads((HERE / 'source-manifest.json').read_text())
    row = next(r for r in manifest['sources'] if r['project'] == 'mkdocs' and r['path'] == path)
    assert hashlib.sha256(raw).hexdigest() == row['sha256']
    from docmancer.docs.application import read_context_admission
    inputs = []
    def observe(candidates, **kwargs):
        inputs.append((deepcopy(candidates), deepcopy(kwargs['query_plan'])))
        yield from iter_prefit_context_variants(candidates, **kwargs)
    monkeypatch.setattr(read_context_admission, 'iter_prefit_context_variants', observe)
    capture = capture_reference_case(tmp_path, {path: raw.decode()}, QUESTION)
    assert inputs
    candidates, plan = inputs[0]
    return capture, candidates, plan


def test_shared_proposals_deliver_precedence_without_public_proof(tmp_path, monkeypatch):
    capture, candidates, plan = prepared(tmp_path, monkeypatch)
    payload = capture['public_payload']
    assert any(WITNESS in row['snippet'] for row in payload['sources'])
    assert docs_context_budget_tokens(payload) <= 800
    assert not payload['answer_supported'] and not payload['edit_ready']
    kwargs = dict(query_plan=plan, expected_project_identity=candidates[0]['project_identity'],
                  max_tokens=800, diagnostics={})
    assert list(preferred_context_variants(candidates, **kwargs))
    assert list(iter_prefit_context_variants(candidates, **kwargs)) == [
        (original, variant) for original, variant, _ in preferred_context_variants(candidates, **kwargs)
    ] + list(iter_read_context_variants(candidates, **kwargs))


@pytest.mark.parametrize('change', [
    {'project_identity': 'other'}, {'freshness': 'stale'},
    {'index_freshness': 'dirty'}, {'lifecycle_status': 'archived'},
    {'instruction_risk_flags': ['injection']}, {'risk_flags': ['unsafe']},
])
def test_shared_proposals_recompute_source_guards(tmp_path, monkeypatch, change):
    _, candidates, plan = prepared(tmp_path, monkeypatch)
    identity = candidates[0]['project_identity']
    changed = deepcopy(candidates)
    for row in changed:
        row.update(change)
    assert not list(iter_prefit_context_variants(changed, query_plan=plan,
        expected_project_identity=identity, max_tokens=800, diagnostics={}))


def test_shared_proposals_recompute_snapshot(tmp_path, monkeypatch):
    _, candidates, plan = prepared(tmp_path, monkeypatch)
    changed = deepcopy(candidates)
    for row in changed:
        row['_reference_evidence']['raw_document'] += ' changed'
    assert not list(iter_prefit_context_variants(changed, query_plan=plan,
        expected_project_identity=candidates[0]['project_identity'], max_tokens=800, diagnostics={}))


@pytest.mark.parametrize('field,value', [
    ('canonical_path', 'docs/other.md'), ('document_id', 'other'),
    ('content_sha256', '0' * 64),
])
def test_shared_proposals_recompute_prepared_identity(tmp_path, monkeypatch, field, value):
    _, candidates, plan = prepared(tmp_path, monkeypatch)
    changed = deepcopy(candidates)
    for row in changed:
        row['_reference_evidence']['source'][field] = value
    assert not list(iter_prefit_context_variants(changed, query_plan=plan,
        expected_project_identity=candidates[0]['project_identity'], max_tokens=800, diagnostics={}))


def test_shared_proposals_reject_changed_question(tmp_path, monkeypatch):
    _, candidates, plan = prepared(tmp_path, monkeypatch)
    plan = deepcopy(plan)
    plan['original_question'] += ' Only when private overrides are disabled.'
    assert not list(iter_prefit_context_variants(candidates, query_plan=plan,
        expected_project_identity=candidates[0]['project_identity'], max_tokens=800, diagnostics={}))


def test_shared_proposals_enforce_complete_packet_budget(tmp_path, monkeypatch):
    _, candidates, plan = prepared(tmp_path, monkeypatch)
    assert not list(iter_prefit_context_variants(candidates, query_plan=plan,
        expected_project_identity=candidates[0]['project_identity'], max_tokens=1, diagnostics={}))


@pytest.mark.parametrize('body', [
    'The page title navigation configuration wins?',
    'page title wins when navigation configuration and Markdown content define different titles.',
    '# Navigation title override\n\nUnrelated network details.',
    'Page is documented. Title is documented. Navigation is documented.',
])
def test_precedence_proposals_do_not_rescue_echo_or_heading(tmp_path, monkeypatch, body):
    from docmancer.docs.application import read_context_admission
    inputs = []
    def observe(candidates, **kwargs):
        inputs.append((deepcopy(candidates), deepcopy(kwargs)))
        yield from iter_prefit_context_variants(candidates, **kwargs)
    monkeypatch.setattr(read_context_admission, 'iter_prefit_context_variants', observe)
    capture = capture_reference_case(tmp_path, {'docs/guide.md': '# Guide\n\n' + body + '\n'}, QUESTION)
    if not inputs:
        assert not capture['public_payload'].get('sources')
        return
    for candidates, kwargs in inputs:
        kwargs.pop('lifecycle_intent', None)
        assert not list(preferred_context_variants(candidates, **kwargs))
