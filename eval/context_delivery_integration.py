"""Installed real stdio/SQLite acceptance for model view and truthful selection.

Independent source facts; no mock retrieval, selection, storage or validators.
Client tamper probes start with an actual delivered response, never a fake source.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

DOCUMENT = "# QuillTransit\n\n## Session lease\n\nA session lease lasts 37 seconds. Renewal is allowed twice, with a 9 second pause. A signed refusal is never retried.\n\n## Export\n\nExports require an active session lease and explicit user approval.\n"
QUESTION = "Сколько действует аренда сессии QuillTransit, сколько разрешено продлений и повторяется ли подписанный отказ?"
TRANSLATION = "How long does a QuillTransit session lease last, how many renewals are allowed, and is a signed refusal retried?"
ARMS = ("plain", "view", "view-structured")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ordinary_payload(reply):
    """Status/error are not source-evidence packets; do not use the evidence SDK."""
    if reply.structuredContent is not None:
        assert isinstance(reply.structuredContent, dict)
        return reply.structuredContent
    assert len(reply.content) == 1 and reply.content[0].type == "text"
    value = json.loads(reply.content[0].text)
    assert isinstance(value, dict)
    return value


def worker(args):
    import yaml
    from docmancer.mcp._docs_server_part01 import _run_async, call_docs_tool_payload
    from docmancer.docs.application.section_compression import observe_section_compression
    runtime = load("delivery_runtime", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = load("delivery_state", args.repo / "eval/prepared_model_comparison40/run.py")
    root = args.work / args.arm / "project"
    out = args.out / args.arm
    runtime.write_project(root, {"README.md": DOCUMENT})
    catalog = root / "docatlas.project-docs.yaml"
    value = yaml.safe_load(catalog.read_text())
    value["documentation_languages"] = {"README.md": ["en"]}
    catalog.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    with runtime.isolated_service(args.work / args.arm / "state") as (service, cfg):
        inventory = runtime.index_project(service, cfg, root)
        before = (helper.logical_state(inventory), helper.source_state(root))
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="minilm-sections-v1",
            DOCATLAS_MINILM_MODEL_DIR=str(args.model), DOCATLAS_CONTEXT_ABSTENTION="off",
            DOCATLAS_MCP_TEXT_FALLBACK="0" if args.arm == "view-structured" else "1",
            DOCATLAS_MCP_MODEL_VIEW="1" if args.arm.startswith("view") else "off")
        req = {"question": QUESTION, "search_question": TRANSLATION, "project_path": str(root)}
        off = call_docs_tool_payload("get_docs_context", req, service)
        with observe_section_compression() as trace:
            on = call_docs_tool_payload("get_docs_context", req, service)
        assert off == on, "host-only rank traces changed public response"
        save(out / "trace.json", trace)
        save(out / "observer-equivalence.json", {"equal": True, "public_handler_calls": 2})
        try:
            asyncio.run(_run_async(service))
        finally:
            peak = Path("/sys/fs/cgroup/memory.peak")
            save(out / "state.json", {"database_unchanged": before[0] == helper.logical_state(inventory),
                "sources_unchanged": before[1] == helper.source_state(root),
                "container_peak_bytes": int(peak.read_text()) if peak.exists() else None})


async def run(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.interfaces.host_context import extract_tool_payload, EvidenceDeliveryError
    from docmancer.docs.application.section_compression import expand_sections
    from docmancer.docs.application.model_context_view import resolve_model_reference, FORMAT
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    from copy import deepcopy
    counts = {"preparations": 0, "stdio_tool_calls": 0, "public_handler_calls": 0, "resource_reads": 0}
    records = []
    for arm in ARMS:
        out = args.out / arm
        out.mkdir(parents=True)
        root = args.work / arm / "project"
        params = StdioServerParameters(command=sys.executable, args=["-I", str(Path(__file__).resolve()),
            "--worker", "--arm", arm, "--repo", str(args.repo), "--work", str(args.work),
            "--out", str(args.out), "--model", str(args.model)], env=dict(os.environ))
        counts["preparations"] += 1
        counts["public_handler_calls"] += 2
        with (out / "stderr.log").open("w") as err:
          async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                assert {t.name for t in tools} == {"get_docs_context", "prepare_docs", "docs_status"}
                if arm.startswith("view"):
                    assert next(t for t in tools if t.name == "get_docs_context").outputSchema is None
                save(out / "tools.json", [t.model_dump() for t in tools])
                status = await client.call_tool("docs_status", {
                    "action": "project", "project_path": str(root), "include_language": True})
                counts["stdio_tool_calls"] += 1
                save(out / "language.json", status.model_dump(by_alias=True))
                assert not status.isError
                assert ordinary_payload(status)["documentation_language"]["languages"] == ["en"]
                req = {"question": QUESTION, "search_question": TRANSLATION, "project_path": str(root)}
                result = await client.call_tool("get_docs_context", req)
                counts["stdio_tool_calls"] += 1
                save(out / "reply.json", result.model_dump(by_alias=True))
                assert not result.isError
                wire = extract_tool_payload(result)
                payload = expand_sections(wire)
                assert payload["status"] == "ok", payload
                assert payload["source_selection"]["omitted_rows"] == 0
                assert payload["source_selection"]["selected_rows"] == len(payload["sources"])
                assert payload["answer_supported"] is False and payload["edit_ready"] is False
                text = "\n".join(row["snippet"] for row in payload["sources"])
                for fact in ("37 seconds", "twice", "9 second", "signed refusal is never retried"):
                    assert fact in text, fact
                for row in payload["sources"]:
                    assert row["path_or_url"] == "README.md" and row["snippet"] in DOCUMENT
                    span = "".join(DOCUMENT.splitlines(keepends=True)[row["line_start"]-1:row["line_end"]])
                    assert row["snippet"] in span
                visible = json.loads(result.content[0].text)
                if arm.startswith("view"):
                    assert visible["context_format"] == FORMAT and result.structuredContent is None
                    meta = result.model_dump(by_alias=True)["_meta"]
                    source = resolve_model_reference(visible, meta, visible["sources"][0]["ref"])
                    assert source == payload["sources"][0]
                    assert [r["text"] for r in visible["sources"]] == [r["snippet"] for r in payload["sources"]]
                    assert all("content_sha256" not in r and "source_uri" not in r for r in visible["sources"])
                    for case in ("changed-text", "missing-meta", "wrong-ref"):
                        modified = deepcopy(result.model_dump(by_alias=True))
                        if case == "missing-meta":
                            modified.pop("_meta")
                        else:
                            body = json.loads(modified["content"][0]["text"])
                            body["sources"][0]["text" if case == "changed-text" else "ref"] = "not the issued value"
                            modified["content"][0]["text"] = json.dumps(body)
                        try:
                            extract_tool_payload(modified)
                        except EvidenceDeliveryError:
                            pass
                        else:
                            raise AssertionError(case + " not rejected")
                    candidates = [row for row in payload["sources"] if row.get("source_uri")]
                    assert len(candidates) >= 2
                    actual = await client.read_resource(candidates[0]["source_uri"])
                    counts["resource_reads"] += 1
                    assert json.loads(actual.contents[0].text)["status"] in ("complete", "truncated")
                    path = root / candidates[-1]["path_or_url"]
                    prior = path.read_bytes()
                    try:
                        path.write_bytes(prior + b"\nChanged source snapshot.\n")
                        stale = json.loads((await client.read_resource(candidates[-1]["source_uri"])).contents[0].text)
                        counts["resource_reads"] += 1
                        assert stale["status"] in ("source_changed", "source_unavailable") and not stale.get("snippet")
                        assert stale.get("reason_code") in ("source_policy_or_snapshot_changed", "snapshot_digest_mismatch")
                        save(out / "stale-resource.json", stale)
                    finally:
                        path.write_bytes(prior)
                else:
                    assert visible.get("context_format") != FORMAT
                for label, request, expected in (
                    # A scorer overflow must actually acquire source candidates.
                    # 'environment' belongs to Poetry's separate existing control,
                    # not to this independent session-lease document.
                    ("long-query", {"question": "lease " * 140, "project_path": str(root)}, "section_compression_query_limit"),
                    ("blank-search", {**req, "search_question": " "}, "invalid_search_question"),
                ):
                    response = await client.call_tool("get_docs_context", request)
                    counts["stdio_tool_calls"] += 1
                    error = ordinary_payload(response)
                    save(out / f"{label}.json", {"isError": response.isError, "payload": error})
                    assert response.isError and error["error"]["reason_code"] == expected, (label, error)
                    assert error.get("context_format") != FORMAT and not response.model_dump(by_alias=True).get("_meta")
                body = result.content[0].text.encode()
                full = json.dumps(wire, ensure_ascii=False, separators=(",", ":")).encode()
                record = {"arm": arm, "status": payload["status"], "rows": len(payload["sources"]),
                    "model_text_tokens": projection_token_count(body), "machine_packet_tokens": projection_token_count(full)}
                if arm.startswith("view"):
                    assert record["model_text_tokens"] < record["machine_packet_tokens"]
                records.append(record)
        state = json.loads((out / "state.json").read_text())
        assert state["database_unchanged"] and state["sources_unchanged"]
        trace = json.loads((out / "trace.json").read_text())[0]
        assert len(trace["ranked_sections"]) == trace["candidate_sections"]
        assert all(r["selected"] for r in trace["ranked_sections"])
    save(args.out / "SUMMARY.json", {"head": os.getenv("TESTED_SHA"), "passed": True, "records": records,
        "counts": counts, "source_fact_checks": True, "observer_equal": True,
        "claim_boundary": "installed public stdio and SDK adapter, NOT autonomous strong-model behavior or provider billing"})


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "work", "out", "model"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--arm", choices=ARMS)
    args = parser.parse_args()
    for name in ("repo", "work", "out", "model"):
        setattr(args, name, getattr(args, name).resolve())
    if args.worker:
        return worker(args)
    import docmancer
    installed = Path(docmancer.__file__).resolve().parent
    assert not installed.is_relative_to(args.repo)
    assert all(p.read_bytes() == (args.repo / "docmancer" / p.relative_to(installed)).read_bytes() for p in installed.rglob("*.py"))
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(mode=0o700, parents=True)
    args.out.mkdir(parents=True)
    save(args.out / "FREEZE.json", {"question": QUESTION, "search_question": TRANSLATION,
        "source_sha256": hashlib.sha256(DOCUMENT.encode()).hexdigest(), "source": DOCUMENT})
    asyncio.run(run(args))

if __name__ == "__main__":
    main()
