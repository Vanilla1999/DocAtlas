import importlib.util
from pathlib import Path
from copy import deepcopy
import pytest

PATH = Path(__file__).resolve().parents[2] / 'v2plan'
spec = importlib.util.spec_from_file_location('grounded_budget_probe', PATH / 'grounded_budget_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_budget_admits_same_exact_dto_only_when_it_fits():
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    from docmancer.docs.application._docs_context_payload import _payload
    from docmancer.docs.application.model_visible_projection import _snapshot_entry, _source_digest
    from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
    text = 'Storage retention command:\n\n```sh\nretention\n# ' + 'x' * 5000 + '\n```\n\nOnly in test instances.\n'
    item = {'snippet': text, 'content': text, 'path': 'docs/guide.md',
            'project_identity': 'fixture', 'authority': 'source_of_truth',
            'doc_scope': 'project', 'generation_id': 'fixture-generation'}
    row = {'evidence_id': 'ev-fixture', 'path_or_url': 'docs/guide.md',
           'section': 'Guide', 'snippet': text, 'version_binding': 'unversioned',
           'content_sha256': _source_digest(item), 'project_identity': 'fixture',
           'line_start': 1, 'line_end': text.count('\n'),
           'authority': 'source_of_truth', 'scope': 'project'}
    plan = build_documentation_query_plan('storage retention').as_payload()
    def build(proposals):
        return _payload([row for _ in proposals], query_plan=plan), {'ev-fixture': _snapshot_entry(item, row)}
    proposal = {'proposal_id': 'one', 'native_rank': 1, 'source_identity': 'fixture'}
    small = probe.ordered_packet([proposal], budget=800, check=lambda p: None, build=build)
    large = probe.ordered_packet([proposal], budget=3000, check=lambda p: None, build=build)
    assert small['payload'] is None
    assert large['payload'] is not None
    assert 800 < docs_context_budget_tokens(large['payload']) <= 3000
    assert large['payload']['sources'][0]['snippet'] == text


def fixture_packet(proposals):
    items = []
    for p in proposals:
        text = p.get('text', 'Storage retention behavior is documented here.\n')
        path = p['source_identity'] + '.md'
        items.append({'snippet': text, 'content': text, 'path': path,
                      'project_identity': 'fixture', 'authority': 'source_of_truth',
                      'doc_scope': 'project', 'generation_id': 'generation',
                      'char_span': [0, len(text)], '_reference_evidence': {
                          'raw_document': text, 'source': {'canonical_path': path}}})
    return probe.render_packet(items, query_plan=probe.build_documentation_query_plan('storage retention').as_payload())


def test_thirty_alternatives_finish_without_combinatorial_exhaustion():
    proposals = [{'proposal_id': str(i), 'native_rank': i,
                  'source_identity': str(i // 2)} for i in range(30)]
    result = probe.ordered_packet(proposals, budget=3000, check=lambda p: None, build=fixture_packet)
    assert result['status'] == 'completed_first_fit'
    assert result['visits'] == 30
    assert len(result['payload']['sources']) == 3
    assert result['build_calls'] == 4
    reverse = probe.ordered_packet(list(reversed(proposals)), budget=3000, check=lambda p: None, build=fixture_packet)
    assert reverse['payload'] == result['payload']


def test_oversized_first_hit_and_final_mutation():
    proposals = [{'proposal_id': 'large', 'native_rank': 0, 'source_identity': 'large', 'text': 'x' * 13000},
                 {'proposal_id': 'small', 'native_rank': 1, 'source_identity': 'small'}]
    result = probe.ordered_packet(proposals, budget=800, check=lambda p: None, build=fixture_packet)
    assert result['trace'][0]['reason'] == 'dto_budget'
    assert result['payload']['sources'][0]['path_or_url'] == 'small.md'
    calls = 0
    def mutate(p):
        nonlocal calls
        calls += 1
        return 'source_window_mismatch' if calls > 1 else None
    result = probe.ordered_packet(proposals[1:], budget=800, check=mutate, build=fixture_packet)
    assert result['status'] == 'final_recheck_failed'
    assert result['payload'] is None


@pytest.mark.parametrize('policy', ['passage', 'owner'])
def test_native_inventory_keeps_or_exposes_external_restriction(tmp_path, policy):
    text = '# Storage\n\nStorage retention behavior configuration:\n\n```sh\nretention storage\n```\n\n' + ('Background information. ' * 85) + '\n\nOnly use storage retention on the test instance.\n'
    digest = probe.hashlib.sha256(text.encode()).hexdigest()
    store = probe.SQLiteStore(tmp_path / 'index.db', passage_profile=probe.PassageProfile())
    metadata = {'project_identity': 'fixture', 'project_path': str(tmp_path),
                'project_doc_path': 'guide.md', 'source_class': 'project_doc',
                'authority': 'source_of_truth', 'doc_scope': 'project',
                'source_content_hash': digest}
    store.add_documents([probe.Document(source='guide.md', content=text, metadata=metadata)])
    filters = {'project_identity': 'fixture', 'project_path': str(tmp_path), 'source_class': 'project_doc'}
    question = 'storage retention behavior configuration'
    retrieval = store.query_passages(question, filters=filters)
    context = probe.SourceReferenceContext(store, question=question, filters=filters)
    proposals, _, _ = probe.inventory(store, question=question, filters=filters, policy=policy,
                                      retrieval=retrieval, context=context)
    commands = [p for p in proposals if '```sh' in p['item']['snippet']]
    assert commands
    for p in commands:
        assert probe.source_window_eligibility(p['item'], question=question, expected_project_identity='fixture').eligible
        if policy == 'owner':
            assert 'Only use storage retention on the test instance.' in p['item']['snippet']
        else:
            assert 'Only use storage retention on the test instance.' not in p['item']['snippet']
        mutated = deepcopy(p['item'])
        mutated['snippet'] += ' forged'
        assert not probe.source_window_eligibility(mutated, question=question, expected_project_identity='fixture').eligible


def test_first_fit_can_lose_a_feasible_better_combination():
    proposals = [{'proposal_id': str(i), 'native_rank': i, 'source_identity': str(i),
                  'text': 'Storage retention behavior.\n' + 'x' * size}
                 for i, size in enumerate((1700, 600, 600))]
    first = probe.ordered_packet(proposals, budget=800, check=lambda p: None, build=fixture_packet)
    other = probe.ordered_packet(proposals[1:], budget=800, check=lambda p: None, build=fixture_packet)
    assert len(first['payload']['sources']) == 1
    assert len(other['payload']['sources']) == 2
    assert first['status'] == 'completed_first_fit'


def load_audit():
    spec = importlib.util.spec_from_file_location('grounded_loss_audit', PATH / 'grounded_loss_audit.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    return audit


def test_loss_audit_requires_complete_multipart_witness():
    audit = load_audit()
    claim = {'witness_sets': [{'parts': [{'path': 'a.md', 'text': 'command'},
                                        {'path': 'b.md', 'text': 'restriction'}]}]}
    rows = [{'path_or_url': 'a.md', 'snippet': 'command'}]
    assert audit.witness_groups(claim, rows) == []
    rows.append({'path_or_url': 'wrong.md', 'snippet': 'restriction'})
    assert audit.witness_groups(claim, rows) == []
    rows.append({'path_or_url': 'b.md', 'snippet': 'restriction'})
    assert audit.witness_groups(claim, rows) == [0]


def test_loss_audit_separates_discovery_admission_and_packing():
    audit = load_audit()
    stages = {'source': [0], 'retrieval': [], 'proposals': [], 'admitted': [], 'final': []}
    assert audit.classify(stages) == 'discovery_pool_loss'
    stages.update(retrieval=[0], proposals=[0])
    assert audit.classify(stages) == 'read_admission_loss'
    stages.update(admitted=[0])
    assert audit.classify(stages) == 'packing_or_final_loss'
    stages.update(final=[0])
    assert audit.classify(stages) == 'literal_visible'


def test_loss_audit_cannot_write_archived_database(tmp_path):
    import sqlite3
    audit = load_audit()
    path = tmp_path / 'archive.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE preserved(value TEXT)')
        connection.execute("INSERT INTO preserved VALUES ('original')")
    store = audit.ReadOnlyStore(path, 'generation')
    with store._connect() as connection:
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            connection.execute('DELETE FROM preserved')
        assert connection.execute('SELECT value FROM preserved').fetchone()[0] == 'original'


def test_layer_probe_binds_subject_only_to_verified_owner(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(PATH))
    from admission_layer_probe import inspect_layers
    question = 'If one QueueTasks function raises an exception, what happens to later tasks?'
    for heading, expected in [('QueueTasks', 'verified_owner'), ('OtherTasks', 'unresolved')]:
        text = f'# {heading}\n\nTasks execute in order. If one raises an exception, later tasks stop.\n'
        start = text.index('Tasks execute')
        store = probe.SQLiteStore(tmp_path / (heading + '.db'), passage_profile=probe.PassageProfile())
        metadata = {'project_identity': 'fixture', 'project_path': str(tmp_path),
                    'project_doc_path': 'tasks.md', 'source_class': 'project_doc',
                    'authority': 'source_of_truth', 'doc_scope': 'project',
                    'source_content_hash': probe.hashlib.sha256(text.encode()).hexdigest()}
        store.add_documents([probe.Document(source='tasks.md', content=text, metadata=metadata)])
        filters = {k: metadata[k] for k in ('project_identity', 'project_path', 'source_class')}
        context = probe.SourceReferenceContext(store, question=question, filters=filters)
        chunk = probe.Chunk(source='tasks.md', text=text[start:], chunk_index=0,
                            metadata=dict(metadata, char_span=[start, len(text)]))
        prepared = context.prepare([chunk])[0]
        item = dict(prepared.metadata, path='tasks.md', snippet=prepared.text)
        layers = inspect_layers(item, question=question, identity='fixture', probe=probe)
        assert layers['source_eligible']
        assert layers['subjects'] == [{'term': 'queuetasks', 'location': expected}]
        assert 'queuetasks' not in item['snippet'].casefold()
        if expected == 'verified_owner':
            literal_question = 'What does `QueueTasks` do?'
            literal_context = probe.SourceReferenceContext(store, question=literal_question, filters=filters)
            literal_prepared = literal_context.prepare([chunk])[0]
            literal_item = dict(literal_prepared.metadata, path='tasks.md', snippet=literal_prepared.text)
            literal_layers = inspect_layers(literal_item, question=literal_question, identity='fixture', probe=probe)
            assert 'queuetasks' in literal_layers['literal_missing']
        if expected == 'unresolved':
            forged = deepcopy(item)
            forged['_reference_evidence']['owner']['text'] = '# QueueTasks\n'
            layers = inspect_layers(forged, question=question, identity='fixture', probe=probe)
            assert not layers['source_eligible']
            assert layers['reference_reason'] == 'invalid_subject_owner'
            assert layers['subjects'][0]['location'] == 'unresolved'


@pytest.mark.parametrize('body,expected', [
    ('HTTPX storage retention behavior is documented.', True),
    ('HTTPX storage retention behavior?', False),
    ('OtherClient storage retention behavior is documented.', False),
])
def test_corrected_candidate_case_handling_keeps_native_veto(tmp_path, monkeypatch, body, expected):
    monkeypatch.syspath_prepend(str(PATH))
    from corrected_admission_probe import corrected_reason
    question = 'HTTPX storage retention behavior'
    text = '# Guide\n\n' + body + '\n'
    store = probe.SQLiteStore(tmp_path / 'index.db', passage_profile=probe.PassageProfile())
    metadata = {'project_identity': 'fixture', 'project_path': str(tmp_path),
                'project_doc_path': 'guide.md', 'source_class': 'project_doc',
                'authority': 'source_of_truth', 'doc_scope': 'project',
                'source_content_hash': probe.hashlib.sha256(text.encode()).hexdigest()}
    store.add_documents([probe.Document(source='guide.md', content=text, metadata=metadata)])
    filters = {k: metadata[k] for k in ('project_identity', 'project_path', 'source_class')}
    context = probe.SourceReferenceContext(store, question=question, filters=filters)
    retrieval = store.query_passages(question, filters=filters)
    proposals, _, _ = probe.inventory(store, question=question, filters=filters,
                                      policy='owner', retrieval=retrieval, context=context)
    assert proposals
    p = proposals[0]
    reason = corrected_reason(p, question=question, identity='fixture', probe=probe)
    assert (reason is None) is expected
    native = probe.read_context_admission(p['item'], question=question, expected_project_identity='fixture')
    assert native.allowed is expected
    if expected:
        assert probe.read_reason(p['item'], question=question, identity='fixture') == 'missing_exact_or_subject'
        changed = deepcopy(p)
        changed['item']['snippet'] += ' forged'
        assert corrected_reason(changed, question=question, identity='fixture', probe=probe) == 'source_window_mismatch'


def test_temporal_diagnostic_exposes_keyword_constraint_collision(monkeypatch):
    monkeypatch.syspath_prepend(str(PATH))
    from temporal_condition_probe import inspect_contracts
    questions = ['When do QueueTasks run relative to returning the response?',
                 'Когда выполняются QueueTasks относительно отправки ответа?']
    for question in questions:
        rows = inspect_contracts(question, 'QueueTasks run after returning the response.')
        assert len(rows) == 1
        row = rows[0]
        assert row['parsed_frame']['operator'] == 'temporal_order'
        assert row['parsed_frame']['constraints'] == ()
        assert row['constraint_text'] == [question]
        assert row['existing_applicability'] is False


def test_temporal_diagnostic_preserves_state_negation_and_exception_controls(monkeypatch):
    monkeypatch.syspath_prepend(str(PATH))
    from temporal_condition_probe import MATRIX, inspect_contracts
    observed = {name: inspect_contracts(question, body) for name, _, question, body in MATRIX}
    for name in ('scenario-default-match', 'scenario-negated-state-match', 'temporal-parsed-state-match'):
        assert observed[name][0]['existing_applicability'] is True
    for name in ('scenario-default-wrong-state', 'scenario-default-missing-state',
                 'scenario-default-wrong-subject', 'scenario-negated-state-wrong',
                 'temporal-parsed-state-wrong', 'scenario-exception', 'temporal-unless',
                 'scenario-if-event', 'scenario-if-event-wrong-polarity'):
        assert observed[name][0]['existing_applicability'] is False
        assert observed[name][0]['constraint_spans']
    assert observed['quoted-marker'][0]['constraint_spans'] == []


def test_research_compiler_uses_empty_typed_constraints_for_temporal_question(monkeypatch):
    monkeypatch.syspath_prepend(str(PATH))
    from typed_constraint_compiler import compile_typed_constraints
    from docmancer.docs.domain.query_reference_binding import resolve_references, ScopeKey
    question = 'When do QueueTasks run relative to returning the response?'
    references = resolve_references(question, catalog=(), scope=ScopeKey('fixture', '', 'generation'),
                                    catalog_complete=True, document_suffixes=frozenset())
    contracts = compile_typed_constraints(question, references)
    assert len(contracts) == 1
    assert contracts[0].need.relation == 'temporal_order'
    assert contracts[0].constraint_spans == ()


def test_research_compiler_preserves_condition_and_unknown_controls(monkeypatch):
    monkeypatch.syspath_prepend(str(PATH))
    from typed_constraint_compiler import compile_typed_constraints, native_compile
    from temporal_condition_probe import MATRIX
    from docmancer.docs.domain.query_reference_binding import resolve_references, ScopeKey
    from docmancer.docs.application.need_context_disposition import _applicable_context
    controls = {}
    for name, _, question, body in MATRIX:
        refs = resolve_references(question, catalog=(), scope=ScopeKey('fixture', '', 'generation'),
                                  catalog_complete=True, document_suffixes=frozenset())
        current = compile_typed_constraints(question, refs)
        original = native_compile(question, refs)
        controls[name] = [_applicable_context(c, question, body) for c in current]
        for before, after in zip(original, current):
            from dataclasses import replace
            assert replace(after, constraint_spans=before.constraint_spans) == before
        if name in ('temporal-ru', 'temporal-with-state', 'temporal-unless', 'scenario-exception',
                    'scenario-if-event', 'scenario-if-event-wrong-polarity', 'quoted-marker'):
            assert current == original
    for name in ('temporal-en', 'temporal-ru-supported', 'scenario-default-match',
                 'scenario-negated-state-match', 'temporal-parsed-state-match'):
        assert controls[name] == [True]
    for name in ('scenario-default-wrong-state', 'scenario-default-missing-state',
                 'scenario-default-wrong-subject', 'scenario-negated-state-wrong',
                 'temporal-parsed-state-wrong', 'scenario-exception', 'temporal-unless'):
        assert controls[name] == [False]


def test_research_compiler_keeps_offsets_composition_and_private_tail(monkeypatch):
    monkeypatch.syspath_prepend(str(PATH))
    from typed_constraint_compiler import compile_typed_constraints, native_compile
    from docmancer.docs.domain.query_reference_binding import resolve_references, ScopeKey
    def refs(question):
        return resolve_references(question, catalog=(), scope=ScopeKey('fixture', '', 'generation'),
                                   catalog_complete=True, document_suffixes=frozenset())
    question = 'Please, what is OrbitClient default timeout when preview is disabled?'
    compiled = compile_typed_constraints(question, refs(question))
    assert [question[s.start:s.end] for s in compiled[0].constraint_spans] == ['preview', 'disabled']
    question = ('When do QueueTasks run relative to returning the response? '
                'Also identify the exact value chosen in our private production deployment.')
    compiled = compile_typed_constraints(question, refs(question))
    original = native_compile(question, refs(question))
    assert len(compiled) == len(original) == 2
    assert compiled[0].constraint_spans == ()
    assert compiled[1] == original[1]
    assert 'private production' in compiled[1].need.query_span_text
    composed = 'Which page title wins when the navigation configuration and Markdown content define different titles?'
    assert compile_typed_constraints(composed, refs(composed)) == native_compile(composed, refs(composed))
    assert compile_typed_constraints(question, refs('Other request?')) == native_compile(question, refs('Other request?'))
