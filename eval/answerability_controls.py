"""Independent installed stdio controls; no V40 labels or mocked components.

Each scenario has its own process/config and real catalog preparation. Only the
client knows the expected behavior. Russian checks unknown/pass-through, NOT
Russian semantic accuracy. New QA source is independent of V40.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from datetime import timedelta
import resource

sys.path.insert(0, str(Path(__file__).parent))
from answerability_integration import module, save, sha

DOCUMENT = '''# Aster Service

## Network

Aster listens on port 8127. Enable TLS by setting transport = "tls".

## Refresh

The refresh interval is 17 seconds. Set refresh_enabled = false to disable refresh.
'''
SCENARIOS = {
    "positive": ("What port does Aster listen on?", "en", "enforce"),
    "absent": ("Who founded Aster?", "en", "enforce"),
    "observe_only": ("Who founded Aster?", "en", "observe"),
    "unknown_language": ("Какой порт использует Aster?", "ru", "enforce"),
    "missing_model": ("What port does Aster listen on?", "en", "enforce"),
    # The original long query matched no source and never reached QA. Keep that
    # real boundary as its own case; use source-matching words for QA overflow.
    "no_candidates": ("configuration " * 90, "en", "enforce"),
    "long_query": ("What port does Aster listen on? " * 15, "en", "enforce"),
}


def worker(args):
    from docmancer.mcp._docs_server_part01 import _run_async, call_docs_tool_payload
    from docmancer.docs.application.answerability import observe_answerability
    runtime = module("answerability_control_fixture", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = module("answerability_control_helpers", args.repo / "eval/prepared_model_comparison40/run.py")
    root = args.work / "project"
    runtime.write_project(root, {"README.md": DOCUMENT})
    with runtime.isolated_service(args.work / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        before = helper.logical_state(inventory), helper.source_state(root)
        question, language, mode = SCENARIOS[args.scenario]
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="off", DOCATLAS_CONTEXT_ABSTENTION="off",
                          DOCATLAS_MCP_TEXT_FALLBACK="1", HF_HUB_OFFLINE="1")
        request = {"question": question, "project_path": str(root), "scope": "project"}
        baseline = call_docs_tool_payload("get_docs_context", request, service)
        save(args.out / "baseline.json", baseline)
        if args.scenario == "long_query":
            assert baseline.get("sources"), "QA overflow control must reach the checked-source boundary"
        os.environ.update(DOCATLAS_CONTEXT_ABSTENTION=mode, DOCATLAS_ABSTENTION_LANGUAGE=language,
                          DOCATLAS_ABSTENTION_MODEL_DIR=str(args.qa_model if args.scenario != "missing_model" else args.work / "missing"))
        with observe_answerability() as receipts:
            try:
                asyncio.run(_run_async(service))
            finally:
                save(args.out / "server.json", {"observations": receipts, "state_unchanged": before == (helper.logical_state(inventory), helper.source_state(root)),
                    "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)})


async def client(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    results = []
    for name, (question, language, mode) in SCENARIOS.items():
        work, out = args.work / name, args.out / name
        out.mkdir(parents=True)
        params = StdioServerParameters(command=sys.executable, args=["-I", str(Path(__file__).resolve()),
            "--worker", "--scenario", name, "--repo", str(args.repo), "--work", str(work),
            "--out", str(out), "--qa-model", str(args.qa_model)], env=dict(os.environ))
        with (out / "stderr.log").open("w") as err:
            async with stdio_client(params, errlog=err) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
                    await session.initialize()
                    response = await session.call_tool("get_docs_context", {"question": question,
                        "project_path": str(work / "project"), "scope": "project"})
                    raw = response.content[0].text
                    (out / "wire.json").write_text(raw, encoding="utf-8")
                    payload = json.loads(raw)
        baseline = json.loads((out / "baseline.json").read_text())
        server = json.loads((out / "server.json").read_text())
        code = (payload.get("error") or {}).get("reason_code")
        if name == "missing_model":
            passed = response.isError and code == "answerability_model_unavailable_or_corrupt" and not payload.get("sources")
        elif name == "long_query":
            passed = response.isError and code == "answerability_query_limit" and not payload.get("sources")
        elif name == "absent":
            passed = not response.isError and payload.get("reason_code") == "answer_not_found_in_acquired_context" and payload.get("sources") == [] and not payload.get("read_next")
        elif name == "no_candidates":
            passed = not response.isError and payload == baseline and not payload.get("sources") and server["observations"] == []
            passed = passed and payload.get("reason_code") != "answer_not_found_in_acquired_context"
        else:
            passed = not response.isError and payload == baseline and bool(payload.get("sources"))
            if name == "positive":
                passed = passed and any("8127" in r["snippet"] for r in payload["sources"])
            if name == "unknown_language":
                passed = passed and server["observations"][0]["decision"] == "unknown" and not server["observations"][0]["scan_complete"]
        passed = bool(passed and server["state_unchanged"])
        results.append({"scenario": name, "pass": passed, "reason_code": code or payload.get("reason_code"),
                        "rss_peak_bytes": server["rss_peak_bytes"], "observations": server["observations"]})
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    save(args.out / "SUMMARY.json", {"head": os.environ.get("TESTED_SHA"), "platform": sys.platform,
        "python": sys.version, "results": results, "public_calls": 2 * len(SCENARIOS), "preparations": len(SCENARIOS),
        "boundary": "installed wheel; real stdio MCP; independent synthetic source; no mocked model",
        "russian_semantic_accuracy": "NOT CLAIMED: unsupported-language pass-through only"})
    assert all(r["pass"] for r in results), "answerability controls failed"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("repo", "work", "out", "qa-model"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--scenario", choices=SCENARIOS)
    args = p.parse_args()
    for key in ("repo", "work", "out", "qa_model"):
        setattr(args, key, getattr(args, key).resolve())
    if args.worker:
        worker(args)
        return
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(args.repo)
    product = {str(p.relative_to(origin)): sha(p.read_bytes()) for p in origin.rglob("*.py")}
    assert all(sha((args.repo / "docmancer" / path).read_bytes()) == h for path, h in product.items())
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700)
    args.out.mkdir(parents=True)
    save(args.out / "FREEZE.json", {"head": os.environ.get("TESTED_SHA"), "product": product,
        "document_sha256": sha(DOCUMENT.encode()), "scenarios": SCENARIOS,
        "model": json.loads((args.qa_model / "manifest.json").read_text())})
    asyncio.run(client(args))


if __name__ == "__main__":
    main()
