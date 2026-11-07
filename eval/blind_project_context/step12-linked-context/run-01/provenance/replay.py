"""Bounded live-acquisition replay, not fresh Qwen or final MCP acceptance.

Reuse the existing structural probe's passive return hook. Genuine public MCP
retrieval supplies live checked sources; saved actual Qwen scores supply only
selection input. The second fixture has an explicit component seed, not model
output. No scorer/retrieval/storage/validator is replaced. Run once per approved
checkpoint with a new --out directory; BLOCKED inventories are not repaired.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import yaml

from docmancer.docs.application import context_evidence_scoring as scorer
from docmancer.docs.application.context_evidence_structure import EvidenceDocuments
from docmancer.docs.application.experimental_context_finalization import project_native_rank_context, _rebuild
from docmancer.docs.application.minimal_context_selection import delivery_size, model_closure_receipt
from docmancer.docs.application.minimal_context_structure import (
    StructuralContextError, build_units, close_selection, recheck_structural_row,
)
from docmancer.docs.application.model_visible_projection import _refresh_estimate, _snapshot_entry, validate_model_visible_projection
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.mcp.docs_server import call_docs_tool_payload
from eval.evidence_quality_v2 import runtime
from eval.heuristic_removal.receipts import database, deadline, files, integrity, ledger, save, sha, snapshots
from .inputs import ROOT, COVERAGE, frozen_inputs, guard_inputs

BOUNDARY = "public in-process acquisition with live structural selection-input replay; not final public Qwen packet"
LIMITS = [
    "Seen development material; no fresh validation gate or model inference.",
    "Closure packets are reconstructed inside a passive same-call observer, not returned by the public Qwen route.",
    "Ordinary public packets are saved separately and never replaced by closure output.",
    "No issued source capabilities for reconstructed packets; no installed/stdio/client/answer-model acceptance.",
    "Token counts describe reconstructed document packets, not provider instructions/history/billing.",
]


class IncompleteReplay(Exception):
    pass


def unit_key(row):
    return row["path"], row["source_sha256"], row["char_start"], row["char_end"]


def stable_rows(packet):
    return sorted((r["path_or_url"], r["line_start"], r["line_end"], r["snippet"], r["scope"])
                  for r in packet.get("sources", ()))


def measure(packet, bound, retrieval, root, documents, modules, case):
    checked = integrity(packet, root, documents, modules)
    assert not checked["errors"], checked
    intervals = []
    for row in packet.get("sources", ()):
        entry = bound[row["evidence_id"]]
        ref = entry["source"]["_reference_evidence"]
        path = row["path_or_url"]
        start, end = ref["char_start"], ref["char_end"]
        assert path not in modules and row["scope"] == "project"
        assert ref["raw_document"] == documents[path]
        assert sha(documents[path].encode()) == ref["source"]["content_sha256"]
        assert row["snippet"] == documents[path][start:end]
        assert recheck_structural_row(row, entry, retrieval)["status"] == "complete"
        intervals.append((path, start, end))
    found = [i for i, fact in enumerate(case["facts"]) if any(
        path == fact["path"] and start <= fact["start"] and fact["end"] <= end
        for path, start, end in intervals)]
    errors = validate_model_visible_projection(packet, snapshot=bound)
    assert not errors, errors
    tokens = delivery_size(packet)
    assert tokens <= 50000, ("reconstructed_packet_emergency_limit", tokens)
    return dict(facts_found=len(found), facts_total=len(case["facts"]), fact_indices=found,
                delivered_rows=len(intervals), source_bytes=sum(len(r["snippet"].encode()) for r in packet.get("sources", ())),
                source_tokens=sum(projection_token_count(r["snippet"].encode()) for r in packet.get("sources", ())),
                reconstructed_packet_tokens=tokens, intervals=intervals, checked_rows=checked["rows"])


def replay_case(case, payload, snapshot, retrieval, root, documents, modules, counts, expired):
    structure = build_units(payload, snapshot, retrieval, recipe=scorer.STRUCTURAL_RECIPE)
    EvidenceDocuments(structure)  # Same checked pre-scoring context builder; no inference.
    def structure_digest():
        return sha(json.dumps(dict(metadata=structure.metadata, receipt=structure.receipt,
                                  units=[vars(unit) for unit in structure.units]), sort_keys=True).encode())
    original_structure = structure_digest()
    live = {unit_key(row): ident for ident, row in structure.metadata.items()}
    assert len(live) == len(structure.metadata), "ambiguous live unit identity"
    if "scores" in case:
        frozen = {unit_key(row): row for row in case["scores"]}
        assert len(frozen) == len(case["scores"]), "ambiguous frozen score identity"
        missing, unexpected = sorted(frozen.keys() - live.keys()), sorted(live.keys() - frozen.keys())
        if missing or unexpected:
            raise IncompleteReplay(json.dumps(dict(missing_frozen_units=missing, unexpected_live_units=unexpected)))
        selected = {live[key] for key, score in frozen.items() if score["score"] >= case["threshold"]}
        seed_kind = "actual_saved_qwen_scores_at_unchanged_frozen_threshold"
    else:
        path, start, end = case["component_seed"]
        matching = [ident for key, ident in live.items() if (key[0], key[2], key[3]) == (path, start, end)]
        if len(matching) != 1:
            raise IncompleteReplay("explicit component seed missing or ambiguous")
        selected = set(matching)
        seed_kind = "explicit_source_authored_component_input_not_model_selection"
    for key in live:
        assert key[0] in documents and key[0] not in modules
        assert sha(documents[key[0]].encode()) == key[1]
    result = dict(seed_kind=seed_kind, live_units=len(live), seed_units=len(selected),
                  structural_inputs_sha256=original_structure,
                  seeds=[{k: structure.metadata[i][k] for k in ("path", "source_sha256", "char_start", "char_end")}
                         for i in sorted(selected)], variants={})
    for variant in ("off", "one-hop-v1"):
        counts["closure_calls"] += 1
        rows, bound, closure = close_selection(structure, selected, payload, snapshot, retrieval,
                                                reference_expansion=variant)
        assert structure_digest() == original_structure, "closure mutated structural/scoring inputs"
        packet, bound = _rebuild(payload, bound, retrieval, rows, reason="structural_replay")
        bound = {r["evidence_id"]: {
            **_snapshot_entry(bound[r["evidence_id"]]["source"], r),
            **{k: bound[r["evidence_id"]][k] for k in ("structural_native_candidate", "structural_recipe")},
        } for r in packet.get("sources", ())}
        packet["source_selection"] = {"closure": model_closure_receipt(closure)}
        _refresh_estimate(packet)
        metrics = measure(packet, bound, retrieval, root, documents, modules, case)
        counts["structural_row_rechecks"] += metrics["delivered_rows"]
        if rows:
            row = packet["sources"][0]
            expired.append((row, bound[row["evidence_id"]], retrieval))
        result["variants"][variant] = dict(metrics=metrics, packet=packet, host_closure=closure)
    before, after = (result["variants"][v] for v in ("off", "one-hop-v1"))
    assert set(before["metrics"]["fact_indices"]) <= set(after["metrics"]["fact_indices"])
    assert set(map(tuple, before["metrics"]["intervals"])) <= set(map(tuple, after["metrics"]["intervals"]))
    if "historical_packet" in case:
        assert stable_rows(before["packet"]) == stable_rows(case["historical_packet"]), "baseline differs from saved exact Qwen rows"
    if case["no_answer"]:
        assert not selected and not before["packet"]["sources"] and not after["packet"]["sources"]
    if "forbidden" in case:
        assert after["metrics"]["facts_found"] == len(case["facts"]), "required guard source condition missing"
        for path, quote in case["forbidden"]:
            assert not any(r["path_or_url"] == path and quote in r["snippet"] for r in after["packet"]["sources"])
        refs = after["host_closure"]["reference_expansion"]["references"]
        for origin, target in case["pending"]:
            assert any(r["origin"] == origin and r["target"] == target and r["status"] == "pending" for r in refs), (origin, target, refs)
        assert any(r["target"] == "other.md#navigation-only" and r["navigation"] for r in refs)
        assert any(r["target"] == case["literal_html_target"] and r["origin"] == "selected_body"
                   and r["status"] == "included" for r in refs), "literal HTML target was rewritten or unresolved"
    return result


def run_group(name, documents, module_rows, cases, out, counts):
    target = out / name
    project = target / "project"
    runtime.write_project(project, documents)
    catalog = project / "docatlas.project-docs.yaml"
    data = yaml.safe_load(catalog.read_text())
    modules = {r["path"]: r for r in module_rows}
    for entry in data["documents"]:
        if entry["path"] in modules:
            entry.update(scope="module", module_path=modules[entry["path"]]["module_path"])
    catalog.write_text(yaml.safe_dump(data, sort_keys=False))
    results = []
    with runtime.isolated_service(target / "state") as (service, config):
        os.environ.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT="0", DOCATLAS_CONTEXT_LINKS="off",
                          DOCATLAS_CONTEXT_COMPRESSION="off")
        counts["public_prepares"] += 1
        ledger(out / "EXECUTION_LEDGER.jsonl", "prepare_docs", "started", group=name)
        with deadline(60):
            inventory = runtime.index_project(service, config, project)
        save(target / "preparation.json", inventory)
        save(target / "committed-sources.json", snapshots(inventory, project, documents))
        original_db, original_files = database(config.index.db_path), files(project)
        for case in cases:
            captured, expired = [], []
            observation = {"callbacks": 0, "errors": [], "blocked": []}

            def profile(frame, event, value):
                if event == "call" and frame.f_code.co_name in {"score_evidence_units", "score_complete_units"}:
                    counts["model_scorer_calls"] += 1
                if event != "return" or frame.f_code is not project_native_rank_context.__code__ or not value:
                    return
                observation["callbacks"] += 1
                try:
                    captured.append(replay_case(case, *value, frame.f_locals["retrieval"], project,
                                                documents, modules, counts, expired))
                except IncompleteReplay as exc:
                    observation["blocked"].append(str(exc))
                except Exception as exc:
                    observation["errors"].append(type(exc).__name__ + ": " + str(exc))

            request = dict(project_path=str(project), question=case["question"], scope="project")
            save(target / (case["id"] + "-request.json"), request)
            counts["public_contexts"] += 1
            ledger(out / "EXECUTION_LEDGER.jsonl", "get_docs_context", "started", case=case["id"])
            previous, started = sys.getprofile(), time.perf_counter()
            try:
                sys.setprofile(profile)
                with deadline(60):
                    public = call_docs_tool_payload("get_docs_context", request, service)
            finally:
                sys.setprofile(previous)
            assert not integrity(public, project, documents, modules)["errors"]
            for args in expired:
                counts["expired_provenance_checks"] += 1
                try:
                    recheck_structural_row(*args)
                except StructuralContextError:
                    pass
                else:
                    observation["errors"].append("expired structural provenance accepted")
            assert database(config.index.db_path) == original_db and files(project) == original_files
            status = ("FAIL" if observation["errors"] else "BLOCKED" if observation["blocked"] or
                      observation["callbacks"] != 1 or len(captured) != 1 else "PASS_STRUCTURAL_REPLAY_ONLY")
            result = dict(id=case["id"], status=status, seconds=time.perf_counter() - started,
                          public_packet=public, observation=observation, structural_replay=captured,
                          source_and_database_unchanged=True)
            save(target / (case["id"] + ".json"), result)
            ledger(out / "EXECUTION_LEDGER.jsonl", "get_docs_context", "returned", case=case["id"], status_result=status)
            save(out / "counts.json", counts)
            results.append(result)
    return results


def main(args):
    if not __debug__:
        raise ValueError("assertions required")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    documents, modules, cases, frozen_files = frozen_inputs()
    assert all(c["historical_receipt"]["recipe"] == scorer.RECIPE and
               c["historical_receipt"]["contract_sha256"] == scorer.CONTRACT_SHA256 for c in cases)
    guard_documents, guard_modules, guard_cases = guard_inputs()
    product = [ROOT / name for name in (
        "docmancer/docs/application/minimal_context_structure.py", "docmancer/docs/application/bounded_context_links.py",
        "docmancer/docs/application/minimal_context_selection.py", "docmancer/docs/application/context_evidence_scoring.py",
        "docmancer/docs/application/context_evidence_structure.py", "pyproject.toml", "uv.lock",
        "docmancer/docs/application/experimental_context_finalization.py", "eval/evidence_quality_v2/runtime.py",
        "eval/blind_project_context/probe_minimal_structure.py", "eval/heuristic_removal/receipts.py",
        "v2plan/STEP12_LINKED_CONTEXT_CHECKPOINT_RU.md")]
    paths = [*frozen_files, *product, Path(__file__), Path(__file__).with_name("inputs.py")]
    input_hashes = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in paths}
    counts = dict(public_prepares=0, public_contexts=0, resource_reads=0, model_scorer_calls=0,
                  closure_calls=0, structural_row_rechecks=0, expired_provenance_checks=0)
    manifest = dict(boundary=BOUNDARY, python=platform.python_version(),
                    source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    input_sha256=input_hashes, cases=[c["id"] for c in cases + guard_cases],
                    planned_counts=dict(public_prepares=2, public_contexts=5, resource_reads=0,
                                        model_scorer_calls=0, closure_calls=10),
                    guard_source_sha256={p: sha(raw.encode()) for p, raw in guard_documents.items()},
                    guard_inputs=guard_cases, coverage=COVERAGE, limitations=LIMITS)
    save(out / "execution-manifest.json", manifest)  # Before any prepare/query.
    results = []
    try:
        results.extend(run_group("meridian", documents, modules, cases, out, counts))
        results.extend(run_group("guard", guard_documents, guard_modules, guard_cases, out, counts))
        assert counts["model_scorer_calls"] == 0
        assert counts["public_prepares"] == 2 and counts["public_contexts"] == 5
        assert all(sha((ROOT / path).read_bytes()) == digest for path, digest in input_hashes.items())
        status = "FAIL" if any(r["status"] == "FAIL" for r in results) else (
            "BLOCKED" if any(r["status"] == "BLOCKED" for r in results) else "PASS_STRUCTURAL_REPLAY_ONLY")
        summary = dict(status=status, boundary=BOUNDARY, counts=counts, coverage=COVERAGE,
                       results=[{k: r[k] for k in ("id", "status", "seconds", "observation")} for r in results],
                       metrics={r["id"]: {v: value["metrics"] for v, value in r["structural_replay"][0]["variants"].items()}
                                for r in results if r["structural_replay"]}, limitations=LIMITS)
        save(out / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if status == "PASS_STRUCTURAL_REPLAY_ONLY" else 2
    except BaseException as exc:
        save(out / "failure.json", dict(status="FAIL_NOT_PASS", error=repr(exc), counts=counts))
        raise
    finally:
        save(out / "counts.json", counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New isolated result/fixture directory")
    raise SystemExit(main(parser.parse_args()))
