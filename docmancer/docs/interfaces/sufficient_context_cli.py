"""Explicit managed host; stock OpenCode behavior is not changed.

Example: python -m docmancer.docs.interfaces.sufficient_context_cli --help
Model servers and source index must already be provisioned by the host.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys


async def run(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.final_context_autorater import ExplicitLocalModel, FinalContextAutorater
    from .sufficient_context_session import SufficientContextSession
    critic = ExplicitLocalModel(endpoint=args.checker_url, model=args.checker_model,
                                weights_sha256=args.checker_sha256)
    rater = FinalContextAutorater(critic, selector_sha256=args.selector_sha256)
    env = dict(os.environ)
    env.pop('OPENAI_API_KEY', None)
    env['DOCATLAS_MCP_TEXT_FALLBACK'] = '1'
    cli = str(Path(sys.executable).with_name('doc-atlas'))
    async with stdio_client(StdioServerParameters(command=cli, args=['mcp', 'docs-serve'], env=env)) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=600)) as client:
            await client.initialize()
            bindings = {'project_path': str(args.project.resolve()), 'scope': args.scope}
            for key in ('module_path', 'version', 'library'):
                if getattr(args, key) is not None:
                    bindings[key] = getattr(args, key)
            session = SufficientContextSession(client, question=args.question, bindings=bindings,
                checker=rater, max_recoveries=args.max_recoveries)
            value = await session.prepare()
            output = {'answer_input': value, 'assessment': session.assessment(), 'answer': None,
                      'paid_status': 'NOT_REQUESTED', 'paid_usage': None}
            if args.answer_model:
                from .paid_answer_provider import PaidAnswerProvider
                key = os.environ.get('OPENAI_API_KEY', '')
                if not key:
                    output['paid_status'] = 'BLOCKED_MISSING_CREDENTIAL'
                else:
                    provider = PaidAnswerProvider(api_key=key, model=args.answer_model, max_calls=1)
                    try:
                        output['answer'] = await session.answer(provider)
                        output['paid_status'] = 'COMPLETED_OR_ROUTED_ABSTENTION'
                    except Exception as exc:
                        output['paid_status'] = 'FAILED'
                        output['paid_error'] = type(exc).__name__
                    finally:
                        output['paid_usage'] = provider.records
            return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--question', required=True)
    p.add_argument('--scope', choices=('project', 'module', 'all'), default='project')
    for key in ('module-path', 'version', 'library'):
        p.add_argument('--' + key)
    p.add_argument('--checker-url', required=True)
    p.add_argument('--checker-model', required=True)
    p.add_argument('--checker-sha256', required=True)
    p.add_argument('--selector-sha256', required=True)
    p.add_argument('--max-recoveries', type=int, choices=(0, 1, 2), default=1)
    p.add_argument('--answer-model', help='Explicit paid Responses API model; requires OPENAI_API_KEY')
    args = p.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args)), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'status': 'operational_error', 'error_type': type(exc).__name__}))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
