"""Synthetic boundaries for the existing qualifier plus source-bound scope."""
from copy import deepcopy
import pytest
from section_scope import ScopeBinder, STAMP_KEYS, installed
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.application import docs_context_projection as projection

TEXT = "The tasks run in order. Later tasks will not run after an exception."
PROBE = {"query_text": "WorkQueue tasks run order exception", "query_terms": ["workqueue", "tasks", "run", "order", "exception"], "exact_terms": ["workqueue"]}


def fixture(doc=None, text=TEXT):
    if doc is None:
        doc = "# API\n\n## WorkQueue\n\n" + text + "\n"
    start = doc.index(text)
    raw = dict(content=text, char_start=start, char_end=start + len(text), path="api.md",
               project_identity="p", source_class="project_doc", freshness="current", index_freshness="synchronized",
               authority="source_of_truth", lifecycle_status="active", version="v1",
               _source_snapshot_sha256="frozen-snapshot", _source_catalog_hash="frozen-catalog")
    source = dict(snippet=text, path_or_url="api.md", section="invented metadata", _qualification_candidate=raw,
                  _expected_project_identity="p")
    binder = ScopeBinder({"api.md": doc}, "p", {"api.md": tuple(raw.get(k) for k in STAMP_KEYS)})
    return binder, source


def check(binder, source, probe=None):
    return binder.qualify(qualify_evidence, probe or PROBE, source, query_id="query-original",
                          visible_text=source["snippet"], evidence_text=source["snippet"],
                          candidate=source["_qualification_candidate"], expected_project_identity="p")


def test_recovers_same_section_not_body_rewrite():
    binder, source = fixture()
    before = deepcopy(source)
    assert not qualify_evidence(PROBE, query_id="q", visible_text=TEXT, evidence_text=TEXT).qualified
    result, proof = check(binder, source)
    assert result.qualified and proof["headings"][-1]["text"] == "## WorkQueue"
    assert source == before


@pytest.mark.parametrize("heading", ["## OtherQueue", "## WorkQueueExtra"])
def test_neighbour_or_prefix(heading):
    binder, source = fixture("# API\n## WorkQueue\nOther text.\n" + heading + "\n" + TEXT)
    assert not check(binder, source)[0].qualified


def test_nested_other_owner():
    binder, source = fixture("# WorkQueue\n## OtherQueue\n" + TEXT)
    assert not check(binder, source)[0].qualified


@pytest.mark.parametrize("key,value", [("project_identity", "foreign"), ("version", "v2"),
    ("_source_snapshot_sha256", "changed"), ("_source_catalog_hash", "changed"), ("freshness", "stale"),
    ("index_freshness", "old"), ("stale", True), ("risk_flags", ["risk"]),
    ("instruction_risk_flags", ["instruction"]), ("source_class", "code")])
def test_policy_never_rescues(key, value):
    binder, source = fixture()
    source["_qualification_candidate"][key] = value
    assert not check(binder, source)[0].qualified


def test_fake_metadata_is_not_context():
    binder, source = fixture("# OtherQueue\n" + TEXT)
    source["section"] = "WorkQueue"
    source["_qualification_candidate"]["heading_path"] = "WorkQueue"
    assert not check(binder, source)[0].qualified


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_fenced_heading_not_owner(fence):
    binder, source = fixture("# API\n" + fence + "\n## WorkQueue\n" + fence + "\n" + TEXT)
    assert not check(binder, source)[0].qualified


def test_html_heading_not_owner():
    binder, source = fixture("# API\n<div>\n## WorkQueue\n</div>\n\n" + TEXT)
    assert not check(binder, source)[0].qualified


def test_one_body_match_not_rescued():
    binder, source = fixture(text="Tasks.")
    assert not check(binder, source)[0].qualified


def test_heading_only_not_rescued():
    binder, source = fixture(text="## tasks run order exception")
    assert not check(binder, source)[0].qualified


def test_absent_library_name_not_guessed():
    binder, source = fixture()
    probe = {**PROBE, "exact_terms": ["workqueue", "somelibrary"]}
    assert not check(binder, source, probe)[0].qualified


def test_trimmed_window_is_requalified_not_inherited():
    binder, source = fixture()
    assert check(binder, source)[0].qualified
    source["snippet"] = "tasks"
    assert not check(binder, source)[0].qualified


def test_wrong_offsets_not_rescued():
    binder, source = fixture()
    source["_qualification_candidate"]["char_start"] += 1
    assert not check(binder, source)[0].qualified


def test_repeated_quote_is_ambiguous():
    binder, source = fixture(text=TEXT + "\n" + TEXT)
    source["snippet"] = TEXT
    assert not check(binder, source)[0].qualified


def test_setext_outline():
    binder, source = fixture("API\n===\n\nWorkQueue\n---\n\n" + TEXT)
    assert check(binder, source)[0].qualified


def test_span_crossing_sibling_does_not_borrow_owner():
    text = TEXT + "\n## OtherQueue\n" + TEXT
    binder, source = fixture("# API\n## WorkQueue\n" + text, text=text)
    assert not check(binder, source)[0].qualified


def test_plain_semantic_rejection_unchanged():
    binder, source = fixture()
    result, proof = check(binder, source, {"query_text": "queue timeout cancellation", "query_terms": ["queue", "timeout", "cancellation"]})
    assert not result.qualified and proof is None


def test_forbidden_term_stays_rejected():
    binder, source = fixture()
    result, proof = check(binder, source, {**PROBE, "forbidden_evidence_terms": ["exception"]})
    assert not result.qualified and proof is None


def test_patch_is_restored_even_after_failure():
    binder, _ = fixture()
    original = projection._requalify_visible_source
    with pytest.raises(RuntimeError):
        with installed(binder, "scope_requalify", []):
            assert projection._requalify_visible_source is not original
            raise RuntimeError("synthetic")
    assert projection._requalify_visible_source is original
