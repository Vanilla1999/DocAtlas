"""Separate verbatim/snapshot checks on saved instrumented calls; no retrieval."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from eval.evidence_quality_v2.audit import audit_payload

REPO = Path(__file__).resolve().parents[4]


def main(output):
    rows = []
    for path in sorted((REPO / 'roadmap/search-quality-2026-10-01/audit/raw/traces/external48').glob('*.json.gz')):
        trace = json.loads(gzip.decompress(path.read_bytes()))
        project = path.name.split('-')[0]
        for index, projection in enumerate(trace['stages']['projector_outputs']):
            errors = audit_payload(projection['payload'], projection['snapshot'],
                                   REPO / 'eval/evidence_quality_v2/sources' / project)
            rows.append({'id': path.name.removesuffix('.json.gz'), 'projection': index,
                         'trace_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'errors': errors})
    value = {'checks': len(rows), 'violations': sum(bool(row['errors']) for row in rows), 'rows': rows,
             'digest_policy': 'Snapshot evidence-material binding via canonical validator; raw file SHA is not content_sha256'}
    with output.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')
    print(f"{value['checks']} saved projection checks; {value['violations']} violations")
    assert value['checks'] == 48 and value['violations'] == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    main(parser.parse_args().output)
