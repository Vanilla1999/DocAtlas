"""Stage-local checks; these are not native recovery acceptance."""
import pytest
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
from unittest.mock import patch

from v2plan.next07_grounded_candidate import escape_fts_query, proposals, structural_spans
from v2plan.next07_grounded_reference import fixture_inputs
from v2plan.next07_grounded_run import ROOT
from v2plan.next07_grounded_candidate import read_decision


def prepared_units(tmp_path, documents, question):
    from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
    from tests.docs._global_evidence_fixtures import capture_fixture

    original = SourceReferenceContext.prepare
    candidates = {}

    def observe(context, chunks, *args, **kwargs):
        prepared = original(context, chunks, *args, **kwargs)
        for chunk in prepared:
            evidence = chunk.metadata.get('_reference_evidence')
            if not evidence:
                continue
            raw, identity = evidence['raw_document'], evidence['source']
            spans, _ = structural_spans(raw, identity['document_id'])
            for start, end in spans:
                key = (chunk.source, start, end)
                if key in candidates:
                    continue
                proposal = chunk.model_copy(update={'text': raw[start:end], 'metadata': {
                    **chunk.metadata, 'char_span': [start, end]}})
                rebound = original(context, [proposal], *args, **kwargs)
                if rebound:
                    row = rebound[0]
                    candidates[key] = {**row.metadata, 'snippet': row.text,
                        'path': row.metadata['project_doc_path'], 'char_span': [start, end]}
        return prepared  # Native N is unchanged; observer does not install C.

    with patch.object(SourceReferenceContext, 'prepare', observe):
        capture = capture_fixture(tmp_path, documents, question)
    return list(candidates.values()), capture


def decision(row, question, identity=None):
    result = read_decision(row, question=question,
        expected_project_identity=identity or row['project_identity'])
    if directory := os.environ.get('NEXT07_CONTROL_OUT'):
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        # One append-only diagnostic row, including source bytes and guard inputs.
        with (target / 'decisions.jsonl').open('a') as stream:
            stream.write(json.dumps({'question': question, 'candidate': row,
                'decision': asdict(result)}, ensure_ascii=False, default=str) + '\n')
    return result


@pytest.mark.parametrize('query,expected', [
    ('foo bar', '"foo bar" OR "foo" OR "bar"'),
    ('"hello world"', '"hello world"'),
    ('test "exact phrase" word', '"test exact phrase word" OR "test" OR "exact phrase" OR "word"'),
    ('', '""'),
])
def test_pinned_query(query, expected):
    assert escape_fts_query(query) == expected


@pytest.mark.parametrize('index', [0, 1])
def test_i2_original_fixture_spans(index):
    value, error, documents, question = fixture_inputs(ROOT)[index]
    inventory = [{'raw': text, 'identity': path, 'path': path, 'title': '', 'url': ''}
        for path, text in documents.items()]
    rows, omitted = proposals(inventory, question)
    assert not omitted
    assert len(rows) <= 20
    assert any(f'{value} seconds' in r['content'] for r in rows)
    assert any(f'An expired operation raises `{error}`.' in r['content'] for r in rows)
    for row in rows:
        assert row['raw'][row['start']:row['end']] == row['content']
        assert row['raw'].encode()[row['byte_start']:row['byte_end']] == row['content'].encode()


def test_i2_no_clipping_oversized_atom():
    raw = '# Owner\n\n' + 'x' * 6000
    spans, omitted = structural_spans(raw, 'source')
    assert omitted
    assert all('x' not in raw[a:b] for a, b in spans)


def test_i2_repeated_unicode_offsets():
    raw = '# Δ\n\nSame 😀 text.\n\nSame 😀 text.\n'
    spans, omitted = structural_spans(raw, 'source')
    assert spans == [(0, len(raw))]
    assert not omitted


@pytest.mark.parametrize('index', [0, 1])
def test_i3_original_fact_context(tmp_path, index):
    value, error, docs, question = fixture_inputs(ROOT)[index]
    rows, _ = prepared_units(tmp_path, docs, question)
    for needle in (f'{value} seconds', f'An expired operation raises `{error}`.'):
        matches = [r for r in rows if needle in r['snippet']]
        assert matches
        assert any(decision(r, question).allowed for r in matches)


@pytest.mark.parametrize('change', [
    {'project_identity': 'other'}, {'repository_identity': 'other'},
    {'freshness': 'stale'}, {'index_freshness': 'dirty'},
    {'risk_flags': ['unsafe']}, {'instruction_risk_flags': ['injection']},
    {'lifecycle_status': 'archived'}, {'char_span': [0, 1]},
    {'resolved_version': 'wrong'}, {'generation_id': 'wrong'},
    {'path': 'docs/other.md'}, {'source_class': 'library_doc'},
])
def test_i3_guard_mutations(tmp_path, change):
    _, _, docs, question = fixture_inputs(ROOT)[0]
    rows, _ = prepared_units(tmp_path, docs, question)
    row = next(r for r in rows if '17 seconds' in r['snippet'])
    assert decision(row, question).allowed
    identity = row['project_identity']
    changed = deepcopy(row)
    changed.update(change)
    assert not decision(changed, question, identity).allowed


def test_i3_existing_disabled_enabled_negative(tmp_path):
    # Existing supported state control, not a new condition language.
    question = 'What is OrbitClient default timeout when preview is disabled?'
    allowed = '# OrbitClient\n\nWhen preview is disabled, OrbitClient default timeout is 7 seconds.\n'
    forbidden = allowed.replace('preview is disabled', 'preview is enabled')
    rows, _ = prepared_units(tmp_path / 'positive', {'guide.md': allowed}, question)
    assert any(decision(r, question).allowed for r in rows)
    rows, _ = prepared_units(tmp_path / 'negative', {'guide.md': forbidden}, question)
    assert rows
    assert not any(decision(r, question).allowed for r in rows)


def test_i3_trailing_restriction_across_structural_boundary(tmp_path):
    question = 'Which exception does LeaseClient raise when an operation expires?'
    # Fixed hard-max boundary control: the source's restriction follows a long
    # intervening paragraph in the same heading section. No algorithm tuning.
    raw = ('# LeaseClient\n\nLeaseClient raises `LeaseExpired`.\n\n'
        + 'Documentation. ' * 330 + '\n\nOnly when an operation expires.\n')
    rows, _ = prepared_units(tmp_path, {'guide.md': raw}, question)
    facts = [r for r in rows if 'LeaseClient raises `LeaseExpired`.' in r['snippet']]
    assert facts
    for row in facts:
        if decision(row, question).allowed:
            assert 'Only when an operation expires.' in row['snippet']
