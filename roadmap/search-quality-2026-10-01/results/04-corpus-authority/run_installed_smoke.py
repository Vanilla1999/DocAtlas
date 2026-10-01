"""Current/history catalog controls through installed MCP stdio."""
import asyncio
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import docmancer
import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / 'installed'
PATHS = ['docs/adr/0002-context-retrieval-vs-answer-proof.md',
         'docs/adr/0003-context-first-project-reads.md',
         'docs/mcp-docs-server.md', 'eval/project_answer_surface_v1/README.md',
         'eval/project_context_quality/README.md']


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


async def main():
    OUT.mkdir(exist_ok=False)
    installed = Path(docmancer.__file__).resolve().parent
    assert 'site-packages' in installed.parts
    for source in (REPO / 'docmancer').rglob('*.py'):
        assert source.read_bytes() == (installed / source.relative_to(REPO / 'docmancer')).read_bytes()
    work = Path(tempfile.mkdtemp(prefix='authority-stdio-', dir='/tmp/opencode'))
    root = work / 'project'
    root.mkdir()
    catalog = yaml.safe_load((REPO / 'docatlas.project-docs.yaml').read_text())
    entries = [row for row in catalog['documents'] if row['path'] in PATHS]
    assert len(entries) == len(PATHS)
    for path in PATHS:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / path, target)
    (root / 'docatlas.project-docs.yaml').write_text(yaml.safe_dump({'schema_version': 1, 'documents': entries}))
    (root / '.gitignore').write_text('.docatlas/\n')
    (root / 'docatlas.yaml').write_text('index:\n  db_path: .docatlas/project.db\n  extracted_dir: .docatlas/extracted\n')
    for cmd in (['git', 'init', '-q'], ['git', 'add', '.'],
                ['git', '-c', 'user.name=Smoke', '-c', 'user.email=smoke@example.invalid', 'commit', '-qm', 'fixture']):
        subprocess.run(cmd, cwd=root, check=True)
    save('provenance.json', {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
         'runtime_import': str(installed), 'version': importlib.metadata.version('doc-atlas'),
         'fixture': str(root), 'catalog_entries': entries,
         'corpus_sha256': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in PATHS}})
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DOCATLAS_', 'DOCMANCER_')) and k != 'PYTHONPATH' and not k.endswith('API_KEY')}
    env.update(DOCATLAS_HOME=str(work / 'home'), DOCATLAS_AUTO_VECTORS='0', DOCATLAS_OFFLINE='1', DO_NOT_TRACK='1')
    params = StdioServerParameters(command=str(REPO / '.venv/bin/doc-atlas'), args=['mcp', 'docs-serve'], cwd=str(work), env=env)
    with (OUT / 'stderr.log').open('w') as err:
        async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                async def call(name, request, label):
                    wire = await asyncio.wait_for(session.call_tool(name, request), 120)
                    payload = wire.structuredContent
                    if not isinstance(payload, dict):
                        payload = json.loads(next(block.text for block in wire.content if block.type == 'text'))
                    save(label + '.json', {'request': request, 'wire': wire.model_dump(mode='json', by_alias=True)})
                    return payload

                sync = await call('prepare_docs', {'action': 'sync_project_docs', 'project_path': str(root), 'with_vectors': False}, 'sync')
                assert sync['status'] == 'success', sync
                questions = {
                    'current': 'Do current project reads return server-authored docs_answer?',
                    'history': 'What did the historical project-answer surface v1 evaluation protocol freeze?',
                }
                roles = []
                by_path = {row['path']: row for row in entries}
                for label, question in questions.items():
                    result = await call('get_docs_context', {'project_path': str(root), 'question': question}, label)
                    assert result['status'] == 'ok', result
                    sources = result['sources']
                    assert sources
                    for source in sources:
                        path = source['path_or_url']
                        assert path in by_path and source['snippet'] in (root / path).read_text()
                        assert source['evidence_id']
                        roles.append({'query': label, 'evidence_id': source['evidence_id'], **by_path[path]})
                    if label == 'current':
                        assert all(by_path[s['path_or_url']]['status'] == 'active' for s in sources)
                    else:
                        assert any(s['path_or_url'] == 'eval/project_answer_surface_v1/README.md' for s in sources), result
                save('evidence-roles.json', roles)
    print('PASS installed MCP current/history controls')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    OUT = parser.parse_args().output.resolve()
    asyncio.run(main())
