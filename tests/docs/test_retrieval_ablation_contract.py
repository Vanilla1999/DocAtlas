"""Freeze guards; these tests do not claim a packet-quality result."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from experiments.retrieval_ablation.run import freeze_inputs, verify_frozen


def fixture(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCATLAS_OFFLINE', '1')
    monkeypatch.setenv('DOCATLAS_AUTO_VECTORS', '0')
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    raw = b'# Retry\n\nDo not retry cancellation.\n'
    (corpus / 'retry.md').write_bytes(raw)
    spec = {'schema_version': 1, 'sources': [{'path': 'retry.md', 'sha256': hashlib.sha256(raw).hexdigest()}]}
    return corpus, spec


def test_freeze_preserves_exact_original_literals_and_excludes_labels(tmp_path, monkeypatch):
    corpus, spec = fixture(tmp_path, monkeypatch)
    (corpus / 'private-labels.md').write_text('The hidden expected answer is secret.')
    question = '  Do not normalize ` /-S`, `*`, or `**`.\n'
    output = tmp_path / 'frozen'
    freeze_inputs(corpus, spec, {'question': question}, output)
    assert json.loads((output / 'request.json').read_bytes())['question'] == question
    assert not (output / 'corpus/private-labels.md').exists()
    assert verify_frozen(output)['panel'] == 'original_only'


@pytest.mark.parametrize('path', ['request.json', 'source-manifest.json', 'protocol.json', 'corpus/retry.md'])
def test_changed_frozen_input_stops_run(tmp_path, monkeypatch, path):
    corpus, spec = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'frozen'
    freeze_inputs(corpus, spec, {'question': 'retry'}, output)
    with (output / path).open('ab') as stream:
        stream.write(b'\n')
    with pytest.raises(ValueError, match='hash mismatch'):
        verify_frozen(output)


@pytest.mark.parametrize('name', ['gold', 'expected_api', 'answer_supported', 'edit_ready', 'threshold'])
def test_answer_and_authority_fields_never_reach_runtime(tmp_path, monkeypatch, name):
    corpus, spec = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='request'):
        freeze_inputs(corpus, spec, {'question': 'retry', name: 'secret'}, tmp_path / 'frozen')
    assert not (tmp_path / 'frozen').exists()


@pytest.mark.parametrize('name', ['../retry.md', '/retry.md', './retry.md', 'a/../retry.md'])
def test_traversal_is_rejected(tmp_path, monkeypatch, name):
    corpus, spec = fixture(tmp_path, monkeypatch)
    spec['sources'][0]['path'] = name
    with pytest.raises(ValueError, match='path'):
        freeze_inputs(corpus, spec, {'question': 'retry'}, tmp_path / 'frozen')


def test_symlink_inside_frozen_bundle_is_rejected(tmp_path, monkeypatch):
    corpus, spec = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'frozen'
    freeze_inputs(corpus, spec, {'question': 'retry'}, output)
    (output / 'corpus/retry.md').unlink()
    (output / 'corpus/retry.md').symlink_to(corpus / 'retry.md')
    with pytest.raises(ValueError, match='symlink'):
        verify_frozen(output)


def test_corpus_symlink_ancestor_is_rejected(tmp_path, monkeypatch):
    corpus, spec = fixture(tmp_path, monkeypatch)
    (tmp_path / 'alias').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        freeze_inputs(tmp_path / 'alias/corpus', spec, {'question': 'retry'}, tmp_path / 'frozen')


def test_freeze_never_overwrites_previous_outputs(tmp_path, monkeypatch):
    corpus, spec = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'frozen'
    freeze_inputs(corpus, spec, {'question': 'retry'}, output)
    before = (output / 'freeze.json').read_bytes()
    with pytest.raises(FileExistsError):
        freeze_inputs(corpus, spec, {'question': 'different'}, output)
    assert (output / 'freeze.json').read_bytes() == before


def test_changed_runtime_is_not_another_run_of_same_protocol(tmp_path, monkeypatch):
    from experiments.retrieval_ablation import run
    corpus, spec = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'frozen'
    freeze_inputs(corpus, spec, {'question': 'retry'}, output)
    changed = deepcopy(run.runtime_identity())
    changed['lock_sha256'] = '0' * 64
    monkeypatch.setattr(run, 'runtime_identity', lambda: changed)
    with pytest.raises(ValueError, match='runtime'):
        verify_frozen(output)


def test_freeze_manifest_symlink_is_rejected(tmp_path, monkeypatch):
    corpus, spec = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'frozen'
    freeze_inputs(corpus, spec, {'question': 'retry'}, output)
    (output / 'freeze.json').rename(tmp_path / 'moved.json')
    (output / 'freeze.json').symlink_to(tmp_path / 'moved.json')
    with pytest.raises(ValueError, match='symlink'):
        verify_frozen(output)


def test_freeze_metadata_cannot_promote_holdout_or_quality(tmp_path, monkeypatch):
    corpus, spec = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'frozen'
    freeze_inputs(corpus, spec, {'question': 'retry'}, output)
    manifest = json.loads((output / 'freeze.json').read_bytes())
    manifest['independent_holdout'] = True
    manifest['quality_status'] = 'SUFFICIENT'
    (output / 'freeze.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='evaluation'):
        verify_frozen(output)


def test_review_never_counts_diagnostics_as_packet_quality():
    from experiments.retrieval_ablation.review import summarize
    result = {'arm': 'A', 'execution_status': 'EXECUTED', 'quality_status': 'UNJUDGED',
              'packet_status': 'BLOCKED_SAFE_PACKET_ADAPTER', 'model_visible_packet': None,
              'freeze_sha256': 'same'}
    summary = summarize([result])
    assert summary['planned_runs'] == 2
    assert summary['missing_arms'] == ['P']
    assert summary['semantic_evaluable'] == 0
    assert summary['quality_outcome'] == 'INCONCLUSIVE'
    assert summary['execution_counts'] == {'EXECUTED': 1}
    result['model_visible_packet'] = {'answer_supported': True}
    with pytest.raises(ValueError, match='not a public packet'):
        summarize([result])


def test_review_preserves_blockers_and_rejects_unpaired_runs():
    from experiments.retrieval_ablation.review import summarize
    result = {'arm': 'P', 'execution_status': 'BLOCKED_ENV', 'quality_status': 'UNJUDGED',
              'freeze_sha256': 'same'}
    assert summarize([result])['execution_counts'] == {'BLOCKED_ENV': 1}
    with pytest.raises(ValueError, match='frozen'):
        summarize([result, {**result, 'freeze_sha256': 'different'}])
    with pytest.raises(ValueError, match='no runs'):
        summarize([])
    with pytest.raises(ValueError, match='duplicate'):
        summarize([result, result])


@pytest.mark.parametrize('key,value', [
    ('DOCATLAS_OFFLINE', '0'), ('DOCATLAS_AUTO_VECTORS', '1'), ('PYTHONHASHSEED', '1'),
])
def test_changed_runtime_flags_fail_closed(tmp_path, monkeypatch, key, value):
    corpus, spec = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'frozen'
    freeze_inputs(corpus, spec, {'question': 'retry'}, output)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match='runtime'):
        verify_frozen(output)


def test_runtime_freeze_covers_untracked_runtime_modules(tmp_path, monkeypatch):
    import uuid
    from experiments.retrieval_ablation.run import ROOT
    corpus, spec = fixture(tmp_path, monkeypatch)
    module = ROOT / 'docmancer' / ('_ablation_guard_' + uuid.uuid4().hex + '.py')
    try:
        module.write_text('# Initial runtime source.\n')
        frozen = tmp_path / 'frozen'
        freeze_inputs(corpus, spec, {'question': 'retry'}, frozen)
        module.write_text('# Changed runtime source.\n')
        with pytest.raises(ValueError, match='runtime'):
            verify_frozen(frozen)
    finally:
        module.unlink(missing_ok=True)


def test_runtime_source_symlink_cannot_escape_frozen_inventory(tmp_path, monkeypatch):
    import uuid
    from experiments.retrieval_ablation.run import ROOT
    corpus, spec = fixture(tmp_path, monkeypatch)
    target = tmp_path / 'external.py'
    target.write_text('# External runtime.\n')
    module = ROOT / 'docmancer' / ('_ablation_guard_' + uuid.uuid4().hex + '.py')
    try:
        module.symlink_to(target)
        with pytest.raises(ValueError, match='symlink'):
            freeze_inputs(corpus, spec, {'question': 'retry'}, tmp_path / 'frozen')
    finally:
        module.unlink(missing_ok=True)
