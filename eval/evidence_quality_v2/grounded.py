"""Pinned Grounded native lexical comparison plus an explicitly named adapter.

Native results retain Grounded's text and limits. The controlled adapter only
maps *already visible* paragraphs to exact original source paragraphs, keeps
native order and applies the predeclared token/three-block cap without gold.
Unmappable paragraphs are reported, never forged into contiguous citations.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import traceback
from urllib.parse import unquote,urlparse

from eval.evidence_quality_v2.cost import count_input,model_visible_text,percentiles
from eval.evidence_quality_v2.run import load_protocol,documents_for,registry_for
from eval.evidence_quality_v2.runtime import save_json,digest
from eval.evidence_quality_v2.semantic import assess_context


def rendered_normalization(text: str) -> str:
    """Formatting only: no stemming, paraphrases, polarity or identifier changes."""
    text=re.sub(r'\[([^\]]+)\]\([^\n)]+\)',r'\1',text)
    text=re.sub(r'(?<!\w)[*_]{1,2}([^\n]+?)[*_]{1,2}(?!\w)',r'\1',text)
    text=re.sub(r'(?m)^\s*[-*+]\s+', '- ', text)
    return ' '.join(text.split())


def paragraphs(text: str):
    """Source-local atomic paragraphs (lists and fenced blocks are not split)."""
    lines=text.splitlines(keepends=True)
    start=0;fenced=False;block=[]
    for index,line in enumerate(lines):
        if line.lstrip().startswith(('```','~~~')): fenced=not fenced
        if not line.strip() and not fenced:
            if block:
                yield start+1,index,''.join(block).rstrip('\n')
                block=[]
        else:
            if not block:start=index
            block.append(line)
    if block:yield start+1,len(lines),''.join(block).rstrip('\n')


def extract_visible_sources(text: str,root: Path,documents: dict[str,str]) -> tuple[list[dict],dict]:
    """Source binding for evaluation only, not a claim of native citation hashes."""
    matches=list(re.finditer(r'(?m)^Result (\d+): (file://[^\n]+)\n',text))
    sources=[];mapped=[];errors=[];seen=set()
    for index,match in enumerate(matches):
        path=Path(unquote(urlparse(match.group(2)).path)).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append('result outside isolated corpus');continue
        rel=str(path.relative_to(root.resolve()))
        if rel not in documents:
            errors.append('result absent from ingest manifest: '+rel);continue
        end=matches[index+1].start() if index+1<len(matches) else len(text)
        body=text[match.end():end].strip()
        body=re.sub(r'\n-+\s*$','',body).strip()
        norm=rendered_normalization(body)
        occurrences=[]
        for first,last,original in paragraphs(documents[rel]):
            needle=rendered_normalization(original)
            at=norm.find(needle)
            if needle and at>=0:
                occurrences.append((at,first,last,original))
        occurrences.sort()
        for position,first,last,original in occurrences:
            identity=(rel,first,last)
            if identity in seen:continue
            seen.add(identity)
            # Native assessment uses only an original equivalent of an entirely
            # visible paragraph. The normalized match is exported for review.
            eid='mapped-'+hashlib.sha256(repr(identity).encode()).hexdigest()[:16]
            source={'evidence_id':eid,'path_or_url':rel,'snippet':original,'line_start':first,'line_end':last,
                    'content_sha256':digest(documents[rel].encode()),'mapping':'formatting-only paragraph preimage',
                    'native_result':int(match.group(1)),'native_normalized_offset':position}
            sources.append(source)
        mapped.append({'result':int(match.group(1)),'path':rel,'paragraphs_mapped':len(occurrences),
                       'native_body':body,'native_contiguous_citation':'NOT_PROVIDED'})
    return sources,{'native_results':len(matches),'mapping':mapped,'binding_errors':errors,
                    'unmapped_results':sum(not r['paragraphs_mapped'] for r in mapped),
                    'note':'Conservative paragraph mapping is not a universal semantic judge; unresolved text stays reviewable.'}


def controlled_context(sources: list[dict],max_tokens: int=800,max_sources: int=3) -> dict:
    """Same source-preserving adapter for both systems, no access to case/gold."""
    chosen=[];seen=set();dropped=0
    for row in sources:
        clean={k:row[k] for k in ('evidence_id','path_or_url','snippet','line_start','line_end','content_sha256') if k in row}
        identity=(clean.get('path_or_url'),clean.get('line_start'),clean.get('line_end'),clean.get('snippet'))
        if identity in seen:continue
        seen.add(identity)
        proposed={'kind':'docs_context','answer_supported':False,'sources':[*chosen,clean]}
        if len(chosen)>=max_sources or count_input(json.dumps(proposed,ensure_ascii=False,sort_keys=True,separators=(',',':')))['actual_tokens']>max_tokens:
            dropped+=1;continue
        chosen.append(clean)
    payload={'kind':'docs_context','answer_supported':False,'sources':chosen}
    return {'payload':payload,'dropped_whole_source_blocks':dropped,
            'size':count_input(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')))}


def inspect_ingest(store: Path,root: Path,project: str,documents: dict) -> dict:
    with sqlite3.connect(store/'documents.db') as db:
        rows=db.execute('SELECT p.url FROM pages p JOIN versions v ON v.id=p.version_id JOIN libraries l ON l.id=v.library_id WHERE l.name=?',(project,)).fetchall()
        urls=sorted(row[0] for row in rows)
        embeddings=db.execute('SELECT count(*) FROM documents d JOIN pages p ON p.id=d.page_id JOIN versions v ON v.id=p.version_id JOIN libraries l ON l.id=v.library_id WHERE l.name=? AND d.embedding IS NOT NULL',(project,)).fetchone()[0]
        chunks=db.execute('SELECT count(*) FROM documents d JOIN pages p ON p.id=d.page_id JOIN versions v ON v.id=p.version_id JOIN libraries l ON l.id=v.library_id WHERE l.name=?',(project,)).fetchone()[0]
    expected=sorted((root/rel).as_uri() for rel in documents)
    return {'expected_urls':expected,'indexed_urls':urls,'missing':sorted(set(expected)-set(urls)),
            'unexpected':sorted(set(urls)-set(expected)),'non_null_embeddings':embeddings,'chunks':chunks}


async def query_all(node: Path,output: Path,config: Path,env: dict,cases: list,manifest: dict):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    common=['--config',str(config),'--store-path',str(output/'store'),'--no-telemetry','--no-logo']
    params=StdioServerParameters(command='node',args=[str(node),'mcp','--protocol','stdio','--read-only',*common],env=env,cwd=str(output))
    rows=[]
    with (output/'mcp-stderr.log').open('w') as errors:
        async with stdio_client(params,errlog=errors) as (read,write):
            async with ClientSession(read,write) as session:
                init=await session.initialize();tools=await session.list_tools()
                save_json(output/'initialize.json',init.model_dump(mode='json'))
                save_json(output/'tools-list.json',tools.model_dump(mode='json'))
                props=next(t for t in tools.tools if t.name=='search_docs').inputSchema['properties']
                if not {'library','query','limit'}.issubset(props):raise ValueError('pinned search schema drift')
                for case in cases:
                    project=case['project_group'];root=output/'corpus'/project
                    docs=documents_for(project,manifest);registry=registry_for(project,manifest)
                    for limit in (1,3,5):
                        args={'library':project,'query':case['question'],'limit':limit}
                        try:
                            start=time.perf_counter()
                            result=await asyncio.wait_for(session.call_tool('search_docs',args),timeout=60)
                            elapsed=time.perf_counter()-start
                            wire=result.model_dump(mode='json',by_alias=True)
                            text=model_visible_text(wire,'text')
                            row={'id':case['id'],'project':project,'split':case['split'],'family':case['family'],
                                 'answerability':case['answerability'],'limit':limit,'request':args,
                                 'wire':wire,'native_size':count_input(text),'seconds':elapsed,'is_error':result.isError}
                            # Persist official result before any scoring or mapping.
                            save_json(output/'native'/str(limit)/f'{case["id"]}.json',row)
                            sources,binding=extract_visible_sources(text,root,docs)
                            native=assess_context(case,{'sources':sources},registry)
                            controlled=controlled_context(sources)
                            row.update(binding=binding,native_assessment=native,controlled=controlled,
                                       controlled_assessment=assess_context(case,controlled['payload'],registry))
                        except Exception as exc:
                            row={'id':case['id'],'project':project,'split':case['split'],'family':case['family'],
                                 'answerability':case['answerability'],'limit':limit,'request':args,'error':repr(exc)}
                            with (output/'errors.log').open('a') as log:log.write(traceback.format_exc()+'\n')
                        rows.append(row);save_json(output/'assessed'/str(limit)/f'{case["id"]}.json',row)
                    print(project,case['id'],[(r['limit'],r.get('native_assessment',{}).get('context_sufficiency',r.get('error'))) for r in rows[-3:]],flush=True)
    return rows


def run(node: Path,output: Path,docatlas_output: Path | None=None):
    protocol,cases,manifest=load_protocol();output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    package=json.loads((node.parents[1]/'package.json').read_text())
    if package['name']!='@arabold/docs-mcp-server' or package['version']!='3.1.0':raise ValueError('Grounded pin mismatch')
    env={k:v for k,v in os.environ.items() if not k.endswith('API_KEY') and k not in ('OPENAI_BASE_URL','AZURE_OPENAI_ENDPOINT')}
    env.update(PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1',DO_NOT_TRACK='1',DOCS_MCP_APP_TELEMETRY_ENABLED='false',HOME=str(output/'home'))
    Path(env['HOME']).mkdir(exist_ok=True)
    store=output/'store';config=output/'config.json'
    config.write_text(json.dumps({'app':{'storePath':str(store),'telemetryEnabled':False},'scraper':{'maxPages':1,'maxDepth':1,
        'security':{'fileAccess':{'mode':'allowedRoots','allowedRoots':[str(output/'corpus')],'includeHidden':True,'followSymlinks':False}}}}))
    common=['--config',str(config),'--store-path',str(store),'--no-telemetry','--no-logo']
    ingests={}
    for project in sorted({c['project_group'] for c in cases}):
        root=output/'corpus'/project;docs=documents_for(project,manifest)
        start=time.perf_counter();commands=[]
        for rel,text in docs.items():
            target=root/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')
            cmd=['node',str(node),'scrape',project,target.as_uri(),'--max-pages','1','--max-depth','1','--no-clean',*common]
            proc=subprocess.run(cmd,env=env,cwd=output,text=True,capture_output=True,timeout=180)
            commands.append({'path':rel,'exit':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            save_json(output/'ingest-commands'/f'{project}.json',commands)
            if proc.returncode:raise RuntimeError('Grounded ingest failed; raw operational log saved')
        ingests[project]={**inspect_ingest(store,root,project,docs),'seconds':time.perf_counter()-start}
        save_json(output/'ingest.json',ingests)
        if ingests[project]['non_null_embeddings'] or ingests[project]['missing'] or ingests[project]['unexpected']:
            raise RuntimeError('ingest/mode differs from pinned selected corpus')
    rows=asyncio.run(query_all(node,output,config,env,cases,manifest))
    save_json(output/'rows.json',rows)
    return summarize_saved(output,docatlas_output)


def summarize_saved(output: Path,docatlas_output: Path | None=None):
    protocol,cases,manifest=load_protocol()
    rows=[json.loads(p.read_text()) for p in sorted((output/'assessed').glob('*/*.json'))]
    expected={(c['id'],limit) for c in cases for limit in (1,3,5)}
    if {(r['id'],r['limit']) for r in rows} != expected or len(rows)!=len(expected):
        raise ValueError('incomplete or duplicate native query inventory')
    ingests=json.loads((output/'ingest.json').read_text())
    summary={'package':'@arabold/docs-mcp-server','version':'3.1.0','mode':'verified null embeddings, FTS-only',
        'native_transport':'official text channel; only one host channel counted',
        'semantic_assessment':'approved source paragraphs with formatting-only mapping; unknown/unmapped alternatives need review',
        'unseen_validation':'NOT_MEASURED','host_quality':'NOT_MEASURED','ingest':ingests,'limits':{},'paired_controlled_docatlas':{}}
    for limit in (1,3,5):
        subset=[r for r in rows if r['limit']==limit];valid=[r for r in subset if not r.get('error') and not r.get('is_error')]
        within=[r for r in valid if r['answerability']=='within_budget']
        summary['limits'][str(limit)]={'cases':len(subset),'errors':len(subset)-len(valid),
            'within_budget_total':sum(r['answerability']=='within_budget' for r in subset),
            'native_recognized_sufficient':sum(r['native_assessment']['context_sufficiency']=='sufficient' for r in within),
            'controlled_recognized_sufficient':sum(r['controlled_assessment']['context_sufficiency']=='sufficient' for r in within),
            'native_sufficiency':dict(Counter(r['native_assessment']['context_sufficiency'] for r in valid)),
            'controlled_sufficiency':dict(Counter(r['controlled_assessment']['context_sufficiency'] for r in valid)),
            'native_tokens':percentiles(r['native_size']['actual_tokens'] for r in valid),
            'controlled_tokens':percentiles(r['controlled']['size']['actual_tokens'] for r in valid),
            'latency_seconds':percentiles(r['seconds'] for r in valid),
            'unmapped_results':sum(r['binding']['unmapped_results'] for r in valid)}
    if docatlas_output:
        controlled_rows=[]
        for case in cases:
            file=docatlas_output/'payloads'/'A-current'/f'{case["id"]}.json'
            if not file.exists():raise ValueError('missing native DocAtlas payload for common adapter')
            payload=json.loads(file.read_text());adapted=controlled_context(payload.get('sources',[]))
            assessment=assess_context(case,adapted['payload'],registry_for(case['project_group'],manifest))
            controlled_rows.append({'id':case['id'],'answerability':case['answerability'],'controlled':adapted,'assessment':assessment})
        save_json(output/'docatlas-common-adapter.json',controlled_rows)
        summary['paired_controlled_docatlas']={'cases':len(controlled_rows),'within_budget_recognized_sufficient':sum(r['answerability']=='within_budget' and r['assessment']['context_sufficiency']=='sufficient' for r in controlled_rows),
            'tokens':percentiles(r['controlled']['size']['actual_tokens'] for r in controlled_rows)}
    save_json(output/'summary.json',summary);save_json(output/'rows.json',rows)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--node-entry',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--docatlas-output',type=Path)
    parser.add_argument('--summarize-saved',action='store_true')
    args=parser.parse_args();report=(summarize_saved(args.output,args.docatlas_output) if args.summarize_saved else run(args.node_entry,args.output,args.docatlas_output))
    print(json.dumps(report['limits'],indent=2));return int(any(r['errors'] for r in report['limits'].values()))

if __name__=='__main__':raise SystemExit(main())
