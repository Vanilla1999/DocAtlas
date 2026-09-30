"""Opt-in real-handler DEVELOPMENT probe; no simulated search or model answers.

Run as a module from a full checkout. Only manifest-listed source bytes are
indexed. No labels, profiles or modified assembly are injected by this probe.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any

from .reference_core import make_request


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_sources(root: Path, spec: dict) -> tuple[dict[str, str], str]:
    """An explicit source manifest is required; never glob a directory of labels."""
    if (not isinstance(spec, dict) or set(spec) != {'schema_version', 'sources'}
            or type(spec['schema_version']) is not int or spec['schema_version'] != 1
            or not isinstance(spec['sources'], list) or not spec['sources']):
        raise ValueError('invalid source manifest')
    if root.is_symlink():
        raise ValueError('symlink corpus root')
    root = root.resolve(strict=True)
    documents: dict[str, str] = {}
    for row in spec['sources']:
        if not isinstance(row, dict) or set(row) != {'path', 'sha256'}:
            raise ValueError('invalid source row')
        name = row['path']
        if not isinstance(name, str) or not name or '\\' in name:
            raise ValueError('invalid source path')
        rel = PurePosixPath(name)
        if (rel.is_absolute() or '..' in rel.parts or rel.as_posix() != name
                or rel.suffix != '.md' or name in documents):
            raise ValueError('invalid or duplicate source path')
        expected = row['sha256']
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError('invalid source hash')
        current = root
        for part in rel.parts:
            current /= part
            if current.is_symlink():
                raise ValueError('source path contains a symlink')
        target = current.resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError('source path escapes corpus or is not a file')
        raw = target.read_bytes()
        if _digest(raw) != expected:
            raise ValueError('source hash mismatch: ' + name)
        documents[name] = raw.decode('utf-8')
    canonical = json.dumps(sorted((name, _digest(text.encode('utf-8')))
        for name, text in documents.items()), ensure_ascii=False, separators=(',', ':'))
    return documents, _digest(canonical.encode('utf-8'))


def validated_request(supplied: dict, project_path: str) -> dict:
    if (not isinstance(supplied, dict) or 'question' not in supplied
            or set(supplied) - {'question', 'lookup_queries'}):
        raise ValueError('request may contain only question and lookup_queries')
    return make_request(supplied['question'], supplied.get('lookup_queries', []),
                        project_path=project_path, scope='all')


def _trace_json_default(value: object) -> list[str]:
    """Observer requirement-ID sets have no order; encode them deterministically.

    Do not use default=str: that would silently corrupt unknown trace objects.
    """
    if isinstance(value, (set, frozenset)) and all(isinstance(item, str) for item in value):
        return sorted(value)
    raise TypeError(f'unsupported trace value: {type(value).__name__}')


def write_report(path: Path, result: dict) -> None:
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False,
                         default=_trace_json_default) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(encoded)


def environment() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    def git(*args: str) -> str | None:
        completed = subprocess.run(['git', '-C', str(root), *args],
            capture_output=True, text=True, check=False, timeout=10)
        return completed.stdout.strip() if completed.returncode == 0 else None
    packages = sorted({(d.metadata.get('Name') or '', d.version)
                       for d in metadata.distributions()})
    return {'python': sys.version, 'sqlite': sqlite3.sqlite_version,
            'packages': packages, 'git_revision': git('rev-parse', 'HEAD'),
            'git_status': git('status', '--porcelain'),
            'tracked_diff_sha256': _digest((git('diff', 'HEAD') or '').encode())}


def run(corpus: Path, spec: dict, supplied: dict) -> dict:
    validated_request(supplied, '/validation-only')
    documents, corpus_sha256 = load_sources(corpus, spec)
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.evidence_quality_v2.observer import observe_call
    from eval.evidence_quality_v2.run import audit_payload
    from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens

    with tempfile.TemporaryDirectory(prefix='docatlas-language-baseline-') as tmp:
        base = Path(tmp)
        project = base / 'project'
        write_project(project, documents)
        request = validated_request(supplied, str(project))
        with isolated_service(base / 'state') as (service, config):
            config.retrieval.default_mode = 'lexical'
            config.retrieval.max_sections_per_source = 2
            index = index_project(service, config, project)
            started = time.perf_counter()
            payload, trace = observe_call(service, request)
            elapsed = time.perf_counter() - started
            failed = payload.get('status') == 'failed'
            errors = None if failed else audit_payload(payload, trace.get('snapshot', {}), project)
            budget = None if failed else docs_context_budget_tokens(payload)
            if budget is not None and budget > 800:
                errors.append('packet exceeds 800 tokens')
            if index['excluded_or_failed_paths'] or index['unexpected_paths']:
                raise RuntimeError('corpus indexing was incomplete or widened')
            # Payload/trace use the existing runtime's JSON-compatible DTOs.
            return {'schema_version': 1, 'evaluation_kind': 'real_handler_development_probe',
                'status': 'HANDLER_FAILED' if failed else 'AUDIT_FAILED' if errors else 'EXECUTED',
                'independent_holdout': False, 'planner_origin': 'supplied_unverified',
                'agent_evaluation': 'NOT_MEASURED', 'fact_coverage': None,
                'product_activation': False, 'environment': environment(),
                'corpus_sha256': corpus_sha256, 'request': request,
                'payload': payload, 'trace': trace, 'index': index,
                'audit_errors': errors, 'budget_tokens': budget, 'handler_seconds': elapsed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus-dir', type=Path, required=True)
    parser.add_argument('--source-manifest', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    try:
        result = run(args.corpus_dir,
            json.loads(args.source_manifest.read_text(encoding='utf-8')),
            json.loads(args.request.read_text(encoding='utf-8')))
    except ModuleNotFoundError as exc:
        # Dependency/import failure is not a retrieval miss or a behavioural RED.
        result = {'schema_version': 1, 'status': 'BLOCKED_IMPORT',
            'missing_module': exc.name, 'exception_type': type(exc).__name__,
            'evaluation_kind': 'real_handler_development_probe',
            'agent_evaluation': 'NOT_MEASURED', 'fact_coverage': None,
            'independent_holdout': False, 'environment': environment()}
    write_report(args.output, result)
    print(args.output)
    return 2 if result['status'] == 'BLOCKED_IMPORT' else 0 if result['status'] == 'EXECUTED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
