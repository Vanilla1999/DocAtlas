"""Two public lanes on an unchanged main corpus; same-call traces kept separate."""
import asyncio
from copy import deepcopy
import gzip
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch

import docmancer

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / 'experiment'
# Installed runtime must win; only eval support is imported from checkout.
sys.path.append(str(REPO))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from docmancer.core.config import DocmancerConfig
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.service import LibraryDocsService
from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.trace import source_span

TRANSLATIONS = {
    'projectA-Q07': 'Which files does DocAtlas consider project documentation, and how can I see what it missed?',
    'projectA-Q29': 'May text inside README be treated as an instruction to an agent if it says to ignore previous instructions?',
}


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def protocol():
    text = (REPO / 'roadmap/search-quality-2026-10-01/audit/PROJECT_80_REVIEW_RU.md').read_text()
    cases = []
    for line in text.splitlines():
        if not line.startswith('| projectA-'):
            continue
        cells = [cell.strip() for cell in line.split('|')]
        if cells[1] in {'projectA-Q07', 'projectA-Q14', 'projectA-Q29', 'projectA-Q30'}:
            question = cells[2]
            cases.append({'id': cells[1], 'question': question,
                          'lookup': TRANSLATIONS.get(cells[1], question)})
    return cases


async def main():
    OUT.mkdir(exist_ok=False)
    package = Path(docmancer.__file__).resolve().parent
    assert 'site-packages' in package.parts
    main_head = subprocess.check_output(['git', 'rev-parse', 'main'], cwd=REPO, text=True).strip()
    hashes = {}
    for name in subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', main_head, 'docmancer'], cwd=REPO, text=True).splitlines():
        if name.endswith('.py'):
            expected = subprocess.check_output(['git', 'show', f'{main_head}:{name}'], cwd=REPO)
            assert (package / Path(name).relative_to('docmancer')).read_bytes() == expected, name
            hashes[name] = hashlib.sha256(expected).hexdigest()
    work = Path(tempfile.mkdtemp(prefix='bilingual-main-', dir='/tmp/opencode'))
    root = work / 'project'
    root.mkdir()
    archive = subprocess.check_output(['git', 'archive', main_head], cwd=REPO)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(root, filter='data')
    candidates = ProjectMetadataReader().read(root)
    assert candidates.docs_catalog_valid
    corpus = {row.path: hashlib.sha256((root / row.path).read_bytes()).hexdigest() for row in candidates.docs_candidates}
    (root / 'docatlas.yaml').write_text('index:\n  db_path: .docatlas/index.db\n  extracted_dir: .docatlas/extracted\n')
    for cmd in (['git', 'init', '-q'], ['git', 'add', '.'], ['git', '-c', 'user.name=Experiment', '-c', 'user.email=experiment@example.invalid', 'commit', '-qm', 'main corpus fixture']):
        subprocess.run(cmd, cwd=root, check=True)
    cases = protocol()
    save('protocol.json', {'lanes': ['question-only', 'same-need-lookup'], 'cases': cases,
         'english_controls': 'Q14/Q30 retain identical English lookup; no answer-oriented rewrite',
         'activation': False, 'packing_replay': False})
    save('provenance.json', {'main': main_head, 'branch_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
         'version': importlib.metadata.version('doc-atlas'), 'import_path': str(package), 'production_sha256': hashes,
         'fixture': str(root), 'corpus_sha256': corpus, 'corpus_documents': len(corpus)})
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DOCATLAS_', 'DOCMANCER_')) and k != 'PYTHONPATH' and not k.endswith('API_KEY')}
    env.update(DOCATLAS_HOME=str(work / 'home'), DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0', DO_NOT_TRACK='1')
    params = StdioServerParameters(command='/home/viadmin/.local/bin/doc-atlas', args=['mcp', 'docs-serve'], cwd=str(work), env=env)
    requests = []
    with (OUT / 'stderr.log').open('w') as err:
        async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                async def call(name, args, label):
                    wire = await asyncio.wait_for(session.call_tool(name, args), 300)
                    save(label + '.json', {'request': args, 'wire': wire.model_dump(mode='json', by_alias=True)})
                    return wire.structuredContent or json.loads(next(block.text for block in wire.content if block.type == 'text'))
                result = await call('prepare_docs', {'action': 'sync_project_docs', 'project_path': str(root), 'with_vectors': False}, 'sync')
                assert result['status'] == 'success', result
                for case in cases:
                    for lane in ('question-only', 'same-need-lookup'):
                        args = {'question': case['question'], 'project_path': str(root), 'scope': 'all'}
                        if lane == 'same-need-lookup':
                            args['lookup_queries'] = [case['lookup']]
                        await call('get_docs_context', args, case['id'] + '-' + lane)
                        requests.append((case['id'], lane, args))
    os.environ.update(env)
    config = DocmancerConfig.from_yaml(root / 'docatlas.yaml')
    config.index.db_path = str(root / '.docatlas/index.db')
    config.index.extracted_dir = str(root / '.docatlas/extracted')
    service = LibraryDocsService(config=config, config_source='explicit')
    for identity, lane, args in requests:
        windows = []
        cap = RetrievalDispatcher._limit_sections_per_source
        def capture(self, chunks, *a, **kw):
            before = list(chunks)
            after = cap(self, before, *a, **kw)
            windows.append({'before': [source_span(c) for c in before], 'after': [source_span(c) for c in after]})
            return after
        with patch.object(RetrievalDispatcher, '_limit_sections_per_source', capture):
            payload, trace = observe_call(service, args)
        trace['pre_cap_windows'] = windows
        trace['payload'] = payload
        (OUT / f'{identity}-{lane}-trace.json.gz').write_bytes(gzip.compress(json.dumps(trace, ensure_ascii=False, default=str).encode(), mtime=0))
    assert corpus == {row.path: hashlib.sha256((root / row.path).read_bytes()).hexdigest() for row in candidates.docs_candidates}
    print(f'Saved installed-main two-lane packets and separate traces; corpus={len(corpus)}')


if __name__ == '__main__':
    asyncio.run(main())
