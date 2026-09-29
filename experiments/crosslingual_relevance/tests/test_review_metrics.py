"""Tests of the actual existing M2/M4/M5 entry points, not replacement stubs."""
from types import SimpleNamespace
import hashlib
import pytest

from experiments.crosslingual_relevance.m4_dense_candidates import _is_gold_chunk, M15_DEV_TASKS
from experiments.crosslingual_relevance.m5_real_scorer import _check_gold, TYPER_TASKS
from experiments.crosslingual_relevance.run import recall_at_k
from eval.evidence_quality_v2.run import documents_for, load_protocol


def test_recall_is_not_hit_rate():
    assert recall_at_k([True,False,True],k=1) == 0.5


@pytest.mark.parametrize('metadata', [{}, {'source_path':'docs/advanced/timeouts.md'},
    {'source_path':'timeouts.md','line_start':1,'line_end':4},
    {'source_path':'docs/advanced/timeouts.md','line_start':3,'line_end':3},
    {'source_path':'docs/advanced/timeouts.md','line_start':1,'line_end':4}])
def test_file_or_overlap_without_canonical_fact_is_not_gold(metadata):
    chunk = SimpleNamespace(metadata=metadata, text='Not the canonical timeout rule.')
    assert not _is_gold_chunk(chunk, M15_DEV_TASKS[0])


def test_correct_source_and_complete_witness_are_recognised():
    _,_,manifest = load_protocol()
    raw = documents_for('httpx', manifest)['docs/advanced/timeouts.md']
    chunk = SimpleNamespace(text='\n'.join(raw.splitlines()[:4]), metadata={
        'source_path':'docs/advanced/timeouts.md','line_start':1,'line_end':4,
        'project_identity':'local:httpx',
        'source_content_hash':hashlib.sha256(raw.encode()).hexdigest(),
    })
    task = {**M15_DEV_TASKS[0], 'expected_project_identity':'local:httpx'}
    assert _is_gold_chunk(chunk, task)


def test_wrong_project_cannot_borrow_same_file_path_and_text():
    _,_,manifest = load_protocol()
    raw = documents_for('httpx',manifest)['docs/advanced/timeouts.md']
    chunk = SimpleNamespace(text='\n'.join(raw.splitlines()[:4]), metadata={
        'source_path':'docs/advanced/timeouts.md','line_start':1,'line_end':4,
        'project_identity':'local:foreign'})
    assert not _is_gold_chunk(chunk, {**M15_DEV_TASKS[0], 'expected_project_identity':'local:httpx'})


def test_one_typer_clause_is_not_the_entire_answer():
    task = TYPER_TASKS[0]
    result = _check_gold({'sources':[{'snippet':task['gold_phrases'][0]}]}, task)
    assert result['gold_found'] is False


def test_keyword_only_does_not_prove_teardown_order():
    task = {'id':'m15-dev-03','project':'starlette','formulation':'RU',
            'gold_phrases':['teardown','lifespan']}
    result = _check_gold({'sources':[{'snippet':'The lifespan reference.'}]},task)
    assert result['gold_found'] is False


def test_default_duration_requires_exception_and_inactivity_not_just_number():
    task={'id':'m15-dev-01','project':'httpx','formulation':'mixed',
          'gold_phrases':['enforces timeouts','TimeoutException','5 seconds']}
    result=_check_gold({'sources':[{'snippet':'The example sleeps for 5 seconds.'}]}, task)
    assert result['gold_found'] is False
