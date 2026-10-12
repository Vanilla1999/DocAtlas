"""Two diagnostic X-rank/client-exact-prune paired host experiments."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'admission-full-20261012'


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj


def score_only():
    driver=module(OLD/'D_xprovence_runner.py','saved_author_runner')
    driver.run(SimpleNamespace(serial_slot='v2-X-diagnostic-pair-001',input=ROOT/'X/input.json',
          output=ROOT/'X/joint_receipt.json',assets=OLD/'D_assets',
          corpus=Path('/tmp/opencode/docatlas-compact-review/eval/main_flow_comparison/corpus.md'),threshold=.3))


def merged(ranges):
    result=[]
    for a,b in sorted(ranges):
        if a>=b: continue
        if result and a<=result[-1][1]: result[-1][1]=max(b,result[-1][1])
        else: result.append([a,b])
    return result


def main():
    import run_public as run
    from docmancer.mcp._docs_server_part01 import create_local_mcp_service
    from eval.evidence_quality_v2.runtime import _FixtureService
    run.ledger=json.loads((ROOT/'LEDGER.json').read_text())
    if (ROOT/'X/STARTED.json').exists(): raise RuntimeError('No automatic X repeat')
    run.save('X/STARTED.json',{'cases':['Q16','Q46'],'k':2,'threshold':.3,'source':'existing unchanged live-native pool','forwards_planned':16})
    corpus=(run.REPO/'eval/main_flow_comparison/corpus.md').read_text()
    cases=[];baselines={}
    for cid in ['Q16','Q46']:
        baseline=json.loads((ROOT/f'public/{cid}_B1.json').read_text());baselines[cid]=baseline
        rows=baseline['pools'][0]['pool']
        candidates=[dict(id=row['id'],text=row['text'],text_sha256=row['text_sha256'],char_start=row['span'][0],
                         char_end=row['span'][1],source_sha256=row['binding']['content_sha256']) for row in rows]
        cases.append(dict(id=cid,question=baseline['question'],candidates=candidates))
    run.save('X/input.json',{'boundary':'same actual public captured native pool, source validators preserved','cases':cases})
    command=[str(OLD/'model-runtime/bin/python'),str(Path(__file__).resolve()),'--score']
    run.save('X/command.json',command)
    with (ROOT/'X/model.log').open('w') as log:
        status=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    if not (ROOT/'X/joint_receipt.json').exists(): raise RuntimeError('X model failed before receipt')
    receipt=json.loads((ROOT/'X/joint_receipt.json').read_text())
    run.ledger['model_forwards']+=receipt['forward_calls'];run.save('LEDGER.json',run.ledger)
    if status.returncode or not receipt.get('complete') or not all(row['full_pool_scored'] for row in receipt['cases']):
        raise RuntimeError('Full X pool scoring unavailable')
    prep=json.loads((ROOT/'prepares/main.json').read_text());binding=json.loads((ROOT/'bindings/main.json').read_text())
    home=Path(prep['storage_path']).parents[2]
    env=dict(run.ORIGINAL_ENV)
    env.update({key:str(home/key.lower()) for key in ('HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME','DOCATLAS_HOME')})
    env.update(DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0',DOCATLAS_EXPERIMENT_ADMISSION='policy_candidates_v1')
    with patch.dict(run.os.environ,env,clear=True):
        cold=create_local_mcp_service();service=_FixtureService(cold)
        if cold.member_storage_policy.generation()!=prep['generation_id']: raise RuntimeError('Store generation changed')
        service.materialize(read_only_startup=True)
    fixture=(service,Path(binding['project']),{'README.md':corpus},prep['generation_id'],env)
    host=module(OLD/'B_host_runner.py','existing_host')
    for scored in receipt['cases']:
        cid=scored['id'];baseline=baselines[cid];pool=baseline['pools'][0];ids=[row['id'] for row in pool['pool']]
        if set(ids)!=set(row['candidate_id'] for row in scored['rows']): raise RuntimeError('X pool row identity mismatch')
        order=[ids.index(value) for value in scored['ranked_ids']]
        case=dict(id=cid,split='diagnostic',question=baseline['question'])
        result=run.public_call(case,'X-rank',fixture,pool,order,2)
        selected=[row for row in scored['rows'] if row['candidate_id'] in scored['ranked_ids'][:2]]
        if any(not row['span_mapping_proven'] for row in selected): raise RuntimeError('Exact source mapping unavailable')
        view_started=time.monotonic()
        rank_sources=[];prune_sources=[];bindings=[]
        for item in result['payload'].get('sources') or []:
            parentid=item['evidence_id'];text=item['snippet']
            bound=result['validation_snapshot'][parentid]
            ref=bound['source']['_reference_evidence'];reftext=ref['text']
            if reftext.count(text)!=1: raise RuntimeError('Ambiguous public snippet span')
            first=ref['char_start']+reftext.index(text);last=first+len(text)
            if corpus[first:last]!=text: raise RuntimeError('Public snippet mismatch')
            provenance={key:item[key] for key in ('path_or_url','scope','version_binding','line_start','line_end','project_identity','authority') if key in item}
            rank_sources.append(dict(source_id=parentid,text=text,provenance=provenance))
            # Keep expansions outside selected native windows; masks never pretend to score them.
            native=merged([[max(first,row['original_window']['char_start']),min(last,row['original_window']['char_end'])] for row in selected])
            keep=[];cursor=first
            for a,b in native:
                if cursor<a: keep.append([cursor,a])
                cursor=max(cursor,b)
            if cursor<last: keep.append([cursor,last])
            for row in selected:
                keep += [[max(first,span['char_start']),min(last,span['char_end'])] for span in row['retained_spans']]
            for match in re.finditer(r'(?m)^#{1,6}[^\n]*(?:\n|$)',text):
                keep.append([first+match.start(),first+match.end()])
            for a,b in merged(keep):
                fragment=corpus[a:b]
                if not fragment.strip(): continue
                childid='excerpt-'+run.digest([parentid,a,b,fragment])[:16]
                prune_sources.append(dict(source_id=childid,text=fragment,provenance=provenance))
                bindings.append(dict(source_id=childid,parent_source_id=parentid,path='README.md',char_start=a,char_end=b,
                                     text=fragment,text_sha256=run.sha256(fragment.encode()).hexdigest(),parent_span=[first,last],
                                     source_sha256=run.sha256(corpus.encode()).hexdigest()))
        run.save(f'X/{cid}_bindings.json',{'boundary':'client exact excerpts, not new public DTO','selected_native_ids':scored['ranked_ids'][:2],
                                        'parent_public_sha256':run.digest(result),'excerpts':bindings,
                                        'view_build_seconds':time.monotonic()-view_started})
        for arm,sources in [('X-rank',rank_sources),('X-prune',prune_sources)]:
            if run.ledger['host_requests']>=60: raise RuntimeError('Host budget')
            model_input={'question':case['question'],'sources':sources}
            run.save(f'X/{cid}_{arm}_model_input.json',model_input)
            messages=[dict(role='system',content=(OLD/'HOST_PROMPT_RU.txt').read_text()),dict(role='user',content=run.canonical(model_input))]
            run.ledger['host_requests']+=1;run.save('LEDGER.json',run.ledger)
            with patch.dict(run.os.environ,run.ORIGINAL_ENV,clear=True):
                actual=host.invoke(ROOT/'host'/f'{cid}_{arm}',messages,
                      {'case_id':cid,'arm':arm,'client_pruning':arm=='X-prune','parent_public_sha256':run.digest(result),
                       'native_selected_ids':scored['ranked_ids'][:2]},60)
            if actual['execution']!='EXECUTED': raise RuntimeError('Existing host blocked')
    run.save('X/COMPLETION.json',{'status':'COMPLETED_DIAGNOSTIC_PAIR','ledger':run.ledger})


if __name__=='__main__':
    if '--score' in sys.argv:
        score_only()
    else:
        try: main()
        except Exception as exc:
            ROOT.joinpath('X/BLOCKER.json').write_text(json.dumps({'error':repr(exc)},ensure_ascii=False))
            raise
