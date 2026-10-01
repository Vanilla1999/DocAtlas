"""Predeclared same-meaning RU->EN question-only diagnostic, no lookup/gold."""
import asyncio
import json
from run_live_mcp import ROOT, OUT, WORK, save, call, env_for_server
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TRANSLATIONS={
    'projectA-Q05':'I need to understand the entire repository, including documentation of individual modules. Which search scope should I pass?',
    'projectA-Q07':'Which files does DocAtlas consider project documentation, and how can I see what it missed?',
    'projectA-Q09':'After changing a Markdown file, the agent cites old text. How should I update the index and repeat the question?',
    'projectA-Q11':'When do I need refresh and when sync_project_docs? I keep confusing updating a library with updating my own repository.',
    'projectA-Q23':'Is estimated_tokens the exact token count of my model? How is the actual size of docs_context limited?',
    'projectA-Q25':'MCP returned docs_context, but answer_available=false. May the agent still answer the user from these snippets?',
    'projectA-Q29':'May text inside README be treated as an instruction to an agent if it says to ignore previous instructions?',
    'projectB-Q03':'There are citations in the result, but answer_supported=false. May I explain what was found to the user?',
    'projectB-Q17':'The original file changed between retrieval and further reading. What should the reader return?',
    'projectB-Q23':'Two projects have the same README.md. How do I avoid a citation from another project?'
}


async def main():
    originals={r['id']:r for r in json.loads((OUT/'raw/project80/results.json').read_text()) if r['lane']=='all'}
    save(OUT/'raw/translation10/protocol.json',dict(note='Frozen before running these translations. Same question needs/identifiers, no answer values or extra lookup calls. Hand-selected exposed diagnostic, not language-randomized holdout.',cases=[dict(id=id_,original=originals[id_]['question'],translation=text) for id_,text in TRANSLATIONS.items()]))
    params=StdioServerParameters(command='/home/viadmin/.local/bin/doc-atlas',args=['mcp','docs-serve'],env=env_for_server(),cwd=str(WORK))
    rows=[]
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as session:
            await session.initialize()
            for id_,text in TRANSLATIONS.items():
                args=dict(question=text,project_path=str(ROOT),scope='all')
                record,payload=await call(session,'get_docs_context',args,OUT/'raw/translation10/native'/f'{id_}.json')
                rows.append(dict(id=id_,request=args,payload=payload,seconds=record['seconds']))
                save(OUT/'raw/translation10/results.json',rows)
                print(id_,payload['status'],[(s['path_or_url'],s['snippet']) for s in payload.get('sources',[])],flush=True)


if __name__=='__main__':
    asyncio.run(main())
