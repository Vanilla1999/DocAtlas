"""Stored refresh contracts cannot change the loaded registry identity."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from tests.test_dictionary_exit_finite_callers import (
    ROOT, ROBOTS, _sources, _target, service, transport,
)


def _files(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in Path(root).rglob("*") if path.is_file()}


def _persist(facade, record, spec):
    return facade.registry.upsert(
        library=record.name, ecosystem=record.ecosystem, version=record.version,
        source_type=record.source_type, docs_url=record.docs_url,
        docs_url_template=record.docs_url_template, target_spec=spec,
        now=facade.library_docs._now(), status=record.status,
    )


@pytest.mark.parametrize("field,value", [
    ("library", "other"), ("ecosystem", "pub"), ("version", "v2"),
    ("source_type", "guides"), ("source_type", "UNKNOWN"),
    ("library", ""), ("library", "!!!"), ("library", []),
    ("ecosystem", " "), ("ecosystem", {}), ("ecosystem", None),
    ("version", ""), ("version", "v1/other"), ("version", 2),
    ("version", None), ("source_type", ""), ("source_type", []),
    ("source_type", "api\n"),
    ("library", "__missing__"), ("ecosystem", "__missing__"),
    ("version", "__missing__"), ("source_type", "__missing__"),
])
def test_stored_identity_mismatch_rejects_before_dispatch_and_mutation(
    field, value, service, transport, tmp_path, monkeypatch,
):
    facade, agent = service
    initial = facade.prefetch_docs("finite", target=_target(), force_refresh=True)
    assert initial.status == "updated"
    record = facade.registry.get(initial.library_id)
    spec = deepcopy(record.target_spec)
    spec[field] = value
    if value == "__missing__":
        spec.pop(field)
    spec["identity"] = {"nested": {"selected": [ROOT, ROBOTS]}}
    record = _persist(facade, record, spec)
    frozen_spec = json.dumps(record.target_spec, sort_keys=True)
    jobs = facade.jobs.list()
    transport[0].clear()
    agent.calls.clear()
    before = _files(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("identity mismatch reached ingest dispatch")

    monkeypatch.setattr(facade.library_docs.ingest_orchestrator, "prefetch_docs", forbidden)
    result = facade.refresh_docs(record.library_id, force=True)
    assert result.status == "needs_explicit_target"
    assert result.reason_codes == ["explicit_target_identity_mismatch"]
    assert transport[0] == [] and agent.calls == []
    assert facade.jobs.list() == jobs
    assert facade.registry.get(record.library_id) == record
    assert json.dumps(record.target_spec, sort_keys=True) == frozen_spec
    assert _files(tmp_path) == before
    assert _sources(facade, record) == {ROOT, ROBOTS}


@pytest.mark.parametrize("mechanical", [False, True])
def test_valid_stored_identity_refresh_preserves_exact_contract(mechanical, service, transport):
    facade, agent = service
    initial = facade.prefetch_docs("finite", target=_target(), force_refresh=True)
    assert initial.status == "updated"
    record = facade.registry.get(initial.library_id)
    spec = deepcopy(record.target_spec)
    spec["identity"] = {"nested": {"selected": [ROOT, ROBOTS]}}
    if mechanical:
        spec.update(library=" FINITE ", ecosystem=" WEB ", version=" V1 ", source_type=" API ")
    record = _persist(facade, record, spec)
    frozen_spec = deepcopy(record.target_spec)
    jobs = facade.jobs.list()
    transport[0].clear()
    agent.calls.clear()
    result = facade.refresh_docs(record.library_id, force=True)
    assert result.status in {"updated", "skipped"}
    assert result.library_id == record.library_id == "web:finite@v1:api"
    assert set(transport[0]) == {ROOT, ROBOTS}
    assert _sources(facade, record) == {ROOT, ROBOTS}
    current = facade.registry.get(record.library_id)
    assert current.name.strip().lower() == "finite"
    assert current.ecosystem.strip().lower() == "web"
    assert current.version == "v1" and current.source_type == "api"
    for key in ("docs_url", "seed_urls", "allowed_domains", "path_prefixes", "source_manifest", "identity"):
        assert current.target_spec[key] == frozen_spec[key]
    assert record.target_spec == frozen_spec
    assert facade.jobs.list() == jobs
    assert all(kwargs["exact_urls"] == [url] and kwargs["robots_urls"] == [ROBOTS]
               for url, kwargs, _ in agent.calls)


def test_identity_comparison_does_not_drop_source_without_ecosystem(service, transport):
    facade, agent = service
    target = replace(_target(), ecosystem=None)
    initial = facade.prefetch_docs("finite", target=target, force_refresh=True)
    record = facade.registry.get(initial.library_id)
    spec = deepcopy(record.target_spec)
    spec["source_type"] = "guides"
    record = _persist(facade, record, spec)
    transport[0].clear()
    agent.calls.clear()
    result = facade.refresh_docs(record.library_id, force=True)
    assert result.reason_codes == ["explicit_target_identity_mismatch"]
    assert facade.registry.get(record.library_id) == record
    assert transport[0] == [] and agent.calls == []
