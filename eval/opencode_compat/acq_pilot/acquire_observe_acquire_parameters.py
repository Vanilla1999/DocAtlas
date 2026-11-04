import hashlib,json,os,time
from pathlib import Path
R=Path('/tmp/opencode/acq-pilot'); corpus='L0'
os.environ.update(DOCATLAS_HOME='/home/viadmin/.local/share/docatlas-acq-pilot/L0/docatlas-home',DOCATLAS_CONTEXT_COMPRESSION='off',DOCATLAS_MCP_MODEL_VIEW='off',DOCATLAS_MCP_COMPACT_TEXT='1',DOCATLAS_TRACE='0',DOCATLAS_EXPERIMENT_JOINT_RELEVANCE='off',DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0',DOCATLAS_MCP_TEXT_FALLBACK='1',NO_PROXY='*',HF_HUB_OFFLINE='1',TIKTOKEN_CACHE_DIR=str(R/'tiktoken-cache'))
from docmancer.core.member_read_store import MemberReadStore
from docmancer.mcp._docs_server_part01 import create_local_mcp_service,call_docs_tool_payload
events=[]; original=MemberReadStore.acquire_candidates
def observer(self,text,*,expand=None,filters=None):
    start=time.perf_counter(); rows=original(self,text,expand=expand,filters=filters)
    events.append({'text':text,'expand':expand,'filters':filters,'count':len(rows),'seconds':time.perf_counter()-start,'ordered_section_ids':[x.metadata.get('section_id') for x in rows],'acquisition':rows[0].metadata.get('acquisition') if rows else None})
    return rows
MemberReadStore.acquire_candidates=observer
q=json.loads(Path('/home/viadmin/StudioProjects/DocAtlas/eval/opencode_compat/acq_pilot/oracle.json').read_text())['questions'][0]
args={'project_path':'/tmp/opencode/semantic-signal-experiment/project','question':q['question'],'search_question':q['search_question'],'scope':'project'}
payload=call_docs_tool_payload('get_docs_context',args,create_local_mcp_service())
out={'scope':'separate read-only in-process P1 parameter observation; wrapper preserves returned production objects','args':args,'events':events,'payload_sha256':hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
path=R/'acquire-observed-L0-v0-P1.json'; assert not path.exists();path.write_text(json.dumps(out,ensure_ascii=False,indent=2))
print([(x['expand'],x['count']) for x in events],flush=True)
