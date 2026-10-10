"""Isolated fixture setup; only corpus files, never annotation files, are indexed."""
from __future__ import annotations
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import threading
import time
from unittest.mock import patch

from docmancer.mcp._docs_server_part01 import LocalMemberService


# Environment selection is process-wide. Serialize fixture lifetimes, and keep
# each host-selected store alive for the driver's same-fixture replay lanes.
_ENV_LOCK = threading.RLock()
_FIXTURE_HOMES: dict[Path, TemporaryDirectory] = {}


class _FixtureService(LocalMemberService):
    """Expose the real service only after the public cold preparation succeeds.

    Same-call observers set/delete attributes on their service. Forward those
    operations too, so they observe the actual materialized production facade.
    """

    def __init__(self, cold):
        object.__setattr__(self, '_cold', cold)

    def materialize(self, *, read_only_startup: bool = False):
        return self._cold.materialize(read_only_startup=read_only_startup)

    def __getattr__(self, name):
        if name in {'config', 'config_source', 'config_path', 'member_storage_policy'}:
            return getattr(self._cold, name)
        return getattr(self.materialize(read_only_startup=True), name)

    def __setattr__(self, name, value):
        setattr(self.materialize(read_only_startup=True), name, value)

    def __delattr__(self, name):
        delattr(self.materialize(read_only_startup=True), name)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def write_project(root: Path, documents: dict[str, str]) -> None:
    """No QA data in this function's interface. Real sources are copied unchanged."""
    import yaml
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for relative, text in sorted(documents.items()):
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError('source escapes fixture root')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode('utf-8'))
        entries.append(dict(path=relative, role='other', scope='project', description='Pinned documentation source',
                            authority='source_of_truth', status='active', impact='track'))
    (root / 'docatlas.project-docs.yaml').write_text(yaml.safe_dump(
        {'schema_version': 1, 'code_files': [], 'documents': entries}, sort_keys=False), encoding='utf-8')


@contextmanager
def isolated_service(state: Path):
    from docmancer.mcp._docs_server_part01 import create_local_mcp_service
    state = state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    with _ENV_LOCK:
        if state not in _FIXTURE_HOMES:
            # Artifact directories can have group-writable ancestors. They must
            # never be storage ancestors; /tmp is sticky and mkdtemp is private.
            _FIXTURE_HOMES[state] = TemporaryDirectory(prefix='docatlas-evidence-', dir='/tmp')
        home = Path(_FIXTURE_HOMES[state].name)
        env = {key: value for key, value in os.environ.items() if not key.startswith('DOCATLAS_')}
        env.update({key: str(home / key.lower()) for key in (
            'HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'DOCATLAS_HOME')})
        env.update(DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0')
        with patch.dict(os.environ, env, clear=True):
            # This production factory ignores project/CWD config and creates no
            # registry, agent, database or ownership marker on a cold store.
            cold = create_local_mcp_service()
            yield _FixtureService(cold), cold.config


def index_project(service, config, root: Path) -> dict:
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import CATALOG_FILENAME, read_project_docs_catalog
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
    start = time.perf_counter()
    root = root.resolve()
    if (root / 'docatlas.yaml').exists() or (root / 'docatlas.yaml').is_symlink():
        raise ValueError('fixture must not inherit project configuration')
    catalog = read_project_docs_catalog(root)
    if not catalog.present or not catalog.valid or catalog.roots or catalog.code_files or not catalog.entries:
        raise ValueError('fixture requires a nonempty finite docs-only catalog')
    cold = service._cold
    policy = cold.member_storage_policy
    if config is not cold.config or config.index.db_path != str(policy.db_path):
        raise ValueError('fixture config must use the same host-selected member store')
    exists = policy.validate(root, config.index.db_path)
    documents = [{'path': entry.path, 'content_sha256': digest((root / entry.path).read_bytes()),
                  'catalog_entry_hash': catalog_entry_hash(entry)} for entry in catalog.entries]
    mutation = {'operation': 'sync_project_docs', 'confirm': True,
                'storage_path': str(policy.db_path),
                'catalog_sha256': digest((root / CATALOG_FILENAME).read_bytes()),
                'expected_generation_id': policy.generation() if exists else None,
                'documents': documents}
    result = call_docs_tool_payload('prepare_docs', {
        'action': 'sync_project_docs', 'project_path': str(root), 'mutation': mutation,
    }, cold)
    if result.get('status') != 'success':
        raise RuntimeError(f'fixture ingest failed: {result}')
    generation = result['metrics']['generation_id']
    # Diagnostics read the committed host target, never open a second/eager DB.
    with closing(policy.connect()) as db:
        rows = [dict(row) for row in db.execute(
            'SELECT stable_chunk_id, source_path, display_text, line_start, line_end FROM retrieval_children WHERE generation_id = ?',
            (generation,))]
        schema = '\n'.join(row[0] or '' for row in db.execute('SELECT sql FROM sqlite_master ORDER BY name'))
    expected = sorted(entry.path for entry in catalog.entries)
    indexed = sorted({row['source_path'] for row in rows})
    return {'seconds': time.perf_counter()-start, 'expected_paths': expected,
            'indexed_paths': indexed, 'excluded_or_failed_paths': sorted(set(expected)-set(indexed)),
            'unexpected_paths': sorted(set(indexed)-set(expected)), 'rows': rows,
            'sqlite_version': sqlite3.sqlite_version, 'schema_sha256': digest(schema.encode()),
            'config_sha256': digest(config.model_dump_json().encode()),
            'storage_path': str(policy.db_path), 'generation_id': generation,
            'catalog_sha256': mutation['catalog_sha256'], 'documents': documents,
            'transaction_metrics': result['metrics']}
