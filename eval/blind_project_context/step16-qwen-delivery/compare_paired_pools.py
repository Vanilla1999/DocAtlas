"""Compare persisted label-free manifests from actual paired MCP calls."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load(path):
    groups = defaultdict(list)
    for line in path.open(encoding='utf-8'):
        event = json.loads(line)
        if event.get('event') != 'pool_manifest':
            continue
        key = (event['original_question'], json.dumps(event['budget'], sort_keys=True),
               event['portion'], event['stage'])
        for field in ('normalized_rows', 'normalized_snapshots'):
            if digest(event[field]) != event[field + '_sha256']:
                raise ValueError(f'corrupt manifest: {path} {field}')
        # Hash-check each full manifest, then retain only comparison evidence.
        # Full source snapshots stay on disk; holding all of them can exhaust RAM.
        groups[key].append({field: event[field] for field in
                            ('normalized_rows_sha256', 'normalized_snapshots_sha256', 'row_count')})
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('a', type=Path)
    parser.add_argument('b', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    a, b = load(args.a), load(args.b)
    comparisons = []
    for key in sorted(set(a) | set(b)):
        left, right = a.get(key, []), b.get(key, [])
        equal = len(left) == len(right) and bool(left)
        pairs = []
        for x, y in zip(left, right):
            checks = {field: x[field] == y[field] for field in
                      ('normalized_rows_sha256', 'normalized_snapshots_sha256', 'row_count')}
            equal = equal and all(checks.values())
            pairs.append({'checks': checks, 'a_rows': x['row_count'], 'b_rows': y['row_count']})
        comparisons.append({'question_sha256': hashlib.sha256(key[0].encode()).hexdigest(),
                            'budget': json.loads(key[1]), 'portion': key[2], 'stage': key[3],
                            'a_manifests': len(left), 'b_manifests': len(right),
                            'equal': equal, 'pairs': pairs})
    stages = {key[3] for key in a} & {key[3] for key in b}
    valid = bool(comparisons) and stages == {'raw_checked', 'post_prune', 'eligible'} and all(c['equal'] for c in comparisons)
    result = {'same_checked_pools_verified': valid, 'comparisons': comparisons,
              'limitations': 'Pool equality only; not delivery, model accuracy, source authorization or final budget validation.'}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'same_checked_pools_verified': valid, 'stage_comparisons': len(comparisons)}))
    return 0 if valid else 2


if __name__ == '__main__':
    raise SystemExit(main())
