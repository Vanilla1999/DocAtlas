"""One opt-in development CLI for P and controlled lexical ablations.

Outputs must be outside the checkout. No gold, rubric, model or packet override
is accepted. These runs do not establish OS gold isolation or answer quality.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

from experiments.language_aware_context.baseline_probe import (
    load_sources, validated_request, write_report, _trace_json_default,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name('protocol.json')


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':'), default=_trace_json_default).encode('utf-8')


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
    paths = sorted(set(_git('ls-files', '--cached', '--others', '--exclude-standard').splitlines()))
    inventory = [(path, sha256(_no_symlinks(ROOT / path).read_bytes())) for path in paths
                 if (ROOT / path).is_file() or (ROOT / path).is_symlink()]
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


@contextmanager
def _indexed_native(documents, protocol, base):
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from docmancer.core.sqlite_store import SQLiteStore
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
        filters = {'project_identity': next(iter(identities)), 'project_path': str(project),
                   'source_class': 'project_file', 'project_docs': True,
                   'doc_scope': 'project', 'resolved_version': ''}
        yield store, index, filters, project


def _native_pool(store, documents, filters, request, protocol):
    from .adapters import native_diagnostic
    from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
    references = SourceReferenceContext(store, question=request['question'], filters=filters)
    plan = references.plan(request['question'])
    locators = [r for r in plan['references'] if r['role'] == 'source_locator']
    if locators:
        # Match the actual reference gate's conjunction, including unresolved
        # or ambiguous locators. They must not consume bounded exposure first.
        allowed = set.intersection(*(set(r['source_ids']) if r['state'] == 'resolved' else set()
                                     for r in locators))
        filters = {**filters, 'source': {'in': sorted(key for key, identity in references.sources.items()
                                                    if identity.document_id in allowed)}}
    result = native_diagnostic(store, [request['question'], *request.get('lookup_queries', [])],
        filters=filters, sources=documents, raw_limit=protocol['raw_hits'],
        unique_limit=protocol['unique_candidates'])
    result['root_reference_plan'] = plan
    result['pre_exposure_reference_catalog_sources'] = len(references.sources)
    return result


def _deliver(store, native, documents, project, request, protocol, *, arm='A'):
    from .packet import pack_native
    from eval.evidence_quality_v2.run import audit_payload
    result = deepcopy(native)
    result.update(pack_native(store, native, sources=documents, question=request['question'],
        lookups=request.get('lookup_queries', []), max_tokens=protocol['dto_tokens'],
        source_entries=protocol['source_entries'], sections_per_source=protocol['max_sections_per_source'],
        assembly=arm in ('D_L', 'E_G_L'), soft_gate=arm == 'E_G_L'))
    result['audit_errors'] = audit_payload(result['model_visible_packet'], result['packet_snapshot'], project)
    if result['audit_errors']:
        result['execution_status'] = result['packet_status'] = 'AUDIT_FAILED'
    result.update(arm=arm, native_pool_sha256=sha256(_json(native)),
                  evaluation_kind='source_bound_project_markdown_development')
    return result


def _native_fixture(corpus, spec, request, protocol):
    documents, _ = load_sources(corpus, spec)
    with tempfile.TemporaryDirectory(prefix='docatlas-ablation-') as tmp:
        with _indexed_native(documents, protocol, Path(tmp)) as (store, index, filters, project):
            started = time.perf_counter()
            native = _native_pool(store, documents, filters, request, protocol)
            result = _deliver(store, native, documents, project, request, protocol)
            result.update(index=index, seconds=time.perf_counter() - started)
            return result


def _matrix_fixture(corpus, spec, request, protocol, *, results=None):
    """A/B use one physical fixture path; B/D/E share exact saved native bytes.

    Public project snapshots are the only indexed input. This remains a
    development execution, not an OS-blinded gold/answer evaluation.
    """
    from unittest.mock import patch
    from docmancer.core.sqlite_store import SQLiteStore
    from .structure import canonical_markdown
    from .adapters import observe_native_sql
    documents, _ = load_sources(corpus, spec)
    if results is None:
        results = {}
    with tempfile.TemporaryDirectory(prefix='docatlas-controlled-') as tmp:
        base = Path(tmp) / 'fixture'
        for representation in ('A', 'B'):
            try:
                extracts = {name: canonical_markdown(text) for name, text in documents.items()} if representation == 'B' else {}
            except ValueError as exc:
                if not str(exc).startswith('BLOCKED_REPRESENTATION:'):
                    raise
                for arm in ('B', 'D_L', 'E_G_L'):
                    results[arm] = {'arm': arm, 'execution_status': 'BLOCKED_REPRESENTATION',
                        'blocker': str(exc), 'quality_status': 'UNJUDGED', 'model_visible_packet': None}
                break
            canonical = {name: value['text'] for name, value in extracts.items()} if extracts else documents
            with _indexed_native(canonical, protocol, base) as (store, index, filters, project):
                native = _native_pool(store, canonical, filters, request, protocol)
                # Serialize BEFORE any alternative delivery. Replay this actual
                # pool, not a newly searched list with an equivalent-looking name.
                saved_pool = _json(native)
                before_index = sha256(store.db_path.read_bytes())
                arms = ('A',) if representation == 'A' else ('B', 'D_L', 'E_G_L')
                with observe_native_sql() as replay_sql, patch.object(SQLiteStore, '_search_rows', side_effect=AssertionError('new global search during saved-pool replay')):
                    for arm in arms:
                        started = time.perf_counter()
                        result = _deliver(store, json.loads(saved_pool), canonical, project, request, protocol, arm=arm)
                        if replay_sql.lanes:
                            raise ValueError('new native SQL during saved-pool delivery')
                        if sha256(store.db_path.read_bytes()) != before_index or _json(native) != saved_pool:
                            raise ValueError('saved pool/index mutated during delivery')
                        result.update(index=index, seconds=time.perf_counter()-started,
                            source_artifacts=extracts, canonical_documents=canonical,
                            representation='current-valid-markdown' if arm == 'A' else 'commonmark-source-structure-v1',
                            citation_space='raw_project_snapshot' if arm == 'A' else 'canonical_project_extract',
                            saved_native_pool=json.loads(saved_pool),
                            search_count=native['search_count'] if arm in ('A', 'B') else 0,
                            inherited_search_count=0 if arm in ('A', 'B') else native['search_count'],
                            controlled_project_path=str(project))
                        results[arm] = result
                if representation == 'B':
                    assert results['B']['native_pool_sha256'] == results['D_L']['native_pool_sha256'] == results['E_G_L']['native_pool_sha256']
                    left = _json(results['D_L']['prepared_candidates'])
                    right = _json(results['E_G_L']['prepared_candidates'])
                    if left != right:
                        raise ValueError('soft gate pair did not receive identical prepared input')
                    for arm in ('D_L', 'E_G_L'):
                        results[arm]['pre_gate_input_sha256'] = sha256(left)
            # This is exclusively our own fresh TemporaryDirectory. Reusing the
            # identical physical path controls path-derived identities/budgets.
            shutil.rmtree(base)
    return results


def run_matrix(frozen: Path, output: Path) -> dict:
    manifest = verify_frozen(frozen)
    output = _external_new_directory(output)
    request = json.loads((frozen / 'request.json').read_bytes())
    spec = json.loads((frozen / 'source-manifest.json').read_bytes())
    protocol = json.loads((frozen / 'protocol.json').read_bytes())
    from .adapters import product_probe
    results = {}
    try:
        product = product_probe(frozen / 'corpus', spec, request)
        product['execution_status'] = product['status']
        results['P'] = product
    except Exception as exc:
        results['P'] = {'arm': 'P', 'execution_status': 'BLOCKED_ENV' if isinstance(exc, ModuleNotFoundError) else 'HANDLER_FAILED',
                        'exception_type': type(exc).__name__, 'quality_status': 'UNJUDGED'}
    try:
        _matrix_fixture(frozen / 'corpus', spec, request, protocol, results=results)
    except Exception as exc:
        for arm in ('A', 'B', 'D_L', 'E_G_L'):
            results.setdefault(arm, {'arm': arm, 'execution_status': 'BLOCKED_ENV' if isinstance(exc, ModuleNotFoundError) else 'HANDLER_FAILED',
                'exception_type': type(exc).__name__, 'exception_message': str(exc), 'quality_status': 'UNJUDGED'})
    verify_frozen(frozen)
    for arm, result in results.items():
        result.update(freeze_sha256=sha256((frozen / 'freeze.json').read_bytes()),
            panel=manifest['panel'], product_activation=False, independent_holdout=False,
            agent_evaluation='ANSWER_EVALUATION_NOT_RUN', gold_isolation='NOT_IMPLEMENTED_DEVELOPMENT_ONLY',
            planned_arms=['P', 'A', 'B', 'D_L', 'E_G_L'],
            packet_contract='source-bound-project-v1' if arm != 'P' else 'real-handler')
        write_report(output / arm / 'result.json', result)
    return results

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
    result.update(packet_contract='source-bound-project-v1' if arm == 'A' else 'real-handler',
                  gold_isolation='NOT_IMPLEMENTED_DEVELOPMENT_ONLY',
                  freeze_sha256=sha256((frozen / 'freeze.json').read_bytes()),
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
    matrix = commands.add_parser('matrix')
    matrix.add_argument('--frozen', type=Path, required=True)
    matrix.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze_inputs(args.corpus_dir, json.loads(_no_symlinks(args.source_manifest).read_bytes()),
                      json.loads(_no_symlinks(args.request).read_bytes()), args.output)
        return 0
    if args.command == 'matrix':
        results = run_matrix(args.frozen, args.output)
        print(json.dumps({arm: result['execution_status'] for arm, result in results.items()}))
        return 0 if all(r['execution_status'] == 'EXECUTED' for r in results.values()) else 2
    result = run_frozen(args.frozen, args.output, args.arm)
    print(json.dumps({key: result.get(key) for key in ('arm', 'execution_status', 'packet_status')}))
    return 0 if result['execution_status'] == 'EXECUTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
