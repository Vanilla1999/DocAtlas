"""One frozen public-boundary I.4 measurement; stop on substantive failure."""
import json
import os
from pathlib import Path
from v2plan.next07_grounded_public import installed
from v2plan.next07_grounded_reference import fixture_inputs
from v2plan.next07_grounded_run import ROOT
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.project_context_quality.capture_public_context import capture_public_call


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args().out
    out.mkdir(exist_ok=False)
    os.environ['DOCATLAS_OFFLINE'] = '1'
    fixtures = fixture_inputs(ROOT)
    inputs = [(str(i), docs, question, ['17 seconds', 'LeaseExpired'] if i == 0 else
        ['29 seconds', 'WaitExpired']) for i, (_, _, docs, question) in enumerate(fixtures)]
    _, _, docs, question = fixtures[0]
    inputs.append(('partial', {p: text for p, text in docs.items() if p != 'error.md'}, question, ['17 seconds']))
    results = []
    for name, docs, question, expected in inputs:
        p = out / name
        p.mkdir()
        root = (p / 'corpus').resolve()
        write_project(root, docs)
        with isolated_service(p / 'state') as (service, config):
            index_project(service, config, root)
            request = dict(project_path=str(root), question=question, scope='project')
            native = capture_public_call(service, request)
            trace = {}
            with installed(service, trace):
                candidate = capture_public_call(service, request)
            for filename, data in [('N', native), ('C', candidate), ('trace', trace)]:
                (p / (filename + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
            payload = candidate['public_payload']
            visible = '\n'.join(s['snippet'] for s in payload.get('sources', []))
            valid = payload.get('kind') == 'docs_context' and trace.get('projection_calls', 0) > 0
            passed = valid and all(token in visible for token in expected) and not trace['validator']
            results.append(dict(case=name, valid=valid, passed=passed, snippets=visible,
                cost=trace.get('budget'), source_count=len(payload.get('sources', [])),
                validator=trace.get('validator'), restored=trace['restored']))
            if not passed:
                break
    verdict = 'VALIDATED_LOCAL_I4' if len(results) == 3 and all(r['passed'] for r in results) else (
        'REJECTED' if results[-1]['valid'] else 'BLOCKED_INVALID')
    (out / 'result.json').write_text(json.dumps(dict(verdict=verdict, cases=results), indent=2))
    print(json.dumps(dict(verdict=verdict, cases=results), indent=2))


if __name__ == '__main__':
    main()
