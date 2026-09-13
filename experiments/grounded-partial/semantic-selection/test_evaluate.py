"""Counterexamples for the new diagnostic's union-of-spans semantics."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('semantic_h1_evaluate',Path(__file__).with_name('evaluate.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def item(text,start,end,path='a.md'):
    return {'key':text,'raw':{'text':text,'source':path,'metadata':{'line_span':[start,end]}}}

def case(text='First rule.\nExcept on failure.'):
    return {'id':'synthetic','required_claims':[{'witness_sets':[{'parts':[{'path':'a.md','line_start':1,'line_end':2,'text':text}]}]}]}

DOC={'a.md':'First rule.\nExcept on failure.\nFirst rule.\nExcept on failure.\n','b.md':'First rule.\nExcept on failure.\n'}

def test_two_children_can_supply_one_complete_witness():
    assert m.complete(case(),[item('First rule.',1,1),item('Except on failure.',2,2)],DOC)['complete']

def test_missing_exception_is_incomplete():
    assert not m.complete(case(),[item('First rule.',1,1)],DOC)['complete']

def test_same_text_at_wrong_occurrence_does_not_count():
    assert not m.complete(case(),[item('First rule.\nExcept on failure.',3,4)],DOC)['complete']

def test_other_source_does_not_count():
    assert not m.complete(case(),[item('First rule.\nExcept on failure.',1,2,'b.md')],DOC)['complete']

def test_tokens_truncated_from_scorer_are_not_visible():
    i=item('First rule.\nExcept on failure.',1,2)
    assert not m.complete(case(),[i],DOC,{i['key']:{'seen_text':'First rule.'}})['complete']

def test_fabricated_span_is_reported_unmapped():
    i=item('First rule. Except on success.',1,2)
    result=m.complete(case(),[i],DOC)
    assert not result['complete'] and result['unmapped']==[i['key']]
