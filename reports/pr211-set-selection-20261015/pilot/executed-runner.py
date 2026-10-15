"""Installed-wheel A/D integration pilot; one attempt, no prompt repair.

The approved OpenCode stateless host receives only public frozen source windows.
No host session, tools, repository instructions, or oracle enter its prompt.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time


REPO = Path(__file__).resolve().parents[2]
CORPUS = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.site.resolve()))
    # Real storage policy disallows group-writable /tmp/opencode ancestors.
    os.environ["TMPDIR"] = "/tmp"
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.docs.application import experimental_set_selection as selection
    from docmancer.docs.application.experimental_candidate_selection import experimental_selection_observer
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    for name in ("experimental_set_selection.py", "experimental_context_finalization.py"):
        installed = Path(selection.__file__).with_name(name)
        assert installed.is_relative_to(args.site.resolve())
        assert installed.read_bytes() == (REPO/"docmancer/docs/application"/name).read_bytes()
    if args.run_dir.exists() or args.work_dir.exists():
        raise ValueError("new run and work directories required; never overwrite or retry")
    args.run_dir.mkdir(parents=True)
    args.work_dir.mkdir(parents=True)
    out = args.run_dir
    runtime = load("set_fixture", REPO/"eval/evidence_quality_v2/runtime.py")
    helpers = load("set_helpers", CORPUS/"run.py")
    cases = [c for c in json.loads((CORPUS/"questions.json").read_text())["cases"]
             if c["id"] in {"V40-P03", "V40-E01"}]
    families = {f["id"]: f for f in json.loads((CORPUS/"source_plan.json").read_text())["families"]}
    frozen = {str(p.relative_to(CORPUS)): sha(p.read_bytes())
              for p in CORPUS.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    config = selection.SetSelectorConfig(
        model_id="openai/gpt-5.6-luna#medium",
        runtime="OpenCode stateless /api/experimental/generate; openai provider",
    )
    save(out/"MANIFEST.json", {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "product_hashes": {name: sha((REPO/"docmancer/docs/application"/name).read_bytes())
                           for name in ("experimental_set_selection.py", "experimental_context_finalization.py")},
        "config": config.__dict__, "corpus_hashes": frozen,
        "boundary": "installed wheel, in-process public MCP, real isolated SQLite",
        "host": {"endpoint": "https://chatgpt.com/backend-api/codex",
                 "model_id": "gpt-5.6-luna", "providerID": "openai", "variant": "medium",
                 "context_limit_configured": 400000, "input_limit_configured": 272000,
                 "output_limit_configured": 128000, "sampling": "provider default/unknown",
                 "transport_output_cap": "not exposed by stateless API; 8192 is context reserve only",
                 "billing_tokens": "not exposed by stateless API",
                 "backend_retries": "not exposed; client retries 0"},
        "limits": {"preparations": 2, "context_calls": 4, "host_attempts": 2,
                   "host_timeout_seconds": 180, "automatic_retries": 0},
        "method": "prompted baseline inspired by SetR 3.2/5.3; no training or emitted CoT; full pool, JSON IDs",
    })
    (out/"PROMPT.txt").write_text(selection.PROMPT)
    results = []

    def ledger(operation, **details):
        with (out/"ledger.jsonl").open("a") as handle:
            handle.write(json.dumps({"operation": operation, **details}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    for case in cases:
        case_id, group = case["id"], case["project_group"]
        case_out = out/case_id
        case_out.mkdir()
        root = args.work_dir/group
        documents = {p: (CORPUS/"sources"/group/p).read_text() for p in families[group]["paths"]}
        runtime.write_project(root, documents)
        print("PREPARE " + case_id, flush=True)
        with runtime.isolated_service(args.work_dir/"state"/group) as (service, settings):
            ledger("prepare", case=case_id)
            with helpers.time_limit(180):
                inventory = runtime.index_project(service, settings, root)
            with sqlite3.connect(inventory["storage_path"]) as db:
                snapshots = [{"path": str(Path(source).relative_to(root)), "sha256": sha(content.encode())}
                             for source, content in db.execute(
                                 "SELECT source, content FROM generation_sources WHERE generation_id=?",
                                 (inventory["generation_id"],))]
            assert {s["path"]: s["sha256"] for s in snapshots} == {p: sha(t.encode()) for p,t in documents.items()}
            save(case_out/"preparation.json", {"root": str(root), "inventory": inventory, "snapshots": snapshots})
            before = helpers.logical_state(inventory), helpers.source_state(root)
            request = {"question": case["question"], "project_path": str(root), "scope": "project"}
            save(case_out/"request.json", request)

            def generate(prompt):
                body = {"prompt": prompt, "model": {"id": "gpt-5.6-luna", "providerID": "openai", "variant": "medium"}}
                save(case_out/"host-request.json", body)
                ledger("host_attempt", case=case_id)
                completed = subprocess.run(
                    ["opencode", "api", "post", "/api/experimental/generate", "--data", json.dumps(body, ensure_ascii=False)],
                    capture_output=True, timeout=180,
                )
                (case_out/"host-stdout.bin").write_bytes(completed.stdout)
                (case_out/"host-stderr.bin").write_bytes(completed.stderr)
                if completed.returncode:
                    raise RuntimeError("host transport failed")
                return json.loads(completed.stdout)["data"]["text"]

            packets, traces, metadata = {}, {}, {}
            receipts = []
            for arm in ("A", "D"):
                observations = []
                started = time.perf_counter()
                manager = (selection.experimental_set_selector(generate, config=config)
                           if arm == "D" else nullcontext([]))
                ledger("context_attempt", case=case_id, arm=arm)
                with manager as records, experimental_selection_observer(observations.append) as observer:
                    with helpers.time_limit(210):
                        packet = call_docs_tool_payload("get_docs_context", request, service)
                if arm == "D":
                    receipts = records
                    save(case_out/"selector-receipts.json", receipts)
                wire = json.dumps(packet, ensure_ascii=False).encode()
                (case_out/(arm+"-dto.json")).write_bytes(wire)
                packets[arm] = packet
                traces[arm] = [{key: observation[key] for key in ("pool", "excluded", "complete_candidates")}
                               for observation in observations]
                metadata[arm] = {"seconds": time.perf_counter()-started, "dto_tokens": projection_token_count(wire),
                                 "dto_bytes": len(wire), "source_count": len(packet.get("sources") or []),
                                 "observer_errors": observer.errors,
                                 "state_unchanged": before == (helpers.logical_state(inventory), helpers.source_state(root))}
                print(case_id, arm, json.dumps(metadata[arm]), flush=True)
            save(case_out/"metadata.json", metadata)
            # Independent immutable oracle is opened only after this pair is saved.
            evaluator = load("set_offline_evaluator", CORPUS/"evaluate.py")
            gold = json.loads((CORPUS/"gold_spans.json").read_text())["cases"]
            if isinstance(gold, list):
                gold = {c["id"]: c for c in gold}
            sources = {}
            for relative, content in documents.items():
                offsets = [0]
                for line in content.splitlines(keepends=True):
                    offsets.append(offsets[-1]+len(line))
                sources[relative] = {"content": content, "raw": content.encode(), "sha256": sha(content.encode()),
                                     "line_offsets": offsets, "errors": []}
            prepared = {"root": str(root), "sources": sources}
            for arm, packet in packets.items():
                verified, intervals, errors = evaluator._source_rows(packet, prepared)
                oracle = evaluator._gold(case, gold[case_id], prepared, intervals)
                parts = [p for claim in oracle["claims"] for witness in claim["witness_sets"] for p in witness["parts"]]
                metadata[arm].update(source_errors=errors, oracle_errors=oracle["errors"],
                                     coverage=[{"covered": p["covered_characters"], "expected": p["expected_characters"]} for p in parts],
                                     oracle_pass=oracle["all_documented_claims_covered"] and not errors and not oracle["errors"])
                save(case_out/(arm+"-assessment.json"), {"verified_sources": verified, "oracle": oracle, "source_errors": errors})
            baseline = packets["A"].get("sources") or []
            expected_windows = [{"id": f"w{i}", "path": r.get("path_or_url"), "section": r.get("section"), "text": r["snippet"]}
                                for i,r in enumerate(baseline)]
            same_pool = (len(receipts) == 1 and expected_windows == receipts[0]["windows"]
                         and [r["evidence_id"] for r in baseline] == receipts[0]["evidence_ids"]
                         and len(traces["A"]) == len(traces["D"]) == 1 and traces["A"] == traces["D"])
            delivered = packets["D"].get("sources") or []
            selected = receipts[0].get("selected_evidence_ids", []) if receipts else []
            exact_delivery = set(selected) == {r["evidence_id"] for r in delivered}
            baseline_by_id = {r["evidence_id"]: r for r in baseline}
            immutable = all(r == baseline_by_id.get(r["evidence_id"]) for r in delivered)
            passed = (same_pool and exact_delivery and immutable
                      and receipts[0]["status"] == "selected"
                      and all(m["oracle_pass"] and m["state_unchanged"] and not m["observer_errors"] for m in metadata.values())
                      and metadata["D"]["dto_tokens"] < metadata["A"]["dto_tokens"])
            results.append({"case_id": case_id, "arms": metadata, "same_pool": same_pool,
                            "exact_delivery": exact_delivery, "immutable_rows": immutable,
                            "selector": {k:v for k,v in (receipts[0] if receipts else {}).items()
                                         if k not in {"prompt", "windows", "evidence_ids", "raw_response"}}, "pass": passed})
            save(out/"RESULTS.json", results)
            assert all(sha((CORPUS/p).read_bytes()) == digest for p,digest in frozen.items())
            if not passed:
                print("STOP: pilot FAIL; no retries or V40", flush=True)
                return 1
    print("Both pilot cases PASS; V40 requires the subsequent frozen runner", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
