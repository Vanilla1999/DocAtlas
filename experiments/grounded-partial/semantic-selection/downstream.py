"""Native downstream diagnostic: reorder existing candidates, preserve all gates."""
import argparse,gzip,json,os,sqlite3,time,sys
from pathlib import Path
from unittest.mock import patch
from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService
from docmancer.docs.application import _project_docs_service_part03 as project
from eval.evidence_quality_v2.run import load_protocol,registry_for,audit_payload,stage_assessment
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.semantic import assess_context
from docmancer.docs.application.model_visible_projection import canonical_projection_bytes,docs_context_budget_tokens
from docmancer.docs.application.projection_tokenizer import projection_token_count
sys.path.insert(0,str(Path(__file__).resolve().parent))
from export import candidate_key,key,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--scores',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    _,cases,manifest=load_protocol();scores={r['key']:{c['key']:c['score'] for c in r['candidates']} for r in json.loads((a.scores/'scores.json').read_text())};bases={r['id']:r for r in json.loads((a.baseline/'baselines.json').read_text())};rows=[];native=project._retrieval_stage_diagnostics
    for lib in sorted({c['project_group'] for c in cases}):
        root=a.fixture/'corpus'/lib;state=a.output/lib;state.mkdir()
        with sqlite3.connect(f'file:{a.fixture/"state"/lib/"index.db"}?mode=ro',uri=True) as src:
            with sqlite3.connect(state/'index.db') as dst:src.backup(dst)
        os.environ.update(DOCATLAS_HOME=str(state/'home'),DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0')
        config=DocmancerConfig();config.index.db_path=str(state/'index.db');config.index.extracted_dir=str(state/'extracted')
        service=LibraryDocsService(config=config,config_source='explicit',registry=LibraryRegistry(str(state/'index.db')),agent=DocmancerAgent(config=config),job_tracker=DocsJobTracker())
        for case in [c for c in cases if c['project_group']==lib]:
            sc=scores[key(case['question'],lib)];transitions=[]
            def reorder(plan,candidates):
                before=[candidate_key(c.model_dump(mode='json')) for c in candidates]
                # New auxiliary calls are allowed. Unscored candidates retain their relative order last.
                candidates.sort(key=lambda c:-sc.get(candidate_key(c.model_dump(mode='json')),float('-inf')))
                after=[candidate_key(c.model_dump(mode='json')) for c in candidates]
                assert sorted(before)==sorted(after)
                transitions.append({'before':before,'after':after,'unscored':[k for k in before if k not in sc]})
                return native(plan,candidates)
            started=time.perf_counter()
            with patch.object(project,'_retrieval_stage_diagnostics',reorder):payload,trace=observe_call(service,{'question':case['question'],'project_path':str(root),'scope':'all'})
            errors=audit_payload(payload,trace['snapshot'],root)
            row={'id':case['id'],'answerability':case['answerability'],'payload':payload,'assessment':assess_context(case,payload,registry_for(lib,manifest)),'seconds_excluding_scoring':time.perf_counter()-started,'transitions':transitions,'audit_errors':errors,'admission_tokens':docs_context_budget_tokens(payload),'actual_tokens':projection_token_count(canonical_projection_bytes(payload)),'stages':stage_assessment(case,payload,trace,json.loads((a.fixture/'ingest'/f'{lib}.json').read_text()),registry_for(lib,manifest))}
            rows.append(row);save(a.output/'rows.json',rows);(a.output/f'{case["id"]}.trace.json.gz').write_bytes(gzip.compress(json.dumps(trace,ensure_ascii=False,default=str).encode(),mtime=0));print(case['id'],row['assessment']['context_sufficiency'],errors,flush=True)
    pos=[r for r in rows if r['answerability']=='within_budget'];ok=lambda r:r['assessment']['context_sufficiency']=='sufficient'
    summary={'execution':'native_reordered_existing_candidates_with_cached_scores','A':sum(ok(bases[r['id']]) for r in pos),'B':sum(ok(r) for r in pos),'wins':[r['id'] for r in pos if ok(r) and not ok(bases[r['id']])],'losses':[r['id'] for r in pos if not ok(r) and ok(bases[r['id']])],'audit_errors':sum(len(r['audit_errors']) for r in rows),'unscored_candidates':sum(len(t['unscored']) for r in rows for t in r['transitions']),'max_admission_tokens':max(r['admission_tokens'] for r in rows),'controls_sufficient':[r['id'] for r in rows if r['answerability']!='within_budget' and ok(r)]}
    save(a.output/'summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
