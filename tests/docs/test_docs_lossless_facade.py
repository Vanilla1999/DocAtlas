"""Full facade and reader-binding components; private files, no indexed MCP claim."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

import pytest

from docmancer.docs.application import docs_context_projection as facade
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.application.source_continuation import (
    SourceContinuationReader, attach_docs_context_read_next, attach_source_continuation_locators,
    bind_project_source_continuations,
)
from docmancer.docs.infrastructure.project_source_read_gateway import ProjectSourceReadGateway
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from tests.docs.test_docs_lossless_context_projection import fixture as context_fixture, source_text


def private_sources(tmp_path, *, kind="code", large=False, four=False, partial=False):
    retrieval, rows = context_fixture(kind, large=large, four=four, partial=partial)
    (tmp_path / "docs").mkdir()
    # Only the first source has an adjacent, unrelated section. It is not proof
    # for the question, but it offers a real bounded source-local read target.
    rows[0]["content"] += "\n\n# Appendix\n" + "\n".join(
        f"Resume phase {n} only after recording the consent decision for checkpoint {n}."
        for n in range(20)
    )
    rows[0]["display_text"] = rows[0]["content"]
    rows[0]["line_end"] = rows[0]["line_start"] + len(rows[0]["content"].splitlines()) - 1
    rows[0]["char_end"] = len(rows[0]["content"])
    rows[0]["display_content_hash"] = hashlib.sha256(rows[0]["content"].encode()).hexdigest()
    for row in rows:
        path = tmp_path / row["path"]
        path.write_text("\n".join(f"Preface {n}." for n in range(9)) + "\n" + row["content"] + "\n")
    catalog_path = tmp_path / "docatlas.project-docs.yaml"
    catalog_path.write_text("schema_version: 1\ndocuments:\n" + "".join(
        f"  - path: {row['path']}\n    role: runbook\n    scope: project\n"
        "    authority: source_of_truth\n    status: active\n    description: Validation contract\n"
        for row in rows
    ))
    catalog = read_project_docs_catalog(tmp_path)
    assert catalog.present and catalog.valid
    metadata = {}
    for row in rows:
        path = tmp_path / row["path"]
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        entry = next(entry for entry in catalog.entries if entry.path == row["path"])
        catalog_hash = "sha256:" + hashlib.sha256(json.dumps(
            asdict(entry), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        row.update(_source_snapshot_sha256=digest, _source_catalog_hash=catalog_hash)
        metadata[str(path)] = {
            "project_path": str(tmp_path), "project_identity": "offline-context",
            "project_doc_path": row["path"], "project_doc_content_hash": digest,
            "project_doc_catalog_entry_hash": catalog_hash, "source_class": "project_file",
            "doc_scope": "project", "authority": "source_of_truth", "lifecycle_status": "active",
        }

    class Store:
        active = True

        def source_metadata(self, path):
            return metadata.get(path)

        def section_ids_for_source(self, path):
            return [path] if self.active and path in metadata else []

        def section_filter_metadata_for(self, ids):
            return {key: dict(metadata[key]) for key in ids if key in metadata}

    store = Store()
    gateway = ProjectSourceReadGateway(lambda: store, identity_for_root=lambda root: "offline-context")
    now = [0]
    reader = SourceContinuationReader(gateway, clock=lambda: now[0])
    retrieval["_source_continuation_project_root"] = str(tmp_path)
    return retrieval, rows, reader, store, metadata, now


def small_positive(tmp_path):
    root = tmp_path / "positive"
    root.mkdir()
    retrieval, rows, reader, *_ = private_sources(root, partial=True)
    payload, snapshot = facade.project_docs_context(retrieval=retrieval)
    assert payload.get("sources") and len(payload["read_next"]) == 1
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []
    bind_project_source_continuations(reader, str(root), payload, snapshot)
    target = payload["read_next"][0]
    assert reader.has_reference(target["source_uri"])
    assert "consent decision" in reader.read(target["source_uri"])["snippet"]
    return payload, snapshot


def assert_quotes(payload, snapshot, rows, kind, large):
    assert len(payload["sources"]) == len(rows)
    assert {row["path_or_url"] for row in payload["sources"]} == {row["path"] for row in rows}
    for row in payload["sources"]:
        index = next(i for i, item in enumerate(rows) if item["path"] == row["path_or_url"])
        quote = source_text(kind, index, large=large)
        assert row["snippet"] == quote
        assert (row["line_start"], row["line_end"]) == (10, 9 + len(quote.splitlines()))
        bound = snapshot[row["evidence_id"]]
        assert bound["projected_source"] == row
        assert bound["source"]["content"] == rows[index]["content"]
        assert bound["source_uri"] == row["source_uri"]
    assert payload["answer_supported"] is payload["answer_available"] is payload["edit_ready"] is False
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []


@pytest.mark.parametrize("kind", ["list", "table", "code"])
@pytest.mark.parametrize("budget", [256, 800], ids=["legacy-256", "legacy-800"])
def test_large_facade_keeps_four_quotes_locators_and_real_issued_target(tmp_path, kind, budget):
    small_positive(tmp_path)
    root = tmp_path / "large"
    root.mkdir()
    retrieval, rows, reader, *_ = private_sources(root, kind=kind, large=True, four=True)
    payload, snapshot = facade.project_docs_context(retrieval=retrieval, max_tokens=budget)
    assert_quotes(payload, snapshot, rows, kind, True)
    assert payload["estimated_tokens"] > 800
    assert len(payload["read_next"]) == 1
    target = deepcopy(payload["read_next"][0])
    assert snapshot["__read_next__"]["source"]["_source_snapshot_sha256"] == target["snapshot_sha256"]
    before = deepcopy(payload["sources"])
    bind_project_source_continuations(reader, str(root), payload, snapshot)
    assert payload["sources"] == before and payload["read_next"] == [target]
    assert all(reader.has_reference(row["source_uri"]) for row in payload["sources"])
    assert reader.has_reference(target["source_uri"])
    result = reader.read(target["source_uri"])
    assert result["status"] == "complete" and "consent decision" in result["snippet"]
    assert (result["path"], result["project_identity"], result["content_sha256"]) == (
        target["path"], target["project_identity"], target["snapshot_sha256"],
    )
    assert (result["line_start"], result["line_end"]) == (target["line_start"], target["line_end"])
    assert reader.read(target["source_uri"])["status"] == "source_unavailable"


@pytest.mark.parametrize("large", [False, True], ids=["short", "long"])
def test_partial_facade_keeps_qualified_quote_and_honest_missing_lookup(tmp_path, large):
    small_positive(tmp_path)
    root = tmp_path / "partial"
    root.mkdir()
    retrieval, rows, reader, *_ = private_sources(root, large=large, partial=True)
    payload, snapshot = facade.project_docs_context(retrieval=retrieval)
    assert_quotes(payload, snapshot, rows, "code", large)
    assert payload["covered_query_ids"] == ["query-original"]
    assert payload["missing_query_ids"] == ["query-lookup-1"] and payload["query_coverage"] == "partial"
    assert len(payload["read_next"]) == 1
    bind_project_source_continuations(reader, str(root), payload, snapshot)
    assert reader.has_reference(payload["read_next"][0]["source_uri"])


@pytest.mark.parametrize("change", ["failed_issue", "permission", "identity", "hash", "path"])
def test_target_binding_failures_do_not_evict_quotes_or_publish_dead_target(tmp_path, monkeypatch, change):
    small_positive(tmp_path)
    root = tmp_path / "rejected"
    root.mkdir()
    retrieval, rows, reader, *_ = private_sources(root, large=True, four=True)
    payload, snapshot = facade.project_docs_context(retrieval=retrieval)
    assert_quotes(payload, snapshot, rows, "code", True)
    assert len(payload["read_next"]) == 1
    before = [row["snippet"] for row in payload["sources"]]
    if change == "failed_issue":
        monkeypatch.setattr(reader, "issue_range", lambda *args, **kwargs: None)
    elif change == "permission":
        path = root / "docatlas.project-docs.yaml"
        path.write_text(path.read_text().replace("authority: source_of_truth", "authority: historical"))
    elif change == "identity":
        payload["read_next"][0]["project_identity"] = "foreign"
    elif change == "hash":
        payload["read_next"][0]["snapshot_sha256"] = "sha256:" + "0" * 64
    else:
        payload["read_next"][0]["path"] = "docs/foreign.md"
    bind_project_source_continuations(reader, str(root), payload, snapshot)
    assert payload["read_next"] == [] and payload["recovery_reason_code"] == "source_unavailable"
    assert [row["snippet"] for row in payload["sources"]] == before
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []


@pytest.mark.parametrize("change", ["confirmation", "operational", "foreign_source", "forged_lookup"])
def test_facade_keeps_existing_delivery_and_literal_qualification_vetoes(tmp_path, change):
    small_positive(tmp_path)
    root = tmp_path / "veto"
    root.mkdir()
    retrieval, rows, *_ = private_sources(root, partial=True)
    if change == "confirmation":
        retrieval.update(requires_confirmation=True, status="confirmation_required")
    elif change == "operational":
        retrieval["delivery_decision"] = {"deliverable": False, "reason_code": "catalog_invalid"}
    elif change == "foreign_source":
        rows[0]["project_identity"] = "foreign"
    else:
        retrieval["documentation_query_plan"]["queries"][0]["text"] = "unrelated ledger checksum"
    payload, snapshot = facade.project_docs_context(retrieval=retrieval)
    assert not payload.get("sources") and not payload.get("read_next")
    assert not reader_references(snapshot)
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []


def reader_references(snapshot):
    return [row for row in snapshot.values() if isinstance(row, dict) and row.get("source_uri")]


@pytest.mark.parametrize("change", ["snapshot", "revoked", "expiry", "forged_uri"])
def test_genuinely_issued_target_still_rechecks_current_snapshot_policy_and_expiry(tmp_path, change):
    small_positive(tmp_path)
    root = tmp_path / "current"
    root.mkdir()
    retrieval, rows, reader, store, _, now = private_sources(root, large=True, four=True)
    payload, snapshot = facade.project_docs_context(retrieval=retrieval)
    assert_quotes(payload, snapshot, rows, "code", True)
    assert len(payload["read_next"]) == 1
    bind_project_source_continuations(reader, str(root), payload, snapshot)
    target = payload["read_next"][0]
    uri = target["source_uri"]
    assert reader.has_reference(uri)
    if change == "snapshot":
        path = root / target["path"]
        path.write_text(path.read_text() + "Changed bytes.\n")
    elif change == "revoked":
        store.active = False
    elif change == "expiry":
        now[0] = 601
    else:
        uri += "?start=1"
    result = reader.read(uri)
    assert result["status"] in {"source_changed", "source_unavailable"} and "snippet" not in result


def test_attachment_helpers_do_not_spend_quote_budget_or_desync_locators(tmp_path):
    payload, snapshot = small_positive(tmp_path)
    target = deepcopy(payload["read_next"][0])
    before = deepcopy(payload["sources"])
    assert attach_docs_context_read_next(payload, target, max_tokens=1) is True
    attach_source_continuation_locators(payload, snapshot, root=str(tmp_path / "positive"), max_tokens=1)
    assert payload["sources"] == before and payload["read_next"] == [target]
    for row in payload["sources"]:
        assert snapshot[row["evidence_id"]]["projected_source"]["source_uri"] == row["source_uri"]
    assert validate_model_visible_projection(payload, snapshot=snapshot) == []
