from types import SimpleNamespace
from pathlib import Path

from tests._shared_test_docs_service import _service


def test_async_service_fixture_retains_its_index_root_after_next_fixture_changes_home(tmp_path, monkeypatch):
    record = SimpleNamespace(library_id="example-docs")
    first = _service(tmp_path / "first", monkeypatch)
    before = first._index_config_for(record)
    second = _service(tmp_path / "second", monkeypatch)
    after = first._index_config_for(record)
    other = second._index_config_for(record)
    assert after.index.db_path == before.index.db_path
    assert after.index.db_path != other.index.db_path
    assert Path(after.index.db_path).is_relative_to(tmp_path / "first")
