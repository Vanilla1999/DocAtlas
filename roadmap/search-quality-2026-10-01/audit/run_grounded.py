"""Grounded 3.2.1 live stdio comparison on byte-identical selected sources."""
from __future__ import annotations
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from run_live_mcp import ROOT, OUT, WORK, save
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.grounded import extract_visible_sources, controlled_context, inspect_ingest
from eval.evidence_quality_v2.semantic import assess_context
from eval.evidence_quality_v2.cost import count_input, percentiles, model_visible_text
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

NODE = Path('/tmp/opencode/search-audit-tools-20261001/node_modules/@arabold/docs-mcp-server/dist/index.js')
GWORK = WORK / 'grounded'
GOUT = OUT / 'raw/grounded'


async def run():
    _, cases, manifest = load_protocol()
    package = json.loads((NODE.parent.parent / 'package.json').read_text())
    assert package['version'] == '3.2.1'
    GWORK.mkdir(parents=True, exist_ok=True)
    store=GWORK/'store'
    config=GWORK/'config.json'
    config.write_text(json.dumps({'app':{'storePath':str(store),'telemetryEnabled':False},
        'scraper':{'maxPages':10000,'maxDepth':30,'security':{'fileAccess':{
            'mode':'allowedRoots','allowedRoots':[str(GWORK/'corpus')],
            'includeHidden':True,'followSymlinks':False}}}}))
    common=['--config',str(config),'--store-path',str(store),'--no-telemetry','--no-logo']
    env={k:v for k,v in os.environ.items() if not k.endswith('API_KEY')
         and k not in ('OPENAI_BASE_URL','AZURE_OPENAI_ENDPOINT')}
    env.update(PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1',DO_NOT_TRACK='1',
               DOCS_MCP_APP_TELEMETRY_ENABLED='false',HOME=str(GWORK/'home'))
    Path(env['HOME']).mkdir(exist_ok=True)
    save(GOUT/'runtime.json',dict(package=package,command=['node',str(NODE)],
        config=json.loads(config.read_text()),mode='no embedding provider; FTS-only, checked in database',
        comparison='same bytes; native output plus non-product common 800-token/3-block adapter'))
    ingests={}
    for group in sorted({c['project_group'] for c in cases}):
        docs=documents_for(group,manifest)
        corpus=GWORK/'corpus'/group
        logs=[]
        for rel,text in docs.items():
            dest=corpus/rel
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(text)
            command=['node',str(NODE),'scrape',group,dest.as_uri(),
                '--max-pages','1','--max-depth','1','--no-clean',*common]
            start=time.perf_counter()
            process=subprocess.run(command,env=env,cwd=GWORK,capture_output=True,text=True,timeout=240)
            logs.append(dict(command=command,returncode=process.returncode,
                seconds=time.perf_counter()-start,stdout=process.stdout,stderr=process.stderr))
            save(GOUT/'ingest-commands'/f'{group}.json',logs)
            if process.returncode:
                raise RuntimeError('Grounded ingest failed: '+group)
        ingests[group]=inspect_ingest(store,corpus,group,docs)
        save(GOUT/'ingest.json',ingests)
        if any(ingests[group][key] for key in ('missing','unexpected','non_null_embeddings')):
            raise RuntimeError('Ingest parity failed: '+group)
        print('INGEST',group,ingests[group]['chunks'],flush=True)
    params=StdioServerParameters(command='node',args=[str(NODE),'mcp','--protocol','stdio',
        '--read-only',*common],env=env,cwd=str(GWORK))
    rows=[]
    with (GOUT/'mcp-stderr.log').open('w') as errorlog:
        async with stdio_client(params,errlog=errorlog) as (read,write):
            async with ClientSession(read,write) as session:
                save(GOUT/'initialize.json',(await session.initialize()).model_dump(mode='json'))
                tools=await session.list_tools()
                save(GOUT/'tools-list.json',tools.model_dump(mode='json'))
                tool=next(t for t in tools.tools if t.name=='search_docs')
                assert {'library','query','limit'}.issubset(tool.inputSchema['properties'])
                for case in cases:
                    group=case['project_group']
                    for limit in (3,5):
                        args={'library':group,'query':case['question'],'limit':limit}
                        start=time.perf_counter()
                        response=await asyncio.wait_for(session.call_tool('search_docs',args),timeout=90)
                        wire=response.model_dump(mode='json',by_alias=True)
                        text=model_visible_text(wire,'text')
                        record=dict(id=case['id'],project=group,family=case['family'],
                            answerability=case['answerability'],limit=limit,request=args,
                            seconds=time.perf_counter()-start,is_error=response.isError,wire=wire,
                            native_size=count_input(text))
                        save(GOUT/'native'/str(limit)/(case['id']+'.json'),record)
                        sources,binding=extract_visible_sources(text,GWORK/'corpus'/group,documents_for(group,manifest))
                        adapted=controlled_context(sources)
                        record.update(binding=binding,mapped_sources=sources,
                            assessment=assess_context(case,{'sources':sources},registry_for(group,manifest)),
                            controlled=adapted,
                            controlled_assessment=assess_context(case,adapted['payload'],registry_for(group,manifest)))
                        rows.append(record)
                        save(GOUT/'results.json',rows)
                    print('GROUNDED',case['id'],[(r['limit'],r['assessment']['context_sufficiency']) for r in rows[-2:]],flush=True)
    summary={}
    for limit in (3,5):
        subset=[r for r in rows if r['limit']==limit]
        positives=[r for r in subset if r['answerability']=='within_budget']
        summary[str(limit)]=dict(cases=len(subset),positives=len(positives),
            recognized_sufficient=sum(r['assessment']['context_sufficiency']=='sufficient' for r in positives),
            controlled_recognized_sufficient=sum(r['controlled_assessment']['context_sufficiency']=='sufficient' for r in positives),
            assessments=dict(Counter(r['assessment']['context_sufficiency'] for r in subset)),
            controlled_assessments=dict(Counter(r['controlled_assessment']['context_sufficiency'] for r in subset)),
            tokens=percentiles(r['native_size']['actual_tokens'] for r in subset),
            latency=percentiles(r['seconds'] for r in subset),
            unmapped_results=sum(r['binding']['unmapped_results'] for r in subset),
            binding_errors=sum(bool(r['binding']['binding_errors']) for r in subset),
            tool_errors=sum(r['is_error'] for r in subset))
    save(GOUT/'summary.json',summary)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    asyncio.run(run())
