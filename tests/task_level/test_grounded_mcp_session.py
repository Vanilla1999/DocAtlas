"""A real host adapter must retain useful facts across failed follow-up I/O."""
import asyncio
import json
from copy import deepcopy

from docmancer.docs.interfaces.grounded_mcp_session import GroundedMCPSession


class Client:
    def __init__(self):
        self.reads = 0
        self.calls = []
        self.context = {'kind': 'docs_context', 'status': 'ok', 'answer_supported': False,
            'sources': [{'evidence_id': 'primary', 'path_or_url': 'docs/jobs.md',
                'project_identity': 'repo', 'snippet': 'Poll until the job is terminal.',
                'line_start': 1, 'line_end': 1, 'source_uri': 'docatlas://source/' + 'a'*24}]}

    async def call_tool(self, name, arguments):
        self.calls.append((name, deepcopy(arguments)))
        return {'structuredContent': self.context}

    async def read_resource(self, uri):
        self.reads += 1
        raise OSError('disconnected')


def test_failed_read_keeps_grounded_partial_and_stops_repeated_io():
    async def run():
        client = Client()
        session = await GroundedMCPSession.start(client,
            arguments={'question': 'When is a job terminal and when should I retry?', 'project_path': '/repo'},
            requested_facts={'terminal': 'When is the job terminal?', 'retry': 'When may I retry?'})
        session.support('terminal', evidence_id='primary', quote='Poll until the job is terminal.')
        uri = client.context['sources'][0]['source_uri']
        assert (await session.read(uri, missing_fact_id='retry'))['reason_code'] == 'source_read_failed'
        await session.read(uri, missing_fact_id='retry')
        assert client.reads == 1
        result = session.finish()
        assert result['status'] == 'partial'
        assert result['known'][0]['quote'] == 'Poll until the job is terminal.'
        assert result['missing'] == ['When may I retry?']
        assert not result['answer_supported']
        assert len(client.calls) == 1
    asyncio.run(run())


def test_async_resource_binding_and_no_automatic_read_for_a_locator():
    async def run():
        client = Client()
        async def reader(uri):
            client.reads += 1
            return {'contents': [{'text': json.dumps({'status': 'complete',
                'path': 'docs/jobs.md', 'project_identity': 'repo',
                'content_sha256': 'sha256:'+'b'*64, 'line_start': 2, 'line_end': 2,
                'snippet': 'Retry after success.'})}]}
        client.read_resource = reader
        session = await GroundedMCPSession.start(client,
            arguments={'question': 'When may I retry?', 'project_path': '/repo'},
            requested_facts={'retry': 'When may I retry?'})
        assert client.reads == 0
        result = await session.read(client.context['sources'][0]['source_uri'], missing_fact_id='retry')
        assert result['snippet'] == 'Retry after success.'
        session.support('retry', evidence_id='read-1', quote='Retry after success.')
        assert session.finish()['status'] == 'host_assessed_complete'
        assert not session.finish()['answer_supported']
        await session.read(client.context['sources'][0]['source_uri'], missing_fact_id='retry')
        assert client.reads == 1
    asyncio.run(run())


def test_unquoted_claim_and_unadvertised_recovery_are_rejected():
    async def run():
        import pytest
        session = await GroundedMCPSession.start(Client(),
            arguments={'question': 'Is retry safe?', 'project_path': '/repo'},
            requested_facts={'retry': 'Is retry safe?'})
        with pytest.raises(ValueError):
            session.support('retry', evidence_id='primary', quote='Retry is always safe.')
        called = []
        async def search(**kwargs):
            called.append(kwargs)
        result = await session.recover(search)
        assert result['status'] == 'stopped' and not called
        assert session.finish()['status'] == 'insufficient'
    asyncio.run(run())


def test_recovery_is_bounded_preserves_known_facts_and_does_not_repeat():
    async def run():
        client = Client()
        client.context['recommended_next_action'] = {'tool': 'code_search',
            'type': 'search_local_source', 'requires_confirmation': False, 'query_terms': ['retry job']}
        session = await GroundedMCPSession.start(client,
            arguments={'question': 'When is a job terminal and when may I retry?', 'project_path': '/repo'},
            requested_facts={'terminal': 'When is a job terminal?', 'retry': 'When may I retry?'})
        session.support('terminal', evidence_id='primary', quote='Poll until the job is terminal.')
        await session.read(client.context['sources'][0]['source_uri'], missing_fact_id='retry')
        calls = []
        async def search(**kwargs):
            calls.append(kwargs)
            return {'sources': [{'path_or_url': 'src/jobs.py', 'snippet': 'Retry after success.'}]}
        assert (await session.recover(search))['status'] == 'context_added'
        assert session.finish()['stop_reason'] == 'source_read_failed'  # Preserve the concrete failure.
        assert session.finish()['next_step'] is None
        await session.recover(search)
        assert calls == [{'project_path': '/repo', 'query_terms': ('retry job',)}]
        assert session.finish()['status'] == 'partial'
        session.support('retry', evidence_id='recovery-1', quote='Retry after success.')
        assert session.finish()['status'] == 'host_assessed_complete'
    asyncio.run(run())


def test_preparation_issue_is_returned_as_next_step_without_mutation():
    async def run():
        client = Client()
        action = {'tool': 'prepare_docs', 'requires_confirmation': True,
                  'arguments': {'action': 'sync_project_docs', 'project_path': '/repo'}}
        client.context = {'status': 'needs_confirmation', 'kind': 'docs_issue',
                          'recommended_next_action': action}
        session = await GroundedMCPSession.start(client,
            arguments={'question': 'How do jobs work?', 'project_path': '/repo'},
            requested_facts={'jobs': 'How do jobs work?'})
        assert session.finish()['status'] == 'insufficient'
        assert session.finish()['next_step'] == action
        assert client.reads == 0 and len(client.calls) == 1
    asyncio.run(run())
