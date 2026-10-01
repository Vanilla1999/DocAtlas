"""Reproduce cleanup cache lifetime and empty-index recovery on owned fixtures."""
import asyncio
import json
from run_live_mcp import OUT, WORK, save, call, env_for_server
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    project=WORK/'lifecycle-fixture'
    project.mkdir(parents=True,exist_ok=True)
    (project/'README.md').write_text('# DocAtlas\n\nUse prepare_docs with action=sync_project_docs to index local project documentation.\n')
    (project/'docatlas.yaml').write_text('index:\n  provider: sqlite\n  db_path: .docatlas/docatlas.db\n  extracted_dir: .docatlas/extracted\n')
    params=StdioServerParameters(command='/home/viadmin/.local/bin/doc-atlas',args=['mcp','docs-serve'],env=env_for_server(),cwd=str(WORK))
    async def execute_sequence(restart=False):
        with (OUT/'raw/lifecycle'/('probe-restart-stderr.log' if restart else 'probe-stderr.log')).open('w') as errors:
            async with stdio_client(params,errlog=errors) as (r,w):
                async with ClientSession(r,w) as session:
                    await session.initialize()
                    if not restart:
                        await call(session,'get_docs_context',dict(question='How do I prepare local project documentation?',project_path=str(project),scope='all'),OUT/'raw/lifecycle/probe-empty-index-query.json')
                    await call(session,'prepare_docs',dict(action='sync_project_docs',project_path=str(project),with_vectors=False),OUT/'raw/lifecycle'/('probe-restart-sync.json' if restart else 'probe-first-sync.json'))
                    if restart:
                        return
                    _,preview=await call(session,'prepare_docs',dict(action='clear_index',project_path=str(project),scope='project-local'),OUT/'raw/lifecycle/probe-clear-preview.json')
                    await call(session,'prepare_docs',dict(**preview['arguments_patch'],allow_incomplete=True),OUT/'raw/lifecycle/probe-clear-apply.json')
                    _,after=await call(session,'prepare_docs',dict(action='sync_project_docs',project_path=str(project),with_vectors=False),OUT/'raw/lifecycle/probe-after-clear-sync.json')
                    print(json.dumps(after,ensure_ascii=False,indent=2))
    await execute_sequence()
    await execute_sequence(restart=True)


if __name__=='__main__':
    asyncio.run(main())
