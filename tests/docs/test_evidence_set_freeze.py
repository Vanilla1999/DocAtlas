"""Run identities cannot be silently overwritten on resume."""
import json
import pytest
from eval.evidence_sets_v1.freeze import write_once_manifest


def test_first_write_and_identical_resume(tmp_path):
    path = tmp_path / 'freeze.json'
    write_once_manifest(path, {'runtime': 'a', 'corpus': 'x'})
    assert path.is_file()
    before = path.read_bytes()
    write_once_manifest(path, {'corpus': 'x', 'runtime': 'a'})
    assert path.read_bytes() == before


@pytest.mark.parametrize('field', ['runtime', 'corpus', 'lock', 'questions', 'tokenizer', 'mode'])
def test_resume_rejects_changed_fingerprint(tmp_path, field):
    path = tmp_path / 'freeze.json'
    write_once_manifest(path, {field: 'a'})
    with pytest.raises(ValueError, match='freeze mismatch'):
        write_once_manifest(path, {field: 'b'})
    assert json.loads(path.read_text()) == {field: 'a'}


def test_nonfinite_json_is_not_a_valid_identity(tmp_path):
    with pytest.raises(ValueError):
        write_once_manifest(tmp_path / 'freeze.json', {'value': float('nan')})


def test_symlink_cannot_redirect_a_resume_write(tmp_path):
    target = tmp_path / 'unrelated.json'
    target.write_text('{"safe": true}')
    path = tmp_path / 'freeze.json'
    path.symlink_to(target)
    with pytest.raises(ValueError):
        write_once_manifest(path, {'safe': False})
    assert json.loads(target.read_text()) == {'safe': True}


def test_freeze_inputs_hashes_real_files_and_rejects_changes(tmp_path):
    from hashlib import sha256
    import subprocess
    from eval.evidence_sets_v1.freeze import freeze_inputs
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'docmancer').mkdir()
    module = repo / 'docmancer/example.py'
    module.write_text('VALUE = 1\n')
    (repo / 'uv.lock').write_text('locked')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    out = tmp_path / 'audit'
    result = freeze_inputs(repo, out)
    assert result.get('files', {}).get('docmancer/example.py') == sha256(module.read_bytes()).hexdigest()
    module.write_text('VALUE = 2\n')
    with pytest.raises(ValueError, match='freeze mismatch'):
        freeze_inputs(repo, out)
