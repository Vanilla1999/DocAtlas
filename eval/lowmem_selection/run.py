"""Installed stdio experiment; source coverage is not paid-model correctness."""
from __future__ import annotations
import argparse, asyncio, hashlib, importlib.util, json, os, resource, statistics, sys, time
from datetime import timedelta
from pathlib import Path

POLICIES = ('main', 'fixed', 'adaptive-gap-v1', 'facet-tiny-select-v1', 'facet-tiny-plan-v1')

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inputs(args):
    if args.suite=='v40':
        helper=load('lowmem_v40',args.repo/'eval/adaptive_gap_integration.py')
        return helper.inputs(args)
    base=args.repo/'eval/lowmem_selection'/args.suite
    cases=json.loads((base/'questions.json').read_text())
    docs=json.loads((base/'sources.json').read_text())
    return [{**c,'project_group':args.suite} for c in cases],{args.suite:docs}

def request(case,root):
    return {'question':case['question'],'project_path':str(root),'scope':'project',
            **{k:case[k] for k in ('search_question','lookup_queries') if k in case}}

def worker(args):
    from docmancer.mcp._docs_server_part01 import _run_async,call_docs_tool_payload
    from docmancer.docs.application.section_compression import observe_section_compression
    runtime=load('lowmem_runtime',args.repo/'eval/evidence_quality_v2/runtime.py')
    state=load('lowmem_state',args.repo/'eval/prepared_model_comparison40/run.py')
    cases,families=inputs(args); root=args.work/args.family/'project';out=args.out/args.family
    runtime.write_project(root,families[args.family])
    with runtime.isolated_service(args.work/args.family/'state') as (service,config):
        inventory=runtime.index_project(service,config,root)
        save(out/'preparation.json',inventory)
        before=state.logical_state(inventory),state.source_state(root)
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION='off',DOCATLAS_CONTEXT_ABSTENTION='off')
        for c in cases:
            if c['project_group']==args.family:
                pool=call_docs_tool_payload('get_docs_context',request(c,root),service)
                assert pool.get('kind')=='docs_context',pool
                save(out/(c['id']+'-pool.json'),pool)
        os.environ.update(DOCATLAS_MINILM_MODEL_DIR='/model',DOCATLAS_MCP_TEXT_FALLBACK='1',
            DOCATLAS_MCP_MODEL_VIEW='1',DOCATLAS_SECTION_WIRE_FORMAT='adaptive-v2',
            DOCATLAS_TINY_URL='http://127.0.0.1:8099',DOCATLAS_TINY_MODEL='docatlas-tiny')
        for k in ('DOCATLAS_CONTEXT_COMPRESSION','DOCATLAS_SECTION_TOP_K','DOCATLAS_SECTION_UNITS','DOCATLAS_SECTION_SELECTION'):
            os.environ.pop(k,None)
        if args.policy!='main':os.environ['DOCATLAS_SECTION_SELECTION']=args.policy
        if args.policy=='fixed':os.environ['DOCATLAS_SECTION_TOP_K']='5'
        if args.policy=='adaptive-gap-v1':os.environ['DOCATLAS_SECTION_UNITS']='markdown-owner-v1'
        with observe_section_compression() as observed:
            try:asyncio.run(_run_async(service))
            finally:
                save(out/'server.json',{'observations':observed,
                    'database_unchanged':before[0]==state.logical_state(inventory),
                    'files_unchanged':before[1]==state.source_state(root),
                    'rss_peak_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})

def source_intervals(rows,docs):
    intervals={}
    for row in rows:
        p,t=row['path_or_url'],row['snippet']; assert p in docs
        lines=docs[p].splitlines(keepends=True); a,b=row['line_start'],row['line_end']
        assert type(a) is int and type(b) is int and 1<=a<=b<=len(lines)
        window=''.join(lines[a-1:b]);assert t in window
        start=sum(map(len,lines[:a-1]))+window.index(t)
        intervals.setdefault(p,[]).append((start,start+len(t)))
    return intervals

def part_covered(part,intervals,docs):
    p,q=part['path'],part['quote'];assert docs[p].count(q)==1
    cursor=docs[p].index(q);end=cursor+len(q)
    for a,b in sorted(intervals.get(p,[])):
        if b<=cursor:continue
        if a>cursor:return False
        cursor=b
        if cursor>=end:return True
    return False

async def execute(args):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.interfaces.host_context import extract_tool_payload
    from docmancer.docs.application.section_compression import expand_sections
    import tiktoken
    enc=tiktoken.get_encoding('o200k_base');cases,families=inputs(args);records=[]
    for family,docs in families.items():
        folder=args.out/family;folder.mkdir(parents=True)
        root=args.work/family/'project'
        params=StdioServerParameters(command=sys.executable,args=['-I',str(Path(__file__).resolve()),
            '--worker','--family',family,'--repo',str(args.repo),'--work',str(args.work),
            '--out',str(args.out),'--policy',args.policy,'--suite',args.suite],env=dict(os.environ))
        with (folder/'stderr.log').open('w') as err:
          async with stdio_client(params,errlog=err) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=240)) as session:
                await session.initialize()
                for c in [x for x in cases if x['project_group']==family]:
                    started=time.monotonic();r=await session.call_tool('get_docs_context',request(c,root))
                    elapsed=time.monotonic()-started;wire=r.model_dump(by_alias=True)
                    save(folder/(c['id']+'-reply.json'),wire)
                    texts=[p.text for p in r.content if p.type=='text'];text='\n'.join(texts)
                    record={'id':c['id'],'family':family,'question':c['question'],
                            'tool_error':bool(r.isError),'seconds':elapsed,'tokens':len(enc.encode(text))}
                    rows=[];packet=None
                    pool=json.loads((folder/(c['id']+'-pool.json')).read_text())
                    if not r.isError:
                        packet=expand_sections(extract_tool_payload(r));rows=packet.get('sources',[])
                        assert packet.get('kind')=='docs_context',packet
                        admitted={x['evidence_id']:x for x in pool['sources']}
                        assert all(x==admitted[x['evidence_id']] for x in rows),'original rows changed'
                        source_intervals(rows,docs)
                        assert packet.get('answer_supported') is False
                    else:record['error_text']=text
                    record['rows']=len(rows)
                    save(folder/(c['id']+'-expanded.json'),packet or {'sources':[]})
                    record['selection_applied']=False
                    records.append(record)
                    print(json.dumps({'case':c['id'],'policy':args.policy,'seconds':round(elapsed,2),
                                      'tokens':record['tokens'],'error':record['tool_error']}),flush=True)
        state=json.loads((folder/'server.json').read_text())
        assert state['database_unchanged'] and state['files_unchanged']
        observations=state['observations']
        # Original/search question hash is matched; no gold enters the selector.
        for record in [r for r in records if r['family']==family]:
            c=next(x for x in cases if x['id']==record['id'])
            key=hashlib.sha256((c.get('search_question') or c['question']).encode()).hexdigest()
            obs=next((o for o in observations if o['scoring_question_sha256']==key),None)
            record['selection']=obs
            if obs:record['selection_applied']=obs.get('tiny_selection',{}).get('applied',False)
    return records

