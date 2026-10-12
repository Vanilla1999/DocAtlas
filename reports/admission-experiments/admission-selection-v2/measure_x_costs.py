"""Saved paired host/source accounting, no inference."""
import json
from pathlib import Path
import tiktoken

ROOT=Path(__file__).resolve().parent
codec=tiktoken.get_encoding('o200k_base')


def count(value):
    return len(codec.encode(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))))


def main():
    result=[]
    model=json.loads((ROOT/'X/joint_receipt.json').read_text())
    byid={row['id']:row for row in model['cases']}
    for cid in ['Q16','Q46']:
        selection=json.loads((ROOT/f'public/{cid}_X-rank.json').read_text())
        capture=json.loads((ROOT/f'public/{cid}_B1.json').read_text())
        scoring=sum(row['inference_seconds'] for row in byid[cid]['rows'])
        reconstruction=json.loads((ROOT/f'X/{cid}_bindings.json').read_text())['view_build_seconds']
        for arm in ['X-rank','X-prune']:
            request=json.loads((ROOT/f'host/{cid}_{arm}/request.json').read_text())
            receipt=json.loads((ROOT/f'host/{cid}_{arm}/receipt.json').read_text())
            inputs=json.loads((ROOT/f'X/{cid}_{arm}_model_input.json').read_text())
            result.append({'id':cid,'arm':arm,'snippet_proxy_tokens':sum(count(item['text']) for item in inputs['sources']),
                           'submitted_prompt_proxy_tokens':count(request['prompt']),'source_count':len(inputs['sources']),
                           'host_seconds':receipt['latency_seconds'],'resident_joint_forward_seconds':scoring,
                           'actual_public_requests':2,'public_seconds':capture['elapsed_seconds']+selection['elapsed_seconds'],
                           'observed_turn_seconds_lower_bound':capture['elapsed_seconds']+selection['elapsed_seconds']+scoring+receipt['latency_seconds']+(reconstruction if arm=='X-prune' else 0),
                           'view_build_seconds':reconstruction if arm=='X-prune' else 0,
                           'reconstruction_cost':'combined span reconstruction/provenance view assembly charged conservatively to pruning arm'})
    output={'rows':result,'codec':'o200k_base proxy NOT billing','cold_load_seconds':model['cold_load_seconds'],
            'forwards':model['forward_calls'],'rss_bytes':model['peak_rss_bytes'],
            'pairing':'same joint scores/retained masks, same native selected IDs, same actual parent public packet',
            'boundary':'product-integrated ranking + client exact-span pruning; no native pruned public DTO claim'}
    output['timing_limit']='Per-case sums are lower bounds: author tokenization/mapping, process startup/import, JSON/storage overhead not allocated. Joint runner total_seconds and cold_load_seconds remain in raw receipt. Do not claim complete latency/speedup.'
    (ROOT/'X/COSTS.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
