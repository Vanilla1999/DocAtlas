"""Literal root context must not become semantic interpretation or proof."""
from dataclasses import FrozenInstanceError, asdict, replace
from hashlib import sha256

import pytest

from docmancer.docs.application.need_context_disposition import classify_need_context
from docmancer.docs.domain.evidence_set_types import SourceKey
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.query_reference_binding import (
    CatalogSource, ScopeKey, resolve_references,
)
from docmancer.docs.domain.question_retrieval_needs import retrieval_needs


QUESTIONS = (
    '  If `Client.send` fails, which exception is raised? What is its default?\n',
    'Если `Client.send` завершится ошибкой, что произойдёт? Каково значение по умолчанию?',
    'Compare `Client.send` and `Client.read` when preview is disabled; explain both.',
    'Сравни `Client.send` и `Client.read`, только если режим отключён; объясни оба.',
    'List three categories of `Client.send`; explain each and then configure it.',
    'Перечисли три категории `Client.send`; объясни каждую, затем настрой её.',
    'Why is this required? How is it configured? Which prerequisites apply?',
    'Почему это требуется? Как это настроено? Какие условия необходимы?',
    'ordinary question with no literal identity',
    '\tВопрос без технических символов.\r\n',
)
SCOPE = ScopeKey('literal-project', 'v1', 'literal-snapshot')


def plan(question):
    return resolve_references(question, catalog=(), scope=SCOPE)


@pytest.mark.parametrize('question', QUESTIONS)
def test_full_original_is_one_unresolved_need_and_contract(question):
    (need,) = retrieval_needs(question)
    (contract,) = compile_need_contracts(question, plan(question))
    for current in (need, contract.need):
        assert current.query_span_text.encode('utf-8') == question.encode('utf-8')
        assert (current.query_span_start, current.query_span_end) == (0, len(question))
        assert current.subject == current.context == ''
        assert current.relation == 'unresolved'
    assert need.need_id == 'need-1'
    assert contract.need.need_id == 'sentence-1'
    assert contract.interpretation == 'unresolved'
    assert contract.requirement == 'unknown' and contract.expected_count is None
    assert contract.constraint_spans == contract.prerequisite_need_ids == ()
    assert contract.alternative_spans == contract.category_spans == ()
    assert retrieval_needs(question) == (need,)
    assert compile_need_contracts(question, plan(question)) == (contract,)
    with pytest.raises(FrozenInstanceError):
        need.subject = 'inferred'
    with pytest.raises(FrozenInstanceError):
        contract.interpretation = 'supported'


@pytest.mark.parametrize('question', ['', ' ', '\n\t', '\r\n'])
def test_blank_input_has_no_needs(question):
    assert retrieval_needs(question) == compile_need_contracts(question, plan(question)) == ()


