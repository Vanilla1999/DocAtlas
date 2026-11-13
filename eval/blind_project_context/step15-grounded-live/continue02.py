"""Four fresh Locations after proven pre-provider readiness failure. No model retry."""
import importlib.util, json, os, pathlib, sys, time
HERE=pathlib.Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r',HERE/'attempt02.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
OUT=r.OUT/'live-02'
def prepare():
    assert r.load(r.OUT/'D/V-M1/accounting.json')['provider_requests']==0
    assert r.load(r.OUT/'D/V-M1/runtime/receipt.json')['cleanup']['no_live_owned_processes']
    OUT.mkdir(exist_ok=False)
    r.save(OUT/'recovery.json',dict(reason='Grounded startup takes 23.9s in real observer transport; prior 10s readiness guard fired before any provider request',prior_provider_requests=0,prior_model_tool_calls=0,change='readiness 10s to 60s; MCP startup timeout 60s; four new locations; all model criteria and prompts unchanged',transport_probe=str(r.OUT/'transport-probe/complete.json')))
    setup=r.load(r.OUT/'setup-complete.json')
    for task in r.load(r.OLD/'tasks.json'):
        case=OUT/'D'/task['id'];case.mkdir(parents=True,mode=0o700)
        location=r.WORK/'locations/live-02/D'/task['id'];location.mkdir(parents=True)
        config=r.load(r.OUT/'D'/task['id']/'config.json')
        config['plugins'][0]['package']=str(HERE/'profile-ready60')
        config['plugins'][1]['options']=dict(output=str(case/'capture'),fatal=str(case/'fatal.json'))
        server=config['mcp']['servers']['grounded'];server['command'][3]=str(case);server['cwd']=str(location)
        server['timeout']={'startup':60000,'catalog':30000}
        r.save(case/'config.json',config);r.save(location/'opencode.json',config)
    inputs={str(p):r.sha(p) for p in [pathlib.Path(__file__),HERE/'attempt02.py',HERE/'profile-ready60/index.js',HERE/'profile-ready60/package.json',r.OLD/'observer/index.js',r.OLD/'observe_stdio.py',r.OLD/'session_runtime.py',r.OLD.parent/'step13-runtime-token-review/session_runtime.py',r.OLD/'tasks.json']}
    for p in (r.WORK/'locations/live-02').rglob('opencode.json'):inputs[str(p)]=r.sha(p)
    r.save(OUT/'setup-complete.json',dict(opencode=setup['opencode'],model=setup['model'],inputs=inputs,timeout=900,max_steps=12))
def run():
    setup=r.load(OUT/'setup-complete.json');old=r.module('old_run',r.OLD/'run.py');runtime=r.module('runtime',r.OLD/'session_runtime.py');account=r.module('account',r.OLD/'account.py')
    for p,h in setup['inputs'].items():assert r.sha(pathlib.Path(p))==h,p
    assert old.auth_topology(pathlib.Path(setup['opencode']),r.WORK)==r.load(r.OUT/'auth-topology.json')
    r.save(OUT/'run-started.json',dict(time_ns=time.time_ns(),model=setup['model'],sessions=4))
    results=[]
    for task in r.load(r.OLD/'tasks.json'):
        assert r.snapshot()==r.load(r.OUT/'index-inspection.json')
        case=OUT/'D'/task['id'];r.save(case/'started.json',dict(time_ns=time.time_ns(),model=setup['model']))
        launched=runtime.launch_session(opencode=pathlib.Path(setup['opencode']),location=r.WORK/'locations/live-02/D'/task['id'],question=task['question'],env=old.client_environment(r.WORK),
            output=case/'runtime',model=setup['model'],agent='measure',timeout=900,title='Step15 D '+task['id'],owned_process_files=(case/'mcp-process.json',),fatal=case/'fatal.json',capture=case/'capture')
        m=account.summarize(case,'C',task['id']);m['arm']='D';m['accounting_branch']='C: skip only DocAtlas binding extraction'
        r.save(case/'accounting.json',m);r.save(case/'index-after.json',r.snapshot());(case/'answer.md').write_text(m['answer']);results.append(m)
        if not launched['receipt']['transport_pass'] or (case/'fatal.json').exists() or m['capture_errors'] or m['retries'] or not m['usage_coverage_complete'] or m['mcp_missing_responses'] or m['session_ids_count']!=1:
            raise RuntimeError('Model/provider/capture failure; no retry: '+task['id'])
        assert r.snapshot()==r.load(r.OUT/'index-inspection.json')
        print('captured',task['id'],m['provider_requests'],m['usage'],flush=True)
    r.save(OUT/'results.json',results);r.save(OUT/'run-complete.json',dict(sessions=4,status='CAPTURED_NOT_SEMANTICALLY_GRADED'))
if __name__=='__main__':
    os.umask(0o077)
    try: {'prepare':prepare,'run':run}[sys.argv[1]]()
    except BaseException as e:
        if OUT.exists():
            p=OUT/(sys.argv[1]+'-exception.json')
            if not p.exists():r.save(p,dict(type=type(e).__name__,message=str(e),no_model_retry=True))
        raise
