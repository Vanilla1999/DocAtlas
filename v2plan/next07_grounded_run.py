"""Exclusive, read-only I.0 capture for the Grounded-first experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)

    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT)

    head = git('rev-parse', 'HEAD').decode().strip()
    branch = git('branch', '--show-current').decode().strip()
    assert branch == 'next07-feasibility-audit'
    patch = git('diff', '--binary', 'HEAD')
    (out / 'baseline.patch').write_bytes(patch)
    (out / 'baseline-status.txt').write_bytes(git('status', '--short'))
    inputs = [p.decode() for p in git('ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p]
    inputs = [p for p in inputs if not (ROOT / p).resolve().is_relative_to(out)]
    input_hashes = {p: sha((ROOT / p).read_bytes()) for p in inputs if (ROOT / p).is_file()}
    # Only executable untracked inputs belong in the baseline checkout. Historical
    # output directories are hashed, not copied into a new experimental corpus.
    with tarfile.open(out / 'untracked-inputs.tar.gz', 'w:gz') as archive:
        for p in inputs:
            if p.endswith('.py'):
                archive.add(ROOT / p, arcname=p, recursive=False)
    with (out / 'baseline-head.tar.gz').open('wb') as stream:
        subprocess.run(['git', 'archive', '--format=tar.gz', head], cwd=ROOT, stdout=stream, check=True)
    baseline = Path('/tmp/opencode') / ('next07-' + out.name + '-baseline')
    baseline.mkdir(exist_ok=False)
    for name in ('baseline-head.tar.gz', 'untracked-inputs.tar.gz'):
        with tarfile.open(out / name) as archive:
            archive.extractall(baseline, filter='data')
    subprocess.run(['git', 'apply', str(out / 'baseline.patch')], cwd=baseline, check=True)
    py = ROOT / '.venv/bin/python'
    assert py.is_file()
    collection = subprocess.run([str(py), '-m', 'pytest', '--collect-only', '-q',
        'tests/docs/test_read_context_admission_boundary.py'], cwd=baseline, capture_output=True, text=True)
    save(out / 'collection.json', {'command': collection.args, 'returncode': collection.returncode,
        'stdout': collection.stdout, 'stderr': collection.stderr})
    assert collection.returncode == 0
    nodes = [line for line in collection.stdout.splitlines() if line.startswith('tests/') and '::' in line]
    allow = []
    for node in nodes:
        if ('test_added_identity_or_condition_does_not_preserve_context[When ' in node
                or any('test_local_topic_witness_rejects_heading_echo_and_scattered_terms[' + body + ']' in node
                    for body in ('storage retention details are documented.',
                        'storage is documented. retention is documented. behavior is documented.',
                        'storage behavior retention is documented.'))):
            allow.append({'node_id': node, 'old_obligation': 'empty read context without condition proof or lexical floor',
                'new_expectation': 'source-bound context may be delivered; no applicability/support/edit credit',
                'reason': 'approved isolated read-policy delta',
                'remaining_guards': 'source/security/identity/scope/version/freshness/snapshot/span/exact and known mismatch'})
    save(out / 'policy-delta.json', {'allowlist': allow, 'other_nodes': [n for n in nodes if n not in {a['node_id'] for a in allow}],
        'frozen_80_expectations': 'unchanged; conflicts are not PASS', 'status': 'frozen before candidate'})
    claims_path = ROOT / 'v2plan/artifacts/loss-attribution/claims.json'
    claims = json.loads(claims_path.read_text())
    supported = sorted({(r['case_id'], r['claim_id']) for r in claims if r.get('baseline_status') == 'supported'})
    provenance = json.loads((ROOT / 'v2plan/artifacts/corrected-owner-1500/provenance.json').read_text())
    historical = Path(provenance['input']) / 'results.json'
    archive_ok = historical.is_file() and sha(historical.read_bytes()) == provenance['input_results_sha256']
    save(out / 'historical-claims.json', {'pairs': supported, 'count': len(supported),
        'ledger': str(claims_path.relative_to(ROOT)), 'ledger_sha256': sha(claims_path.read_bytes()),
        'original_archive': str(historical), 'original_archive_hash_verified': archive_ok,
        'retention': 'NOT_RUN; extraction is not retention acceptance'})
    if archive_ok:
        with tarfile.open(out / 'historical-results.tar.gz', 'w:gz') as archive:
            archive.add(historical, arcname='results.json')
            archive.add(historical.parent / 'protocol.json', arcname='protocol.json')
    plan = (ROOT / 'v2plan/NEXT_07_READ_PIPELINE_OWNERSHIP_RU.md').read_text()
    (out / 'frozen-plan.md').write_text(plan)
    fixture = ROOT / 'tests/docs/test_need_local_admission.py'
    versions = {name: subprocess.check_output(command, text=True).strip() for name, command in {
        'python': [str(py), '--version'], 'node': ['node', '--version'], 'npm': ['npm', '--version']}.items()}
    save(out / 'protocol.json', {'step': 'I.0', 'question': 'What is LeaseClient default timeout duration for requests and which exception is raised when an operation expires?',
        'parameters': [[17, 'LeaseExpired'], [29, 'WaitExpired']], 'fixture_path': str(fixture.relative_to(ROOT)),
        'fixture_sha256': sha(fixture.read_bytes()), 'python': str(py), 'versions': versions,
        'grounded': {'package': '@arabold/docs-mcp-server', 'version': '3.2.1', 'source_sha': 'f2938c47bb8937c650f0d5ddb614f867773b29f4'},
        'candidate': {'structural_chars': [500, 1500, 5000], 'tokenizer': 'porter unicode61',
            'bm25': [10.0, 1.0, 5.0, 1.0], 'pool_max': 20, 'packer': 'whole-window first-fit; no clipping/rescue',
            'admission_budget': 800, 'source_rows': 3, 'runtime_implementation': 'NOT_RUN'},
        'controls_and_criteria': 'frozen-plan.md sections I.0–I.6 and 4; no changes allowed',
        'caps_and_required_commands': 'Candidate-specific inventory NOT_RUN; must be completed before I.2, no cap increase authorized',
        'isolation': {'checkout': str(baseline), 'benchmark': 'local corpus only; no API keys/embeddings/telemetry'},
        'historical_inventory': 'historical-claims.json', 'policy_delta': 'policy-delta.json'})
    save(out / 'provenance.json', {'head': head, 'branch': branch, 'patch_sha256': sha(patch),
        'untracked_sha256': input_hashes, 'baseline_checkout': str(baseline), 'versions': versions,
        'runtime_sha256': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted((ROOT / 'docmancer').rglob('*.py'))}})
    save(out / 'i0-result.json', {'verdict': 'DONE' if archive_ok and len(supported) == 49 else 'BLOCKED',
        'historical_pairs': len(supported), 'archive_hash_verified': archive_ok,
        'policy_delta_count': len(allow), 'candidate_not_implemented': True})
    print(out)


if __name__ == '__main__':
    main()
