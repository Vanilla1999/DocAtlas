"""Gate A research controls; not public delivery or permission acceptance."""
from tests.docs.test_gate_a_contract_candidate import candidate

import pytest


@pytest.mark.parametrize('body,allowed', [
    ('A handler for QueueHub can be synchronous.', True),
    ('A handler for QueueHub must be asynchronous.', True),
    ('A handler for QueueHub can be asynchronous.', False),
    ('A handler for QueueHub can be synchronous?', False),
    ('Can a handler for QueueHub be synchronous?', False),
    ('A handler for OtherHub can be synchronous.', False),
])
def test_factual_answer_is_not_rejected_as_query_echo(body, allowed):
    result = candidate.decide_fact_or_topic('Can a handler for QueueHub be synchronous?', body)
    assert (result.state == 'allowed') is allowed
    if allowed:
        assert result.reason == 'recomputed_local_fact_context'


def test_default_value_and_condition_are_recomputed():
    question = 'What is the default timeout of RelayClient when preview is disabled?'
    body = 'When preview is disabled, RelayClient default timeout is 7 seconds.'
    assert candidate.decide_fact_or_topic(question, body).state == 'allowed'
    assert candidate.decide_fact_or_topic(question, body.replace('disabled', 'enabled')).state != 'allowed'
    assert candidate.decide_fact_or_topic(question, 'RelayClient default timeout is 7 seconds.').state != 'allowed'
    assert candidate.decide_fact_or_topic(question, body.replace('timeout', 'retry delay')).state != 'allowed'


@pytest.mark.parametrize('question,raw', [
    ('Which ways enable strict mode?', 'Strict mode can be enabled in these ways:\n\n- Use a per-call option.\n- Set a model configuration.\n'),
    ('How do transport keys map to protocols?', '| Transport key | Protocol |\n|---|---|\n| `ALPHA_KEY` | scheme-a |\n| `BETA_KEY` | scheme-b |\n'),
    ('storage retention behavior', 'Configure storage retention behavior with this command:\n\n```sh\nretention --current\n# Run only against the test instance.\n```\n'),
])
def test_intact_structures_have_current_window_witnesses(question, raw):
    assert candidate.decide_structural_window(question, raw, 0, len(raw)).state == 'allowed'
    # Cut inside the last item/row/fence. The lexical witness must not authorize clipping.
    assert candidate.decide_structural_window(question, raw, 0, len(raw) - 8).state != 'allowed'
    changed = raw.replace('strict mode', 'other mode').replace('Protocol', 'Error code')
    if changed != raw:
        assert candidate.decide_structural_window(question, changed, 0, len(changed)).state != 'allowed'


def test_code_without_context_and_unclosed_fence_stay_unknown():
    raw = '```sh\nretention --current\n```\n'
    assert candidate.decide_structural_window('storage retention behavior', raw, 0, len(raw)).state != 'allowed'
    raw = 'Configure storage retention behavior with this command:\n\n```sh\nretention --current\n'
    assert candidate.decide_structural_window('storage retention behavior', raw, 0, len(raw)).state != 'allowed'


def windows():
    return [
        {'source': 'a.md', 'candidate_id': 'first', 'start': 0, 'end': 100},
        {'source': 'a.md', 'candidate_id': 'first', 'start': 0, 'end': 30},
        {'source': 'b.md', 'candidate_id': 'second', 'start': 0, 'end': 20},
    ]


def test_bounded_solver_finds_objective_winner_and_stable_ties():
    # Arithmetic solver control, not actual DTO tokenization acceptance.
    def cost(packet):
        return 100 + sum(w['end'] - w['start'] for w in packet)
    result = candidate.solve_packets(windows(), candidate_order=('first', 'second'),
                                    packet_cost=cost, max_tokens=160)
    assert result.status == 'optimal_in_inventory'
    assert {(w['candidate_id'], w['end']) for w in result.windows} == {('first', 30), ('second', 20)}
    assert result.whole_dto_tokens == 150
    assert candidate.solve_packets(list(reversed(windows())), candidate_order=('first', 'second'),
        packet_cost=cost, max_tokens=160) == result


