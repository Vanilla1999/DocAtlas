"""Shared source-bound sufficiency, citation budget and ordinary-projector diagnostics."""
import argparse,json,gzip,hashlib,sys,math,re,collections
from pathlib import Path
from copy import deepcopy
from eval.evidence_quality_v2.run import load_protocol,documents_for,registry_for,audit_payload
from eval.evidence_quality_v2.semantic import assess_context
from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application.model_visible_projection import _docs_source,_snapshot_entry,docs_context_budget_tokens
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application._project_docs_service_part03 import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup
from docmancer.core.models import RetrievedChunk
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'semantic-selection'))
import importlib.util
spec=importlib.util.spec_from_file_location('h1_coverage',Path(__file__).resolve().parent.parent/'semantic-selection/evaluate.py');h1=importlib.util.module_from_spec(spec);spec.loader.exec_module(h1);complete=h1.complete

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def item(c):return {'key':c['key'],'raw':{'text':c['text'],'source':c['path'],'metadata':{'line_span':[c['line_start'],c['line_end']]}}}
def bm25(question,texts):
 tokens=lambda s:re.findall(r'\w+',s.casefold());counts=[collections.Counter(tokens(s)) for s in texts];lens=[sum(c.values()) for c in counts];avg=sum(lens)/max(1,len(lens));qs=set(tokens(question));scores=[]
 for c,l in zip(counts,lens):
  score=0.
  for q in qs:
   df=sum(q in other for other in counts);tf=c[q]
   if tf:score+=math.log(1+(len(counts)-df+.5)/(df+.5))*tf*2.2/(tf+1.2*(.25+.75*l/max(1,avg)))
  scores.append(score)
 return sorted(range(len(texts)),key=lambda j:-scores[j])
def rrf(first,second):
 scores=collections.defaultdict(float)
 for order in [first,second]:
  for i,k in enumerate(order):scores[k]+=1/(60+i+1)
 return sorted(scores,key=lambda k:-scores[k])

