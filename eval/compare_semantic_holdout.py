"""Read actual executed holdout arms; never tune a selector or suppress losses."""
import json
import os
from pathlib import Path


def main():
    root=Path(os.environ['RUNNER_TEMP'])
    values={}
    for policy in ('fixed','facet-guarded-v1','default','auto'):
        folder=root/'unseen-arms'/f'facet-live-unseen-{policy}-{os.environ["GITHUB_RUN_ID"]}'/'run'
        values[policy]={'summary':json.loads((folder/'SUMMARY.json').read_text()),
                        'rows':json.loads((folder/'ASSESSMENTS.json').read_text()),
                        'freeze':json.loads((folder/'FREEZE.json').read_text())}
    a,b=values['fixed'],values['facet-guarded-v1']
    # Both effective defaults must match the explicit facet selector in the
    # same source-pool execution. Citation nonces differ between executions;
    # compare mandatory facts, section counts, and original input hashes.
    for label in ('default', 'auto'):
        implicit=values[label]
        assert implicit['freeze']['inputs']==b['freeze']['inputs']
        assert implicit['summary']['head']==b['summary']['head']==os.environ['GITHUB_SHA']
        assert implicit['summary']['cases']==b['summary']['cases']==16
        rows={r['case_id']:r for r in implicit['rows']}
        explicit={r['case_id']:r for r in b['rows']}
        assert rows.keys()==explicit.keys()
        for cid in rows:
            assert rows[cid]['question']==explicit[cid]['question']
            assert rows[cid]['selected_groups']==explicit[cid]['selected_groups']
            assert rows[cid]['coverage']['facts']==explicit[cid]['coverage']['facts']
            assert rows[cid]['integrity']==explicit[cid]['integrity']
    assert a['freeze']['inputs']==b['freeze']['inputs']
    assert a['summary']['head']==b['summary']['head']==os.environ['GITHUB_SHA']
    old={r['case_id']:r for r in a['rows']}
    new={r['case_id']:r for r in b['rows']}
    assert old.keys()==new.keys() and len(new)==16
    losses=[];fact_losses=[]
    for cid in old:
        assert old[cid]['question']==new[cid]['question'] and old[cid]['search_question']==new[cid]['search_question']
        if old[cid]['answerability']=='unanswerable':continue
        if old[cid]['passed'] and not new[cid]['passed']:losses.append(cid)
        old_f={r['id']:r['covered'] for r in old[cid]['coverage']['facts']}
        new_f={r['id']:r['covered'] for r in new[cid]['coverage']['facts']}
        assert old_f.keys()==new_f.keys()
        fact_losses += [f for f in old_f if old_f[f] and not new_f[f]]
    complete=b['summary']['documented_pass']==b['summary']['documented_total']
    cheaper=b['summary']['tokens_sum']<a['summary']['tokens_sum']
    integrity=all(x['summary']['integrity_pass']==16 for x in values.values())
    result={'head':os.environ['GITHUB_SHA'],'summaries':{k:v['summary'] for k,v in values.items()},
            'new_case_losses':losses,'new_fact_losses':fact_losses,'all_documented_covered':complete,
            'less_visible_context':cheaper,'integrity':integrity,
            'retrieval_gate_passed':complete and cheaper and integrity and not losses and not fact_losses,
            'default_matches_explicit_facets':True,'auto_with_preprovisioned_model_matches_facets':True,
            'provider_usage':None,'answer_model_calls':0,'default_rollout':False,
            'boundary':'New frozen source-authored synthetic holdout, not externally authored or a production sample. No tuning after execution.'}
    out=root/'unseen-paired';out.mkdir(parents=True,exist_ok=True)
    (out/'HOLDOUT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    assert result['retrieval_gate_passed'], 'unseen evidence/token gate failed; retain data and do not tune on this holdout'


if __name__=='__main__':main()
