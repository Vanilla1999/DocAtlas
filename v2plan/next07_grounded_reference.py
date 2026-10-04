"""I.1: actual pinned packaged CLI, unchanged fixtures and native baseline."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from v2plan.next07_grounded_run import save, sha


def fixture_inputs(checkout):
    """Evaluate only the original test's docs/question expressions, not its asserts."""
    tree = ast.parse((checkout / 'tests/docs/test_need_local_admission.py').read_text())
    test = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
        and n.name == 'test_separate_default_and_exception_survive_long_root')
    rows = []
    parameters = test.decorator_list[0].args[1]
    for value, error in ast.literal_eval(parameters):
        docs = next(n.value for n in test.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'docs' for t in n.targets))
        call = next(n.value for n in test.body if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
            and n.value.func.id == 'capture_fixture')
        documents = eval(compile(ast.Expression(docs), '<frozen-fixture>', 'eval'), {'__builtins__': {}}, {'value': value, 'error': error})
        rows.append((value, error, documents, ast.literal_eval(call.args[2])))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--install', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    protocol = json.loads((out / 'protocol.json').read_text())
    checkout = Path(protocol['isolation']['checkout'])
    assert json.loads((out / 'i0-result.json').read_text())['verdict'] == 'DONE'
    results_dir = out / 'reference'
    results_dir.mkdir(exist_ok=False)
    work = Path('/tmp/opencode') / ('next07-' + out.name + '-reference')
    work.mkdir(exist_ok=False)
    install = args.install.resolve()
    package_root = install / 'node_modules/@arabold/docs-mcp-server'
    package = json.loads((package_root / 'package.json').read_text())
    assert package['name'] == '@arabold/docs-mcp-server' and package['version'] == '3.2.1'
    entry = package_root / package['bin']['docs-mcp-server']
    lock = json.loads((install / 'package-lock.json').read_text())
    locked = lock['packages']['node_modules/@arabold/docs-mcp-server']
    assert locked['version'] == '3.2.1' and locked['integrity']
    save(results_dir / 'package-manifest.json', {'package': package, 'lock_entry': locked,
        'installed_files_sha256': {str(p.relative_to(package_root)): sha(p.read_bytes())
            for p in sorted(package_root.rglob('*')) if p.is_file()},
        'entry': str(entry), 'lock_sha256': sha((install / 'package-lock.json').read_bytes())})
    env = {k: os.environ[k] for k in ('PATH', 'LANG') if k in os.environ}
    env.update(HOME=str(work / 'home'), DO_NOT_TRACK='1', DOCS_MCP_APP_TELEMETRY_ENABLED='false',
        PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1')
    (work / 'home').mkdir()

    def invoke(command, target, cwd=work):
        result = subprocess.run(command, env=env, cwd=cwd, capture_output=True, text=True, timeout=240)
        save(target, {'command': command, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode:
            raise RuntimeError(f'command failed; preserved {target}')
        return result.stdout

    for mode in ('scrape', 'search'):
        invoke(['node', str(entry), mode, '--help'], results_dir / (mode + '-help.json'))
    registry = json.loads(invoke(['npm', 'view', '@arabold/docs-mcp-server@3.2.1', 'dist', '--json'], results_dir / 'registry.json'))
    assert registry['integrity'] == locked['integrity']
    ref = invoke(['git', 'ls-remote', 'https://github.com/arabold/docs-mcp-server.git', 'refs/tags/v3.2.1', 'refs/tags/v3.2.1^{}'], results_dir / 'upstream-ref.json')
    assert protocol['grounded']['source_sha'] in ref
    # npm pack checks the registry tarball integrity and records its file manifest.
    packed = json.loads(invoke(['npm', 'pack', '@arabold/docs-mcp-server@3.2.1', '--json'], results_dir / 'npm-pack.json'))[0]
    assert packed['integrity'] == locked['integrity']
    import tarfile
    with tarfile.open(work / packed['filename']) as archive:
        equality = {}
        for member in archive.getmembers():
            if member.isfile():
                relative = member.name.removeprefix('package/')
                equality[relative] = archive.extractfile(member).read() == (package_root / relative).read_bytes()
    save(results_dir / 'registry-byte-verification.json', {'all_equal': all(equality.values()), 'files_equal': equality})
    assert all(equality.values())
    summary = []
    for value, error, documents, question in fixture_inputs(checkout):
        row_dir = results_dir / str(value)
        row_dir.mkdir()
        case = work / str(value)
        corpus = case / 'corpus'
        corpus.mkdir(parents=True)
        config = {'app': {'storePath': str(case / 'store'), 'telemetryEnabled': False},
            'scraper': {'maxPages': 1, 'maxDepth': 1, 'security': {'fileAccess': {
                'mode': 'allowedRoots', 'allowedRoots': [str(corpus)], 'includeHidden': False, 'followSymlinks': False}}}}
        save(case / 'config.json', config)
        save(row_dir / 'config.json', config)
        source_rows = []
        for name, text in documents.items():
            target = corpus / name
            target.write_bytes(text.encode())
            (row_dir / name).write_bytes(text.encode())
            source_rows.append({'path': name, 'sha256': sha(text.encode()), 'bytes': len(text.encode())})
            invoke(['node', str(entry), 'scrape', 'lease-fixture', target.as_uri(), '--max-pages', '1',
                '--max-depth', '1', '--no-clean', '--config', str(case / 'config.json'), '--store-path',
                str(case / 'store'), '--no-telemetry', '--no-logo'], row_dir / ('scrape-' + name + '.json'))
        raw = invoke(['node', str(entry), 'search', 'lease-fixture', question, '--limit', '3', '--output', 'json',
            '--config', str(case / 'config.json'), '--store-path', str(case / 'store'), '--no-telemetry', '--no-logo'],
            row_dir / 'search.json')
        results = json.loads(raw)
        databases = list((case / 'store').rglob('*.db'))
        assert len(databases) == 1
        with sqlite3.connect(f'file:{databases[0]}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            chunks = [dict(r) for r in db.execute('SELECT d.id,d.content,d.metadata,d.sort_order,p.url FROM documents d JOIN pages p ON p.id=d.page_id ORDER BY d.id')]
            count = db.execute('SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL').fetchone()[0]
        save(row_dir / 'chunks.json', chunks)
        save(row_dir / 'sources.json', source_rows)
        visible = '\n'.join(r['content'] for r in results)
        checks = {'default': f'{value} seconds' in visible, 'exception_with_condition': any(
            f'An expired operation raises `{error}`.' in r['content'] for r in results),
            'owners': all('LeaseClient' in r['content'] for r in results if f'{value} seconds' in r['content'] or error in r['content']),
            'zero_embeddings': count == 0}
        # Capture N in a separate isolated process; no chat-agent/SQL substitute.
        native_script = ('import json; from pathlib import Path; from tests.docs._global_evidence_fixtures import capture_fixture; '
            f'docs={documents!r}; capture=capture_fixture(Path({str(case / "native")!r}), docs, {question!r}); '
            f'Path({str(row_dir / "native-capture.json")!r}).write_text(json.dumps(capture,ensure_ascii=False,indent=2,default=str)+"\\n")')
        native_env = dict(env, DOCATLAS_OFFLINE='1')
        result = subprocess.run([protocol['python'], '-c', native_script], cwd=checkout, env=native_env, capture_output=True, text=True, timeout=240)
        save(row_dir / 'native-command.json', {'command': result.args, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        summary.append({'parameter': [value, error], 'checks': checks, 'native_exit': result.returncode,
            'results': results, 'size': {'raw_json_utf8_bytes': len(raw.encode()), 'raw_json_chars': len(raw)},
            'grounded_budget_parity': 'NOT_CLAIMED; search limit is not whole-DTO budget'})
    save(results_dir / 'summary.json', {'rows': summary, 'verdict': 'DONE' if all(all(r['checks'].values()) and r['native_exit'] == 0 for r in summary) else 'REJECTED',
        'transport': 'actual packaged CLI SearchTool; not MCP transport', 'reader': 'NOT_RUN',
        'normalized_output': 'not attested as original spans'})
    print(json.dumps({'out': str(results_dir), 'checks': [r['checks'] for r in summary]}))


if __name__ == '__main__':
    main()
