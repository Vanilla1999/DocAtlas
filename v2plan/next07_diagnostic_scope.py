"""Complete paired corpus diagnostics. Never promotes the rejected candidate.

Use --compact-read to evaluate the caller-owned uncapped output policy. The
source corpus, assessor and all query/answer labels remain external to selection.
Each arm is saved before assessment. Quality failures do not stop other cases;
a failed restoration or changed frozen input does stop the run.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'v2plan/artifacts/next07/grounded-first/20261004-1b1cf6b7/historical-claims.json'
HISTORY_SHA256 = '5e581e456b500eeed5fb33ff49df12857fe4d51e0e8886b3e705d4ab1fba5217'


class IsolationError(RuntimeError):
    pass


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    temporary.replace(path)


def fingerprint(paths):
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(paths)) if path.is_file()}


def validate_request(request, schema):
    """The dispatcher also forbids undeclared keys; do not infer service kwargs."""
    from jsonschema import Draft202012Validator
    unknown = sorted(set(request) - set(schema.get('properties', {})))
    errors = ['unknown public fields: ' + ', '.join(unknown)] if unknown else []
    errors.extend(error.message for error in Draft202012Validator(schema).iter_errors(request))
    return errors


def ledger_pairs(value):
    pairs = value.get('pairs')
    if not isinstance(pairs, list) or any(
            not isinstance(row, list) or len(row) != 2
            or any(not isinstance(item, str) or not item for item in row) for row in pairs):
        raise ValueError('ledger requires explicit nonempty [case_id, claim_id] pairs')
    result = {tuple(row) for row in pairs}
    if len(result) != len(pairs) or value.get('count', len(pairs)) != len(result):
        raise ValueError('duplicate IDs or inconsistent ledger count')
    return result


def _supported(record):
    assessment = record.get('assessment') or {}
    claims = {**assessment.get('claims', {}), **assessment.get('optional_claims', {})}
    return {key for key, result in claims.items() if result.get('status') == 'supported'}


def summarize(rows, expected_ids, historical=None):
    """Execution validity, recognized support and integrity are separate axes."""
    expected = set(expected_ids)
    by_id = {row['case_id']: row for row in rows}
    if len(by_id) != len(rows) or not set(by_id) <= expected:
        raise ValueError('duplicate or unexpected corpus case')
    valid = {cid for cid, row in by_id.items()
             if all(row[arm].get('valid_execution') and row[arm].get('assessment') is not None
                    for arm in ('N', 'C'))}
    n_ids = {(cid, claim) for cid in valid for claim in _supported(by_id[cid]['N'])}
    c_ids = {(cid, claim) for cid in valid for claim in _supported(by_id[cid]['C'])}
    integrity_failures = {arm: sorted(cid for cid, row in by_id.items() if row[arm].get('audit_errors'))
                          for arm in ('N', 'C')}
    result = {
        'diagnostic_status': 'CORPUS_DIAGNOSTICS_COMPLETE' if valid == expected else 'DIAGNOSTICS_PARTIAL',
        'candidate_verdict': 'REJECTED_N10_UNCHANGED', 'rollout': 'NOT_AUTHORIZED',
        'expected_pairs': len(expected), 'recorded_pairs': len(rows), 'valid_pairs': len(valid),
        'invalid_or_unmeasured_pairs': sorted(expected - valid),
        'public_calls_attempted': {arm: sum(bool(row[arm].get('call_attempted')) for row in rows)
                                   for arm in ('N', 'C')},
        'audit_failure_case_ids': integrity_failures,
        'fresh_assessor_only': {
            'retained': sorted(n_ids & c_ids), 'lost_recognized_support': sorted(n_ids - c_ids),
            'gained': sorted(c_ids - n_ids),
            'note': 'Only valid evaluated pairs. These are assessor matches, not source-integrity approval. '
                    'needs_review remains in the queue; loss is not proof that the fact is absent.'},
        'fresh_source_valid_retained': sorted((cid, claim) for cid, claim in n_ids & c_ids
            if not by_id[cid]['N'].get('audit_errors') and not by_id[cid]['C'].get('audit_errors')),
        'review_queue': [{'arm': arm, **entry} for row in rows for arm in ('N', 'C')
                         for entry in (row[arm].get('assessment') or {}).get('review_queue', [])],
        'historical_partial_retention': 'NOT_MEASURED: separate explicit ledger required',
        'remaining_public_controls': 'NOT_RUN_BY_THIS_CORPUS_COMMAND; scope smoke is a separate test',
    }
    if historical is None:
        result['historical_49'] = {'status': 'UNKNOWN: ledger unavailable or hash mismatch'}
    else:
        known, retained, lost, unknown = set(historical), set(), set(), set()
        for cid, claim in known:
            record = by_id.get(cid, {}).get('C', {})
            assessment = record.get('assessment') or {}
            status = {**assessment.get('claims', {}), **assessment.get('optional_claims', {})}.get(claim, {}).get('status')
            if not record.get('valid_execution') or record.get('audit_errors') or status in (None, 'needs_review'):
                unknown.add((cid, claim))
            elif status == 'supported':
                retained.add((cid, claim))
            else:
                lost.add((cid, claim))
        result['historical_49'] = {'retained': sorted(retained), 'lost': sorted(lost), 'UNKNOWN': sorted(unknown),
            'note': 'Invalid, unaudited and unrecognized C results are UNKNOWN, not implicit losses.'}
    return result


def observed_claim_rows(case, trace, registry, assess):
    """Link known witness rows to real packing events, without inventing causes."""
    inputs = trace.get('projection_input')
    if not isinstance(inputs, list):
        return {'status': 'UNOBSERVED'}
    sources = [{**row, 'path_or_url': row.get('path') or row.get('path_or_url'),
                'evidence_id': f'input-row-{index}'} for index, row in enumerate(inputs)]
    assessed = assess(case, {'sources': sources}, registry)
    by_id = {source['evidence_id']: source for source in sources}
    events = trace.get('decisions', [])
    linked = {}
    for claim_id, claim in assessed['claims'].items():
        ids = {eid for witness in claim.get('supporting_witnesses', []) for eid in witness['evidence_ids']}
        linked[claim_id] = []
        for eid in sorted(ids):
            row = by_id[eid]
            matches = [event for event in events if event.get('path') == row.get('path_or_url')
                       and event.get('span') == row.get('char_span')]
            linked[claim_id].append({'path': row.get('path_or_url'), 'span': row.get('char_span'),
                'events': matches, 'status': 'OBSERVED_ROW' if len(matches) == 1 else 'UNOBSERVED_OR_AMBIGUOUS'})
    return {'input_assessment': assessed, 'row_outcomes': linked,
            'note': 'Observed row outcomes, not a proof of the unique causal stage of every claim loss.'}


def capture_arm(service, request, directory, arm, limits):
    from docmancer.docs.interfaces.mcp import context_tools
    from eval.project_context_quality.capture_public_context import capture_public_call
    from v2plan.next07_grounded_public import installed
    trace = {'arm': arm}
    native_validator = context_tools.validate_model_visible_projection

    def observe_validator(*args, **kwargs):
        errors = native_validator(*args, **kwargs)
        trace.setdefault('handler_validation', []).append({'errors': list(errors), 'max_tokens': kwargs.get('max_tokens')})
        trace['final_snapshot'] = deepcopy(kwargs.get('snapshot') or {})
        return errors

    manager = installed(service, trace, delivery_limits=limits) if arm == 'C' else patch.object(
        context_tools, 'validate_model_visible_projection', observe_validator)
    record = {'call_attempted': True, 'valid_execution': False, 'assessment': None, 'audit_errors': []}
    start = time.perf_counter()
    try:
        with manager:
            capture = capture_public_call(service, request)
        record['capture'] = capture
        payload = capture['public_payload']
        record['valid_execution'] = (payload.get('status') in {'ok', 'truncated', 'insufficient_evidence'}
            and payload.get('kind') == 'docs_context' and not trace.get('exceptions')
            and bool(trace.get('handler_validation')))
        record['execution_error'] = None if record['valid_execution'] else payload.get('error') or 'handler/validator not reached'
    except Exception as exc:
        record['execution_error'] = {'type': type(exc).__name__, 'message': str(exc),
                                     'traceback': traceback.format_exc()}
    finally:
        record['seconds'] = time.perf_counter() - start
        if arm == 'N':
            trace['restored'] = context_tools.validate_model_visible_projection is native_validator
        record['trace'] = trace
        save(directory / 'capture.json', record)
    if trace.get('restored') is not True:
        raise IsolationError(f'{arm} hooks were not restored; saved {directory}')
    return record


def paired_cases(cases, measure, persist):
    """No first-quality-failure stop; measure records case-local invalid runs."""
    result = []
    for case in cases:
        row = {'case_id': case['id'], 'project_group': case['project_group']}
        for arm in ('N', 'C'):
            row[arm] = measure(case, arm)
        persist(row)
        result.append(row)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--compact-read', action='store_true')
    args = parser.parse_args(argv)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.evidence_quality_v2.semantic import assess_context
    from eval.evidence_quality_v2.audit import audit_payload
    from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
    from docmancer.docs.domain.read_delivery_limits import COMPACT_READ_LIMITS
    from docmancer.mcp._docs_server_tool_data import RAW_TOOLS

    protocol, cases, manifest = load_protocol()
    if len(cases) != 80 or len({case['id'] for case in cases}) != 80:
        raise ValueError('expected 80 distinct frozen cases')
    schema = next(tool['inputSchema'] for tool in RAW_TOOLS if tool['name'] == 'get_docs_context')
    requests = {case['id']: {'question': case['question'],
        'project_path': str(out / 'corpus' / case['project_group']), 'scope': 'all'} for case in cases}
    preflight = {cid: validate_request(request, schema) for cid, request in requests.items()}
    save(out / 'request-preflight.json', preflight)
    if any(preflight.values()):
        save(out / 'result.json', {'diagnostic_status': 'BLOCKED_SCHEMA_PREFLIGHT', 'errors': preflight})
        return 2
    paths = [*ROOT.glob('docmancer/**/*.py'), *ROOT.glob('v2plan/next07*.py'),
        *ROOT.glob('v2plan/third_party/grounded-3.2.1/*.py'), *ROOT.glob('eval/evidence_quality_v2/*.py'),
        *ROOT.glob('eval/evidence_quality_v2/*.json'), *ROOT.glob('eval/evidence_quality_v2/sources/**/*'),
        ROOT / 'eval/project_context_quality/capture_public_context.py', HISTORY]
    frozen = fingerprint(paths)
    historical = None
    history_status = 'UNKNOWN'
    if HISTORY.is_file() and hashlib.sha256(HISTORY.read_bytes()).hexdigest() == HISTORY_SHA256:
        historical = ledger_pairs(json.loads(HISTORY.read_text()))
        if len(historical) != 49:
            raise ValueError('historical ledger count changed')
        history_status = 'PINNED_EXTRACTION_VERIFIED; not a new historical replay'
    save(out / 'protocol.json', {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'argv': sys.argv if argv is None else argv, 'python': sys.executable,
        'frozen_hashes': frozen, 'source_manifest': manifest, 'frozen_protocol': protocol,
        'requests': requests, 'policy': 'compact' if args.compact_read else 'bounded',
        'candidate_verdict': 'REJECTED_N10_UNCHANGED', 'historical_ledger': history_status})
    (out / 'baseline.patch').write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT))
    (out / 'baseline-status.txt').write_bytes(subprocess.check_output(['git', 'status', '--short'], cwd=ROOT))
    rows = []
    try:
        for group in sorted({case['project_group'] for case in cases}):
            subset = [case for case in cases if case['project_group'] == group]
            root = out / 'corpus' / group
            docs = documents_for(group, manifest)
            registry = registry_for(group, manifest)
            write_project(root, docs)
            with isolated_service(out / 'state' / group) as (service, config):
                save(out / 'index' / (group + '.json'), index_project(service, config, root))

                def measure(case, arm):
                    directory = out / 'cases' / case['id'] / arm
                    limits = COMPACT_READ_LIMITS if arm == 'C' and args.compact_read else None
                    record = capture_arm(service, requests[case['id']], directory, arm, limits)
                    if record['valid_execution']:
                        payload, trace = record['capture']['public_payload'], record['trace']
                        try:
                            record['cost'] = docs_context_budget_tokens(payload)
                            record['source_count'] = len(payload.get('sources') or [])
                            record['audit_errors'] = audit_payload(payload, trace['final_snapshot'], root, delivery_limits=limits)
                            record['assessment'] = assess_context(case, payload, registry)
                            if arm == 'C':
                                record['observed_claim_rows'] = observed_claim_rows(case, trace, registry, assess_context)
                        except Exception as exc:
                            record['assessment_error'] = {'type': type(exc).__name__, 'message': str(exc),
                                                          'traceback': traceback.format_exc()}
                    save(directory / 'assessment.json', {key: value for key, value in record.items() if key not in ('capture', 'trace')})
                    return {key: value for key, value in record.items() if key not in ('capture', 'trace')}

                def persist(row):
                    rows.append(row)
                    save(out / 'cases' / row['case_id'] / 'result.json', row)
                    save(out / 'result.json', summarize(rows, requests, historical))
                paired_cases(subset, measure, persist)
    except Exception as exc:
        # Index/corpus/global failures end this revision with existing data intact.
        save(out / 'run-error.json', {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()})
    unchanged = fingerprint(paths) == frozen
    result = summarize(rows, requests, historical)
    result['frozen_inputs_unchanged'] = unchanged
    if not unchanged:
        result['diagnostic_status'] = 'INVALID_CHANGED_INPUTS'
    save(out / 'result.json', result)
    history = result['historical_49']
    report = [
        '# Diagnostic corpus replay', '',
        f"Status: {result['diagnostic_status']}",
        'Candidate: REJECTED_N10_UNCHANGED. Rollout NOT_AUTHORIZED.', '',
        f"Valid evaluated pairs: {result['valid_pairs']}/{result['expected_pairs']}.",
        f"Public calls attempted: {result['public_calls_attempted']}.",
        f"Audit failure case IDs: {result['audit_failure_case_ids']}.",
        f"Fresh assessor-only counts: { {key: len(value) for key, value in result['fresh_assessor_only'].items() if isinstance(value, list)} }.",
        f"Historical ledger counts: { {key: len(value) for key, value in history.items() if isinstance(value, list)} }.",
        f"Frozen inputs unchanged: {unchanged}.", '',
        'Exact ID lists and review queues: result.json. Per-arm captures,',
        'assessments and observed packing events: cases/<case-id>/{N,C}/.',
        'Historical partial retention and other public controls were NOT_RUN',
        'by this corpus command. Diagnostic completion is not acceptance.',
        'The missing local 3026969d results have not been reconstructed.',
    ]
    (out / 'SUMMARY_RU.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    save(out / 'postflight-hashes.json', fingerprint(paths))
    print(json.dumps({key: result[key] for key in ('diagnostic_status', 'valid_pairs', 'expected_pairs', 'candidate_verdict')}, indent=2))
    return 0 if result['diagnostic_status'] == 'CORPUS_DIAGNOSTICS_COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
