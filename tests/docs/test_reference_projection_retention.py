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


def test_serialized_reference_window_retains_valid_evidence(tmp_path):
    source, _, _ = _captured_source(tmp_path)
    reloaded = json.loads(json.dumps(source))
    result = _qualify(reloaded, source["_reference_evidence"]["text"])
    assert result.qualified
    assert {b["field"] for b in result.trace["reference_bindings"]} >= {"path", "body"}


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


def test_projection_requalification_performs_no_io(tmp_path, monkeypatch):
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
    source, question, _ = _captured_source(tmp_path)
    source["snippet"] = source["_reference_evidence"]["text"]
    def forbidden(*args, **kwargs):
        raise AssertionError("projection attempted I/O")
    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("pathlib.Path.read_text", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    result = _requalify_visible_source(source, query_text={"query-original": question})
    assert result["retrieval_query_matches"]["query-original"]["qualified"] is True


@pytest.mark.parametrize("field,value", [("path_or_url", "Other.md"), ("generation_id", "snapshot:other"), ("snippet", "Fabricated continuation.")])
def test_structural_continuation_revalidates_source_and_current_bytes(tmp_path, field, value):
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
    source, question, _ = _captured_source(tmp_path)
    trace = dict(source["retrieval_query_matches"]["query-original"])
    trace.update(query_origin="canonical", qualified=True, coverage_kind="derived", qualification_route="same_atom_continuation")
    trace.pop("derived_from_query_id", None)
    source.update(snippet=source["_reference_evidence"]["text"],
        retrieval_query_matches={"query-canonical": trace}, _independent_query_plan={})
    before = _requalify_visible_source(source, query_text={"query-canonical": question})
    assert before["retrieval_query_matches"]["query-canonical"]["qualified"] is True
    source[field] = value
    after = _requalify_visible_source(source, query_text={"query-canonical": question})
    assert after["retrieval_query_matches"]["query-canonical"]["qualified"] is False


def test_default_and_exception_survive_with_a_named_source(tmp_path):
    cap = capture_reference_case(tmp_path, {"VeloraGuide.md":
        "# LeaseClient\n\nLeaseClient default timeout is `17` seconds.\n\nA timeout raises `LeaseExpired`.\n"
    }, "What is LeaseClient default timeout and which exception is raised, according to the file VeloraGuide?")
    assert "17" in visible(cap) and "LeaseExpired" in visible(cap)


def test_disabled_condition_is_not_replaced_by_enabled_example(tmp_path):
    cap = capture_reference_case(tmp_path, {"VeloraGuide.md":
        "# audit-mode\n\nIf preview mode is not enabled, audit-mode has no effect.\n\nWhen preview mode is enabled, configure audit-mode using `--audit`.\n"
    }, "In the file VeloraGuide, what happens to audit-mode when preview mode is disabled?")
    assert "has no effect" in visible(cap)


def test_full_projector_replays_prepared_snapshot_without_io(tmp_path, monkeypatch):
    from docmancer.docs.application._docs_context_projection_core import project_docs_context
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    cap = capture_reference_case(tmp_path, {"Guide.md": "# Install\n\nInstallation command: run `atlas prepare`.\n"},
        "What installation command is documented in the file Guide?")
    retrieval = copy.deepcopy(cap["projection_attempts"][0]["before_projection"])
    def forbidden(*args, **kwargs):
        raise AssertionError("full projector attempted I/O")
    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr("pathlib.Path.read_text", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    payload, snapshot = project_docs_context(retrieval=retrieval)
    assert "atlas prepare" in "\n".join(row["snippet"] for row in payload["sources"])
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []


def test_application_does_not_relabel_old_generation_as_current(tmp_path, monkeypatch):
    from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
    real = SourceReferenceContext.prepare
    def alter(self, chunks, query_text=None):
        changed = [chunk.model_copy(update={"metadata": {**chunk.metadata, "generation_id": "old-generation"}}) for chunk in chunks]
        return real(self, changed, query_text)
    monkeypatch.setattr(SourceReferenceContext, "prepare", alter)
    cap = capture_reference_case(tmp_path, {"Guide.md": "# Install\n\nInstallation command: run `atlas prepare`.\n"},
        "What installation command is documented in the file Guide?")
    assert not cap["public_payload"].get("sources")


def test_independent_lookup_keeps_own_identity_without_claiming_root_support(tmp_path):
    question = "What does the constant ARGON return in the file Guide?"
    lookup = "What installation command prepares this tool?"
    text = "# Guide\n\nThe constant ARGON returns `73`.\n\nInstallation command: run `atlas prepare` to prepare this tool.\n"
    cap = capture_reference_case(tmp_path, {"Guide.md": text}, question, lookups=(lookup,))
    source = copy.deepcopy(cap["projection_attempts"][0]["before_projection"]["context_pack"][0])
    crop = "Installation command: run `atlas prepare` to prepare this tool."
    source.update(char_start=text.index(crop), char_end=text.index(crop)+len(crop))
    probe = {"query_text": lookup, "query_origin": "host_lookup", "query_terms": ["installation", "command", "prepares", "tool"], "exact_terms": []}
    result = qualify_evidence(probe, query_id="query-lookup-1", visible_text=crop,
        evidence_text=crop, candidate=source, expected_project_identity=source["project_identity"])
    assert result.qualified, result.trace
    assert "argon" not in result.trace["exact_terms"]
    assert not _qualify(source, crop).qualified, "independent lookup cannot certify root code identity"
    source["path"] = "Other.md"
    assert not qualify_evidence(probe, query_id="query-lookup-1", visible_text=crop,
        evidence_text=crop, candidate=source).qualified


@pytest.mark.parametrize("symbol,value", [("orbit.Stop", "0"), ("kernel.Halt", "3")])
def test_anaphoric_default_keeps_exact_symbol_and_exit_value(tmp_path, symbol, value):
    cap = capture_reference_case(tmp_path, {"exit.md": f"# Termination\n\nRaising `{symbol}()` does not by itself imply an error.\n\n## Exit status\n\n`{symbol}()` takes an optional code parameter. By default, code is `{value}`, meaning there was no error.\n"},
        f"Does raising {symbol}() itself imply an error, and what is its default exit code?")
    assert f"code is `{value}`" in visible(cap)


def test_unanswerable_new_sentence_does_not_hide_answerable_local_fact(tmp_path):
    cap = capture_reference_case(tmp_path, {"client.md": "# NetClient\n\nNetClient enforces timeouts everywhere by default.\n\nThe default behavior raises `NetExpired` after 17 seconds of inactivity.\n"},
        "What is NetClient default timeout behavior: how long and which exception? Also identify the exact value chosen in our private production deployment.")
    assert "NetExpired" in visible(cap) and "17 seconds" in visible(cap)
    assert cap["public_payload"]["answer_supported"] is False


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


def test_visible_term_presence_caches_repeated_regex_work(monkeypatch):
    from docmancer.docs.domain import evidence_qualification as qualification

    calls = 0
    real = qualification.technical_term_pattern

    def counted(term, *, exact=True):
        nonlocal calls
        calls += 1
        return real(term, exact=exact)

    monkeypatch.setattr(qualification, "technical_term_pattern", counted)
    if hasattr(qualification._visible_term_present, "cache_clear"):
        qualification._visible_term_present.cache_clear()
    term = "cacheprobe_z91"
    text = "prefix cacheprobe_z91 suffix"
    assert qualification._visible_term_present(term, text, exact=True)
    assert qualification._visible_term_present(term, text, exact=True)
    assert calls == 1
