"""One I.4 public-boundary measurement; no retries or algorithm changes."""
import hashlib
import json
import os
from pathlib import Path
import sys

from v2plan.next07_grounded_public import installed, _record_exception
from v2plan.next07_grounded_reference import fixture_inputs
from v2plan.next07_grounded_run import ROOT
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.project_context_quality.capture_public_context import capture_public_call


def _save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + '\n')


def _assess_capture(capture, trace, documents, value, error, *, partial=False):
    """Check the returned MCP bytes, not just the pre-handler packer trace."""
    payload = (capture or {}).get('public_payload') or {}
    sources = payload.get('sources') or []
    visible = '\n'.join(s.get('snippet', '') for s in sources)
    context_packet = payload.get('kind') == 'docs_context'
    cost = docs_context_budget_tokens(payload) if context_packet else None
    validations = trace.get('handler_validation') or []
    checks = {
        'returned_context': context_packet,
        'real_projection_called': trace.get('projection_calls', 0) > 0,
        'handler_validator_reached': bool(validations),
        'handler_validator_clean': bool(validations) and all(not v['errors'] for v in validations),
        'packer_validator_clean': trace.get('validator') == [],
        'restored': trace.get('restored') is True,
        'no_handler_exception': not trace.get('exceptions'),
        'whole_dto_800': cost is not None and cost <= 800,
        'source_cap_3': 0 < len(sources) <= 3,
        'no_answer_or_edit_credit': all(payload.get(k) is False for k in (
            'answer_supported', 'answer_available', 'edit_ready')),
        'retrieval_only': payload.get('support_status') == 'retrieval_only',
        'source_bytes': bool(sources) and all(
            s.get('path_or_url') in documents and bool(s.get('snippet'))
            and s['snippet'] in documents[s['path_or_url']] for s in sources),
        'default_with_owner': any(
            s.get('path_or_url') == 'default.md' and '# LeaseClient' in s.get('snippet', '')
            and f'The default timeout is {value} seconds.' in s.get('snippet', '') for s in sources),
    }
    if partial:
        checks['missing_exception_not_fabricated'] = error not in visible and all(
            s.get('path_or_url') != 'error.md' for s in sources)
    else:
        checks['exception_with_owner_and_condition'] = any(
            s.get('path_or_url') == 'error.md' and '# LeaseClient' in s.get('snippet', '')
            and f'An expired operation raises `{error}`.' in s.get('snippet', '') for s in sources)
    # A meaningful projection which fails a guard or returns insufficient is a
    # candidate failure, not automatically an environment/wiring blocker.
    valid = (trace.get('projection_calls', 0) > 0
             and not trace.get('exceptions') and trace.get('restored') is True)
    return dict(valid=valid, passed=valid and all(checks.values()), checks=checks,
        snippets=visible, cost=cost, pre_handler_cost=trace.get('budget'),
        source_count=len(sources), validator=validations,
        restored=trace.get('restored'), public_error=payload.get('error'))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args().out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    os.environ['DOCATLAS_OFFLINE'] = '1'
    _save(out / 'run.json', {
        'argv': sys.argv, 'python': sys.version, 'executable': sys.executable,
        'cwd': str(Path.cwd()), 'DOCATLAS_OFFLINE': os.environ['DOCATLAS_OFFLINE'],
        'code_sha256': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('next07_grounded_candidate.py', 'next07_grounded_public.py',
                         'next07_grounded_final_run.py')},
        'automatic_retries': 0, 'retention_and_full_suite': 'NOT_RUN by this target-local runner',
    })
    fixtures = fixture_inputs(ROOT)
    inputs = [(str(i), docs, question, value, error, False)
        for i, (value, error, docs, question) in enumerate(fixtures)]
    value, error, docs, question = fixtures[0]
    inputs.append(('partial', {p: text for p, text in docs.items() if p != 'error.md'},
        question, value, error, True))
    results = []
    for name, docs, question, value, error, partial in inputs:
        p = out / name
        p.mkdir()
        root = (p / 'corpus').resolve()
        native = candidate = None
        trace = {}
        try:
            write_project(root, docs)
            with isolated_service(p / 'state') as (service, config):
                index_project(service, config, root)
                request = dict(project_path=str(root), question=question, scope='project')
                native = capture_public_call(service, request)
                with installed(service, trace):
                    candidate = capture_public_call(service, request)
        except Exception as exc:
            _record_exception(trace, 'runner', exc)
        finally:
            for filename, data in [('N', native), ('C', candidate), ('trace', trace)]:
                _save(p / (filename + '.json'), data)
        result = _assess_capture(candidate, trace, docs, value, error, partial=partial)
        results.append(dict(case=name, **result))
        if not result['passed']:
            break
    verdict = 'VALIDATED_LOCAL_I4' if len(results) == 3 and all(r['passed'] for r in results) else (
        'REJECTED' if results and results[-1]['valid'] else 'BLOCKED_INVALID')
    summary = dict(verdict=verdict, cases=results, I5='NOT_RUN', I6='NOT_RUN',
        rollout='NOT_AUTHORIZED')
    _save(out / 'result.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if verdict == 'VALIDATED_LOCAL_I4' else 1 if verdict == 'REJECTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
