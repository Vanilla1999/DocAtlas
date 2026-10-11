"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})





















def test_list_marks_stale_libraries(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.registry.upsert(
        library="old",
        ecosystem=None,
        docs_url="https://old.example.com",
        now=_old_iso(),
        status="available",
        last_refreshed_at=_old_iso(),
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="fresh",
        ecosystem=None,
        docs_url="https://fresh.example.com",
        now=now,
        status="available",
        last_refreshed_at=now,
    )

    stale = service.list_libraries(stale_only=True)

    assert [item.library_id for item in stale] == ["old"]
    assert stale[0].stale is True
