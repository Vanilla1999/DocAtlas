import json,os,sys,time
from pathlib import Path
R=Path('/tmp/opencode/acq-pilot'); corpus=sys.argv[1]; variant=os.environ['DOCATLAS_EXPERIMENT_ACQUISITION']
os.environ.update(DOCATLAS_HOME=str(Path('/home/viadmin/.local/share/docatlas-acq-pilot')/corpus/'docatlas-home'),DOCATLAS_CONTEXT_COMPRESSION='off',DOCATLAS_MCP_MODEL_VIEW='off',DOCATLAS_MCP_COMPACT_TEXT='1',DOCATLAS_TRACE='0',DOCATLAS_EXPERIMENT_JOINT_RELEVANCE='off',DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0',DOCATLAS_MCP_TEXT_FALLBACK='1',NO_PROXY='*',HF_HUB_OFFLINE='1',TIKTOKEN_CACHE_DIR=str(R/'tiktoken-cache'))
from docmancer.mcp._docs_server_part01 import create_local_mcp_service,call_docs_tool_payload
import docmancer.docs.application._project_docs_service_part03 as mod
from docmancer.core.sqlite_store import SQLiteStore
events=[]
orig_plan=mod.build_documentation_query_plan
def observe_plan(*a,**kw):
    obj=orig_plan(*a,**kw); events.append({'stage':'actual_plan','payload':obj.as_payload()});return obj
mod.build_documentation_query_plan=observe_plan
orig_qualify=mod._qualify_candidate_lookups
def dump(items): return [x.model_dump(mode='json') if hasattr(x,'model_dump') else str(x) for x in items]
def observe_qualify(*a,**kw):
    before=dump(a[0]); result=orig_qualify(*a,**kw);events.append({'stage':'qualification','before':before,'after':dump(result)});return result
mod._qualify_candidate_lookups=observe_qualify
orig_search=SQLiteStore._search_rows
def observe_search(self,*a,**kw):
    rows=orig_search(self,*a,**kw);events.append({'stage':'search_rows','query':a[0],'limit':a[1],'filters':kw.get('filters'),'ordered_ids':[r.get('stable_chunk_id') for r in rows]});return rows
SQLiteStore._search_rows=observe_search
project=Path('/tmp/opencode/semantic-signal-experiment/project') if corpus=='L0' else R/'L2-project'
q=json.loads(Path('/home/viadmin/StudioProjects/DocAtlas/eval/opencode_compat/acq_pilot/oracle.json').read_text())['questions'][0]
args={'project_path':str(project),'question':q['question'],'search_question':q['search_question'],'scope':'project'}
t=time.perf_counter(); payload=call_docs_tool_payload('get_docs_context',args,create_local_mcp_service()); elapsed=time.perf_counter()-t
out={'note':'separate in-process read-only observation, not a stdio pilot call; transparent wrappers preserve outputs','args':args,'elapsed':elapsed,'payload':payload,'events':events}
(R/f'observation-{corpus}-{variant}-P1.json').write_text(json.dumps(out,ensure_ascii=False,default=str))
print(corpus,variant,'status',payload.get('status'),'events',[(x['stage'],len(x.get('before',x.get('ordered_ids',[])))) for x in events],flush=True)
