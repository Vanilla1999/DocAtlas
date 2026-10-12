#!/usr/bin/env python3
"""One-shot saved-data packaging only. No product/model/test/host imports or execution."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = Path('/tmp/opencode/docatlas-review-evidence/admission-full-20261012/live-default-off-controls/pytest/test_public_partial_context_prcurrent/qualification-review-proof.json')
TEST = Path('/tmp/opencode/docatlas-compact-review/tests/test_project_context_quality_v2_protocol.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    if (ROOT / 'FREEZE.json').exists():
        raise SystemExit('Already frozen; refusing overwrite')
    raw = OLD.read_bytes()
    old = json.loads(raw)
    hashes = {}
    for rel, text in old['documents'].items():
        path = ROOT / 'inputs/corpus/legacy_priority' / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        # Literal saved document strings, no product helper or generated prose.
        path.write_bytes(text.encode('utf-8'))
        hashes[rel] = sha(path.read_bytes())
    write_json(ROOT / 'CONTROL_PROVENANCE.json', {
        'source_artifact': str(OLD), 'source_artifact_sha256': sha(raw),
        'source_definition': str(TEST), 'source_definition_sha256': sha(TEST.read_bytes()),
        'source_definition_lines': [466, 561], 'documents_sha256': hashes,
        'saved_observation_only': {key: {
            'request': old[key]['request'],
            'support_status': old[key]['payload'].get('support_status'),
            'source_count': len(old[key]['payload'].get('sources') or []),
        } for key in ('numeric', 'numeric_range')},
        'not_executed': True, 'v3_new_project_binding_required': True,
    })
    cases = json.loads((ROOT / 'inputs/cases.json').read_text())
    spec = json.loads((ROOT / 'private/oracle_spec.json').read_text())
    oracle = []
    for case in cases:
        label = spec[case['id']]
        witnesses = []
        for rel, quote in label['witnesses']:
            data = (ROOT / 'inputs/corpus' / case['project'] / rel).read_bytes()
            text = data.decode('utf-8')
            if text.count(quote) != 1:
                raise SystemExit('Nonunique witness: ' + case['id'])
            start = text.index(quote)
            end = start + len(quote)
            witnesses.append({
                'path': rel, 'quote': quote, 'document_sha256': sha(data),
                'quote_sha256': sha(quote.encode('utf-8')),
                'char_start': start, 'char_end': end,
                'line_start': text.count('\n', 0, start) + 1,
                'line_end': text.count('\n', 0, end - 1) + 1,
            })
        oracle.append({**case, **label, 'witnesses': witnesses,
                       'host_verdict_before_outputs': 'NOT_RUN'})
    write_json(ROOT / 'private/oracle.json', {
        'schema': 'v3-independent-oracle-1', 'char_units': 'Unicode code points',
        'span_convention': '[start,end)', 'lines': '1-based inclusive', 'cases': oracle,
    })
    write_json(ROOT / 'private/calibration_labels.json', {
        'cases': [case for case in oracle if case['split'] == 'calibration'],
    })
    files = {str(p.relative_to(ROOT)): sha(p.read_bytes())
             for p in sorted(ROOT.rglob('*')) if p.is_file()}
    write_json(ROOT / 'FREEZE.json', {
        'schema': 'v3-independent-freeze-1',
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'stage': 'PRE_V3_OUTPUTS', 'product_runtime_tests_models_host_executed': False,
        'execution_inputs': 'inputs/', 'private_oracle': 'private/oracle.json',
        'calibration_labels_separate': 'private/calibration_labels.json',
        'sha256': files, 'counts': {'calibration': 3, 'holdout': 4, 'legacy_controls': 2,
                                  'new_documents': 4, 'legacy_documents': 5},
        'freeze_manifest_excludes_self': True,
        'contract_A_B_review': 'PENDING_COORDINATOR_REQUEST',
        'outputs_review': 'NOT_RUN',
    })
    print('Frozen inputs, witnesses and private oracle. Manifest SHA256: ' + sha((ROOT / 'FREEZE.json').read_bytes()))


if __name__ == '__main__':
    main()
