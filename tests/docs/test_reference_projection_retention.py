import copy
import json
import pytest
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from tests.docs._reference_binding_fixtures import capture_reference_case, visible


def _captured_source(tmp_path):
    text = "# Constants\n\nThe constant ARGON returns `73`.\n\nThe other constant returns `91`.\n"
    question = "What does the constant `ARGON` return in the file Guide?"
    capture = capture_reference_case(tmp_path, {"Guide.md": text}, question)
    rows = capture["projection_attempts"][0]["before_projection"]["context_pack"]
    assert rows
    source = copy.deepcopy(rows[0])
    assert source.get("_reference_evidence"), "native application did not supply a snapshot"
    return source, question, text


def _qualify(source, text):
    probe = source["retrieval_query_matches"]["query-original"]
    return qualify_evidence(probe, query_id="query-original", visible_text=text,
        evidence_text=text, candidate=source, expected_project_identity=source["project_identity"])


def test_crop_cannot_inherit_a_removed_exact_symbol(tmp_path):
    source, _, text = _captured_source(tmp_path)
    crop = "The other constant returns `91`."
    source.update(char_start=text.index(crop), char_end=text.index(crop)+len(crop))
    assert not _qualify(source, crop).qualified


@pytest.mark.parametrize("field,value", [("path", "Other.md"), ("project_identity", "repo:other"),
    ("_source_snapshot_sha256", "sha256:"+"b"*64), ("generation_id", "snapshot:other"), ("resolved_version", "v99")])
def test_source_switch_cannot_reuse_binding(tmp_path, field, value):
    source, _, _ = _captured_source(tmp_path)
    source[field] = value
    assert not _qualify(source, source["_reference_evidence"]["text"]).qualified


def test_trace_bindings_do_not_override_current_source(tmp_path):
    source, _, _ = _captured_source(tmp_path)
    source["path"] = "Other.md"
    source["retrieval_query_matches"]["query-original"].update(qualified=True,
        bound_subject_context="ARGON", reference_bindings=[{"role": "source_locator", "trusted": True}])
    assert not _qualify(source, source["_reference_evidence"]["text"]).qualified


def test_missing_plan_cannot_reuse_prequalified_trace(tmp_path):
    source, _, _ = _captured_source(tmp_path)
    source.pop("_reference_root_plan")
    assert not _qualify(source, source["_reference_evidence"]["text"]).qualified


@pytest.mark.parametrize("symbol,value", [("orbit.Stop", "0"), ("kernel.Halt", "3")])
def test_anaphoric_default_keeps_exact_symbol_and_exit_value(tmp_path, symbol, value):
    cap = capture_reference_case(tmp_path, {"exit.md": f"# Termination\n\nRaising `{symbol}()` does not by itself imply an error.\n\n## Exit status\n\n`{symbol}()` takes an optional code parameter. By default, code is `{value}`, meaning there was no error.\n"},
        f"Does raising {symbol}() itself imply an error, and what is its default exit code?")
    assert f"code is `{value}`" in visible(cap)


def test_source_reference_context_derives_missing_line_span_from_attested_bytes(tmp_path, monkeypatch):
    from docmancer.docs.application.source_reference_evidence import SourceReferenceContext

    real = SourceReferenceContext.prepare

    def without_line_span(self, chunks, query_text=None):
        changed = [
            chunk.model_copy(update={"metadata": {
                key: value for key, value in (chunk.metadata or {}).items()
                if key != "line_span"
            }})
            for chunk in chunks
        ]
        return real(self, changed, query_text)

    monkeypatch.setattr(SourceReferenceContext, "prepare", without_line_span)
    text = "\nFirst fact is alpha.\nSecond fact is beta.\n"
    cap = capture_reference_case(
        tmp_path, {"Guide.md": text},
        "What first fact is documented in the file Guide?",
    )
    row = cap["projection_attempts"][0]["before_projection"]["context_pack"][0]
    assert row["line_start"] == 1
    assert row["line_end"] == 3


def test_source_reference_context_keeps_exact_whitespace_inside_attested_span(tmp_path):
    text = "\nFirst fact is alpha.\nSecond fact is beta.\n"
    cap = capture_reference_case(
        tmp_path, {"Guide.md": text},
        "What first fact is documented in the file Guide?",
    )
    row = cap["projection_attempts"][0]["before_projection"]["context_pack"][0]
    evidence = row["_reference_evidence"]
    assert evidence["char_start"] == 0
    assert evidence["char_end"] == len(text)
    assert evidence["text"] == text
    assert row["line_start"] == 1
    assert row["line_end"] == 3

