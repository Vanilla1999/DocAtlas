"""Extend the existing installed-MCP scenario, not the product or its scorers.

All comparison requests use real native reads, SQLite and installed ONNX models.
Source equality and expected witnesses are checked after all delivered responses.
"""
from __future__ import annotations
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location("installed_coverage_scenario", Path(__file__).with_name("coverage_selection_integration.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
# Reuse the existing client/server scenario but dispatch children through this
# evaluator's CLI (which recognizes the additional experiment policies/suite).
base.__file__ = __file__
_original_inputs = base.inputs


def inputs(args):
    if args.suite != "preservation8":
        return _original_inputs(args)
    value = json.loads((args.repo / "eval/semantic_preservation_holdout/inputs.json").read_text())
    return value["cases"], {f["id"]: f["documents"] for f in value["families"]}


base.inputs = inputs


def assess_new(args, records):
    # Independent exact-span oracle accepts alternative ORIGINAL witnesses only.
    # It does not consume NLI decisions or generate expected claims from them.
    cases, families = inputs(args)
    oracle = base.load("independent_span_oracle", args.repo / "eval/prepared_model_comparison40/evaluate.py")
    gold = {c["id"]: c for c in json.loads((args.repo / "eval/semantic_preservation_holdout/gold.json").read_text())["cases"]}
    for row in records:
        g = gold[row["case_id"]]
        row["answerability"] = g["answerability"]
        if row["runtime_error"]:
            row.update(passed=False, integrity=False, claims=[]); continue
        prepared = {"root": str(args.work / row["family"] / "project"), "sources": {}}
        for path, text in families[row["family"]].items():
            offsets = [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared["sources"][path] = {"raw": text.encode(), "content": text, "sha256": base.digest(text.encode()), "line_offsets": offsets, "errors": []}
        payload = json.loads((args.out / row["family"] / (row["case_id"] + "-expanded.json")).read_text())
        _, intervals, errors = oracle._source_rows(payload, prepared)
        claims = []
        for claim in g["claims"]:
            alternatives = []
            for witness_set in claim["witness_sets"]:
                covered = []
                for w in witness_set:
                    raw = prepared["sources"][w["path"]]["content"]
                    assert raw.count(w["text"]) == 1
                    a = raw.index(w["text"])
                    covered.append(not oracle._uncovered(a, a + len(w["text"]), intervals.get(w["path"], [])))
                alternatives.append(bool(covered) and all(covered))
            claims.append({"id": claim["id"], "covered": any(alternatives)})
        row.update(claims=claims, integrity=not errors, errors=errors,
                   passed=not errors and (not payload["sources"] if g["answerability"] == "unanswerable" else all(c["covered"] for c in claims)))
    base.save(args.out / "ASSESSMENTS.json", records)
    summary = {"head": os.environ["TESTED_SHA"], "suite": args.suite, "policy": args.policy,
        "cases": len(records), "runtime_errors": sum(r["runtime_error"] for r in records),
        "integrity_errors": sum(not r["integrity"] for r in records),
        "required_facts": sum(len(r["claims"]) for r in records),
        "retained_facts": sum(c["covered"] for r in records for c in r["claims"]),
        "model_visible_tokens": sum(r.get("tokens", 0) for r in records),
        "seconds_total": sum(r["seconds"] for r in records),
        "counts": {k: {"total": sum(r["answerability"] == k for r in records),
            "passed": sum(r["answerability"] == k and r["passed"] for r in records)}
            for k in ("within_budget", "partial", "unanswerable")},
        "provider_usage": None, "answer_model_calls": 0}
    base.save(args.out / "SUMMARY.json", summary)
    assert not summary["runtime_errors"] and not summary["integrity_errors"]


def main():
    p = argparse.ArgumentParser()
    for name in ("repo", "work", "out", "model", "qa-model"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--suite", choices=("v40", "new16", "fresh8", "semantic12", "preservation8"), required=True)
    p.add_argument("--policy", choices=("facet-guarded-v1", "semantic-exact-prune-v1", "semantic-nli-prune-v1", "semantic-rescue-v1"), required=True)
    p.add_argument("--worker", action="store_true"); p.add_argument("--family")
    args = p.parse_args()
    for name in ("repo", "work", "out", "model", "qa_model"):
        setattr(args, name, getattr(args, name).resolve())
    if args.worker:
        return base.worker(args)
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(args.repo)
    assert all(f.read_bytes() == (args.repo / "docmancer" / f.relative_to(origin)).read_bytes() for f in origin.rglob("*.py"))
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700); args.out.mkdir(parents=True)
    dirs = ("prepared_model_comparison40", "adaptive_gap_holdout", "fresh_dialogues/fixtures", "fresh_dialogues/oracle", "semantic_sufficiency_holdout", "semantic_preservation_holdout")
    hashes = {str(f.relative_to(args.repo)): base.digest(f.read_bytes()) for d in dirs
              for f in (args.repo / "eval" / d).rglob("*") if f.is_file() and "__pycache__" not in f.parts}
    base.save(args.out / "FREEZE.json", {"head": os.environ["TESTED_SHA"], "files": hashes})
    records = asyncio.run(base.client(args))
    if args.suite == "preservation8":
        assess_new(args, records)
    else:
        base.assess(args, records)
    observations = [o["semantic_sufficiency"] for family in inputs(args)[1]
        for o in json.loads((args.out / family / "server.json").read_text())["observations"] if o.get("semantic_sufficiency")]
    base.save(args.out / "CHECKER.json", {"observations": observations,
        "model_pairs": sum(o.get("model_pairs", 0) for o in observations),
        "removed_groups": sum(o.get("removed_groups", 0) for o in observations),
        "added_groups": sum(o.get("added_groups", 0) for o in observations),
        "unknown_mutations": sum(o.get("status") == "unknown" and bool(o.get("added_groups") or o.get("removed_groups")) for o in observations)})
    assert all(not (o.get("added_groups") or o.get("removed_groups")) for o in observations if o.get("status") == "unknown")
    assert all(base.digest((args.repo / f).read_bytes()) == h for f, h in hashes.items())


if __name__ == "__main__":
    main()
