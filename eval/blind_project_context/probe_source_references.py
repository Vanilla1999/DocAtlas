"""Real SQLite/catalog/filesystem + public resource-read candidate integration.

Isolated authored fixtures, not the frozen benchmark. No retrieval/validation mocks.
Run with the supported environment: python -m eval.blind_project_context.probe_source_references
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time

from pytest import MonkeyPatch

from docmancer.docs.application.source_continuation import (
    SourceContinuationReader, SourceReference, bind_project_source_continuations,
    source_continuation_uri,
)
from docmancer.docs.application.standalone_text_view import render_standalone_text
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.mcp.docs_server import call_docs_tool_payload, current_tools, read_docs_resource
from tests._fixture_member_transaction import indexed_fixture_member_service


def run() -> dict:
    began = time.monotonic()
    # The host scratch ancestor must satisfy the production storage guard.
    with tempfile.TemporaryDirectory(prefix="step10-refs-", dir="/tmp/opencode") as directory, MonkeyPatch.context() as env:
        root = Path(directory)
        env.setenv("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT", "1")
        env.setenv("DOCATLAS_EXPERIMENT_MINI_PATH", "/tmp/opencode/step10-mini-assets")
        env.setenv("DOCATLAS_CONTEXT_COMPRESSION", "off")
        project = root / "project"
        project.mkdir()
        (project / "docs").mkdir()
        (project / "pyproject.toml").write_text('[project]\nname="source-reference-probe"\nversion="0.1"\n')
        sections = [f"# Section {n}\r\nRule {n}: retain exact bytes.\r\n" for n in range(131)]
        long_section = "# Full procedure\r\n" + "".join(f"{n}. Verify step {n}.\r\n" for n in range(80))
        tail = "# Last section\nFinal exception: preserve this tail.\n"
        text = "".join(sections) + long_section + tail
        huge = "# Emergency\n" + " x" * 51000 + "END_UNTRIMMED\n"
        (project / "docs/reference.md").write_bytes(text.encode())
        (project / "docs/huge.md").write_bytes(huge.encode())
        (project / "docatlas.project-docs.yaml").write_text(
            "schema_version: 1\ndocuments:\n" + "".join(
                f"  - path: {path}\n    role: runbook\n    scope: project\n"
                "    authority: source_of_truth\n    status: active\n    description: Source read fixture\n"
                for path in ("docs/reference.md", "docs/huge.md")))
        service, _ = indexed_fixture_member_service(root, env, project, ("docs/reference.md", "docs/huge.md"))
        reader = service.source_reader
        store = service._read_agent_instance().store

        def original(path: str, start: int, end: int) -> dict:
            metadata = store.source_metadata(str(project / path))
            return {"path": path, "project_identity": metadata["project_identity"],
                    "_source_snapshot_sha256": metadata["project_doc_content_hash"],
                    "_source_catalog_hash": metadata["project_doc_catalog_entry_hash"],
                    "authority": "source_of_truth", "doc_scope": "project",
                    "line_start": start, "line_end": end}

        def packet_for(spans: list[tuple[int, int]], *, path="docs/reference.md", body=text):
            packet = {"kind": "docs_context", "status": "ok", "sources": [],
                      "context_quality": {"status": "unverified"},
                      "source_selection": {"policy": "integration-probe", "complete": True}}
            snapshot = {}
            lines = body.splitlines(keepends=True)
            for index, (start, end) in enumerate(spans):
                source = original(path, start, end)
                evidence_id = f"fixture-{index}"
                projected = {"evidence_id": evidence_id, "path_or_url": path,
                             "project_identity": source["project_identity"],
                             "scope": "project", "authority": "source_of_truth",
                             "line_start": start, "line_end": end,
                             "content_sha256": source["_source_snapshot_sha256"],
                             "snippet": "".join(lines[start - 1:end]),
                             "source_uri": source_continuation_uri(str(project), source)}
                packet["sources"].append(projected)
                snapshot[evidence_id] = {"source": source, "projected_source": deepcopy(projected)}
            return packet, snapshot

        calls = 0
        def read(uri):
            nonlocal calls
            calls += 1
            return call_docs_tool_payload("read_docs_source", {"uri": uri}, service)

        assert "read_docs_source" in {tool["name"] for tool in current_tools()}

        # More than the old registry capacity, in one atomic packet. Every
        # capability must remain usable and every read must preserve source bytes.
        packet, snapshot = packet_for([(2 * n + 1, 2 * n + 1) for n in range(131)])
        before = deepcopy(packet)
        bind_project_source_continuations(reader, str(project), packet, snapshot)
        assert packet == before, packet
        for n, row in enumerate(packet["sources"]):
            result = read(row["source_uri"])
            assert result["snippet"].encode() == sections[n].encode(), result
        assert read(packet["sources"][0]["source_uri"])["status"] == "source_unavailable"
        assert json.loads(read_docs_resource(packet["sources"][0]["source_uri"], service)["text"])["status"] == "source_unavailable"
        retry, retry_snapshot = deepcopy(before), deepcopy(snapshot)
        bind_project_source_continuations(reader, str(project), retry, retry_snapshot)
        assert retry["reason_code"] == "source_reference_batch_rejected"

        # One chain exceeds both the legacy two-read limit and forty-line limit.
        base = original("docs/reference.md", 1, 1)
        reference = SourceReference(str(project), base["project_identity"], base["path"],
            base["_source_snapshot_sha256"], base["_source_catalog_hash"], "source_of_truth", "project", None, 259)
        uri = reader.issue(reference)
        delivered = []
        while uri:
            result = read(uri)
            delivered.append(result["snippet"])
            uri = result["continuation"]
        assert delivered == sections[129:] + [long_section, tail]

        # A mixed valid/invalid batch never publishes the valid first reference.
        rejected, bad_snapshot = packet_for([(3, 4), (5, 6)])
        rejected_uris = [row["source_uri"] for row in rejected["sources"]]
        bad_snapshot["fixture-1"]["source"]["_source_catalog_hash"] = "sha256:" + "0" * 64
        bind_project_source_continuations(reader, str(project), rejected, bad_snapshot)
        assert rejected["reason_code"] == "source_reference_batch_rejected"
        assert all(read(uri)["status"] == "source_unavailable" for uri in rejected_uris)

        # Whole selected emergency packet is renderable for pricing, but neither
        # its body nor a usable reference is published by the binder.
        emergency, emergency_snapshot = packet_for([(1, 2)], path="docs/huge.md", body=huge)
        rendered = render_standalone_text(emergency).text
        assert rendered is not None and "END_UNTRIMMED" in rendered
        tokens = projection_token_count(rendered.encode())
        assert tokens > 50000
        emergency_uri = emergency["sources"][0]["source_uri"]
        bind_project_source_continuations(reader, str(project), emergency, emergency_snapshot)
        assert emergency["reason_code"] == "context_emergency_stop" and not emergency["sources"]
        assert read(emergency_uri)["status"] == "source_unavailable"
        big = original("docs/huge.md", 1, 1)
        big_ref = replace(reference, path="docs/huge.md", content_sha256=big["_source_snapshot_sha256"],
                          catalog_entry_hash=big["_source_catalog_hash"], line_end=1)
        result = read(reader.issue(big_ref))
        assert result["reason_code"] == "context_emergency_stop" and "snippet" not in result

        # A controlled clock is the only substituted boundary. Real policy,
        # SQLite and filesystem checks still run on every bind/read.
        now = [100.0]
        expiring = SourceContinuationReader(reader.gateway, clock=lambda: now[0])
        service.source_reader = expiring
        timed, timed_snapshot = packet_for([(1, 2)])
        timed_uri = timed["sources"][0]["source_uri"]
        bind_project_source_continuations(expiring, str(project), timed, timed_snapshot)
        assert timed["status"] == "ok"
        now[0] = 500.0
        bind_project_source_continuations(expiring, str(project), timed, timed_snapshot)
        assert timed["status"] == "ok"
        now[0] = 701.0
        assert read(timed_uri)["status"] == "source_unavailable"
        bind_project_source_continuations(expiring, str(project), timed, timed_snapshot)
        assert timed["reason_code"] == "source_reference_batch_rejected"
        assert read(timed_uri)["status"] == "source_unavailable"
        service.source_reader = reader

        # Real filesystem drift after issuance must not produce latest bytes.
        stale_uri = reader.issue(reference)
        (project / "docs/reference.md").write_bytes(text.encode() + b"changed\n")
        assert read(stale_uri)["status"] == "source_changed"
        return {"status": "pass", "boundary": "application binder + public read_docs_source tool; real SQLite/catalog/filesystem",
                "source_tool_calls": calls, "cross_resource_replay_calls": 1, "atomic_batch_references": 131,
                "structural_chain_reads": len(delivered), "largest_delivered_lines": 81,
                "expiry_clock": "controlled; rebind did not extend expiry or revive URI",
                "emergency_packet_tokens": tokens, "seconds": round(time.monotonic() - began, 3)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
