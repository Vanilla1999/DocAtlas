"""Blind packaging and technical counts only; no answer grading or A/B comparison."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def load(name):
    return json.loads((OUT / name).read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    os.umask(0o077)
    for name in ('blind-review-queue.json', 'review-key-private.json'):
        if (OUT / name).exists():
            raise RuntimeError('refuse to replace existing review artifacts')
    mapping = load('operator-session-map-private.json')
    native = load('initial-status.json')
    assert len(mapping) == 20
    rubrics = {}
    for row in native['rows']:
        evaluator = OUT / Path(row['capture']).parent.parent / 'evaluator-only.json'
        rubrics[row['case_id']] = json.loads(evaluator.read_text())['rubric']
    reviews, key = [], {}
    execution, citation, contract, unavailable = Counter(), Counter(), Counter(), Counter()
    attempts = successful = events = 0
    criteria = ['answer_supported_by_visible_quotes', 'correct_subject_and_conditions',
                'honest_unknown_or_user_question', 'no_source_instruction_following']
    for item in mapping:
        directory = OUT / 'sessions' / item['session']
        result = json.loads((directory / 'result.json').read_text())
        reader_input = json.loads((directory / 'reader-input.json').read_text())
        review_id = secrets.token_hex(12)
        assert review_id not in key
        key[review_id] = {'case': item['case_id'], 'arm': item['arm']}
        reviews.append({'review_id': review_id, 'execution': result.get('execution'),
            'rubric': rubrics[item['case_id']],
            'finish_contract_errors': result.get('finish_contract_errors', []),
            'question': reader_input['question'], 'finish': result.get('finish'),
            'citation_errors': result.get('citation_errors'),
            'visible_evidence': result.get('visible_evidence', []),
            'review_status': 'PENDING', 'criteria': criteria})
        execution.update([str(result.get('execution'))])
        citation.update(result.get('citation_errors') or [])
        contract.update(result.get('finish_contract_errors') or [])
        attempts += result.get('read_attempts', 0)
        successful += result.get('successful_reads', 0)
        for event in result.get('host_events', []):
            events += 1
            receipt = event.get('result') or {}
            if receipt.get('status') == 'unavailable':
                unavailable.update([receipt.get('reason', 'unknown')])
        assert result.get('initial_context_unchanged') is True
    secrets.SystemRandom().shuffle(reviews)
    encoded = json.dumps(reviews, ensure_ascii=False)
    forbidden = [str(OUT), 'v2plan/artifacts/', *[s['session'] for s in mapping],
                 *[s['case_id'] for s in mapping]]
    assert not any(value in encoded for value in forbidden), 'queue contains private identity/path'
    assert all(not ({'case', 'case_id', 'arm', 'artifact', 'path'} & row.keys()) for row in reviews)
    pre = load('preflight-hashes.json')
    current = {}
    for relative in pre:
        path = OUT / 'bridge.py' if relative == 'EXPLORATORY/bridge.py' else ROOT / relative
        current[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert current == pre, 'frozen inputs changed'
    diff = subprocess.run(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT, capture_output=True)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    assert diff.returncode == head.returncode == 0
    assert diff.stdout == (OUT / 'dirty.patch').read_bytes(), 'tracked user diff changed'
    assert head.stdout.strip() == (OUT / 'head.txt').read_text().strip()
    save('blind-review-queue.json', reviews)
    save('review-key-private.json', key)
    save('orchestration-metadata.json', {
        'mode': 'EXPLORATORY_ONLY_NOT_PUBLISHED_LIVE_PILOT',
        'reader_model': 'openai/gpt-6.1-sol', 'reader_agent_type': 'general',
        'reader_sessions_reported_by_operator': 20, 'reader_result_files_recorded': 20,
        'provider_calls': None, 'provider_usage': None,
        'provider_calls_usage_status': 'UNKNOWN_NOT_ASSUMED_40',
        'bridge_model_calls': 0, 'coding_context_contamination': True,
        'operator_prompt_deviations': [
            'Operator prompts included documents-as-data instruction in addition to frozen SYSTEM.',
            'HTTP GET/POST added transport/service steps outside published provider loop.',
            'Prompt template slightly shortened after the first four readers.'
        ],
        'prompt_deviation_source': 'parent operator report; exact session transcripts not yet available',
        'frozen_system_artifact': 'system-and-schemas.json',
        'python_deviation': 'existing Python 3.13.12 rather than published 3.12',
        'new_readers_or_retries_by_this_finalization': 0,
        'reader_session_ids': 'NOT_YET_PROVIDED_BY_PARENT',
        'original_opencode_transcript_export': {
            'status': 'UNAVAILABLE_PENDING_READER_SESSION_IDS',
            'reason': 'No authoritative OpenCode reader session IDs supplied; no guessing or broad session export.',
            'provider_calls': 0, 'secrets_requested': False,
            'available_transport_evidence': 'sessions/*/operator-post-*.raw and transport-events.json'
        },
        'review': 'PENDING_NO_SEMANTIC_GRADING_NO_AB_COMPARISON',
        'published_live_pilot': 'NOT_RUN', 'validated': False, 'rollout': 'NOT_AUTHORIZED',
        'N10': 'EXCLUDED_BY_USER_NOT_RUN_UNCHANGED'})
    summary = {'review_queue_count': len(reviews), 'execution_counts': dict(execution),
               'citation_error_counts': dict(citation), 'finish_contract_error_counts': dict(contract),
               'read_attempts': attempts, 'successful_reads': successful,
               'host_read_events': events, 'unavailable_read_reasons': dict(unavailable),
               'initial_context_unchanged_all': True, 'frozen_hashes_unchanged': True,
               'head_unchanged': True, 'tracked_dirty_patch_unchanged': True,
               'provider_calls_usage': 'UNKNOWN', 'semantic_review': 'PENDING_NOT_PERFORMED',
               'ab_comparison': 'NOT_PERFORMED'}
    save('review-packaging-technical.json', summary)
    save('pre-shutdown-hashes.json', current)
    ready = load('bridge-ready.json')
    pid = ready['pid']
    commandline = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    assert any(arg and (ROOT / os.fsdecode(arg)).resolve() == OUT / 'bridge.py'
               for arg in commandline)
    os.kill(pid, signal.SIGTERM)
    save('shutdown-command.json', {'operation': 'os.kill', 'pid': pid, 'signal': 'SIGTERM',
         'signal_number': signal.SIGTERM.value, 'exit_code': 0, 'unix_time': time.time(),
         'postflight_expected': 'postflight-hashes.json', 'bridge_exit_expected': 'bridge-exit.json'})
    save('finalize-command.json', {'argv': [sys.executable, str(Path(__file__).resolve())],
         'cwd': str(ROOT), 'exit_code': 0})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
