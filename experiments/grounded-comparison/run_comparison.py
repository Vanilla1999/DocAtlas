"""Fixed-source no-LLM comparison; witness labels never enter retrieval."""
from __future__ import annotations
import argparse, asyncio, hashlib, json, os, re, subprocess, sys, time
from collections import defaultdict
from pathlib import Path
from datetime import timedelta

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str)+'\n')

def sha(b): return hashlib.sha256(b).hexdigest()

def sectionize(text, group, version, path):
    """Heading boundaries outside fences; lists/tables/code are not cut."""
    lines=text.splitlines(keepends=True); starts=[0]; contexts={0: []}; stack=[]; fence=None
    for i,line in enumerate(lines):
        m=re.match(r'^\s*(`{3,}|~{3,})',line)
        if m:
            mark=m.group(1)[0]
            if fence is None: fence=mark
            elif fence == mark: fence=None
            continue
        if fence: continue
        h=re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$',line)
        if h:
            level=len(h[1]); stack=[(n,t) for n,t in stack if n<level]; stack.append((level,h[2]))
            if i not in starts: starts.append(i)
            contexts[i]=[t for _,t in stack]
    result={}; mapping={}
    for n,(a,b) in enumerate(zip(starts,starts[1:]+[len(lines)])):
        body=''.join(lines[a:b])
        if not body.strip(): continue
        rel=f'{path}.section-{n:04}.md'
        prefix=f'Library: {group}\nVersion: {version}\nSource: {path}\nHeading context: '+ ' > '.join(contexts.get(a,[]))+'\n\n'
        result[rel]=prefix+body
        mapping[rel]={'original_path':path,'line_start':a+1,'line_end':b,'prefix':prefix,'original_body':body}
    return result,mapping

def command(args, env, cwd, out, timeout=180):
    t=time.perf_counter()
    try:
        p=subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True,timeout=timeout)
        rec={'command':args,'exit_code':p.returncode,'seconds':time.perf_counter()-t,'stdout':p.stdout,'stderr':p.stderr}
    except subprocess.TimeoutExpired as e:
        rec={'command':args,'error':'timeout','seconds':time.perf_counter()-t,'stdout':str(e.stdout),'stderr':str(e.stderr)}
    save(out,rec)
    if rec.get('exit_code') != 0: raise RuntimeError(f'command failed: {out}')
    return rec

