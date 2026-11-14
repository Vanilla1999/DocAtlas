"""Installed public-MCP Q6 measurement with an optional passive recorder.

Run with the installed environment's Python (or supply --python). Each run
performs one context read and, only for a new --work directory, one explicit
preparation. Reuse --work for every lane; --out must be a fresh directory.
The worker never opens the oracle. Only the parent checks the returned source
rows against independently frozen source quotations after the MCP call.

Raw responses, capability URIs, and observations stay in --out. summary.json
contains no absolute paths or live capabilities and is suitable for review.
An observed/unobserved pair can use --compare-to OUT to check exact wire parity.
No answering model or automatic model provisioning is part of this runner.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import nullcontext
from datetime import timedelta
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
QUESTION = "How does OpenCode compact delivery work, what size limits apply, and how is a delivery failure diagnosed?"


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def worker():
    """Every wrapper calls and returns the unmodified production function."""
    from docmancer.docs.application import joint_context_selection as joint
    from docmancer.core.sqlite_store import SQLiteStore

    observation = Path(os.environ["Q6_OBSERVATION_PATH"]) if os.environ.get("Q6_OBSERVATION_PATH") else None
    select, acquire = joint.select_joint_context, SQLiteStore.acquire_candidates

    def append(event):
        # Recorder failures are explicit, never a replacement product result.
        if observation is None:
            return
        try:
            with observation.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            print("Q6_OBSERVER_GAP:" + type(exc).__name__, file=sys.stderr)

    def observed_acquire(self, text, *args, **kwargs):
        chunks = acquire(self, text, *args, **kwargs)
        try:
            append({"event": "acquisition", "query": text, "rows": [
                {"rank": i, "text": chunk.text, "score": chunk.score,
                 "source": chunk.source, "metadata": chunk.metadata}
                for i, chunk in enumerate(chunks, 1)]})
        except Exception as exc:
            append({"event": "observer_gap", "stage": "acquisition", "error": type(exc).__name__})
        return chunks

    def observed_select(payload, snapshot, retrieval, *args, **kwargs):
        before = None
        try:
            before = json.loads(json.dumps({"sources": payload.get("sources"),
                "snapshot": snapshot, "query_plan": retrieval.get("documentation_query_plan")}, default=str))
        except Exception as exc:
            append({"event": "observer_gap", "stage": "selection_input", "error": type(exc).__name__})
        result = select(payload, snapshot, retrieval, *args, **kwargs)
        append({"event": "joint_selection", "before": before, "after": result[0],
                "diagnostics": retrieval.get("retrieval_diagnostics")})
        return result

    if observation is not None:
        joint.select_joint_context = observed_select
        SQLiteStore.acquire_candidates = observed_acquire
    scope = nullcontext()
    mode = os.environ.get("Q6_SELECTION_MODE", "lexical")
    if mode in {"body", "contextual"}:
        spec = importlib.util.spec_from_file_location("q6_contextual_relevance", HERE / "contextual_relevance.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        scope = module.installed_relevance(mode, observer=append)
    from docmancer.cli.__main__ import cli
    sys.argv = ["doc-atlas", "mcp", "docs-serve"]
    with scope:
        cli()


def helpers():
    spec = importlib.util.spec_from_file_location("q6_stdio_helpers", REPO / "eval/opencode_compat/installed_stdio.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_project(work):
    import yaml
    catalog_path = REPO / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    project = work / "project"
    names = [catalog_path.name, *(entry["path"] for entry in catalog["documents"])]
    frozen = json.loads((HERE / "FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    if set(names) != set(frozen["source_files"]):
        raise RuntimeError("Catalog membership differs from the frozen Q6 corpus")
    for name in names:
        if digest((REPO / name).read_bytes()) != frozen["source_files"][name]:
            raise RuntimeError("Repository source differs from the frozen Q6 corpus: " + name)
    if not project.exists():
        project.mkdir(parents=True)
        for name in names:
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
        for entry in catalog["documents"]:
            if entry.get("module_path"):
                (project / entry["module_path"]).mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in names:
        data = (project / name).read_bytes()
        if data != (REPO / name).read_bytes():
            raise RuntimeError("Frozen source mismatch: " + name)
        hashes[name] = digest(data)
    documents = {entry["path"]: (project / entry["path"]).read_text(encoding="utf-8")
                 for entry in catalog["documents"]}
    return project, catalog, documents, hashes


def validate_oracle(documents, case):
    oracle_bytes = (HERE / "oracle.json").read_bytes()
    frozen = json.loads((HERE / "FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    if digest(oracle_bytes) != frozen["oracle_sha256"]:
        raise RuntimeError("The frozen independent oracle changed")
    bundle = json.loads(oracle_bytes)
    oracle = bundle if case == "Q6" else bundle["regressions"][case]
    if case == "Q6" and oracle["question"] != QUESTION:
        raise RuntimeError("The frozen question changed")
    for fact in oracle["facts"]:
        text = documents[fact["path"]]
        lines = text.splitlines(keepends=True)
        excerpt = "".join(lines[fact["line_start"] - 1:fact["line_end"]])
        if fact["quote"] not in excerpt or text.count(fact["quote"]) != 1:
            raise RuntimeError("Frozen oracle mismatch: " + fact["id"])
    return oracle


def stable_rows(rows):
    """Identity-bound pool contents, excluding process-local capabilities."""
    fields = ("path_or_url", "section", "snippet", "line_start", "line_end",
              "scope", "version_binding", "authority", "instruction_trust", "content_sha256")
    return [{key: row.get(key) for key in fields} for row in rows]


def verify_and_score(payload, documents, catalog, oracle, helper):
    rows = helper.source_rows(payload)
    entries = {entry["path"]: entry for entry in catalog["documents"]}
    covered = {path: bytearray(len(text)) for path, text in documents.items()}
    checks = []
    for row in rows:
        path = row["path_or_url"]
        if path not in documents:
            raise AssertionError("Delivered source is outside frozen catalog")
        text = documents[path]
        lines = text.splitlines(keepends=True)
        start, end = row["line_start"], row["line_end"]
        if not (type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)):
            raise AssertionError("Invalid delivered line coordinates")
        section = "".join(lines[start - 1:end])
        snippet = row["snippet"]
        if not snippet or section.count(snippet) != 1:
            raise AssertionError("Delivered bytes do not match source coordinates")
        if row.get("authority") != entries[path]["authority"]:
            raise AssertionError("Delivered authority does not match catalog")
        if row.get("scope") != entries[path]["scope"]:
            raise AssertionError("Delivered scope does not match catalog")
        if row.get("version_binding") != "unversioned":
            raise AssertionError("Unexpected version binding")
        if not str(row.get("evidence_id", "")).startswith("ev-"):
            raise AssertionError("Missing evidence reference")
        if not str(row.get("source_uri", "")).startswith("docatlas://source/"):
            raise AssertionError("Missing source continuation")
        offset = sum(map(len, lines[:start - 1])) + section.index(snippet)
        covered[path][offset:offset + len(snippet)] = b"\1" * len(snippet)
        checks.append({"path": path, "line_start": start, "line_end": end,
                       "snippet_sha256": digest(snippet.encode()),
                       "content_sha256": row.get("content_sha256")})
    facts = []
    for fact in oracle["facts"]:
        start = documents[fact["path"]].index(fact["quote"])
        end = start + len(fact["quote"])
        facts.append({"id": fact["id"], "delivered": all(covered[fact["path"]][start:end])})
    return rows, checks, facts


def observation_summary(events, rows, documents):
    acquired = [event for event in events if event["event"] == "acquisition"]
    selected = [event for event in events if event["event"] == "joint_selection"]
    result = {"acquisitions": [], "selections": []}
    for event in acquired:
        pool = [{"rank": row["rank"], "text_sha256": digest(row["text"].encode()),
                 "score": row["score"], "path": (row.get("metadata") or {}).get("project_doc_path")}
                for row in event["rows"]]
        result["acquisitions"].append({"query": event["query"], "count": len(pool),
                                       "ordered_pool_sha256": digest(encode(pool))})
    delivered = {row["evidence_id"]: row for row in rows}
    all_checked = set()
    for event in selected:
        pool = event["before"]["sources"] or []
        snapshot = event["before"]["snapshot"]
        hashes_checked = 0
        for identity, row in delivered.items():
            if identity not in snapshot:
                continue
            source = snapshot[identity]["source"]
            material = {
                "path": source.get("path") or source.get("source") or source.get("url") or source.get("source_url"),
                "section": source.get("heading_path") or source.get("title"),
                "content": source.get("content") or source.get("display_text"),
                "snippet": source.get("snippet") or source.get("code"),
                "version": source.get("version_binding") or source.get("version") or source.get("requested_version"),
            }
            if digest(encode(material)) != row.get("content_sha256", snapshot[identity].get("content_sha256")):
                raise AssertionError("Delivered binding hash differs from original source material")
            for key in ("content", "snippet"):
                value = material[key]
                # Some sources keep a structured snippet description in the
                # binding. It is hashed in its original shape, not treated as
                # delivered evidence. Actual wire text was checked separately.
                if isinstance(value, str) and value and value not in documents[row["path_or_url"]]:
                    raise AssertionError("Hash-bound source material is not verbatim from the frozen file")
            hashes_checked += 1
            all_checked.add(identity)
        result["selections"].append({"checked_rows": len(pool),
            "ordered_pool_sha256": digest(encode(stable_rows(pool))),
            "raw_sources_sha256": digest(encode(pool)), "raw_snapshot_sha256": digest(encode(snapshot)),
            "delivered_binding_hashes_checked": hashes_checked,
            "query_plan_sha256": digest(encode(event["before"]["query_plan"]))})
    if selected and all_checked != set(delivered):
        raise AssertionError("Not every delivered source binding was verified from the recorded live snapshot")
    result["all_delivered_bindings_checked"] = all_checked == set(delivered) if selected else None
    return result


def tree_state():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()
    return {"commit": git("rev-parse", "HEAD"), "changed_paths": git("status", "--short").splitlines()}


def summarize(out, compare_to=None):
    """Read saved receipts only; never initialize MCP, prepare, or query."""
    import yaml
    helper = helpers()
    config = json.loads((out / "run-config.json").read_text(encoding="utf-8"))
    source_hashes = json.loads((out / "source-manifest.json").read_text(encoding="utf-8"))
    project = Path(config["environment"]["DOCATLAS_HOME"]).parent / "project"
    for name, expected in source_hashes.items():
        if digest((project / name).read_bytes()) != expected:
            raise AssertionError("Saved source manifest no longer matches prepared files")
    catalog = yaml.safe_load((project / "docatlas.project-docs.yaml").read_text(encoding="utf-8"))
    documents = {entry["path"]: (project / entry["path"]).read_text(encoding="utf-8")
                 for entry in catalog["documents"]}
    if config["oracle_sha256"] != digest((HERE / "oracle.json").read_bytes()):
        raise AssertionError("The frozen oracle changed after the recorded MCP call")
    oracle = validate_oracle(documents, config["case"])
    raw_reply = json.loads((out / "response.json").read_text(encoding="utf-8"))
    text = (out / "wire.txt").read_text(encoding="utf-8")
    if raw_reply.get("isError") or len(raw_reply["content"]) != 1 or raw_reply["content"][0]["text"] != text:
        raise AssertionError("Saved successful MCP text/receipt mismatch")
    packet = json.loads(text)
    if json.loads((out / "state-before.json").read_text()) != json.loads((out / "state-after.json").read_text()):
        raise AssertionError("Recorded context read changed indexed logical state")
    rows, checks, facts = verify_and_score(packet, documents, catalog, oracle, helper)
    events_path = out / "observation.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()] if events_path.exists() else []
    if (any(event.get("event") == "observer_gap" for event in events)
        or "Q6_OBSERVER_GAP:" in (out / "server.stderr").read_text(encoding="utf-8")):
        raise AssertionError("Observer dropped an event")
    observation = observation_summary(events, rows, documents)
    if config["observe"] and (not observation["acquisitions"] or not observation["selections"]):
        raise AssertionError("Incomplete observation; cannot claim checked-pool comparison")
    budget = helper.delivered_budget(text)
    budget["max_tokens_or_bytes_over_four"] = max(budget["o200k_tokens"], math.ceil(budget["utf8_bytes"] / 4))
    if budget["max_tokens_or_bytes_over_four"] > 12000:
        raise AssertionError("Actual MCP text exceeds unchanged delivery budget")
    parity = None
    if compare_to:
        parity = json.loads((compare_to.resolve() / "response.json").read_text(encoding="utf-8")) == raw_reply
    timing_file = out / "timing.json"
    seconds = json.loads(timing_file.read_text()).get("context_seconds") if timing_file.exists() else None
    ledger = json.loads((out / "calls.json").read_text(encoding="utf-8"))
    profile = config.get("profile", "compact" if config["environment"].get("DOCATLAS_MCP_COMPACT_TEXT") == "1" else "canonical")
    summary = {"boundary": "installed_public_stdio_mcp", "question": config["question"],
        "case": config["case"], "mode": config["mode"], "profile": profile,
        "observed": config["observe"], "scope": "unchanged default request; original catalog",
        "documents": len(documents), "catalog_sha256": source_hashes["docatlas.project-docs.yaml"],
        "oracle_sha256": config["oracle_sha256"], "recorded_harness_sha256": config["harness_sha256"],
        "evaluator_sha256": digest((HERE / "probe.py").read_bytes()),
        "calls": ledger, "seconds": seconds, "budget": budget,
        "source_rows": len(rows), "facts": facts, "delivered_facts": sum(f["delivered"] for f in facts),
        "source_fidelity": checks, "source_and_index_unchanged": True,
        "observation": observation, "exact_wire_parity": parity,
        "wire_sha256": digest(text.encode()), "delivered_rows_sha256": digest(encode(stable_rows(rows))),
        "status": packet.get("status"), "reason_code": packet.get("reason_code"),
        "answer_quality": "NOT_TESTED", "provider_usage": None}
    save(out / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in (
        "case", "mode", "profile", "observed", "calls", "seconds", "budget", "source_rows", "facts",
        "observation", "exact_wire_parity", "source_and_index_unchanged")}, ensure_ascii=False, indent=2))
    if parity is False:
        raise AssertionError("Observed and unobserved raw MCP responses differ")


async def run(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import docmancer
    helper = helpers()
    work, out = args.work.resolve(), args.out.resolve()
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=False)
    project, catalog, documents, source_hashes = prepare_project(work)
    oracle = validate_oracle(documents, args.case)
    question = oracle["question"]
    env = helper.environment(work)
    env.pop("DOCATLAS_MINILM_MODEL_DIR", None)  # No ambient optional model inheritance.
    env["DOCATLAS_CONTEXT_COMPRESSION"] = "off"
    if args.profile == "compact":
        env["DOCATLAS_MCP_COMPACT_TEXT"] = "1"
    if args.mode != "lexical":
        if args.model_dir is None or not args.model_dir.is_dir():
            raise ValueError("An explicit provisioned --model-dir is required for semantic modes")
        env.update(DOCATLAS_EXPERIMENT_JOINT_RELEVANCE="mini",
                   DOCATLAS_EXPERIMENT_MINI_PATH=str(args.model_dir.resolve()))
    env["Q6_SELECTION_MODE"] = args.mode
    if args.observe:
        env.update(Q6_OBSERVATION_PATH=str(out / "observation.jsonl"), DOCATLAS_TRACE="1")
    mutation, database = helper.prepared_mutation(env, project)
    need_prepare = not database.exists()
    use_worker = args.observe or args.mode in {"body", "contextual"}
    command_args = ["-I", str(HERE / "probe.py"), "--worker"] if use_worker else ["-I", "-m", "docmancer.cli", "mcp", "docs-serve"]
    params = StdioServerParameters(command=sys.executable, args=command_args, env=env, cwd=str(work))
    ledger = {"server_processes": 1, "initializations": 0, "list_tools": 0,
              "prepare_docs": 0, "get_docs_context": 0, "read_docs_source": 0,
              "answer_model_calls": 0}
    save(out / "source-manifest.json", source_hashes)
    save(out / "run-config.json", {"question": question, "case": args.case, "mode": args.mode,
        "profile": args.profile, "observe": args.observe,
        "environment": env, "executable": sys.executable, "package": docmancer.__file__,
        "oracle_sha256": digest((HERE / "oracle.json").read_bytes()),
        "harness_sha256": digest((HERE / "probe.py").read_bytes()),
        "contextual_relevance_sha256": digest((HERE / "contextual_relevance.py").read_bytes())
            if (HERE / "contextual_relevance.py").exists() else None,
        "git": tree_state()})
    before, packet, reply, text, seconds = None, None, None, None, None
    try:
        with (out / "server.stderr").open("w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as streams:
                async with ClientSession(*streams, read_timeout_seconds=timedelta(minutes=15)) as session:
                    ledger["initializations"] += 1
                    await session.initialize()
                    ledger["list_tools"] += 1
                    tool_catalog = await session.list_tools()
                    save(out / "tools.json", tool_catalog.model_dump(mode="json"))
                    if need_prepare:
                        ledger["prepare_docs"] += 1
                        prepared = await session.call_tool("prepare_docs", {
                            "action": "sync_project_docs", "project_path": str(project), "mutation": mutation})
                        save(out / "prepare.json", prepared.model_dump(mode="json"))
                        preparation, _ = helper.text_payload(prepared)
                        if preparation.get("status") != "success":
                            raise RuntimeError("Preparation failed; see prepare.json")
                    before = helper.state(database)
                    save(out / "state-before.json", before)
                    started = time.perf_counter()
                    ledger["get_docs_context"] += 1
                    reply = await session.call_tool("get_docs_context", {"project_path": str(project), "question": question})
                    seconds = time.perf_counter() - started
                    save(out / "timing.json", {"context_seconds": seconds})
                    save(out / "response.json", reply.model_dump(mode="json"))
                    packet, text = helper.text_payload(reply)
                    (out / "wire.txt").write_text(text, encoding="utf-8")
    finally:
        save(out / "calls.json", ledger)
        if before is not None:
            after = helper.state(database)
            save(out / "state-after.json", after)
            if before != after:
                raise AssertionError("Context read changed indexed logical state")
        for name, expected in source_hashes.items():
            if digest((project / name).read_bytes()) != expected:
                raise AssertionError("Context read changed a frozen source")
    if reply.isError:
        raise AssertionError("MCP context read failed; raw response retained")
    summarize(out, args.compare_to)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--python", type=Path, help="Installed environment interpreter; coordinator and worker both use it")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--observe", action="store_true")
    parser.add_argument("--case", choices=("Q6", "main-flow-Q1", "main-flow-Q9", "T01-en"), default="Q6")
    parser.add_argument("--mode", choices=("lexical", "mini", "body", "contextual"), default="lexical")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--profile", choices=("compact", "canonical"), default="compact")
    parser.add_argument("--compare-to", type=Path)
    parser.add_argument("--rescore", type=Path, help="Offline-only evaluation of saved OUT; no product calls")
    args = parser.parse_args()
    if args.worker:
        worker()
        return
    if args.python and os.path.abspath(str(args.python)) != os.path.abspath(sys.executable):
        command = [str(args.python), "-I", str(HERE / "probe.py"), *sys.argv[1:]]
        raise SystemExit(subprocess.call(command))
    if args.rescore:
        summarize(args.rescore.resolve(), args.compare_to)
        return
    if args.work is None or args.out is None:
        parser.error("--work and --out are required")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
