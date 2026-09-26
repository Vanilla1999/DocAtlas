"""Frozen acceptance artifacts are independent of the indexed documentation."""
import hashlib
import json
from pathlib import Path

import pytest
from eval.evidence_quality_v2 import run
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / 'eval/tdd_acceptance'


def _read(name):
    path = BANK / name
    assert path.is_file(), f'Missing pinned acceptance artifact: {name}'
    return json.loads(path.read_text())


def test_required_facts_are_pinned_separately_from_runtime_inputs():
    inventory = _read('inventory.json')
    assert inventory['runtime_cases_sha256'] == hashlib.sha256((ROOT / 'eval/tdd_questions30/cases.json').read_bytes()).hexdigest()
    rubric = _read('baseline-rubric.json')
    assert inventory['baseline_rubric_sha256'] == hashlib.sha256((BANK / 'baseline-rubric.json').read_bytes()).hexdigest()
    assert [case['id'] for case in rubric['cases']] == [f'N{i:02}' for i in range(1, 31)]
    for case in rubric['cases']:
        assert case['required_facts'] and case['source_paths'] and case['basis']
    wire = json.loads((ROOT / 'eval/tdd_questions30/cases.json').read_text())
    assert all(set(case) == {'id', 'question', 'scope', 'lookup_queries'} for case in wire)
    assert inventory['independent_holdout'] is False


def test_contract_revision_does_not_overwrite_the_original_negative_gold():
    rubric = _read('baseline-rubric.json')
    revisions = _read('revisions.json')
    original = next(case for case in rubric['cases'] if case['id'] == 'N04')
    assert any('не содержит' in fact for fact in original['required_facts'])
    revision = revisions['N04']
    assert len(revision['introduced_commit']) == 40
    assert revision['required_facts'] != original['required_facts']
    assert revision['basis'] == 'code_verified'
    assert all(revisions[key]['reason'] for key in ('N03', 'N04'))


def test_all_eight_historical_failures_bind_the_existing_frozen_cases():
    inventory = _read('inventory.json')
    historical = inventory['historical']
    assert historical['ids'] == ['fastapi-01', 'fastapi-02', 'fastapi-06', 'httpx-03', 'mkdocs-05', 'pydantic-03', 'typer-05', 'uv-04']
    for path, digest in historical['files'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    protocol, cases, sources = run.load_protocol()
    assert set(historical['ids']) <= {case['id'] for case in cases}
    assert all(case['required_claims'] for case in cases if case['id'] in historical['ids'])


def test_evaluator_only_answers_never_become_indexed_docs(tmp_path):
    root = tmp_path / 'project'
    marker = 'EVALUATOR_ONLY_FALSE_ANSWER_9f2a'
    write_project(root, {'docs/guide.md': '# Guide\n\nDocumented normal behavior.\n'})
    poison = root / 'eval/expected.md'
    poison.parent.mkdir()
    poison.write_text(f'# Expected answers\n\n{marker}\n')
    with isolated_service(tmp_path / 'state') as (service, config):
        indexed = index_project(service, config, root)
    assert indexed['indexed_paths'] == ['docs/guide.md']
    assert marker not in json.dumps(indexed['rows'])
