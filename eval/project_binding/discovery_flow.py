"""One installed lifecycle scenario: approval, membership, move and refusal.

The tiny fixture is separate from the unchanged Black corpus. Expected facts
are written here before any runtime result exists, not derived from retrieval.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path


DOCUMENTS = {
    "README.md": "# Release checks\n\nA release uses the cobalt channel.\n",
    "packages/relay/notes/release.md": "# Release checks\n\nThe release gate needs a signed manifest.\n",
}
QUESTION = "Which release channel is used, and what does the release gate need?"


def reason(packet):
    return packet.get("reason_code") or (packet.get("error") or {}).get("reason_code")


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


async def run(recorder, work, environment, installed_command, server, checks, state):
    project = work / "discovery-project"
    for relative, text in DOCUMENTS.items():
        write(project, relative, text)
    write(project, ".gitignore", "scratch/\n")
    write(project, "scratch/ignored.md", "# Release checks\n\nIgnored scratch content must not be indexed.\n")
    write(project, "node_modules/vendor/README.md", "# Release checks\n\nVendor content is not project documentation.\n")
    write(project, "nested-ignore/.gitignore", "*.md\n")
    write(project, "nested-ignore/hidden.md", "# Release checks\n\nNested ignored content must not be indexed.\n")
    outside = work / "outside-document.md"
    outside.write_text("# Release checks\n\nOutside-project content must never be indexed.\n")
    (project / "outside-link.md").symlink_to(outside)
    assert not (project / "docs").exists() and not (project / "docatlas.project-docs.yaml").exists()
    env = environment(work / "discovery-host")
    storage = Path(env["DOCATLAS_HOME"]) / "mcp-members/members.db"
    command = installed_command() + ["mcp", "docs-serve", "--project-root", str(project)]
    before_cold = state.files(project), state.files(work / "discovery-host"), outside.read_bytes()
    async with server(recorder, "discovery", command, env, work / "unrelated-cwd") as session:
        cold, _ = await recorder.call(session, "discovery-cold", "get_docs_context", {"question": QUESTION})
        assert reason(cold) == "needs_prepare" and not checks.decoded_rows(cold)[0]
        assert cold.get("confirmation_reason") == "local_index_write"
        unconfirmed, _ = await recorder.call(session, "discovery-unconfirmed", "prepare_docs", {
            "action": "discover_project_docs"})
        assert reason(unconfirmed) == "confirmation_required"
        assert unconfirmed.get("mutation_performed") is False
        assert not storage.exists()
        assert (state.files(project), state.files(work / "discovery-host"), outside.read_bytes()) == before_cold

        prepared, item = await recorder.call(session, "discovery-PREPARE", "prepare_docs", {
            "action": "discover_project_docs", "confirm": True})
        assert not item["isError"] and prepared.get("status") == "success", prepared
        assert prepared["manifest_origin"] == "host" and prepared["candidate_count"] == len(DOCUMENTS)
        assert prepared["mutation_performed"] is True
        discovery = prepared["discovery"]
        assert discovery["mode"] == "bounded_discovery" and discovery["complete"] is True
        assert discovery["selected_documents"] == len(DOCUMENTS)
        assert discovery["source_bytes"] == sum(len(text.encode()) for text in DOCUMENTS.values())
        assert discovery["scanned_entries"] >= len(DOCUMENTS) and discovery["excluded_entries"]
        inventory = {"storage_path": str(storage), "generation_id": prepared["metrics"]["generation_id"]}
        checks.save(recorder.out / "discovery-SNAPSHOTS.json", state.snapshots(inventory, project, DOCUMENTS))
        assert state.files(project) == before_cold[0] and outside.read_bytes() == before_cold[2]
        assert not (project / "docatlas.project-docs.yaml").exists()
        before = state.database(storage), state.files(project)

        packet, item = await recorder.call(session, "discovery-read", "get_docs_context", {"question": QUESTION})
        assert not item["isError"], packet
        rows, _, _ = checks.checked_rows(packet, DOCUMENTS, project, authority="supporting")
        assert {row["path"] for row in rows} == set(DOCUMENTS)
        for path, fact in (("README.md", "cobalt channel"),
                           ("packages/relay/notes/release.md", "signed manifest")):
            assert any(fact in row["text"] for row in rows if row["path"] == path)
        retained = next(row for row in rows if row["path"] == "README.md")
        moved_row = next(row for row in rows if row["path"] != "README.md")
        await recorder.resource(session, "discovery-source-read", retained, DOCUMENTS, project)
        language, item = await recorder.call(session, "discovery-language", "docs_status", {
            "action": "project", "include_language": True})
        assert not item["isError"], language
        assert (state.database(storage), state.files(project)) == before

        # This explicit fixture mutation is not a product write or auto-refresh.
        old_relative = "packages/relay/notes/release.md"
        new_relative = "packages/relay/notes/moved-release.md"
        recorder.note("fixture_source_move", "started", old=old_relative, new=new_relative)
        (project / old_relative).rename(project / new_relative)
        recorder.note("fixture_source_move", "returned")
        moved_documents = {"README.md": DOCUMENTS["README.md"], new_relative: DOCUMENTS[old_relative]}
        before_moved = state.database(storage), state.files(project)
        stale, _ = await recorder.call(session, "discovery-stale", "get_docs_context", {"question": QUESTION})
        assert reason(stale) == "needs_prepare" and not checks.decoded_rows(stale)[0], stale
        recorder.counts["resources/read"] += 1
        recorder.note("resources/read", "started", label="discovery-stale-source", uri=moved_row["source_uri"])
        resource = await asyncio.wait_for(session.read_resource(moved_row["source_uri"]), 60)
        assert len(resource.contents) == 1
        stale_source = json.loads(resource.contents[0].text)
        checks.save(recorder.out / "discovery-stale-source.json", stale_source)
        assert stale_source.get("status") in {"source_unavailable", "source_changed"}, stale_source
        recorder.note("resources/read", "returned", label="discovery-stale-source",
                      status_value=stale_source.get("status"))
        assert (state.database(storage), state.files(project)) == before_moved
        refreshed, _ = await recorder.call(session, "discovery-REPREPARE", "prepare_docs", {
            "action": "discover_project_docs", "confirm": True})
        assert refreshed.get("status") == "success" and refreshed["candidate_count"] == 2, refreshed
        assert refreshed["metrics"]["generation_id"] != inventory["generation_id"]
        assert state.files(project) == before_moved[1]
        after_refresh = state.database(storage), state.files(project)
        current, item = await recorder.call(session, "discovery-current", "get_docs_context", {"question": QUESTION})
        assert not item["isError"], current
        current_rows, _, _ = checks.checked_rows(current, moved_documents, project, authority="supporting")
        assert {row["path"] for row in current_rows} == set(moved_documents)
        assert any("cobalt channel" in row["text"] for row in current_rows if row["path"] == "README.md")
        assert any("signed manifest" in row["text"] for row in current_rows if row["path"] == new_relative)
        await recorder.resource(session, "discovery-moved-source-read",
                                next(row for row in current_rows if row["path"] == new_relative), moved_documents, project)
        assert (state.database(storage), state.files(project)) == after_refresh

        # A supported per-project boundary limit, not a patched implementation,
        # must abort inventory before any partial host manifest/index commit.
        boundary_config = project / "docatlas.yaml"
        assert not boundary_config.exists()
        recorder.note("fixture_discovery_budget", "configured", max_scanned_files=1)
        write(project, "docatlas.yaml", "project:\n  max_scanned_files: 1\n")
        limited_files = state.files(project)
        exhausted, _ = await recorder.call(session, "discovery-budget-refusal", "prepare_docs", {
            "action": "discover_project_docs", "confirm": True})
        assert reason(exhausted) == "project_discovery_budget_exceeded", exhausted
        assert exhausted.get("mutation_performed") is False
        assert state.database(storage) == after_refresh[0] and state.files(project) == limited_files
        boundary_config.unlink()
        recorder.note("fixture_discovery_budget", "restored")
        assert (state.database(storage), state.files(project)) == after_refresh

        # An explicit empty allowlist must win over the previously prepared
        # host manifest. It is not consent to discover unrelated files again.
        write(project, "docatlas.project-docs.yaml", "schema_version: 1\ncode_files: []\ndocuments: []\n")
        before_empty = state.database(storage), state.files(project)
        empty, _ = await recorder.call(session, "discovery-empty-catalog-read", "get_docs_context", {"question": QUESTION})
        assert reason(empty) == "no_project_document_members" and not checks.decoded_rows(empty)[0]
        refused, _ = await recorder.call(session, "discovery-empty-catalog-prepare", "prepare_docs", {
            "action": "discover_project_docs", "confirm": True})
        assert refused.get("status") != "success" and refused.get("mutation_performed") is not True, refused
        assert (state.database(storage), state.files(project)) == before_empty

        # Replacing the bound directory must not reuse the same pathname as a
        # new authority. Keep both directories for the isolated CI artifact.
        relocated = work / "discovery-project-relocated"
        project.rename(relocated)
        project.mkdir()
        write(project, "README.md", "# Release checks\n\nAn unrelated replacement uses another channel.\n")
        before_replaced = state.database(storage), state.files(project), state.files(relocated)
        changed, item = await recorder.call(session, "discovery-root-replaced", "get_docs_context", {"question": QUESTION})
        assert item["isError"] and reason(changed) == "docs_context_target_changed"
        assert not checks.decoded_rows(changed)[0]
        assert (state.database(storage), state.files(project), state.files(relocated)) == before_replaced
    assert (state.database(storage), state.files(project), state.files(relocated)) == before_replaced
    assert outside.read_bytes() == before_cold[2]
    checks.save(recorder.out / "DISCOVERY.json", {
        "pass": True, "initial_generation": inventory["generation_id"],
        "refreshed_generation": refreshed["metrics"]["generation_id"],
        "documents_outside_docs_directory": True, "finite_membership_and_raw_hashes_checked": True,
        "ignored_vendor_nested_ignore_symlink_excluded": True, "product_no_repository_writes": True,
        "unconfirmed_and_stale_reads_do_not_prepare": True, "source_move_requires_confirmed_preparation": True,
        "continuation_provider_scope_verified": True, "empty_explicit_catalog_not_widened": True,
        "budget_exhaustion_no_partial_manifest_or_index_commit": True,
        "replacement_root_not_followed": True,
        "fixture_mutations": ["source rename", "temporary boundary budget config", "empty explicit catalog", "root replacement"],
        "after_exit_database_and_project_files_unchanged": True,
    })
