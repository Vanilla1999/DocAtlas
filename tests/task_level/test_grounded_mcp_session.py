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









