"""Installed MCP acceptance for opt-in MiniLM section compression.

Five real catalog/SQLite preparations, forty uncompressed public calls, and forty
compressed calls delivered over stdio. The oracle is loaded only after delivery.
Extra public scenarios: overlong query, resource read, changed source rejection,
and missing model assets. No external transport or scorer is mocked.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
from datetime import timedelta


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dataset(repo):
    root = repo / "eval/prepared_model_comparison40"
    cases = json.loads((root / "questions.json").read_text())["cases"]
    families = json.loads((root / "source_plan.json").read_text())["families"]
    assert len(cases) == 40 and len({c["id"] for c in cases}) == 40
    return root, cases, families


def wire_cost(wire):
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    data = wire.encode("utf-8")
    tokens = projection_token_count(data)
    return max(tokens, math.ceil(len(data) / 4)), tokens


def worker(args):
    runtime = load_module("section_fixture", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = load_module("section_helpers", args.repo / "eval/prepared_model_comparison40/run.py")
    from docmancer.mcp._docs_server_part01 import _run_async, call_docs_tool_payload
    from docmancer.docs.application.section_compression import observe_section_compression
    corpus, cases, families = dataset(args.repo)
    family = next(f for f in families if f["id"] == args.family)
    cases = [c for c in cases if c["project_group"] == args.family]
    root = args.work / args.family / "project"
    documents = {p: (corpus / "sources" / args.family / p).read_text(encoding="utf-8")
                 for p in family["paths"]}
    runtime.write_project(root, documents)
    assert all((root / p).read_bytes() == (corpus / "sources" / args.family / p).read_bytes()
               for p in documents)
    out = args.out / args.family
    with runtime.isolated_service(args.work / args.family / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        before_db, before_files = helper.logical_state(inventory), helper.source_state(root)
        save(out / "preparation.json", {"root": str(root), "inventory": inventory})
        # The fixture isolates HOME/DOCATLAS_*; opt-in is re-applied only after
        # authorized preparation. No setting comes from document contents.
        os.environ["DOCATLAS_CONTEXT_COMPRESSION"] = "off"
        with observe_section_compression() as observations:
            if not args.missing_model:
                for case in cases:
                    request = {"question": case["question"], "project_path": str(root), "scope": "project"}
                    start = time.perf_counter()
                    payload = call_docs_tool_payload("get_docs_context", request, service)
                    save(out / (case["id"] + "-baseline.json"), payload)
                    assert payload.get("kind") == "docs_context" and payload.get("sources")
                    assert "context_format" not in payload
                    save(out / (case["id"] + "-baseline-time.json"), time.perf_counter() - start)
                assert observations == [], "disabled mode must not score"
            os.environ.update(
                DOCATLAS_MCP_MODEL_VIEW="1" if args.model_view else "off",
                DOCATLAS_CONTEXT_COMPRESSION="minilm-sections-v1",
                DOCATLAS_MINILM_MODEL_DIR=str(args.model),
                DOCATLAS_MCP_TEXT_FALLBACK="1",
                HF_HUB_OFFLINE="1",
                DOCATLAS_SECTION_TOP_K=str(args.top_k), DOCATLAS_SECTION_UNITS=args.units,
                DOCATLAS_SECTION_WIRE_FORMAT=args.wire_format,
            )
            try:
                asyncio.run(_run_async(service))
            finally:
                memory_peak = Path("/sys/fs/cgroup/memory.peak")
                save(out / "server.json", {
                    "observations": observations,
                    "database_unchanged": helper.logical_state(inventory) == before_db,
                    # Source mutation is restored in the revocation scenario.
                    "files_unchanged_before_revoke": before_files,
                    "files_after": helper.source_state(root),
                    "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                    "container_memory_peak": int(memory_peak.read_text()) if memory_peak.is_file() else None,
                    "versions": {name: importlib.metadata.version(name) for name in
                                 ("onnxruntime", "tokenizers", "tiktoken", "mcp")},
                })


def assert_operational_error(response, expected, receipt_path):
    """Verify the actual public error envelope, not a fabricated direct DTO."""
    assert len(response.content) == 1 and response.content[0].type == "text"
    payload = json.loads(response.content[0].text)
    save(receipt_path, {"isError": response.isError, "payload": payload})
    assert response.isError and payload.get("status") == "failed", payload
    assert (payload.get("error") or {}).get("reason_code") == expected, payload
    assert not payload.get("sources") and not payload.get("source_groups"), payload


async def client(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.section_compression import expand_sections, encode_sections, FORMAT, LEGACY_FORMAT
    _, cases, families = dataset(args.repo)
    records, controls = [], []
    for family in families:
        group = family["id"]
        out = args.out / group
        out.mkdir(parents=True, exist_ok=True)
        params = StdioServerParameters(command=sys.executable, args=[
            "-I", str(Path(__file__).resolve()), "--worker", "--family", group,
            *( ["--model-view"] if args.model_view else [] ),
            "--top-k", str(args.top_k), "--units", args.units, "--wire-format", args.wire_format,
            "--repo", str(args.repo), "--work", str(args.work),
            "--out", str(args.out), "--model", str(args.model),
        ], env=dict(os.environ))
        root = args.work / group / "project"
        with (out / "stderr.log").open("w") as stderr:
            async with stdio_client(params, errlog=stderr) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
                    await session.initialize()
                    assert "get_docs_context" in {t.name for t in (await session.list_tools()).tools}
                    group_rows = []
                    for case in (c for c in cases if c["project_group"] == group):
                        request = {"question": case["question"], "project_path": str(root), "scope": "project"}
                        begin = time.perf_counter()
                        result = await session.call_tool("get_docs_context", request)
                        elapsed = time.perf_counter() - begin
                        assert not result.isError, result
                        assert len(result.content) == 1 and result.content[0].type == "text"
                        text = result.content[0].text
                        display = json.loads(text)
                        if args.model_view:
                            from docmancer.docs.interfaces.host_context import extract_tool_payload
                            from docmancer.docs.application.model_context_view import resolve_model_reference, FORMAT as VIEW_FORMAT
                            assert display["context_format"] == VIEW_FORMAT
                            raw_result = result.model_dump(by_alias=True)
                            wire = extract_tool_payload(result)
                            metadata = raw_result["_meta"]
                            restored = expand_sections(wire)
                            assert [x["text"] for x in display["sources"]] == [x["snippet"] for x in restored["sources"]]
                            for visible, source in zip(display["sources"], restored["sources"], strict=True):
                                assert resolve_model_reference(display, metadata, visible["ref"]) == source
                            save(out / (case["id"] + "-private.json"), metadata)
                        else:
                            wire = display
                        source_wire_text = json.dumps(wire, ensure_ascii=False, separators=(",", ":"))
                        assert wire.get("context_format") in (FORMAT, LEGACY_FORMAT), wire
                        assert result.structuredContent is None, "must not duplicate full metadata in another output"
                        assert text == json.dumps(display, ensure_ascii=False, separators=(",", ":"), sort_keys=args.model_view)
                        expanded = expand_sections(wire)
                        assert wire == json.loads(source_wire_text), "decoder must not mutate received wire data"
                        assert expand_sections(expanded) == expanded, "expanded public DTO must remain lossless"
                        # Diagnostic serialization of the same delivered sources,
                        # not a second retrieval or historical emitted-wire run.
                        legacy = encode_sections(expanded, context_format=LEGACY_FORMAT)
                        assert expand_sections(legacy) == expanded
                        legacy_text = json.dumps(legacy, ensure_ascii=False, separators=(",", ":"))
                        assert wire["estimated_tokens"] == wire_cost(source_wire_text)[0] <= 12000
                        assert wire_cost(text)[0] <= 12000
                        baseline = json.loads((out / (case["id"] + "-baseline.json")).read_text())
                        old = {r["evidence_id"]: r for r in baseline["sources"]}
                        assert expanded["sources"], "ranking failure must not masquerade as abstention"
                        for row in expanded["sources"]:
                            previous = old[row["evidence_id"]]
                            assert row == previous, ("selected source was altered", case["id"], row, previous)
                        chosen = {(r["path_or_url"], r.get("section"), r["project_identity"], r["scope"],
                                   r["version_binding"], r["authority"]) for r in expanded["sources"]}
                        if args.units == "legacy":
                            assert len(chosen) <= args.top_k
                        wanted = [r["evidence_id"] for r in baseline["sources"]
                                  if (r["path_or_url"], r.get("section"), r["project_identity"], r["scope"],
                                      r["version_binding"], r["authority"]) in chosen]
                        assert wanted == [r["evidence_id"] for r in expanded["sources"]], "partial acquired section"
                        (out / (case["id"] + "-wire.json")).write_bytes(text.encode("utf-8"))
                        save(out / (case["id"] + "-expanded.json"), expanded)
                        records.append({
                            "case_id": case["id"], "family": group,
                            "context_format": display["context_format"],
                            "model_view": args.model_view,
                            "same_call_machine_tokens": wire_cost(source_wire_text)[1],
                            "baseline_tokens": wire_cost(json.dumps(baseline, ensure_ascii=False))[1],
                            "tokens": wire_cost(text)[1], "cost": wire_cost(text)[0],
                            "wire_utf8_bytes": len(text.encode("utf-8")),
                            "same_payload_v1_tokens": wire_cost(legacy_text)[1],
                            "same_payload_v1_cost": wire_cost(legacy_text)[0],
                            "same_payload_v1_utf8_bytes": len(legacy_text.encode("utf-8")),
                            "v1_comparison_boundary": "diagnostic reserialization; not historical emitted wire",
                            "expanded_utf8_bytes": len(json.dumps(expanded, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
                            "rows": len(expanded["sources"]), "sections": len(chosen),
                            "seconds": elapsed, "whole_acquired_sections": True, "roundtrip_sources": True,
                        })
                        if case["id"] == "V40-B01":
                            from docmancer.docs.interfaces.grounded_mcp_session import GroundedMCPSession
                            sdk = GroundedMCPSession(session, request, wire, {"answer": "documented constraints"})
                            assert sdk.context["sources"] == expanded["sources"]
                            try:
                                GroundedMCPSession(session, request, wire, {}, evidence_budget=10)
                            except ValueError:
                                pass
                            else:
                                raise AssertionError("explicit SDK budget ignored")
                        group_rows = expanded["sources"]
                        print(json.dumps(records[-1]), flush=True)
                    if group == "poetry" and not args.policy_diagnostic:
                        # Distinct public error: no query truncation or full-pool fallback.
                        bad = await session.call_tool("get_docs_context", {
                            "question": "environment " * 140, "project_path": str(root), "scope": "project",
                        })
                        assert_operational_error(bad, "section_compression_query_limit", out / "query-overflow.json")
                        controls.append({"scenario": "query_overflow", "pass": True})
                        # Read capabilities from actual issued selected rows.
                        candidates = [r for r in group_rows if r.get("source_uri")]
                        assert len(candidates) >= 2
                        rr = await session.read_resource(candidates[0]["source_uri"])
                        value = json.loads(rr.contents[0].text)
                        save(out / "resource-read.json", value)
                        assert value.get("status") in ("complete", "truncated"), value
                        controls.append({"scenario": "issued_resource", "pass": True})
                        stale = candidates[-1]
                        target = root / stale["path_or_url"]
                        before = target.read_bytes()
                        try:
                            target.write_bytes(before + b"\nChanged after context delivery.\n")
                            rr = await session.read_resource(stale["source_uri"])
                            value = json.loads(rr.contents[0].text)
                            save(out / "changed-source.json", value)
                            assert value.get("status") in ("source_changed", "source_unavailable"), value
                            assert value.get("reason_code") in (
                                "source_policy_or_snapshot_changed", "snapshot_digest_mismatch"), value
                            assert not value.get("snippet"), value
                            controls.append({"scenario": "changed_source_rejected", "pass": True})
                        finally:
                            target.write_bytes(before)
        server = json.loads((out / "server.json").read_text())
        assert server["database_unchanged"]
        assert server["files_unchanged_before_revoke"] == server["files_after"]
        assert server["rss_peak_bytes"] <= 1_000_000_000
        assert len(server["observations"]) == len([c for c in cases if c["project_group"] == group])
    # Separate process: no engine cache can conceal missing local assets.
    group = "poetry"
    badwork, badout = args.work / "missing", args.out / "missing"
    badout.mkdir()
    params = StdioServerParameters(command=sys.executable, args=[
        "-I", str(Path(__file__).resolve()), "--worker", "--missing-model", "--family", group,
        "--repo", str(args.repo), "--work", str(badwork), "--out", str(badout),
        "--model", str(args.work / "absent-model"),
    ], env=dict(os.environ))
    with (badout / "stderr.log").open("w") as stderr:
        async with stdio_client(params, errlog=stderr) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.call_tool("get_docs_context", {
                    "question": next(c["question"] for c in cases if c["id"] == "V40-P03"),
                    "project_path": str(badwork / group / "project"), "scope": "project",
                })
                assert_operational_error(response, "section_compression_model_unavailable", badout / "missing-model.json")
    server = json.loads((badout / group / "server.json").read_text())
    assert server["database_unchanged"] and server["files_unchanged_before_revoke"] == server["files_after"]
    assert server["observations"] == []
    controls.append({"scenario": "missing_model_no_fallback", "pass": True})
    save(args.out / "DELIVERY.json", {"cases": records, "controls": controls,
                                     "public_calls": 81 if args.policy_diagnostic else 82,
                                     "preparations": 6, "resource_reads": 0 if args.policy_diagnostic else 2})
    return records, controls


def assess(args, records, controls):
    # Only now may the independent evaluator and answer annotations be opened.
    corpus, cases, families = dataset(args.repo)
    oracle = load_module("section_independent_oracle", corpus / "evaluate.py")
    gold = {c["id"]: c for c in json.loads((corpus / "gold_spans.json").read_text())["cases"]}
    families = {f["id"]: f for f in families}
    results = []
    for record in records:
        case = next(c for c in cases if c["id"] == record["case_id"])
        prepared = {"root": str(args.work / record["family"] / "project"), "sources": {}}
        for name in families[record["family"]]["paths"]:
            data = (corpus / "sources" / record["family"] / name).read_bytes()
            text, offsets = data.decode("utf-8"), [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared["sources"][name] = {"raw": data, "content": text, "sha256": sha(data),
                                         "line_offsets": offsets, "errors": []}
        payload = json.loads((args.out / record["family"] / (case["id"] + "-expanded.json")).read_text())
        verified, intervals, errors = oracle._source_rows(payload, prepared)
        coverage = oracle._gold(case, gold[case["id"]], prepared, intervals)
        valid = not errors and not coverage.get("errors")
        passed = valid and (not payload["sources"] if case["answerability"] == "unanswerable"
                            else coverage["all_documented_claims_covered"])
        cost_non_regression = record["cost"] <= record["same_payload_v1_cost"]
        results.append({**record, "answerability": case["answerability"],
                        "passed": passed, "integrity": valid, "coverage": coverage, "errors": errors,
                        "cost_non_regression": cost_non_regression})
    import statistics
    server_reports = [json.loads((args.out / family / "server.json").read_text()) for family in families]
    summary = {
        "head": os.environ.get("TESTED_SHA"),
        "top_k": args.top_k, "units": args.units, "policy_diagnostic_only": args.policy_diagnostic,
        "cases": len(results), "positive_pass": sum(r["passed"] for r in results if r["answerability"] == "within_budget"),
        "partial_pass": sum(r["passed"] for r in results if r["answerability"] == "partial"),
        "strict_empty_pass": sum(r["passed"] for r in results if r["answerability"] == "unanswerable"),
        "integrity_pass": sum(r["integrity"] for r in results),
        "model_view": args.model_view,
        "same_call_machine_tokens_mean": statistics.mean(r["same_call_machine_tokens"] for r in results),
        "tokens_mean": statistics.mean(r["tokens"] for r in results),
        "tokens_max": max(r["tokens"] for r in results),
        "baseline_tokens_mean": statistics.mean(r["baseline_tokens"] for r in results),
        "seconds_median": statistics.median(r["seconds"] for r in results),
        "server_rss_peak_bytes": max(r["rss_peak_bytes"] for r in server_reports),
        "container_memory_peak": max((r["container_memory_peak"] or 0) for r in server_reports),
        "controls": controls, "failed": [r["case_id"] for r in results if not r["passed"]],
        "cost_regressions": [r["case_id"] for r in results if not r["cost_non_regression"]],
        "boundary": "installed wheel; real SQLite; public stdio MCP; client-received bytes",
        "semantic_refusal_implemented": False,
    }
    summary["quality_gate_passed"] = all(r["passed"] for r in results if r["answerability"] != "unanswerable")
    summary["counts"] = {kind: {"total": sum(r["answerability"] == kind for r in results),
                                "pass": sum(r["passed"] for r in results if r["answerability"] == kind)}
                         for kind in sorted({r["answerability"] for r in results})}
    save(args.out / "ASSESSMENTS.json", results)
    save(args.out / "SUMMARY.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    assert all(r["integrity"] for r in results)
    if not args.policy_diagnostic:
        assert summary["quality_gate_passed"], "positive/partial quality gate"
    assert all(r["cost_non_regression"] for r in results), "emitted cost exceeds same-payload v1 diagnostic"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "work", "out", "model"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model-view", action="store_true")
    parser.add_argument("--top-k", type=int, choices=(1, 2, 3, 5), default=5)
    parser.add_argument("--units", choices=("legacy", "markdown-owner-v1"), default="legacy")
    parser.add_argument("--wire-format", choices=("v1", "adaptive-v2"), default="v1")
    parser.add_argument("--policy-diagnostic", action="store_true",
                        help="Report experimental quality FAIL without claiming acceptance; integrity remains mandatory")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--family")
    parser.add_argument("--missing-model", action="store_true")
    args = parser.parse_args()
    for key in ("repo", "work", "out", "model"):
        setattr(args, key, getattr(args, key).resolve())
    if args.worker:
        worker(args)
        return
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(args.repo), "must test the installed wheel"
    product = {str(p.relative_to(origin)): sha(p.read_bytes()) for p in origin.rglob("*.py")}
    assert all(sha((args.repo / "docmancer" / path).read_bytes()) == h for path, h in product.items())
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700)
    args.out.mkdir(parents=True)
    corpus, _, _ = dataset(args.repo)
    frozen = {str(p.relative_to(args.repo)): sha(p.read_bytes()) for p in corpus.rglob("*") if p.is_file()}
    save(args.out / "FREEZE.json", {"head": os.environ.get("TESTED_SHA"), "installed": product,
                                    "corpus": frozen, "model_path": str(args.model), "python": sys.version,
                                    "top_k": args.top_k, "units": args.units,
                                    "quality_claim": "diagnostic only" if args.policy_diagnostic else "regression gate"})
    records, controls = asyncio.run(client(args))
    assess(args, records, controls)
    assert all(sha((args.repo / path).read_bytes()) == h for path, h in frozen.items())


if __name__ == "__main__":
    main()
