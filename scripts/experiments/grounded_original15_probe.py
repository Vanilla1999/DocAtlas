"""Read-only external experiment; never used by DocAtlas retrieval or acceptance.
Runs the published Grounded Docs MCP against exactly the Markdown source paths
indexed by DocAtlas. Gold witnesses are only read by the post-query scorer.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['EXPERIMENT_OUT']).resolve()
OUT.mkdir(parents=True, exist_ok=True)
BASE = Path(os.environ['BASELINE_ROOT']).resolve()
CORPUS = ROOT / 'eval/direct_docatlas_questions_15/cases.json'
CASES = json.loads(CORPUS.read_text())['cases']
NODE = Path(os.environ['GROUNDED_ENTRY']).resolve()


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + '\n')


def trace(label, project, code):
    # Instrument ONLY the offline observer script to export indexed source paths.
    # Production code, queries, ranking and evidence remain unchanged.
    script = (ROOT / 'eval/direct_docatlas_questions_15/audit_first_loss.py').read_text()
    script = script.replace('connection.close()', 'report["indexed_source_paths"] = sorted({str(r["source_path"]) for r in index_rows})\n            connection.close()')
    script = script.replace('"status": payload.get("status"),', '"raw_payload": payload,\n                    "status": payload.get("status"),')
    observer = OUT / 'observer.py'
    observer.write_text(script)
    env = dict(os.environ, DOCATLAS_CODE_ROOT=str(code), DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0')
    result = subprocess.run([sys.executable, str(observer), '--project-root', str(project), '--corpus', str(CORPUS), '--output', str(OUT / (label + '.json'))], env=env, cwd=code, text=True, capture_output=True, timeout=300)
    (OUT / (label + '.log')).write_text(result.stdout + '\nSTDERR\n' + result.stderr)
    print(label, 'returncode=', result.returncode, result.stdout[-2500:], flush=True)
    if result.returncode:
        raise RuntimeError(label + ' trace failed')
    return json.loads((OUT / (label + '.json')).read_text())


def make_corpus(label, project, paths):
    target = OUT / ('corpus-' + label)
    target.mkdir(exist_ok=True)
    manifest = []
    for rel in paths:
        src = (project / rel).resolve()
        if not src.is_relative_to(project) or not src.is_file() or src.suffix.lower() not in ('.md', '.mdx'):
            continue
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        manifest.append({'path': rel, 'sha256': hashlib.sha256(src.read_bytes()).hexdigest(), 'bytes': src.stat().st_size})
    dump(OUT / ('manifest-' + label + '.json'), manifest)
    return target


def search_texts(wire):
    # Text only, no expected-answer text is injected into the search or response.
    return '\n'.join(c.get('text', '') for c in wire.get('content', []) if c.get('type') == 'text')


async def query_grounded(label, folder):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    env = dict(os.environ)
    # This experiment intentionally uses the provider-free lexical mode.
    for name in list(env):
        if name.endswith('API_KEY') or name in ('OPENAI_BASE_URL', 'AZURE_OPENAI_ENDPOINT'):
            env.pop(name, None)
    env.update(DOCS_MCP_APP_TELEMETRY_ENABLED='false', DO_NOT_TRACK='1', PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1')
    config = OUT / ('grounded-' + label + '.json')
    config.write_text(json.dumps({'app': {'storePath': str(OUT / ('store-' + label)), 'telemetryEnabled': False}, 'scraper': {'maxPages': 10000, 'maxDepth': 30, 'security': {'fileAccess': {'mode': 'allowedRoots', 'allowedRoots': [str(folder)], 'includeHidden': True, 'followSymlinks': False}}}}))
    common = ['--config', str(config), '--store-path', str(OUT / ('store-' + label)), '--no-telemetry', '--no-logo']
    scrape_cmd = ['node', str(NODE), 'scrape', 'docatlas-' + label, folder.as_uri(), '--max-pages', '10000', '--max-depth', '30', *common]
    t0 = time.monotonic()
    proc = subprocess.run(scrape_cmd, env=env, cwd=OUT, capture_output=True, text=True, timeout=600)
    (OUT / ('scrape-' + label + '.log')).write_text(proc.stdout + '\nSTDERR\n' + proc.stderr)
    dump(OUT / ('scrape-' + label + '-meta.json'), {'command': scrape_cmd, 'returncode': proc.returncode, 'seconds': time.monotonic()-t0})
    if proc.returncode:
        raise RuntimeError('Grounded scrape failed: ' + proc.stderr[-1800:])
    params = StdioServerParameters(command='node', args=[str(NODE), 'mcp', '--protocol', 'stdio', '--read-only', *common], env=env, cwd=str(OUT))
    rows = []
    with (OUT / ('mcp-' + label + '-stderr.log')).open('w') as errors:
        async with stdio_client(params, errlog=errors) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = await session.list_tools()
                dump(OUT / ('grounded-' + label + '-init.json'), init.model_dump(mode='json'))
                dump(OUT / ('grounded-' + label + '-tools.json'), tools.model_dump(mode='json'))
                tool = next(t for t in tools.tools if t.name == 'search_docs')
                props = tool.inputSchema.get('properties', {})
                libkey = next((k for k in ('library', 'libraryName', 'library_name') if k in props), None)
                if not libkey or 'query' not in props:
                    raise RuntimeError('Unexpected search schema: ' + json.dumps(tool.inputSchema))
                for lane in ('default', 'limit3'):
                    for case in CASES:
                        args = {libkey: 'docatlas-' + label, 'query': case['question']}
                        if lane == 'limit3':
                            if 'limit' not in props:
                                raise RuntimeError('search_docs has no limit parameter')
                            args['limit'] = 3
                        start = time.monotonic()
                        result = await asyncio.wait_for(session.call_tool('search_docs', args), timeout=90)
                        wire = result.model_dump(mode='json', by_alias=True)
                        text = search_texts(wire)
                        # Only an explicitly labelled lexical diagnostic, not a semantic answer grade.
                        factchecks = {g['id']: any(w['text'].casefold() in text.casefold() for w in g['witnesses']) for g in case['fact_groups']}
                        row = {'id': case['id'], 'lane': lane, 'request': args, 'seconds': time.monotonic()-start, 'isError': result.isError, 'raw': wire, 'text_chars': len(text), 'wire_chars': len(json.dumps(wire, ensure_ascii=False)), 'literal_witness_hits': factchecks}
                        dump(OUT / 'grounded-raw' / label / lane / (case['id'] + '.json'), row)
                        rows.append({k:v for k,v in row.items() if k != 'raw'})
                        print('GROUNDED', label, lane, case['id'], sum(factchecks.values()), '/', len(factchecks), 'chars=', len(text), 'error=', result.isError, flush=True)
    dump(OUT / ('grounded-' + label + '-summary.json'), rows)


def main():
    traces = {}
    for label, project, code in [('baseline', BASE, BASE), ('current', ROOT, ROOT), ('old-code-new-docs', ROOT, BASE), ('new-code-old-docs', BASE, ROOT)]:
        try:
            traces[label] = trace(label, project, code)
        except Exception:
            (OUT / (label + '-error.txt')).write_text(traceback.format_exc())
            print(label, 'FAILED; preserved error', flush=True)
    for label, project in [('baseline', BASE), ('current', ROOT)]:
        try:
            paths = traces[label]['indexed_source_paths']
            folder = make_corpus(label, project, paths)
            asyncio.run(query_grounded(label, folder))
        except Exception:
            (OUT / ('grounded-' + label + '-error.txt')).write_text(traceback.format_exc())
            print('GROUNDED', label, 'FAILED; preserved error', flush=True)
    dump(OUT / 'run-complete.json', {'complete': True, 'note': 'Inspect per-lane errors; completion is not a quality PASS.', 'code_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()})


if __name__ == '__main__':
    main()
