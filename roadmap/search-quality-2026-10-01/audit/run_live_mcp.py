"""Fresh installed-artifact stdio audit. Gold is used only AFTER wire persistence."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time

ROOT = Path('/tmp/opencode/docatlas-ablation')
OUT = Path(__file__).resolve().parent
WORK = Path('/tmp/opencode/search-audit-work-20261001')
# Installed production must win over this checkout's modules.
import docmancer
assert '/uv/tools/doc-atlas/' in str(docmancer.__file__), docmancer.__file__
sys.path.append(str(ROOT))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.runtime import write_project
from eval.evidence_quality_v2.semantic import assess_context
from eval.evidence_quality_v2.cost import count_input, percentiles


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def payload_from_wire(wire):
    structured = wire.get('structuredContent')
    if isinstance(structured, dict):
        return structured
    for block in wire.get('content', []):
        if block.get('type') == 'text':
            try:
                parsed = json.loads(block['text'])
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, KeyError):
                pass
    raise ValueError('No JSON public payload in MCP response')


def env_for_server():
    env = {k: v for k, v in os.environ.items() if not k.endswith('API_KEY')}
    env.update(DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0',
               DOCATLAS_MCP_TEXT_FALLBACK='1', DOCATLAS_MCP_DEBUG_ERRORS='1',
               DOCATLAS_HOME=str(WORK / 'home'), DO_NOT_TRACK='1')
    return env


async def call(session, tool, args, dest):
    start = time.perf_counter()
    response = await asyncio.wait_for(session.call_tool(tool, args), timeout=300)
    wire = response.model_dump(mode='json', by_alias=True)
    record = dict(tool=tool, request=args, seconds=time.perf_counter()-start,
                  is_error=response.isError, wire=wire)
    # Unaltered official wire persisted before evaluation.
    save(dest, record)
    return record, payload_from_wire(wire)


def verify_sources(payload, project):
    errors = []
    seen = set()
    for source in payload.get('sources', []):
        eid = source.get('evidence_id')
        if not eid or eid in seen:
            errors.append('missing_or_duplicate_evidence_id')
        seen.add(eid)
        path = (project / str(source.get('path_or_url', ''))).resolve()
        if not path.is_relative_to(project) or not path.is_file():
            errors.append('not_project_file:' + str(path))
            continue
        data = path.read_bytes()
        # This is a canonical evidence-material digest, NOT a file digest.
        # Byte/hash binding requires the private same-call snapshot validator.
        if not re.fullmatch(r'[0-9a-f]{64}', str(source.get('content_sha256') or '')):
            errors.append('invalid_evidence_digest:' + str(path))
        text = data.decode('utf-8')
        snippet = source.get('snippet', '')
        if not snippet or snippet not in text:
            errors.append('non_verbatim:' + str(path))
        lo, hi = source.get('line_start'), source.get('line_end')
        if not isinstance(lo, int) or not isinstance(hi, int) or lo < 1 or hi < lo:
            errors.append('invalid_lines:' + str(path))
        elif snippet not in '\n'.join(text.splitlines()[lo-1:hi]):
            errors.append('line_span_mismatch:' + str(path))
    return errors


def snapshot_index(project, label):
    db_path = project / '.docatlas/docatlas.db'
    with sqlite3.connect('file:' + str(db_path) + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        children = [dict(r) for r in db.execute('SELECT stable_chunk_id,source_path,display_text,line_start,line_end FROM retrieval_children')]
        counts = {t: db.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                  for t in ('sources', 'retrieval_children', 'retrieval_parents')}
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    manifest = []
    for rel in sorted({r['source_path'] for r in children}):
        source = project / rel
        if not source.is_file():
            continue
        data = source.read_bytes()
        manifest.append(dict(path=rel, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)))
        destination = WORK / 'corpus' / label / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    save(OUT / 'raw/index' / (label + '.json'), dict(db_path=str(db_path),
         counts=counts, integrity_check=integrity, manifest=manifest, rows=children))


async def run():
    WORK.mkdir(exist_ok=True)
    params = StdioServerParameters(command='/home/viadmin/.local/bin/doc-atlas',
        args=['mcp', 'docs-serve'], env=env_for_server(), cwd=str(WORK))
    project_cases = []
    for name, prefix in [('questions.json', 'projectA'), ('followup_questions.json', 'projectB')]:
        protocol = json.loads((ROOT / 'experiments/grounded-partial' / name).read_text())
        save(OUT / 'raw/protocol' / name, protocol)
        project_cases.extend([{**c, 'id': prefix + '-' + c['id']} for c in protocol['cases']])
    _, external, manifest = load_protocol()
    save(OUT / 'raw/protocol/external80.json', dict(cases=external, source_manifest=manifest))
    save(OUT / 'raw/runtime.json', dict(production_module=docmancer.__file__,
        version=importlib.metadata.version('doc-atlas'), executable=sys.executable,
        transport='actual installed executable over MCP stdio',
        network='offline environment flags, no OS-enforced network isolation',
        scoring='frozen known witnesses; needs_review is not failure or success'))
    rows = []
    with (OUT / 'raw/docatlas-mcp-stderr.log').open('w') as err:
        async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write) as session:
                save(OUT / 'raw/initialize.json', (await session.initialize()).model_dump(mode='json'))
                save(OUT / 'raw/tools-list.json', (await session.list_tools()).model_dump(mode='json'))
                _, prepared = await call(session, 'prepare_docs', dict(action='sync_project_docs',
                    project_path=str(ROOT), with_vectors=False), OUT / 'raw/lifecycle/fresh-process-sync.json')
                if prepared.get('status') != 'success':
                    raise RuntimeError('Fresh-process project sync failed: ' + json.dumps(prepared))
                await call(session, 'docs_status', dict(action='project', project_path=str(ROOT), details=True),
                           OUT / 'raw/lifecycle/after-status.json')
                snapshot_index(ROOT, 'docatlas-project')
                for lane in ('default', 'all', 'guided'):
                    for case in project_cases:
                        args = dict(question=case['question'], project_path=str(ROOT))
                        if lane != 'default':
                            args['scope'] = 'all'
                        if lane == 'guided':
                            args['lookup_queries'] = case['host_lookups']
                        wire, payload = await call(session, 'get_docs_context', args,
                            OUT / 'raw/project80' / lane / (case['id'] + '.json'))
                        row = dict(id=case['id'], lane=lane, question=case['question'],
                            language=case.get('language'), topic=case['topic'], request=args,
                            seconds=wire['seconds'], payload=payload,
                            tokens=count_input(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))),
                            integrity_errors=verify_sources(payload, ROOT))
                        rows.append(row)
                        save(OUT / 'raw/project80/results.json', rows)
                        print('PROJECT', lane, case['id'], payload.get('status'), len(payload.get('sources',[])), flush=True)
                external_rows = []
                for group in sorted({c['project_group'] for c in external}):
                    project = WORK / 'fixtures' / group
                    write_project(project, documents_for(group, manifest))
                    (project / 'docatlas.yaml').write_text('index:\n  provider: sqlite\n  db_path: .docatlas/docatlas.db\n  extracted_dir: .docatlas/extracted\n')
                    _, prepared = await call(session, 'prepare_docs', dict(action='sync_project_docs',
                        project_path=str(project), with_vectors=False), OUT / 'raw/lifecycle' / (group + '-sync.json'))
                    if prepared.get('status') != 'success':
                        raise RuntimeError('Fixture preparation failed: ' + group)
                    snapshot_index(project, group)
                    for case in [c for c in external if c['project_group'] == group]:
                        args = dict(question=case['question'], project_path=str(project), scope='all')
                        wire, payload = await call(session, 'get_docs_context', args,
                            OUT / 'raw/external80/native' / (case['id'] + '.json'))
                        row = dict(id=case['id'], project=group, family=case['family'],
                            split=case['split'], answerability=case['answerability'], request=args,
                            seconds=wire['seconds'], payload=payload,
                            assessment=assess_context(case, payload, registry_for(group,manifest)),
                            tokens=count_input(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))),
                            integrity_errors=verify_sources(payload, project))
                        external_rows.append(row)
                        save(OUT / 'raw/external80/results.json', external_rows)
                        print('EXTERNAL', case['id'], row['assessment']['context_sufficiency'], flush=True)
                # Bounded resource read diagnostic, not an automatic answer-quality credit.
                for row in rows:
                    if row['lane'] != 'all' or row['id'] not in ('projectA-Q07','projectA-Q15','projectB-Q16','projectB-Q28'):
                        continue
                    for i, source in enumerate(row['payload'].get('sources',[])[:1]):
                        if source.get('source_uri'):
                            start=time.perf_counter()
                            result=await session.read_resource(source['source_uri'])
                            save(OUT / 'raw/resource-reads' / (row['id']+'.json'),dict(
                                id=row['id'],uri=source['source_uri'],seconds=time.perf_counter()-start,
                                wire=result.model_dump(mode='json')))
    summary = dict(project80={}, external80={})
    for lane in ('default','all','guided'):
        selected=[r for r in rows if r['lane']==lane]
        summary['project80'][lane]=dict(cases=len(selected),
            statuses=dict(Counter(r['payload'].get('status') for r in selected)),
            kinds=dict(Counter(r['payload'].get('kind') for r in selected)),
            nonempty=sum(bool(r['payload'].get('sources')) for r in selected),
            integrity_violations=sum(bool(r['integrity_errors']) for r in selected),
            tokens=percentiles(r['tokens']['actual_tokens'] for r in selected),
            latency=percentiles(r['seconds'] for r in selected))
    positives=[r for r in external_rows if r['answerability']=='within_budget']
    summary['external80']=dict(cases=len(external_rows),positives=len(positives),
        recognized_sufficient=sum(r['assessment']['context_sufficiency']=='sufficient' for r in positives),
        assessments=dict(Counter(r['assessment']['context_sufficiency'] for r in external_rows)),
        required_supported=sum(r['assessment']['required_supported'] for r in external_rows),
        required_count=sum(r['assessment']['required_count'] for r in external_rows),
        integrity_violations=sum(bool(r['integrity_errors']) for r in external_rows),
        tokens=percentiles(r['tokens']['actual_tokens'] for r in external_rows),
        latency=percentiles(r['seconds'] for r in external_rows))
    save(OUT / 'raw/live-summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__ == '__main__':
    asyncio.run(run())
