"""Four synthetic same-question lookup pairs; native runtime remains unchanged."""
import argparse
from pathlib import Path
from unittest.mock import patch

from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.runtime import index_project, isolated_service, save_json, write_project


QUESTION = ('What is OrbitClient default timeout and what timeout '
            'is configured for OrbitClient in production?')
KNOWN = 'OrbitClient default timeout is 5 seconds.'
LOOKUP = 'OrbitClient timeout configured in production'
CASES = {
    'both': 'OrbitClient timeout configured in production is 12 seconds.',
    'absent': 'Production deployment uses three replicas.',
    'wrong': 'NovaClient timeout configured in staging is 12 seconds.',
    'partial': 'OrbitClient timeout configured in production is managed by the deployment owner.',
}


def run(output):
    from docmancer.docs.application.projection_decision_trace import ProjectionDecisionTrace
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, sentence in CASES.items():
        root = (output / name / 'corpus').resolve()
        write_project(root, {'defaults.md': '# Guide\n\n' + KNOWN + '\n',
                             'deployment.md': '# Guide\n\n' + sentence + '\n'})
        with isolated_service(output / name / 'state') as (service, config):
            save_json(output / name / 'ingest.json', index_project(service, config, root))
            for arm in ('original', 'focused'):
                request = {'project_path': str(root), 'scope': 'project', 'question': QUESTION}
                if arm == 'focused':
                    request['lookup_queries'] = [LOOKUP]
                decisions = []
                original_record = ProjectionDecisionTrace.record

                def record(instance, stage, decision, reason, candidate, variant=None, **kwargs):
                    decisions.append({'stage': stage, 'decision': decision, 'reason': reason,
                                      'candidate_path': candidate.get('path_or_url', candidate.get('path'))
                                      if isinstance(candidate, dict) else None,
                                      'snippet': (variant or {}).get('snippet')})
                    return original_record(instance, stage, decision, reason, candidate, variant, **kwargs)

                with patch.object(ProjectionDecisionTrace, 'record', record):
                    payload, trace = observe_call(service, request)
                trace['executed_decisions'] = decisions
                save_json(output / name / (arm + '.json'), {'request': request, 'payload': payload, 'trace': trace})
                rows.append({'case': name, 'arm': arm, 'sources': payload.get('sources', []),
                             'flags': {k: v for k, v in payload.items() if k != 'sources'}})
    save_json(output / 'summary.json', rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
