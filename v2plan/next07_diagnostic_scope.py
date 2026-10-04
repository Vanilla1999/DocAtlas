"""Diagnostic only: unchanged C, stop on invalid execution, not quality failure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from eval.evidence_quality_v2.run import load_protocol, documents_for
from eval.evidence_quality_v2.runtime import isolated_service, index_project, write_project
from eval.project_context_quality.capture_public_context import capture_public_call
from tests.docs.test_read_context_admission_boundary import QUESTION, BODY
from v2plan.next07_grounded_public import installed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=False)
    os.environ['DOCATLAS_OFFLINE'] = '1'
    def save(name, value):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')
    protocol, cases, manifest = load_protocol()
    assert len(cases) == 80
    files = [Path('v2plan/next07_grounded_candidate.py'), Path('v2plan/next07_grounded_public.py'),
        Path('v2plan/next07_grounded_final_run.py'), Path('eval/evidence_quality_v2/cases.json'),
        Path('eval/evidence_quality_v2/protocol.json'), Path('eval/evidence_quality_v2/source-manifest.json'),
        *Path('v2plan/third_party/grounded-3.2.1').rglob('*.py')]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    save('protocol.json', dict(status='DIAGNOSTIC_ONLY', candidate_verdict='REJECTED_N10',
        head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        hashes=hashes, corpus=manifest, frozen_protocol=protocol,
        corpus_source_hashes={project: {path: hashlib.sha256(text.encode()).hexdigest()
            for path, text in documents_for(project, manifest).items()}
            for project in sorted({c['project_group'] for c in cases})},
        controls_order=['working_positive', 'N1_module_request'],
        input=dict(documents={'docs/guide.md': '# Guide\n\n' + BODY + '\n'}, question=QUESTION),
        mutation={'module': 'nonexistent-diagnostic-module'},
        quality_failure='record and continue', invalid_execution='STOP',
        replay_scope='all, unchanged from frozen run.py',
        I4='REUSED_NOT_RERUN', G='REUSED_NOT_RERUN'))
    (out / 'baseline.patch').write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'HEAD']))
    (out / 'baseline-status.txt').write_bytes(subprocess.check_output(['git', 'status', '--short']))
    root = (out / 'corpus').resolve()
    write_project(root, {'docs/guide.md': '# Guide\n\n' + BODY + '\n'})
    results = []
    with isolated_service(out / 'state') as (service, config):
        save('index.json', index_project(service, config, root))
        for name, extra in [('working_positive', {}), ('N1_module_request', {'module': 'nonexistent-diagnostic-module'})]:
            request = dict(project_path=str(root), scope='project', question=QUESTION, **extra)
            native = capture_public_call(service, request)
            trace = {}
            with installed(service, trace):
                candidate = capture_public_call(service, request)
            save(name + '-N.json', native)
            save(name + '-C.json', candidate)
            save(name + '-trace.json', trace)
            invalid = bool(trace.get('exceptions')) or not trace['restored'] or candidate['public_payload'].get('status') == 'failed'
            results.append(dict(case=name, invalid=invalid, restored=trace['restored'],
                sources=candidate['public_payload'].get('sources', [])))
            if invalid:
                break
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    save('result.json', dict(candidate_verdict='REJECTED_N10_UNCHANGED', diagnostic_status='STOP_INVALID'
        if results[-1]['invalid'] else 'SCOPE_CONTROL_COMPLETED', cases=results,
        immutable_hashes_verified=True, paired_80='NOT_RUN_AFTER_TECHNICAL_STOP',
        historical_49='NOT_RUN', partial_retention='NOT_RUN',
        losses='NOT_MEASURED_NOT_EMPTY_SET', remaining_controls='NOT_RUN_AFTER_TECHNICAL_STOP'))
    print((out / 'result.json').read_text())
    return int(results[-1]['invalid'])


if __name__ == '__main__':
    raise SystemExit(main())
