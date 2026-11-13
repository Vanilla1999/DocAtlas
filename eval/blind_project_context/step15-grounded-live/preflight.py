"""No-provider MCP connectivity and source delivery check, outside model context."""
import asyncio, importlib.util, json, os
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('runner',HERE/'attempt02.py'); r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
async def main():
    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ};env.update(r.server_env())
    with (r.OUT/'preflight.stderr.log').open('x') as stderr:
      async with stdio_client(StdioServerParameters(command=r.CLI,args=r.command('--protocol','stdio','--read-only')[1:],cwd=str(r.WORK),env=env),errlog=stderr) as (read,write):
       async with ClientSession(read,write) as session:
        r.save(r.OUT/'preflight-init.json',(await session.initialize()).model_dump(mode='json'))
        tools=await session.list_tools();r.save(r.OUT/'preflight-tools.json',tools.model_dump(mode='json'))
        assert {'search_docs','fetch_url'} <= {t.name for t in tools.tools}
        calls=[('list_libraries',{})]
        calls += [('fetch_url',dict(url=s['url'],followRedirects=False)) for s in r.load(HERE/'sources.json')]
        for i,(name,args) in enumerate(calls):
            result=await session.call_tool(name,args)
            r.save(r.OUT/'preflight-calls'/f'{i:02d}.json',dict(name=name,arguments=args,result=result.model_dump(mode='json')))
            assert not result.isError,(name,args)
    r.save(r.OUT/'preflight-complete.json',dict(provider_calls=0,real_mcp_calls=len(calls),model_context_contains_preflight_results=False))
asyncio.run(main())
