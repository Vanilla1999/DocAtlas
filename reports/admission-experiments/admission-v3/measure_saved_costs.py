"""No product/model execution: account saved V3 receipts and actual requests."""
from hashlib import sha256
from collections import defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    rows = []
    for path in sorted((ROOT / 'public').glob('*.json')):
        r = json.loads(path.read_text())
        rows.append({'kind': 'context', 'case_id': r['case_id'], 'arm': r['arm'], 'status': r['status'],
                     'seconds': r.get('elapsed_seconds'),
                     'sources': len(r.get('payload', {}).get('sources') or []),
                     'snippet_chars': sum(len(s.get('snippet', '')) for s in (r.get('payload', {}).get('sources') or []))})
    for path in sorted((ROOT / 'prepares').glob('*.json')):
        r = json.loads(path.read_text())
        rows.append({'kind': 'prepare', 'group': path.stem, 'seconds': r.get('seconds'), 'status': 'EXECUTED'})
    for path in sorted((ROOT / 'host').glob('*/receipt.json')):
        r = json.loads(path.read_text())
        request = json.loads((path.parent / 'request.json').read_text())
        prompt = request['prompt']
        rows.append({'kind': 'host', 'case_id': r['provenance']['case_id'], 'arm': r['provenance']['arm'],
                     'status': r['execution'], 'seconds': r.get('latency_seconds'),
                     'submitted_prompt_chars': len(prompt), 'submitted_prompt_utf8_bytes': len(prompt.encode()),
                     'request_sha256': r['request_sha256'], 'billing': 'UNKNOWN',
                     'actual_provider_tokens': 'UNKNOWN', 'backend_revision': 'UNKNOWN', 'sampling': 'UNKNOWN'})
    extraction = list((ROOT / 'citation').glob('*_extracted.json'))
    for path in sorted((ROOT / 'citation').glob('*_cost.json')):
        r = json.loads(path.read_text())
        rows.append({'kind': 'citation_reconstruction', 'case_id': path.stem.removesuffix('_cost'),
                     'status': 'EXECUTED', 'seconds': r['assembly_seconds'] + r['reconstruction_seconds'], **r})
    public = {(r['case_id'], r['arm']): r for r in rows if r['kind'] == 'context'}
    hosts = {(r['case_id'], r['arm']): r for r in rows if r['kind'] == 'host'}
    for row in hosts.values():
        parent = ('B1' if row['case_id'] in ('Q16', 'Q46') else 'V3') if row['arm'] == 'Citation' else row['arm']
        row['public_parent_arm'] = parent
        row['standalone_turn_seconds_lower_bound'] = (row.get('seconds') or 0) + (public[(row['case_id'], parent)].get('seconds') or 0)
        if row['arm'] == 'Citation':
            timing = json.loads((ROOT / 'citation' / (row['case_id'] + '_cost.json')).read_text())
            row['standalone_turn_seconds_lower_bound'] += timing['assembly_seconds'] + timing['reconstruction_seconds']
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['kind'], row.get('arm', 'all'))].append(row)
    summaries = [{'kind': kind, 'arm': arm, 'count': len(group),
                  'observed_seconds_lower_bound': sum(r.get('seconds') or 0 for r in group),
                  'submitted_prompt_chars': sum(r.get('submitted_prompt_chars', 0) for r in group),
                  'submitted_prompt_utf8_bytes': sum(r.get('submitted_prompt_utf8_bytes', 0) for r in group)}
                 for (kind, arm), group in grouped.items()]
    paired_ids = sorted(cid for cid, arm in hosts if arm == 'B1' and (cid, 'V3') in hosts)
    paired = {'case_ids': paired_ids, 'arms': {arm: {
        'host_attempts': len(paired_ids),
        'submitted_prompt_chars': sum(hosts[(cid, arm)]['submitted_prompt_chars'] for cid in paired_ids),
        'submitted_prompt_utf8_bytes': sum(hosts[(cid, arm)]['submitted_prompt_utf8_bytes'] for cid in paired_ids),
        'host_seconds': sum(hosts[(cid, arm)]['seconds'] for cid in paired_ids),
        'turn_seconds_lower_bound': sum(hosts[(cid, arm)]['standalone_turn_seconds_lower_bound'] for cid in paired_ids)
    } for arm in ('B1', 'V3')},
        'warning': 'B1 empty/partial vs V3 recovered evidence: not equal-quality cost comparison; single-pass timings not speedup.'}
    citation_pairs = []
    for (cid, arm), child in hosts.items():
        if arm != 'Citation':
            continue
        base = hosts[(cid, child['public_parent_arm'])]
        citation_pairs.append({'case_id': cid, 'parent_arm': child['public_parent_arm'],
            'base_chars': base['submitted_prompt_chars'], 'citation_chars': child['submitted_prompt_chars'],
            'delta_chars': child['submitted_prompt_chars'] - base['submitted_prompt_chars'],
            'base_bytes': base['submitted_prompt_utf8_bytes'], 'citation_bytes': child['submitted_prompt_utf8_bytes'],
            'warning': 'Same evidence content; distinct generator schema/line framing, not ranking gain or original quote repair.'})
    ledger = json.loads((ROOT / 'LEDGER.json').read_text()) if (ROOT / 'LEDGER.json').exists() else {}
    result = {'ledger': ledger, 'rows': rows,
              'auxiliary_documentation_lookup': {'attempts': ledger.get('documentation_context_attempts', 0),
                  'status': ledger.get('documentation_context_status'), 'billing_tokens_backend': 'UNKNOWN',
                  'not_evaluation_context': '57 actual experiment contexts plus one preliminary docs-router request; total58 within80 ceiling'},
              'observed_seconds_sum_lower_bound': sum(r.get('seconds') or 0 for r in rows),
              'citation_extraction_receipts': len(extraction),
              'summary': summaries, 'paired_base_costs': paired, 'citation_pairs': citation_pairs,
              'runtime_seconds': json.loads((ROOT / 'COMPLETION.json').read_text())['runtime_seconds'] if (ROOT / 'COMPLETION.json').exists() else None,
              'submitted_token_proxy': 'NOT_MEASURED; actual chars/UTF8 bytes recorded; no billing tokenizer assumed',
              'neural_scoring_seconds': 0, 'neural_acquisition_downloads': 0,
              'actual_turn_accounting': 'Base B1/V3: one public acquisition + host. Citation: exact captured parent shared once in actual workload; standalone turn includes parent acquisition + assembly + host + reconstruction.',
              'artifact_bytes': sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()),
              'limits': 'Preparation/acquisition/host and four citation assembly/reconstruction stages observed. Process/import/serialization/tokenization and other unallocated work not fully split per-case: timing sums lower bounds. No p95 or financial advantage claim.',
              'billing_backend': 'UNKNOWN', 'local_neural_forwards': ledger.get('model_forwards', 0)}
    (ROOT / 'COSTS_V3.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    manifest = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
                for folder in ('public', 'host', 'prepares', 'bindings', 'citation')
                for p in sorted((ROOT / folder).rglob('*')) if p.is_file()}
    (ROOT / 'RAW_HASHES.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
