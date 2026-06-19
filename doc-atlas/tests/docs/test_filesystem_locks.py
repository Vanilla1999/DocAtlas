from pathlib import Path

from docmancer.docs.infrastructure.filesystem_locks import FilesystemLockGateway


def test_filesystem_lock_path_remains_stable(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))

    lock = FilesystemLockGateway().lock_for("/pub/riverpod/2.0/api")

    assert Path(lock.lock_file) == tmp_path / "home" / "locks" / "docs-pub-riverpod-2-0-api.lock"
