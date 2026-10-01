"""Evaluation-only immutable identities; no timestamps or synthesized evidence."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from typing import Any, Mapping


def write_once_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    """Create atomically without clobbering another run; identical resume is inert."""
    data = (json.dumps(dict(manifest), sort_keys=True, indent=2,
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('freeze mismatch: symlink destination')
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.freeze-', delete=False) as f:
        temporary = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        # Atomic create-if-absent. os.replace would overwrite a competing freeze.
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise ValueError(f'freeze mismatch: {path}') from None
    finally:
        temporary.unlink(missing_ok=True)


def freeze_inputs(repo: Path, output: Path) -> dict[str, Any]:
    """Hash real tracked runtime, evaluator, corpus, tests, lock and installed env."""
    repo, output = Path(repo).resolve(), Path(output).resolve()
    if output.is_relative_to(repo) or repo.is_relative_to(output):
        raise ValueError('run output overlaps source checkout')
    paths = subprocess.check_output(
        ['git', '-C', str(repo), 'ls-files', '-z'], text=True).split('\0')
    hashes = {}
    for name in sorted(p for p in paths if p):
        if (name.startswith(('docmancer/', 'eval/evidence_quality_v2/', 'tests/'))
                or name in {'uv.lock', 'pyproject.toml', 'pytest.ini'}):
            path = repo / name
            if path.is_symlink() or not path.is_file():
                raise ValueError(f'not an ordinary frozen input: {name}')
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    installed = {}
    for name in ('pytest', 'pydantic', 'pydantic-settings', 'regex', 'httpx',
                 'w3lib', 'fastembed', 'mcp', 'sqlite-vec', 'tiktoken'):
        try:
            installed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed[name] = None
    manifest = {'schema_version': 'evidence-sets-freeze-v1', 'files': hashes,
                'python': platform.python_version(), 'installed': installed,
                'mode': {'vectors': False, 'max_tokens': 800, 'max_source_rows': 3}}
    write_once_manifest(output / 'freeze.json', manifest)
    return manifest
