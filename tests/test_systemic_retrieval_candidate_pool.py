from __future__ import annotations

from docmancer.core.models import RetrievedChunk
from scripts.run_systemic_retrieval_plan_gate import _candidate_pool_fingerprint


def _chunk(*, section_id: int, stable_id: str, parent_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        source="/tmp/volatile-fixture-root/docs/policy.md",
        chunk_index=7,
        text=text,
        score=1.0,
        metadata={
            "section_id": section_id,
            "stable_chunk_id": stable_id,
            "parent_logical_id": parent_id,
            "project_doc_path": "docs/policy.md",
            "source_path": "docs/policy.md",
            "source_class": "project_file",
        },
    )


def _isolated_chunk(source: str) -> RetrievedChunk:
    return RetrievedChunk(
        source=source,
        chunk_index=7,
        text="Policy fact.",
        score=1.0,
        metadata={"source_class": "project_file"},
    )


def test_candidate_pool_fingerprint_ignores_fresh_index_ids() -> None:
    first = [_chunk(section_id=11, stable_id="stable-a", parent_id="parent-a", text="Policy fact.")]
    rebuilt = [_chunk(section_id=907, stable_id="stable-b", parent_id="parent-b", text="Policy fact.")]

    assert _candidate_pool_fingerprint(first) == _candidate_pool_fingerprint(rebuilt)


def test_candidate_pool_fingerprint_detects_semantic_candidate_change() -> None:
    first = [_chunk(section_id=11, stable_id="stable-a", parent_id="parent-a", text="Policy fact.")]
    changed = [_chunk(section_id=11, stable_id="stable-a", parent_id="parent-a", text="Different policy fact.")]

    assert _candidate_pool_fingerprint(first) != _candidate_pool_fingerprint(changed)


def test_candidate_pool_fingerprint_ignores_isolated_corpus_root() -> None:
    first = [_isolated_chunk("/tmp/run-a/cap-on/corpus/uv/docs/policy.md")]
    rebuilt = [_isolated_chunk("/tmp/run-b/cap-off/corpus/uv/docs/policy.md")]

    assert _candidate_pool_fingerprint(first) == _candidate_pool_fingerprint(rebuilt)


def test_candidate_pool_fingerprint_preserves_project_relative_source_identity() -> None:
    policy = [_isolated_chunk("/tmp/run-a/cap-on/corpus/uv/docs/policy.md")]
    config = [_isolated_chunk("/tmp/run-b/cap-off/corpus/uv/docs/config.md")]

    assert _candidate_pool_fingerprint(policy) != _candidate_pool_fingerprint(config)


def test_case_pool_allows_skipped_and_repeated_auxiliary_calls() -> None:
    from scripts.run_systemic_retrieval_plan_gate import _FrozenCasePools
    pools = _FrozenCasePools()
    pools.capture(('project', 'question'), ('main',), [_isolated_chunk('docs/main.md')])
    pools.capture(('project', 'question'), ('aux',), [_isolated_chunk('docs/aux.md')])
    before = pools.fingerprint(('project', 'question'))
    assert pools.replay(('project', 'question'), ('main',))
    assert pools.replay(('project', 'question'), ('main',))
    assert pools.fingerprint(('project', 'question')) == before


def test_case_pool_does_not_borrow_another_questions_candidates() -> None:
    from scripts.run_systemic_retrieval_plan_gate import _FrozenCasePools
    pools = _FrozenCasePools()
    pools.capture(('project', 'first'), ('aux',), [_isolated_chunk('docs/first.md')])
    pools.capture(('project', 'second'), ('main',), [_isolated_chunk('docs/second.md')])
    assert pools.replay(('project', 'second'), ('aux',)) == []
    assert pools.replay(('project', 'second'), ('new-route',)) == []


def test_case_pool_replay_cannot_mutate_the_frozen_snapshot() -> None:
    from scripts.run_systemic_retrieval_plan_gate import _FrozenCasePools
    pools = _FrozenCasePools()
    pools.capture(('project', 'question'), ('main',), [_isolated_chunk('docs/main.md')])
    before = pools.fingerprint(('project', 'question'))
    replay = pools.replay(('project', 'question'), ('main',))
    replay[0].metadata['changed'] = True
    replay.clear()
    assert pools.fingerprint(('project', 'question')) == before
    assert 'changed' not in pools.replay(('project', 'question'), ('main',))[0].metadata


def test_causal_lane_branch_change_preserves_case_support(tmp_path, monkeypatch) -> None:
    import json
    from types import SimpleNamespace
    from scripts import run_systemic_retrieval_plan_gate as gate

    dispatcher = SimpleNamespace()
    chunks = [_isolated_chunk('docs/a.md'), _isolated_chunk('docs/b.md')]

    def run(self, query, **kwargs):
        return gate.RetrievalDispatcher._limit_sections_per_source(self, chunks, limit=2)

    def observe(service, arguments):
        found = gate.RetrievalDispatcher.run(dispatcher, arguments['question'])
        if len(found) > 1:
            gate.RetrievalDispatcher.run(dispatcher, 'additional adaptive lookup')
        return {}, {}

    def evaluate(output, **kwargs):
        gate.evidence.observe_call(None, {'project_path': '/fixture/project', 'question': 'main'})
        output.mkdir(parents=True)
        (output / 'rows.json').write_text(json.dumps([{'id': 'one'}]))
        return {'variants': {'A-current': {}}}

    monkeypatch.setattr(gate.RetrievalDispatcher, 'run', run)
    monkeypatch.setattr(gate.RetrievalDispatcher, '_limit_sections_per_source', lambda self, chunks, **kw: chunks[:1])
    monkeypatch.setattr(gate.evidence, 'observe_call', observe)
    monkeypatch.setattr(gate.evidence, 'run', evaluate)
    pools = gate._FrozenCasePools()
    common = dict(work=tmp_path, protocol={}, cases=[], manifest={}, pools=pools)
    baseline = gate._run_lane(name='baseline', **common)
    counter = gate._run_lane(name='counter', cap='off', fixture_output=baseline['output'], **common)
    assert baseline['available_case_pools'] == counter['available_case_pools']
    assert len(counter['consumed_pools']) == 2
    assert counter['unsupported_routes'][0]['query'] == 'additional adaptive lookup'


def test_selector_proxy_choice_cannot_consult_gold_or_exceed_budget() -> None:
    from scripts.run_systemic_retrieval_plan_gate import _proxy_choice
    candidates = [
        dict(indices=[0], proxy=[5], tokens=300, sources=1, sufficient=False),
        dict(indices=[1], proxy=[1], tokens=300, sources=1, sufficient=True),
        dict(indices=[2], proxy=[99], tokens=801, sources=1, sufficient=True),
    ]
    assert _proxy_choice(candidates)['indices'] == [0]
    for candidate in candidates:
        candidate['sufficient'] = not candidate['sufficient']
    assert _proxy_choice(candidates)['indices'] == [0]
