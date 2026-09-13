"""Read-only diagnostic on the unmodified public MCP handler; no gold in inputs."""
from pathlib import Path
import os,json,gzip,time,hashlib,sqlite3,subprocess,traceback
from copy import deepcopy
from unittest.mock import patch
from collections import Counter
from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker,LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.trace import source_span
from eval.evidence_quality_v2.run import audit_payload
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.application.model_visible_projection import canonical_projection_bytes

import argparse, shutil
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--protocol',type=Path,default=Path(__file__).with_name('questions.json'))
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--db-path',type=Path,required=True)
parser.add_argument('--expected-commit',required=True)
cli=parser.parse_args()
ROOT=Path.cwd().resolve()
OUT=cli.output.resolve()
if OUT.is_relative_to(ROOT): raise SystemExit('Raw evidence output must be outside the checkout')
OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'results.json').exists(): raise SystemExit('Choose a fresh output directory')
shutil.copyfile(cli.protocol,OUT/'questions.json')
def save(path,value):
 data=(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n').encode()
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_bytes(gzip.compress(data,mtime=0) if path.suffix=='.gz' else data)
protocol=json.loads((OUT/'questions.json').read_text())
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert head==cli.expected_commit, head
state=OUT/'state';state.mkdir(exist_ok=True)
os.environ['DOCATLAS_HOME']=str(state/'home');os.environ['DOCATLAS_AUTO_VECTORS']='0';os.environ['DOCATLAS_OFFLINE']='1'
config=DocmancerConfig.from_yaml(ROOT/'docatlas.yaml')
config.index.db_path=str(cli.db_path.resolve())
config.index.extracted_dir=str(cli.db_path.resolve().parent/'extracted')
service=LibraryDocsService(config=config,config_source='explicit',registry=LibraryRegistry(config.index.db_path),agent=DocmancerAgent(config=config),job_tracker=DocsJobTracker())
preflight=call_docs_tool_payload('get_docs_context',{'question':protocol['cases'][0]['question'],'project_path':str(ROOT)},service)
save(OUT/'preparation.json',{'preflight':preflight,'setup':'repo config with isolated local SQLite; project sync without vectors; frozen questions unchanged'})
start=time.perf_counter();synced=service.sync_project_docs(str(ROOT),with_vectors=False)
assert synced.status=='success',str(synced)
with sqlite3.connect(config.index.db_path) as db:
 db.row_factory=sqlite3.Row
 indexed=[dict(x) for x in db.execute('SELECT stable_chunk_id,source_path,display_text,line_start,line_end FROM retrieval_children')]
save(OUT/'index.json.gz',indexed)
manifest=[]
for path in sorted({r['source_path'] for r in indexed}):
 source=(ROOT/path).resolve()
 if source.is_relative_to(ROOT) and source.is_file():
  data=source.read_bytes();manifest.append({'path':path,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
  target=OUT/'corpus'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
save(OUT/'environment.json',{'commit':head,'questions_sha256':hashlib.sha256((OUT/'questions.json').read_bytes()).hexdigest(),'config':config.model_dump(mode='json'),'indexed_children':len(indexed),'indexed_documents':len(manifest),'index_seconds':time.perf_counter()-start,'source_manifest':manifest,'mode':'public MCP handler in process; lexical/offline; one shared immutable indexed fixture; instrumented latency, not host-agent latency'})
print('indexed',len(manifest),'documents',len(indexed),'children',flush=True)
results=[]
for lane in ('minimal','all','guided'):
 for case in protocol['cases']:
  args={'question':case['question'],'project_path':str(ROOT)}
  if lane!='minimal':args['scope']='all'
  if lane=='guided':args['lookup_queries']=case['host_lookups']
  dispatch=[];caps=[];stack=[]
  run_fn=RetrievalDispatcher.run;cap_fn=RetrievalDispatcher._limit_sections_per_source
  def run(self,query,*a,**kw):
   row={'query':query,'arguments':deepcopy(kw)};dispatch.append(row);stack.append(row)
   try:
    out=run_fn(self,query,*a,**kw)
    row.update(mode_used=getattr(out,'mode_used',None),result=[source_span(x) for x in out.chunks])
    return out
   finally:stack.pop()
  def cap(self,chunks,*a,**kw):
   original=list(chunks)
   result=cap_fn(self,original,*a,**kw)
   caps.append({'query':stack[-1]['query'] if stack else None,'arguments':deepcopy(kw),'before':[source_span(x) for x in original],'after':[source_span(x) for x in result]})
   return result
  started=time.perf_counter();cpu_started=time.process_time()
  try:
   with patch.object(RetrievalDispatcher,'run',run),patch.object(RetrievalDispatcher,'_limit_sections_per_source',cap):
    payload,trace=observe_call(service,args)
   duration=time.perf_counter()-started
   trace['dispatcher_calls']=dispatch;trace['pre_cap_windows']=caps
   errors=audit_payload(payload,trace['snapshot'],ROOT)
   trace_path=f'traces/{lane}/{case["id"]}.json.gz';save(OUT/trace_path,trace)
   same=None
   if case['id'] in ('Q01','Q18','Q25','Q37'):
    native=call_docs_tool_payload('get_docs_context',args,service)
    same=native==payload
    if not same:save(OUT/f'observer_control/{lane}-{case["id"]}.json',{'native':native,'observed':payload})
   row={'id':case['id'],'lane':lane,'question':case['question'],'topic':case['topic'],'arguments':args,'payload':payload,'actual_tokens':projection_token_count(canonical_projection_bytes(payload)),'seconds':duration,'cpu_seconds':time.process_time()-cpu_started,'audit_errors':errors,'native_observer_equal':same,'trace':trace_path,'counts':{'dispatcher_calls':len(dispatch),'pre_cap_candidates':sum(len(x['before']) for x in caps),'post_cap_candidates':sum(len(x['after']) for x in caps),'query_window':sum(len(x['sources']) for x in trace['stages']['query_window']),'retrieved':sum(len(x['sources']) for x in trace['stages']['retrieved_candidates']),'projector_inputs':len(trace['stages']['projector_inputs']),'qualified_variants':sum(len(x['after']) for x in trace['stages']['qualified_fragments'])}}
  except Exception:
   row={'id':case['id'],'lane':lane,'question':case['question'],'error':traceback.format_exc()}
  results.append(row);save(OUT/'results.json',results)
  print(lane,case['id'],row.get('payload',{}).get('status'),row.get('payload',{}).get('kind'),len(row.get('payload',{}).get('sources',[])),row.get('actual_tokens'),row.get('error','')[-180:],flush=True)
save(OUT/'summary.json',{'rows':len(results),'lanes':{lane:{'kinds':dict(Counter(x.get('payload',{}).get('kind','ERROR') for x in results if x['lane']==lane)),'errors':[x['id'] for x in results if x['lane']==lane and (x.get('error') or x.get('audit_errors'))],'observer_mismatches':[x['id'] for x in results if x['lane']==lane and x.get('native_observer_equal') is False]} for lane in ('minimal','all','guided')}})
