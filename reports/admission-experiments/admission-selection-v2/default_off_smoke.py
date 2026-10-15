"""Two original public default-off requests after the new selector hook.

Reuse unchanged main project/store. Not full50/default regression or host inference.
"""
import json
from pathlib import Path
from unittest.mock import patch

import run_public as run
from docmancer.mcp._docs_server_part01 import create_local_mcp_service
from eval.evidence_quality_v2.runtime import _FixtureService


def main():
    root=run.ROOT
    if (root/'DEFAULT_OFF_SMOKE.json').exists():
        raise RuntimeError('No repeated default smoke')
    run.ledger=json.loads((root/'LEDGER.json').read_text())
    prepared=json.loads((root/'prepares/main.json').read_text())
    project=Path(json.loads((root/'bindings/main.json').read_text())['project'])
    home=Path(prepared['storage_path']).parents[2]
    env=dict(run.ORIGINAL_ENV)
    env.update({key:str(home/key.lower()) for key in ('HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME','DOCATLAS_HOME')})
    env.update(DOCATLAS_OFFLINE='1',DOCATLAS_AUTO_VECTORS='0')
    env.pop('DOCATLAS_EXPERIMENT_ADMISSION',None)
    rows=[]
    with patch.dict(run.os.environ,env,clear=True):
        cold=create_local_mcp_service();service=_FixtureService(cold)
        if cold.member_storage_policy.generation()!=prepared['generation_id']:
            raise RuntimeError('Default smoke store changed')
        service.materialize(read_only_startup=True)
        for cid in ['Q16','Q46']:
            source=json.loads((root/f'public/{cid}_B1.json').read_text())
            before=run.state(service,project)
            run.ledger['context_attempts']+=1;run.save('LEDGER.json',run.ledger)
            payload,snapshot=run._call_with_snapshot({'question':source['question'],'project_path':str(project),'scope':'project'},service)
            after=run.state(service,project)
            expected=(not payload.get('sources') and payload.get('status')=='insufficient_evidence'
                      and payload.get('answer_supported') is False and payload.get('edit_ready') is False and before==after)
            rows.append({'id':cid,'question':source['question'],'payload':payload,'snapshot':snapshot,
                         'state_before':before,'state_after':after,'matches_archived_empty_default':expected})
            run.save('DEFAULT_OFF_SMOKE.json',{'boundary':'two real public default-off requests; not full parity/regression',
                     'new_prepares':0,'model_forwards':0,'host_requests':0,'results':rows,'ledger':run.ledger})
            if not expected: raise RuntimeError('Default-off behavior mismatch')


if __name__=='__main__': main()
