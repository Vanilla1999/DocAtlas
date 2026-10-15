"""Offline immutable historical scoring; no product calls, no oracle rewriting.

The original evaluator functions are reused verbatim for historical60. New D's
published byte-witness schema is consumed only offline after freeze; never infer gold.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import save, sha


def assess(manifest_path, run_dir, output):
    if output.exists():
        raise ValueError("fresh assessment output required")
    manifest = json.loads(manifest_path.read_bytes())
    for name, digest in manifest["inputs_sha256"].items():
        if sha(Path(name).read_bytes()) != digest:
            raise ValueError("frozen source/oracle/code changed: " + name)
    evaluator_path = Path(__file__).resolve().parents[1] / "prepared_model_comparison40/evaluate.py"
    spec = importlib.util.spec_from_file_location("frozen_historical_evaluation", evaluator_path)
    historical = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(historical)
    records = []
    for dataset_index, dataset in enumerate(manifest["config"]["datasets"]):
        directory = Path(dataset["path"]).resolve()
        is_new = dataset_index == 2
        cases = json.loads((directory / ("sealed/questions.json" if is_new else "questions.json")).read_bytes())["cases"]
        if is_new and dataset.get("oracle_schema") != "D_literal_byte_witness_sets_v1":
            raise ValueError("new20 schema differs from D published interface")
        oracles = {case["id"]: case for case in json.loads((directory / (
            "sealed/oracle.json" if is_new else "gold_spans.json")).read_bytes())["cases"]}
        for arm in dataset["arms"]:
            lane = run_dir / arm
            for case in cases:
                candidates = [run_dir / name for name in manifest.get("recovery_lanes", {}).get(arm, [arm])]
                lane = next((candidate for candidate in candidates if (
                    candidate / "calls" / str(dataset_index) / case["id"] / arm / "public-payload.json"
                ).exists()), run_dir / arm)
                destination = lane / "calls" / str(dataset_index) / case["id"] / arm
                payload_path = destination / "public-payload.json"
                if not payload_path.exists():
                    records.append(dict(dataset=dataset_index, case_id=case["id"], arm=arm, status="NOT_RETURNED"))
                    continue
                preparation = json.loads((lane / "preparation" / f'{dataset_index}-{case["project_group"]}.json').read_bytes())
                sources = {}
                corpus_root = directory / ("corpus" if is_new else "sources") / case["project_group"]
                for source in corpus_root.rglob("*"):
                    if not source.is_file():
                        continue
                    raw = source.read_bytes()
                    text = raw.decode()
                    offsets = [0]
                    for line in text.splitlines(keepends=True):
                        offsets.append(offsets[-1] + len(line))
                    sources[source.relative_to(corpus_root).as_posix()] = dict(
                        content=text, raw=raw, line_offsets=offsets, sha256=sha(raw), errors=[])
                prepared = dict(root=preparation["root"], sources=sources)
                metadata = json.loads((destination / "metadata.json").read_bytes())
                row = dict(dataset=dataset_index, case_id=case["id"], arm=arm, status="returned",
                           answerability=case.get("answerability"), seconds=metadata["seconds"],
                           answer_quality="NOT MEASURED", unsupported_generated_claims="NOT MEASURED",
                           semantic_sufficiency="NOT MEASURED: independent label-hidden review required")
                row["read_only_pass"] = metadata.get("database_unchanged") is True and metadata.get("files_unchanged") is True
                row["runtime_integrity_errors"] = metadata.get("integrity_errors", [])
                for name in ("native", "packed"):
                    path = payload_path if name == "native" else destination / "packed.json"
                    if not path.exists():
                        row[name] = dict(status="MISSING_RECEIPT", integrity_errors=["packing_or_payload_receipt_missing"])
                        continue
                    payload = json.loads(path.read_bytes())
                    verified, intervals, errors = historical._source_rows(payload, prepared)
                    coverage = new_coverage(case, oracles[case["id"]], prepared, payload, verified) if is_new else historical._gold(
                        case, oracles[case["id"]], prepared, intervals)
                    negative = case.get("answerability") == ("negative" if is_new else "unanswerable")
                    errors = list(errors) + list(coverage.get("errors", []))
                    valid = not errors and row["read_only_pass"] and not row["runtime_integrity_errors"]
                    documented_pass = coverage.get("all_required_facts_covered" if is_new else "all_documented_claims_covered")
                    row[name] = dict(exact_frozen_coverage=coverage, integrity_errors=errors,
                                     public_call_and_integrity_pass=valid,
                                     strict_positive_pass=bool(valid and documented_pass) if case.get("answerability") == ("positive" if is_new else "within_budget") else None,
                                     strict_partial_documented_pass=bool(valid and documented_pass) if case.get("answerability") == "partial" else None,
                                     source_count=len(payload.get("sources") or []),
                                     strict_negative_empty_source_pass=bool(valid and not payload.get("sources")) if negative else None,
                                     source_receipts=verified)
                records.append(row)
    save(output / "CASE_RESULTS.json", dict(measure="unchanged original witness spans; not entailment/answer quality",
         oracle_not_passed_to_runtime=True, cases=records))


def new_coverage(case, oracle, prepared, payload, verified):
    """D contract: literal bytes, OR alternatives / AND witnesses; no text cleanup."""
    delivered = {}
    for row in verified:
        if row["integrity_pass"]:
            delivered.setdefault(row["relative_path"], []).append(payload["sources"][row["source_index"]]["snippet"].encode())
    facts, errors = [], []
    for fact in oracle["required_facts"]:
        alternatives = []
        for witnesses in fact["witness_sets"]:
            parts = []
            for witness in witnesses:
                path = Path(witness["path"])
                prefix = Path("corpus") / case["project_group"]
                if path.is_relative_to(prefix):
                    path = path.relative_to(prefix)
                relative = path.as_posix()
                source = prepared["sources"].get(relative)
                text = witness["text"].encode()
                left, right = witness["start_byte"], witness["end_byte"]
                valid = source is not None and source["sha256"] == witness["sha256"] and (
                    type(left) is int and type(right) is int and 0 <= left < right <= len(source["raw"]))
                valid = valid and source["raw"][left:right] == text
                if not valid:
                    errors.append("independent_witness_hash_or_byte_span_mismatch:" + fact["id"])
                parts.append(dict(path=relative, start_byte=left, end_byte=right,
                                  source_valid=valid, covered=bool(valid and any(text in snippet for snippet in delivered.get(relative, [])))))
            alternatives.append(dict(parts=parts, covered=bool(parts) and all(part["covered"] for part in parts)))
        facts.append(dict(id=fact["id"], alternatives=alternatives, covered=any(a["covered"] for a in alternatives)))
    return dict(facts=facts, all_required_facts_covered=bool(facts) and not errors and all(f["covered"] for f in facts),
                unavailable_obligations=oracle.get("unavailable_obligations", []),
                forbidden_claims=oracle.get("forbidden_claims", []), errors=errors,
                measure="D literal source-text presence, pinned half-open raw byte witnesses; not semantic entailment")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assess(args.manifest, args.run_dir, args.output)
