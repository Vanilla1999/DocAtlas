"""Probe input/output tests; these do not execute a DocAtlas handler."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import pytest

from experiments.language_aware_context.baseline_probe import (
    load_sources, validated_request, write_report,
)


def fixture(tmp_path: Path):
    root = tmp_path / 'sources'
    root.mkdir()
    raw = b'# Retry\n\nDo not retry after cancellation.\n'
    (root / 'retry.md').write_bytes(raw)
    spec = {'schema_version': 1, 'sources': [
        {'path': 'retry.md', 'sha256': hashlib.sha256(raw).hexdigest()}]}
    return root, spec, raw


def test_only_manifest_sources_are_loaded(tmp_path):
    root, spec, raw = fixture(tmp_path)
    (root / 'labels.md').write_text('Never index these annotations.')
    documents, identity = load_sources(root, spec)
    assert documents == {'retry.md': raw.decode()}
    assert len(identity) == 64
    assert load_sources(root, spec)[1] == identity


def test_changed_source_hash_is_rejected(tmp_path):
    root, spec, _ = fixture(tmp_path)
    (root / 'retry.md').write_text('Wrong snapshot')
    with pytest.raises(ValueError, match='hash'):
        load_sources(root, spec)


@pytest.mark.parametrize('path', ['../retry.md', '/retry.md', 'a/../retry.md',
    'a\\retry.md', 'a//retry.md', './retry.md'])
def test_noncanonical_paths_are_rejected(tmp_path, path):
    root, spec, _ = fixture(tmp_path)
    spec['sources'][0]['path'] = path
    with pytest.raises(ValueError, match='path'):
        load_sources(root, spec)


def test_symlink_directory_is_rejected(tmp_path):
    root, spec, raw = fixture(tmp_path)
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    (elsewhere / 'file.md').write_bytes(raw)
    (root / 'link').symlink_to(elsewhere, target_is_directory=True)
    spec['sources'][0]['path'] = 'link/file.md'
    with pytest.raises(ValueError, match='symlink'):
        load_sources(root, spec)


@pytest.mark.parametrize('mode', ['duplicate', 'empty', 'extra', 'wrong_schema'])
def test_invalid_manifest_is_rejected(tmp_path, mode):
    root, spec, _ = fixture(tmp_path)
    if mode == 'duplicate':
        spec['sources'] *= 2
    elif mode == 'empty':
        spec['sources'] = []
    elif mode == 'extra':
        spec['gold'] = 'secret'
    else:
        spec['schema_version'] = True
    with pytest.raises(ValueError):
        load_sources(root, spec)


def test_request_preserves_original_and_has_no_policy_overrides():
    question = '  Чем отличаются ` /-S` и `/-S`?\n'
    request = validated_request({'question': question, 'lookup_queries': ['compare forms']}, '/repo')
    assert request == {'question': question, 'lookup_queries': ['compare forms'],
                       'project_path': '/repo', 'scope': 'all'}
    with pytest.raises(ValueError):
        validated_request({'question': question, 'answer_supported': True}, '/repo')


@pytest.mark.parametrize('supplied', [{}, [], {'question': 123}, {'question': 'q', 'gold': 'secret'}])
def test_invalid_request_fails_before_importing_handler(supplied):
    with pytest.raises(ValueError):
        validated_request(supplied, '/repo')


def test_report_cannot_overwrite_previous_run(tmp_path):
    target = tmp_path / 'new' / 'result.json'
    write_report(target, {'status': 'NOT_EVALUATED', 'score': None})
    assert json.loads(target.read_text())['score'] is None
    with pytest.raises(FileExistsError):
        write_report(target, {'status': 'PASS'})
    assert json.loads(target.read_text())['status'] == 'NOT_EVALUATED'


def test_nonfinite_report_is_rejected_before_file_creation(tmp_path):
    target = tmp_path / 'result.json'
    with pytest.raises(ValueError):
        write_report(target, {'value': float('nan')})
    assert not target.exists()
