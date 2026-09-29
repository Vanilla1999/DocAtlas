from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from tokenizers import Tokenizer, models, pre_tokenizers
from experiments.crosslingual_relevance.evaluation_v2 import (
    rank_full_pool, save_new_report, canonical_row, assess_packet, corpus_documents,
)
from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer
from experiments.crosslingual_relevance.context_rescue import installed, apply_rescue
from experiments.crosslingual_relevance.model_manifest import build_manifest, verify_manifest, REQUIRED
from experiments.crosslingual_relevance.mpnet_scorer import token_observation
from experiments.crosslingual_relevance.m6_holdout import valid_for_model_quality
from docmancer.docs.domain.evidence_qualification import EvidenceQualification


def blocks():
    return [{'block_id':str(i),'path':'file','text':f'document {i}'} for i in range(8)]


def judgments():
    return {'blocks':[{'block_id':str(i),'relevant_to_question':i==7,'source_allowed':True,
                      'covered_fact_ids':['fact'] if i==7 else []} for i in [0,1,2,7]]}


def test_all_blocks_ranked_before_gold_labels_are_attached():
    result=rank_full_pool(blocks(),[.9,.8,.7,.6,.5,.4,.3,.1],judgments())
    assert result['pool_size']==8
    assert result['known_allowed_positive_recall_at_k']==0
    assert result['unjudged_in_top_k']==2
    assert result['fully_judged'] is False
    assert result['semantic_false_positive_rate'] is None


def test_gold_first_input_does_not_bias_score_ties():
    b=blocks(); t=judgments()
    one=rank_full_pool(b,[.5]*8,t)['block_scores']
    two=rank_full_pool(list(reversed(b)),[.5]*8,t)['block_scores']
    assert one==two


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-float('inf')])
def test_ranking_rejects_nonfinite_rows(bad):
    with pytest.raises(ValueError): rank_full_pool(blocks(),[bad]*8,judgments())


def test_new_reports_cannot_overwrite_an_existing_result(tmp_path):
    path=tmp_path/'results.json';path.write_text('archived')
    with pytest.raises(FileExistsError): save_new_report(path,{'new':True})
    assert path.read_text()=='archived'


def test_nonfinite_metrics_are_not_written_as_json_nan(tmp_path):
    path=tmp_path/'result.json'
    with pytest.raises(ValueError): save_new_report(path,{'score':float('nan')})
    assert not path.exists()


def test_all_required_claims_are_anded_but_alternative_witnesses_are_ored():
    raw=corpus_documents('httpx')['docs/advanced/timeouts.md']
    # No text injection: actual canonical rule in actual cited lines.
    row={'path_or_url':'docs/advanced/timeouts.md','snippet':'\n'.join(raw.splitlines()[:4]),
         'line_start':1,'line_end':4}
    task={'id':'m15-dev-01','project':'httpx'}
    good=assess_packet({'sources':[row]},task,audit_errors=[])
    assert good['required_count']==2 and good['supported_count']==2
    assert good['verdict']=='PASS'
    row['snippet']=raw.splitlines()[0]
    partial=assess_packet({'sources':[row]},task,audit_errors=[])
    assert partial['supported_count']==1 and partial['verdict']=='FAIL'
    no_audit=assess_packet({'sources':[row]},task)
    assert no_audit['source_policy_status']=='NOT_EVALUATED'


@pytest.mark.parametrize('field,value',[('line_start',True),('line_start',0),('line_end',9999),
 ('source_content_hash','0'*64),('path_or_url','timeouts.md')])
def test_bad_source_coordinates_or_digest_are_never_gold(field,value):
    docs=corpus_documents('httpx');raw=docs['docs/advanced/timeouts.md']
    row={'path_or_url':'docs/advanced/timeouts.md','line_start':1,'line_end':4,
         'snippet':'\n'.join(raw.splitlines()[:4])}
    row[field]=value
    assert canonical_row(row,docs)['status']!='verified'


@pytest.fixture
def model_dir(tmp_path):
    root=tmp_path/'model'
    for name in REQUIRED:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('test:'+name).encode())
    return root


def test_model_manifest_binds_actual_files_not_block_count(model_dir):
    manifest=build_manifest(model_dir)
    assert len(manifest['fingerprint'])==64
    assert manifest['inference']['expected_dimensions']==768
    assert verify_manifest(model_dir,manifest)==manifest
    assert manifest['hub_revision'] is None  # Never invent a repo commit.


