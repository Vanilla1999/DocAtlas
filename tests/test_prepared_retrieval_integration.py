"""Independent, model-free prepared-retrieval integration oracle.

The documents, questions, revisions, facts and caps below were fixed before
the first runtime execution. Do not repair them after observing a failure.
These are in-process public MCP scenarios with real member preparation and
SQLite lexical retrieval; they do not establish installed-stdio, semantic
answer quality or a latency improvement. No old holdout corpus is consumed.

Environment changes select experiments only. Retrieval, selection, validation,
storage and source continuation run unchanged, without mocks or observers.
An irrelevant experimental packet still FAILS the old empty-source contract;
its source-integrity checks are a separate result.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

import pytest
import yaml

from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource
from eval.evidence_quality_v2 import runtime


ADMISSION_ENV = "DOCATLAS_EXPERIMENT_ADMISSION"
PARENTS_ENV = "DOCATLAS_EXPERIMENT_PREPARED_PARENTS"
CAP_ENV = "DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS"
WIDE_CAP = 12000
SMALL_CAP = 900

# Frozen independently authored corpus and task oracle, including both revisions.
OPTICS_DOCUMENTS = {
    "docs/packing.md": (
        "# Field optics packing\n\n"
        "For an observation trip, lenses travel in rigid cases.\n"
        "A rigid case holds at most 4 lenses.\n"
        "Foam dividers separate every pair of lenses.\n"
        "Take the case inventory with the equipment.\n\n"
        "## Storage after return\n\n"
        "Remove the blue transport tags before putting empty cases into storage.\n"
    ),
    "docs/issue.md": (
        "# Field optics issue record\n\n"
        "The issue record for an observation trip goes to the collection custodian.\n"
        "The collection custodian checks completeness and signs before departure.\n"
        "A courier may carry the packed cases but may not sign the issue record.\n\n"
        "## Archive shelf\n\n"
        "Store completed folders with the tab marked «optique».\n"
    ),
}
OPTICS_QUESTION = (
    "For an observation trip with 11 lenses, how must the lenses be packed "
    "and who receives and signs the issue record?"
)
OPTICS_FACTS = {
    "docs/packing.md": (
        "A rigid case holds at most 4 lenses.",
        "Foam dividers separate every pair of lenses.",
    ),
    "docs/issue.md": (
        "The issue record for an observation trip goes to the collection custodian.",
        "The collection custodian checks completeness and signs before departure.",
    ),
}
UPDATED_ISSUE = (
    "# Field optics issue record\n\n"
    "The issue record for an observation trip goes to the instrumentation registrar.\n"
    "The instrumentation registrar checks completeness and signs before departure.\n"
    "A courier may carry the packed cases but may not sign the issue record.\n\n"
    "## Archive shelf\n\n"
    "Store completed folders with the tab marked «optique».\n"
)
UPDATED_OPTICS_FACTS = {
    "docs/packing.md": OPTICS_FACTS["docs/packing.md"],
    "docs/issue.md": (
        "The issue record for an observation trip goes to the instrumentation registrar.",
        "The instrumentation registrar checks completeness and signs before departure.",
    ),
}
SCOPE_DOCUMENTS = {
    "docs/camera.md": (
        "# Camera shutter control\n\n"
        "`SHUTTER_DELAY` sets shutter delay to 230 milliseconds.\n"
        "Changing `SHUTTER_DELAY` requires restarting the camera controller.\n"
    ),
    "modules/imaging/guide.md": (
        "# Sensor gain\n\n"
        "`SENSOR_GAIN` controls sensor gain for flat-field calibration.\n"
        "Apply the gain after the sensor reaches its operating temperature.\n"
    ),
}
SHUTTER_QUESTION = "Does `SHUTTER_DELAY` set shutter delay to 230 milliseconds?"
EXACT_NEGATIVE_QUESTION = "What configures `SHUTTER_DELAY_EXTRA`?"
MODULE_QUESTION = "Explain `SENSOR_GAIN` and sensor gain."
UNLISTED_QUESTION = "In docs/unlisted.md, explain `UNLISTED_PIN`."

CHECKLIST_STEPS = (
    "Record the serial number from each lens barrel in the case inventory before closing the case.",
    "Inspect every foam divider for torn edges and replace a divider if the tear exposes its rigid insert.",
    "Fit both protective caps to every lens so that neither optical surface can touch the divider during transport.",
    "Keep the cleaning cloth in the separate mesh pocket so that it cannot move between the packed lenses.",
    "Check that the case gasket sits continuously in its groove, including the corners beside both hinges.",
    "Remove sand from each latch recess with the soft brush before engaging the latch over its retaining hook.",
    "Close the latches on opposite sides in turn and inspect the lid for an uneven gap around its entire rim.",
    "Write the destination and the equipment custodian on a blue transport tag fixed to the main carrying handle.",
    "Place the paper case inventory in the clear external sleeve with its identifying heading facing outward.",
    "Leave the pressure equalisation valve closed during loading and keep its protective cover firmly attached.",
    "Secure the case upright with the broad restraint strap and route the strap through both vehicle anchor loops.",
    "Keep the case clear of the vehicle heater outlet so that hot air cannot flow directly across the lid gasket.",
    "Ask the driver to inspect the restraint strap after loading and to report any contact with a sharp metal edge.",
    "Photograph the closed case and its transport tag after loading so that the receiving custodian can compare them.",
    "Count the packed cases against the dispatch sheet before the vehicle leaves the equipment collection point.",
    "Give the receiving custodian the dispatch sheet together with the case inventory when the vehicle arrives.",
)
CHECKLIST_DOCUMENTS = {
    "docs/dispatch.md": (
        "# Optical case dispatch checklist\n\n"
        "Complete every dispatch checklist step before handing over an optical case.\n"
        + "\n".join(f"- {step}" for step in CHECKLIST_STEPS)
        + "\n\n## Filing after arrival\n\n"
        "File the signed dispatch sheet in the room labelled «réception».\n"
    ),
}
CHECKLIST_QUESTION = "What are all the optical case dispatch checklist steps?"
CHECKLIST_FACTS = {"docs/dispatch.md": CHECKLIST_STEPS}


@pytest.fixture
def state_root(tmp_path):
    """Reuse the established private store lifecycle, including real restart."""
    state = tmp_path / "member-state"
    try:
        yield state
    finally:
        home = runtime._FIXTURE_HOMES.pop(state.resolve(), None)
        if home is not None:
            home.cleanup()


def _context(service, project, question, **scope_arguments):
    arguments = {
        "question": question, "project_path": str(project),
        "scope": "project", **scope_arguments,
    }
    original_arguments = deepcopy(arguments)
    payload = call_docs_tool_payload("get_docs_context", arguments, service)
    # This optional audit happens after the real public call and before assertions.
    # It neither observes nor replaces any product stage and adds no product call.
    destination = os.environ.get("PYTEST_DOCATLAS_ARTIFACT_DIR")
    if destination:
        output = Path(destination).expanduser().resolve()
        storage = Path(service.config.index.db_path).resolve().parent
        if output.is_relative_to(project.resolve()) or output.is_relative_to(storage):
            raise ValueError("context audit directory must be outside fixture project and storage")
        output.mkdir(parents=True, exist_ok=True)
        current_test = os.environ.get("PYTEST_CURRENT_TEST", "")
        record = {
            "schema_version": 1,
            "tool": "get_docs_context",
            "test_nodeid": current_test.rsplit(" (", 1)[0],
            "pytest_current_test": current_test,
            "arguments": original_arguments,
            "public_payload": payload,
            "utf8_quarter_proxy": _packet_proxy(payload),
            "public_source_count": len(payload.get("sources") or ()),
        }
        (output / f"context-{uuid4().hex}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
    return payload


def _sql_connect(inventory):
    return sqlite3.connect(Path(inventory["storage_path"]).as_uri() + "?mode=ro", uri=True)


def _database_state(inventory):
    """Logical persistent state, read-only; no expected implementation snapshot."""
    with closing(_sql_connect(inventory)) as connection:
        schema = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name",
        ).fetchall()
        tables = {}
        for name, _ in schema:
            quoted = '"' + name.replace('"', '""') + '"'
            tables[name] = sorted(connection.execute(f"SELECT * FROM {quoted}").fetchall(), key=repr)
        return schema, tables


def _file_state(project):
    return {path.relative_to(project).as_posix(): path.read_bytes()
            for path in project.rglob("*") if path.is_file()}


def _committed_documents(inventory, project, documents):
    """Check the real published snapshot against the authored source bytes."""
    with closing(_sql_connect(inventory)) as connection:
        rows = connection.execute(
            "SELECT source, content, metadata_json FROM generation_sources WHERE generation_id=?",
            (inventory["generation_id"],),
        ).fetchall()
    assert {path for path, _, _ in rows} == {str(project / name) for name in documents}
    for path, content, metadata_json in rows:
        relative = Path(path).relative_to(project).as_posix()
        assert content == documents[relative]
        assert json.loads(metadata_json)["project_doc_content_hash"] == (
            "sha256:" + hashlib.sha256(documents[relative].encode("utf-8")).hexdigest()
        )


def _prepared_manifest(inventory):
    with closing(_sql_connect(inventory)) as connection:
        row = connection.execute(
            "SELECT validation_json FROM index_generations WHERE generation_id=?",
            (inventory["generation_id"],),
        ).fetchone()
    return json.loads(row[0]).get("prepared_parents")


def _relative_source(row, project, *, key="path_or_url"):
    path = Path(row[key])
    return path.relative_to(project).as_posix() if path.is_absolute() else path.as_posix()


def _assert_packet_sources(payload, project, documents, *, module_paths=()):
    assert payload.get("kind") == "docs_context", payload
    assert payload.get("answer_supported") is not True, payload
    assert payload.get("answer_available") is not True, payload
    assert payload.get("edit_ready") is not True, payload
    identities = set()
    evidence_ids = []
    for row in payload.get("sources") or ():
        relative = _relative_source(row, project)
        assert relative in documents, row
        text = documents[relative]
        lines = text.splitlines()
        start, end = row["line_start"], row["line_end"]
        assert type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), row
        snippet = row["snippet"]
        raw_span = "".join(text.splitlines(keepends=True)[start - 1:end])
        assert snippet and snippet in raw_span, row
        assert row["scope"] == ("module" if relative in module_paths else "project"), row
        assert row["authority"] == "source_of_truth", row
        # Public content_sha256 is a projection fingerprint, not a raw-file SHA.
        assert re.fullmatch(r"[0-9a-f]{64}", row["content_sha256"]), row
        assert row.get("project_identity"), row
        identities.add(row["project_identity"])
        evidence_ids.append(row["evidence_id"])
    assert len(identities) <= 1
    assert len(evidence_ids) == len(set(evidence_ids))
    for target in payload.get("read_next") or ():
        relative = _relative_source(target, project, key="path")
        assert relative in documents, target
        assert target["snapshot_sha256"] == (
            "sha256:" + hashlib.sha256(documents[relative].encode("utf-8")).hexdigest()
        )
        assert 1 <= target["line_start"] <= target["line_end"] <= len(documents[relative].splitlines())
        if identities:
            assert target["project_identity"] in identities


def _assert_facts(payload, project, facts):
    assert payload.get("context_available") is True, payload
    for relative, required in facts.items():
        snippets = [row["snippet"] for row in payload.get("sources") or ()
                    if _relative_source(row, project) == relative]
        for fact in required:
            assert any(fact in snippet for snippet in snippets), (relative, fact, snippets)


def _semantic_packet(payload):
    """Compare the full public DTO, except session capabilities and their estimate.

    Opaque capabilities may be reissued or unavailable within a session; their
    bytes affect estimated_tokens. Every other field, including policy, recovery
    instructions and evidence fingerprints, remains part of the parity assertion.
    The final budget is checked independently on the unmodified actual payload.
    """
    stable = deepcopy(payload)
    stable.pop("estimated_tokens", None)
    for key in ("sources", "read_next"):
        for row in stable.get(key) or ():
            row.pop("source_uri", None)
    return stable


def _read_continuation(service, row, project, documents):
    """One optional public bounded read; never follow its next cursor."""
    if not row.get("source_uri"):
        return 0
    resource = read_docs_resource(row["source_uri"], service)
    assert resource is not None
    result = json.loads(resource["text"])
    if "snippet" not in result:
        assert result == {"status": "complete", "reason_code": "end_of_source"}, result
        return 1
    relative = _relative_source(result, project, key="path")
    assert relative == _relative_source(row, project)
    assert result["project_identity"] == row["project_identity"]
    assert result["content_sha256"] == (
        "sha256:" + hashlib.sha256(documents[relative].encode("utf-8")).hexdigest()
    )
    lines = documents[relative].splitlines()
    start, end = result["line_start"], result["line_end"]
    assert 1 <= start <= end <= len(lines) and end - start < 40
    assert result["snippet"] == "\n".join(lines[start - 1:end])
    return 1


def _packet_proxy(payload):
    # The frozen wire proxy is independent of the production estimator/tokenizer.
    return (len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 3) // 4


def test_source_valid_candidates_deliver_multifacet_bound_read_only_packet(
    tmp_path, monkeypatch, state_root, record_property,
):
    """1 prepare, 2 contexts, at most 2 bounded source reads."""
    project = tmp_path / "project"
    runtime.write_project(project, OPTICS_DOCUMENTS)
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        inventory = runtime.index_project(service, config, project)
        _committed_documents(inventory, project, OPTICS_DOCUMENTS)
        before, files_before = _database_state(inventory), _file_state(project)
        baseline = _context(service, project, OPTICS_QUESTION)
        _assert_packet_sources(baseline, project, OPTICS_DOCUMENTS)
        env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
        env.setenv(CAP_ENV, str(WIDE_CAP))
        expanded = _context(service, project, OPTICS_QUESTION)
        _assert_packet_sources(expanded, project, OPTICS_DOCUMENTS)
        _assert_facts(expanded, project, OPTICS_FACTS)
        assert expanded.get("answer_supported") is False
        assert expanded.get("answer_available") is False
        assert expanded.get("edit_ready") is False
        # Existing retrieval attribution may survive; broader admission grants
        # no new query credit and does not establish complete answer coverage.
        assert set(expanded.get("covered_query_ids") or ()) <= set(baseline.get("covered_query_ids") or ())
        assert expanded.get("support_status") == "retrieval_only"
        assert expanded.get("coverage_policy") == "retrieval_attribution_only"
        assert (expanded.get("context_quality") or {}).get("status") in {"unverified", "partial"}
        assert _packet_proxy(expanded) <= WIDE_CAP
        reads = 0
        for relative, facts in OPTICS_FACTS.items():
            row = next(row for row in expanded["sources"]
                       if _relative_source(row, project) == relative and facts[0] in row["snippet"])
            reads += _read_continuation(service, row, project, OPTICS_DOCUMENTS)
        record_property("bounded_source_reads", reads)
        assert _database_state(inventory) == before
        assert _file_state(project) == files_before


def test_prepared_retrieval_preserves_default_and_scope_boundaries(
    tmp_path, monkeypatch, state_root, record_property,
):
    """1 prepare, 10 contexts, at most 1 bounded source read."""
    project, foreign = tmp_path / "project", tmp_path / "foreign-project"
    runtime.write_project(project, SCOPE_DOCUMENTS)
    catalog_path = project / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    for entry in catalog["documents"]:
        if entry["path"] == "modules/imaging/guide.md":
            entry.update(scope="module", module_path="modules/imaging")
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    (project / "docs/unlisted.md").write_text(
        "# Unlisted\n\n`UNLISTED_PIN` opens the private calibration cabinet.\n", encoding="utf-8",
    )
    runtime.write_project(foreign, {"docs/camera.md": SCOPE_DOCUMENTS["docs/camera.md"]})
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        env.setenv(PARENTS_ENV, "1")
        inventory = runtime.index_project(service, config, project)
        _committed_documents(inventory, project, SCOPE_DOCUMENTS)
        assert _prepared_manifest(inventory)
        before, files_before = _database_state(inventory), _file_state(project)
        foreign_before = _file_state(foreign)
        env.delenv(PARENTS_ENV)
        positive_off = _context(service, project, SHUTTER_QUESTION)
        negative_off = _context(service, project, EXACT_NEGATIVE_QUESTION)
        env.setenv(PARENTS_ENV, "1")
        positive_on = _context(service, project, SHUTTER_QUESTION)
        negative_on = _context(service, project, EXACT_NEGATIVE_QUESTION)
        shutter_facts = {"docs/camera.md": ("`SHUTTER_DELAY` sets shutter delay to 230 milliseconds.",)}
        _assert_facts(positive_off, project, shutter_facts)
        _assert_facts(positive_on, project, shutter_facts)
        assert _semantic_packet(positive_off) == _semantic_packet(positive_on)
        assert not negative_off.get("sources") and not negative_on.get("sources")
        assert _semantic_packet(negative_off) == _semantic_packet(negative_on)
        for payload in (positive_off, positive_on, negative_off, negative_on):
            _assert_packet_sources(payload, project, SCOPE_DOCUMENTS, module_paths=("modules/imaging/guide.md",))

        env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
        env.setenv(CAP_ENV, str(WIDE_CAP))
        unassessed_negative = _context(service, project, EXACT_NEGATIVE_QUESTION)
        _assert_packet_sources(unassessed_negative, project, SCOPE_DOCUMENTS, module_paths=("modules/imaging/guide.md",))
        assert unassessed_negative.get("answer_supported") is False
        assert unassessed_negative.get("answer_available") is False
        assert unassessed_negative.get("edit_ready") is False
        assert not unassessed_negative.get("covered_query_ids")
        # This recorded FAIL is not converted into a relevance PASS by this test.
        record_property("negative_empty_source_current_contract",
                        "FAIL" if unassessed_negative.get("sources") else "PASS")
        record_property("unassessed_negative_source_count", len(unassessed_negative.get("sources") or ()))
        all_scope = _context(service, project, MODULE_QUESTION, scope="all")
        project_scope = _context(service, project, MODULE_QUESTION)
        module_scope = _context(service, project, MODULE_QUESTION, scope="module", module_path="modules/imaging")
        for payload in (all_scope, module_scope):
            _assert_packet_sources(payload, project, SCOPE_DOCUMENTS, module_paths=("modules/imaging/guide.md",))
            _assert_facts(payload, project, {"modules/imaging/guide.md": (
                "`SENSOR_GAIN` controls sensor gain for flat-field calibration.",
            )})
        _assert_packet_sources(project_scope, project, {"docs/camera.md": SCOPE_DOCUMENTS["docs/camera.md"]})
        unlisted = _context(service, project, UNLISTED_QUESTION)
        assert not unlisted.get("sources"), unlisted
        foreign_result = _context(service, foreign, SHUTTER_QUESTION)
        assert not foreign_result.get("sources"), foreign_result
        assert foreign_result.get("answer_available") is not True
        row = next(row for row in module_scope["sources"]
                   if _relative_source(row, project) == "modules/imaging/guide.md")
        record_property("bounded_source_reads", _read_continuation(service, row, project, SCOPE_DOCUMENTS))
        assert _database_state(inventory) == before
        assert _file_state(project) == files_before
        assert _file_state(foreign) == foreign_before


def test_prepared_parents_parity_legacy_freshness_update_and_restart(
    tmp_path, monkeypatch, state_root, record_property,
):
    """2 prepare/sync calls, 6 contexts, at most 3 bounded source reads."""
    project = tmp_path / "project"
    runtime.write_project(project, OPTICS_DOCUMENTS)
    updated_documents = {**OPTICS_DOCUMENTS, "docs/issue.md": UPDATED_ISSUE}
    resource_reads = 0
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        legacy = runtime.index_project(service, config, project)
        assert _prepared_manifest(legacy) is None
        env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
        env.setenv(CAP_ENV, str(WIDE_CAP))
        legacy_state, legacy_files = _database_state(legacy), _file_state(project)
        on_demand = _context(service, project, OPTICS_QUESTION)
        env.setenv(PARENTS_ENV, "1")
        legacy_fallback = _context(service, project, OPTICS_QUESTION)
        _assert_facts(on_demand, project, OPTICS_FACTS)
        _assert_facts(legacy_fallback, project, OPTICS_FACTS)
        _assert_packet_sources(legacy_fallback, project, OPTICS_DOCUMENTS)
        assert _semantic_packet(on_demand) == _semantic_packet(legacy_fallback)
        assert _database_state(legacy) == legacy_state
        assert _file_state(project) == legacy_files
        old_issue = next(row for row in legacy_fallback["sources"]
                         if _relative_source(row, project) == "docs/issue.md")

        (project / "docs/issue.md").write_text(UPDATED_ISSUE, encoding="utf-8")
        edited_files = _file_state(project)
        env.setenv(CAP_ENV, str(SMALL_CAP))
        stale = _context(service, project, OPTICS_QUESTION)
        assert not stale.get("sources") and stale.get("context_available") is False, stale
        assert stale.get("requires_confirmation") is True, stale
        assert _packet_proxy(stale) <= SMALL_CAP  # Includes the final recovery decoration.
        if old_issue.get("source_uri"):
            unavailable = json.loads(read_docs_resource(old_issue["source_uri"], service)["text"])
            resource_reads += 1
            assert unavailable["status"] in {"source_changed", "source_unavailable"}, unavailable
            assert "snippet" not in unavailable
        assert _database_state(legacy) == legacy_state
        assert _file_state(project) == edited_files

        env.setenv(CAP_ENV, str(WIDE_CAP))
        prepared = runtime.index_project(service, config, project)
        assert prepared["generation_id"] != legacy["generation_id"]
        assert _prepared_manifest(prepared)["generation_id"] == prepared["generation_id"]
        _committed_documents(prepared, project, updated_documents)
        prepared_state = _database_state(prepared)
        env.delenv(PARENTS_ENV)
        updated_on_demand = _context(service, project, OPTICS_QUESTION)
        env.setenv(PARENTS_ENV, "1")
        updated_prepared = _context(service, project, OPTICS_QUESTION)
        for payload in (updated_on_demand, updated_prepared):
            _assert_packet_sources(payload, project, updated_documents)
            _assert_facts(payload, project, UPDATED_OPTICS_FACTS)
            assert "collection custodian" not in "\n".join(row["snippet"] for row in payload["sources"])
        assert _semantic_packet(updated_on_demand) == _semantic_packet(updated_prepared)
        row = next(row for row in updated_prepared["sources"]
                   if _relative_source(row, project) == "docs/issue.md")
        resource_reads += _read_continuation(service, row, project, updated_documents)
        assert _database_state(prepared) == prepared_state
        assert _file_state(project) == edited_files

    with runtime.isolated_service(state_root) as (service, _), monkeypatch.context() as env:
        env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
        env.setenv(PARENTS_ENV, "1")
        env.setenv(CAP_ENV, str(WIDE_CAP))
        restarted = _context(service, project, OPTICS_QUESTION)
        _assert_packet_sources(restarted, project, updated_documents)
        _assert_facts(restarted, project, UPDATED_OPTICS_FACTS)
        assert _semantic_packet(restarted) == _semantic_packet(updated_prepared)
        row = next(row for row in restarted["sources"] if _relative_source(row, project) == "docs/issue.md")
        resource_reads += _read_continuation(service, row, project, updated_documents)
        assert _database_state(prepared) == prepared_state
        assert _file_state(project) == edited_files
    record_property("bounded_source_reads", resource_reads)


def test_final_experimental_budget_preserves_facts_and_bounds_full_packet(
    tmp_path, monkeypatch, state_root, record_property,
):
    """1 prepare, 4 contexts; recovery-under-cap is exercised in the lifecycle test."""
    project = tmp_path / "project"
    runtime.write_project(project, CHECKLIST_DOCUMENTS)
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        env.setenv(PARENTS_ENV, "1")
        inventory = runtime.index_project(service, config, project)
        _committed_documents(inventory, project, CHECKLIST_DOCUMENTS)
        before, files_before = _database_state(inventory), _file_state(project)
        default_before = _context(service, project, CHECKLIST_QUESTION)
        env.setenv(ADMISSION_ENV, "source_valid_candidates_v1")
        env.setenv(CAP_ENV, str(WIDE_CAP))
        wide = _context(service, project, CHECKLIST_QUESTION)
        _assert_packet_sources(wide, project, CHECKLIST_DOCUMENTS)
        _assert_facts(wide, project, CHECKLIST_FACTS)
        assert wide.get("support_status") == "retrieval_only"
        assert wide.get("coverage_policy") == "retrieval_attribution_only"
        assert SMALL_CAP < _packet_proxy(wide) <= WIDE_CAP
        env.setenv(CAP_ENV, str(SMALL_CAP))
        bounded = _context(service, project, CHECKLIST_QUESTION)
        _assert_packet_sources(bounded, project, CHECKLIST_DOCUMENTS)
        assert _packet_proxy(bounded) <= SMALL_CAP, bounded
        assert bounded.get("answer_supported") is False
        assert bounded.get("answer_available") is False
        assert bounded.get("edit_ready") is False
        # Budget truncation must not restore hidden native query credits or
        # promote the already published packet's unverified coverage.
        assert set(bounded.get("covered_query_ids") or ()) <= set(wide.get("covered_query_ids") or ())
        if bounded.get("sources"):
            assert bounded.get("support_status") == "retrieval_only"
            assert bounded.get("coverage_policy") == "retrieval_attribution_only"
        else:
            assert bounded.get("support_status") == "insufficient_evidence"
        if (wide.get("context_quality") or {}).get("status") != "checked":
            assert (bounded.get("context_quality") or {}).get("status") != "checked"
        if wide.get("facet_coverage") != "full":
            assert bounded.get("facet_coverage") != "full"
        record_property("wide_packet_utf8_quarter_proxy", _packet_proxy(wide))
        record_property("small_packet_utf8_quarter_proxy", _packet_proxy(bounded))
        record_property("small_cap_delivered_source_count", len(bounded.get("sources") or ()))
        env.delenv(CAP_ENV)
        env.delenv(ADMISSION_ENV)
        default_after = _context(service, project, CHECKLIST_QUESTION)
        assert _semantic_packet(default_before) == _semantic_packet(default_after)
        _assert_packet_sources(default_after, project, CHECKLIST_DOCUMENTS)
        assert _database_state(inventory) == before
        assert _file_state(project) == files_before
