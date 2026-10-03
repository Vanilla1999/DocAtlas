"""Full native calls paired on one index; only original-read function changes."""
import argparse
import hashlib
from collections import Counter
import json
from pathlib import Path
import subprocess
from types import ModuleType
from unittest.mock import patch

from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.runtime import isolated_service, index_project, write_project, save_json
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.semantic import assess_context
from docmancer.docs.application import read_context_admission as admission


def run(output, baseline):
    output.mkdir(parents=True, exist_ok=False)
    source = subprocess.check_output(['git', 'show', baseline + ':docmancer/docs/application/read_context_admission.py'], text=True)
    old = ModuleType('docmancer.docs.application._baseline_read')
    old.__package__ = 'docmancer.docs.application'
    # dataclass resolves its defining module during construction.
    import sys
    sys.modules[old.__name__] = old
    exec(compile(source, '<pinned-baseline-read>', 'exec'), old.__dict__)
    current = admission.read_context_admission
    protocol, cases, manifest = load_protocol()
    rows = []
    for project in sorted({c['project_group'] for c in cases}):
        root = (output / project / 'corpus').resolve()
        write_project(root, documents_for(project, manifest))
        with isolated_service(output / project / 'state') as (service, config):
            index_project(service, config, root)
            for case in [c for c in cases if c['project_group'] == project]:
                row = {'case_id': case['id'], 'answerability': case['answerability'], 'arms': {}}
                for name, function in [('baseline', old.read_context_admission), ('candidate', current)]:
                    with patch.object(admission, 'read_context_admission', function):
                        payload, trace = observe_call(service, {'project_path': str(root), 'scope': 'project', 'question': case['question']})
                    save_json(output / project / (case['id'] + '-' + name + '.json'), [payload, trace])
                    row['arms'][name] = {'payload': payload, 'assessment': assess_context(case, payload, registry_for(project, manifest))}
                rows.append(row)
    summary = {'cases': len(rows), 'baseline_commit': baseline,
               'identical_payload_cases': sum(r['arms']['baseline']['payload'] == r['arms']['candidate']['payload'] for r in rows),
               'arms': {}, 'lost': [], 'changed_flags': []}
    for arm in ('baseline', 'candidate'):
        summary['arms'][arm] = {'supported': sum(r['arms'][arm]['assessment']['required_supported'] for r in rows),
            'claim_statuses': dict(Counter(c['status'] for r in rows for c in r['arms'][arm]['assessment']['claims'].values())),
            'negative_packets': [r['case_id'] for r in rows if r['answerability'] == 'unanswerable' and r['arms'][arm]['payload'].get('sources')]}
    for r in rows:
        a, b = r['arms']['baseline'], r['arms']['candidate']
        for cid, claim in a['assessment']['claims'].items():
            if claim['status'] == 'supported' and b['assessment']['claims'][cid]['status'] != 'supported':
                summary['lost'].append(r['case_id'] + ':' + cid)
        for flag in ('answer_supported', 'edit_ready', 'coverage_policy', 'support_status'):
            if a['payload'].get(flag) != b['payload'].get(flag):
                summary['changed_flags'].append([r['case_id'], flag])
    save_json(output / 'results.json', rows)
    save_json(output / 'summary.json', summary)
    save_json(output / 'protocol.json', protocol)
    save_json(output / 'provenance.json', {
        'baseline_commit': subprocess.check_output(['git', 'rev-parse', baseline], text=True).strip(),
        'candidate_read_sha256': hashlib.sha256(Path(admission.__file__).read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'paired full native calls, same index, service defaults unchanged',
        'validation': 'exposed frozen corpus; not unseen'})
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', required=True)
    args = parser.parse_args()
    run(args.output, args.baseline)
