from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest
from experiments.language_aware_context.pilot_io import (
    planning_messages, parse_plan, answering_messages, evidence_blocks,
    quote_window, validate_sources, freeze_file_hashes,
)


def test_planner_never_gets_body_gold_or_scope_authority():
    hint = {'shares': {'en': .8, 'ru': .2}, 'query_languages': ['en','ru'],
            'hint_only': True, 'gold': 'SOLUTION', 'body': 'SECRET', 'answer_supported': True}
    messages, literals = planning_messages('What about ` /-S` versus `/-S`?', hint)
    user = json.loads(messages[1]['content'])
    assert set(user) == {'original_question', 'protected_literals', 'source_language_hint'}
    assert set(user['source_language_hint']) == {'shares', 'query_languages', 'hint_only'}
    assert 'SOLUTION' not in str(messages) and 'SECRET' not in str(messages)
    assert literals == (' /-S', '/-S')


def test_a_b_differ_only_by_hint_and_preserve_original():
    question = 'Если `x` не задан, когда выполняется запрос?'
    a, la = planning_messages(question, None)
    b, lb = planning_messages(question, {'shares': {'en':1}, 'query_languages':['en'], 'hint_only':True})
    assert a[0] == b[0] and la == lb
    au, bu = json.loads(a[1]['content']), json.loads(b[1]['content'])
    bu.pop('source_language_hint')
    assert au == bu and 'не' in au['original_question']


def test_literal_restoration_is_byte_exact():
    q = 'Compare ` /-S` and `/-S`'
    _, literals = planning_messages(q, None)
    actual = parse_plan('{"lookup_queries":["compare [[LIT_0]] versus [[LIT_1]]"]}', literals, q)
    assert actual == ('compare  /-S versus /-S',)


@pytest.mark.parametrize('raw', [
    '{}', '{"lookup_queries":[]}', '{"lookup_queries":["a","b"]}',
    '{"lookup_queries":"x"}', '{"lookup_queries":[4]}',
    '{"lookup_queries":["x"],"answer_supported":true}',
    '```json\n{"lookup_queries":["x"]}\n```',
    '{"lookup_queries":["'+('x'*241)+'"]}',
])
def test_malformed_plans_are_not_manually_repaired(raw):
    with pytest.raises((ValueError, TypeError)):
        parse_plan(raw, (), 'original')


def test_missing_literal_rejected():
    with pytest.raises(ValueError):
        parse_plan('{"lookup_queries":["generic question"]}', ('--no-force',), 'q')


def test_only_final_snippets_are_visible_to_answerer():
    payload = {'sources':[{'path':'docs/a.md','snippet':'VISIBLE','content':'HIDDEN'}],
               'diagnostics': {'gold': 'SECRET'}, 'retrieved_candidates':['LEAK']}
    evidence = evidence_blocks(payload)
    messages = answering_messages('Q', evidence)
    assert evidence == [{'id':'S1','path':'docs/a.md','text':'VISIBLE'}]
    assert all(x not in str(messages) for x in ('HIDDEN','SECRET','LEAK'))


def test_oracle_and_empty_use_identical_answer_instruction():
    assert answering_messages('Q',[])[0] == answering_messages('Q',[{'id':'S1','text':'x'}])[0]


def test_quote_retains_original_whitespace_and_coordinates():
    text = 'intro\nA   condition\n  is required.\ntail'
    start,end,raw = quote_window(text, 'A condition is required.')
    assert raw == 'A   condition\n  is required.'
    assert text[start:end] == raw


@pytest.mark.parametrize('text,needle', [('X X','X'), ('Not allowed.','Allowed.'), ('abc',''), ('abc','abcd')])
def test_ambiguous_missing_or_modified_quote_fails_before_evaluation(text, needle):
    with pytest.raises(ValueError):
        quote_window(text, needle)


def test_blob_pin_is_verified_before_decoding_or_indexing():
    raw = 'Русский текст'.encode()
    pin = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    validate_sources(raw,pin)
    with pytest.raises(ValueError):
        validate_sources(raw+b' ',pin)


def test_freeze_changes_when_any_input_byte_changes(tmp_path):
    (tmp_path/'a').write_text('one')
    before = freeze_file_hashes(tmp_path,['a'])
    (tmp_path/'a').write_text('two')
    assert freeze_file_hashes(tmp_path,['a']) != before


def test_new_pilot_balance_and_exclusion():
    root=Path(__file__).resolve().parents[2]/'experiments/language_aware_context'
    tasks=json.loads((root/'pilot.tasks.json').read_text())
    protocol=json.loads((root/'pilot.protocol.json').read_text())
    assert len(tasks)==12 and len({t['id'] for t in tasks})==12
    assert {lang:sum(t['query_language']==lang for t in tasks) for lang in ('ru','en','mixed')} == {'ru':4,'en':4,'mixed':4}
    assert len({t['family'] for t in tasks})==4
    assert sum(not t['answerable'] for t in tasks)==3
    assert protocol['neighbor_assembly'] is False
    assert protocol['product_activation'] is False
    assert not any(s['repository'] in ('fastapi/typer','encode/httpx') for s in protocol['sources'])
