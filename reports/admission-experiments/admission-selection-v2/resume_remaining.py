"""Recover only unconsumed requests after shell deadline; no prepares/scoring/retries."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import run_public as run
from docmancer.mcp._docs_server_part01 import create_local_mcp_service
from eval.evidence_quality_v2.runtime import _FixtureService


def main():
    root=run.ROOT
    if (root/'RECOVERY_RECEIPT.json').exists():
        raise RuntimeError('No repeated recovery attempt')
    run.ledger=json.loads((root/'LEDGER.json').read_text())
    consumed=[]
    for receipt in (root/'host').glob('*/receipt.json'):
        data=json.loads(receipt.read_text())
        if data['execution']=='STARTED':
            consumed.append({'case_arm':receipt.parent.name,'status':'INTERRUPTED_COMPLETION_UNKNOWN',
                             'runner_retry':False,'receipt_sha256':run.sha256(receipt.read_bytes()).hexdigest()})
    run.save('RECOVERY_RECEIPT.json',{'reason':'foreground shell tool killed process after120s; research budget2h not exceeded',
         'consumed_unknown':consumed,'new_prepares':0,'new_model_forwards':0,'only_missing_requests':True})
    corpus=json.loads((root/'review/corpus.json').read_text())['documents']
    docs_by_group={}
    for doc in corpus:
        docs_by_group.setdefault(doc['document_group'],{})[doc['path']]=doc['content']
    docs_by_group['main']={'README.md':(run.REPO/'eval/main_flow_comparison/corpus.md').read_text()}
    # For old fixtures use the exact document bytes already bound in captured B1 snapshots.
    for group,cid in [('owner','OtherAPI'),('unrelated','unrelated')]:
        bound=json.loads((root/f'public/{cid}_B1.json').read_text())
        prep=json.loads((root/f'prepares/{group}.json').read_text())
        project=Path(json.loads((root/f'bindings/{group}.json').read_text())['project'])
        docs_by_group[group]={str(Path(d['path'])):(project/d['path']).read_text() for d in prep['documents']}
    fixtures={}
    for group in ['tidal_ferry','main','owner','unrelated']:
        prep=json.loads((root/f'prepares/{group}.json').read_text())
        binding=json.loads((root/f'bindings/{group}.json').read_text())
        home=Path(prep['storage_path']).parents[2]
        env=dict(run.ORIGINAL_ENV)
        env.update({key:str(home/key.lower()) for key in ('HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME','DOCATLAS_HOME')})
        env.update(DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0',DOCATLAS_EXPERIMENT_ADMISSION='policy_candidates_v1')
        with patch.dict(os.environ,env,clear=True):
            cold=create_local_mcp_service()
            if str(cold.member_storage_policy.db_path)!=prep['storage_path'] or cold.member_storage_policy.generation()!=prep['generation_id']:
                raise RuntimeError('Cannot restore same genuine store/generation')
            service=_FixtureService(cold)
            service.materialize(read_only_startup=True)
        fixtures[group]=(service,Path(binding['project']),docs_by_group[group],prep['generation_id'],env)
    cases=json.loads((root/'review/cases.json').read_text())['cases']
    cases=[case for case in cases if case['id'] in ('HOLD07','HOLD08')]
    extra=json.loads((run.REPO/'eval/main_flow_comparison/questions_extra40.json').read_text())
    cases += [dict(id=f'Q{i}',split='diagnostic',question=extra[i-11][0],document_group='main') for i in (16,46)]
    cases += [dict(id='OtherAPI',split='diagnostic',question='How does OtherAPI handle packet delivery during recovery?',document_group='owner'),
              dict(id='unrelated',split='diagnostic',question='Как DocAtlas отправляет сообщения через квантовый канал?',document_group='unrelated')]
    scores={row['id']:row for row in json.loads((root/'scores/evaluation_receipt.json').read_text())['cases']}
    k=json.loads((root/'FROZEN_SELECTION.json').read_text())['k']
    for case in cases:
        cid=case['id'];b1=json.loads((root/f'public/{cid}_B1.json').read_text());pool=b1['pools'][0]
        results={'B1':b1}
        for arm in ('Budget','Mini'):
            path=root/f'public/{cid}_{arm}.json'
            if path.exists():
                results[arm]=json.loads(path.read_text())
            else:
                results[arm]=run.public_call(case,arm,fixtures[case['document_group']],pool,scores[cid]['order'],k)
        for arm in ('B1','Budget','Mini'):
            if (root/f'host/{cid}_{arm}').exists():
                continue
            run.host_call(case,arm,results[arm])
    run.save('COMPLETION.json',{'status':'COMPLETED_PRIMARY_WITH_ONE_INTERRUPTED_HOST', 'ledger':run.ledger,
                               'interrupted_unknown':consumed,'recovery_prepares':0,'recovery_model_forwards':0})


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        run.save('RECOVERY_BLOCKER.json',{'error':repr(exc),'ledger':run.ledger})
        raise
