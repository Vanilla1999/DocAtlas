"""Research replay of real installed-MCP outputs. Not a new product acceptance test.
Frozen: complete source sections; BM25(k1=1.2,b=.75) vs MiniLM-MaxP;
top-5 primary, top-10 sensitivity; all candidates; no abstention/score cutoffs;
non-overlapping model-only token slices <=512; no emitted text truncation.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, math, os
from pathlib import Path
import re, resource, statistics, sys, time

def sha(raw): return hashlib.sha256(raw).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def load(path): return json.loads(path.read_bytes())
def union(spans):
    merged=[]
    for a,b in sorted(spans):
        if merged and a<=merged[-1][1]: merged[-1][1]=max(merged[-1][1],b)
        else: merged.append([a,b])
    return merged

def prepare(repo,base,case):
    corpus=repo/'eval/prepared_model_comparison40'
    record=load(base/'docatlas/preparation'/f"{case['project_group']}.json")
    declared={r['path']:r['content_sha256'].removeprefix('sha256:') for r in record['inventory']['documents']}
    snapshots={r['path']:r['content_sha256'].removeprefix('sha256:') for r in record['snapshot_sources']}
    sources={}
    for p in (corpus/'sources'/case['project_group']).rglob('*'):
        if not p.is_file(): continue
        raw=p.read_bytes();text=raw.decode('utf-8');offsets=[0]
        for line in text.splitlines(keepends=True): offsets.append(offsets[-1]+len(line))
        rel=p.relative_to(corpus/'sources'/case['project_group']).as_posix()
        assert declared.get(rel)==snapshots.get(rel)==sha(raw),'pinned source hash mismatch'
        sources[rel]={'content':text,'raw':raw,'sha256':sha(raw),'line_offsets':offsets,'errors':[]}
    return {'root':record['root'],'sources':sources}

def sections(dto,prepared):
    grouped=collections.defaultdict(list);placed={}
    for i,r in enumerate(dto['sources']):
        path=r['path_or_url'];s=prepared['sources'][path];off=s['line_offsets']
        lo,hi=off[r['line_start']-1],off[r['line_end']];positions=[];pos=lo
        while True:
            p=s['content'].find(r['snippet'],pos,hi)
            if p<0: break
            positions.append(p);pos=p+1
        if len(positions)!=1: raise ValueError('nonunique source placement')
        a=positions[0];placed[i]=(a,a+len(r['snippet']))
        key=(path,r.get('section',''),r['project_identity'],r['scope'],r['version_binding'],r['authority'])
        grouped[key].append(i)
    result=[]
    for key,ids in sorted(grouped.items()):
        path,section=key[:2];spans=union(placed[i] for i in ids)
        text='\n\n'.join(prepared['sources'][path]['content'][a:b] for a,b in spans)
        result.append({'key':list(key),'path':path,'section':section,'row_indices':ids,'spans':spans,'text':text})
    assert sorted(i for s in result for i in s['row_indices'])==list(range(len(dto['sources'])))
    return result

def compact(prepared,units):
    paths=sorted({s['path'] for s in units});mapping={p:f'S{i+1}' for i,p in enumerate(paths)}
    docs=[{'id':mapping[p],'path':p} for p in paths];parts=[]
    for s in sorted(units,key=lambda x:(x['path'],x['spans'][0][0])):
        for a,b in s['spans']:
            parts.append({'doc':mapping[s['path']],'chars':[a,b],'text':prepared['sources'][s['path']]['content'][a:b]})
    return {'schema':'research-compact-source-sections-v1','support':'unassessed','authority':'source-data-only','documents':docs,'parts':parts}

def bm25(query,units):
    terms=lambda text:re.findall(r'[^\W_]+',text.lower(),flags=re.UNICODE)
    docs=[terms(s['text']) for s in units];n=len(docs)
    dfs=collections.Counter(t for d in docs for t in set(d));avg=sum(map(len,docs))/max(1,n);q=set(terms(query));out=[]
    for d in docs:
        tf=collections.Counter(d);denom=1.2*(1-.75+.75*len(d)/max(avg,1))
        out.append(sum(math.log(1+(n-dfs[t]+.5)/(dfs[t]+.5))*tf[t]*2.2/(tf[t]+denom) for t in q if tf[t]))
    return out,{'scored_sections':n,'model_calls':0}

class Neural:
    def __init__(self,model):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        start=time.perf_counter();opts=ort.SessionOptions()
        opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
        opts.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        self.session=ort.InferenceSession(str(model/'onnx/model.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
        self.tok=Tokenizer.from_file(str(model/'tokenizer.json'));self.tok.no_truncation();self.tok.no_padding()
        self.cls=self.tok.token_to_id('[CLS]');self.sep=self.tok.token_to_id('[SEP]')
        self.init_seconds=time.perf_counter()-start
    def score(self,query,units):
        import numpy as np
        q=self.tok.encode(query,add_special_tokens=False).ids
        if len(q)>128: raise ValueError('query_overflow:no truncation')
        cap=512-len(q)-3;out=[];calls=0;max_seq=0;split_sections=0;total=0
        names={x.name for x in self.session.get_inputs()}
        for s in units:
            p=self.tok.encode(s['text'],add_special_tokens=False).ids
            chunks=[p[i:i+cap] for i in range(0,len(p),cap)] or [[]]
            assert sum(map(len,chunks))==len(p)
            if len(chunks)>1: split_sections+=1
            values=[]
            for chunk in chunks:
                ids=[self.cls]+q+[self.sep]+chunk+[self.sep];types=[0]*(len(q)+2)+[1]*(len(chunk)+1)
                feeds={'input_ids':np.array([ids],dtype=np.int64),'attention_mask':np.ones((1,len(ids)),dtype=np.int64),'token_type_ids':np.array([types],dtype=np.int64)}
                logits=self.session.run(None,{k:v for k,v in feeds.items() if k in names})[0]
                values.append(float(logits.reshape(-1)[0]));calls+=1;max_seq=max(max_seq,len(ids));total+=len(ids)
            out.append(max(values))
        return out,{'scored_sections':len(units),'model_calls':calls,'max_pair_tokens':max_seq,'split_sections':split_sections,'total_pair_tokens':total,'truncated_tokens':0}

def run(args):
    import tiktoken
    enc=tiktoken.get_encoding('o200k_base')
    tokens=lambda obj:len(enc.encode(json.dumps(obj,ensure_ascii=False,separators=(',',':')),disallowed_special=()))
    cases=load(args.baseline/'docatlas/MANIFEST.json')['cases'];assert len(cases)==40
    model=Neural(args.model) if args.arm=='minilm' else None;records=[];fingerprints={}
    for case in cases:
        start=time.perf_counter();cid=case['id'];dto=load(args.baseline/'docatlas'/f'{cid}-dto.json');prepared=prepare(args.repo,args.baseline,case)
        units=sections(dto,prepared);before=time.perf_counter()
        scores,diag=model.score(case['question'],units) if model else bm25(case['question'],units)
        score_seconds=time.perf_counter()-before;ranked=sorted(range(len(units)),key=lambda i:(-scores[i],units[i]['key']));profiles={}
        for k in (5,10):
            chosen=ranked[:k];selected=[units[i] for i in chosen];ids=sorted(j for u in selected for j in u['row_indices']);rows=[dto['sources'][j] for j in ids]
            view=compact(prepared,selected);wire=json.dumps(view,ensure_ascii=False,separators=(',',':')).encode()
            save(args.out/args.arm/cid/f'top{k}.json',{'selected_rows':rows,'model_view':view})
            profiles[str(k)]={'selected_sections':len(chosen),'selected_rows':len(rows),'compact_tokens':tokens(view),'compact_bytes':len(wire),'compact_cost':max(tokens(view),math.ceil(len(wire)/4)),'source_chars':sum(len(r['snippet']) for r in rows),'selected_indices':chosen,'whole_sections':True}
        rec={'case_id':cid,'answerability':case['answerability'],'pool_rows':len(dto['sources']),'pool_sections':len(units),'score_seconds':score_seconds,'total_seconds':time.perf_counter()-start,'baseline_dto_tokens':len(enc.encode(json.dumps(dto,ensure_ascii=False),disallowed_special=())),'baseline_compact_tokens':tokens(compact(prepared,units)),'profiles':profiles,'diagnostics':diag}
        save(args.out/args.arm/cid/'scores.json',{'units':[{k:v for k,v in u.items() if k!='text'} for u in units],'scores':scores,'ranked':ranked,'record':rec});records.append(rec)
        for name,s in prepared['sources'].items(): fingerprints[case['project_group']+'/'+name]=s['sha256']
        print(json.dumps({'case':cid,'arm':args.arm,'seconds':round(score_seconds,3),'sections':len(units),'tokens5':profiles['5']['compact_tokens']}),flush=True)
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024;cg=Path('/sys/fs/cgroup/memory.peak');cg_peak=int(cg.read_text()) if cg.exists() else None
    save(args.out/f'{args.arm}-results.json',{'arm':args.arm,'cases':records,'peak_rss_bytes':peak,'cgroup_memory_peak_bytes':cg_peak,'model_load_seconds':model.init_seconds if model else 0,'source_hashes':fingerprints,'policy':'top5 primary/top10 sensitivity, no tuning','scope':'offline research replay of 40 real MCP outputs; not installed current product','memory_limit_bytes':1000000000})
    if peak>1000000000: raise RuntimeError('RAM FAIL')

def assess(args):
    corpus=args.repo/'eval/prepared_model_comparison40';spec=importlib.util.spec_from_file_location('independent_oracle',corpus/'evaluate.py')
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    gold={c['id']:c for c in load(corpus/'gold_spans.json')['cases']};cases=load(args.baseline/'docatlas/MANIFEST.json')['cases'];summary={};details=[]
    for arm in ('bm25','minilm'):
        data=load(args.out/f'{arm}-results.json');by_id={r['case_id']:r for r in data['cases']}
        for k in (5,10):
            counts=collections.Counter();rows=[]
            for case in cases:
                cid=case['id'];prepared=prepare(args.repo,args.baseline,case);packet=load(args.out/arm/cid/f'top{k}.json');src=packet['selected_rows']
                verified,intervals,errors=oracle._source_rows({'sources':src},prepared);coverage=oracle._gold(case,gold[cid],prepared,intervals)
                view=packet['model_view'];paths={d['id']:d['path'] for d in view['documents']};rendered=collections.defaultdict(list)
                for part in view['parts']:
                    p=paths[part['doc']];a,b=part['chars'];assert part['text']==prepared['sources'][p]['content'][a:b];rendered[p].append((a,b))
                assert {p:union(s) for p,s in rendered.items()}=={p:union(s) for p,s in intervals.items()}
                valid=not errors and not coverage.get('errors');passed=valid and (not src if case['answerability']=='unanswerable' else coverage['all_documented_claims_covered'])
                counts[case['answerability']+'_total']+=1;counts[case['answerability']+'_pass']+=int(passed);counts['integrity_pass']+=int(valid);counts['total_pass']+=int(passed)
                row={'arm':arm,'k':k,'case_id':cid,'pass':passed,'answerability':case['answerability'],'coverage':coverage,'errors':errors,**by_id[cid]['profiles'][str(k)]};details.append(row);rows.append(row)
            costs=[r['compact_tokens'] for r in rows]
            summary[f'{arm}-top{k}']={**counts,'tokens_total':sum(costs),'tokens_mean':statistics.mean(costs),'tokens_median':statistics.median(costs),'tokens_max':max(costs),'over_12000':sum(r['compact_cost']>12000 for r in rows),'score_seconds_median':statistics.median(r['score_seconds'] for r in data['cases']),'score_seconds_total':sum(r['score_seconds'] for r in data['cases']),'peak_rss_bytes':data['peak_rss_bytes'],'cgroup_memory_peak_bytes':data['cgroup_memory_peak_bytes'],'failed':[r['case_id'] for r in rows if not r['pass']],'P03':next(r['pass'] for r in rows if r['case_id']=='V40-P03'),'E01':next(r['pass'] for r in rows if r['case_id']=='V40-E01')}
    save(args.out/'SUMMARY.json',summary);save(args.out/'ASSESSMENTS.json',details);print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--model',type=Path);p.add_argument('--arm',choices=['bm25','minilm','assess'],required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.arm=='assess': assess(a)
    else: run(a)
