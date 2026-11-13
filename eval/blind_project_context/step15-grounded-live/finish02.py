"""Continue only not-started cases; fix legacy DocAtlas-only retrieval classifier."""
import importlib.util, pathlib, os, time
HERE=pathlib.Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r',HERE/'attempt02.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
OUT=r.OUT/'live-02'
def classify(case):
    receipt=r.load(case/'runtime/receipt.json');m=r.load(case/'accounting.json')
    checks=dict(session_finished=receipt['session_status']=='finished',answer_produced=receipt['answer_status']=='produced',exit_zero=receipt['returncode']==0,
       not_terminated=receipt['termination'] is None,no_failures=not receipt['failures'],no_capture_errors=not receipt['capture_errors'] and not m['capture_errors'],
       capture_completed=receipt['provider_capture_completed_before_cleanup'],cleanup=receipt['cleanup']['no_live_owned_processes'] and receipt['cleanup']['leader_reaped'],
       no_fatal=not (case/'fatal.json').exists(),no_retries=m['retries']==0,usage_complete=m['usage_coverage_complete'],single_session=m['session_ids_count']==1,
       responses_complete=m['mcp_missing_responses']==0,original_question=m['original_question_in_first_request'],
       grounded_retrieval=m['actual_mcp_calls'].get('search_docs',0)>0,
       allowed_tools_only=set(m['model_tool_calls']) <= {'grounded_search_docs','grounded_fetch_url'})
    r.save(case/'grounded-transport-verification.json',dict(checks=checks,transport_pass=all(checks.values()),legacy_receipt_unchanged=True,
       boundary='Legacy classifier counts only DocAtlas/files retrieval names. Grounded retrieval independently verified from actual stdio calls; no model rerun or semantic grade.'))
    return all(checks.values())
def main():
    tasks=r.load(r.OLD/'tasks.json');setup=r.load(OUT/'setup-complete.json')
    for p,h in setup['inputs'].items():assert r.sha(pathlib.Path(p))==h,p
    assert classify(OUT/'D'/tasks[0]['id'])
    r.save(OUT/'classifier-recovery.json',dict(reason='V-M1 finished successfully with 3 provider responses and 2 real Grounded calls; historical classifier only recognizes DocAtlas/files tool names',model_errors=0,provider_errors=0,repeated_cases=[],remaining=[t['id'] for t in tasks[1:]],script_sha256=r.sha(pathlib.Path(__file__))))
    old=r.module('old_run',r.OLD/'run.py');runtime=r.module('runtime',r.OLD/'session_runtime.py');account=r.module('account',r.OLD/'account.py')
    assert old.auth_topology(pathlib.Path(setup['opencode']),r.WORK)==r.load(r.OUT/'auth-topology.json')
    for task in tasks[1:]:
        assert r.snapshot()==r.load(r.OUT/'index-inspection.json')
        case=OUT/'D'/task['id'];r.save(case/'started.json',dict(time_ns=time.time_ns(),model=setup['model']))
        runtime.launch_session(opencode=pathlib.Path(setup['opencode']),location=r.WORK/'locations/live-02/D'/task['id'],question=task['question'],env=old.client_environment(r.WORK),
            output=case/'runtime',model=setup['model'],agent='measure',timeout=900,title='Step15 D '+task['id'],owned_process_files=(case/'mcp-process.json',),fatal=case/'fatal.json',capture=case/'capture')
        m=account.summarize(case,'C',task['id']);m['arm']='D';m['accounting_branch']='C: skip only DocAtlas binding extraction'
        r.save(case/'accounting.json',m);r.save(case/'index-after.json',r.snapshot());(case/'answer.md').write_text(m['answer'])
        if not classify(case):raise RuntimeError('Session failed; no retry '+task['id'])
        assert r.snapshot()==r.load(r.OUT/'index-inspection.json')
        print('captured',task['id'],m['provider_requests'],m['usage'],flush=True)
    r.save(OUT/'results.json',[r.load(OUT/'D'/t['id']/'accounting.json') for t in tasks])
    r.save(OUT/'run-complete.json',dict(sessions=4,status='CAPTURED_NOT_SEMANTICALLY_GRADED',model_retries=0))
if __name__=='__main__':
    os.umask(0o077)
    try:main()
    except BaseException as e:
        r.save(OUT/'finish-exception.json',dict(type=type(e).__name__,message=str(e)));raise
