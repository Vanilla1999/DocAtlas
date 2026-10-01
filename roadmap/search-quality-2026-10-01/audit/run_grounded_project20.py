"""Predeclared bilingual 20-case project diagnostic on the identical 134 files."""
import asyncio
import json
import os
import subprocess
import time
from run_live_mcp import ROOT, OUT, WORK, save
from run_grounded import NODE, GWORK
from eval.evidence_quality_v2.grounded import inspect_ingest
from eval.evidence_quality_v2.cost import count_input, model_visible_text
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

IDS=['projectA-Q02','projectA-Q05','projectA-Q07','projectA-Q09','projectA-Q11',
     'projectA-Q14','projectA-Q18','projectA-Q23','projectA-Q25','projectA-Q29',
     'projectB-Q03','projectB-Q04','projectB-Q08','projectB-Q10','projectB-Q14',
     'projectB-Q17','projectB-Q20','projectB-Q23','projectB-Q28','projectB-Q34']


async def main():
    destination=OUT/'raw/grounded-project20'
    cases={r['id']:r for r in json.loads((OUT/'raw/project80/results.json').read_text()) if r['lane']=='all'}
    save(destination/'protocol.json',dict(ids=IDS,note='Chosen mechanism cases before Grounded run; 10 RU and 10 EN, not random holdout.'))
    corpus=WORK/'corpus/docatlas-project'
    docs={entry['path']:(corpus/entry['path']).read_text() for entry in json.loads((OUT/'raw/index/docatlas-project.json').read_text())['manifest']}
    store=GWORK/'project-store'
    config=GWORK/'project-config.json'
    config.write_text(json.dumps({'app':{'storePath':str(store),'telemetryEnabled':False},'scraper':{
        'maxPages':10000,'maxDepth':30,'security':{'fileAccess':{'mode':'allowedRoots',
            'allowedRoots':[str(corpus)],'includeHidden':True,'followSymlinks':False}}}}))
    common=['--config',str(config),'--store-path',str(store),'--no-telemetry','--no-logo']
    env={k:v for k,v in os.environ.items() if not k.endswith('API_KEY') and k not in ('OPENAI_BASE_URL','AZURE_OPENAI_ENDPOINT')}
    env.update(PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1',DO_NOT_TRACK='1',DOCS_MCP_APP_TELEMETRY_ENABLED='false',HOME=str(GWORK/'home'))
    command=['node',str(NODE),'scrape','docatlas',corpus.as_uri(),'--max-pages','10000','--max-depth','30','--no-clean',*common]
    start=time.perf_counter()
    proc=subprocess.run(command,env=env,cwd=GWORK,capture_output=True,text=True,timeout=600)
    save(destination/'ingest-command.json',dict(command=command,seconds=time.perf_counter()-start,returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
    if proc.returncode:
        raise RuntimeError('Grounded project ingest failed')
    ingest=inspect_ingest(store,corpus,'docatlas',docs)
    # Directory scraping omitted one URL. Restore corpus parity before querying,
    # without changing the questions, scoring, or the document bytes.
    supplemental=[]
    for url in ingest['missing']:
        command=['node',str(NODE),'scrape','docatlas',url,'--max-pages','1','--max-depth','1','--no-clean',*common]
        start=time.perf_counter();proc=subprocess.run(command,env=env,cwd=GWORK,capture_output=True,text=True,timeout=300)
        supplemental.append(dict(command=command,seconds=time.perf_counter()-start,returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
    save(destination/'supplemental-ingest.json',supplemental)
    ingest=inspect_ingest(store,corpus,'docatlas',docs)
    save(destination/'ingest.json',ingest)
    if any(ingest[k] for k in ('missing','unexpected','non_null_embeddings')):
        raise RuntimeError('Grounded project corpus parity failure')
    params=StdioServerParameters(command='node',args=[str(NODE),'mcp','--protocol','stdio','--read-only',*common],env=env,cwd=str(GWORK))
    rows=[]
    with (destination/'stderr.log').open('w') as errs:
        async with stdio_client(params,errlog=errs) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                for id_ in IDS:
                    case=cases[id_];args=dict(library='docatlas',query=case['question'],limit=3)
                    start=time.perf_counter();response=await session.call_tool('search_docs',args)
                    wire=response.model_dump(mode='json',by_alias=True);text=model_visible_text(wire,'text')
                    row=dict(id=id_,question=case['question'],language=case['language'],request=args,
                        wire=wire,is_error=response.isError,seconds=time.perf_counter()-start,text=text,size=count_input(text))
                    save(destination/'native'/f'{id_}.json',row);rows.append(row)
                    save(destination/'results.json',rows)
                    print(id_,row['size']['actual_tokens'],flush=True)


if __name__=='__main__':
    asyncio.run(main())