@pytest.mark.parametrize('name',sorted(REQUIRED))
def test_model_file_tampering_is_rejected(model_dir,name):
    manifest=build_manifest(model_dir)
    (model_dir/name).write_bytes(b'changed')
    with pytest.raises(ValueError): verify_manifest(model_dir,manifest)


def test_extra_model_file_is_not_silently_unpinned(model_dir):
    manifest=build_manifest(model_dir)
    (model_dir/'extra.bin').write_bytes(b'additional weights')
    with pytest.raises(ValueError): verify_manifest(model_dir,manifest)


def test_corrupted_manifest_is_rejected(model_dir):
    manifest=build_manifest(model_dir);manifest['inference']['pooling']='CLS'
    with pytest.raises(ValueError): verify_manifest(model_dir,manifest)


def test_repository_name_cannot_masquerade_as_revision(model_dir):
    with pytest.raises(ValueError): build_manifest(model_dir,'Xenova/model')


def test_external_model_symlink_is_rejected(model_dir,tmp_path):
    outside=tmp_path/'outside';outside.write_text('weights')
    (model_dir/'escape').symlink_to(outside)
    with pytest.raises(ValueError): build_manifest(model_dir)


def test_actual_tokenizer_used_length_is_separate_from_full_input():
    tok=Tokenizer(models.WordLevel({'[UNK]':0,'a':1,'b':2,'c':3,'d':4},unk_token='[UNK]'))
    tok.pre_tokenizer=pre_tokenizers.Whitespace()
    tok.enable_truncation(max_length=3)
    before=tok.to_str()
    result=token_observation(tok,'a b c d')
    assert result['full_token_count']==4 and result['used_token_count']==3
    assert result['truncated'] is True
    assert result['consumed_offsets']==[[0,1],[2,3],[4,5]]
    assert tok.to_str()==before


def test_other_threads_never_inherit_the_installing_question():
    import docmancer.docs.domain.evidence_qualification as eq
    calls=[]
    def qualify():
        return eq.qualify_evidence({'query_text':'question','query_terms':['zzzz']},
            query_id='q',visible_text='A long enough but unrelated source sentence about settings.',
            candidate={'project_identity':'local:test'})
    with installed(lambda q,t:calls.append(q) or .9,question='owner-question'):
        with ThreadPoolExecutor(max_workers=1) as executor:
            result=executor.submit(qualify).result()
        assert not result.qualified and calls==[]
        result=qualify()
        assert result.qualified and calls==['owner-question']


def test_overlapping_installation_fails_without_leaking_patches():
    def nested():
        with installed(lambda q,t:.9,question='other'): pass
    with installed(lambda q,t:.9,question='outer'):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(RuntimeError): executor.submit(nested).result()
    # Lock restored even after rejected competing installations.
    with installed(lambda q,t:.9,question='next'): pass


def test_score_trace_is_bounded_and_explicit_about_dropped_events():
    s=BoundedScorer(lambda q,t:.9,max_events=2)
    s.score('q','text');s.score('q','text');s.score('q','text')
    assert len(s.events)==2 and s.summary['events_dropped']==1
    assert 'evidence_text' not in s.events[0]
    events=s.events;events[0]['score']=0
    assert s.events[0]['score']==.9


def test_opt_in_actual_input_capture_and_source_binding():
    s=BoundedScorer(lambda q,t:.9,capture_text=True)
    eq=EvidenceQualification(False,(),None,'insufficient_visible_match',{})
    result=apply_rescue(eq,query_id='query-original',question='unchanged',evidence_text='A short real rule.',
        source_identity='local:test',source_binding={'path':'docs/a.md','snapshot':'fixed'},scorer=s)
    assert result.trace['context_relevance_binding']['source_binding']['path']=='docs/a.md'
    assert s.events[0]['evidence_text']=='A short real rule.'
    assert result.covered_query_ids==() and result.trace['admission_only'] is True
    assert result.trace['context_relevance_binding']['scorer_identity']['verified'] is False


def test_logit_score_requires_explicit_unbounded_finite_score_contract():
    s=BoundedScorer(lambda q,t:4.0,score_range=None)
    assert s.score('q','text')==4.0


def test_oracle_can_never_count_as_model_quality_even_when_all_claims_present():
    row={'evaluation_kind':'oracle_plumbing','gold_oracle_used':True,'model_executed':True,
         'model_identity':{'verified':True},'scorer_summary':{'degraded':False},
         'assessment':{'source_policy_status':'PASS'}}
    assert not valid_for_model_quality(row)
    row.update(evaluation_kind='real_model_replay',gold_oracle_used=False)
    assert valid_for_model_quality(row)
    row['model_identity']['verified']=False
    assert not valid_for_model_quality(row)
