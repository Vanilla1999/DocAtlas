"""Frozen public N10 control; stop at a substantive forbidden packet."""
import argparse
import json
import os
from pathlib import Path

from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.project_context_quality.capture_public_context import capture_public_call
from v2plan.next07_grounded_public import installed
from tests.docs.test_read_context_admission_boundary import QUESTION, BODY


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args().out
    out.mkdir(exist_ok=False)
    os.environ['DOCATLAS_OFFLINE'] = '1'
    negative = '# storage retention behavior\n\nUnrelated network details.'
    protocol = dict(control='N10', question=QUESTION, positive=BODY, negative=negative,
        expectation='working positive returns context; frozen negative returns no sources',
        node='tests/docs/test_read_context_admission_boundary.py::test_local_topic_witness_rejects_heading_echo_and_scattered_terms[# storage retention behavior\n\nUnrelated network details.]',
        classification='exposed development/regression; not unseen',
        stop='first substantive forbidden packet; no algorithm/expectation changes')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    results = []
    for name, body in [('positive', BODY), ('negative', negative)]:
        p = out / name
        p.mkdir()
        root = (p / 'corpus').resolve()
        write_project(root, {'docs/guide.md': '# Guide\n\n' + body + '\n'})
        with isolated_service(p / 'state') as (service, config):
            index_project(service, config, root)
            request = dict(project_path=str(root), question=QUESTION, scope='project')
            n = capture_public_call(service, request)
            trace = {}
            with installed(service, trace):
                c = capture_public_call(service, request)
            for key, value in [('N', n), ('C', c), ('trace', trace)]:
                (p / (key + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))
            payload = c['public_payload']
            valid = bool(trace.get('projection_calls')) and not payload.get('error') and not trace.get('validator')
            sources = payload.get('sources', [])
            passed = valid and (bool(sources) if name == 'positive' else not sources)
            results.append(dict(case=name, valid=valid, passed=passed, sources=sources,
                handler_validation=trace.get('handler_validation'), restored=trace['restored']))
            if not passed:
                break
    verdict = 'PASS_N10' if len(results) == 2 and all(r['passed'] for r in results) else (
        'REJECTED' if results[-1]['valid'] else 'BLOCKED_INVALID')
    result = dict(verdict=verdict, cases=results)
    (out / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if verdict == 'PASS_N10' else 1


if __name__ == '__main__':
    raise SystemExit(main())
