"""Research-only read contract; production expectations are not rewritten."""
from copy import deepcopy
from dataclasses import fields
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'v2plan'))
from unified_read_admission import unified_read_admission
from tests.docs.test_read_context_admission_boundary import QUESTION
from tests.docs.test_grounded_budget_probe import probe


def prepared(tmp_path, question=QUESTION,
             body='storage retention behavior is documented in this current guide.', heading='Guide'):
    # Prepare source references before native semantic filtering, including negatives.
    prefix = f'# {heading}\n\n'
    text = prefix + body + '\n'
    metadata = {'project_identity': 'fixture', 'project_path': str(tmp_path),
                'project_doc_path': 'guide.md', 'source_class': 'project_doc',
                'authority': 'source_of_truth', 'doc_scope': 'project',
                'source_content_hash': probe.hashlib.sha256(text.encode()).hexdigest()}
    store = probe.SQLiteStore(tmp_path / 'index.db', passage_profile=probe.PassageProfile())
    store.add_documents([probe.Document(source='guide.md', content=text, metadata=metadata)])
    filters = {k: metadata[k] for k in ('project_identity', 'project_path', 'source_class')}
    context = probe.SourceReferenceContext(store, question=question, filters=filters)
    start = len(prefix)
    chunk = probe.Chunk(source='guide.md', text=text[start:], chunk_index=0,
                       metadata=dict(metadata, char_span=[start, len(text)]))
    ready = context.prepare([chunk])[0]
    return None, dict(ready.metadata, snippet=ready.text, path='guide.md'), None


def decide(candidate, question=QUESTION):
    from docmancer.docs.application.read_context_admission import read_context_admission
    research = unified_read_admission(candidate, question=question,
                                     expected_project_identity=candidate['project_identity'])
    native = read_context_admission(candidate, question=question,
                                    expected_project_identity=candidate['project_identity'])
    assert native.allowed == research.allowed
    return native


def test_partial_context_is_read_only_and_has_one_decision(tmp_path):
    _, candidate, _ = prepared(tmp_path)
    result = decide(candidate)
    assert result.allowed
    assert {f.name for f in fields(result)} == {'allowed', 'reason'}


def test_read_decision_never_calls_proof_qualification(tmp_path, monkeypatch):
    _, candidate, _ = prepared(tmp_path)
    import docmancer.docs.domain.evidence_qualification as qualification
    def forbidden(*args, **kwargs):
        raise AssertionError('proof qualification used as read decision')
    monkeypatch.setattr(qualification, 'qualify_evidence', forbidden)
    import docmancer.docs.application.read_context_admission as native
    monkeypatch.setattr(native, 'qualify_evidence', forbidden, raising=False)
    assert native.read_context_admission(candidate, question=QUESTION,
                                         expected_project_identity=candidate['project_identity']).allowed
    assert decide(candidate).allowed


@pytest.mark.parametrize('body,allowed', [
    ('storage retention behavior is documented.', True),
    ('storage retention behavior is not supported.', True),
    ('# storage retention behavior\n\nUnrelated network details.', False),
    ('storage retention behavior?', False),
    ('storage retention behavior.', False),
    ('storage is documented. retention is documented. behavior is documented.', False),
    ('storage behavior retention is documented.', False),
    ('Storage retention behavior never deletes active records.', True),
    ('# Storage retention behavior\n\nTransport retries use exponential backoff.', False),
    ('Storage retention behavior is documented? Consult your deployment owner.', False),
])
def test_one_existing_locality_rule_without_polarity_proof(tmp_path, body, allowed):
    _, candidate, _ = prepared(tmp_path, body=body)
    assert decide(candidate).allowed is allowed


@pytest.mark.parametrize('change', [
    {'project_identity': 'other'}, {'freshness': 'stale'}, {'index_freshness': 'dirty'},
    {'risk_flags': ['unsafe']}, {'instruction_risk_flags': ['injection']},
    {'lifecycle_status': 'archived'}, {'char_span': [0, 1]},
    {'snippet': 'forged'},
])
def test_source_guards_stay_closed(tmp_path, change):
    _, candidate, _ = prepared(tmp_path)
    identity = candidate['project_identity']
    candidate.update(change)
    from docmancer.docs.application.read_context_admission import read_context_admission
    assert not read_context_admission(candidate, question=QUESTION,
                                      expected_project_identity=identity).allowed
    assert not unified_read_admission(candidate, question=QUESTION,
                                     expected_project_identity=identity).allowed


def test_source_and_request_are_rechecked_not_cached(tmp_path):
    _, candidate, _ = prepared(tmp_path)
    candidate['allowed'] = True
    changed = deepcopy(candidate)
    changed['_reference_evidence']['raw_document'] += ' forged'
    assert not decide(changed).allowed
    assert not decide(candidate, QUESTION + ' changed').allowed


@pytest.mark.parametrize('question', [
    '`OtherEngine` storage retention behavior.',
    'When caching is disabled, what is storage retention behavior?',
])
def test_literal_and_unknown_condition_do_not_get_rescue(tmp_path, question):
    _, candidate, _ = prepared(tmp_path, question=question)
    assert not decide(candidate, question).allowed


def test_clipping_does_not_inherit_read_approval(tmp_path):
    _, candidate, _ = prepared(tmp_path)
    assert decide(candidate).allowed
    start = candidate['char_span'][0]
    raw = candidate['_reference_evidence']['raw_document']
    candidate.update(snippet=raw[start:start + 7], char_span=[start, start + 7])
    assert not decide(candidate).allowed


@pytest.mark.parametrize('body,allowed', [
    ('When preview is disabled, OrbitClient default timeout is 7 seconds.', True),
    ('When preview is enabled, OrbitClient default timeout is 7 seconds.', False),
    ('OrbitClient default timeout is 7 seconds.', False),
    ('When preview is disabled, OtherClient default timeout is 7 seconds.', False),
    ('When preview is disabled, OrbitClient default timeout is not configurable.', True),
    ('When preview is enabled, OrbitClient default timeout is not configurable.', False),
])
def test_existing_state_applicability_is_preserved(tmp_path, body, allowed):
    question = 'What is OrbitClient default timeout when preview is disabled?'
    _, candidate, _ = prepared(tmp_path, question=question, body=body)
    assert decide(candidate, question).allowed is allowed


@pytest.mark.parametrize('heading,question,allowed', [
    ('OrbitClient', 'What is OrbitClient default storage retention behavior?', True),
    ('OtherClient', 'What is OrbitClient default storage retention behavior?', False),
    ('OrbitClient', 'What is `OrbitClient` default storage retention behavior?', False),
])
def test_verified_owner_subject_does_not_replace_body_literal(tmp_path, heading, question, allowed):
    _, candidate, _ = prepared(tmp_path, question=question, heading=heading,
                              body='Default storage retention behavior is documented.')
    assert decide(candidate, question).allowed is allowed
    if allowed:
        forged = deepcopy(candidate)
        forged['_reference_evidence']['owner']['text'] = '# OtherClient\n'
        assert not decide(forged, question).allowed