def hybrid_factorial(question, pool, vector_orders, contexts):
 """Change only sparse contextualization and dense chunk encoding; cite originals."""
 bykey = {c['key']: c for c in pool}
 if len(bykey) != len(pool) or not pool:
  raise ValueError('Expected a nonempty unique source pool')
 for name in ('plain', 'late'):
  order = vector_orders[name]
  if len(order) != len(pool) or set(order) != set(bykey):
   raise ValueError('Both dense orders must cover the same complete source pool')
 if not set(bykey) <= set(contexts):
  raise ValueError('Missing context description')
 lanes = {}
 for contextual in (False, True):
  texts = [(contexts[c['key']] + '\n' if contextual else '') + c['text'] for c in pool]
  sparse = [pool[j]['key'] for j in bm25(question, texts)]
  for dense in ('plain', 'late'):
   name = 'hybrid_' + ('context_bm25_' if contextual else '') + dense
   lanes[name] = [bykey[k] for k in rrf(sparse, vector_orders[dense])]
 return lanes

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--xprovence',type=Path);p.add_argument('--embeddings',type=Path);p.add_argument('--context-embeddings',type=Path);p.add_argument('--contexts',type=Path);p.add_argument('--hybrid-factorial-only',action='store_true');a=p.parse_args()
 if a.hybrid_factorial_only and (not a.embeddings or not a.contexts or a.xprovence or a.context_embeddings):p.error('factorial requires plain/late embeddings and contexts only')
 a.output.mkdir(exist_ok=False)
 _,cases,manifest=load_protocol();chunks=json.loads((a.input/'chunks.json').read_text());chunkmap={c['key']:c for c in chunks};questions=json.loads((a.input/'questions.json').read_text());docs=json.loads((a.input/'documents.json').read_text());docmap={d['key']:d for d in docs}
 for c in chunks:
  text=docmap[c['document']]['text'];c['line_start']=text[:c['char_start']].count('\n')+1;c['line_end']=text[:c['char_end']-1].count('\n')+1
 qmap={q['key']:q for q in questions};baselines=json.loads(Path('/tmp/docatlas-h1-baseline/baselines.json').read_text());basemap={r['id']:r for r in baselines};templates={};cache={};sections={}
 for c in cases:
  t=json.loads(gzip.decompress(Path('/tmp/docatlas-h1-baseline',c['id']+'.trace.json.gz').read_bytes()))['stages']['projector_inputs']
  if t:
   templates[c['id']]=t[0]
   for s in t[0]['context_pack']:cache.setdefault((c['project_group'],s['path']),s)
 sections=json.loads((a.input/'sections.json').read_text())
 def raw_for(case,c):
  lib=case['project_group'];raw=deepcopy(cache[(lib,c['path'])]);body=c['text'];document=next(d['text'] for d in docs if d['library']==lib and d['path']==c['path']);assert document[c['char_start']:c['char_end']]==body;raw.update(content=body,display_text=body,char_start=c['char_start'],char_end=c['char_end'],line_start=c['line_start'],line_end=c['line_end'],retrieval_query_matches={},retrieval_query_ids=[],project_ranking={})
  for k in ['snippet','code','stable_chunk_id','parent_logical_id','display_content_hash']:raw.pop(k,None)
  raw['document_data']={**raw.get('document_data',{}),'content':body}
  raw['surrounding_context']=body;raw['token_estimate']=max(1,len(body.encode('utf-8'))//4);raw['why_selected']='Research candidate from the verified source file'
  sec=next((s for s in sections[lib] if s['source_path']==c['path'] and s['line_start']<=c['line_start']<=s['line_end']),None)
  if sec:
   raw.update(title=sec['title'],heading_path=sec['anchor']);raw['section']={**raw.get('section',{}),'title':sec['title'],'heading_path':sec['anchor']};raw['source']={**raw.get('source',{}),'title':sec['title']}
  chunk=RetrievedChunk(source=c['path'],text=body,chunk_index=0,score=0.,metadata=deepcopy(raw))
  for lookup in templates[case['id']]['documentation_query_plan']['queries']:
   look=DocumentationLookup(**lookup);chunk=_tag_retrieval_query([chunk],look.query_id,look.text,look,expected_project_identity=raw['project_identity'])[0]
  raw['retrieval_query_matches']=chunk.metadata['retrieval_query_matches'];raw['retrieval_query_ids']=chunk.metadata['retrieval_query_ids'];return raw
 def pack(case,selected):
  raw=[raw_for(case,c) for c in selected];inp=deepcopy(templates[case['id']]);inp['context_pack']=raw
  payload,snapshot=projection.project_docs_context(retrieval=inp);root=Path('/tmp/docatlas-continued-systemic/acceptance/full80_current/corpus')/case['project_group'];errors=audit_payload(payload,snapshot,root)
  for s in payload.get('sources',[]):
   if not any(s['path_or_url']==c['path'] and s['snippet'] in c['text'] for c in selected):errors.append('replay snippet escaped selected literal candidate spans')
  sources=[];snap={};budget_skips=0
  for source in raw:
   if len(sources)==3:break
   if not source['content'] or len(source['content'])>3000:continue
   s=_docs_source(source,display_snippet=source['content']);s.update(project_identity=source['project_identity'],authority=source['authority'],scope=source['doc_scope'],line_start=source['line_start'],line_end=source['line_end'])
   if any(old['evidence_id']==s['evidence_id'] for old in sources):continue
   trial=_payload([*sources,s],query_plan={'queries':[],'broad_context_only':True})
   if docs_context_budget_tokens(trial)>800:budget_skips+=1;continue
   sources.append(s);snap[s['evidence_id']]=_snapshot_entry(source,s)
  advisory=_payload(sources,query_plan={'queries':[],'broad_context_only':True})
  if not sources:
   empty=deepcopy(inp);empty['context_pack']=[];advisory,snap=projection.project_docs_context(retrieval=empty)
  packet_errors=audit_payload(advisory,snap,root)
  return {'replay':payload,'replay_snapshot':snapshot,'packet_snapshot':snap,'replay_assessment':assess_context(case,payload,registry_for(case['project_group'],manifest)),'replay_errors':errors,'source_only_packet':advisory,'packet_assessment':assess_context(case,advisory,registry_for(case['project_group'],manifest)),'packet_errors':packet_errors,'packet_budget_skips':budget_skips}
 lanes={q['key']:{} for q in questions}
 if a.embeddings:
  for r in json.loads(a.embeddings.read_text()):
   for name,values in r['lanes'].items():lanes[r['key']][name]=[chunkmap[v['key']] for v in values]
 if a.context_embeddings:
  for r in json.loads(a.context_embeddings.read_text()):
   for name,values in r['lanes'].items():lanes[r['key']][name]=[chunkmap[v['key']] for v in values]
 if a.hybrid_factorial_only:
  contexts={r['key']:r['context'] for r in json.loads(a.contexts.read_text())}
  for q in questions:
   pool=[c for c in chunks if c['library']==q['library']]
   orders={name:[c['key'] for c in lanes[q['key']][name]] for name in ('plain','late')}
   lanes[q['key']]=hybrid_factorial(q['question'],pool,orders,contexts)
 elif a.embeddings:
  contexts={r['key']:r['context'] for r in json.loads(a.contexts.read_text())} if a.contexts else None
  for q in questions:
   pool=[c for c in chunks if c['library']==q['library']];bykey={c['key']:c for c in pool};plain=bm25(q['question'],[c['text'] for c in pool]);lanes[q['key']]['bm25']=[pool[j] for j in plain]
   lanes[q['key']]['hybrid_plain']=[bykey[k] for k in rrf([pool[j]['key'] for j in plain],[c['key'] for c in lanes[q['key']]['plain']])]
   if contexts:
    ctx=bm25(q['question'],[contexts[c['key']]+'\n'+c['text'] for c in pool]);lanes[q['key']]['bm25_context']=[pool[j] for j in ctx]
    lanes[q['key']]['hybrid_context']=[bykey[k] for k in rrf([pool[j]['key'] for j in ctx],[c['key'] for c in lanes[q['key']]['context']])]
 xcoverage={}
 if a.xprovence:
  for xr in json.loads(a.xprovence.read_text()):
   b=next(b for b in baselines if b['question_key']==xr['key']);original=[];pruned=[];xmap={x['key']:x for x in xr['candidates']}
   for source in b['pool']:
    rr=source['raw'];meta=rr['metadata'];lib=qmap[xr['key']]['library'];doc=next(d for d in docs if d['library']==lib and d['path']==meta['project_doc_path']);start=doc['text'].find(rr['text'].strip(),sum(map(len,doc['text'].splitlines(keepends=True)[:meta['line_span'][0]-1])),sum(map(len,doc['text'].splitlines(keepends=True)[:meta['line_span'][1]])));assert start>=0
    text=rr['text'];lefttrim=len(text)-len(text.lstrip());absolute=start-lefttrim
    original.append({'key':source['key'],'library':lib,'path':doc['path'],'text':text.strip(),'char_start':start,'char_end':start+len(text.strip()),'line_start':doc['text'][:start].count('\n')+1,'line_end':doc['text'][:start+len(text.strip())-1].count('\n')+1})
    spans=xmap[source['key']]['spans'];merged=[]
    for span in spans:
     if merged and not text[merged[-1][1]:span['start']].strip():merged[-1]=(merged[-1][0],span['end'])
     else:merged.append((span['start'],span['end']))
    for s,e in merged:
     st=absolute+s;en=absolute+e;assert doc['text'][st:en]==text[s:e]
     pruned.append({'key':source['key']+':'+str(s),'parent_key':source['key'],'library':lib,'path':doc['path'],'text':text[s:e],'char_start':st,'char_end':en,'line_start':doc['text'][:st].count('\n')+1,'line_end':doc['text'][:en-1].count('\n')+1})
   rank=sorted(original,key=lambda c:-xmap[c['key']]['score']);top={c['key'] for c in rank[:5]};prunedtop=[c for p in rank[:5] for c in pruned if c['parent_key']==p['key']]
   lanes[xr['key']]['x_original']=original;lanes[xr['key']]['x_rank']=rank;lanes[xr['key']]['x_rank_top5']=rank[:5];lanes[xr['key']]['x_pruned']=pruned;lanes[xr['key']]['x_rank_pruned_top5']=prunedtop
   xcoverage[xr['key']]={'input_chars':sum(c['input_chars'] for c in xr['candidates']),'retained_chars':sum(c['retained_chars'] for c in xr['candidates']),'retained_spans':len(pruned)}
 rows=[]
 for case in cases:
  qk=sha(case['project_group']+'\n'+case['question']);documents=documents_for(case['project_group'],manifest)
  for name,selected in lanes[qk].items():
   # Pruned fragments can split one candidate; report entire retained set separately.
   ks={str(k):complete(case,[item(c) for c in selected[:k]],documents) for k in [1,3,5,10,20]}
   full=complete(case,[item(c) for c in selected],documents)
   # Bounded source admission sees up to20 fragments/candidates, never gold spans.
   out=pack(case,selected[:20]);rows.append({'id':case['id'],'variant':name,'answerability':case['answerability'],'coverage':ks,'all_coverage':full,'selected_keys':[c['key'] for c in selected[:20]],**out})
  save(a.output/'rows.json',rows);print(case['id'],'evaluated',len(lanes[qk]),flush=True)
 summary={}
 for name in sorted({r['variant'] for r in rows}):
  rs=[r for r in rows if r['variant']==name];pos=[r for r in rs if r['answerability']=='within_budget'];ok=lambda r:r['replay_assessment']['context_sufficiency']=='sufficient';baseok=lambda r:basemap[r['id']]['assessment']['context_sufficiency']=='sufficient'
  summary[name]={'top_k':{str(k):sum(r['coverage'][str(k)]['complete'] for r in pos) for k in [1,3,5,10,20]},'all':sum(r['all_coverage']['complete'] for r in pos),'replay_sufficient':sum(ok(r) for r in pos),'replay_wins':[r['id'] for r in pos if ok(r) and not baseok(r)],'replay_losses':[r['id'] for r in pos if baseok(r) and not ok(r)],'source_only_packet_sufficient':sum(r['packet_assessment']['context_sufficiency']=='sufficient' for r in pos),'audit_errors':sum(len(r['replay_errors'])+len(r['packet_errors']) for r in rs),'controls_replay_sufficient':[r['id'] for r in rs if r['answerability']!='within_budget' and ok(r)]}
 save(a.output/'summary.json',summary);save(a.output/'x_compression.json',xcoverage);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
