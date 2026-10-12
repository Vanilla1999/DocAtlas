"""Saved-input accounting only; no inference/product re-execution or gold labels."""
from hashlib import sha256
import json
from pathlib import Path
import statistics

import tiktoken

ROOT=Path(__file__).resolve().parent
codec=tiktoken.get_encoding('o200k_base')


def tokens(value):
    return len(codec.encode(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))))


def main():
    scores={}
    loads=[]
    for path in (ROOT/'scores').glob('*_receipt.json'):
        record=json.loads(path.read_text())
        loads.append({'stage':path.stem,'cold_load_seconds':record['cold_load_seconds'],'rss_bytes':record['rss_bytes'],
                      'forwards':record['forwards'],'wall_seconds':record['wall_seconds']})
        for case in record['cases']:
            scores[case['id']]={'resident_seconds':sum(row.get('seconds',0) for row in case['rows']),
                                 'input_tokens':sum(row['tokens'] for row in case['rows']),
                                 'forwards':len([row for row in case['rows'] if row['status']=='SCORED'])}
    rows=[]
    for path in sorted((ROOT/'public').glob('*.json')):
        record=json.loads(path.read_text());payload=record['payload'];cid=record['case_id'];arm=record['arm']
        hostdir=ROOT/'host'/f'{cid}_{arm}'
        receipt=json.loads((hostdir/'receipt.json').read_text()) if (hostdir/'receipt.json').exists() else None
        request=json.loads((hostdir/'request.json').read_text()) if (hostdir/'request.json').exists() else None
        rows.append({'id':cid,'split':record['split'],'arm':arm,'sources':len(payload.get('sources') or []),
                     'pool_size':len(record['pools'][0]['pool']),
                     'snippet_proxy_tokens':sum(tokens(item['snippet']) for item in payload.get('sources') or []),
                     'public_dto_proxy_tokens':tokens({k:v for k,v in payload.items() if k!='diagnostics'}),
                     'submitted_prompt_proxy_tokens':tokens(request['prompt']) if request else None,
                     'context_seconds':record['elapsed_seconds'],
                     'host_seconds':receipt.get('latency_seconds') if receipt else None,
                     'host_status':receipt['execution'] if receipt else 'NOT_RUN_CALIBRATION',
                     'resident_rank_seconds':scores[cid]['resident_seconds'] if arm=='Mini' else 0})
    bykey={(row['id'],row['arm']):row for row in rows}
    for row in rows:
        if row['host_status']=='EXECUTED':
            initial=bykey[(row['id'],'B1')]['context_seconds']
            row['observed_turn_seconds_lower_bound']=row['context_seconds']+row['resident_rank_seconds']+row['host_seconds']+(initial if row['arm']!='B1' else 0)
            row['actual_context_requests_per_turn']=1 if row['arm']=='B1' else 2
        else:
            row['observed_turn_seconds_lower_bound']=None
    summaries=[]
    for split in ['holdout','diagnostic']:
        for arm in ['B1','Budget','Mini']:
            subset=[row for row in rows if row['arm']==arm and row['split']==split]
            complete=[row for row in subset if row['host_status']=='EXECUTED']
            summaries.append({'split':split,'arm':arm,'cases':len(subset),'host_completed':len(complete),
                'submitted_prompt_proxy_tokens':sum(row['submitted_prompt_proxy_tokens'] or 0 for row in subset),
                'context_seconds':sum(row['context_seconds'] for row in subset),
                'host_completed_seconds':sum(row['host_seconds'] for row in complete),
                'turn_completed_seconds_lower_bound':sum(row['observed_turn_seconds_lower_bound'] for row in complete),
                'snippet_proxy_tokens':sum(row['snippet_proxy_tokens'] for row in subset),
                'public_dto_proxy_tokens':sum(row['public_dto_proxy_tokens'] for row in subset)})
    output={'codec':'o200k_base proxy, NOT billing/host actual tokenizer','rows':rows,'summaries':summaries,'model_stages':loads,
            'billing':'UNKNOWN','backend_revision':'UNKNOWN','p95':'NOT_MEASURED',
            'actual_execution':'B1 capture once, Budget/Mini re-acquire same exact pool in same stores then select; saved scores used without repeated inference',
            'actual_turn_accounting':'Budget/Mini include initial B1 capture cost + own selection public read + Mini resident scores + host. Cold loads separately; no hypothetical one-call latency claim.',
            'timing_limit':'Per-case sums are lower bounds: model tokenization, process startup/import, alignment, JSON/storage overhead not separately allocated. Whole scorer wall and cold load are reported separately; omitted work is UNKNOWN, not zero. No complete latency or speedup claim.',
            'interrupted_host':'HOLD07_Budget request submitted but completion unknown; prompt counts include it, wall cost unknown/excluded from completed totals',
            'ledger':json.loads((ROOT/'LEDGER.json').read_text())}
    (ROOT/'COSTS_V2.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'summaries':summaries,'model_stages':loads},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
