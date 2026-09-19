#!/usr/bin/env python3
"""Throwaway ABC comparison, not a production implementation or a holdout.
A/B share normally retrieved pre-window candidates. C0/C1 separately compare
existing search text with a real parent paragraph, identical FTS and caps.
No extra search calls, generated evidence, learned gold, or budget widening.
"""
from __future__ import annotations
import copy, hashlib, json, os, re, sqlite3, subprocess, sys, time
from pathlib import Path
from unittest.mock import patch
import numpy as np
SHA='95e61265656283d609bc1328c46c52b2bf1a069e'
EXPECTED='git:github.com/Vanilla1999/DocAtlas'
ROOT=Path(os.environ['CORPUS']).resolve()
OUT=Path(os.environ['ABC_OUT']); OUT.mkdir(parents=True,exist_ok=True)
INPUT=Path(os.environ['ABC_INPUT'])
def dump(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
def digest(text): return hashlib.sha256(text.encode()).hexdigest()
def git(*args): return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
assert git('rev-parse','HEAD')==SHA and not git('status','--porcelain','--untracked-files=all')
data=json.loads(INPUT.read_text()); assert data['runtime_sha']==SHA and len(data['cases'])==30
from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker,LibraryDocsService
from eval.project_context_quality.capture_public_context import capture_public_call
from docmancer.docs.application import _project_docs_service_part03 as pds
from docmancer.docs.domain.evidence_qualification import evidence_policy_rejection_reason,_visible_term_present
from docmancer.docs.domain.project_doc_ranking import source_lane_allowed
from docmancer.docs.domain.query_terms import documentation_query_terms,documentation_exact_terms
from docmancer.docs.domain.context_blocks import source_block_alternatives
from docmancer.docs.domain.context_windows import _focused_line_range
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.context_selection import context_selection_decision
from docmancer.docs.application.model_visible_projection import (_docs_source,_snapshot_entry,project_insufficient,docs_context_budget_tokens,validate_model_visible_projection)
os.environ['DOCATLAS_OFFLINE']='1'; os.environ['DOCATLAS_AUTO_VECTORS']='0'; os.environ['DOCATLAS_HOME']=str(OUT/'home')
cfg=DocmancerConfig(); cfg.index.db_path=str(OUT/'index.sqlite'); cfg.index.extracted_dir=str(OUT/'extracted')
svc=LibraryDocsService(config=cfg,config_source='explicit',registry=LibraryRegistry(cfg.index.db_path),agent=DocmancerAgent(config=cfg),job_tracker=DocsJobTracker())
assert svc.sync_project_docs(str(ROOT),with_vectors=False).status=='success'
files={}
binding_rejections=[]
def bind(item):
    item=copy.deepcopy(item); path=str(item.get('path') or item.get('project_doc_path') or item.get('source_path') or '')
    if Path(path).is_absolute():
        try: path=str(Path(path).relative_to(ROOT))
        except ValueError: return None
    try:
        target=(ROOT/path).resolve(strict=True)
        if ROOT not in target.parents: return None
        if path not in files: files[path]=target.read_text(encoding='utf-8')
    except (OSError,UnicodeError): return None
    raw=str(item.get('content') or item.get('display_text') or '')
    if not raw.strip(): return None
    original=files[path]; start=item.get('char_start')
    if not isinstance(start,int) or original[start:start+len(raw)]!=raw:
        start=original.find(raw)
        if start<0 or original.find(raw,start+1)>=0:
            binding_rejections.append({'path':path,'reason':'no_unique_source_span'}); return None
    ls,le=_focused_line_range(original,start,start+len(raw),1)
    item.update(path=path,content=raw,char_start=start,char_end=start+len(raw),line_start=ls,line_end=le,source_file_sha256=digest(original))
    return item

def from_chunk(c):
    md=copy.deepcopy(c.metadata or {})
    md.update(path=md.get('project_doc_path') or md.get('source_path') or str(c.source),content=c.text,score=float(c.score),char_start=(md.get('char_span') or [None])[0])
    return bind(md)

native=[]
for case in data['cases']:
    pools=[]; original=pds._retrieval_stage_diagnostics
    def observe(plan,candidates):
        pools.extend(x for c in candidates if (x:=from_chunk(c)) is not None)
        return original(plan,candidates)
    req={'project_path':str(ROOT),'scope':'project','question':case['question'],'lookup_queries':case['lookup_queries']}
    t=time.perf_counter()
    with patch.object(pds,'_retrieval_stage_diagnostics',observe): cap=capture_public_call(svc,req)
    unique={}
    for x in pools: unique.setdefault((x['path'],x['char_start'],x['char_end']),x)
    native.append({'id':case['id'],'question':case['question'],'lookup_queries':case['lookup_queries'],'pool':list(unique.values()),'capture':cap,'elapsed':time.perf_counter()-t})
    print('captured',case['id'],len(unique),flush=True)
dump('native.json',native)
conn=sqlite3.connect(cfg.index.db_path); conn.row_factory=sqlite3.Row
gen=conn.execute('SELECT active_generation_id FROM index_state WHERE singleton=1').fetchone()[0]
parents={r['logical_id']:dict(r) for r in conn.execute('SELECT * FROM retrieval_parents WHERE generation_id=?',(gen,))}
allrows=[]
for row in conn.execute('SELECT * FROM retrieval_children WHERE generation_id=?',(gen,)):
    r=dict(row); md=json.loads(r.get('metadata_json') or '{}')
    for key in ('project_identity','doc_scope','source_class','authority','lifecycle_status','index_freshness','module_id'):
        if r.get(key) is not None: md[key]=r[key]
    md.update(path=md.get('project_doc_path') or r.get('source_path') or r['source'],content=r['display_text'],char_start=r['char_start'],stable_chunk_id=r['stable_chunk_id'],heading_path=md.get('heading_path') or r['title'],retrieval_text=r['retrieval_text'],context_prefix=r.get('context_prefix',''),parent_logical_id=r['parent_logical_id'])
    x=bind(md)
    if x is None: continue
    parent=parents.get(r['parent_logical_id'],{})
    prose=[p.strip() for p in re.split(r'\n\s*\n',parent.get('display_text','')) if p.strip() and not p.lstrip().startswith(('#','```','~~~'))]
    x['structural_prefix']='\n'.join([str(x.get('heading_path','')),prose[0] if prose else ''])[:600]
    allrows.append(x)
dump('index_rows.json',allrows); dump('source_files.json',files)

def allowed(x,q,plan):
    if x.get('doc_scope') not in (None,'','project'): return False
    probe=next((v for v in plan.get('queries',[]) if v.get('query_id')=='query-original'),{})
    reason=evidence_policy_rejection_reason(probe,visible_text=x['content'],candidate=x,catalog_role=str(x.get('catalog_role') or x.get('project_doc_reason') or ''),expected_project_identity=EXPECTED,lifecycle_intent='history' if 'history' in q.casefold() or 'historical' in q.casefold() else 'current')
    if reason or not source_lane_allowed(x['path'],q): return False
    exact=[t.normalized_value for t in documentation_exact_terms(q)]
    return all(_visible_term_present(t,x['content'].casefold(),exact=True) for t in exact)

def fts_scores(rows,queries,field):
    if not rows: return []
    db=sqlite3.connect(':memory:'); db.execute("CREATE VIRTUAL TABLE f USING fts5(body,tokenize='unicode61')")
    db.executemany('INSERT INTO f(rowid,body) VALUES (?,?)',[(i+1,field(x)) for i,x in enumerate(rows)])
    values=np.zeros(len(rows),dtype=float)
    for q in queries:
        terms=tuple(dict.fromkeys(documentation_query_terms(q))); match=' OR '.join('"'+s.replace('"','""')+'"' for s in terms)
        if not match: continue
        for rowid,score in db.execute('SELECT rowid,bm25(f) FROM f WHERE f MATCH ?',(match,)): values[rowid-1]=max(values[rowid-1],-score)
    db.close(); return values.tolist()

def atoms(rows):
    units=[]
    for x in rows:
        raw=x['content']; seen=set()
        for start,end in ((0,len(raw)),*source_block_alternatives(raw).spans):
            text=raw[start:end]
            if not text.strip() or (start,end) in seen: continue
            seen.add((start,end)); y=dict(x); y.update(snippet=text,unit_start=x['char_start']+start,unit_end=x['char_start']+end); units.append(y)
    return units

def make_packet(units,scores,q,lookups):
    chosen=[]; snapshots={}; selected=[]
    plan={'original_question':q,'queries':[{'query_id':'query-original','text':q,'origin':'original'},*[{'query_id':f'query-lookup-{i+1}','text':v,'origin':'host_lookup'} for i,v in enumerate(lookups)]],'broad_context_only':True,'component_scope_complete':False}
    qids=tuple(x['query_id'] for x in plan['queries']); order=sorted(range(len(units)),key=lambda i:(-scores[i],units[i]['path'],units[i]['unit_start'],units[i]['unit_end'])); chunk_ids=set()
    for i in order:
        x=units[i]; sid=(x['path'],x['char_start'],x['char_end'])
        if len(chunk_ids)>=20 and sid not in chunk_ids: continue
        chunk_ids.add(sid)
        if any(x['path']==y['path'] and not (x['unit_end']<=y['unit_start'] or x['unit_start']>=y['unit_end']) for y in selected): continue
        eid='ev-'+digest(x['path']+':'+str(x['unit_start'])+':'+str(x['unit_end'])+':'+x['source_file_sha256'])[:16]
        s=_docs_source(x,evidence_id=eid,display_snippet=x['snippet'])
        if s is None: continue
        raw=files[x['path']]; assert raw[x['unit_start']:x['unit_end']]==x['snippet']
        ls,le=_focused_line_range(raw,x['unit_start'],x['unit_end'],1)
        s.update(project_identity=x['project_identity'],line_start=ls,line_end=le,authority=str(x.get('authority') or 'supporting'),scope='project')
        tentative=[*chosen,s]; p=_payload(tentative,decision=context_selection_decision(tentative,qids),query_plan=plan)
        if docs_context_budget_tokens(p)>800: continue
        chosen=tentative; selected.append(x); snapshots[eid]=_snapshot_entry(x,s)
        if len(chosen)==3: break
    if not chosen: p=project_insufficient(kind='docs_context',missing=['No safe source block fits the bounded response.'],recommended_next_action=None,max_tokens=300)
    else: p=_payload(chosen,decision=context_selection_decision(chosen,qids),query_plan=plan)
    errors=validate_model_visible_projection(p,snapshot=snapshots,max_tokens=800)
    assert docs_context_budget_tokens(p)<=800 and p['kind']=='docs_context' and not p.get('answer_supported') and not p.get('edit_ready')
    return {'payload':p,'validation_errors':errors,'budget_tokens':docs_context_budget_tokens(p),'selected_spans':[{'path':x['path'],'start':x['unit_start'],'end':x['unit_end'],'source_sha256':x['source_file_sha256']} for x in selected]}

model_meta={}; model_error=None
try:
    from huggingface_hub import HfApi,hf_hub_download
    from transformers import AutoTokenizer
    import onnxruntime as ort
    name='cross-encoder/ms-marco-MiniLM-L6-v2'; rev=HfApi().model_info(name).sha
    model_path=hf_hub_download(name,'onnx/model.onnx',revision=rev); tokenizer=AutoTokenizer.from_pretrained(name,revision=rev)
    options=ort.SessionOptions(); options.intra_op_num_threads=2
    session=ort.InferenceSession(model_path,sess_options=options,providers=['CPUExecutionProvider'])
    model_meta={'name':name,'revision':rev,'onnx_sha256':hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),'max_length':512,'batch_size':16,'threads':2,'bytes':Path(model_path).stat().st_size}
