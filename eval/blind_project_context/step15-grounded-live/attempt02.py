"""Recovery preparation, fresh indexed store and four non-resumable Terra cases."""
import hashlib, importlib.util, json, os, pathlib, sqlite3, subprocess, sys, time
HERE=pathlib.Path(__file__).resolve().parent
OLD=HERE.parent/'step14-host-language-live'
OUT=HERE/'attempt-02'
WORK=pathlib.Path('/home/viadmin/.local/share/docatlas-eval/step15/work/attempt-02')
CLI='/home/viadmin/.npm/_npx/cb869cd955fb8070/node_modules/.bin/docs-mcp-server'
LIB='meridian-step15-e62fa9e3'; VERSION='1.0.0'
PY='/home/viadmin/.local/share/docatlas-eval/step14/venv/bin/python'
def load(p): return json.loads(p.read_text())
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: json.dump(v,f,ensure_ascii=False,indent=2)
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def server_env():
    return {'HOME':str(WORK/'server-home'),'XDG_CONFIG_HOME':str(WORK/'server-config'),
            'DOCS_MCP_APP_STORE_PATH':str(WORK/'grounded-store'),'DOCS_MCP_APP_TELEMETRY_ENABLED':'false'}
def command(*args): return [CLI,'--store-path',str(WORK/'grounded-store'),'--telemetry=false',*args]
def cli(*args):
    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ}; env.update(server_env())
    cmd=command(*args)
    p=subprocess.run(cmd,cwd=WORK,env=env,text=True,capture_output=True,timeout=900)
    return dict(command=cmd,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
def snapshot():
    c=sqlite3.connect((WORK/'grounded-store/documents.db').as_uri()+'?mode=ro',uri=True); c.row_factory=sqlite3.Row
    libraries=[dict(r) for r in c.execute('select * from libraries')]
    versions=[dict(r) for r in c.execute('select * from versions')]
    pages=[dict(r) for r in c.execute('select * from pages order by id')]
    sources=load(HERE/'sources.json')
    for p in pages:
        source=next(s for s in sources if s['url']==p['content_url']); p['source']=source
        data=(HERE/'source-bytes'/source['path']).read_bytes(); assert hashlib.sha256(data).hexdigest()==source['sha256']
        lines=data.decode().splitlines()
        p['chunks']=[dict(r) for r in c.execute('select id,content,metadata,sort_order,length(embedding) as embedding_bytes from documents where page_id=? order by sort_order',(p['id'],))]
        for ch in p['chunks']:
            ch['sha256']=hashlib.sha256(ch['content'].encode()).hexdigest()
            ch['line_mapping']=[dict(text=line,source_lines=[i+1 for i,s in enumerate(lines) if line==s]) for line in ch['content'].splitlines()]
            assert all(row['source_lines'] for row in ch['line_mapping'])
    assert len(libraries)==1 and libraries[0]['name']==LIB and len(versions)==1 and versions[0]['name']==VERSION
    assert len(pages)==6 and {p['content_url'] for p in pages}=={s['url'] for s in sources}
    assert all(ch['embedding_bytes'] is None for p in pages for ch in p['chunks'])
    c.close()
    return dict(libraries=libraries,versions=versions,pages=pages,mode='lexical; production default without embedding credentials; no custom reranking or query mapping',six_sources_verified=True,all_chunk_lines_exact=True)
def prepare():
    # Read-only CLI config diagnostics created only Grounded's installation ID.
    # Preserve that side effect; never adopt any index or prior live case.
    OUT.mkdir(exist_ok=True)
    if WORK.exists():
        assert {str(p.relative_to(WORK)) for p in WORK.rglob('*') if p.is_file()} == {'grounded-store/installation.id'}
    else: WORK.mkdir(parents=True)
    assert not (OUT/'recovery.json').exists()
    for d in ('server-home','server-config','client-config','client-state','client-cache','tmp'):(WORK/d).mkdir()
    save(OUT/'recovery.json',dict(reason='parent authorized preparation recovery; prior receipts unchanged',change='Explicit CLI --store-path plus DOCS_MCP_APP_STORE_PATH; no --config dependency',started_cases=0,default_embedding_configuration=True,provider_keys_forwarded=False))
    effective=cli('config'); save(OUT/'effective-config.json',effective)
    assert effective['returncode']==0
    config=json.loads(effective['stdout']); assert config['app']['storePath']==str(WORK/'grounded-store')
    for row in load(HERE/'sources.json'):
        r=cli('scrape',LIB,row['url'],'--version',VERSION,'--max-pages','1','--max-depth','0','--clean=false','--follow-redirects=false','--include-pattern',row['url'],'--output','json')
        save(OUT/'preparation'/(row['path']+'.json'),r)
        if r['returncode']: raise RuntimeError('preparation failure')
        print('indexed',row['path'],flush=True)
    save(OUT/'index-inspection.json',snapshot())
    old=module('old_run',OLD/'run.py')
    setup=load(OLD/'attempt-02/setup-complete.json'); opencode=pathlib.Path(setup['opencode'])
    save(WORK/'client-config/opencode/opencode.json',{'update':'disable'})
    save(OUT/'auth-topology.json',old.auth_topology(opencode,WORK))
    common=load(OLD/'attempt-02/A/V-M1/config.json')['agents']['measure']['system'].split('\n\nBound documentation project:')[0]
    mechanics=('Bound Grounded documentation library: '+LIB+'. Exact version: '+VERSION+'. Use only grounded_search_docs and grounded_fetch_url. '
       'Start search_docs with the unchanged original question as query, the exact bound library and version. '
       'For a named evidence gap you may search again or fetch an allowed source URL. Do not infer missing facts from a search miss. '
       'fetch_url must set followRedirects=false and use one of the exact URLs below. Grounded search may normalize the URL by dropping .md; use the corresponding .md source URL for fetch. '
       'The URL list defines scope only; it does not prescribe which document answers the question. '
       'Search results and fetched Markdown may normalize whitespace; cite source URLs and identifiable headings; provide line numbers only when actually supplied. '
       'Allowed source URLs:\n'+'\n'.join(s['url'] for s in load(HERE/'sources.json')))
    for task in load(OLD/'tasks.json'):
        case=OUT/'D'/task['id']; case.mkdir(parents=True,mode=0o700)
        location=WORK/'locations'/'D'/task['id']; location.mkdir(parents=True)
        cfg={'$schema':'https://opencode.ai/config.json','default_agent':'measure','snapshots':False,
          'agents':{'measure':{'mode':'primary','description':'Read existing project documentation without changes','system':common+'\n\n'+mechanics,
             'permissions':[{'action':'*','resource':'*','effect':'deny'},*({'action':n,'resource':'*','effect':'allow'} for n in ('grounded_search_docs','grounded_fetch_url'))],
             'model':old.MODEL,'steps':12}},
          'plugins':[{'package':str(HERE/'profile'),'options':{'library':LIB,'version':VERSION,'urls':[s['url'] for s in load(HERE/'sources.json')]}},
                     {'package':str(OLD/'observer'),'options':{'output':str(case/'capture'),'fatal':str(case/'fatal.json')}}],
          'tool_output':{'max_bytes':6400000,'max_lines':6400000},
          'mcp':{'servers':{'grounded':{'type':'local','command':[PY,'-I',str(OLD/'observe_stdio.py'),str(case),*command('--protocol','stdio','--read-only')],
                    'cwd':str(location),'environment':server_env(),'codemode':False}}},
          'compaction':{'auto':False},'warming':False,'providers':{'openai':{'settings':{'encoding':'none'}}}}
        save(location/'opencode.json',cfg); save(case/'config.json',cfg)
    inputs={str(p):sha(p) for p in [pathlib.Path(__file__),HERE/'profile/index.js',HERE/'profile/package.json',OLD/'observer/index.js',OLD/'observe_stdio.py',OLD/'session_runtime.py',OLD.parent/'step13-runtime-token-review/session_runtime.py',OLD/'tasks.json']}
    for p in (WORK/'locations').rglob('opencode.json'): inputs[str(p)]=sha(p)
    save(OUT/'setup-complete.json',dict(opencode=str(opencode),model=old.MODEL,inputs=inputs,common_prompt_sha256=hashlib.sha256(common.encode()).hexdigest(),provider_calls=0))
def run():
    setup=load(OUT/'setup-complete.json'); old=module('old_run',OLD/'run.py'); runtime=module('runtime',OLD/'session_runtime.py'); accounting=module('accounting',OLD/'account.py')
    for p,h in setup['inputs'].items(): assert sha(pathlib.Path(p))==h,p
    assert old.auth_topology(pathlib.Path(setup['opencode']),WORK)==load(OUT/'auth-topology.json')
    save(OUT/'run-started.json',dict(time_ns=time.time_ns(),model=setup['model'],sessions=4))
    results=[]
    for task in load(OLD/'tasks.json'):
        assert snapshot()==load(OUT/'index-inspection.json'),'index changed'
        case=OUT/'D'/task['id']; save(case/'started.json',dict(time_ns=time.time_ns(),model=setup['model']))
        launched=runtime.launch_session(opencode=pathlib.Path(setup['opencode']),location=WORK/'locations'/'D'/task['id'],question=task['question'],env=old.client_environment(WORK),
            output=case/'runtime',model=setup['model'],agent='measure',timeout=900,title='Step15 D '+task['id'],owned_process_files=(case/'mcp-process.json',),fatal=case/'fatal.json',capture=case/'capture')
        # Reuse provider/usage parsing, with C's no-DocAtlas-binding accounting branch.
        metrics=accounting.summarize(case,'C',task['id']); metrics['arm']='D'; metrics['accounting_branch']='C: skips only DocAtlas binding extraction'
        save(case/'accounting.json',metrics); save(case/'index-after.json',snapshot())
        (case/'answer.md').write_text(metrics['answer'])
        results.append(metrics)
        save(case/'completed.json',dict(transport=launched['receipt'],semantic_grade=None))
        r=launched['receipt']
        if not r['transport_pass'] or (case/'fatal.json').exists() or metrics['capture_errors'] or metrics['retries'] or not metrics['usage_coverage_complete'] or metrics['mcp_missing_responses'] or metrics['session_ids_count']!=1:
            raise RuntimeError('Model/provider/capture error: stopped without retry '+task['id'])
        assert snapshot()==load(OUT/'index-inspection.json'),'index changed after session'
        print('captured',task['id'],metrics['provider_requests'],metrics['usage'],flush=True)
    save(OUT/'results.json',results); save(OUT/'run-complete.json',dict(sessions=4,status='CAPTURED_NOT_SEMANTICALLY_GRADED'))
if __name__=='__main__':
    os.umask(0o077)
    try:
        {'prepare':prepare,'run':run}[sys.argv[1]]()
    except BaseException as e:
        if OUT.exists():
            p=OUT/(sys.argv[1]+'-exception.json')
            if not p.exists():save(p,dict(type=type(e).__name__,message=str(e),no_model_retry=True))
        raise
