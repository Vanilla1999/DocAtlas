"""Actual public MCP/SQLite experiment, same-generation pool identity checks.

Observers invoke original components; selection is the explicit product extension.
No mock retrieval/storage/validation, no model-visible oracle.
"""
from contextlib import ExitStack, closing
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

REPO = Path('/tmp/opencode/docatlas-compact-review')
ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent/'admission-full-20261012'
sys.path.insert(0,str(REPO))
from eval.evidence_quality_v2.runtime import isolated_service, index_project, write_project
from scripts.run_project_docs_self_host_gate import _call_with_snapshot
from docmancer.docs.application.experimental_candidate_selection import experimental_candidate_selector


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def save(name,value):
    path=ROOT/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')


def window(chunk):
    metadata=chunk.metadata or {}
    reference=metadata.get('_reference_evidence') or {}
    source=reference.get('source') or {}
    return {'id':digest([source.get('document_id'),reference.get('char_start'),reference.get('char_end'),chunk.text]),
            'text':chunk.text, 'text_sha256':sha256(chunk.text.encode()).hexdigest(),
            'source':chunk.source,'chunk_index':chunk.chunk_index,'score':chunk.score,
            'path':source.get('canonical_path'),'span':[reference.get('char_start'),reference.get('char_end')],
            'binding':source,'metadata':metadata}


def state(service,project):
    policy=service._cold.member_storage_policy
    with closing(policy.connect()) as db:
        rows=[tuple(row) for row in db.execute('SELECT generation_id,source,content,content_hash,source_identity FROM generation_sources ORDER BY generation_id,source')]
    files=[project/'docatlas.project-docs.yaml']+[Path(row[1]) for row in rows]
    return {'generation':policy.generation(),'rows':rows,'files':{str(p):sha256(p.read_bytes()).hexdigest() for p in files}}


def integrity(payload,snapshot,documents,project,generation):
    errors=[]
    identity='local:'+sha256(str(project).encode()).hexdigest()
    for item in payload.get('sources') or []:
        bound=snapshot.get(item.get('evidence_id')) or {}
        ref=((bound.get('source') or {}).get('_reference_evidence') or {})
        source=ref.get('source') or {}
        scope=source.get('scope') or {}
        path=item.get('path_or_url'); text=documents.get(path)
        a,b=ref.get('char_start'),ref.get('char_end')
        if (text is None or bound.get('projected_source')!=item or ref.get('raw_document')!=text
            or source.get('canonical_path')!=path or source.get('content_sha256')!=sha256(text.encode()).hexdigest()
            or scope.get('project_id')!=identity or scope.get('snapshot_id')!=generation
            or scope.get('version')!='' or item.get('scope')!='project' or item.get('version_binding')!='unversioned'
            or item.get('project_identity')!=identity or not isinstance(a,int) or not isinstance(b,int)
            or not 0<=a<b<=len(text) or ref.get('text')!=text[a:b]
            or not item.get('snippet') or item['snippet'] not in text[a:b]):
            errors.append('invalid_bound_source:'+str(item.get('evidence_id')))
    if payload.get('answer_supported') is True or payload.get('edit_ready') is True:
        errors.append('unexpected_authority')
    return errors


def public_call(case,arm,fixture,expected=None,order=None,k=None):
    with patch.dict(os.environ,fixture[4],clear=True):
        return _public_call(case,arm,fixture,expected,order,k)


