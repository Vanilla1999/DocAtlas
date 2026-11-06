"""Explicitly prepare frozen catalogs through installed stdio; retain receipts."""
import argparse
import asyncio
import json
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from run import server_env, member_grant, payload_of


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-root', type=Path, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    for corpus in ('L0', 'L2'):
        root = args.prepared_root / (corpus + '-0')
        env = server_env(root, Path(__file__).resolve().parents[2], None, {})
        env.pop('PYTHONPATH', None)
        params = StdioServerParameters(command=str(args.executable), args=['mcp', 'docs-serve'], env=env, cwd=str(root))
        with (args.out / (corpus + '.stderr')).open('w') as stderr:
            async with stdio_client(params, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    cold, _ = payload_of(await session.call_tool('get_docs_context', {
                        'project_path': str(root / 'project'), 'question': 'Read project documentation.'}))
                    (args.out / (corpus + '-cold.json')).write_text(json.dumps(cold, indent=2))
                    if cold.get('reason_code') != 'member_store_uninitialized':
                        raise RuntimeError(f'Expected uninitialized store: {cold}')
                    prepared, _ = payload_of(await session.call_tool('prepare_docs', {
                        'action': 'sync_project_docs', 'project_path': str(root / 'project'),
                        'mutation': member_grant(root / 'project', cold['storage_path'])}))
                    (args.out / (corpus + '-prepare.json')).write_text(json.dumps(prepared, indent=2))
                    if prepared.get('status') != 'success':
                        raise RuntimeError(prepared)
                    print(corpus, 'prepared', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
