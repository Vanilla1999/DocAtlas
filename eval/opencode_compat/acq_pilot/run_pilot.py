import asyncio,hashlib,json,os,sqlite3,sys,time,traceback
from pathlib import Path
sys.path.append('/home/viadmin/StudioProjects/DocAtlas')
from eval.opencode_compat.installed_stdio import environment,prepared_mutation,source_rows
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
import tiktoken

R=Path('/tmp/opencode/acq-pilot'); home=Path('/home/viadmin/.local/share/docatlas-acq-pilot')
home.mkdir(mode=0o700,exist_ok=True)
old=Path('/tmp/opencode/semantic-signal-experiment')
projects={'L0':old/'project','L2':R/'L2-project'}
oracle=json.loads(Path('/home/viadmin/StudioProjects/DocAtlas/eval/opencode_compat/acq_pilot/oracle.json').read_text())
os.environ['TIKTOKEN_CACHE_DIR']=str(R/'tiktoken-cache'); enc=tiktoken.get_encoding('cl100k_base')
def env_for(corpus,variant='v0',trace='1'):
    (R/('env-'+corpus)).mkdir(exist_ok=True)
    env=environment(R/('env-'+corpus)); env['DOCATLAS_HOME']=str(home/corpus/'docatlas-home')
    (home/corpus).mkdir(mode=0o700,exist_ok=True); (home/corpus).chmod(0o700)
    Path(env['DOCATLAS_HOME']).mkdir(mode=0o700,exist_ok=True); Path(env['DOCATLAS_HOME']).chmod(0o700)
    env.update(DOCATLAS_CONTEXT_COMPRESSION='off',DOCATLAS_MCP_MODEL_VIEW='off',DOCATLAS_MCP_COMPACT_TEXT='1',DOCATLAS_TRACE=trace,DOCATLAS_EXPERIMENT_JOINT_RELEVANCE='off',TIKTOKEN_CACHE_DIR=str(R/'tiktoken-cache'))
    if variant is not None: env['DOCATLAS_EXPERIMENT_ACQUISITION']=variant
    return env
def params(env):
    return StdioServerParameters(command=str(R/'venv/bin/python'),args=['-I','-m','docmancer.cli','mcp','docs-serve'],env=env,cwd=str(R))
def setup_l0():
    env=env_for('L0'); store=Path(env['DOCATLAS_HOME'])/'mcp-members/members.db'; store.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    source=Path('/home/viadmin/.local/share/docatlas-semantic-signal-experiment/docatlas-home/mcp-members/members.db')
    if not store.exists():
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(store) as dst: src.backup(dst)
        store.chmod(0o600)
    from docmancer.core.member_storage_policy import MemberStoragePolicy
    policy=MemberStoragePolicy(Path(env['DOCATLAS_HOME']),store)
    policy.marker.write_text(json.dumps(policy._ownership(store.stat()))); policy.marker.chmod(0o600)
    from unittest.mock import patch
    from docmancer.mcp._docs_server_part01 import create_local_mcp_service
    with patch.dict(os.environ,env,clear=True): policy=create_local_mcp_service().member_storage_policy
    assert policy.validate(projects['L0'])
    return store
async def prepare_l2():
    env=env_for('L2'); mutation,store=prepared_mutation(env,projects['L2'])
    with (R/'L2-prepare.stderr').open('w') as err:
        async with stdio_client(params(env),errlog=err) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                reply=await session.call_tool('prepare_docs',{'action':'sync_project_docs','project_path':str(projects['L2']),'mutation':mutation})
                (R/'L2-prepare.json').write_text(reply.model_dump_json(indent=2))
                data=json.loads(reply.content[0].text)
                print('prepare',data.get('status'),data.get('reason_code'),flush=True)
                if data.get('status')!='success': raise RuntimeError('L2 prepare failed: '+str(data))
    return store
async def batch(corpus,variant,trace='1',only=None,label=None):
    env=env_for(corpus,variant,trace); project=projects[corpus]; name=label or f'{corpus}-{variant}'
    catalog={e.path:e for e in read_project_docs_catalog(project).entries}
    identity='local:'+hashlib.sha256(str(project.resolve()).encode()).hexdigest()
    with (R/(name+'.stderr')).open('w') as err:
        async with stdio_client(params(env),errlog=err) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                for i,q in enumerate(oracle['questions'] if only is None else [oracle['questions'][only]]):
                    args={'project_path':str(project),'question':q['question'],'search_question':q['search_question'],'scope':'project'}
                    t=time.perf_counter(); reply=await session.call_tool('get_docs_context',args); elapsed=time.perf_counter()-t
                    stem=R/(name+'-'+q['id']); stem.with_suffix('.reply.json').write_text(reply.model_dump_json(indent=2))
                    text=reply.content[0].text; stem.with_suffix('.payload.json').write_text(text)
                    data=json.loads(text); rows=source_rows(data); checks=[]
                    for row in rows:
                        try:
                            p=row['path_or_url']; e=catalog[p]; data_bytes=(project/p).read_bytes(); lines=data_bytes.decode().splitlines(keepends=True)
                            checks.append({'path':p,'source_sha256':hashlib.sha256(data_bytes).hexdigest(),'line_start':row['line_start'],'line_end':row['line_end'],'identity_ok':row['project_identity']==identity,'scope_ok':row['scope']==e.scope,'authority_ok':row['authority']==e.authority,'version_ok':row['version_binding']=='unversioned','span_text_ok':row['snippet'] in ''.join(lines[row['line_start']-1:row['line_end']]),'metadata':row})
                        except Exception as exc: checks.append({'error':repr(exc),'row':row})
                    result={'seconds':elapsed,'temperature':'cold_process' if i==0 else 'warm_process','isError':reply.isError,'status':data.get('status'),'raw_cl100k_tokens':len(enc.encode(text,disallowed_special=())),'bytes':len(text.encode()),'source_checks':checks,'arguments':args}
                    stem.with_suffix('.metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)); print(name,q['id'],elapsed,data.get('status'),flush=True)
async def main():
    l0=setup_l0(); print('L0',l0,flush=True)
    l2=await prepare_l2(); print('L2',l2,flush=True)
    for corpus,variant in [('L0','v0'),('L0','v5'),('L2','v5'),('L2','v0')]: await batch(corpus,variant)
    await batch('L0','v5','0',0,'L0-v5-traceoff')
    await batch('L0',None,'1',0,'L0-default')
asyncio.run(main())