def _public_call(case,arm,fixture,expected=None,order=None,k=None):
    check_budget()
    service,project,documents,generation=fixture[:4]
    observed=[]
    def choose(question,pool,excluded,original):
        rows=[window(chunk) for chunk in pool]
        complete=[window(chunk) for chunk in original]
        for row in rows:
            ref=row['metadata'].get('_reference_evidence') or {}
            a,b=row['span']; path=row['path']; text=documents.get(path)
            scope=row['binding'].get('scope') or {}
            if (text is None or ref.get('raw_document')!=text or ref.get('text')!=row['text']
                or not isinstance(a,int) or not isinstance(b,int) or text[a:b]!=row['text']
                or row['binding'].get('content_sha256')!=sha256(text.encode()).hexdigest()
                or scope.get('snapshot_id')!=generation or scope.get('version')!=''):
                raise RuntimeError('Pool source binding/allowlist defect')
        receipt={'question':question,'pool':rows,'pool_sha256':digest(rows),
                 'complete_candidates':complete,'complete_sha256':digest(complete),
                 'excluded':[{'candidate':window(chunk),'reason':reason,'original_ordinal':ordinal} for chunk,reason,ordinal in excluded]}
        observed.append(receipt)
        if expected is not None and (receipt['pool_sha256']!=expected['pool_sha256'] or receipt['complete_sha256']!=expected['complete_sha256']):
            raise RuntimeError('Common candidate bytes/order/bindings changed')
        selected=None if arm=='B1' else (list(range(len(rows))) if arm=='Budget' else order)[:k]
        receipt['selected_indices']=selected
        if digest([window(chunk) for chunk in original])!=receipt['complete_sha256']:
            raise RuntimeError('Host callback mutated candidate objects')
        return selected
    before=state(service,project)
    start=time.monotonic()
    result={'case_id':case['id'],'split':case['split'],'arm':arm,'question':case['question'],
            'request':{'question':case['question'],'project_path':str(project),'scope':'project'},'status':'STARTED'}
    ledger['context_attempts']+=1
    if ledger['context_attempts']>80:
        raise RuntimeError('Public call budget exceeded')
    try:
        with experimental_candidate_selector(choose):
            payload,snapshot=_call_with_snapshot(result['request'],service)
        result.update(payload=payload,validation_snapshot=snapshot,pools=observed,status='EXECUTED',
                      elapsed_seconds=time.monotonic()-start)
        result['state_before']=before
        result['state_after']=state(service,project)
        result['integrity_errors']=integrity(payload,snapshot,documents,project,generation)
        if result['state_before']!=result['state_after']:
            result['integrity_errors'].append('read_state_changed')
        if result['integrity_errors']:
            raise RuntimeError('Source policy integrity defect')
        if len(observed)!=1:
            raise RuntimeError('Expected one shared candidate boundary, got '+str(len(observed)))
    except Exception as exc:
        result.update(status='BLOCKED',error=repr(exc),pools=observed,elapsed_seconds=time.monotonic()-start)
        raise
    finally:
        save('public/'+case['id']+'_'+arm+'.json',result)
        save('LEDGER.json',ledger)
    return result


def host_call(case,arm,result):
    check_budget()
    if ledger['host_requests']>=60:
        raise RuntimeError('Host request ceiling')
    payload=result['payload']
    sources=[]
    for item in payload.get('sources') or []:
        sources.append({'source_id':item['evidence_id'],'text':item['snippet'],
                        'provenance':{key:item[key] for key in ('path_or_url','scope','version_binding','line_start','line_end','project_identity','authority') if key in item}})
    model_input={'question':case['question'],'sources':sources}
    messages=[{'role':'system','content':(OLD/'HOST_PROMPT_RU.txt').read_text()},
              {'role':'user','content':canonical(model_input)}]
    module=importlib.util.spec_from_file_location('existing_host_runner',OLD/'B_host_runner.py')
    host=importlib.util.module_from_spec(module);module.loader.exec_module(host)
    ledger['host_requests']+=1
    save('LEDGER.json',ledger)
    with patch.dict(os.environ,ORIGINAL_ENV,clear=True):
        receipt=host.invoke(ROOT/'host'/f"{case['id']}_{arm}",messages,
                          {'case_id':case['id'],'arm':arm,'public_result_sha256':digest(result),'presentation':'source_id,text,real-public-provenance'},60)
    if receipt['execution']!='EXECUTED':
        raise RuntimeError('Existing host unavailable; no replacement/retry')


ledger={'prepares':0,'context_attempts':0,'host_requests':0,'model_forwards':0}
ORIGINAL_ENV=dict(os.environ)
START=time.monotonic()


def check_budget():
    if time.monotonic()-START>7200:
        raise RuntimeError('Two-hour runtime budget')
    if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>4*1024**3:
        raise RuntimeError('Artifact ceiling')


def score(cases,captures,stage):
    inputs=[{'id':case['id'],'question':case['question'],**captures[case['id']]['pools'][0]} for case in cases]
    if ledger['model_forwards']+sum(len(row['pool']) for row in inputs)>500:
        raise RuntimeError('Cumulative primary model forward ceiling before inference')
    save(f'scores/{stage}_input.json',inputs)
    output=ROOT/f'scores/{stage}_receipt.json'
    command=[str(OLD/'model-runtime/bin/python'),str(ROOT/'score_mini.py'),str(ROOT/f'scores/{stage}_input.json'),str(output)]
    save(f'scores/{stage}_command.json',command)
    with (ROOT/f'scores/{stage}.log').open('w') as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
    if not output.exists():
        raise RuntimeError('Model process failed before receipt: '+str(result.returncode))
    receipt=json.loads(output.read_text())
    ledger['model_forwards']+=receipt['forwards'];save('LEDGER.json',ledger)
    if receipt['input_sha256']!=sha256((ROOT/f'scores/{stage}_input.json').read_bytes()).hexdigest():
        raise RuntimeError('Score input binding mismatch')
    byid={row['id']:row for row in receipt['cases']}
    for case in cases:
        cid=case['id']; rows=captures[cid]['pools'][0]['pool']; scores=byid[cid]
        if (scores['pool_sha256']!=captures[cid]['pools'][0]['pool_sha256']
            or [r['id'] for r in scores['rows']]!=[r['id'] for r in rows]):
            raise RuntimeError('Score pool identity mismatch')
    if result.returncode or receipt['status']!='SCORED':
        raise RuntimeError('Complete native scoring blocked; see saved receipt')
    return byid


