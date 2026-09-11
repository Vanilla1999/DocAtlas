from copy import deepcopy
import pytest
from eval.evidence_quality_v2.run import lexical_candidates, lookup_variant, load_protocol, summarize


def test_neutral_rank_changes_only_order_not_eligibility_or_text():
    rows=[{'path_or_url':'a.md','snippet':'generic introduction','line_start':1},
          {'path_or_url':'b.md','snippet':'connection timeout rule','line_start':2}]
    before=deepcopy(rows)
    result=lexical_candidates(rows,query_text={'query-original':'connection timeout'})
    assert result==[rows[1],rows[0]]
    assert rows==before
    assert sorted(map(repr,result))==sorted(map(repr,rows))


def test_lookup_experiments_keep_original_strings_and_no_gold():
    q='How is `uv.lock` used?'
    assert lookup_variant(q,'L-duplicate')==[q]
    assert lookup_variant(q,'L-explicit')==['uv.lock']
    assert lookup_variant(q,'A-current') is None
    assert lookup_variant(q,'L-nearby')==['deployment changelog maintenance']


def test_protocol_remains_bound_before_run():
    protocol,cases,manifest=load_protocol()
    assert len(cases)==80 and len(manifest['sources'])==14
    assert protocol['unseen_validation']=='NOT_MEASURED'


def test_failed_attempt_is_in_primary_denominator_and_cluster_pair():
    protocol,_,_=load_protocol()
    rows=[]
    for variant in ['A-current','B-no-canonical']:
        rows.append({'id':'one','project':'neutral','family':'condition','split':'development',
            'answerability':'within_budget','variant':variant,'error':'intentional operational error'})
    summary=summarize(rows,protocol)
    assert summary['variants']['A-current']['within_budget']==1
    assert summary['variants']['A-current']['operational_errors']==1
    assert summary['paired']['B-no-canonical']['comparative_outcome']=='INCONCLUSIVE'


def test_nested_code_snippet_is_exact_observed_text_not_a_mapping():
    from eval.evidence_quality_v2.trace import source_span
    from eval.evidence_quality_v2.run import _stage_sources
    row=source_span({'source_path':'docs/deploy.md','snippet':{'code':'Only after approval.','why_relevant':'metadata'},'line_start':4,'line_end':4})
    assert row['snippet']=='Only after approval.'
    assert row['path_or_url']=='docs/deploy.md'
    assert len(_stage_sources([row,row]))==1


def test_grounded_mapping_does_not_fill_unseen_gaps(tmp_path):
    from eval.evidence_quality_v2.grounded import extract_visible_sources
    document='# Rule\n\nAlways validate.\n\nDo not deploy without approval.\n\nEnd.\n'
    text=f'Result 1: {(tmp_path/"guide.md").as_uri()}\n\n# Rule\nAlways validate.\nEnd.\n'
    sources,report=extract_visible_sources(text,tmp_path,{'guide.md':document})
    assert all('approval' not in s['snippet'] for s in sources)
    assert report['native_results']==1
    assert all(s['snippet'] in document for s in sources)


def test_grounded_no_path_escape_or_unseen_source(tmp_path):
    from eval.evidence_quality_v2.grounded import extract_visible_sources
    sources,report=extract_visible_sources('Result 1: file:///not-our-corpus.md\n\nDeploy now.',tmp_path,{})
    assert not sources and report['binding_errors']


def test_adapter_drops_whole_blocks_never_trims_required_negation(monkeypatch):
    import eval.evidence_quality_v2.grounded as g
    monkeypatch.setattr(g,'count_input',lambda text:dict(actual_tokens=len(text),utf8_bytes=len(text)))
    sources=[{'evidence_id':'one','path_or_url':'a','snippet':'not '+('x'*800),'line_start':1,'line_end':1},
             {'evidence_id':'two','path_or_url':'b','snippet':'Only after approval.','line_start':1,'line_end':1}]
    out=g.controlled_context(sources,max_tokens=400,max_sources=3)
    assert out['dropped_whole_source_blocks']==1
    assert out['payload']['sources']==[sources[1]]


def test_absence_record_is_not_forged_into_a_source_path():
    from eval.evidence_quality_v2.trace import source_span
    from eval.evidence_quality_v2.run import _stage_sources
    source=source_span({'source':{'evidence_class':'absent_in_source'},'snippet':'absent_in_source'})
    assert source['path_or_url'] is None and source['non_source_record']
    assert _stage_sources([source])[0]['path_or_url'] is None


def test_duplicate_array_is_rejected_by_existing_public_schema():
    import jsonschema
    from pathlib import Path
    import ast
    data=Path(__file__).resolve().parents[2]/'docmancer/mcp/_docs_server_tool_data.py'
    assert '"uniqueItems": True' in data.read_text()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(['question','question'],{'type':'array','uniqueItems':True})
