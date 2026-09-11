import json
import pytest
from eval.evidence_quality_v2.cost import model_visible_text, count_input, summarize_usage, percentiles
from eval.evidence_quality_v2.answers import assess_answer, context_answer_matrix

class BytesEncoder:
    def encode(self, text, **kwargs): return list(text.encode())

@pytest.mark.parametrize('payload',[{'s':'Привет 🌍'},{'s':'"\\\n\t'},{'s':'<|endoftext|>'}])
def test_choose_one_channel_not_double_count(payload):
    wire={'structuredContent':payload,'content':[{'type':'text','text':json.dumps(payload,ensure_ascii=True,indent=2)}]}
    structured=model_visible_text(wire,'structured');text=model_visible_text(wire,'text')
    assert json.loads(structured)==json.loads(text)==payload
    assert count_input(structured,BytesEncoder())['actual_tokens']==len(structured.encode())
    assert count_input(text,BytesEncoder())['actual_tokens']==len(text.encode())

@pytest.mark.parametrize('wire,mode',[({},'structured'),({},'text'),({},'both'),({'structuredContent':{'diagnostics':{}}},'structured')])
def test_invalid_channels_fail_closed(wire,mode):
    with pytest.raises(ValueError):model_visible_text(wire,mode)

def test_provider_usage_not_added_twice():
    result=summarize_usage([{'usage':{'input_tokens':100,'output_tokens':20,'cached_input_tokens':80,'reasoning_tokens':10}},
                           {'error':'timeout','usage':{'input_tokens':150,'output_tokens':5,'cached_input_tokens':100,'reasoning_tokens':0}}])
    assert result['provider_total_tokens']==275
    assert result['uncached_input_tokens']==70
    assert result['failed_attempts']==1

def test_absent_usage_is_not_zero():
    assert summarize_usage([{}])['provider_total_tokens'] is None
    assert summarize_usage([])['known_subtotals']['input_tokens'] is None
    assert percentiles([])['p95'] is None
    assert percentiles(range(1,21))=={'n':20,'p50':10,'p95':19}

@pytest.mark.parametrize('usage',[{'input_tokens':-1},{'input_tokens':True},{'input_tokens':1,'cached_input_tokens':2},{'output_tokens':1,'reasoning_tokens':2}])
def test_invalid_provider_counts(usage):
    with pytest.raises(ValueError):summarize_usage([{'usage':usage}])

@pytest.fixture
def record():
    case={'id':'a','project_group':'p','policy':{'version':'2'},'required_claims':[{'id':'approval','witness_sets':[{'parts':[{'text':'Deploy only after approval.'}]}]}]}
    payload={'sources':[{'evidence_id':'s','path_or_url':'a.md','snippet':'Deploy only after approval.'}]}
    return case,payload,{'a.md':{'project_group':'p','version':'2'}}

def test_correct_hash_does_not_validate_opposite_claim(record):
    c,p,r=record
    answer={'assertions':[{'claim_id':'approval','stance':'negated','evidence_ids':['s']}]}
    assert assess_answer(c,p,r,answer,valid_evidence_ids={'s'})['outcome']=='unsupported_claim'

def test_partial_with_gap_is_not_hallucination(record):
    c,p,r=record;c['required_claims'].append({'id':'unknown','witness_sets':[]})
    answer={'assertions':[{'claim_id':'approval','evidence_ids':['s']}],'explicit_gap':True}
    assert assess_answer(c,p,r,answer,valid_evidence_ids={'s'})['outcome']=='supported_partial'

def test_wrong_version_or_invalid_citation(record):
    c,p,r=record;r['a.md']['version']='3'
    a={'assertions':[{'claim_id':'approval','evidence_ids':['s']}]}
    assert assess_answer(c,p,r,a,valid_evidence_ids={'s'})['outcome']=='unsupported_claim'
    r['a.md']['version']='2'
    assert assess_answer(c,p,r,a,valid_evidence_ids=set())['outcome']=='unsupported_claim'

def test_refusal_is_na_not_perfect_support(record):
    c,p,r=record;out=assess_answer(c,p,r,{},valid_evidence_ids={'s'})
    assert out['outcome']=='unjustified_refusal' and out['support_ratio'] is None
    assert context_answer_matrix([out])[0]['count']==1

def test_unrecognized_extra_claim_goes_to_review(record):
    c,p,r=record
    out=assess_answer(c,p,r,{'assertions':[{'claim_id':'extra','evidence_ids':['s']}]},valid_evidence_ids={'s'})
    assert out['outcome']=='needs_review'
