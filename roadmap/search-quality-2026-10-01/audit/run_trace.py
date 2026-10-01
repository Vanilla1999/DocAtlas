"""Read-only same-call observer; separate diagnostic run, not MCP latency."""
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import traceback
from unittest.mock import patch

from run_live_mcp import ROOT, OUT, WORK, save
os.environ.update(DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0',DOCATLAS_HOME=str(WORK/'trace-home'))
from docmancer.core.config import DocmancerConfig
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import _service_for_project_path
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.trace import source_span
from eval.evidence_quality_v2.run import load_protocol,documents_for,registry_for,stage_assessment
from eval.evidence_quality_v2.audit import audit_payload
from eval.evidence_quality_v2.runtime import write_project
from eval.evidence_quality_v2.semantic import assess_context


def service_for(root):
    # Explicit resolved paths keep observer dispatch on this same service instance.
    config=DocmancerConfig.from_yaml(root/'docatlas.yaml')
    config.index.db_path=str(root/'.docatlas/docatlas.db')
    config.index.extracted_dir=str(root/'.docatlas/extracted')
    return LibraryDocsService(config=config,config_source='explicit')


def trace_case(service,root,case,label,index=None,registry=None):
    args=dict(question=case['question'],project_path=str(root),scope='all')
    dispatch=[];caps=[];stack=[]
    run=RetrievalDispatcher.run
    cap=RetrievalDispatcher._limit_sections_per_source
    def capture_run(self,query,*a,**kw):
        row=dict(query=query,arguments=deepcopy(kw));dispatch.append(row);stack.append(row)
        try:
            result=run(self,query,*a,**kw)
            row.update(mode_used=getattr(result,'mode_used',None),result=[source_span(c) for c in result.chunks])
            return result
        finally:
            stack.pop()
    def capture_cap(self,chunks,*a,**kw):
        before=list(chunks);result=cap(self,before,*a,**kw)
        caps.append(dict(query=stack[-1]['query'] if stack else None,arguments=deepcopy(kw),
                         before=[source_span(c) for c in before],after=[source_span(c) for c in result]))
        return result
    start=time.perf_counter()
    try:
        with patch.object(RetrievalDispatcher,'run',capture_run),patch.object(RetrievalDispatcher,'_limit_sections_per_source',capture_cap):
            payload,trace=observe_call(service,args)
        trace.update(dispatcher_calls=dispatch,pre_cap_windows=caps)
        rel=f'raw/traces/{label}/{case["id"]}.json.gz'
        destination=OUT/rel
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(gzip.compress(json.dumps(trace,ensure_ascii=False,default=str).encode(),mtime=0))
        row=dict(id=case['id'],panel=label,request=args,payload=payload,seconds=time.perf_counter()-start,
                 trace=rel,snapshot_audit_errors=audit_payload(payload,trace['snapshot'],root),counts=dict(dispatcher_calls=len(dispatch),
                 pre_cap_candidates=sum(len(c['before']) for c in caps),
                 post_cap_candidates=sum(len(c['after']) for c in caps),
                 retrieved=sum(len(c['sources']) for c in trace['stages']['retrieved_candidates']),
                 query_window=sum(len(c['sources']) for c in trace['stages']['query_window']),
                 qualified_variants=sum(len(c['after']) for c in trace['stages']['qualified_fragments'])))
        if index is not None:
            row.update(assessment=assess_context(case,payload,registry),
                       stage_assessment=stage_assessment(case,payload,trace,index,registry))
    except Exception:
        row=dict(id=case['id'],panel=label,error=traceback.format_exc())
    print(label,case['id'],row.get('assessment',{}).get('context_sufficiency'),row.get('counts'),row.get('error','')[-200:],flush=True)
    return row


def main():
    rows=[]
    _,cases,manifest=load_protocol()
    for group in sorted({c['project_group'] for c in cases}):
        root=WORK/'trace-fixtures'/group
        write_project(root,documents_for(group,manifest))
        (root/'docatlas.yaml').write_text('index:\n  provider: sqlite\n  db_path: .docatlas/docatlas.db\n  extracted_dir: .docatlas/extracted\n')
        service=service_for(root)
        result=service.sync_project_docs(str(root),with_vectors=False)
        assert result.status=='success'
        with sqlite3.connect(service.config.index.db_path) as db:
            db.row_factory=sqlite3.Row
            indexed=[dict(r) for r in db.execute('SELECT stable_chunk_id,source_path,display_text,line_start,line_end FROM retrieval_children')]
        save(OUT/'raw/trace-index'/f'{group}.json',indexed)
        for case in [c for c in cases if c['project_group']==group and c['answerability']=='within_budget']:
            rows.append(trace_case(service,root,case,'external48',dict(rows=indexed),registry_for(group,manifest)))
            save(OUT/'raw/trace-results.json',rows)
    selection=[1,4,7,10,14,18,20,24,29,31,34,36,38,40]
    save(OUT/'raw/trace-selection.json',dict(project_numbers=selection,note='Preselected mechanism diagnostics; not random sample.'))
    service=service_for(ROOT)
    for file,prefix in [('questions.json','projectA'),('followup_questions.json','projectB')]:
        cases=json.loads((ROOT/'experiments/grounded-partial'/file).read_text())['cases']
        for case in cases:
            if int(case['id'][1:]) not in selection:
                continue
            case={**case,'id':prefix+'-'+case['id']}
            rows.append(trace_case(service,ROOT,case,'project28'))
            save(OUT/'raw/trace-results.json',rows)
    print('TRACE COMPLETE',len(rows),flush=True)


if __name__=='__main__':
    main()
