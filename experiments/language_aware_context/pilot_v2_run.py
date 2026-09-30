"""Fresh FP32 pilot. V1 tasks remain viewed and are not reused as holdout."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import queue
import os
from .pilot_run import Agent, acquire, prepare, HERE
from .baseline_probe import run, write_report, environment
from .packing_experiment import packing_experiment
from .pilot_io import (sha256, planning_messages, parse_plan, answering_messages,
                       evidence_blocks, freeze_file_hashes)


class FP32Agent(Agent):
    """Reuse the tested transport/cache without changing the historical v1 worker."""
    def __init__(self, python: str, output: Path):
        self.log = (output / 'agent-stderr.log').open('w')
        keep = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'LD_LIBRARY_PATH')
        env = {k: os.environ[k] for k in keep if k in os.environ}
        env.update(PYTHONHASHSEED='0', HF_HUB_DISABLE_TELEMETRY='1',
                   HF_HUB_DISABLE_IMPLICIT_TOKEN='1', TOKENIZERS_PARALLELISM='false')
        self.process = subprocess.Popen([python, str(HERE / 'pilot_fp32_agent.py'),
            '--identity', str(output / 'model-identity.json')], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=self.log, text=True, env=env, bufsize=1)
        self.lines = queue.Queue()
        def read():
            for line in self.process.stdout:
                self.lines.put(line)
            self.lines.put('')
        threading.Thread(target=read, daemon=True).start()
        self.ready = self.receive(900)
        if self.ready.get('ready') is not True:
            raise RuntimeError('model worker failed readiness')
        self.cache = {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--agent-python', required=True)
    parser.add_argument('--shard', type=int, choices=(0, 1, 2), required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((HERE / 'pilot_v2.protocol.json').read_text())
    tasks = json.loads((HERE / 'pilot_v2.tasks.json').read_text())
    files = ['pilot_v2.protocol.json', 'pilot_v2.tasks.json', 'pilot_io.py', 'pilot_fp32_agent.py',
             'pilot_run.py', 'pilot_v2_run.py', 'PILOT_GRADING.md', 'packing_experiment.py',
             'baseline_probe.py', 'source_profile.py', 'reference_core.py']
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
    agent = FP32Agent(args.agent_python, out)
    rows = []
    try:
        for task in tasks[args.shard * 3:(args.shard+1) * 3]:
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
                    observed.update(planner_origin='real_pinned_Qwen_FP32',
                        evaluation_kind='fresh_frozen_public_pilot_v2',
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
            'logical_model_requests': len(rows) + 6, 'unique_model_generations': len(agent.cache),
            'health_generations': 2, 'shard': args.shard,
            'hypothesis_acceptance': None, 'product_activation': False})
    finally:
        agent.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
