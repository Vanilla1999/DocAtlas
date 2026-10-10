"""Same-index real MCP baseline/alias ablation; diagnostic, never release approval."""
from __future__ import annotations

import dataclasses
import gzip
import hashlib
import json
import socket
import sqlite3
import subprocess
import sys
import time
import types
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encode(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    if isinstance(value, Path):
        return str(value)
    return {"unserialized_type": type(value).__name__}


def index_digest(db):
    tables = []
    with sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True) as connection:
        for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            if name.startswith("sqlite_") or "fts" in name.casefold():
                continue
            rows = list(connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"'))
            material = sorted(json.dumps(row, default=lambda v: {"binary_sha256": digest(v)}, sort_keys=True) for row in rows)
            tables.append(dict(table=name, rows=len(rows), sha256=digest(json.dumps(material).encode())))
    return dict(tables=tables, sha256=digest(json.dumps(tables, sort_keys=True).encode()))


def main():
    from docmancer.docs.domain import project_retrieval_intent as intent

    # Keep the unaccepted local trust diff out of the published baseline.
    old = {name: value for name, value in vars(intent).items()
           if isinstance(value, types.FunctionType) and value.__module__ == intent.__name__}
    published = subprocess.check_output(["git", "show", "8d2381d8:docmancer/docs/domain/project_retrieval_intent.py"])
    exec(compile(published, intent.__file__, "exec"), vars(intent))
    for module in list(sys.modules.values()):
        if module and getattr(module, "__name__", "").startswith("docmancer."):
            for name, value in list(vars(module).items()):
                for old_name, old_fn in old.items():
                    if value is old_fn:
                        setattr(module, name, getattr(intent, old_name))
    from scripts import run_project_docs_self_host_gate as gate
    from docmancer.docs.application.model_visible_projection import estimate_projection_tokens

    data_path = ROOT / "eval/direct_docatlas_questions_15/cases.json"
    data = json.loads(data_path.read_text())
    cases = tuple(gate.LiveCase(case_id=c["id"], question=c["question"], scope="all", expected_kind="docs_context",
        relevant_paths=tuple(dict.fromkeys(w["path"] for g in c["fact_groups"] for w in g["witnesses"])),
        required_fact_groups=tuple(tuple((w["path"], w["text"]) for w in g["witnesses"]) for g in c["fact_groups"])) for c in data["cases"])
    original_call = gate._call_with_snapshot
    alias_builder = intent.build_project_retrieval_aliases
    alias_targets = [(module, name) for module in list(sys.modules.values())
                     if module and getattr(module, "__name__", "").startswith("docmancer.")
                     for name, value in list(vars(module).items()) if value is alias_builder]
    pairs, sockets = [], []
    snapshot = None
    stages = {"_run", "qualify_evidence", "rerank_project_doc_chunks", "select_context_candidates", "project_docs_context"}

    def observe(arguments, service):
        nonlocal snapshot
        before = index_digest(service.config.index.db_path)
        if snapshot is None:
            snapshot = before
        assert before == snapshot, "Index changed before paired call"
        outputs = {}
        for arm in ("published-baseline", "no-alias"):
            calls, events = [], []
            def builder(question):
                aliases = alias_builder(question) if arm == "published-baseline" else ()
                calls.append(dict(question=question, aliases=[encode(a) for a in aliases]))
                return aliases
            def profile(frame, event, result):
                if event == "return" and frame.f_code.co_name in stages and str(frame.f_globals.get("__name__", "")).startswith("docmancer."):
                    # Real return observation, never replay qualification.
                    events.append(dict(function=frame.f_code.co_name, module=frame.f_globals.get("__name__"),
                        query=frame.f_locals.get("query") or frame.f_locals.get("query_text"),
                        result=json.loads(json.dumps(result, default=encode))))
            previous = sys.getprofile()
            start = time.perf_counter()
            try:
                with ExitStack() as stack:
                    for module, name in alias_targets:
                        stack.enter_context(patch.object(module, name, builder))
                    sys.setprofile(profile)
                    payload, bound = original_call(arguments, service)
            finally:
                sys.setprofile(previous)
            elapsed = time.perf_counter() - start
            after = index_digest(service.config.index.db_path)
            assert before == after, "Paired index mutated"
            outputs[arm] = dict(payload=payload, snapshot=bound, events=events, alias_calls=calls,
                elapsed_instrumented_seconds=elapsed, serialized_tokens=estimate_projection_tokens({k: v for k, v in (payload or {}).items() if k != "diagnostics"}),
                citation_integrity=gate._citation_integrity(payload or {}, bound),
                index_sha256=after["sha256"])
        assert outputs["no-alias"]["alias_calls"], "Ablation did not reach alias builder"
        assert all(not c["aliases"] for c in outputs["no-alias"]["alias_calls"])
        pairs.append(dict(arguments=arguments, retrieval_config=encode(service.config.retrieval), arms=outputs))
        return outputs["published-baseline"]["payload"], outputs["published-baseline"]["snapshot"]

    def deny_socket(self, address):
        sockets.append(str(address))
        raise RuntimeError("P2 diagnostic forbids external connects")

    with patch.object(gate, "_call_with_snapshot", observe), patch.object(socket.socket, "connect", deny_socket), patch.object(socket.socket, "connect_ex", deny_socket):
        baseline_report = gate.run(cases=cases, negative_cases=())
    summaries = []
    for case, pair in zip(data["cases"], pairs, strict=True):
        result = dict(case_id=case["id"], question=case["question"], arms={})
        for arm, observed in pair["arms"].items():
            payload = observed["payload"] or {}
            facts = {}
            for group in case["fact_groups"]:
                facts[group["id"]] = any(w["text"].casefold() in str(s.get("snippet") or "").casefold()
                    and s.get("path_or_url") == w["path"] for w in group["witnesses"] for s in payload.get("sources", []) if isinstance(s, dict))
            result["arms"][arm] = dict(facts=facts, all_facts_delivered=all(facts.values()),
                citation_integrity=observed["citation_integrity"], sources=len(payload.get("sources", [])),
                serialized_tokens=observed["serialized_tokens"], kind=payload.get("kind"),
                answer_supported=payload.get("answer_supported"), edit_ready=payload.get("edit_ready"))
        result["lost_fact_groups"] = [g for g, passed in result["arms"]["published-baseline"]["facts"].items()
                                      if passed and not result["arms"]["no-alias"]["facts"][g]]
        summaries.append(result)
    source_pins = [{"path": p, "sha256": digest((ROOT / p).read_bytes())} for p in sorted(data["sources"])]
    report = dict(schema="p2-real-mcp-alias-ablation-v1", status="DIAGNOSTIC_NOT_P2_DONE", language_lane="EN-to-EN-original-only",
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        product_diff_sha256=digest(subprocess.check_output(["git", "diff", "--", "docmancer"])),
        published_intent_sha256=digest(published), runner_sha256=digest(Path(__file__).read_bytes()),
        cases_sha256=digest(data_path.read_bytes()), source_pins=source_pins, actual_index=snapshot,
        patched_alias_targets=[m.__name__ + "." + n for m, n in alias_targets],
        socket_attempts=sockets, with_vectors=False, model_calls=0, baseline_report=baseline_report,
        pairs=pairs, summaries=summaries,
        limitations=["Direct-15 current-source diagnostic, NOT official frozen-blob gate",
                     "EN same-language original-only; RU same-language/lookups/holdout pending",
                     "No-alias disables builder only; other semantic mechanisms remain",
                     "Stage returns saved but source-bound first-loss classification pending",
                     "Profiler includes overhead; paired production p95 not measured",
                     "Baseline arm always first; cache/order effect not controlled for SLA",
                     "Candidate third arm and adversarial/required controls pending"])
    output = BASE / "archives/p2-real-mcp-alias-ablation-v1.json.gz"
    output.write_bytes(gzip.compress(json.dumps(report, ensure_ascii=False, default=encode).encode(), mtime=0))
    print(json.dumps(dict(output=str(output), cases=len(summaries),
        baseline_full_facts=sum(s["arms"]["published-baseline"]["all_facts_delivered"] for s in summaries),
        no_alias_full_facts=sum(s["arms"]["no-alias"]["all_facts_delivered"] for s in summaries),
        cases_with_losses=[s["case_id"] for s in summaries if s["lost_fact_groups"]], sockets=sockets)))


if __name__ == "__main__":
    main()
