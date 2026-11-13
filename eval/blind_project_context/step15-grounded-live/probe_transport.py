"""Reproduce observer transport startup without any model request."""
import asyncio, datetime, importlib.util, json, os, time
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r',HERE/'attempt02.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
async def main():
    root=r.OUT/'transport-probe';root.mkdir(mode=0o700)
    old=r.module('old_run',r.OLD/'run.py');env=old.client_environment(r.WORK);env.update(r.server_env())
    start=time.monotonic()
    with (root/'client.stderr').open('x') as stderr:
      async with stdio_client(StdioServerParameters(command=r.PY,args=['-I',str(r.OLD/'observe_stdio.py'),str(root),*r.command('--protocol','stdio','--read-only')],cwd=str(r.WORK/'locations/D/V-M1'),env=env),errlog=stderr) as (read,write):
       async with ClientSession(read,write,read_timeout_seconds=datetime.timedelta(seconds=90)) as session:
        init=await session.initialize();r.save(root/'init.json',init.model_dump(mode='json'))
        r.save(root/'tools.json',(await session.list_tools()).model_dump(mode='json'))
        r.save(root/'complete.json',dict(seconds=time.monotonic()-start,provider_requests=0))
asyncio.run(main())
