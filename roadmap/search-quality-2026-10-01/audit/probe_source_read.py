"""Immediate read smoke distinguishes live continuation from late cache eviction."""
import asyncio
import json
import time
from run_live_mcp import ROOT, OUT, WORK, save, call, env_for_server
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params=StdioServerParameters(command='/home/viadmin/.local/bin/doc-atlas',args=['mcp','docs-serve'],env=env_for_server(),cwd=str(WORK))
    case=next(r for r in json.loads((OUT/'raw/project80/results.json').read_text()) if r['id']=='projectB-Q18' and r['lane']=='all')
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as session:
            await session.initialize()
            _,payload=await call(session,'get_docs_context',case['request'],OUT/'raw/resource-reads/immediate-query.json')
            sources=[s for s in payload.get('sources',[]) if s.get('source_uri')]
            if not sources:
                save(OUT/'raw/resource-reads/immediate-read.json',dict(status='no_locator_in_packet'))
                return
            source=sources[0];start=time.perf_counter()
            result=await session.read_resource(source['source_uri'])
            wire=result.model_dump(mode='json',by_alias=True)
            save(OUT/'raw/resource-reads/immediate-read.json',dict(evidence_id=source['evidence_id'],
                uri=source['source_uri'],seconds=time.perf_counter()-start,wire=wire))
            print(json.dumps(wire,ensure_ascii=False,indent=2))


if __name__=='__main__':
    asyncio.run(main())
