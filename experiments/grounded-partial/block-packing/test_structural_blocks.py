from copy import deepcopy
import hashlib
import pytest
from structural_blocks import BlockIndex, installed
from docmancer.docs.application import docs_context_projection as p
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection


def source(document, snippet=None):
    snippet = document if snippet is None else snippet
    start = document.index(snippet)
    return {'content': snippet, 'path': 'api.md', 'path_or_url': 'api.md', 'char_start': start,
            'char_end': start + len(snippet), 'source_class': 'project_doc', 'source_kind': 'docs',
            'project_identity': 'p', 'authority': 'source_of_truth', 'doc_scope': 'project',
            'line_start': 1 + document[:start].count('\n'), 'line_end': 1 + document[:start+len(snippet)].count('\n'),
            'heading_path': 'DataStream', 'version': '1', 'freshness': 'current', 'index_freshness': 'synchronized',
            'lifecycle_status': 'active', '_source_snapshot_sha256': hashlib.sha256(document.encode()).hexdigest()}


def texts(document, snippet=None):
    s = source(document, snippet)
    return [s['content'][a:b] for a,b in BlockIndex({'api.md': document}).alternatives(s, s['content'])]


def retrieve(document):
    s = source(document)
    question = 'How does DataStream process batches?'
    probe = {'query_terms': ['datastream','process','batches'], 'exact_terms': ['datastream'],
             'query_text': question, 'relation': 'direct'}
    s['retrieval_query_matches'] = {'query-original': probe}
    s['retrieval_query_ids'] = ['query-original']
    return {'context_pack':[s], 'question': question, 'project_identity': 'p',
            'documentation_query_plan': {'original_question': question, 'public_query_ids':['query-original'],
                'required_query_ids':['query-original'], 'queries':[{'query_id':'query-original','text':question,'origin':'original'}],
                'unresolved_parts':['context_only:behavior']}}


def run(document, flags=None):
    x = retrieve(document)
    x['context_pack'][0].update(flags or {})
    d = {}
    with installed(BlockIndex({'api.md':document}), d):
        payload, snapshot = p.project_docs_context(retrieval=x)
    assert not validate_model_visible_projection(payload,snapshot=snapshot,max_tokens=800)
    return payload, d


def test_long_intro_cannot_hide_complete_list():
    items = '- alpha: process batches.\n- beta: process batches.\n- gamma: process batches.'
    for intro in ('Brief introduction.', 'Long introduction. '*90):
        assert items in texts(intro+'\n\n'+items)


def test_whole_list_and_items_are_offered():
    t='- alpha: process batches.\n- beta: process batches.'
    tt=texts(t)
    assert t in tt and '- alpha: process batches.' in tt and '- beta: process batches.' in tt


def test_nested_list_stays_with_parent_item():
    t='- alpha:\n  - Nested condition.\n  - Nested exception.\n- beta: Other value.'
    tt=texts(t)
    assert t in tt
    assert '- alpha:\n  - Nested condition.\n  - Nested exception.' in tt
    assert '- Nested exception.' not in tt


def test_table_never_turns_into_orphan_cell_or_row():
    t='| Mode | Rule |\n| --- | --- |\n| alpha | process |\n| beta | skip |'
    assert texts(t)==[t]


def test_code_is_whole():
    t='```python\nfor item in batches:\n    process(item)\n```'
    assert texts(t)==[t]


def test_unclosed_code_is_not_called_complete():
    assert texts('```python\nprocess(batches)')==[]


def test_heading_alone_not_evidence():
    assert texts('# DataStream')==[]


def test_html_unsupported_no_substrings():
    assert texts('<script>\nprocess(batches)\n</script>')==[]


def test_no_cross_section_union():
    t='# Alpha\n\nFirst paragraph.\n\n# Beta\n\nSecond paragraph.'
    assert not any('First paragraph.' in x and 'Second paragraph.' in x for x in texts(t))


def test_incomplete_paragraph_at_chunk_edge_not_promoted():
    doc='One complete sentence; this is the remainder of a single paragraph.'
    assert texts(doc, 'this is the remainder of a single paragraph.')==[]


def test_cannot_read_outside_candidate():
    doc='First paragraph.\n\nSecond paragraph.'
    assert texts(doc, 'First paragraph.')==['First paragraph.']


def test_colon_leadin_not_detached():
    doc='The following modes:\n\n- alpha: process.\n- beta: skip.'
    tt=texts(doc)
    assert 'The following modes:' not in tt and doc in tt


def test_large_fitting_paragraph_reaches_full_dto():
    doc='DataStream can process batches. '+'processing '*145+'This finishes every batch.'
    assert len(doc)>1500
    result,_=run(doc)
    assert result['sources'][0]['snippet']==doc
    assert p.docs_context_budget_tokens(result)<=800


def test_overbudget_block_is_not_arbitrarily_truncated():
    doc='DataStream can process batches. '+'processing '*1800+'This finishes every batch.'
    result,_=run(doc)
    assert not result.get('sources')
    assert result['status']=='insufficient_evidence'


@pytest.mark.parametrize('flags',[{'project_identity':'foreign'},{'stale':True},{'freshness':'old'},
    {'index_freshness':'old'},{'risk_flags':['unsafe']},{'source_class':'code'}])
def test_source_guards_remain(flags):
    result,_=run('DataStream can process batches safely.',flags)
    assert not result.get('sources')


def test_wrong_offset_gets_no_variants():
    doc='One complete paragraph.'; s=source(doc); s['char_start']=1
    assert not BlockIndex({'api.md':doc}).alternatives(s,doc)


def test_unknown_path_cannot_supply_text():
    s=source('One complete paragraph.');s['path']='other.md'
    assert not BlockIndex({'api.md':s['content']}).alternatives(s,s['content'])


def test_no_source_mutation():
    s=source('One complete paragraph.');old=deepcopy(s)
    BlockIndex({'api.md':s['content']}).alternatives(s,s['content'])
    assert s==old


def test_seams_restored_after_exception():
    f,e=p._qualified_fragments,p._expand_selected_snippets
    with pytest.raises(RuntimeError):
        with installed(BlockIndex({}),{}):
            raise RuntimeError('deliberate')
    assert p._qualified_fragments is f and p._expand_selected_snippets is e


def test_3000_chars_offered_whole_but_subject_to_actual_dto_admission():
    doc='DataStream can process batches. '+'processing '*275+'This finishes every batch.'
    assert len(doc)>3000 and texts(doc)==[doc]
    x=retrieve(doc); diagnostics={}
    with installed(BlockIndex({'api.md':doc}),diagnostics):
        result,_=p.project_docs_context(retrieval=x)
    assert not result.get('sources')
    assert diagnostics['fragment_calls'][0]['qualified'][0]['snippet']==doc
    assert x['retrieval_diagnostics']['docs_context_projection']['budget_rejections']==1
