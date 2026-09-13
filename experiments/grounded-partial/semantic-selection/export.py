"""Capture unchanged native baselines and a gold-blind, case-level candidate pool."""
import argparse, hashlib, json, os, sqlite3, time, gzip
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.docs.application import _project_docs_service_part03 as project
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for, audit_payload
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.semantic import assess_context
from eval.evidence_quality_v2.trace import source_span

def sha(x): return hashlib.sha256(x).hexdigest()
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def key(question,library): return sha((library+'\n'+question).encode())
def candidate_key(row):
    s=source_span(row);m=row.get('metadata',{})
    return sha(json.dumps([s['project_identity'],s['path_or_url'],s['line_start'],s['line_end'],m.get('content_hash'),s['snippet']],ensure_ascii=False).encode())

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists();a.output.mkdir(parents=True)
    protocol,cases,manifest=load_protocol();previous={r['id']:r for r in json.loads((a.fixture/'rows.json').read_text())}
    rows=[];scoring=[];mapping={}; native=project._retrieval_stage_diagnostics
    for lib in sorted({c['project_group'] for c in cases}):
        root=a.fixture/'corpus'/lib
        for path,body in documents_for(lib,manifest).items(): assert (root/path).read_text()==body
        state=a.output/lib;state.mkdir()
        with sqlite3.connect(f'file:{a.fixture/"state"/lib/"index.db"}?mode=ro',uri=True) as src:
            with sqlite3.connect(state/'index.db') as dest:src.backup(dest)
        os.environ.update(DOCATLAS_HOME=str(state/'home'),DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0')
        config=DocmancerConfig();config.index.db_path=str(state/'index.db');config.index.extracted_dir=str(state/'extracted')
        service=LibraryDocsService(config=config,config_source='explicit',registry=LibraryRegistry(str(state/'index.db')),agent=DocmancerAgent(config=config),job_tracker=DocsJobTracker())
        identity=service.project_docs._repository_identity(root)
        for case in [c for c in cases if c['project_group']==lib]:
            captured=[]
            def capture(plan,candidates):
                original=next(q for q in plan.queries if q.query_id=='query-original')
                # Re-evaluate for observation only; do not change original candidates.
                tagged=project._tag_retrieval_query(candidates,'query-original',original.text,original,expected_project_identity=identity)
                for raw,tag in zip(candidates,tagged):
                    captured.append({'raw':raw.model_dump(mode='json'),'original_check':tag.metadata['retrieval_query_matches']['query-original']})
                return native(plan,candidates)
            start=time.perf_counter()
            with patch.object(project,'_retrieval_stage_diagnostics',capture):payload,trace=observe_call(service,{'question':case['question'],'project_path':str(root),'scope':'all'})
            elapsed=time.perf_counter()-start
            spans=lambda p:[(s['path_or_url'],s['snippet']) for s in p.get('sources',[])]
            assert spans(payload)==spans(previous[case['id']]['payload']),case['id']
            errors=audit_payload(payload,trace['snapshot'],root);assert not errors,errors
            safe=[];seen=set();rejected=[]
            for item in captured:
                raw=item['raw'];ck=candidate_key(raw)
                if ck in seen:continue
                seen.add(ck)
                reason=item['original_check'].get('qualification_reason')
                # These outcomes follow all source-policy checks; relevance is not admission here.
                if reason not in {'visible_fields','insufficient_visible_match','metadata_only_evidence','missing_visible_query_terms','visible_exact_path','missing_visible_exact_path'}:
                    rejected.append({'key':ck,'reason':reason});continue
                safe.append({'key':ck,**item})
            bounded=safe[:64];qk=key(case['question'],lib);mapping[qk]=case['id']
            entries=[]
            for item in bounded:
                raw=item['raw'];m=raw['metadata'];s=source_span(raw)
                text=s['snippet'];header='\n'.join(str(x) for x in [lib,next(r['ref'] for r in manifest['sources'] if r['project']==lib and r['path']==s['path_or_url']),m.get('title',''),m.get('heading_path','')] if x)
                entries.append({'key':item['key'],'header':header,'text':text})
            scoring.append({'key':qk,'question':case['question'],'candidates':entries})
            row={'id':case['id'],'question_key':qk,'payload':payload,'assessment':assess_context(case,payload,registry_for(lib,manifest)),'seconds':elapsed,'audit_errors':errors,'pool':bounded,'pool_before_64':safe,'policy_rejected':rejected,'fingerprint':sha(json.dumps([i['key'] for i in bounded]).encode())}
            rows.append(row);save(a.output/'baselines.json',rows)
            (a.output/f'{case["id"]}.trace.json.gz').write_bytes(gzip.compress(json.dumps(trace,ensure_ascii=False,default=str).encode(),mtime=0))
            print(case['id'],row['assessment']['context_sufficiency'],'pool',len(bounded),'before',len(safe),flush=True)
    assert sum(r['assessment']['context_sufficiency']=='sufficient' for r in rows if next(c for c in cases if c['id']==r['id'])['answerability']=='within_budget')==33
    (a.output/'candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in scoring))
    save(a.output/'case-map.json',mapping)
    save(a.output/'identity.json',{'frozen':protocol,'candidates_sha256':sha((a.output/'candidates.jsonl').read_bytes()),'baseline_count':len(rows),'baseline_sufficient':33,'baseline_all80_paths_snippets_identical':True})
if __name__=='__main__':main()
