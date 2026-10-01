"""Frozen new-source pilot: real model plans/answers, real handler, paired packing.

No source body or gold facts enter the planner. Canonical public snapshots are
pinned by Git object IDs; no existing Typer/M1.5 task is part of this pilot.
"""
from __future__ import annotations
import argparse
import base64
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import urllib.request

from .baseline_probe import run, write_report, environment
from .packing_experiment import packing_experiment
from .pilot_io import (sha256, validate_sources, quote_window, planning_messages,
                       parse_plan, answering_messages, evidence_blocks, freeze_file_hashes)
from .source_profile import catalog_digest, profile_sources, profile_hint
from .reference_core import ScopeKey

HERE = Path(__file__).resolve().parent


class Agent:
    """One persistent isolated worker; no task labels, credentials or tools passed."""
    def __init__(self, python: str, output: Path):
        self.log = (output / 'agent-stderr.log').open('w')
        keep = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'LD_LIBRARY_PATH')
        env = {k: os.environ[k] for k in keep if k in os.environ}
        env.update(PYTHONHASHSEED='0', HF_HUB_DISABLE_TELEMETRY='1',
                   HF_HUB_DISABLE_IMPLICIT_TOKEN='1', TOKENIZERS_PARALLELISM='false')
        self.process = subprocess.Popen([python, str(HERE / 'pilot_agent.py'),
            '--identity', str(output / 'model-identity.json')], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=self.log, text=True, env=env, bufsize=1)
        self.lines: queue.Queue[str] = queue.Queue()
        def read():
            for line in self.process.stdout:
                self.lines.put(line)
            self.lines.put('')
        threading.Thread(target=read, daemon=True).start()
        self.ready = self.receive(900)
        if self.ready.get('ready') is not True:
            raise RuntimeError('model worker failed readiness')
        self.cache: dict[str, dict] = {}

    def receive(self, timeout: int) -> dict:
        line = self.lines.get(timeout=timeout)
        if not line:
            raise RuntimeError('model worker exited; inspect preserved stderr')
        value = json.loads(line)
        if value.get('error'):
            raise RuntimeError('model worker: ' + json.dumps(value))
        return value

    def generate(self, uid: str, messages: list, maximum: int) -> dict:
        key = sha256(json.dumps([messages, maximum], ensure_ascii=False,
                               sort_keys=True).encode())
        # Identical deterministic inputs may reuse a genuine earlier generation.
        # Explicit linkage is recorded; never described as an additional model call.
        if key in self.cache:
            return {**self.cache[key], 'id': uid,
                    'reused_generation_id': self.cache[key]['id'], 'messages_sha256': key}
        command = {'id': uid, 'messages': messages, 'max_new_tokens': maximum}
        self.process.stdin.write(json.dumps(command, ensure_ascii=False) + '\n')
        self.process.stdin.flush()
        value = self.receive(300)
        if value.get('id') != uid:
            raise RuntimeError('worker response ID mismatch')
        value['messages_sha256'] = key
        self.cache[key] = value
        return value

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)
        self.log.close()


def acquire(protocol: dict, output: Path) -> dict[str, dict]:
    """Only official GitHub blob endpoints. Verify immutable raw bytes before use."""
    rows = {}
    for source in protocol['sources']:
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'DocAtlas-PR204-pilot'}
        token = os.getenv('GITHUB_TOKEN')
        if token:
            headers['Authorization'] = 'Bearer ' + token
        url = f"https://api.github.com/repos/{source['repository']}/git/blobs/{source['blob']}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as stream:
            envelope = json.load(stream)
        if envelope.get('encoding') != 'base64':
            raise ValueError('GitHub blob must be base64')
        raw = base64.b64decode(envelope['content'])
        validate_sources(raw, source['blob'])
        path = output / 'source_bytes' / (source['id'] + '.md')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        rows[source['id']] = {**source, 'text': raw.decode('utf-8'), 'sha256': sha256(raw)}
    return rows


