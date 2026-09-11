"""Isolated fixture setup; only corpus files, never annotation files, are indexed."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from unittest.mock import patch


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
        target.write_text(text, encoding='utf-8')
        entries.append(dict(path=relative, role='other', scope='project', description='Pinned documentation source',
                            authority='source_of_truth', status='active', impact='track'))
    (root / 'docatlas.project-docs.yaml').write_text(yaml.safe_dump(
        {'schema_version': 1, 'documents': entries}, sort_keys=False), encoding='utf-8')


@contextmanager
def isolated_service(state: Path):
    import scripts.run_project_docs_self_host_gate as gate
    state.mkdir(parents=True, exist_ok=True)
    env = {key: str(state / key.lower()) for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'DOCATLAS_HOME')}
    env.update(DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0')
    for path in env.values():
        if path not in ('0', '1'):
            Path(path).mkdir(parents=True, exist_ok=True)
    with patch.dict(os.environ, env):
        config = gate.DocmancerConfig()
        config.index.db_path = str(state / 'index.db')
        config.index.extracted_dir = str(state / 'extracted')
        service = gate.LibraryDocsService(config=config, config_source='explicit',
            registry=gate.LibraryRegistry(config.index.db_path),
            agent=gate.DocmancerAgent(config=config), job_tracker=gate.DocsJobTracker())
        yield service, config


def index_project(service, config, root: Path) -> dict:
    start = time.perf_counter()
    result = service.sync_project_docs(str(root), with_vectors=False)
    if result.status != 'success':
        raise RuntimeError(f'fixture ingest failed: {result.status}')
    with sqlite3.connect(config.index.db_path) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute('SELECT stable_chunk_id, source_path, display_text, line_start, line_end FROM retrieval_children')]
        schema = '\n'.join(row[0] or '' for row in db.execute('SELECT sql FROM sqlite_master ORDER BY name'))
    expected = sorted(str(p.relative_to(root)) for p in root.rglob('*.md'))
    indexed = sorted({row['source_path'] for row in rows})
    return {'seconds': time.perf_counter()-start, 'expected_paths': expected,
            'indexed_paths': indexed, 'excluded_or_failed_paths': sorted(set(expected)-set(indexed)),
            'unexpected_paths': sorted(set(indexed)-set(expected)), 'rows': rows,
            'sqlite_version': sqlite3.sqlite_version, 'schema_sha256': digest(schema.encode()),
            'config_sha256': digest(config.model_dump_json().encode())}
