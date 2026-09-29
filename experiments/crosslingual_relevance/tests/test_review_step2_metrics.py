"""The legacy step2 entry point must obey the same canonical evaluator."""
import pytest
from experiments.crosslingual_relevance.m4_step2_handler import _is_gold_source
from experiments.crosslingual_relevance.m4_dense_candidates import M15_DEV_TASKS
from experiments.crosslingual_relevance.evaluation_v2 import corpus_documents

@pytest.mark.parametrize('row', [{}, {'path_or_url':'docs/advanced/timeouts.md'},
    {'path_or_url':'docs/advanced/timeouts.md','line_start':3,'line_end':3,'snippet':'noise'}])
def test_step2_does_not_certify_filename_or_overlap(row):
    assert not _is_gold_source(row, M15_DEV_TASKS[0])


def test_step2_accepts_complete_canonical_statement():
    raw = corpus_documents('httpx')['docs/advanced/timeouts.md']
    row = {'path_or_url':'docs/advanced/timeouts.md','line_start':1,'line_end':4,
           'snippet':'\n'.join(raw.splitlines()[:4])}
    assert _is_gold_source(row, M15_DEV_TASKS[0])
