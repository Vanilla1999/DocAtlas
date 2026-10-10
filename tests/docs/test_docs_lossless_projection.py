"""Component quote fidelity, independent of selection and public output budgets."""
from copy import deepcopy
import hashlib

import pytest

from docmancer.docs.application._model_visible_docs_support import (
    _docs_source,
    _snapshot_entry,
    _source_digest,
)
from docmancer.docs.application.model_visible_projection_helpers import canonical_projection_bytes


def source(snippet="Storage records retain their creation timestamp."):
    return {
        "path": "docs/record-validation.md",
        "heading_path": "Record validation",
        "content": snippet,
        "snippet": snippet,
        "version_binding": "2.0",
    }


def test_source_normalizer_retains_complete_long_unique_code():
    lines = ["```python", "def validate_record(record):"]
    for index in range(64):
        lines.extend([
            f'    if record["field_{index}"] != "required-value-{index}":',
            f'        raise ValueError("invalid field_{index}")',
        ])
    lines.extend(['    return record["field_63"]', "```"])
    snippet = "\n".join(lines)
    assert len(snippet) > 3_000
    original = source(snippet)
    before = deepcopy(original)

    row = _docs_source(original, evidence_id="ev-long-code")

    assert row is not None
    assert row == {
        "evidence_id": "ev-long-code",
        "path_or_url": original["path"],
        "section": original["heading_path"],
        "snippet": snippet,
        "version_binding": original["version_binding"],
        "content_sha256": _source_digest(original),
    }
    assert original == before


def test_source_normalizer_preserves_snapshot_binding():
    original = source()
    before = deepcopy(original)
    row = _docs_source(original, evidence_id="ev-bound-quote")
    assert row is not None
    material = {
        "path": original["path"],
        "section": original["heading_path"],
        "content": original["content"],
        "snippet": original["snippet"],
        "version": original["version_binding"],
    }
    expected_digest = hashlib.sha256(canonical_projection_bytes(material)).hexdigest()
    assert row["content_sha256"] == expected_digest == _source_digest(original)
    assert expected_digest != hashlib.sha256(row["snippet"].encode("utf-8")).hexdigest()
    snapshot = _snapshot_entry(original, row)
    assert snapshot["source"] == before
    assert snapshot["projected_source"] == row
    assert {key: snapshot[key] for key in row} == row

    changed_text = {**row, "snippet": "Different source bytes."}
    assert changed_text != snapshot["projected_source"]
    changed_original = {**original, "snippet": changed_text["snippet"]}
    assert _source_digest(changed_original) != snapshot["projected_source"]["content_sha256"]
    changed_hash = {**row, "content_sha256": "0" * 64}
    assert changed_hash["content_sha256"] != _source_digest(snapshot["source"])
    assert changed_hash != snapshot["projected_source"]

    original["snippet"] = "Caller changed its source."
    row["snippet"] = "Caller changed its projected row."
    assert snapshot["source"] == before
    assert snapshot["projected_source"]["snippet"] == before["snippet"]


@pytest.mark.parametrize("field,value,accepted", [
    pytest.param("path", "", False, id="empty-path"),
    pytest.param("snippet", "", False, id="empty-snippet"),
    pytest.param("path", "p" * 500, True, id="path-500"),
    pytest.param("path", "p" * 501, False, id="path-501"),
    pytest.param("heading_path", "s" * 300, True, id="section-300"),
    pytest.param("heading_path", "s" * 301, False, id="section-301"),
    pytest.param("version_binding", "v" * 100, True, id="version-100"),
    pytest.param("version_binding", "v" * 101, False, id="version-101"),
])
def test_source_normalizer_keeps_identity_guards(field, value, accepted):
    original = source()
    if field == "snippet" and not value:
        original["content"] = ""
    original[field] = value
    before = deepcopy(original)

    row = _docs_source(original)

    assert original == before
    if not accepted:
        assert row is None
        return
    assert row is not None
    assert row["path_or_url"] == original["path"]
    assert row["section"] == original["heading_path"]
    assert row["version_binding"] == original["version_binding"]
    assert row["snippet"] == original["snippet"]
    assert row["content_sha256"] == _source_digest(original)
