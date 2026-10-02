"""Review-only predicate/objective contracts, not native public acceptance."""
import importlib.util
from pathlib import Path
import sys

import pytest

from docmancer.core.models import Document
from docmancer.core.retrieval_passages import PassageProfile
from docmancer.core.sqlite_store import SQLiteStore
from eval.evidence_quality_v2.run import documents_for, load_protocol


path = Path(__file__).resolve().parents[2] / 'roadmap/search-quality-2026-10-01/gate_a_candidate.py'
spec = importlib.util.spec_from_file_location('gate_a_contract_candidate', path)
candidate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = candidate
spec.loader.exec_module(candidate)

QUESTION = ('storage retention behavior. Also identify private production deployment '
            'configuration credentials owner selected runtime settings.')


@pytest.mark.parametrize('body', [
    '# storage retention behavior\n\nUnrelated network details.',
    'storage retention behavior\n==========================\n\nUnrelated network details.',
    'storage retention details are documented.',
    'storage is documented. retention is documented. behavior is documented.',
    'storage behavior retention is documented.',
    'storage retention behavior?',
    'storage retention behavior.',
])
def test_existing_relevance_negatives_remain_not_admitted(body):
    assert candidate.decide_topic(QUESTION, body).state != 'allowed'


def test_echo_and_partial_context_are_distinct():
    question = 'Which page title wins when the navigation configuration and Markdown content define different titles?'
    body = 'page title wins when navigation configuration and Markdown content define different titles.'
    assert candidate.decide_topic(question, body).state != 'allowed'
    assert candidate.decide_topic(QUESTION,
        'storage retention behavior is documented in this current guide.').state == 'allowed'
    greek = 'αποθήκευση διατήρηση συμπεριφορά. Also identify private production deployment configuration credentials owner selected runtime settings.'
    assert candidate.decide_topic(greek,
        'αποθήκευση διατήρηση συμπεριφορά περιγράφονται στον τρέχοντα οδηγό.').state == 'allowed'


def test_soft_wrap_normalization_does_not_cross_paragraph_or_hard_break():
    body = 'storage retention\nbehavior is documented in this current guide.'
    assert candidate.decide_topic(QUESTION, body).state == 'allowed'
    assert candidate.decide_topic(QUESTION, body.replace('\n', '\n\n')).state != 'allowed'
    assert candidate.decide_topic(QUESTION, body.replace('\n', '  \n')).state != 'allowed'
    assert candidate.decide_topic(QUESTION, '```text\n' + body + '\n```').state != 'allowed'


def test_frozen_native_passage_has_topic_context_but_rule_alone_is_unknown(tmp_path):
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == 'mkdocs-05')
    db = SQLiteStore(tmp_path / 'index.db', passage_profile=PassageProfile())
    db.add_documents([Document(source=p, content=t, metadata={
        'project_identity': 'mkdocs-fixture', 'source_class': 'project_doc'})
        for p, t in documents_for('mkdocs', manifest).items()])
    hits = db.query_passages(case['question'], filters={'project_identity': 'mkdocs-fixture'})['candidates']
    witness = case['required_claims'][0]['witness_sets'][0]['parts'][0]['text']
    hit = next(p for p in hits if witness in p['text'])
    decision = candidate.decide_topic(case['question'], hit['text'])
    assert decision.state == 'allowed'
    a, b = decision.witness_span
    assert hit['text'][a:b]
    # No semantic entailment is manufactured for an isolated paraphrase.
    assert candidate.decide_topic(case['question'], witness).state == 'unknown'


def test_packing_objective_preserves_rank_breadth_before_extent_and_cost():
    def objective(rows, cost):
        return candidate.packing_objective(rows, candidate_order=('first', 'second'),
                                           whole_dto_tokens=cost)
    first = {'candidate_id': 'first', 'start': 0, 'end': 100}
    second = {'candidate_id': 'second', 'start': 0, 'end': 30}
    assert objective([first, second], 700) > objective([{**first, 'end': 1000}], 700)
    assert objective([first], 300) > objective([{**first, 'end': 50}], 200)
    assert objective([first], 300) > objective([first], 301)
    assert objective([first, {**first, 'start': 50}], 300)[1] == (100, 0)
