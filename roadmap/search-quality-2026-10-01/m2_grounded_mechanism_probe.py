"""External diagnostic only: Grounded 3.2.1 on unchanged frozen source bytes.

No DocAtlas runtime, fixtures or thresholds are modified. Install the pinned
Grounded package separately and supply a fresh --work directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def summarize(work, output):
    from math import ceil
    from eval.evidence_quality_v2.cost import count_input

    data = json.loads((work / 'mechanism.json').read_text())
    top = data['initial_hits'][0]
    first = data['native']['3'][0]
    old_root = 'file:///tmp/opencode/search-audit-work-20261001/grounded/corpus'
    new_root = (work / 'corpus').as_uri()
    audit = ROOT / 'roadmap/search-quality-2026-10-01/audit/raw/grounded'

    def size(text):
        return {**count_input(text), 'ceil_utf8_bytes_over_4': ceil(len(text.encode()) / 4)}

    def render(results):
        return ''.join(f"\n------------------------------------------------------------\nResult {i+1}: {r['url']}\n\n{r['content']}\n"
                       for i, r in enumerate(results))

    equal = {}
    for limit in (3, 5):
        old = json.loads((audit / f'native/{limit}/mkdocs-05.json').read_text())
        equal[str(limit)] = old['wire']['content'][0]['text'].replace(old_root, new_root) == render(data['native'][str(limit)])
    docatlas = {}
    for name in ('docatlas-native', 'docatlas-ablation'):
        path = work / (name + '.json')
        if path.exists():
            capture = json.loads(path.read_text())
            docatlas[name] = {k: capture[k] for k in ('diagnostic_mode', 'corpus_hash', 'summary',
                'projection_candidate_counts', 'visible_sources', 'answer_supported', 'edit_ready')}
            docatlas[name]['witness_qualifications'] = [
                {'reason': r['reason'], **{k: r['trace'].get(k) for k in ('matched_terms', 'match_ratio', 'missing_exact_terms')}}
                for r in capture['qualifications'] if r['witness']]
            docatlas[name]['witness_context_checks'] = [r for r in capture['context_checks'] if r['witness']]
    summary = {
        'case_id': 'mkdocs-05', 'date': '2026-10-02', 'package_version': data['package_version'],
        'source_ref': 'f2938c47bb8937c650f0d5ddb614f867773b29f4',
        'source_manifest_sha256': data['source_manifest_sha256'], 'question': data['question'],
        'raw_artifact': str(work / 'mechanism.json'),
        'raw_artifact_sha256': hashlib.sha256((work / 'mechanism.json').read_bytes()).hexdigest(),
        'corpus': data['corpus'], 'ingest': data['ingest'], 'fts_query': data['fts_query'],
        'initial_hits': [{**{k: r[k] for k in ('id', 'rank', 'sort_order', 'fts_score', 'witness', 'metadata')},
                          'size': size(r['content']), 'content_sha256': hashlib.sha256(r['content'].encode()).hexdigest()}
                         for r in data['initial_hits']],
        'top_hit_content': top['content'],
        'checks': {
            'top_hit_equals_first_assembled_body': top['content'] == first['content'],
            'limit1_equals_limit3_first_result': data['native']['1'][0] == first,
            'no_neighbors_first_result_unchanged': data['no_neighbors_parent_enabled'][0] == first,
            'old_native_equal_after_url_prefix_normalization': equal,
            'zero_embeddings_all_libraries': all(r['non_null_embeddings'] == 0 for r in data['ingest']),
        },
        'result_chunks': data['result_chunks'],
        'native_sizes_new_url': {k: size(render(rs)) for k, rs in data['native'].items()},
        'native_sizes_old_url': {k: size(render(rs).replace(new_root, old_root)) for k, rs in data['native'].items()},
        'docatlas_recheck': docatlas,
        'limitations': [
            'Same source bytes and query, not identical chunking or budget.',
            'Initial-hit ranking is a read-only SQL replay; assembled output is an actual packaged CLI run.',
            'MCP formatting is reconstructed from pinned mcpServer.ts; not a new MCP transport run.',
            'No-neighbors configuration leaves parent lookup enabled; exact body equality independently excludes added parent bytes for Result 1.',
            'No LLM reader answer evaluated; no aggregate quality claim.',
        ],
    }
    save(output, summary)
    print(json.dumps({'artifact': str(output), 'checks': summary['checks'],
                      'native_sizes': summary['native_sizes_new_url']}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node-entry', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path,
                        help='Summarize an existing run without ingest or search')
    args = parser.parse_args()
    entry, work = args.node_entry.resolve(), args.work.resolve()
    if args.summary_output:
        summarize(work, args.summary_output)
        return
    work.mkdir(parents=True, exist_ok=False)
    package = json.loads((entry.parent.parent / 'package.json').read_text())
    assert package['version'] == '3.2.1'
    evaluation = ROOT / 'eval/evidence_quality_v2'
    protocol = json.loads((evaluation / 'protocol.json').read_text())
    for filename, key in [('cases.json', 'cases_sha256'), ('source-manifest.json', 'source_sha256')]:
        assert hashlib.sha256((evaluation / filename).read_bytes()).hexdigest() == protocol[key]
    manifest = json.loads((evaluation / 'source-manifest.json').read_text())
    cases = json.loads((evaluation / 'cases.json').read_text())['cases']
    case = next(c for c in cases if c['id'] == 'mkdocs-05')
    question = case['question']
    witness = case['required_claims'][0]['witness_sets'][0]['parts'][0]['text']
    contains = lambda text: ' '.join(witness.split()) in ' '.join(text.split())
    config = {'app': {'storePath': str(work / 'store'), 'telemetryEnabled': False},
              'scraper': {'maxPages': 10000, 'maxDepth': 30, 'security': {'fileAccess': {
                  'mode': 'allowedRoots', 'allowedRoots': [str(work / 'corpus')],
                  'includeHidden': True, 'followSymlinks': False}}}}
    save(work / 'config.json', config)
    env = {k: v for k, v in os.environ.items()
           if not k.endswith('API_KEY') and not k.startswith('DOCS_MCP_')
           and k not in ('OPENAI_BASE_URL', 'AZURE_OPENAI_ENDPOINT')}
    env.update(PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1', DO_NOT_TRACK='1',
               DOCS_MCP_APP_TELEMETRY_ENABLED='false', HOME=str(work / 'home'))
    (work / 'home').mkdir()

    def invoke(arguments, name, config_name='config.json'):
        command = ['node', str(entry), *arguments, '--config', str(work / config_name),
                   '--store-path', str(work / 'store'), '--no-telemetry', '--no-logo']
        result = subprocess.run(command, env=env, cwd=work, capture_output=True, text=True, timeout=240)
        save(work / f'{name}.json', {'command': command, 'returncode': result.returncode,
                                   'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode:
            raise RuntimeError(f'{name} failed; see {work / (name + ".json")}')
        return result.stdout

    # Preserve the full 14-file/8-library FTS corpus, not just MkDocs: BM25 IDF
    # statistics are global to the FTS table despite version-scoped selection.
    corpus = []
    for group in sorted({row['project'] for row in manifest['sources']}):
        for row in (r for r in manifest['sources'] if r['project'] == group):
            raw = (evaluation / 'sources' / group / row['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == row['sha256']
            target = work / 'corpus' / group / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            invoke(['scrape', group, target.as_uri(), '--max-pages', '1', '--max-depth', '1', '--no-clean'],
                   f'ingest/{len(corpus):02d}')
            corpus.append({'project': group, 'path': row['path'], 'sha256': row['sha256']})

    native = {}
    for limit in (1, 3, 5):
        native[str(limit)] = json.loads(invoke(['search', 'mkdocs', question, '--limit', str(limit), '--output', 'json'],
                                             f'search-{limit}'))
    # Configured expansion ablation: parents remain enabled. This is NOT a
    # complete no-expansion run; the initial-hit SQL replay below isolates that.
    save(work / 'no-neighbors.json', {**config, 'assembly': {
        'childLimit': 0, 'precedingSiblingsLimit': 0, 'subsequentSiblingsLimit': 0}})
    reduced = json.loads(invoke(['search', 'mkdocs', question, '--limit', '3', '--output', 'json'],
                                'search-no-neighbors-3', 'no-neighbors.json'))
    databases = list((work / 'store').rglob('*.db'))
    assert len(databases) == 1, databases
    db = sqlite3.connect(f'file:{databases[0]}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    # The exact quote-free request exercises the unquoted branch of
    # DocumentStore.escapeFtsQuery. No stopwords, aliases or answer terms added.
    assert '"' not in question
    fts_query = '"' + question + '" OR ' + ' OR '.join('"' + t + '"' for t in question.split(' '))
    version = db.execute("SELECT v.id FROM versions v JOIN libraries l ON l.id=v.library_id WHERE l.name='mkdocs'").fetchall()
    assert len(version) == 1
    hits = [dict(r) for r in db.execute('''
        SELECT d.id, d.content, d.metadata, d.sort_order,
               bm25(documents_fts,10.0,1.0,5.0,1.0) AS fts_score
        FROM documents_fts f JOIN documents d ON f.rowid=d.id JOIN pages p ON d.page_id=p.id
        WHERE p.version_id=? AND documents_fts MATCH ?
          AND NOT EXISTS (SELECT 1 FROM json_each(json_extract(d.metadata,'$.types')) je WHERE je.value='structural')
        ORDER BY fts_score LIMIT 7
    ''', (version[0]['id'], fts_query))]
    for index, hit in enumerate(hits, 1):
        hit.update(rank=index, witness=contains(hit['content']), metadata=json.loads(hit['metadata']))
    chunks = [dict(r) for r in db.execute('''SELECT d.id,d.content,d.sort_order,d.metadata
        FROM documents d JOIN pages p ON p.id=d.page_id WHERE p.version_id=? ORDER BY d.sort_order''', (version[0]['id'],))]
    for chunk in chunks:
        chunk.update(metadata=json.loads(chunk['metadata']), witness=contains(chunk['content']))
    result_chunks = {}
    for limit, results in native.items():
        result_chunks[limit] = [{'score': r['score'], 'witness': contains(r['content']),
            'chunk_ids': [c['id'] for c in chunks if c['content'] in r['content']],
            'chars': len(r['content'])} for r in results]
    ingest = [dict(r) for r in db.execute('''SELECT l.name,COUNT(d.id) AS chunks,
        SUM(d.embedding IS NOT NULL) AS non_null_embeddings,COUNT(DISTINCT p.url) AS urls
        FROM documents d JOIN pages p ON p.id=d.page_id JOIN versions v ON v.id=p.version_id
        JOIN libraries l ON l.id=v.library_id GROUP BY l.name ORDER BY l.name''')]
    summary = {'package_version': package['version'], 'question': question, 'source_manifest_sha256': protocol['source_sha256'],
               'corpus': corpus, 'ingest': ingest, 'fts_query': fts_query, 'initial_hits': hits,
               'chunks': chunks, 'native': native, 'result_chunks': result_chunks,
               'no_neighbors_parent_enabled': reduced,
               'notes': ['Native search via packaged CLI using SearchTool, also used by MCP.',
                         'SQL replay adds sort_order for observation, preserves native FTS rank expression/filter.',
                         'Chunk containment observer uses indexed text only; witness never enters selection.',
                         'External diagnostic; not an equal-budget DocAtlas benchmark.']}
    save(work / 'mechanism.json', summary)
    print(json.dumps({'ingest': ingest, 'initial_hits': [{k: h[k] for k in ('id','rank','sort_order','fts_score','witness')} for h in hits],
                      'result_chunks': result_chunks, 'artifact': str(work / 'mechanism.json')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