def present(public,witness):
    return any(item.get('path_or_url')==witness['source_path'] and witness['quote'] in item.get('snippet','')
               for item in public['payload'].get('sources') or [])


def native_present(pool,witness):
    return any(row['path']==witness['source_path'] and witness['quote'] in row['text'] for row in pool)


def main():
    if (ROOT/'RUN_RECEIPT.json').exists():
        raise RuntimeError('No automatic repeat of consumed experiment')
    manifest=json.loads((ROOT/'review/frozen_manifest.json').read_text())
    # Corpus/cases/calibration hashes bind directly; do not open holdout oracle.
    evidence={name:sha256((ROOT/'review'/name).read_bytes()).hexdigest() for name in ('corpus.json','cases.json','calibration_labels.json','frozen_manifest.json')}
    for name in ('corpus.json','cases.json','calibration_labels.json'):
        if evidence[name]!=manifest['files'][name]['sha256']:
            raise RuntimeError('Frozen inputs changed before execution: '+name)
    save('RUN_RECEIPT.json',{'status':'STARTED','frozen_inputs':evidence,'manifest':manifest.get('files'),
         'product_sha256':{str(p.relative_to(REPO)):sha256(p.read_bytes()).hexdigest() for p in
              [REPO/'docmancer/docs/application/experimental_candidate_selection.py',REPO/'docmancer/docs/application/_project_docs_service_part03.py']}})
    docs=json.loads((ROOT/'review/corpus.json').read_text())['documents']
    cases=json.loads((ROOT/'review/cases.json').read_text())['cases']
    calibration=json.loads((ROOT/'review/calibration_labels.json').read_text())
    cal_labels={row['id']:row for row in calibration['cases']}
    cal=[case for case in cases if case['split']=='calibration']
    holds=[case for case in cases if case['split']=='holdout']
    main_questions=json.loads((REPO/'eval/main_flow_comparison/questions_extra40.json').read_text())
    diagnostics=[{'id':f'Q{i}','split':'diagnostic','question':main_questions[i-11][0],'document_group':'main'} for i in (16,46)]
    diagnostics += [dict(id='OtherAPI',split='diagnostic',question='How does OtherAPI handle packet delivery during recovery?',document_group='owner'),
                    dict(id='unrelated',split='diagnostic',question='Как DocAtlas отправляет сообщения через квантовый канал?',document_group='unrelated')]
    groupdocs={}
    for doc in docs:
        groupdocs.setdefault(doc['document_group'],{})[doc['path']]=doc['content']
    groupdocs['main']={'README.md':(REPO/'eval/main_flow_comparison/corpus.md').read_text()}
    groupdocs['owner']={
        'docs/logs.md':'# Logging\n\nLogs flow to disk after each request.\n',
        'docs/owners.md':'# OtherAPI\n\nOtherAPI validates session credentials before startup.\n\n# DeliveryEngine\n\nPacket delivery resumes after each request.\n',
        'docs/packets.md':'# Packet transport\n\nPackets are delivered after each request.\n',
        'docs/setext.md':'# Pulse notes\n\nTelemetry pulses serialize\n--------------------------\n\nRead the handbook for background.\n',
        'docs/compounds.md':'# DocAtlas\n\nDocAtlas combines batch/queue and batch\\queue labels before startup.\n'}
    groupdocs['unrelated']={'docs/fixture.md':'# Fixture store\n\nDocAtlas stores fixture records for local inspection.\n'}
    captures={}; fixtures={}
    with ExitStack() as stack:
        # Reuse the exact captured service/generation, not serialized admission receipts.
        for group,documents in groupdocs.items():
            check_budget()
            root=Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='docatlas-selection-v2-',dir='/tmp')))
            project=root/'project';write_project(project,documents)
            if group=='main':
                (project/'docatlas.project-docs.yaml').write_text(json.dumps({'schema_version':1,'code_files':[],'documents':[
                    dict(path='README.md',role='overview',scope='project',description='DocAtlas main-flow logging and evaluation documentation',authority='source_of_truth')]}))
            service,config=stack.enter_context(isolated_service(root/'state'))
            ledger['prepares']+=1
            if ledger['prepares']>8:
                raise RuntimeError('Preparation ceiling')
            save('LEDGER.json',ledger)
            prepared=index_project(service,config,project)
            save('prepares/'+group+'.json',prepared)
            env=dict(os.environ);env['DOCATLAS_EXPERIMENT_ADMISSION']='policy_candidates_v1'
            fixtures[group]=(service,project,documents,prepared['generation_id'],env)
            save('bindings/'+group+'.json',{'project':str(project),'source_scope':'project','source_version':'unversioned',
                 'domain_version':'2026.1' if group not in ('main','owner','unrelated') else None,
                 'document_hashes':{path:sha256(text.encode()).hexdigest() for path,text in documents.items()},'generation':prepared['generation_id']})
        for case in cal:
            captures[case['id']]=public_call(case,'B1',fixtures[case['document_group']])
        cal_scores=score(cal,captures,'calibration')
        witnesses=calibration['witnesses']; targets={}
        for case in cal:
            label=cal_labels[case['id']]
            ids=list(dict.fromkeys(wid for fact in label['required_facts'] for wid in fact['source_witnesses']))
            targets[case['id']]=[wid for wid in ids if present(captures[case['id']],witnesses[wid])]
        if not any(targets.values()):
            raise RuntimeError('No B1-delivered calibration obligations; vacuous calibration forbidden')
        options=[]
        for k in (1,2,4):
            lost=[]
            for case in cal:
                cid=case['id'];pool=captures[cid]['pools'][0]['pool']
                selected=[pool[i] for i in cal_scores[cid]['order'][:k]]
                lost += [cid+':'+wid for wid in targets[cid] if not native_present(selected,witnesses[wid])]
            options.append({'k':k,'lost_B1_witnesses':lost})
        valid=[row['k'] for row in options if not row['lost_B1_witnesses']]
        save('CALIBRATION_PROVISIONAL.json',{'targets':targets,'options':options,'selected_k':min(valid) if valid else None})
        if not valid:
            raise RuntimeError('No operational k retains B1 calibration obligations')
        k=min(valid);confirm=[]
        for case in cal:
            cid=case['id'];pool=captures[cid]['pools'][0]
            for arm in ('Budget','Mini'):
                result=public_call(case,arm,fixtures[case['document_group']],pool,cal_scores[cid]['order'],k)
                lost=[wid for wid in targets[cid] if not present(result,witnesses[wid])]
                confirm.append({'id':cid,'arm':arm,'lost_B1_witnesses':lost})
        save('CALIBRATION_FINAL.json',{'k':k,'confirmation':confirm})
        if any(row['lost_B1_witnesses'] for row in confirm if row['arm']=='Mini'):
            raise RuntimeError('Mini calibration final delivery loses B1 obligations; stop without retuning')
        save('FROZEN_SELECTION.json',{'k':k,'method':'minimal Mini native provisional sufficient k, confirmed final public calibration',
             'calibration_sha256':evidence['calibration_labels.json'],'timestamp_unix':time.time(),
             'generator_prompt_sha256':sha256((OLD/'HOST_PROMPT_RU.txt').read_bytes()).hexdigest(),
             'holdout_labels_read':False,'presentation':'source_id,text,actual public provenance','citation_adapter':None})
        evaluation=holds+diagnostics
        for case in evaluation:
            captures[case['id']]=public_call(case,'B1',fixtures[case['document_group']])
        eval_scores=score(evaluation,captures,'evaluation')
        for case in evaluation:
            cid=case['id'];pool=captures[cid]['pools'][0]
            results={'B1':captures[cid]}
            for arm in ('Budget','Mini'):
                results[arm]=public_call(case,arm,fixtures[case['document_group']],pool,eval_scores[cid]['order'],k)
            for arm in ('B1','Budget','Mini'):
                host_call(case,arm,results[arm])
    save('COMPLETION.json',{'status':'COMPLETED_PRIMARY','ledger':ledger,'runtime_seconds':time.monotonic()-START})


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        save('BLOCKER.json',{'error':repr(exc),'ledger':ledger,'runtime_seconds':time.monotonic()-START})
        raise