async def grounded_queries(cli, cfg, rows, env, out):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    server=StdioServerParameters(command='node',args=[str(cli),'--config',str(cfg),'--protocol','stdio','--read-only'],env=env)
    with (out/'grounded-stderr.log').open('w') as err:
        async with stdio_client(server, errlog=err) as (r,w):
            async with ClientSession(r,w) as session:
                await session.initialize()
                save(out/'grounded-tools.json',(await session.list_tools()).model_dump(mode='json'))
                for row in rows:
                    args={'library':row['group'],'version':row['version'],'query':row['question']}
                    t=time.perf_counter()
                    try:
                        result=await session.call_tool('search_docs',args,read_timeout_seconds=timedelta(seconds=60))
                        rec={**row,'arguments':args,'seconds':time.perf_counter()-t,'response':result.model_dump(mode='json')}
                    except Exception as e: rec={**row,'arguments':args,'error':repr(e)}
                    save(out/'grounded'/f"{row['id']}.json",rec)
                    print('grounded',out.name,row['id'],'ERROR' if rec.get('error') else 'done',flush=True)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--repo',type=Path,required=True); p.add_argument('--grounded',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); root=a.repo.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(root))
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from docmancer.mcp.docs_server import call_docs_tool_payload
    casepath=root/'eval/evidence_quality_v2/cases.json'; mpath=root/'eval/evidence_quality_v2/source-manifest.json'
    cases=json.loads(casepath.read_text())['cases']; manifest=json.loads(mpath.read_text())['sources']
    save(out/'protocol.json',{'docatlas_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'grounded_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.grounded,text=True).strip(),
        'cases_sha256':sha(casepath.read_bytes()),'manifest_sha256':sha(mpath.read_bytes()),
        'cases':len(cases),'embeddings':'disabled/unconfigured for BOTH; lexical-only comparison',
        'views':['original','sectionized'],'queries':'exact case questions; no lookup_queries; no answer labels',
        'grounded_limit':'default 5 results','docatlas_budget':'unchanged native 800, max 3 sources',
        'execution':'DocAtlas public handler and real SQLite; Grounded real stdio MCP',
        'timing_comparability':'NOT comparable end-to-end: handler vs stdio',
        'section_transform':'Query-independent heading splits; inherited headings and library/version/source prefix; no paraphrase or gold',
        'scoring':'external post-run same witnesses; manual review for eight known cases; raw defaults and common-budget sensitivity reported separately',
        'model_answers':'NOT_MEASURED'})
    save(out/'cases.json',cases); save(out/'source-manifest.json',manifest)
    documents=defaultdict(dict); versions={}
    for m in manifest:
        b=(root/'eval/evidence_quality_v2/sources'/m['project']/m['path']).read_bytes()
        assert sha(b)==m['sha256'],m['path']
        documents[m['project']][m['path']]=b.decode(); versions[m['project']]=m['ref']
        f=out/'original-source'/m['project']/m['path']; f.parent.mkdir(parents=True,exist_ok=True); f.write_bytes(b)
    questions=[{'id':c['id'],'group':c['project_group'],'version':versions[c['project_group']],'question':c['question'],'answerability':c['answerability']} for c in cases]
    translations={'fastapi-02':'Can a task function for BackgroundTasks be a regular def rather than async def?',
      'fastapi-06':'What components make up an origin in CORS?',
      'httpx-03':'Name the four types of timeout in HTTPX and explain what each one limits.',
      'pydantic-03':'List the ways to enable strict mode, including field, annotation, config and validation call.',
      'typer-05':'How do you specify only the negative name of a boolean option: does the space before / matter?'}
    for cid,q in translations.items(): questions.append({**next(x for x in questions if x['id']==cid),'id':cid+'-en','question':q,'translation_of':cid})
    save(out/'queries.json',questions)
    for view in ['original','sectionized']:
        vout=out/view; vout.mkdir(); rawroot=vout/'grounded-input'; rawroot.mkdir()
        prepared={}; mappings={}
        for group,docs in documents.items():
            new={}; maps={}
            for path,text in docs.items():
                if view=='sectionized':
                    d,mm=sectionize(text,group,versions[group],path); new.update(d); maps.update(mm)
                else:
                    new[path]=text; maps[path]={'original_path':path,'line_start':1,'line_end':len(text.splitlines()),'prefix':'','original_body':text}
            prepared[group]=new; mappings[group]=maps
            for path,text in new.items():
                f=rawroot/group/path; f.parent.mkdir(parents=True,exist_ok=True); f.write_text(text)
        save(vout/'source-map.json',mappings)
        for group,docs in prepared.items():
            project=vout/'docatlas-input'/group; write_project(project,docs)
            with isolated_service(vout/'docatlas-state'/group) as (svc,config):
                inv=index_project(svc,config,project); save(vout/'docatlas-index'/f'{group}.json',inv)
                if inv['excluded_or_failed_paths'] or inv['unexpected_paths']: raise RuntimeError('DocAtlas source coverage mismatch')
                for row in (x for x in questions if x['group']==group):
                    args={'question':row['question'],'project_path':str(project),'scope':'all'}
                    t=time.perf_counter()
                    try: rec={**row,'arguments':args,'response':call_docs_tool_payload('get_docs_context',args,svc),'seconds':time.perf_counter()-t}
                    except Exception as e: rec={**row,'arguments':args,'error':repr(e)}
                    save(vout/'docatlas'/f"{row['id']}.json",rec)
                    print('docatlas',view,row['id'],'ERROR' if rec.get('error') else 'done',flush=True)
        config={'app':{'storePath':str(vout/'grounded-store'),'telemetryEnabled':False},'scraper':{'security':{'fileAccess':{'mode':'allowedRoots','allowedRoots':[str(rawroot)],'followSymlinks':False,'includeHidden':False}}}}
        cfg=vout/'grounded-config.json'; save(cfg,config)
        env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['API_KEY','ACCESS_TOKEN','GITHUB_TOKEN','AZURE_','AWS_','GOOGLE_APPLICATION_CREDENTIALS'])}
        env.update(DOCS_MCP_APP_TELEMETRY_ENABLED='false',NO_COLOR='1',HOME=str(vout/'grounded-home'))
        Path(env['HOME']).mkdir()
        cli=a.grounded.resolve()/'dist/index.js'
        for group in prepared:
            command(['node',str(cli),'--config',str(cfg),'scrape',group,(rawroot/group).as_uri(),'--version',versions[group],'--max-depth','20'],env,a.grounded,vout/'grounded-index'/f'{group}.json')
        command(['node',str(cli),'--config',str(cfg),'list','--output','json'],env,a.grounded,vout/'grounded-library-list.json')
        asyncio.run(grounded_queries(cli,cfg,questions,env,vout))
    save(out/'completion.json',{'status':'COMPLETE','expected_records_per_product_view':len(questions)})

if __name__=='__main__': main()
