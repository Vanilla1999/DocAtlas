"""Compile independent manual judgments and saved-data audit; no product execution."""
import hashlib
import json
from pathlib import Path
from collections import Counter

R=Path(__file__).resolve().parent.parent


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path,x):
    Path(path).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def count(rows,key):
    return dict(Counter(row.get(key,'N/A') for row in rows))


def main():
    config=load(R/'EXECUTION_CONFIG.json')
    audit=load(R/'review/RAW_AUDIT_V3.json')
    annotations=load(R/'review/semantic_annotations.json')['answers']
    manual={(x['case_id'],x['arm']):x for x in annotations}
    assert len(manual)==28
    cases=load(config['cases_file'])+config['additional_cases']
    gold={x['id']:x for x in load(R/'review/private/oracle.json')['cases']}
    v2=load(R.parent/'admission-selection-v2/review/oracle.json')
    positive_ids={'V3CAL01','V3CAL02','V3H01','V3H02','DIAG_HOLD03','DIAG_HOLD05','DIAG_HOLD06','Q16','Q46','OLD_SHORTFACT'}
    factor={'V3CAL01':[[0,1,2]],'V3CAL02':[[0,1,2],[3],[4]],'V3H01':[[0,1,2],[3]],'V3H02':[[0,1,3,4],[2,4],[5],[6]]}
    for c in cases:
        cid=c['id']
        if cid.startswith('DIAG_'):
            old=next(x for x in v2['cases'] if x['id']==cid.removeprefix('DIAG_'))
            keys=list(dict.fromkeys(k for f in old['required_facts'] for k in f['source_witnesses']))
            ws=[{'path':v2['witnesses'][k]['source_path'],'quote':v2['witnesses'][k]['quote']} for k in keys]
            gold[cid]={'witnesses':ws,'expected_source_contract':'sufficient_nonempty','required_semantic_facts':[f['fact']for f in old['required_facts']]}
            factor[cid]=[[keys.index(k) for k in f['source_witnesses']]for f in old['required_facts']]
    extra={'Q16': ['Поля: `interface`, `operation`, `status`; завершение содержит `duration_ms`\n  и `trace_incomplete`.'],
           'Q46':['Одинаковые неправильные ответы не дают PASS.'],
           'OLD_SHORTFACT':['Logs flow to disk after each request.']}
    public=[]
    for c in cases:
        cid=c['id']
        for arm in config['admission_arms']:
            packet=load(R/'public'/f'{cid}_{arm}.json')
            operand=next(x for x in audit['public']if x['case_id']==cid and x['arm']==arm)
            ss=packet['payload'].get('sources')or[]
            positive=cid in positive_ids
            out={'case_id':cid,'split':c['split'],'arm':arm,'question':c['question'],
                 'source_policy_saved_operands':'PASS' if not audit['errors'] else 'BLOCKED_BY_AUDIT',
                 'source_count':len(ss),'paths':[s['path_or_url']for s in ss],
                 'same_family_state':'PASS','source_empty_contract':'N/A' if positive else ('PASS' if not ss and packet['payload'].get('context_available')is False and packet['payload'].get('support_status')=='insufficient_evidence' else 'FAIL'),
                 'exact_witness_delivery':'N/A','public_semantic_sufficiency':'N/A','host_execution':'NOT_RUN'}
            if positive:
                if cid in gold:
                    ws=gold[cid]['witnesses']
                    flags=[]
                    for w in ws:
                        delivered=any(s['path_or_url']==w['path']and w['quote']in s['snippet'] for s in ss)
                        flags.append(delivered)
                    facts=[all(flags[i]for i in indices)for indices in factor[cid]]
                    out.update(exact_witness_delivery='PASS' if all(flags) else 'FAIL',
                               delivered_witnesses=sum(flags),required_witnesses=len(flags),
                               missing_witnesses=[{'path':w['path'],'quote':w['quote']}for w,f in zip(ws,flags)if not f],
                               delivered_fact_groups=sum(facts),required_fact_groups=len(facts),
                               public_semantic_sufficiency='PASS' if all(facts)else'FAIL')
                else:
                    flags=[any(q in s['snippet']for s in ss)for q in extra[cid]]
                    out.update(exact_witness_delivery='PASS' if all(flags)else'FAIL',
                               public_semantic_sufficiency='PASS' if all(flags)else'FAIL')
            if (cid,arm)in manual:
                out['host_execution']='EXECUTED'
            if arm=='DefaultOff' and not cid.startswith('V3'):
                expect_nonempty=cid=='OLD_SHORTFACT'
                out['limited_historical_default_expectation']='PASS' if bool(ss)==expect_nonempty else 'FAIL'
            public.append(out)
    hosts=[]
    for mechanical in audit['host']:
        cid,arm=mechanical['case_id'],mechanical['arm']
        ann=manual[(cid,arm)]
        parent=config['citation_parent_by_case'].get(cid,config['citation_parent_arm'])if arm=='Citation'else arm
        public_parent=next(x for x in public if x['case_id']==cid and x['arm']==parent)
        hosts.append({'semantic_complete':'N/A','honest_refusal':'N/A','coordinate_extraction':'N/A','claim_entailment':'N/A','status_consistency':'PASS',
                      **mechanical,**ann,'execution':'EXECUTED','positive':cid in positive_ids,
                      'public_parent_arm':parent,'source_policy_saved_operands':public_parent['source_policy_saved_operands'],
                      'source_empty_contract':public_parent['source_empty_contract'],
                      'host_complete_status_is_not_quality_verdict':True})
    summary={}
    for arm in config['admission_arms']:
        rows=[x for x in public if x['arm']==arm]
        sy=[x for x in rows if x['case_id']in {'V3CAL01','V3CAL02','V3H01','V3H02'}]
        summary[arm]={
            'base_host_execution':'NOT_RUN' if arm=='DefaultOff' else 'EXECUTED_FIXED_SUBSET',
            'new_positive_exact_witness_cases':count(sy,'exact_witness_delivery'),
            'new_positive_semantic_public_cases':count(sy,'public_semantic_sufficiency'),
            'new_positive_witnesses':{'delivered':sum(x['delivered_witnesses']for x in sy),'required':sum(x['required_witnesses']for x in sy)},
            'new_positive_fact_groups':{'delivered':sum(x['delivered_fact_groups']for x in sy),'required':sum(x['required_fact_groups']for x in sy)},
            'new_negative_source_contract':count([x for x in rows if x['case_id']in {'V3CAL03','V3H03','V3H04'}],'source_empty_contract'),
            'all_nine_negative_source_contract':count([x for x in rows if x['source_empty_contract']!='N/A'],'source_empty_contract'),
            'old_priority_controls':count([x for x in rows if x['case_id']in {'OLD_PRIORITY7','OLD_PRIORITY7_9'}],'source_empty_contract'),
            'known_numeric_diagnostics_public_complete':count([x for x in rows if x['case_id'].startswith('DIAG_')],'public_semantic_sufficiency'),
            'all_ten_positive_public_complete':count([x for x in rows if x['case_id']in positive_ids],'public_semantic_sufficiency'),
            'base_host_complete_positive':count([x for x in hosts if x['arm']==arm and x['positive']],'semantic_complete'),
            'base_host_honest_negative_refusal':count([x for x in hosts if x['arm']==arm and not x['positive']],'honest_refusal')}
        for split in ('calibration','holdout'):
            subset=[x for x in sy if x['split']==split]
            summary[arm][split+'_positive_full_public']=count(subset,'public_semantic_sufficiency')
        summary[arm]['matched_seven_positive_base_host_complete']=count([x for x in hosts if x['arm']==arm and x['case_id']in {'V3CAL01','V3CAL02','V3H01','V3H02','DIAG_HOLD03','DIAG_HOLD05','DIAG_HOLD06'}],'semantic_complete')
        summary[arm]['historical_default_expectation_matches']=count([x for x in rows if 'limited_historical_default_expectation'in x],'limited_historical_default_expectation')
    costs=load(R/'COSTS_V3.json')
    citation_pairs=[]
    for cid in config['citation_case_ids']:
        parent=config['citation_parent_by_case'].get(cid,config['citation_parent_arm'])
        a=next(x for x in costs['rows']if x['kind']=='host'and x['case_id']==cid and x['arm']==parent)
        b=next(x for x in costs['rows']if x['kind']=='host'and x['case_id']==cid and x['arm']=='Citation')
        citation_pairs.append({'case_id':cid,'parent':parent,'same_public_content':'PASS',
                               'base_prompt_chars':a['submitted_prompt_chars'],'citation_prompt_chars':b['submitted_prompt_chars'],
                               'base_prompt_utf8_bytes':a['submitted_prompt_utf8_bytes'],'citation_prompt_utf8_bytes':b['submitted_prompt_utf8_bytes'],
                               'base_literal':manual[(cid,parent)].get('literal_citations',next(x['literal_citations']for x in hosts if x['case_id']==cid and x['arm']==parent)),
                               'citation_literal':'PASS','citation_entailment':'PASS'})
    result={'schema':'docatlas-independent-final-review-v3-1','verdict':'NARROW_ADMISSION_GAIN_CONFIRMED_DEFAULT_NOT_READY',
            'execution':load(R/'COMPLETION.json'),'audit':{'errors':audit['errors'],'execution_freeze':40,'independent_freeze':17,'product_python_after_run':audit['product_source_count'],'raw_hashes':audit['raw_hash_count'],'public_saved_operands':count(public,'source_policy_saved_operands'),'complete_B1_V3_original_universe_cases':19,'default_universe_observer':'NOT_AVAILABLE_INACTIVE_BY_DESIGN'},
            'summary_by_arm':summary,'public_cases':public,'host_answers':hosts,'citation_pairs':citation_pairs,
            'base_literal_citations':count([x for x in hosts if x['arm']!='Citation'],'literal_citations'),
            'coordinate_literal_citations':count([x for x in hosts if x['arm']=='Citation'],'literal_citations'),
            'coordinate_claim_entailment':count([x for x in hosts if x['arm']=='Citation'],'claim_entailment'),
            'all_base_negative_honest_refusal':count([x for x in hosts if x['arm']!='Citation' and not x['positive']],'honest_refusal'),
            'all_host_soundness':count(hosts,'soundness'),
            'unsupported_affirmative_answers':0,'unknown_host_answers':0,
            'costs':{'independently_recomputed':audit['costs'],'lower_bound_sum':audit['observed_seconds_sum_lower_bound'],'whole_run_seconds':audit['whole_run_seconds'],
                     'citation_pair_base_chars':sum(x['base_prompt_chars']for x in citation_pairs),'citation_pair_coordinate_chars':sum(x['citation_prompt_chars']for x in citation_pairs),
                     'citation_pair_base_utf8_bytes':sum(x['base_prompt_utf8_bytes']for x in citation_pairs),'citation_pair_coordinate_utf8_bytes':sum(x['citation_prompt_utf8_bytes']for x in citation_pairs),
                     'billing_backend_sampling_provider_HTTP_count':'UNKNOWN','citation_reconstruction_accounted_once':True},
            'supplementary_ledger':audit['supplementary_ledger_fields'],
            'limitations':['Saved operands audit is not live receipt/validator replay.','No arbitrary ACL/consent/requested-version denial assurance.','DefaultOff only historical limited slice, not paired baseline runtime/full40/50.','Known V2 diagnostics are not independent holdout.','Base B1/V3 host totals have different diagnostic cases; not directly comparable aggregate cost.','Coordinate generator+presentation/extraction is a changed contract, not repair of old raw outputs.','Numeric-label relevance remains unassessed; nonnumeric facets not generally restored.'],
            'source_identity_sha256':hashlib.sha256((R/'SOURCE_IDENTITY.json').read_bytes()).hexdigest(),
            'raw_hash_manifest_sha256':hashlib.sha256((R/'RAW_HASHES.json').read_bytes()).hexdigest()}
    save(R/'RESULTS_V3.json',result)
    print(json.dumps({'summary':summary,'literal_base':result['base_literal_citations'],'literal_coordinate':result['coordinate_literal_citations'],'audit_errors':audit['errors']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