@pytest.mark.parametrize('question', QUESTIONS)
def test_default_compilers_do_not_call_semantic_or_compositional_parsers(monkeypatch, question):
    from docmancer.docs.domain import (
        admission_grammar, need_composition, question_frame_core, question_semantic_frames,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError('default needs called a semantic parser')

    for module, names in (
        (admission_grammar, ('parse_admission_frame',)),
        (need_composition, ('independent_sentence_spans', 'mask_protected', 'compositional_parts')),
        (question_frame_core, ('split_question_clause_spans',)),
        (question_semantic_frames, ('match_comparison_frame',)),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    # Fresh original bytes bypass any previous immutable syntax cache entry.
    original = question + '\n  '
    assert len(retrieval_needs(original)) == 1
    assert compile_need_contracts(original, plan(original))[0].interpretation == 'unresolved'


@pytest.mark.parametrize('locator', ['docs/Guide.md', r'docs\Guide.md', '`Guide.md`', 'Guide.md'])
def test_paths_are_not_body_symbols_or_subjects(locator):
    question = f'В {locator} объясни `Client.send` и Client.send.'
    (contract,) = compile_need_contracts(question, plan(question))
    assert contract.need.hard_exact == ('client.send',)
    assert contract.need.subject == ''
    assert tuple(question[s.start:s.end] for s in contract.focus_spans) == ('Client.send', 'Client.send')


def test_path_like_non_document_literal_does_not_nominate_symbol_or_subject():
    need = retrieval_needs('`src/client.py` src/client.py `Client.send`')[0]
    assert need.hard_exact == ('client.send',) and need.subject == ''


def test_significant_literal_whitespace_and_occurrences_remain_original():
    question = 'О `Client.  send` и `Client.  send`: когда и почему?'
    contract = compile_need_contracts(question, plan(question))[0]
    assert contract.need.hard_exact == ('client.  send',)
    assert tuple(question[s.start:s.end] for s in contract.focus_spans) == ('Client.  send',) * 2


@pytest.mark.parametrize('mutation', ['question', 'span', 'hash', 'role', 'missing', 'object'])
def test_bad_reference_inputs_cannot_acquire_authority_or_weaken_symbols(mutation):
    question = 'If `Client.send` fails, list three outcomes and explain each.'
    original = plan(question)
    bad = original
    if mutation == 'question':
        bad = replace(original, question='other')
    elif mutation in {'span', 'hash', 'role'}:
        ref = original.references[0]
        if mutation == 'role':
            ref = replace(ref, role='source_locator', state='resolved', source_ids=('forged',))
        else:
            mention = replace(ref.mention, **({'start': -1} if mutation == 'span' else {'mention_id': 'forged'}))
            ref = replace(ref, mention=mention)
        bad = replace(original, references=(ref,))
    elif mutation == 'missing':
        bad = replace(original, references=())
    elif mutation == 'object':
        bad = object()
    assert compile_need_contracts(question, bad) == compile_need_contracts(question, original)
    assert compile_need_contracts(question, bad)[0].need.hard_exact == ('client.send',)


def prepared_context(question, body, path='docs/Client.send.md'):
    digest = sha256(body.encode()).hexdigest()
    source = CatalogSource('guide', SCOPE, path, digest)
    references = resolve_references(question, catalog=(source,), scope=SCOPE)
    contract = compile_need_contracts(question, references)[0]
    key = SourceKey(SCOPE, source.document_id, source.canonical_path, digest)
    candidate = {'source_class': 'project_doc', 'project_identity': SCOPE.project_id,
        'resolved_version': SCOPE.version, 'generation_id': SCOPE.snapshot_id,
        'path_or_url': source.canonical_path, 'char_span': [0, len(body)],
        'snippet': body, 'authority': 'source_of_truth',
        '_reference_root_plan': asdict(references),
        '_reference_plans': {question: asdict(references)},
        '_reference_evidence': {'schema_version': 1, 'source': asdict(source),
            'raw_document': body, 'text': body, 'char_start': 0, 'char_end': len(body), 'owner': None}}
    return contract, {'reference_plan': references, 'candidate': candidate,
        'bundles': (), 'prepared_sources': {key: {'source': asdict(source), 'raw_document': body}}}


def test_actual_prepared_locator_and_symbol_body_is_context_not_root_proof():
    question = 'docs/Client.send.md `Client.send` returns a value'
    body = 'Client.send returns a value.\n'
    contract, args = prepared_context(question, body)
    assert contract.need.hard_exact == ('client.send',)
    # Exercise the real occurrence-aware qualifier before the context consumer:
    # the locator is a path obligation, the separate symbol a body obligation.
    qualified = qualify_evidence({'query_text': question, 'query_origin': 'original',
        'relation': 'direct'}, query_id='query-original', visible_text=body,
        evidence_text=body, candidate=args['candidate'],
        expected_project_identity=SCOPE.project_id,
        authoritative_query={'query_id': 'query-original', 'origin': 'original',
            'relation': 'direct', 'text': question})
    assert qualified.qualified, qualified.trace
    assert qualified.trace['exact_terms'] == ['client.send']
    assert qualified.trace['missing_exact_terms'] == []
    assert {b['field'] for b in qualified.trace['reference_bindings']} == {'path', 'body'}
    forged = replace(contract, interpretation='supported', requirement='scalar')
    assert classify_need_context(forged, **args).reason == 'need_contract_mismatch'
    result = classify_need_context(contract, **args)
    assert result.state == 'retrieval_only', result
    assert result.set_id is None


def test_separate_colliding_symbol_still_requires_body_occurrence():
    question = 'docs/Client.send.md `Client.send` returns a value'
    contract, args = prepared_context(question, 'Another.client returns a value.\n')
    assert contract.need.hard_exact == ('client.send',)
    assert classify_need_context(contract, **args).state == 'blocked'


@pytest.mark.parametrize('mutation', ['project', 'snapshot', 'path', 'hash', 'mention', 'body_symbol'])
def test_literal_root_qualification_keeps_source_and_symbol_guards(mutation):
    question = 'docs/Client.send.md `Client.send` returns a value'
    body = 'Client.send returns a value.\n'
    if mutation == 'body_symbol':
        body = 'Other.client returns a value.\n'
    contract, args = prepared_context(question, body)
    candidate = args['candidate']
    if mutation == 'project':
        candidate['project_identity'] = 'foreign'
    elif mutation == 'snapshot':
        candidate['generation_id'] = 'old'
    elif mutation == 'path':
        candidate['path_or_url'] = 'docs/Other.md'
    elif mutation == 'hash':
        candidate['source_content_hash'] = '0' * 64
    elif mutation == 'mention':
        candidate['_reference_root_plan']['references'][0]['mention']['mention_id'] = 'forged'
    result = qualify_evidence({'query_text': question, 'query_origin': 'original',
        'relation': 'direct', 'exact_terms': list(contract.need.hard_exact)},
        query_id='query-original', visible_text=body, evidence_text=body,
        candidate=candidate, expected_project_identity=SCOPE.project_id,
        authoritative_query={'query_id': 'query-original', 'origin': 'original',
            'relation': 'direct', 'text': question})
    assert not result.qualified, result.trace


def test_verified_quoted_catalog_stem_is_context_without_body_locator():
    question = '"Guide" returns a value'
    body = 'Startup returns a value.\n'
    contract, args = prepared_context(question, body, path='docs/Guide.md')
    references = args['reference_plan']
    assert references.references[0].role == 'source_locator'
    assert retrieval_needs(question)[0].hard_exact == ('guide',)
    assert contract.need.hard_exact == () and contract.focus_spans == ()
    result = classify_need_context(contract, **args)
    assert result.state == 'retrieval_only', result
    assert contract.interpretation == 'unresolved' and contract.requirement == 'unknown'
    assert result.set_id is None


def quoted_stem_plan(question):
    catalog = CatalogSource('guide', SCOPE, 'docs/Guide.md', 'a' * 64)
    return resolve_references(question, catalog=(catalog,), scope=SCOPE)


def test_verified_locator_does_not_remove_separate_same_spelling_backtick_symbol():
    question = '"Guide" `Guide` returns a value'
    references = quoted_stem_plan(question)
    assert [ref.role for ref in references.references] == ['source_locator', 'symbol_identity']
    contract = compile_need_contracts(question, references)[0]
    assert contract.need.hard_exact == ('guide',)
    assert tuple(question[s.start:s.end] for s in contract.focus_spans) == ('Guide',)
    assert contract.focus_spans[0].start == question.index('`Guide`') + 1
    contract, args = prepared_context(question, 'Startup returns a value.\n', path='docs/Guide.md')
    assert classify_need_context(contract, **args).state == 'blocked'
    contract, args = prepared_context(question, 'Guide returns a value.\n', path='docs/Guide.md')
    result = classify_need_context(contract, **args)
    assert result.state == 'retrieval_only', result


@pytest.mark.parametrize('mutation', [
    'question', 'mention_id', 'start', 'text', 'explicit', 'syntax_role',
    'state', 'reason', 'empty_ids', 'multiple_ids', 'incomplete', 'scope', 'missing', 'duplicate',
])
def test_malformed_quoted_stem_reference_cannot_remove_literal_obligation(mutation):
    question = '"Guide" returns a value'
    references = quoted_stem_plan(question)
    ref = references.references[0]
    if mutation == 'question':
        references = replace(references, question='other')
    elif mutation in {'mention_id', 'start', 'text', 'explicit', 'syntax_role'}:
        values = {'mention_id': 'forged', 'start': -1, 'text': 'Other',
            'explicit': False, 'syntax_role': 'source_locator'}
        ref = replace(ref, mention=replace(ref.mention, **{mutation: values[mutation]}))
        references = replace(references, references=(ref,))
    elif mutation in {'state', 'reason', 'empty_ids', 'multiple_ids'}:
        changes = {'state': {'state': 'unresolved'}, 'reason': {'reason': 'forged'},
            'empty_ids': {'source_ids': ()}, 'multiple_ids': {'source_ids': ('guide', 'other')}}
        references = replace(references, references=(replace(ref, **changes[mutation]),))
    elif mutation == 'incomplete':
        references = replace(references, catalog_complete=False)
    elif mutation == 'scope':
        references = replace(references, scope=replace(SCOPE, snapshot_id=''))
    elif mutation == 'missing':
        references = replace(references, references=())
    elif mutation == 'duplicate':
        references = replace(references, references=(ref, ref))
    contract = compile_need_contracts(question, references)[0]
    assert contract.need.hard_exact == ('guide',)
    assert contract.interpretation == 'unresolved'
    _, args = prepared_context(question, 'Startup returns a value.\n', path='docs/Guide.md')
    args['reference_plan'] = references
    args['candidate']['_reference_root_plan'] = asdict(references)
    args['candidate']['_reference_plans'] = {question: asdict(references)}
    assert classify_need_context(contract, **args).state == 'blocked'


@pytest.mark.parametrize('question', ['`Guide` returns a value', 'Client.send returns a value'])
def test_forged_locator_role_on_non_stem_symbol_cannot_remove_obligation(question):
    references = plan(question)
    ref = replace(references.references[0], role='source_locator', state='resolved',
        reason='unique_catalog_source', source_ids=('guide',))
    bad = replace(references, references=(ref,))
    assert compile_need_contracts(question, bad)[0].need.hard_exact == retrieval_needs(question)[0].hard_exact


@pytest.mark.parametrize('literal,path', [
    ('"Guide"', 'docs/Other.md'),
    ('`Guide`', 'docs/Guide.md'),
    ('guide_name', 'docs/guide_name.md'),
])
def test_actual_context_forged_locator_cannot_waive_body_symbol(literal, path):
    question = f'{literal} returns a value'
    body = 'Startup returns a value.\n'
    _, args = prepared_context(question, body, path=path)
    original = args['reference_plan']
    assert len(original.references) == 1
    assert original.references[0].role == 'symbol_identity'
    source = args['candidate']['_reference_evidence']['source']
    forged = replace(original.references[0], role='source_locator', state='resolved',
        reason='unique_catalog_source', source_ids=(source['document_id'],))
    references = replace(original, references=(forged,))
    contract = compile_need_contracts(question, references)[0]
    args['reference_plan'] = references
    # Forge both serialized plans, retaining real source hashes, ID and bytes:
    # matching an allowed ID alone must not validate a literal locator identity.
    args['candidate']['_reference_root_plan'] = asdict(references)
    args['candidate']['_reference_plans'] = {question: asdict(references)}
    if literal != '"Guide"':
        assert contract.need.hard_exact == retrieval_needs(question)[0].hard_exact
        assert contract.need.hard_exact
    result = classify_need_context(contract, **args)
    assert result.state == 'blocked', result
    assert contract.interpretation == 'unresolved'