def prepare(protocol: dict, tasks: list[dict], sources: dict, output: Path) -> tuple[dict, dict]:
    """Validate all oracle snippets before any model invocation or retrieval score."""
    from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
    # This import is checked against real repo before commit; no token-estimator substitute.
    scopes, oracles = {}, {}
    for scope, ids in protocol['scopes'].items():
        docs = {sources[s]['local_path']: sources[s]['text'] for s in ids}
        root = output / 'corpora' / scope
        for path, text in docs.items():
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding='utf-8')
        spec = {'schema_version': 1, 'sources': [
            {'path': p, 'sha256': sha256(t.encode())} for p, t in sorted(docs.items())]}
        digest = catalog_digest(docs)
        key = ScopeKey(scope, 'unversioned-snapshot', 'pilot-v1', digest)
        hint = profile_hint(profile_sources(docs, key), key)
        scopes[scope] = {'root': root, 'spec': spec, 'hint': hint, 'catalog_sha256': digest}
    for task in tasks:
        blocks = []
        for group in task['oracle']:
            source = sources[group['source_id']]
            for quote in group['quotes']:
                start, end, raw = quote_window(source['text'], quote)
                blocks.append({'id': f'S{len(blocks)+1}', 'path': source['local_path'],
                               'text': raw, 'char_start': start, 'char_end': end,
                               'source_sha256': source['sha256']})
        if docs_context_budget_tokens({"evidence": blocks}) > 800:
            raise ValueError('oracle exceeds frozen budget; do not silently trim')
        if bool(blocks) != task['answerable']:
            raise ValueError('oracle answerability mismatch')
        oracles[task['id']] = blocks
    return scopes, oracles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--agent-python', required=True)
    parser.add_argument('--shard', type=int, choices=(0, 1, 2), required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((HERE / 'pilot.protocol.json').read_text())
    tasks = json.loads((HERE / 'pilot.tasks.json').read_text())
    files = ['pilot.protocol.json', 'pilot.tasks.json', 'pilot_io.py', 'pilot_agent.py',
             'pilot_run.py', 'packing_experiment.py', 'baseline_probe.py',
             'source_profile.py', 'reference_core.py']
    sources = acquire(protocol, out)
    scopes, oracles = prepare(protocol, tasks, sources, out)
    lock = {'status': 'FROZEN_BEFORE_FIRST_AGENT_CALL',
        'created_at': datetime.now(timezone.utc).isoformat(), 'shard': args.shard,
        'files': freeze_file_hashes(HERE, files), 'environment': environment(),
        'source_sha256': {k: s['sha256'] for k, s in sources.items()},
        'profiles': {k: s['hint'] for k, s in scopes.items()},
        'all_task_ids': [t['id'] for t in tasks], 'product_activation': False}
    write_report(out / 'freeze.json', lock)
    write_report(out / 'oracle-private.json', {'tasks': oracles})
    print('FROZEN', sha256((out / 'freeze.json').read_bytes()), flush=True)
    agent = Agent(args.agent_python, out)
    rows = []
    try:
        for task in tasks[args.shard * 4:(args.shard+1) * 4]:
            scope = scopes[task['scope']]
            plans = {}
            for arm in ('A', 'B'):
                messages, literals = planning_messages(task['question'], scope['hint'] if arm == 'B' else None)
                generated = agent.generate(task['id'] + '-' + arm + '-plan', messages, 96)
                try:
                    queries = list(parse_plan(generated['text'], literals, task['question']))
                    valid, error = True, None
                except (ValueError, TypeError, KeyError, IndexError) as exc:
                    queries, valid, error = [], False, type(exc).__name__ + ': ' + str(exc)
                plans[arm] = {'messages': messages, 'generation': generated,
                              'lookup_queries': queries, 'valid': valid, 'error': error}
            write_report(out / (task['id'] + '-plans.json'), plans)
            for condition in protocol['conditions']:
                observed = None
                if condition in ('oracle', 'no_context'):
                    blocks = oracles[task['id']] if condition == 'oracle' else []
                else:
                    plan = plans[condition[0]]
                    request = {'question': task['question'], 'lookup_queries': plan['lookup_queries']}
                    with (packing_experiment() if condition.endswith('_packing') else nullcontext()):
                        observed = run(scope['root'], scope['spec'], request)
                    if observed['status'] != 'EXECUTED':
                        write_report(out / (task['id'] + '-' + condition + '-error.json'), observed)
                        raise RuntimeError('real handler/audit failed; not an answer-quality miss')
                    observed.update(planner_origin='real_pinned_Qwen',
                        evaluation_kind='fresh_frozen_public_pilot',
                        held_out_from_prior_packing_tuning=True, agent_evaluation='PENDING',
                        negative_oracle=not task['answerable'])
                    blocks = evidence_blocks(observed['payload'])
                messages = answering_messages(task['question'], blocks)
                generated = agent.generate(task['id'] + '-' + condition + '-answer', messages, 144)
                record = {'task_id': task['id'], 'condition': condition, 'question': task['question'],
                    'family': task['family'], 'language': task['query_language'],
                    'evidence': blocks, 'answer_messages': messages, 'answer': generated,
                    'observed': observed, 'plan_valid': plans[condition[0]]['valid'] if condition[0] in plans else None,
                    'fact_score': None, 'product_activation': False}
                name = task['id'] + '-' + condition + '.json'
                write_report(out / name, record)
                row = {k: record[k] for k in ('task_id', 'condition', 'family', 'language', 'plan_valid')}
                row.update(artifact=name, answer_tokens=generated['output_tokens'],
                    reused_generation_id=generated.get('reused_generation_id'),
                    dto_tokens=observed['budget_tokens'] if observed else None,
                    audit_errors=observed['audit_errors'] if observed else None,
                    answer_supported=observed['payload'].get('answer_supported') if observed else None,
                    edit_ready=observed['payload'].get('edit_ready') if observed else None)
                rows.append(row)
                print(json.dumps(row), flush=True)
        if lock['files'] != freeze_file_hashes(HERE, files):
            raise RuntimeError('evaluation code changed after freeze')
        write_report(out / 'summary.json', {'status': 'EXECUTED_NOT_SCORED', 'rows': rows,
            'logical_model_requests': len(rows) + 8, 'unique_model_generations': len(agent.cache),
            'shard': args.shard, 'hypothesis_acceptance': None, 'product_activation': False})
    finally:
        agent.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
