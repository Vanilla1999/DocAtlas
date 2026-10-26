"""Real installed MCP + real HTTP adapter, scripted EXTERNAL model transport.

This tests source binding, caching, invalidation and unknown billing, NOT model
semantics or answer quality. No gold, scorer, retrieval, SQLite or validator mocks.
The loopback response usage is synthetic and MUST NOT be reported as provider cost.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def run(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.interfaces.semantic_provider import ResponsesSemanticProvider
    from docmancer.docs.application.semantic_sufficiency import SemanticSufficiencyChecker
    from docmancer.docs.interfaces.checked_context_session import CheckedContextSession
    from docmancer.docs.interfaces.model_context_session import ModelSessionError
    state = {'mode': 'valid', 'calls': 0, 'started': threading.Event(), 'release': threading.Event()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_POST(self):
            assert self.path == '/v1/responses'
            assert self.headers['Authorization'] == 'Bearer transport-fixture-not-a-key'
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert request['store'] is False and request['text']['format']['strict'] is True
            value = json.loads(request['input'][1]['content'])
            state['calls'] += 1
            if 'final_context' not in value:
                assert set(value) == {'original_question'}, 'planning saw evidence or gold'
                answer = {'decomposition_complete': True, 'obligations': [{
                    'question_quote': value['original_question'], 'requirement': value['original_question']}]}
            else:
                context = value['final_context']
                assert context['question'] == value['original_question']
                source = context['sources'][0]
                quote = source['text'] if state['mode'] != 'forged' else 'NOT A QUOTE IN THE DELIVERED SOURCE 782134'
                answer = {'assessments': [{'id': item['id'], 'status': 'supported', 'gap': '',
                    'evidence': [{'ref': source['ref'], 'quote': quote}]} for item in value['question_only_plan']['obligations']],
                    'additional_missing_requirements': [], 'next_search_question': ''}
                if state['mode'] == 'delayed':
                    state['started'].set()
                    assert state['release'].wait(8), 'test did not release transport'
            body = {'id': f'resp-fixture-{state["calls"]}', 'model': 'transport-fixture', 'status': 'completed',
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(answer)}]}]}
            if state['mode'] != 'missing_usage':
                body['usage'] = {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120,
                    'input_tokens_details': {'cached_tokens': 10}, 'output_tokens_details': {'reasoning_tokens': 5}}
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('x-request-id', f'req-fixture-{state["calls"]}')
            self.end_headers()
            self.wfile.write(data)

    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()

    class FixtureTransport(ResponsesSemanticProvider):
        # Only the external transport is substituted. All validation is real.
        endpoint = f'http://127.0.0.1:{http.server_port}/v1/responses'

    data = json.loads((args.repo / 'eval/semantic_holdout/inputs.json').read_text())
    case = next(c for c in data['cases'] if c['id'] == 'H08')
    root = args.work / 'lumen/project'
    params = StdioServerParameters(command=sys.executable, args=[
        '-I', str(args.repo / 'eval/facet_selection_integration.py'), '--worker', '--family', 'lumen',
        '--suite', 'unseen', '--policy', 'facet-guarded-v1', '--repo', str(args.repo), '--work', str(args.work),
        '--out', str(args.out / 'server'), '--model', str(args.model)], env=dict(os.environ))
    results = []
    try:
        with (args.out / 'stderr.log').open('w') as err:
          async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as client:
                await client.initialize()
                for mode in ('valid', 'forged', 'delayed', 'missing_usage'):
                    state['mode'] = mode
                    provider = FixtureTransport(api_key='transport-fixture-not-a-key', model='transport-fixture', max_calls=8)
                    turn = CheckedContextSession(client, checker=SemanticSufficiencyChecker(provider),
                        question=case['question'], bindings={'project_path': str(root), 'scope': 'project'}, language_mode=True)
                    await turn.language()
                    context = await turn.retrieve(search_question=case['search_question'], lookup_queries=[])
                    before = json.dumps(context, sort_keys=True)
                    refs = [row['ref'] for row in context['sources']]
                    assert refs
                    if mode == 'delayed':
                        task = asyncio.create_task(turn.assess())
                        assert await asyncio.to_thread(state['started'].wait, 8)
                        turn.invalidate()
                        state['release'].set()
                        try:
                            await task
                        except ModelSessionError as exc:
                            assert str(exc) == 'session_invalidated_during_check'
                        else:
                            raise AssertionError('revoked context regained a verdict')
                        assert turn.assessment() is None and not turn.model_input()['sources']
                        try:
                            turn.resolve(refs[0])
                        except ModelSessionError:
                            pass
                        else:
                            raise AssertionError('old reference was resurrected')
                    else:
                        verdict = await turn.assess()
                        assert json.dumps(turn.model_input(), sort_keys=True) == before, 'checker altered source delivery'
                        if mode == 'valid':
                            assert verdict['status'] == 'sufficient' and verdict['authority'] == 'none'
                            count = state['calls']
                            assert await turn.assess() == verdict and state['calls'] == count
                            summary = provider.usage_summary()
                            assert summary['provider_totals']['total_tokens'] == 240
                            assert summary['reasoning_tokens'] == 10 and summary['cached_tokens'] == 20
                            turn.invalidate()
                            assert turn.assessment() is None
                        elif mode == 'forged':
                            assert verdict['status'] == 'unknown' and verdict['reason'] == 'semantic_check_failed'
                        else:
                            assert verdict['status'] == 'unknown'
                            assert provider.usage_summary()['accounting_complete'] is False
                            assert provider.usage_summary()['provider_totals'] is None
                    results.append({'scenario': mode, 'passed': True, 'mcp_calls': len(turn.audit),
                                    'synthetic_transport_calls': len(provider.records)})
                    save(args.out / (mode + '.json'), {'boundary': __doc__, 'mcp_audit': turn.audit,
                        'semantic_audit': turn.semantic_audit, 'synthetic_transport': provider.records})
        server = json.loads((args.out / 'server/lumen/server.json').read_text())
        assert server['database_unchanged'] and server['files_unchanged']
        save(args.out / 'SUMMARY.json', {'scenarios': results, 'passed': True,
            'public_baseline_calls': 8, 'public_preparations': 1,
            'stdio_calls': sum(row['mcp_calls'] for row in results),
            'actual_provider_calls': 0, 'provider_usage': None, 'semantic_accuracy_tested': False,
            'boundary': __doc__})
        print(json.dumps(results), flush=True)
    finally:
        state['release'].set()
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('repo', 'work', 'out', 'model'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    for key in ('repo', 'work', 'out', 'model'):
        setattr(args, key, getattr(args, key).resolve())
    import docmancer
    product = Path(docmancer.__file__).resolve().parent
    assert not product.is_relative_to(args.repo), 'installed wheel required'
    assert all(path.read_bytes() == (args.repo / 'docmancer' / path.relative_to(product)).read_bytes()
               for path in product.rglob('*.py'))
    args.out.mkdir(parents=True, exist_ok=False)
    assert not args.work.exists()
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
