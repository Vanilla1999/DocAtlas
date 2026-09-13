"""Paired diagnostics; never tunes retrieval parameters or opens holdout gold."""
import argparse,json,re
from pathlib import Path
from eval.evidence_quality_v2.run import load_protocol
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
p=argparse.ArgumentParser();p.add_argument('--evaluation',type=Path,required=True);a=p.parse_args()
rows=json.loads((a.evaluation/'rows.json').read_text());_,cases,_=load_protocol();cm={c['id']:c for c in cases};variants=sorted({r['variant'] for r in rows});lookup={(r['variant'],r['id']):r for r in rows}
pos=[c['id'] for c in cases if c['answerability']=='within_budget']
def paired(left,right,metric,ids=pos):
 win=[];loss=[]
 for cid in ids:
  l=metric(lookup[left,cid]);r=metric(lookup[right,cid])
  if r and not l:win.append(cid)
  if l and not r:loss.append(cid)
 return {'left':sum(metric(lookup[left,c]) for c in ids),'right':sum(metric(lookup[right,c]) for c in ids),'wins':win,'losses':loss,'n':len(ids)}
metrics={'top1':lambda r:r['coverage']['1']['complete'],'top5':lambda r:r['coverage']['5']['complete'],'all':lambda r:r['all_coverage']['complete'],'replay':lambda r:r['replay_assessment']['context_sufficiency']=='sufficient','source_only_packet':lambda r:r['packet_assessment']['context_sufficiency']=='sufficient'}
comparisons={}
for left,right in [('x_original','x_rank'),('x_rank_top5','x_rank_pruned_top5'),('plain','late'),('plain','context'),('bm25','bm25_context'),('hybrid_plain','hybrid_context')]:
 if left not in variants or right not in variants:continue
 comparisons[left+' -> '+right]={name:paired(left,right,f) for name,f in metrics.items()}
 for language in ['ru','en']:
  ids=[cid for cid in pos if bool(re.search('[А-Яа-яЁё]',cm[cid]['question']))==(language=='ru')]
  comparisons[left+' -> '+right][language+'_top5']=paired(left,right,metrics['top5'],ids)
limits={v:{'max_replay_tokens':max(docs_context_budget_tokens(r['replay']) for r in rows if r['variant']==v),'max_packet_tokens':max(docs_context_budget_tokens(r['source_only_packet']) for r in rows if r['variant']==v)} for v in variants}
five={cid:{v:{'top5':lookup[v,cid]['coverage']['5']['complete'],'all':lookup[v,cid]['all_coverage']['complete'],'replay':lookup[v,cid]['replay_assessment']['context_sufficiency'],'packet':lookup[v,cid]['packet_assessment']['context_sufficiency']} for v in variants} for cid in ['fastapi-01','pydantic-03','httpx-06','mkdocs-05','uv-05']}
controls={}
for v in variants:
 controls[v]={}
 for kind in ['partial','ambiguous','unanswerable','over_budget']:
  rs=[r for r in rows if r['variant']==v and r['answerability']==kind]
  controls[v][kind]={'cases':len(rs),'replay_sufficient':sum(r['replay_assessment']['context_sufficiency']=='sufficient' for r in rs),'recognized_required_claims':sum(r['replay_assessment']['required_supported'] for r in rs),'with_sources':sum(bool(r['replay'].get('sources')) for r in rs),'claims_answer_supported':sum(bool(r['replay'].get('answer_supported')) for r in rs)}
out={'comparisons':comparisons,'budgets':limits,'five_cases':five,'controls':controls}
(a.evaluation/'paired.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(comparisons,indent=2))
