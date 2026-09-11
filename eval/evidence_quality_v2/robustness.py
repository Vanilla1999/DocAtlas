"""Neutral P4 metamorphic controls through the real index/handler/projector.

Fixtures test a property, not quality on real projects. A missing expected span
is recorded for diagnosis; it does not authorize a speculative production patch.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.runtime import write_project,isolated_service,index_project,save_json,digest
from eval.evidence_quality_v2.run import audit_payload

DOCUMENT='''# Aurora deployment

Aurora publishes a bundle only after the operator approves the release. Without approval, Aurora must not publish the bundle.

## Archive behavior

The archive command does not replace:
- the compiler;
- the debugger;
- the test runner.

## Recovery table

| State | Required action |
| --- | --- |
| `blocked` | Request operator approval. |
| `ready` | Publish the approved bundle. |

## Logging

Aurora records successful deployments in its local audit log.
'''
CASES=[
    {'id':'permission','question':'When may Aurora publish a bundle?','required':['only after the operator approves the release','must not publish the bundle']},
    {'id':'nonreplacement','question':'What does the archive command not replace?','required':['does not replace:','compiler','debugger','test runner']},
    {'id':'keyed_table','question':'What action is required for the `blocked` state?','required':['State','Required action','blocked','Request operator approval.']},
]


def run_variant(output: Path,variant: str) -> dict:
    project=output/'project';documents={'docs/aurora.md':DOCUMENT,'docs/unused.md':'# Other topic\n\nAn unrelated orange notebook has twelve pages.\n'}
    if variant=='formatting':
        documents['docs/aurora.md']=DOCUMENT.replace('`blocked`','blocked').replace('`ready`','ready')
    if variant=='neighbor':documents['docs/aurora.md']=DOCUMENT+'\n## Stationery\n\nThe orange notebook has twelve pages.\n'
    if variant=='reverse_ingest': documents=dict(reversed(list(documents.items())))
    write_project(project,documents)
    if variant=='reverse_ingest':
        import yaml
        manifest=project/'docatlas.project-docs.yaml';data=yaml.safe_load(manifest.read_text());data['documents'].reverse();manifest.write_text(yaml.safe_dump(data,sort_keys=False))
    rows=[]
    with isolated_service(output/'state') as (service,config):
        index=index_project(service,config,project)
        # Effective settings differ only in explicit storage paths. Raw per-root
        # config digests are recorded but never called equal across roots.
        normalized=json.loads(config.model_dump_json()); normalized['index']['db_path']='<STATE>/index.db';normalized['index']['extracted_dir']='<STATE>/extracted'
        for case in CASES:
            request={'question':case['question'],'project_path':str(project),'scope':'all'}
            if variant=='duplicate':request['lookup_queries']=[case['question']]
            payload,trace=observe_call(service,request)
            text='\n'.join(s['snippet'] for s in payload.get('sources',[]))
            present={fact:fact in text for fact in case['required']}
            rows.append({'id':case['id'],'request':request,'payload':payload,'facts':present,
                'complete':all(present.values()),'safety_errors':audit_payload(payload,trace['snapshot'],project),
                'observer_counts':trace['observer_counts']})
            save_json(output/'traces'/f'{case["id"]}.json',trace)
        # Same relative path in another project must not contaminate the first.
        other=output/'other-project';write_project(other,{'docs/aurora.md':'# Aurora deployment\n\nAurora publishes instantly without approval.\n'})
        service.sync_project_docs(str(other),with_vectors=False)
        payload,trace=observe_call(service,{'question':CASES[0]['question'],'project_path':str(project),'scope':'all'})
        other_payload,_=observe_call(service,{'question':CASES[0]['question'],'project_path':str(other),'scope':'all'})
        first_ids={s['project_identity'] for s in payload.get('sources',[])}
        other_ids={s['project_identity'] for s in other_payload.get('sources',[])}
        isolation={'first_has_other_text':any('instantly without approval' in s['snippet'] for s in payload.get('sources',[])),
            'both_have_sources':bool(first_ids and other_ids),'identity_intersection':sorted(first_ids & other_ids)}
    report={'variant':variant,'hash_seed':os.environ.get('PYTHONHASHSEED'),'rows':rows,'isolation':isolation,
            'normalized_config_sha256':digest(json.dumps(normalized,sort_keys=True).encode()),
            'raw_config_sha256':index['config_sha256'],'source_kind':'synthetic metamorphic fixture'}
    save_json(output/'result.json',report);return report


def run(output: Path):
    output.mkdir(parents=True,exist_ok=True)
    matrix=[('base','1'),('long-root-name-for-local-identity','1'),('reverse_ingest','1'),('formatting','1'),('neighbor','1'),('duplicate','1'),('seed-2','2'),('seed-17','17')]
    results=[]
    for variant,seed in matrix:
        env=dict(os.environ,PYTHONHASHSEED=seed,DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0')
        cmd=[sys.executable,'-m','eval.evidence_quality_v2.robustness','--single',variant,'--output',str(output/variant)]
        completed=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=120)
        (output/f'{variant}.log').write_text(completed.stdout+completed.stderr)
        if completed.returncode:raise RuntimeError(f'control failed operationally: {variant}')
        results.append(json.loads((output/variant/'result.json').read_text()))
    baseline={r['id']:r for r in results[0]['rows']}
    changes=[{'variant':result['variant'],'id':row['id'],'before':baseline[row['id']]['facts'],'after':row['facts']}
        for result in results[1:] for row in result['rows'] if row['facts']!=baseline[row['id']]['facts']]
    summary={'runs':len(results),'handler_questions':sum(len(r['rows'])+2 for r in results),
        'baseline_complete':sum(r['complete'] for r in results[0]['rows']),'baseline_count':len(CASES),
        'semantic_changes':changes,'safety_violations':sum(bool(r['safety_errors']) for result in results for r in result['rows']),
        'cross_project_violations':sum(result['isolation']['first_has_other_text'] or bool(result['isolation']['identity_intersection']) for result in results),
        'isolation_controls_with_both_sources':sum(result['isolation']['both_have_sources'] for result in results),
        'production_change':'NONE','verdict':'DISPROVED_ON_THIS_FIXTURE' if not changes and all(r['complete'] for r in results[0]['rows']) else 'INCONCLUSIVE_REQUIRES_FIRST_LOSS_REVIEW',
        'warning':'Characterization, not a test-first runtime fix or real-project holdout score'}
    save_json(output/'summary.json',summary);return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--single')
    args=parser.parse_args();result=run_variant(args.output,args.single) if args.single else run(args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