except Exception as e: model_error=repr(e)
cache={}
def semantic(q,units):
    if model_error: return None
    texts=[str(x.get('heading_path') or '')+'\n'+x['snippet'] for x in units]; missing=list(dict.fromkeys(t for t in texts if (q,t) not in cache))
    for start in range(0,len(missing),16):
        batch=missing[start:start+16]; inputs=tokenizer([q]*len(batch),batch,padding=True,truncation=True,max_length=512,return_tensors='np'); inputs={x.name:inputs[x.name] for x in session.get_inputs()}
        values=session.run(None,inputs)[0].reshape(-1)
        for t,v in zip(batch,values): cache[(q,t)]=float(v)
    return [cache[(q,t)] for t in texts]
results=[]
for case in native:
    q=case['question']; lookups=case['lookup_queries']; queries=[q,*lookups]; attempts=case['capture'].get('projection_attempts') or []; before=attempts[0]['before_projection'] if attempts else {}; plan=before.get('documentation_query_plan') or {}; pool=[x for x in case['pool'] if allowed(x,q,plan)]
    row={'id':case['id'],'question':q,'lookup_queries':lookups,'pool_count':len(case['pool']),'safe_pool_count':len(pool),'baseline':case['capture']['public_payload'],'arms':{}}
    for label,candidates,mode in [('A',pool,'lexical'),('B',pool,'semantic')]:
        units=atoms(candidates); t=time.perf_counter(); values=semantic(q,units) if mode=='semantic' else fts_scores(units,queries,lambda x:str(x.get('heading_path') or '')+'\n'+x['snippet'])
        if values is None: row['arms'][label]={'error':model_error}; continue
        arm=make_packet(units,values,q,lookups); arm.update(elapsed=time.perf_counter()-t,unit_count=len(units)); row['arms'][label]=arm
    eligible=[x for x in allrows if allowed(x,q,plan)]
    for label,field in [('C0',lambda x:x['retrieval_text']),('C1',lambda x:x['structural_prefix']+'\n'+x['retrieval_text'])]:
        t=time.perf_counter(); values=fts_scores(eligible,queries,field); ranks=sorted(range(len(eligible)),key=lambda i:(-values[i],eligible[i]['path'],eligible[i]['char_start']))[:20]; candidates=[eligible[i] for i in ranks if values[i]>0]; units=atoms(candidates)
        scores=fts_scores(units,queries,lambda x:str(x.get('heading_path') or '')+'\n'+x['snippet']); arm=make_packet(units,scores,q,lookups)
        arm.update(elapsed=time.perf_counter()-t,unit_count=len(units),retrieved_count=len(candidates),retrieved_spans=[{'path':x['path'],'start':x['char_start'],'end':x['char_end']} for x in candidates]); row['arms'][label]=arm
    results.append(row); dump('results.json',results); print('compared',case['id'],{k:len(v.get('payload',{}).get('sources',[])) for k,v in row['arms'].items()},flush=True)
controls=[]; reference=next(x for x in allrows if allowed(x,'documentation',{}))
for key,val in [('project_identity','foreign'),('freshness','stale'),('index_freshness','outdated'),('risk_flags',['instruction_risk'])]:
    ok=not allowed({**reference,key:val},'documentation',{}); controls.append({'mutation':key,'rejected':ok}); assert ok
validation_errors=[{'id':r['id'],'arm':a,'errors':v.get('validation_errors')} for r in results for a,v in r['arms'].items() if v.get('validation_errors')]
assert git('rev-parse','HEAD')==SHA and not git('status','--porcelain','--untracked-files=all')
dump('metadata.json',{'runtime_sha':SHA,'corpus_sha':SHA,'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'model':model_meta,'model_error':model_error,'index_count':len(allrows),'context_prefix_nonempty':sum(bool(x['context_prefix']) for x in allrows),'controls':controls,'binding_rejections':binding_rejections,'validation_errors':validation_errors,'scope':'exposed development diagnostic; not independent holdout; not a weak-reader benchmark'})
print('DONE',flush=True)
