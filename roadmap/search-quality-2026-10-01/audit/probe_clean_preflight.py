"""Fresh committed clean fixture: preparation recovery before any indexing."""
import asyncio
import json
import subprocess
from run_live_mcp import OUT, WORK, save, call, env_for_server
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root=WORK/'clean-preflight-fixture'
    root.mkdir(parents=True,exist_ok=True)
    if (root/'.git').exists():
        raise RuntimeError('One-shot fixture already exists; refusing changed reproduction')
    (root/'README.md').write_text('# Local project documentation\n\nUse prepare_docs(action="sync_project_docs") to index repository docs before retrieval.\n')
    (root/'docatlas.yaml').write_text('index:\n  provider: sqlite\n  db_path: .docatlas/docatlas.db\n  extracted_dir: .docatlas/extracted\n')
    (root/'.gitignore').write_text('.docatlas/\n')
    for command in [['git','init','-q'],['git','add','README.md','docatlas.yaml','.gitignore'],
                    ['git','-c','user.name=Audit Fixture','-c','user.email=audit@example.invalid','commit','-qm','Freeze local documentation fixture']]:
        subprocess.run(command,cwd=root,check=True)
    status=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
    assert not status
    save(OUT/'raw/lifecycle/clean-fixture-state.json',dict(root=str(root),git_status=status,
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()))
    params=StdioServerParameters(command='/home/viadmin/.local/bin/doc-atlas',args=['mcp','docs-serve'],env=env_for_server(),cwd=str(WORK))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            await call(session,'docs_status',dict(action='project',project_path=str(root),details=True),OUT/'raw/lifecycle/clean-fixture-status.json')
            _,payload=await call(session,'get_docs_context',dict(question='How do I prepare local project documentation?',project_path=str(root),scope='all'),OUT/'raw/lifecycle/clean-fixture-query.json')
            print(json.dumps(payload,ensure_ascii=False,indent=2))


if __name__=='__main__':
    asyncio.run(main())