def test_work_limited_solver_never_publishes_best_so_far():
    calls = []
    def cost(packet):
        calls.append(packet)
        return 100
    result = candidate.solve_packets(windows(), candidate_order=('first', 'second'),
                                    packet_cost=cost, max_visits=2)
    assert result.status == 'work_limited'
    assert not result.windows and result.whole_dto_tokens is None
    assert result.visits == len(calls) == 2
    with pytest.raises(ValueError):
        candidate.solve_packets(windows() * 2000, candidate_order=('first', 'second'), packet_cost=cost)


def test_solver_counts_invalid_source_cap_work_and_rejects_bad_cost():
    proposals = [{'source': 'one.md', 'candidate_id': str(i), 'start': i, 'end': i + 10} for i in range(3)]
    result = candidate.solve_packets(proposals, candidate_order=('0', '1', '2'), packet_cost=lambda p: 100)
    assert len(result.windows) == 2
    with pytest.raises(ValueError, match='invalid DTO cost'):
        candidate.solve_packets(windows(), candidate_order=('first', 'second'), packet_cost=lambda p: True)


def test_native_source_binding_and_actual_dto_cost(tmp_path):
    from copy import deepcopy
    from tests.docs.test_read_context_admission_boundary import prepared
    from docmancer.docs.domain.source_window_eligibility import source_window_eligibility
    from docmancer.docs.application.model_visible_projection import (
        docs_context_budget_tokens, validate_model_visible_projection,
    )
    from docmancer.docs.application._docs_context_payload import _payload
    question = 'Can a handler for QueueHub be synchronous?'
    body = 'A handler for QueueHub can be synchronous.'
    capture, original, plan = prepared(tmp_path, question=question, body=body)
    identity = original['project_identity']
    assert source_window_eligibility(original, question=question,
        expected_project_identity=identity).eligible
    raw = original['_reference_evidence']['raw_document']
    start, end = original['char_span']
    assert candidate.decide_structural_window(question, raw, start, end).state == 'allowed'
    public = deepcopy(capture['public_payload']['sources'][0])
    public['retrieval_query_ids'] = []
    public['retrieval_query_matches'] = {}
    proposal = {'source': public['path_or_url'], 'candidate_id': original['stable_chunk_id'],
                'start': start, 'end': end}
    def cost(packet):
        return docs_context_budget_tokens(_payload([public] if packet else [], query_plan=plan))
    selected = candidate.solve_packets([proposal], candidate_order=(proposal['candidate_id'],),
                                      packet_cost=cost)
    assert selected.status == 'optimal_in_inventory' and selected.windows
    payload = _payload([public], query_plan=plan)
    snapshot = capture['projection_attempts'][-1]['snapshot']
    assert selected.whole_dto_tokens == docs_context_budget_tokens(payload) <= 800
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert not payload['answer_supported'] and not payload['edit_ready']
    changed = deepcopy(original)
    changed['_reference_evidence']['raw_document'] += ' changed'
    assert not source_window_eligibility(changed, question=question,
        expected_project_identity=identity).eligible


@pytest.mark.parametrize('case_id', ['httpx-07', 'pydantic-07', 'ruff-07'])
def test_known_partial_facts_are_not_lost_to_unresolved_tail(tmp_path, case_id):
    from eval.evidence_quality_v2.run import load_protocol, documents_for
    from docmancer.core.models import Document
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.core.retrieval_passages import PassageProfile
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == case_id)
    db = SQLiteStore(tmp_path / 'index.db', passage_profile=PassageProfile())
    db.add_documents([Document(source=p, content=t, metadata={
        'project_identity': 'partial-fixture', 'source_class': 'project_doc'})
        for p, t in documents_for(case['project_group'], manifest).items()])
    result = db.query_passages(case['question'], filters={'project_identity': 'partial-fixture'})
    assert result['question'] == case['question']
    parts = case['required_claims'][0]['witness_sets'][0]['parts']
    for part in parts:
        hit = next(h for h in result['candidates'] if h['source'] == part['path'] and part['text'] in h['text'])
        assert candidate.decide_fact_or_topic(case['question'], hit['text']).state == 'allowed'
    assert not case['required_claims'][1]['witness_sets']
