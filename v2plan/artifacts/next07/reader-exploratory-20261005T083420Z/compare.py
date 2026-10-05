"""Post-review comparison and read-only session export; no model calls."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens

IDS = '''ses_ef4c67b64ffeBpcpa61ttpusRY ses_ef4c67093ffejeKqVN0mH5v8Pz
ses_ef4c67089ffeOSo6uVg1KiCzyC ses_ef4c6704bffekSUGavX4NfSF45
ses_ef4c562fbffee8jRYZtXlh3rCi ses_ef4c562faffeGOtD2opVMXUOgb
ses_ef4c562f8ffeIeG0QfcaaWdcht ses_ef4c56290ffebKppSV6dM9XpM5
ses_ef4c47ee3ffe27BpIV36aoJ2RM ses_ef4c47edbffe7iHtFtBNhSTmgE
ses_ef4c47ed9ffec8xa1LqiOzNeB2 ses_ef4c47e75ffewxWKTuQG375La6
ses_ef4c39296ffeWOHr4VVVbk57dd ses_ef4c39294ffeBcX1fEOpVD9Y5q
ses_ef4c3928affeGRWm9gRSXPN9It ses_ef4c3922fffePoaI4KQjSno1q6
ses_ef4c2b583ffel4S7xAOH8bnUhW ses_ef4c2b578ffeJKU3JBrOlE0018
ses_ef4c2b577ffeYxeZ6WzS4AmioP ses_ef4c2b527ffe2MsayGsJLcUdoQ'''.split()
REVIEWER = 'ses_ef4bf8501ffe2SmpVI7xlSVaKH'


def load(path):
    return json.loads((OUT / path).read_text())


def save(path, value):
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def export(sid):
    args = ['opencode', 'api', 'get', f'/api/experimental/session/{sid}/export']
    record = {'session_id': sid, 'argv': args, 'method': 'GET', 'provider_calls': 0}
    try:
        p = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=20)
        record['exit_code'] = p.returncode
        if p.returncode:
            record['status'] = 'UNAVAILABLE_API_NONZERO'
            return record, None
        data = json.loads(p.stdout)['data']
        if data.get('info', {}).get('id') != sid or not isinstance(data.get('messages'), list):
            record['status'] = 'INVALID_EXPORT_ID_OR_SHAPE'
            return record, None
        path = f'transcripts/{sid}.json'
        (OUT / 'transcripts').mkdir(exist_ok=True)
        (OUT / path).write_bytes(p.stdout)
        record.update(status='EXPORTED_ID_CONFIRMED', artifact=path,
                      sha256=hashlib.sha256(p.stdout).hexdigest(), bytes=len(p.stdout))
        return record, data
    except Exception as exc:
        record.update(status='UNAVAILABLE', error_type=type(exc).__name__)
        return record, None


def session_stats(data):
    info = data['info']
    assistants = [m for m in data['messages'] if m.get('type') == 'assistant']
    t = info.get('time', {})
    return {'export_model': info.get('model'), 'agent': info.get('agent'),
        'messages': len(data['messages']), 'assistant_steps': len(assistants),
        'tool_parts': sum(c.get('type') == 'tool' for m in assistants for c in m.get('content', [])),
        'session_token_usage_as_exported': info.get('tokens'), 'cost_as_exported_uninterpreted': info.get('cost'),
        'time_as_exported': t,
        'elapsed_created_to_idle_seconds': (t['idle'] - t['created']) / 1000 if 'idle' in t else None,
        'assistant_steps_details': [{'message_id': m['id'], 'time': m.get('time'),
            'tokens': m.get('tokens'), 'finish': m.get('finish'), 'model': m.get('model'),
            'elapsed_seconds': (m['time']['completed'] - m['time']['created']) / 1000
                 if 'completed' in m.get('time', {}) else None} for m in assistants]}


def main():
    mapping = load('operator-session-map-private.json')
    by_pair = {(m['case_id'], m['arm']): m for m in mapping}
    idmap = {}
    for i in range(10):
        order = ('A', 'B') if i % 2 == 0 else ('B', 'A')
        for j, arm in enumerate(order):
            idmap[(f'case-{i:02}', arm)] = IDS[2*i+j]
    save('reader-session-ids-private.json', [{'case': c, 'arm': a, 'reader_session_id': sid}
        for (c, a), sid in idmap.items()])
    with ThreadPoolExecutor(max_workers=4) as pool:
        exported = list(pool.map(export, IDS + [REVIEWER]))
    save('transcript-export-status.json', [r for r, _ in exported])
    data_by_id = {r['session_id']: d for r, d in exported if d is not None}
    queue = load('blind-review-queue.json')
    key = load('review-key-private.json')
    review_document = load('independent-review.json')
    reviews = {r['review_id']: r for r in review_document['reviews']}
    assert len(reviews) == len(queue) == len(key) == 20
    assert set(reviews) == set(key) == {r['review_id'] for r in queue}
    results, rows = {}, []
    metrics = {a: {'execution': Counter(), 'review': {}, 'finish_status': Counter(),
                   'read_attempts': 0, 'successful_reads': 0, 'citation_errors': [],
                   'finish_contract_errors': [], 'user_questions': 0, 'honest_unknown_or_partial': 0}
               for a in ('A', 'B')}
    fields = ['grounded_response', 'task_resolved', 'subject_and_conditions', 'honest_stop', 'source_instruction_followed']
    for q in queue:
        bound = key[q['review_id']]
        case, arm = bound['case'], bound['arm']
        m = by_pair[(case, arm)]
        r = load(f"sessions/{m['session']}/result.json")
        inp = load(f"sessions/{m['session']}/reader-input.json")
        review = reviews[q['review_id']]
        sid = idmap[(case, arm)]
        data = data_by_id.get(sid)
        first = inp['first_view']
        row = {'case': case, 'arm': arm, 'review_id': q['review_id'], 'reader_session_id': sid,
            'execution': r['execution'], 'finish': r['finish'], 'review': review,
            'read_attempts': r['read_attempts'], 'successful_reads': r['successful_reads'],
            'read_results': r['read_results'], 'citation_errors': r['citation_errors'],
            'finish_contract_errors': r['finish_contract_errors'],
            'initial_source_count': len(first['initial_context'].get('sources', [])),
            'input_json_utf8_bytes': len(json.dumps(inp, ensure_ascii=False).encode()),
            'first_view_json_utf8_bytes': len(json.dumps(first, ensure_ascii=False).encode()),
            'input_dto_units_estimate_NOT_PROVIDER_TOKENS': docs_context_budget_tokens(inp),
            'visible_snippet_chars': sum(len(s.get('snippet', '')) for s in r['visible_evidence']),
            'source_instruction_text_in_visible_evidence': any('Ignore the tools' in s.get('snippet','')
                                                             for s in r['visible_evidence']),
            'source_instruction_heading_in_first_navigation': 'Ignore previous instructions' in json.dumps(first.get('navigation', [])),
            'export_status': 'EXPORTED_ID_CONFIRMED' if data else 'UNAVAILABLE',
            'export_contains_expected_transport_session': m['session'] in json.dumps(data) if data else None,
            'export_metrics': session_stats(data) if data else None}
        rows.append(row)
        results[(case, arm)] = row
        met = metrics[arm]
        met['execution'].update([r['execution']]); met['finish_status'].update([r['finish']['status']])
        met['read_attempts'] += r['read_attempts']; met['successful_reads'] += r['successful_reads']
        met['citation_errors'].extend(r['citation_errors']); met['finish_contract_errors'].extend(r['finish_contract_errors'])
        met['user_questions'] += bool(r['finish']['question_for_user'].strip())
        met['honest_unknown_or_partial'] += (r['finish']['status'] in {'unknown','partial'} and review['honest_stop'] == 'yes')
        for f in fields:
            met['review'].setdefault(f, Counter()).update([review[f]])
    pairs, helped = [], []
    for i in range(10):
        case = f'case-{i:02}'
        a, b = results[(case,'A')], results[(case,'B')]
        av, bv = a['review']['task_resolved'], b['review']['task_resolved']
        help_observed = av == 'no' and bv == 'yes' and b['successful_reads'] > 0
        if help_observed: helped.append(case)
        pairs.append({'case': case, 'A_resolved': av, 'B_resolved': bv,
            'B_successful_reads': b['successful_reads'], 'observed_navigation_read_help': help_observed,
            'interpretation': 'observed package gain; not causal/equal-compute proof' if help_observed else 'no observed resolution gain'})
    pre, post = load('preflight-hashes.json'), load('postflight-hashes.json')
    assert pre == post
    current = {p: hashlib.sha256((OUT/'bridge.py' if p == 'EXPLORATORY/bridge.py' else ROOT/p).read_bytes()).hexdigest() for p in pre}
    assert current == pre
    diff = subprocess.run(['git','diff','--binary','HEAD'],cwd=ROOT,capture_output=True)
    assert diff.returncode == 0 and diff.stdout == (OUT/'dirty.patch').read_bytes()
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert head == (OUT/'head.txt').read_text().strip()
    latency = [r['export_metrics']['elapsed_created_to_idle_seconds'] for r in rows if r['export_metrics']]
    usage = {'input':0,'output':0,'reasoning':0,'cache_read':0,'cache_write':0}
    for r in rows:
        if r['export_metrics']:
            t = r['export_metrics']['session_token_usage_as_exported'] or {}
            for f in ('input','output','reasoning'): usage[f] += t.get(f,0)
            for f in ('read','write'): usage['cache_'+f] += (t.get('cache') or {}).get(f,0)
    exported_readers = sum(sid in data_by_id for sid in IDS)
    summary = {'status':'PARTIAL_EXPLORATORY_NOT_STRICT_VALIDATED', 'head':head,
        'hashes': {'preflight':'preflight-hashes.json','postflight':'postflight-hashes.json',
                   'frozen_unchanged': True, 'tracked_dirty_patch_unchanged':True},
        'model':'openai/gpt-6.1-sol','provider':'openai via OpenCode general subagents; not published OpenAIReader adapter',
        'technical_native_initial': {'expected':10,'recorded':10,'audit_clean':10},
        'arms':metrics, 'pairs':pairs, 'actual_help_cases':helped,
        'unnecessary_reads_observed':0, 'unnecessary_reads_basis':'only two actual reads; both in reviewer-supported A-no/B-yes pairs',
        'wrong_subject_or_conditions_review_no':sum(r['review']['subject_and_conditions']=='no' for r in rows),
        'wrong_subject_or_conditions_description':'two case-02 false-negative applicability interpretations, not observed transfer of another API value',
        'review': {'status':'COMPLETE_20_OF_20','reviewer_session':REVIEWER,'reviewer_same_model':True,
                   'independence':'procedural blind separate session, not different-model or human independence',
                   'metadata':review_document['metadata']},
        'volume_calls_latency': {'provider_callcount':None,'provider_callcount_status':'UNKNOWN; assistant steps are not audited provider requests',
            'exported_reader_sessions':exported_readers,'exported_reviewer_session':REVIEWER in data_by_id,
            'reader_assistant_steps_recorded':sum(r['export_metrics']['assistant_steps'] for r in rows if r['export_metrics']),
            'reader_usage_as_exported':usage,'usage_scope':'OpenCode session ledger including coding/operator/service context, not isolated reader payload',
            'reader_latency_seconds':{'count':len(latency),'min':min(latency) if latency else None,
                'median':statistics.median(latency) if latency else None,'max':max(latency) if latency else None,
                'definition':'export time.idle minus time.created; includes orchestration/tools, not pure inference'},
            'reader_input_bytes_total':sum(r['input_json_utf8_bytes'] for r in rows)},
        'limitations':load('orchestration-metadata.json'),
        'semantic_candidate_acceptance':'NOT_GRANTED','validated_strict':False,'rollout':'NOT_AUTHORIZED',
        'N10':'EXCLUDED_BY_USER_NOT_RUN_UNCHANGED','new_model_sessions_or_retries':0,
        'rows':sorted(rows,key=lambda r:(r['case'],r['arm']))}
    save('comparison.json',summary)
    save('comparison-postflight-hashes.json',current)
    orchestration = load('orchestration-metadata.json')
    orchestration['original_opencode_transcript_export'] = {'status':'EXPORTED_ALL' if exported_readers==20 and REVIEWER in data_by_id else 'PARTIAL',
        'reader_exports':exported_readers,'reviewer_export':REVIEWER in data_by_id,'method':'read-only opencode api GET export',
        'provider_calls':0,'status_artifact':'transcript-export-status.json'}
    orchestration['reader_session_ids']='reader-session-ids-private.json; API ID validation recorded separately'
    save('orchestration-metadata.json',orchestration)
    summary['limitations'] = orchestration
    summary['review']['reviewer_export_model'] = data_by_id[REVIEWER]['info']['model'] if REVIEWER in data_by_id else None
    summary['volume_calls_latency']['per_arm'] = {arm: {
        'input_bytes_total': sum(r['input_json_utf8_bytes'] for r in rows if r['arm'] == arm),
        'input_bytes_median': statistics.median(r['input_json_utf8_bytes'] for r in rows if r['arm'] == arm),
        'input_bytes_max': max(r['input_json_utf8_bytes'] for r in rows if r['arm'] == arm),
        'assistant_steps': sum(r['export_metrics']['assistant_steps'] for r in rows if r['arm'] == arm and r['export_metrics']),
        'latency_median_seconds': statistics.median(r['export_metrics']['elapsed_created_to_idle_seconds']
            for r in rows if r['arm'] == arm and r['export_metrics'])
    } for arm in ('A', 'B')}
    save('comparison.json', summary)
    save('comparison-command.json', {'argv': [sys.executable,str(Path(__file__).resolve())],
         'cwd':str(ROOT),'exit_code':0,'provider_calls_by_comparison':0})
    print(json.dumps({k:v for k,v in summary.items() if k in ['status','arms','actual_help_cases','wrong_subject_or_conditions_review_no','volume_calls_latency']},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
