"""Installed MCP + distinct real local critic; false-sufficient and recovery pilot.

No mocks of retrieval/storage/models. Controlled-context fixtures are separate
from the unchanged L10 regression episodes. Paid usage is BLOCKED, never
estimated, without explicit configured credentials AND model.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checker(port=8100):
    from docmancer.docs.application.final_context_autorater import ExplicitLocalModel, FinalContextAutorater
    local = ExplicitLocalModel(endpoint=f'http://127.0.0.1:{port}', model='docatlas-critic',
        weights_sha256='01999f17c39cc3074afae5e9c539bc82d45f2dd7faa3917c66cbef76fce8c0c2',
        output_tokens=768, timeout_seconds=180)
    return FinalContextAutorater(local,
        selector_sha256='7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5')


@asynccontextmanager
async def mcp_client(args, arm):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    env = dict(os.environ)
    # Paid credentials never enter the MCP subprocess or local model prompts.
    env.pop('OPENAI_API_KEY', None)
    env.pop('DOCATLAS_STRONG_MODEL', None)
    env.update(DOCATLAS_MCP_TEXT_FALLBACK='1', DOCATLAS_MINILM_MODEL_DIR=str(args.minilm),
        DOCATLAS_LLM_EVIDENCE=('select' if arm in {'select', 'adaptive'} else 'off'),
        DOCATLAS_LLM_EVIDENCE_URL='http://127.0.0.1:8099',
        DOCATLAS_LLM_EVIDENCE_MODEL='docatlas-local', DOCATLAS_LLM_OUTPUT_TOKENS='1024',
        DOCATLAS_LLM_TIMEOUT_SECONDS='180', DOCATLAS_LLM_EVIDENCE_TRACE='1')
    if arm == 'pool':
        env['DOCATLAS_CONTEXT_COMPRESSION'] = 'off'
    params = StdioServerParameters(command=str(Path(sys.executable).with_name('doc-atlas')),
                                  args=['mcp', 'docs-serve'], env=env)
    with (args.out / f'{arm}-{time.time_ns()}-stderr.jsonl').open('w') as err:
        async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=600)) as client:
                await client.initialize()
                yield client


def validate_sources(session, docs, helpers):
    rows = [session.resolve(row['ref']) for row in session.model_input()['sources']]
    helpers.original_spans(rows, docs)
    return rows


async def assess_fixture(args, case, root, helpers):
    from docmancer.docs.interfaces.checked_context_session import CheckedContextSession
    rater = checker()
    async with mcp_client(args, 'pool') as client:
        session = CheckedContextSession(client, checker=rater, max_checks=1,
            question=case['question'], bindings={'project_path': str(root), 'scope': 'project'})
        started = time.monotonic()
        record = {'id': case['id'], 'expected': case['expected'], 'operational_error': None}
        try:
            await session.retrieve()
            rows = validate_sources(session, case['documents'], helpers)
            # Fixture contract: every frozen required quote really reached the judge.
            text = '\n'.join(r['snippet'] for r in rows)
            record['required_fixture_quotes_delivered'] = all(q in text for q in case['quotes'])
            assert record['required_fixture_quotes_delivered'], 'controlled context not delivered'
            verdict = await session.assess()
            record.update(predicted=verdict['status'], verdict=verdict, context=session.model_input())
        except Exception as exc:
            record.update(predicted='OPERATIONAL_ERROR', operational_error=type(exc).__name__ + ':' + str(exc))
        record.update(seconds=time.monotonic()-started, mcp_audit=session.audit,
                      checker_calls=rater.model.records)
        save(args.out / 'rater' / (case['id'] + '.json'), record)
        print(json.dumps({'case': case['id'], 'expected': case['expected'], 'predicted': record['predicted']}), flush=True)
        return record


async def episode(args, case, root, docs, arm, helpers, provider):
    from docmancer.docs.interfaces.model_context_session import ModelContextSession
    from docmancer.docs.interfaces.sufficient_context_session import SufficientContextSession, ANSWER_INSTRUCTION, ANSWER_SCHEMA
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    from docmancer.docs.application.semantic_sufficiency import canonical
    rater = checker()
    async with mcp_client(args, arm) as client:
        settings = dict(question=case['question'], bindings={'project_path': str(root), 'scope': 'project'})
        session = (SufficientContextSession(client, checker=rater, max_recoveries=1,
                    deadline_seconds=540, **settings) if arm in {'adaptive', 'main-recover'} else ModelContextSession(client, **settings))
        record = {'id': case['id'], 'arm': arm, 'operational_error': None, 'paid_status': 'BLOCKED_NOT_CONFIGURED'}
        started = time.monotonic()
        try:
            if arm in {'adaptive', 'main-recover'}:
                answer_input = await session.prepare()
                record.update(verdict=session.assessment(), semantic_audit=session.semantic_audit,
                              answer_input=answer_input)
            else:
                view = await session.retrieve()
                answer_input = {'context': view, 'response_mode': 'answer',
                                'evidence_assessment': {'status': 'not_assessed', 'fallible': True, 'authority': 'none', 'gaps': []}}
            record['context_seconds'] = time.monotonic()-started
            rows = validate_sources(session, docs, helpers)
            record['sources'] = rows
            record['answer_input'] = answer_input
            record['model_input_tokens_o200k_NOT_BILLED'] = projection_token_count(canonical(answer_input).encode())
            if provider is not None:
                before = len(provider.records)
                try:
                    if arm in {'adaptive', 'main-recover'}:
                        record['answer'] = await session.answer(provider, max_output_tokens=1024)
                    else:
                        record['answer'] = await provider.complete(purpose='answer', instruction=ANSWER_INSTRUCTION,
                            payload=answer_input, schema=ANSWER_SCHEMA, max_output_tokens=1024)
                    record['paid_status'] = 'COMPLETED_OR_ROUTED_ABSTENTION'
                except Exception as exc:
                    record.update(paid_status='FAILED', paid_error=type(exc).__name__)
                record['paid_calls'] = provider.records[before:]
            # Read-only public requests retain the exact original bindings/question.
            for event in session.audit:
                if event['tool'] == 'get_docs_context':
                    request = event['arguments']
                    assert request['question'] == case['question']
                    assert request['scope'] == 'project' and request['project_path'] == str(root)
                    assert not set(request).intersection({'allow_network', 'confirm', 'mutation', 'version'})
            if arm in {'adaptive', 'main-recover'}:
                record['recovery_requests'] = sum(e['tool'] == 'get_docs_context' for e in session.audit) - 1
                assert record['recovery_requests'] <= 1
                # A public state invalidation must invalidate the verdict too.
                session.invalidate()
                assert session.assessment() is None
                assert session.answer_input()['response_mode'] == 'abstain'
                record['invalidation_rejected_stale_assessment'] = True
        except Exception as exc:
            record['operational_error'] = type(exc).__name__ + ':' + str(exc)
        record.update(total_seconds=time.monotonic()-started, mcp_audit=session.audit, checker_calls=rater.model.records)
        save(args.out / 'episodes' / (arm + '-' + case['id'] + '.json'), record)
        print(json.dumps({'arm': arm, 'case': case['id'], 'error': record['operational_error'],
                          'verdict': (record.get('verdict') or {}).get('status'), 'paid': record['paid_status']}), flush=True)
        return record


def memory_sample():
    result = {}
    for label in ('SELECTOR_PID', 'CRITIC_PID'):
        pid = os.environ.get(label)
        if pid and pid.isdecimal():
            data = Path(f'/proc/{pid}/status').read_text()
            result[label] = {line.split(':')[0]: line.split(':')[1].strip()
                             for line in data.splitlines() if line.startswith(('VmRSS:', 'VmHWM:'))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'out', 'work', 'minilm'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--shard', type=int, choices=range(4), required=True)
    args = parser.parse_args()
    for key in ('repo', 'out', 'work', 'minilm'):
        setattr(args, key, getattr(args, key).resolve())
    args.out.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True)
    import docmancer
    installed = Path(docmancer.__file__).resolve().parent
    assert not installed.is_relative_to(args.repo), 'installed wheel required'
    product = ('docs/application/final_context_autorater.py', 'docs/interfaces/sufficient_context_session.py',
               'docs/interfaces/paid_answer_provider.py', 'docs/application/llm_evidence.py')
    assert all(digest(installed / p) == digest(args.repo / 'docmancer' / p) for p in product)
    corpus = args.repo / 'eval/sufficient_context'
    frozen = json.loads((corpus / 'freeze.json').read_text())['cases_sha256']
    assert digest(corpus / 'cases.json') == frozen
    cases = json.loads((corpus / 'cases.json').read_text())[args.shard*3:(args.shard+1)*3]
    helpers = load('sufficiency_eval_helpers', args.repo / 'eval/llm_evidence/run.py')
    runtime = load('sufficiency_eval_runtime', args.repo / 'eval/evidence_quality_v2/runtime.py')
    save(args.out / 'CHECKPOINT.json', {'head': os.environ.get('TESTED_SHA'), 'shard': args.shard,
         'installed_hashes': {p: digest(installed / p) for p in product}, 'fixture_sha256': frozen})
    key, model = os.environ.get('OPENAI_API_KEY'), os.environ.get('DOCATLAS_STRONG_MODEL')
    provider = None
    if key and model:
        from docmancer.docs.interfaces.paid_answer_provider import PaidAnswerProvider
        provider = PaidAnswerProvider(api_key=key, model=model, max_calls=4)
    save(args.out / 'PAID_ACCESS.json', {'status': 'CONFIGURED' if provider else 'BLOCKED_NOT_CONFIGURED',
          'reason': None if provider else 'explicit API key and paid model required', 'usage': None})
    assessments = []
    for case in cases:
        root = args.work / case['id']
        runtime.write_project(root, case['documents'])
        with runtime.isolated_service(args.work / (case['id'] + '-state')) as (service, config):
            inventory = runtime.index_project(service, config, root)
            state = helpers.logical_state(inventory['storage_path'])
            assessment = asyncio.run(assess_fixture(args, case, root, helpers))
            assert state == helpers.logical_state(inventory['storage_path'])
            assert all((root / p).read_text() == text for p, text in case['documents'].items())
            assessments.append(assessment)
    pilot = args.repo / 'eval/llm_evidence'
    docs = json.loads((pilot / 'sources.json').read_text())
    cid = ('L10-03', 'L10-04', 'L10-07', 'L10-08')[args.shard]
    case = next(c for c in json.loads((pilot / 'questions.json').read_text()) if c['id'] == cid)
    root = args.work / 'episodes'
    runtime.write_project(root, docs)
    episodes = []
    with runtime.isolated_service(args.work / 'episode-state') as (service, config):
        inventory = runtime.index_project(service, config, root)
        state = helpers.logical_state(inventory['storage_path'])
        for arm in ('main', 'select', 'main-recover', 'adaptive'):
            episodes.append(asyncio.run(episode(args, case, root, docs, arm, helpers, provider)))
        assert state == helpers.logical_state(inventory['storage_path'])
        assert all((root / p).read_text() == text for p, text in docs.items())
    # Score quotes independently of model requirements, after all delivery.
    gold = json.loads((pilot / 'gold.json').read_text())[cid]
    for item in episodes:
        spans = helpers.original_spans(item.get('sources', []), docs)
        item['required'] = [{'id': fact['id'], 'covered': any(all(helpers.has_part(p, spans, docs) for p in alt)
                            for alt in fact['alternatives'])} for fact in gold['facts']]
        item['gold_answerability'] = gold['expected_status']
        item['false_sufficient'] = (item.get('verdict') or {}).get('status') == 'sufficient' and (
            gold['expected_status'] != 'sufficient' or not all(x['covered'] for x in item['required']))
        save(args.out / 'episodes' / (item['arm'] + '-' + cid + '.json'), item)
    assert digest(corpus / 'cases.json') == frozen
    counts = {}
    for record in assessments:
        k = record['expected'] + ' -> ' + record['predicted']
        counts[k] = counts.get(k, 0) + 1
    result = {'head': os.environ.get('TESTED_SHA'), 'shard': args.shard,
        'rater_confusion': counts, 'rater_cases': assessments, 'episodes': episodes,
        'false_sufficient': sum(x['expected'] != 'sufficient' and x['predicted'] == 'sufficient' for x in assessments),
        'rater_exact_correct': sum(x['expected'] == x['predicted'] for x in assessments),
        'source_and_sqlite_unchanged': True, 'memory_serving_processes': memory_sample(),
        'paid_status': 'ATTEMPTED' if provider else 'BLOCKED_NOT_CONFIGURED',
        'paid_calls': provider.records if provider else [], 'paid_usage': None if not provider else 'see actual response ledgers',
        'scope': 'installed managed-host pilot; not stock OpenCode; same-author frozen cases; no generalization guarantee'}
    save(args.out / 'SUMMARY.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rater_cases', 'episodes', 'paid_calls')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
