from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import sqlite3

import pytest

from docmancer.docs.application.library_index_publication import LibraryIndexPublication
from docmancer.docs.application.library_ingest_ports import LibraryPublicationPorts
from docmancer.docs.registry import LibraryRecord


class _Config:
    def __init__(self, db_path: Path, extracted_dir: Path):
        self.index = type("Index", (), {"db_path": str(db_path), "extracted_dir": str(extracted_dir)})()

    def model_copy(self, *, deep: bool):
        assert deep is True
        return _Config(Path(self.index.db_path), Path(self.index.extracted_dir))


def _record() -> LibraryRecord:
    return LibraryRecord(
        library_id="python:pytest@8:api",
        source_id="source-1",
        canonical_id="python:pytest@8:api",
        name="pytest",
        normalized_name="pytest",
        ecosystem="python",
        version="8",
        source_type="api",
        docs_url="https://docs.pytest.org/",
        docs_url_template=None,
        aliases=[],
        status="available",
        added_at="2026-07-27T00:00:00+00:00",
        last_checked_at=None,
        last_refreshed_at=None,
        last_error=None,
    )


def _payload(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return str(connection.execute("SELECT value FROM payload").fetchone()[0])


def test_publication_rolls_back_index_and_registry_when_registry_update_fails(tmp_path):
    production_db = tmp_path / "index.db"
    with sqlite3.connect(production_db) as connection:
        connection.execute("CREATE TABLE payload (value TEXT)")
        connection.execute("INSERT INTO payload VALUES ('previous')")

    restored, dropped = [], []
    config = _Config(production_db, tmp_path / "extracted")
    publication = LibraryIndexPublication(LibraryPublicationPorts(
        index_config_for=lambda _record: config,
        lock_for=lambda _library_id: nullcontext(),
        restore_record=restored.append,
        drop_library_agent=dropped.append,
        monotonic=lambda: 100.0,
    ))
    staging_config, staging_root = publication.create_staging_index(_record())
    with sqlite3.connect(staging_config.index.db_path) as connection:
        connection.execute("UPDATE payload SET value = 'candidate'")

    with pytest.raises(RuntimeError, match="registry write failed"):
        publication.publish_and_update(
            _record(),
            (staging_config, staging_root),
            registry_update=lambda: (_ for _ in ()).throw(RuntimeError("registry write failed")),
        )

    assert _payload(production_db) == "previous"
    assert restored == []
    assert dropped == []