def grade(args,records):
    cases,families=inputs(args)
    if args.suite=='v40':
        base=args.repo/'eval/prepared_model_comparison40'
        oracle=load('lowmem_oracle',base/'evaluate.py')
        gold={x['id']:x for x in json.loads((base/'gold_spans.json').read_text())['cases']}
    else:
        gold=json.loads((args.repo/'eval/lowmem_selection'/args.suite/'gold.json').read_text())
    for record in records:
        case=next(c for c in cases if c['id']==record['id']);docs=families[record['family']]
        folder=args.out/record['family'];packet=json.loads((folder/(record['id']+'-expanded.json')).read_text())
        pool=json.loads((folder/(record['id']+'-pool.json')).read_text())
        def facts(payload):
            if args.suite=='v40':
                prepared={'root':str(args.work/record['family']/'project'),'sources':{}}
                for p,t in docs.items():
                    offsets=[0]
                    for line in t.splitlines(keepends=True):offsets.append(offsets[-1]+len(line))
                    prepared['sources'][p]={'raw':t.encode(),'content':t,'sha256':hashlib.sha256(t.encode()).hexdigest(),'line_offsets':offsets,'errors':[]}
                _,intervals,errors=oracle._source_rows(payload,prepared);assert not errors,errors
                result=oracle._gold(case,gold[case['id']],prepared,intervals)
                assert not result.get('errors'),result
                return [{'id':x['claim_id'],'covered':x['covered']} for x in result['claims'] if x['documented']]
            intervals=source_intervals(payload.get('sources',[]),docs)
            return [{'id':f['id'],'covered':any(all(part_covered(p,intervals,docs) for p in alt)
                    for alt in f['alternatives'])} for f in gold[case['id']]['facts']]
        record['facts']=facts(packet);record['pool_facts']=facts(pool)
        record['complete']=all(f['covered'] for f in record['facts']) if record['facts'] else None
        record['unknown_answer_correct']='NOT_TESTED'
    return records

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('repo','work','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--policy',choices=POLICIES,required=True);p.add_argument('--suite',choices=('v40','pilot','fresh'),required=True)
    p.add_argument('--worker',action='store_true');p.add_argument('--family');a=p.parse_args()
    for k in ('repo','work','out'):setattr(a,k,getattr(a,k).resolve())
    if a.worker:worker(a);return
    import docmancer
    installed=Path(docmancer.__file__).resolve().parent
    assert not installed.is_relative_to(a.repo),'installed wheel required'
    for f in ('facet_selection.py','tiny_selection.py','section_compression.py'):
        assert (installed/'docs/application'/f).read_bytes()==(a.repo/'docmancer/docs/application'/f).read_bytes()
    frozen=json.loads((a.repo/'eval/lowmem_selection/FREEZE.json').read_text())
    assert all(digest(a.repo/name)==sha for name,sha in frozen.items())
    a.out.mkdir(parents=True,exist_ok=True);a.work.mkdir(parents=True)
    save(a.out/'CHECKPOINT.json',{'head':os.environ.get('TESTED_SHA'),'freeze':frozen,'policy':a.policy,'suite':a.suite})
    records=asyncio.run(execute(a))
    assert all(digest(a.repo/name)==sha for name,sha in frozen.items())
    records=grade(a,records)
    success=[r for r in records if not r['tool_error']]
    summary={'policy':a.policy,'suite':a.suite,'head':os.environ.get('TESTED_SHA'),'cases':records,
        'requirements':sum(len(r['facts']) for r in records),
        'delivered':sum(sum(f['covered'] for f in r['facts']) for r in records),
        'complete_cases':sum(r['complete'] is True for r in records),'documented_cases':sum(bool(r['facts']) for r in records),
        'tool_errors':sum(r['tool_error'] for r in records),'tokens_including_errors':sum(r['tokens'] for r in records),
        'median_success_seconds':statistics.median(r['seconds'] for r in success) if success else None,
        'tiny_applied':sum(r['selection_applied'] for r in records),'stdio_calls':len(records),'pool_calls':len(records),
        'source_and_database_unchanged':True,'paid_model_calls':0,'provider_usage':None,'semantic_answers':'NOT_TESTED'}
    save(a.out/'SUMMARY.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='cases'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
