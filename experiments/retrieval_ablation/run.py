"""One CLI for freezing inputs and running the isolated T00--T04 diagnostic.

Outputs must be outside the checkout. No gold, rubric, model, or packet override
is accepted. The native arm is not suitable for answer generation.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time

from experiments.language_aware_context.baseline_probe import (
    load_sources, validated_request, write_report,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name('protocol.json')


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def _no_symlinks(path: Path) -> Path:
    path = path.absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError('symlink input/output path')
    return path


def _git(*args: str) -> str:
    return subprocess.run(['git', '-C', str(ROOT), *args], check=True,
        capture_output=True, text=True, timeout=30).stdout.strip()


def runtime_identity() -> dict:
    # Hash actual checkout bytes, not just HEAD: dirty edits must not disappear.
    paths = sorted(set(_git('ls-files').splitlines()) | {
        str(path.relative_to(ROOT)) for path in Path(__file__).parent.glob('*') if path.is_file()})
    inventory = [(path, sha256((ROOT / path).read_bytes())) for path in paths
                 if (ROOT / path).is_file() and not (ROOT / path).is_symlink()]
    if _git('rev-parse', '--is-shallow-repository') != 'false' or _git('ls-files', '--deleted'):
        raise ValueError('full checkout required')
    return {'git_revision': _git('rev-parse', 'HEAD'), 'git_status': _git('status', '--porcelain'),
            'tracked_diff_sha256': sha256(_git('diff', 'HEAD', '--binary').encode()),
            'checkout_bytes_sha256': sha256(_json(inventory)),
            'lock_sha256': sha256((ROOT / 'uv.lock').read_bytes()),
            'python': sys.version, 'sqlite': sqlite3.sqlite_version,
            'platform': platform.platform(),
            'runtime_flags': {key: os.environ.get(key) for key in (
                'DOCATLAS_OFFLINE', 'DOCATLAS_AUTO_VECTORS', 'PYTHONHASHSEED')},
            'packages': sorted({(d.metadata.get('Name', ''), d.version) for d in metadata.distributions()})}


def preflight() -> dict:
    environment = runtime_identity()
    with sqlite3.connect(':memory:') as conn:
        conn.execute('CREATE VIRTUAL TABLE probe USING fts5(text)')
    return {'environment': environment, 'fts5': True,
            'offline': os.environ.get('DOCATLAS_OFFLINE') == '1',
            'fixed_hash_seed': os.environ.get('PYTHONHASHSEED') == '0',
            'auto_vectors_disabled': os.environ.get('DOCATLAS_AUTO_VECTORS') == '0'}


def _external_new_directory(path: Path) -> Path:
    path = _no_symlinks(path)
    if path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('artifacts must be outside the checkout')
    path.mkdir(parents=True, exist_ok=False)
    return path


def freeze_inputs(corpus: Path, spec: dict, request: dict, output: Path) -> dict:
    _no_symlinks(corpus)
    validated_request(request, '/validation-only')
    documents, corpus_hash = load_sources(corpus, spec)
    environment = preflight()
    if not all(environment[key] for key in ('offline', 'auto_vectors_disabled', 'fixed_hash_seed')):
        raise ValueError('set DOCATLAS_OFFLINE=1, DOCATLAS_AUTO_VECTORS=0, PYTHONHASHSEED=0')
    if output.absolute().resolve().is_relative_to(corpus.resolve()):
        raise ValueError('freeze output must be outside the corpus')
    output = _external_new_directory(output)
    protocol = json.loads(PROTOCOL.read_bytes())
    protocol['state'] = 'FROZEN'
    payloads = {'request.json': _json(request), 'source-manifest.json': _json(spec),
                'protocol.json': _json(protocol)}
    payloads.update({'corpus/' + name: text.encode('utf-8') for name, text in documents.items()})
    for name, raw in payloads.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest = {'schema_version': 1, 'files': {name: sha256(raw) for name, raw in payloads.items()},
        'environment': environment['environment'], 'corpus_sha256': corpus_hash,
        'panel': 'frozen_host_lookup' if request.get('lookup_queries') else 'original_only',
        'quality_status': 'UNJUDGED', 'independent_holdout': False}
    write_report(output / 'freeze.json', manifest)
    return manifest


def verify_frozen(root: Path) -> dict:
    _no_symlinks(root)
    manifest = json.loads(_no_symlinks(root / 'freeze.json').read_bytes())
    required = {'schema_version', 'files', 'environment', 'corpus_sha256', 'panel',
                'quality_status', 'independent_holdout'}
    if set(manifest) != required or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
        raise ValueError('invalid freeze manifest')
    if manifest['independent_holdout'] is not False or manifest['quality_status'] != 'UNJUDGED':
        raise ValueError('unreviewed evaluation claim')
    if not isinstance(manifest['files'], dict) or not manifest['files']:
        raise ValueError('invalid frozen files')
    for name, digest in manifest['files'].items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or rel.as_posix() != name or '\\' in name:
            raise ValueError('invalid frozen path')
        target = _no_symlinks(root / name)
        if sha256(target.read_bytes()) != digest:
            raise ValueError('frozen file hash mismatch: ' + name)
    spec = json.loads((root / 'source-manifest.json').read_bytes())
    documents, corpus_hash = load_sources(root / 'corpus', spec)
    expected = {'request.json', 'source-manifest.json', 'protocol.json'} | {'corpus/' + name for name in documents}
    if set(manifest['files']) != expected or corpus_hash != manifest['corpus_sha256']:
        raise ValueError('frozen file inventory mismatch')
    request = json.loads((root / 'request.json').read_bytes())
    validated_request(request, '/validation-only')
    protocol = json.loads((root / 'protocol.json').read_bytes())
    expected_protocol = json.loads(PROTOCOL.read_bytes())
    expected_protocol['state'] = 'FROZEN'
    if protocol != expected_protocol:
        raise ValueError('unreviewed protocol change')
    if _json(manifest['environment']) != _json(runtime_identity()):
        raise ValueError('runtime/check-out changed after freeze')
    if ('frozen_host_lookup' if request.get('lookup_queries') else 'original_only') != manifest['panel']:
        raise ValueError('query panel mismatch')
    return manifest


def _native_fixture(corpus, spec, request, protocol):
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from docmancer.core.sqlite_store import SQLiteStore
    from .adapters import native_diagnostic

    documents, _ = load_sources(corpus, spec)
    with tempfile.TemporaryDirectory(prefix='docatlas-ablation-') as tmp:
        base = Path(tmp)
        project = base / 'project'
        write_project(project, documents)
        with isolated_service(base / 'state') as (service, config):
            config.retrieval.default_mode = 'lexical'
            config.retrieval.max_sections_per_source = protocol['max_sections_per_source']
            index = index_project(service, config, project)
            if index['excluded_or_failed_paths'] or index['unexpected_paths']:
                raise RuntimeError('incomplete or widened fixture index')
            store = SQLiteStore(config.index.db_path)
            with store._connect() as conn:
                generation = store._active_generation_id(conn)
                identities = {row[0] for row in conn.execute(
                    'SELECT DISTINCT project_identity FROM retrieval_children WHERE generation_id = ?', (generation,))}
            if len(identities) != 1 or not next(iter(identities)):
                raise ValueError('fixture project identity is not uniquely bound')
            started = time.perf_counter()
            result = native_diagnostic(store, [request['question'], *request.get('lookup_queries', [])],
                filters={'project_identity': next(iter(identities))}, sources=documents,
                raw_limit=protocol['raw_hits'], unique_limit=protocol['unique_candidates'])
            result.update(index=index, seconds=time.perf_counter() - started)
            return result


def run_frozen(frozen: Path, output: Path, arm: str) -> dict:
    if arm not in ('P', 'A'):
        raise ValueError('only P and diagnostic A are implemented')
    manifest = verify_frozen(frozen)
    output = _external_new_directory(output)
    request = json.loads((frozen / 'request.json').read_bytes())
    spec = json.loads((frozen / 'source-manifest.json').read_bytes())
    protocol = json.loads((frozen / 'protocol.json').read_bytes())
    try:
        if arm == 'P':
            from .adapters import product_probe
            result = product_probe(frozen / 'corpus', spec, request)
            result['execution_status'] = result['status']
        else:
            result = _native_fixture(frozen / 'corpus', spec, request, protocol)
    except ModuleNotFoundError as exc:
        result = {'arm': arm, 'execution_status': 'BLOCKED_ENV', 'missing_module': exc.name,
                  'quality_status': 'UNJUDGED'}
    except Exception as exc:
        result = {'arm': arm, 'execution_status': 'HANDLER_FAILED',
                  'exception_type': type(exc).__name__, 'quality_status': 'UNJUDGED'}
    # Detect unexpected code/input writes during the run before accepting it.
    verify_frozen(frozen)
    result.update(freeze_sha256=sha256((frozen / 'freeze.json').read_bytes()),
                  panel=manifest['panel'], product_activation=False,
                  agent_evaluation='ANSWER_EVALUATION_NOT_RUN')
    write_report(output / 'result.json', result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze')
    freeze.add_argument('--corpus-dir', type=Path, required=True)
    freeze.add_argument('--source-manifest', type=Path, required=True)
    freeze.add_argument('--request', type=Path, required=True)
    freeze.add_argument('--output', type=Path, required=True)
    run = commands.add_parser('run')
    run.add_argument('--frozen', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--arm', choices=['P', 'A'], required=True)
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze_inputs(args.corpus_dir, json.loads(_no_symlinks(args.source_manifest).read_bytes()),
                      json.loads(_no_symlinks(args.request).read_bytes()), args.output)
        return 0
    result = run_frozen(args.frozen, args.output, args.arm)
    print(json.dumps({key: result.get(key) for key in ('arm', 'execution_status', 'packet_status')}))
    return 0 if result['execution_status'] == 'EXECUTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
