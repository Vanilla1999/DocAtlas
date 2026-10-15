"""Offline original-oracle scoring and independent source-coordinate diagnostics."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
DATA = REPO / "eval/prepared_model_comparison40"


def main():
    spec = importlib.util.spec_from_file_location("historical", DATA / "evaluate.py")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    questions = {case["id"]: case for case in json.loads((DATA / "questions.json").read_text())["cases"]}
    gold = {case["id"]: case for case in json.loads((DATA / "gold_spans.json").read_text())["cases"]}
    results = []
    for number, case_id in enumerate(("V40-P03", "V40-E01"), 1):
        question = questions[case_id]
        group = question["project_group"]
        directory = ROOT / "run/V0/calls/0" / case_id / "V0"
        preparation = json.loads((ROOT / f"run/V0/preparation/0-{group}.json").read_text())
        prepared = dict(root=preparation["root"], sources={})
        for p in (DATA / "sources" / group).rglob("*"):
            if p.is_file():
                raw = p.read_bytes()
                text = raw.decode()
                offsets = [0]
                for line in text.splitlines(keepends=True):
                    offsets.append(offsets[-1] + len(line))
                prepared["sources"][p.relative_to(DATA / "sources" / group).as_posix()] = dict(
                    raw=raw, content=text, sha256=hashlib.sha256(raw).hexdigest(), line_offsets=offsets, errors=[])
        trace = json.loads((ROOT / f"run/boundaries/call-{number}.json").read_text())
        assert trace["request"]["question"] == question["question"]
        assert not trace["errors"] and trace["omitted_events"] == 0
        stages = []
        targets = []
        for event in trace["events"]:
            if not event["stage"].endswith(".output") or "rows" not in event:
                continue
            intervals = {}
            errors = []
            if event["rows"] and "public" in event["rows"][0]:
                rows = [row["public"] for row in event["rows"]]
                verified, intervals, errors = evaluator._source_rows({"sources": rows}, prepared)
                coverage = evaluator._gold(question, gold[case_id], prepared, intervals)
                for row, check in zip(event["rows"], verified):
                    if event["stage"] == "project_docs_context.output" and check["integrity_pass"]:
                        for claim in coverage["claims"]:
                            for alternative in claim["witness_sets"]:
                                for part in alternative["parts"]:
                                    if part["path"] != check["relative_path"]:
                                        continue
                                    offsets = prepared["sources"][part["path"]]["line_offsets"]
                                    left, right = offsets[part["line_start"]-1], offsets[part["line_end"]]
                                    if any(a < right and b > left for a, b in check["guaranteed_coverage_intervals"]):
                                        targets.append(dict(evidence_id=row["public"]["evidence_id"],
                                            rank=check["source_index"] + 1, public=row["public"], binding=row["binding"],
                                            raw_source_sha256=check["pinned_raw_file_sha256"],
                                            exact_verified_intervals=check["guaranteed_coverage_intervals"]))
            else:
                # Search/acquisition texts are not authorized public evidence. Locate independently.
                for row in event["rows"]:
                    source = str(row.get("source") or "")
                    if not source.startswith(prepared["root"] + "/"):
                        errors.append("source_not_in_prepared_root")
                        continue
                    relative = source[len(prepared["root"])+1:]
                    original = prepared["sources"][relative]["content"]
                    text = row["text"]
                    assert hashlib.sha256(text.encode()).hexdigest() == row["text_sha256"]
                    matches = evaluator._occurrences(original, text, 0, len(original))
                    if not matches:
                        errors.append("no_exact_source_occurrence")
                    elif len(matches) == 1:
                        intervals.setdefault(relative, []).append(matches[0])
                    # Ambiguous occurrence never proves a coordinate.
                coverage = evaluator._gold(question, gold[case_id], prepared, intervals)
            stages.append(dict(sequence=event["sequence"], stage=event["stage"], count=event["count"],
                               integrity_errors=errors, original_gold=coverage))
        assert all(not stage["integrity_errors"] for stage in stages)
        metadata = json.loads((directory / "metadata.json").read_text())
        final_scores = {}
        for name, filename in (("native", "public-payload.json"), ("packed", "packed.json")):
            payload = json.loads((directory / filename).read_text())
            _, intervals, errors = evaluator._source_rows(payload, prepared)
            final_scores[name] = dict(integrity_errors=errors, original_gold=evaluator._gold(question, gold[case_id], prepared, intervals))
        old_dir = REPO / "reports/docatlas-grounded-20261013/sdk-delivery-v40/run/V0/calls/0" / case_id / "V0"
        old = json.loads((old_dir / "public-payload.json").read_text())
        current = json.loads((directory / "public-payload.json").read_text())
        def normalized(payload):
            return {(row["path_or_url"].split("/project/", 1)[-1], row["line_start"], row["line_end"], row["snippet"])
                    for row in payload["sources"]}
        previous, now = normalized(old), normalized(current)
        costs = {target["evidence_id"]: [event for event in trace["events"]
                    if event["stage"] == "budget.cost" and (event.get("option") or {}).get("evidence_id") == target["evidence_id"]]
                 for target in targets}
        ledger = next(event for event in trace["events"] if event["stage"] == "budget.ledger")
        rejected = [target for target in targets if target["evidence_id"] in ledger["all_omitted_evidence_ids"]]
        for target in rejected:
            assert costs[target["evidence_id"]] and all(event["over_cap"] for event in costs[target["evidence_id"]])
        results.append(dict(case_id=case_id, question=question["question"], stages=stages,
                            original_final_scores=final_scores, metadata=metadata, witness_overlapping_rows=targets,
                            budget_cost_observations=costs, budget_ledger=ledger,
                            independently_proven_loss="terminal_public_DTO_budget" if rejected else None,
                            previous_output_comparison=dict(old_count=len(previous), new_count=len(now),
                                removed_count=len(previous-now), added_count=len(now-previous),
                                identical_normalized_rows=previous == now,
                                root_path_character_delta=len(prepared["root"])-len(json.loads((old_dir / "metadata.json").read_text())["public_request"]["project_path"])),
                            observer_errors=trace["errors"], observer_omitted_events=trace["omitted_events"]))
    manifest = json.loads((ROOT / "FROZEN_RUN.json").read_text())
    changed = [name for name, digest in manifest["inputs_sha256"].items() if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
    assert not changed
    (ROOT / "DIAGNOSIS.json").write_text(json.dumps(dict(cases=results, inputs_unchanged=True,
        frozen_files_checked=len(manifest["inputs_sha256"]), additional_product_calls=0), ensure_ascii=False, indent=2) + "\n")
    for result in results:
        print(result["case_id"], result["independently_proven_loss"], result["previous_output_comparison"])


if __name__ == "__main__":
    main()
