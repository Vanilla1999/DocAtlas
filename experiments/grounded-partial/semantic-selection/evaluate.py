"""Post-hoc assessment of frozen scores; annotation access is confined here."""
import argparse, hashlib, json, math, statistics
from pathlib import Path
from eval.evidence_quality_v2.run import load_protocol,documents_for
from eval.evidence_quality_v2.trace import source_span

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def complete(case,items,documents,visible=None):
    coverage={path:set() for path in documents};unmapped=[]
    for item in items:
        s=source_span(item['raw']);path=s['path_or_url'];body=documents[path];lines=body.splitlines(keepends=True)
        start=sum(map(len,lines[:s['line_start']-1]));end=sum(map(len,lines[:s['line_end']]))
        text=(visible[item['key']]['seen_text'] if visible else s['snippet']).strip()
        if not text:continue
        at=body.find(text,start,end)
        if at<0:unmapped.append(item['key']);continue
        coverage[path].update(range(at,at+len(text)))
    def part(p):
        path=p['path'];body=documents[path];lines=body.splitlines(keepends=True)
        start=sum(map(len,lines[:p.get('line_start',1)-1]));end=sum(map(len,lines[:p.get('line_end',len(lines))]))
        text=p['text'].strip();at=body.find(text,start,end)
        assert at>=0,(case['id'],p)
        needed={at+i for i,c in enumerate(text) if not c.isspace()}
        return bool(needed) and needed<=coverage[path]
    claims=[];part_counts=[]
    for claim in case['required_claims']:
        sets=[[part(p) for p in w['parts']] for w in claim.get('witness_sets',[])]
        claims.append(any(all(s) and s for s in sets));part_counts.append(sets)
    return {'complete':bool(claims) and all(claims),'claims':claims,'witness_parts':part_counts,'unmapped':unmapped}

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--scores',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    _,cases,manifest=load_protocol();baselines={r['id']:r for r in json.loads((a.baseline/'baselines.json').read_text())}
    scores={r['key']:r for r in json.loads((a.scores/'scores.json').read_text())};env=json.loads((a.scores/'environment.json').read_text())
    assert env['input_sha256']==hashlib.sha256((a.baseline/'candidates.jsonl').read_bytes()).hexdigest()
    rows=[]
    for case in cases:
        b=baselines[case['id']];sc={s['key']:s for s in scores[b['question_key']]['candidates']};pool=b['pool'];assert set(sc)=={c['key'] for c in pool}
        documents=documents_for(case['project_group'],manifest);ranked=sorted(pool,key=lambda c:-sc[c['key']]['score'])
        row={'id':case['id'],'answerability':case['answerability'],'language':'ru' if any('А'<=c<='я' for c in case['question']) else 'en','pool':complete(case,pool,documents),'pool_before_64':complete(case,b['pool_before_64'],documents),'scorer_visible_pool':complete(case,pool,documents,sc),'A':{},'B':{},'orders':{'A':[c['key'] for c in pool],'B':[c['key'] for c in ranked]}}
        for k in [1,3,5,10]:
            row['A'][k]=complete(case,pool[:k],documents)
            row['B'][k]=complete(case,ranked[:k],documents)
        rows.append(row)
    positives=[r for r in rows if r['answerability']=='within_budget'];summary={'cases':len(rows),'primary_k':5,'native_baseline':33,'ks':{},'pool_complete':sum(r['pool']['complete'] for r in positives),'scorer_visible_pool_complete':sum(r['scorer_visible_pool']['complete'] for r in positives)}
    for k in [1,3,5,10]:
        wins=[r['id'] for r in positives if r['B'][k]['complete'] and not r['A'][k]['complete']];losses=[r['id'] for r in positives if r['A'][k]['complete'] and not r['B'][k]['complete']];n=len(wins)+len(losses)
        summary['ks'][k]={'A':sum(r['A'][k]['complete'] for r in positives),'B':sum(r['B'][k]['complete'] for r in positives),'wins':wins,'losses':losses,'mcnemar_exact_p':min(1,2*sum(math.comb(n,i) for i in range(min(len(wins),len(losses))+1))/(2**n)) if n else 1}
    prime=summary['ks'][5];summary['H1']='supported_for_next_experiment' if len(prime['wins'])>=3 and not prime['losses'] else 'mixed_or_weak' if len(prime['wins'])>len(prime['losses']) else 'not_supported'
    timings=sorted(r['seconds'] for r in scores.values());warm=sorted(r['seconds'] for r in list(scores.values())[1:])
    summary['timings']={'p50_warm_query_seconds':statistics.median(warm),'p95_warm_query_seconds':warm[math.ceil(.95*len(warm))-1],'cold_model_load_seconds':env['load_seconds'],'first_query_seconds':env['first_query_seconds'],'peak_rss_kib':env['peak_rss_kib'],'pairs':env['pairs'],'pair_input_tokens':env['input_tokens']}
    summary['raw_truncation_flags']=sum(c['truncated'] for r in scores.values() for c in r['candidates'])
    summary['truncated_candidates']=sum(bool(c['raw']['text'][len(next(s['seen_text'] for s in scores[b['question_key']]['candidates'] if s['key']==c['key'])):].strip()) for b in baselines.values() for c in b['pool'])
    summary['pool_missing']=[r['id'] for r in positives if not r['pool']['complete']]
    summary['unmapped_spans']=sum(len(r['pool']['unmapped']) for r in rows)
    save(a.output/'rows.json',rows);save(a.output/'summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
