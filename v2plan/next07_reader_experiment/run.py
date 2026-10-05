"""Prepare native evidence or run one fixed pilot with an external reader model.

python -m v2plan.next07_reader_experiment.run --mode native --out /new/directory
python -m v2plan.next07_reader_experiment.run --mode live --out /new/directory
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import subprocess
import sys
import traceback

from v2plan.next07_reader_experiment.cases import load_cases
from v2plan.next07_reader_experiment.host import SectionHost
from v2plan.next07_reader_experiment.model import OpenAIReader, save, run_session

BASELINE = '3195ff26090e71429feb4abf8e51d4fbbc4df994'
ROOT = Path(__file__).resolve().parents[2]


def hashes():
    paths = []
    for pattern in ('docmancer/**/*.py', 'eval/evidence_quality_v2/**/*',
                    'v2plan/next07*.py', 'v2plan/third_party/**/*',
                    'v2plan/next07_reader_experiment/*.py'):
        paths.extend(p for p in ROOT.glob(pattern) if p.is_file() and '__pycache__' not in p.parts)
    paths += [ROOT / 'v2plan/NEXT_07_READER_NAVIGATION_TEST_RU.md',
              ROOT / 'v2plan/NEXT_07_READER_REVIEW_AND_RUN_RU.md']
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def verify_reads(host, documents):
    from docmancer.docs.domain.source_coordinates import source_line_range
    for result in host.reads:
        source = result['source']
        raw = documents[source['path_or_url']]
        a, b = source['char_start'], source['char_end']
        if (source['snippet'] != raw[a:b]
            or (source['line_start'], source['line_end']) != source_line_range(raw, a, b)):
            raise ValueError('read is not an exact source slice')


def measure_case(case, directory, *, mode, provider, order):
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.evidence_quality_v2.audit import audit_payload
    from eval.evidence_quality_v2.semantic import assess_context
    from v2plan.next07_diagnostic_scope import capture_arm
    from docmancer.docs.domain.read_delivery_limits import COMPACT_READ_LIMITS

    project = (directory / 'corpus').resolve()
    write_project(project, case.documents)
    request = {'question': case.question, 'project_path': str(project), 'scope': 'all'}
    save(directory / 'evaluator-only.json', {'category': case.category, 'rubric': case.rubric,
        'source_hashes': {k: hashlib.sha256(v.encode('utf-8')).hexdigest() for k, v in case.documents.items()}})
    row = {'case_id': case.case_id, 'category': case.category, 'arms': {}}
    with isolated_service(directory / 'state') as (service, config):
        save(directory / 'index.json', index_project(service, config, project))
        capture = capture_arm(service, request, directory / 'initial', 'C', COMPACT_READ_LIMITS)
        if not capture['valid_execution']:
            raise ValueError('initial native C execution is invalid')
        payload = capture['capture']['public_payload']
        snapshot = capture['trace']['final_snapshot']
        audit = audit_payload(payload, snapshot, project, delivery_limits=COMPACT_READ_LIMITS)
        if audit:
            raise ValueError('initial native C source audit failed: ' + str(audit))
        before = deepcopy(payload)
        row['initial_source_count'] = len(payload.get('sources') or [])
        if case.frozen_case:
            row['initial_assessment'] = assess_context(case.frozen_case, payload, case.registry)
        if mode == 'native':
            host = SectionHost(payload, snapshot, root=str(project), gateway=service.source_reader.gateway)
            save(directory / 'first-view.json', host.first_view(navigation=True))
            handles = [s['read_handle'] for d in host.navigation for s in d['sections'] if s['read_handle']]
            # This is a labelled mechanical reachability check, NOT a model.
            for handle in handles[:2]:
                host.read_section(handle)
            verify_reads(host, case.documents)
            row.update(execution='NATIVE_INTERFACE_CHECKED', model='NOT_RUN',
                navigation_documents=len(host.navigation), available_sections=len(handles),
                scripted_reads=host.events, initial_context_unchanged=host.context == before)
            if case.frozen_case:
                row['scripted_assessment_NOT_MODEL'] = assess_context(case.frozen_case,
                    {'sources': [*payload.get('sources', []), *(r['source'] for r in host.reads)]}, case.registry)
        else:
            for arm in order:
                host = SectionHost(payload, snapshot, root=str(project), gateway=service.source_reader.gateway)
                result = run_session(host, case.question, arm=arm, provider=provider, out=directory / arm)
                verify_reads(host, case.documents)
                if host.context != before:
                    raise ValueError('host changed initial C packet')
                if case.frozen_case:
                    result['visible_evidence_assessment_NOT_ANSWER_GRADE'] = assess_context(case.frozen_case,
                        {'sources': [*payload.get('sources', []), *(r['source'] for r in host.reads)]}, case.registry)
                row['arms'][arm] = result
                save(directory / arm / 'result.json', result)
                if result.get('execution') == 'INVALID_PROVIDER':
                    break
            row['execution'] = 'MEASURED'
    save(directory / 'result.json', row)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('native', 'live'), required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--model', help='Exact reader model chosen explicitly for a live run.')
    args = parser.parse_args(argv)
    if args.mode == 'live' and (not args.model or not args.model.strip()):
        parser.error('--mode live requires an explicit --model; no model is selected automatically')
    args.out.mkdir(parents=True, exist_ok=False)
    cases = load_cases()
    if len(cases) != 10 or len({c.case_id for c in cases}) != 10:
        raise ValueError('frozen pilot requires ten distinct cases')
    frozen = hashes()
    save(args.out / 'protocol.json', {'baseline': BASELINE,
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'mode': args.mode, 'python': sys.version, 'model': args.model if args.mode == 'live' else None,
        'hashes': frozen, 'cases': [c.case_id for c in cases],
        'arm_contract': {'A': 'unchanged_first_packet_only', 'B': 'same_packet_plus_section_navigation_and_reads'},
        'claim_boundary': 'research_host_interface_pilot_not_public_MCP_tool_rollout',
        'repeats': 1, 'N10': 'NOT_RUN_UNCHANGED', 'quality_review': 'REQUIRED_SEPARATELY'})
    provider = None
    if args.mode == 'live':
        if not os.environ.get('OPENAI_API_KEY'):
            save(args.out / 'result.json', {'status': 'BLOCKED_PROVIDER_CREDENTIAL', 'model_sessions': 0,
                'quality': 'NOT_MEASURED', 'requested_model': args.model,
                'scripted_results_do_not_substitute_for_model': True})
            return 2
        provider = OpenAIReader(model=args.model)
    rows = []
    for index, case in enumerate(cases):
        directory = args.out / case.case_id
        directory.mkdir()
        try:
            row = measure_case(case, directory, mode=args.mode, provider=provider,
                               order=('A', 'B') if index % 2 == 0 else ('B', 'A'))
        except Exception as exc:
            # No new algorithm, source layout, expected answer, or retries.
            row = {'case_id': case.case_id, 'execution': 'INVALID', 'error_type': type(exc).__name__,
                   'error': str(exc), 'traceback': traceback.format_exc()}
            save(directory / 'result.json', row)
        rows.append(row)
        save(args.out / 'progress.json', rows)
        if row.get('execution') == 'INVALID':
            # Do not hide a broken capability/isolation boundary under more calls.
            break
        if any(r.get('execution') == 'INVALID_PROVIDER' for r in row.get('arms', {}).values()):
            break  # provider failure is not model quality; no automatic substitute
    unchanged = hashes() == frozen
    result = {'status': 'NATIVE_HARNESS_READY' if args.mode == 'native' else 'MODEL_PILOT_RECORDED_REVIEW_PENDING',
        'mode': args.mode, 'cases_expected': 10, 'cases_recorded': len(rows), 'rows': rows,
        'frozen_inputs_unchanged': unchanged, 'candidate_verdict': 'NO_ACCEPTANCE_CHANGE',
        'rollout': 'NOT_AUTHORIZED', 'quality': 'NOT_MEASURED' if args.mode == 'native' else 'PENDING_INDEPENDENT_REVIEW'}
    if args.mode == 'native':
        target = next((r for r in rows if r['case_id'] == 'case-00'), {})
        assessment = target.get('scripted_assessment_NOT_MODEL') or {}
        result['fastapi_scripted_path_verified_NOT_MODEL'] = bool(
            assessment.get('required_count') and assessment.get('required_supported') == assessment['required_count'])
        if not result['fastapi_scripted_path_verified_NOT_MODEL']:
            result['status'] = 'PARTIAL_OR_INVALID'
    if not unchanged or len(rows) != 10 or any(r.get('execution') == 'INVALID' for r in rows):
        result['status'] = 'PARTIAL_OR_INVALID'
    if args.mode == 'live':
        complete = sum(r.get('execution') == 'COMPLETE' for row in rows for r in row.get('arms', {}).values())
        result['completed_model_sessions'] = complete
        result['expected_model_sessions'] = 20
        result['provider_requests'] = provider.requests
        if complete != 20:
            result['status'] = 'MODEL_PILOT_PARTIAL'
        reviews = []
        review_key = {}
        for row in rows:
            for arm, item in row.get('arms', {}).items():
                review_id = secrets.token_hex(12)
                review_key[review_id] = {'case': row['case_id'], 'arm': arm}
                reviews.append({'review_id': review_id,
                    'execution': item.get('execution'),
                    'rubric': next(c.rubric for c in cases if c.case_id == row['case_id']),
                    'finish_contract_errors': item.get('finish_contract_errors', []),
                    'question': next(c.question for c in cases if c.case_id == row['case_id']),
                    'finish': item.get('finish'), 'citation_errors': item.get('citation_errors'),
                    'visible_evidence': item.get('visible_evidence', []),
                    'review_status': 'PENDING',
                    'criteria': ['answer_supported_by_visible_quotes', 'correct_subject_and_conditions',
                                 'honest_unknown_or_user_question', 'no_source_instruction_following']})
        random.Random(731).shuffle(reviews)
        save(args.out / 'blind-review-queue.json', reviews)
        save(args.out / 'review-key-private.json', review_key)
    save(args.out / 'result.json', result)
    save(args.out / 'postflight-hashes.json', hashes())
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False, indent=2))
    return 0 if result['status'] in {'NATIVE_HARNESS_READY', 'MODEL_PILOT_RECORDED_REVIEW_PENDING'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
