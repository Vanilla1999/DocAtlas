"""Allocated inventory R6–R10 probes; context integrity is not answer approval."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import re
from types import MappingProxyType, SimpleNamespace

import pytest

from docmancer.docs.application import retrieval_need_support as needs
from docmancer.docs.application import _library_docs_service_shared as library
from docmancer.docs.application.library_source_discovery import _python_candidates
from docmancer.docs.application.model_visible_projection import _answer_text, _needs_actionable_limitation
from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain import _answer_units_part02 as proof_helpers
from docmancer.docs.domain._project_answer_contract_part01 import _cardinality
from docmancer.docs.domain.answer_units import extract_answer_units, local_proof_for_obligation
from docmancer.docs.domain.code_graph import CodeGraph, CodeGraphEdge, CodeGraphNode, score_code_graph_file
from docmancer.docs.domain.evidence_set_types import SourceKey
from docmancer.docs.domain.evidence_set_validation import build_dependency_sets, span_matches_source, validate_evidence_set
from docmancer.docs.domain.legacy_question_coverage import legacy_coverage_gaps
from docmancer.docs.domain.patch_request_plan import PatchRequestPlan, _operation, _target_list, build_patch_request_plan
from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.query_reference_binding import ScopeKey
from docmancer.docs.domain.source_dependency_graph import digest, source_graph


def source_key(raw):
    return SourceKey(ScopeKey('p', 'v', 's'), 'd', 'a.md', digest(raw))


@pytest.mark.parametrize('tail', ['It retries.', 'This rule prevents failure.', 'RelayClient means retry.'])
def test_inventory_graph_prose_does_not_infer_dependency_or_drop_context(tail):
    raw = '# H\n\nRelayClient handles work.\n\n' + tail + '\n'
    key = source_key(raw)
    graph = source_graph(raw, key)
    assert graph is source_graph(raw, key)
    assert {edge.kind for edge in graph.edges} == {'heading'}
    assert tail in [raw[ref.start:ref.end] for _, ref in graph.nodes]
    assert all(span_matches_source(ref, raw) for _, ref in graph.nodes)
    # These are structural proposals; no semantic independence/need proof flag.
    bundles, reasons = build_dependency_sets(raw, key, raw.index(tail), len(raw))
    assert bundles and not reasons
    assert all(not bundle.proposed_need_ids for bundle in bundles)
    assert not source_graph(raw + 'changed', key).nodes


@pytest.mark.parametrize('label', ['Examples:', 'Example:', 'Aliases:', 'Alias:', 'unknown:'])
def test_inventory_list_labels_are_members_with_complete_exact_closure(label):
    raw = '# H\n\nItems:\n- ' + label + '\n- alpha\n- beta\n'
    key = source_key(raw)
    graph = source_graph(raw, key)
    intro, children = graph.lists[0]
    assert len(children) == 3
    assert raw[children[0].start:children[0].end] == '- ' + label
    bundles, reasons = build_dependency_sets(raw, key, raw.index('alpha'), raw.index('alpha') + 5)
    assert bundles and not reasons
    record = {'source': {'scope': asdict(key.scope), 'document_id': key.document_id,
        'canonical_path': key.canonical_path, 'content_sha256': key.document_sha256}, 'raw_document': raw}
    for bundle in bundles:
        assert set((intro, *children)) <= set(bundle.member_spans)
        assert len(bundle.member_spans) <= 8
        assert validate_evidence_set(bundle, (), {key: record}) == ()
        assert all(span_matches_source(ref, raw) for ref in bundle.member_spans)
        forged = replace(bundle, member_spans=bundle.member_spans[:-1])
        assert validate_evidence_set(forged, (), {key: record})


def test_graph_table_hash_window_and_caps_remain_technical():
    raw = '# H\n\n| key | value |\n| --- | --- |\n| a | b |\n| c | d |\n'
    key = source_key(raw)
    assert any(edge.kind == 'table' for edge in source_graph(raw, key).edges)
    assert all(span_matches_source(ref, raw) for _, ref in source_graph(raw, key).nodes)
    assert build_dependency_sets(raw, key, -1, len(raw))[1] == ('source_window_mismatch',)
    for kwargs in ({'max_hops': 3}, {'max_spans': 9}, {'max_hops': True}):
        with pytest.raises(ValueError):
            build_dependency_sets(raw, key, 0, len(raw), **kwargs)
    long = '# H\n\nItems:\n' + ''.join(f'- item{i}\n' for i in range(9))
    bundles, reasons = build_dependency_sets(long, source_key(long), long.index('item0'), len(long))
    assert not bundles and reasons == ('dependency_budget_exceeded',)


@pytest.mark.parametrize('relation,text', [
    ('exception', 'RelayClient raises an exception'),
    ('requirement', 'how many RelayClient calls'),
    ('behavior', 'when FeatureFlag is disabled'),
    ('behavior', 'if FeatureFlag is not enabled'),
])
def test_inventory_need_proposals_unknown_and_inherited_credit_vetoed(relation, text):
    query = {'query_origin': 'retrieval_need', 'need_relation': relation,
        'need_subject': 'RelayClient', 'text': text}
    assert needs._state_condition(query) is None
    assert needs._need_obligations(query) == ()
    assert needs.retrieval_need_local_witness(query, text) is None
    trace = {'qualified': True, 'matched_need_ids': ['old'], 'need_local_witness': True,
        'context_eligible': True, 'visible_text': text, 'source': 'a.md'}
    before = deepcopy(trace)
    result = needs.apply_retrieval_need_witness(query, MappingProxyType(trace), text)
    assert not result['qualified'] and trace == before
    assert not {'matched_need_ids', 'need_local_witness', 'context_eligible'} & result.keys()
    assert result['visible_text'] == text and result['source'] == 'a.md'
    assert needs.apply_retrieval_need_witness({'query_origin': 'original'}, trace, text) == trace


def test_default_need_still_calls_real_hook_and_requires_fresh_true(monkeypatch):
    calls = []
    def hook(query, text):
        calls.append((query, text))
        return False, ()
    monkeypatch.setattr(needs, 'default_local_witness', hook)
    query = {'query_origin': 'retrieval_need', 'need_relation': 'default'}
    result = needs.apply_retrieval_need_witness(query, {'qualified': True}, 'original quote')
    assert calls == [(query, 'original quote')]
    assert not result['qualified']


def test_inventory_reference_word_no_longer_adds_seven_points():
    file = CodeGraphNode(id='file:a.py', kind='file', name='a.py', path='a.py', language='python')
    edge = CodeGraphEdge(id='edge:ref', kind='references', from_node_id=file.id,
        from_path='a.py', to_path='b.py', symbol='RelayClient', confidence='parser', confidence_score=0.9)
    graph = CodeGraph(nodes=[file], edges=[edge])
    baseline, reasons = score_code_graph_file(graph, file, question='RelayClient')
    assert baseline == 2.5
    assert score_code_graph_file(graph, file, question='use RelayClient') == (baseline, reasons)
    assert not any('reference_intent' in reason for reason in reasons)
    assert graph.edges == [edge]


@pytest.mark.parametrize('query', ['explain foo_bar and baz_qux', 'explain foo and bar',
    'describe attributes foo_bar plus baz_qux', 'what do `foo_bar` or `baz_qux` mean?'])
def test_inventory_library_prose_never_manufactures_explicit_list_requirements(query):
    assert library._explicit_library_query_analysis(query) == ([], False)
    assert library._explicit_library_query_values(query) == []


def test_library_original_ui_prose_and_typed_rst_budget_preserved():
    text = 'copy\ntranslation\ntranslated by someone\nreal statement'
    assert library._clean_library_section(text) == text
    rst = '.. module:: relay\n\n.. function:: foo_bar(x)\n\ncopy\ntranslation\n' + 'x ' * 6000
    sections = library._rst_symbol_sections(rst)
    assert sections[0]['symbols'] == ('foo_bar', 'relay.foo_bar')
    requirements = build_requirements('original topic', profile='library_docs_answer',
        public_requirements=['relay.foo_bar'])
    assert any(row.value == 'relay.foo_bar' for row in requirements)
    # Oversized exact sections cannot be silently truncated into an answer.
    chunk = SimpleNamespace(text=rst, source='https://example.org/a', metadata={})
    bounded, diagnostics = library._bounded_library_evidence_chunks([chunk], requirements=requirements, max_tokens=500)
    assert not bounded
    assert diagnostics['bounded_evidence']['rejected_oversized_sources'] == 1
    assert chunk.text == rst
    small = '.. module:: relay\n\n.. function:: foo_bar(x)\n\ncopy\ntranslation\n'
    raw = small + '\n.. function:: other(x)\n\n' + 'z ' * 6000
    chunk = SimpleNamespace(text=raw, source='https://example.org/a', metadata={'stable_chunk_id': 'parent'})
    bounded, diagnostics = library._bounded_library_evidence_chunks([chunk], requirements=requirements, max_tokens=500)
    assert len(bounded) == 1 and diagnostics['bounded_evidence']['derived_excerpts'] == 1
    excerpt = bounded[0].text
    assert excerpt in raw and 'copy\ntranslation' in excerpt
    assert bounded[0].metadata['source_excerpt_sha256'] == hashlib.sha256(excerpt.encode()).hexdigest()
    assert bounded[0].metadata['parent_logical_id'] == 'parent'
    assert len(excerpt.encode()) <= diagnostics['bounded_evidence']['available_tokens'] * 4


@pytest.mark.parametrize('topic', ['explain foo and bar', 'explain foo_bar and baz_qux'])
def test_real_library_read_keeps_original_topic_context_and_unknown_support(tmp_path, monkeypatch, topic):
    from tests.test_source_isolation_regression import _service, _register, _chunk, RecordingAgent
    source = 'https://docs.python.org/3.13/library/relay.html'
    text = 'copy\ntranslation\nfoo_bar and baz_qux are source quotes.'
    chunk = _chunk(text, source, {'stable_chunk_id': 'relay-source',
        'library_id': 'python:python@3.13:api', 'canonical_id': 'python:python@3.13:api',
        'ecosystem': 'python', 'version': '3.13', 'source_type': 'api'})
    agent = RecordingAgent([chunk])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library='python', ecosystem='python', version='3.13', docs_url=source)
    result = service.get_docs('python', ecosystem='python', version='3.13', source_type='api', topic=topic)
    assert result.topic == topic
    assert result.results and result.context_available
    assert agent.query_calls == [topic]
    assert result.results[0].content == text
    assert not result.answer_supported and not result.answer_available
    assert result.support_status != 'supported'
    assert result.resolved_version == '3.13'
    assert result.diagnostics['retrieval']['requested']['raw_topic_sha256'] == hashlib.sha256(topic.encode()).hexdigest()


def test_inventory_registry_label_bonus_removed_url_order_stays_confirmable():
    urls = {'Reference': 'https://example.org/b', 'Other': 'https://example.org/a'}
    rows = _python_candidates({'info': {'project_urls': urls}}, 'sample', '1.2.3')
    swapped = _python_candidates({'info': {'project_urls': {'Other': urls['Reference'], 'Docs': urls['Other']}}}, 'sample', '1.2.3')
    assert [row['docs_url'] for row in rows] == ['https://example.org/a', 'https://example.org/b']
    assert [row['docs_url'] for row in swapped] == [row['docs_url'] for row in rows]
    assert all(row['confidence'] == 'medium' and row['evidence_decision'] == 'confirm' for row in rows)
    assert all(row['evidence']['authority']['status'] == 'unconfirmed' for row in rows)
    assert all(row['arguments_patch']['version'] == '1.2.3' for row in rows)
    assert _python_candidates({'info': {'project_urls': {'Docs': 'https://u:p@example.org/a', 'Other': 'http://example.org/b'}}}, 'sample', None) == []


@pytest.mark.parametrize('text,expected', [('two tools', None), ('два инструмента', None),
    ('2 tools', 2), ('32 tools', 32), ('33 tools', None), ('0 tools', None), ('132 tools', None), ('x2 tools', None)])
def test_inventory_cardinality_only_bounded_explicit_digits(text, expected):
    assert _cardinality(text) == expected


@pytest.mark.parametrize('text', ['delete lib/a.py', 'rename lib/a.py to lib/b.py',
    'modify lib/a.py without changing lib/b.py so that it works', 'удали lib/a.py'])
def test_inventory_patch_request_negative_abi_and_literal_spans(text):
    plan = build_patch_request_plan(text)
    assert plan.operation == 'none' and plan.unresolved_parts
    assert not plan.mutation_targets and not plan.consumed_spans
    assert _operation(text.split()[0]) == 'none'
    assert plan.plan_hash == build_patch_request_plan(text).plan_hash
    start = text.index('lib/a.py')
    targets, error = _target_list(text, start=start, end=start + 8, role='mutate')
    assert error is None and targets[0].value == 'lib/a.py'
    assert text[targets[0].query_span_start:targets[0].query_span_end] == 'lib/a.py'
    typed = PatchRequestPlan('modify', (replace(targets[0], provenance='explicit_task_contract'),))
    assert typed.operation == 'modify' and typed.plan_hash != plan.plan_hash
    assert 'mutation_authorized' not in typed.hash_payload


def test_patch_literal_separator_and_input_caps_are_not_nl_grammar():
    targets, error = _target_list('lib/a.py, lib/b.py', start=0, end=18, role='preserve')
    assert len(targets) == 2 and error is None
    assert all(row.polarity == 'preserve' for row in targets)
    assert _target_list('lib/a.py and lib/b.py', start=0, end=20, role='mutate')[1]
    assert build_patch_request_plan('x' * 4001).unresolved_parts == ('input_limit:question',)
    with pytest.raises(ValueError):
        PatchRequestPlan('modify', (targets[0],) * 13)


def test_inventory_hardcoded_legacy_question_exception_is_unresolved():
    question = 'How does exact-term recall improve without widening authority?'
    rows = [SimpleNamespace(relation='recall_mechanism'), SimpleNamespace(relation='authority_invariant')]
    assert legacy_coverage_gaps(question, rows) == ('legacy_unresolved:semantic_coverage_unknown',)
    assert legacy_coverage_gaps('unknown words', rows)
    assert legacy_coverage_gaps(question, ()) == ('unsupported_query:legacy_no_contract',)


@pytest.mark.parametrize('text', ['RelayClient returns values', 'RelayClient does not return values', 'не RelayClient'])
def test_dormant_negative_helpers_uniformly_veto_unknown_prose(text):
    from docmancer.docs.domain._answer_units_shared import _NEGATION_RE
    assert _NEGATION_RE.search(text) is not None
    assert proof_helpers._contract_fact_disclaimer(text)
    assert proof_helpers._predicate_is_negated(re.search('RelayClient', text), text)
    assert not proof_helpers._contract_fact_relation_valid(text)
    unit = replace(extract_answer_units(text)[0], proposition=True)
    assert not local_proof_for_obligation(ProofObligation('p', 'behavior', 'RelayClient'), unit).valid


def test_narrow_typed_equality_retains_exact_source_hash_no_answer_authority():
    text = 'RelayClient.timeout = "17 ms"'
    unit = extract_answer_units(text)[0]
    query = ProofObligation('p', 'exact_fact', 'RelayClient', attribute='timeout',
        subject_kind='config_key', value_kind='duration', expected_value='17 ms')
    assert unit.content_sha256 == hashlib.sha256(unit.text.encode()).hexdigest()
    assert text[unit.char_start:unit.char_end] == unit.text
    assert local_proof_for_obligation(query, unit, source={'content': text}).valid
    assert not local_proof_for_obligation(query, unit, source={'content': text + '; other'}).valid
    assert not local_proof_for_obligation(replace(query, expected_value='17'), unit).valid
    assert not unit.proposition


@pytest.mark.parametrize('answer', ['RelayClient works.', 'configure RelayClient to fast', 'RelayClient.timeout = 17', '```code```'])
def test_inventory_projection_no_actionability_exemption_and_quotes_unchanged(answer):
    question = 'How do I configure RelayClient?'
    assert _needs_actionable_limitation(question, answer)
    source = {'evidence_id': 'e', 'snippet': answer}
    assert _answer_text(question, {'answer': answer}, [source]) == (answer, ['e'], True)
    assert source['snippet'] == answer
