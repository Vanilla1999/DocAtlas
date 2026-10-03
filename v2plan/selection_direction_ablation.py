"""Isolate no_new_direction removal in memory; never modify runtime files."""
import argparse
import hashlib
import inspect
from pathlib import Path
from unittest.mock import patch

from docmancer.docs.application import _docs_context_projection_core as core
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.run import documents_for, load_protocol, registry_for
from eval.evidence_quality_v2.runtime import index_project, isolated_service, save_json, write_project
from eval.evidence_quality_v2.semantic import assess_context
from v2plan.lookup_gap_probe import CASES, KNOWN, QUESTION


def candidate_function():
    source = inspect.getsource(core.project_docs_context)
    start = source.index('        if sources and not (new_components or\n')
    end = source.index('        required_ids = qualified_ids & required_query_id_set', start)
    removed = source[start:end]
    assert removed.count('continue') == 1 and "'no_new_direction'" in removed
    namespace = dict(core.__dict__)
    exec(compile(source[:start] + source[end:], '<no-new-direction-ablation>', 'exec'), namespace)
    return namespace['project_docs_context'], removed


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    baseline = core.project_docs_context
    candidate, removed = candidate_function()
    protocol, cases, manifest = load_protocol()
    groups = {group: (documents_for(group, manifest), [c for c in cases if c['project_group'] == group])
              for group in sorted({c['project_group'] for c in cases})}
    for name, sentence in CASES.items():
        groups['synthetic-' + name] = (
            {'defaults.md': '# Guide\n\n' + KNOWN + '\n',
             'deployment.md': '# Guide\n\n' + sentence + '\n'},
            [{'id': name, 'question': QUESTION}])
    results = []
    for group, (documents, group_cases) in groups.items():
        root = (output / group / 'corpus').resolve()
        write_project(root, documents)
        with isolated_service(output / group / 'state') as (service, config):
            save_json(output / group / 'ingest.json', index_project(service, config, root))
            for case in group_cases:
                row = {'case': case['id'], 'synthetic': group.startswith('synthetic-'), 'arms': {}}
                for arm, function in [('baseline', baseline), ('ablation', candidate)]:
                    with patch.object(core, 'project_docs_context', function):
                        payload, trace = observe_call(service, {
                            'question': case['question'], 'scope': 'project', 'project_path': str(root)})
                    save_json(output / group / (case['id'] + '-' + arm + '.json'), {'payload': payload, 'trace': trace})
                    assessment = None if row['synthetic'] else assess_context(case, payload, registry_for(group, manifest))
                    row['arms'][arm] = {'payload': payload, 'assessment': assessment}
                results.append(row)
    summary = {'cases': len(results), 'identical_payloads': 0, 'lost_claims': [], 'gained_claims': [],
               'changed_flags': [], 'negative_packets': {}, 'supported': {}, 'synthetic': [],
               'changed_payload_cases': []}
    for arm in ('baseline', 'ablation'):
        summary['supported'][arm] = sum(r['arms'][arm]['assessment']['required_supported'] for r in results if not r['synthetic'])
        negatives = {c['id'] for c in cases if c['answerability'] == 'unanswerable'}
        summary['negative_packets'][arm] = [r['case'] for r in results if not r['synthetic'] and r['case'] in negatives and r['arms'][arm]['payload'].get('sources')]
    for row in results:
        a, b = (row['arms'][arm] for arm in ('baseline', 'ablation'))
        equal = a['payload'] == b['payload']
        summary['identical_payloads'] += equal
        if not equal:
            summary['changed_payload_cases'].append(row['case'])
        for flag in ('answer_supported', 'edit_ready', 'support_status', 'coverage_policy'):
            if a['payload'].get(flag) != b['payload'].get(flag):
                summary['changed_flags'].append([row['case'], flag])
        if row['synthetic']:
            summary['synthetic'].append({'case': row['case'], **{
                arm: [s['snippet'] for s in row['arms'][arm]['payload'].get('sources', [])]
                for arm in ('baseline', 'ablation')}})
        else:
            for cid, claim in a['assessment']['claims'].items():
                after = b['assessment']['claims'][cid]['status']
                if claim['status'] == 'supported' and after != 'supported':
                    summary['lost_claims'].append([row['case'], cid])
                if claim['status'] != 'supported' and after == 'supported':
                    summary['gained_claims'].append([row['case'], cid])
    save_json(output / 'results.json', results)
    save_json(output / 'summary.json', summary)
    save_json(output / 'provenance.json', {'removed_block': removed, 'protocol': protocol,
              'core_sha256': hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest()})
    print(summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
