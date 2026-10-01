"""Small live hosted Context7 diagnostic, explicitly NOT corpus/version-matched."""
import asyncio
import json
import re
import time
from run_live_mcp import ROOT, OUT, save
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from eval.evidence_quality_v2.cost import count_input

SELECTION=['fastapi-02','fastapi-04','starlette-03','typer-01','pydantic-02',
           'pydantic-03','httpx-03','mkdocs-05','ruff-01','uv-05']


async def run():
    cases=json.loads((ROOT/'eval/evidence_quality_v2/cases.json').read_text())['cases']
    cases=[next(c for c in cases if c['id']==id_) for id_ in SELECTION]
    save(OUT/'raw/context7/protocol.json',dict(ids=SELECTION,
        note='Hand-selected development diagnostics; hosted current corpus is not pinned upstream snapshot. No answer model.'))
    prior=OUT/'raw/context7/results.json'
    rows=json.loads(prior.read_text()) if prior.exists() else []
    complete={r['id'] for r in rows if r.get('text') and not r.get('is_error')}
    cases=[c for c in cases if c['id'] not in complete]
    async with streamablehttp_client('https://mcp.context7.com/mcp',timeout=90) as (read,write,_):
        async with ClientSession(read,write) as session:
            save(OUT/'raw/context7/initialize.json',(await session.initialize()).model_dump(mode='json'))
            tools=await session.list_tools()
            save(OUT/'raw/context7/tools-list.json',tools.model_dump(mode='json'))
            names={t.name for t in tools.tools}
            assert {'resolve-library-id','query-docs'} <= names
            resolved={}
            for case in cases:
                group=case['project_group']
                if group not in resolved:
                    args=dict(libraryName=group,query=case['question'])
                    start=time.perf_counter()
                    response=await session.call_tool('resolve-library-id',args)
                    wire=response.model_dump(mode='json',by_alias=True)
                    save(OUT/'raw/context7/resolve'/f'{group}.json',dict(request=args,
                        seconds=time.perf_counter()-start,wire=wire,is_error=response.isError))
                    text='\n'.join(b.get('text','') for b in wire.get('content',[]) if b.get('type')=='text')
                    ids=re.findall(r'Context7-compatible library ID:\s*(/[^\s]+)',text)
                    if response.isError or not ids:
                        rows.append(dict(id=case['id'],error='resolve_failed',wire=wire))
                        save(OUT/'raw/context7/results.json',rows)
                        continue
                    # First ranked matching result; no hidden gold-based library selection.
                    resolved[group]=ids[0]
                args=dict(libraryId=resolved[group],query=case['question'])
                start=time.perf_counter()
                response=await session.call_tool('query-docs',args)
                wire=response.model_dump(mode='json',by_alias=True)
                text='\n'.join(b.get('text','') for b in wire.get('content',[]) if b.get('type')=='text')
                row=dict(id=case['id'],question=case['question'],library_id=resolved[group],
                    request=args,seconds=time.perf_counter()-start,is_error=response.isError,
                    wire=wire,text=text,size=count_input(text),version_matched=False,
                    source_matched=False,semantic_assessment='manual; separate from frozen witness matching')
                save(OUT/'raw/context7/native'/f'{case["id"]}.json',row)
                rows.append(row)
                save(OUT/'raw/context7/results.json',rows)
                print(case['id'],resolved[group],row['size']['actual_tokens'],'error=',response.isError,flush=True)


if __name__=='__main__':
    asyncio.run(run())
