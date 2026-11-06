"""Offline forensic accounting of saved public runs. Never runs inference."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = Path("/tmp/opencode/step8-corpora2/L0-0")


def load(path):
    return json.loads(path.read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(root, name):
    manifest = load(root / name)
    for path, sha in manifest["files"].items():
        assert digest((root / path).read_bytes()) == sha, path
    return len(manifest["files"])


def main():
    calibration = BASE / "step10-calibration"
    verified = verify(calibration, "manifest.json")
    verified += verify(calibration / "measurement-observer", "receipt-manifest.json")
    results = load(calibration / "measurement-observer/results.json")
    tasks = {task["id"]: task for task in load(calibration / "tasks.json")}
    tau = load(calibration / "measurement-observer/policy.json")["threshold"]
    useful = sorted((u["score"], r["id"], u["heading"]) for r in results
                    if r["split"] == "calibration" for u in r["units"] if u["useful"])
    assert useful[0][0] == tau
    empty_tasks = [r for r in results if r["split"] == "calibration" and not r["expected_facts"]]
    negatives = [(u["score"], r["id"], u["heading"]) for r in empty_tasks for u in r["units"]]
    highest_negative = max(negatives)
    report = {"verified_historical_artifacts": verified,
              "calibration": {"threshold": tau, "limiting_positive": useful[0],
                              "positive_pairs": len(useful),
                              "distinct_positive_bodies": len({(tasks[r["id"]]["document"], u["heading"])
                                  for r in results if r["split"] == "calibration"
                                  for u in r["units"] if u["useful"]}),
                              "highest_noanswer_score": highest_negative,
                              "all_direct_positives_and_empty_noanswer_threshold_exists": highest_negative[0] < tau},
              "runs": {}}
    facts = ["Branch name: `feat/<topic>` or `fix/<description>`",
             "Run the full test suite before opening the PR",
             "New connectors or fetchers should include tests where practical"]
    for case in ("original-v3", "renewed-v1"):
        directory = HERE / case
        inp, packet = load(directory / "input.json"), load(directory / "packet.json")
        obs = load(directory / "observations.json")[0]
        scores, receipt = obs["scores"], obs["receipt"]
        threshold = inp["policy"]["threshold"]
        for path, expected in inp["state"]["files"].items():
            assert digest((ROOT / path).read_bytes()) == expected
        for path, expected in inp["state"]["logical_databases"].items():
            with sqlite3.connect((ROOT / path).as_uri() + "?mode=ro", uri=True) as db:
                assert digest("\n".join(db.iterdump()).encode()) == expected
        for row in packet["sources"]:
            raw = (ROOT / "project" / row["path_or_url"]).read_bytes().decode()
            expected = "".join(raw.splitlines(keepends=True)[row["line_start"] - 1:row["line_end"]])
            assert row["snippet"] == expected
            lineage = next(json.loads(s["source_identity"])["candidate"] for s in scores
                           if s["path"] == row["path_or_url"])
            assert row["scope"] == lineage["doc_scope"]
            assert row["authority"] == lineage["authority"]
        ordered = sorted(scores, key=lambda r: r["score"], reverse=True)
        witness = next(r for r in scores if r["path"] == "CONTRIBUTING.md" and r["line_start"] == 59)
        direct = Counter(r["path"] for r in scores if r["score"] >= threshold)
        delivered = Counter(r["path_or_url"] for r in packet["sources"])
        assert sum(direct.values()) == packet["source_selection"]["selected_units"]
        entry = {"threshold": threshold, "units": len(scores), "direct": sum(direct.values()),
                 "delivered": len(packet["sources"]), "model_pairs": receipt["model_pairs"],
                 "facts": [any(f in r["snippet"] for r in packet["sources"]) for f in facts],
                 "witness_rank": ordered.index(witness) + 1, "witness_score": witness["score"],
                 "direct_kept_if_witness_admitted": sum(r["score"] >= witness["score"] for r in scores),
                 "source_spans_and_bound_scopes_checked": len(packet["sources"]),
                 "current_source_and_database_match_pre_call": True,
                 "per_document": {k: {"direct": direct[k], "delivered": v} for k, v in delivered.items()},
                 "selected_roots": [{"path": r["path"], "score": r["score"]} for r in scores
                                    if r["score"] >= threshold and len(r["heading_path"]) == 1]}
        if case == "original-v3":
            gated_out = [r for r in scores if r["contextual_score"] >= threshold and r["score"] < threshold]
            spans = {(r["path_or_url"], r["line_start"], r["line_end"]) for r in packet["sources"]}
            entry.update(contextual_only_kept=sum(r["contextual_score"] >= threshold for r in scores),
                         own_body_only_kept=sum(r["own_body_score"] >= threshold for r in scores),
                         gate_rejections=len(gated_out),
                         gate_rejections_restored_by_closure=sum((r["path"], r["line_start"], r["line_end"]) in spans for r in gated_out))
        if case == "renewed-v1":
            max_query = max(receipt["query_tokens"])
            lanes = len(receipt["query_tokens"])
            unnecessary = [r for r in scores if r["body_tokens"] + r["ancestor_tokens"] + max_query
                           + receipt["pair_special_tokens"] <= receipt["maximum_sequence_length"]
                           and r["pairs"] > lanes]
            single = [r for r in scores if r["pairs"] == lanes]
            entry.update(unnecessary_split_units=len(unnecessary), single_window_per_lane_units=len(single),
                         single_window_per_lane_kept=sum(r["score"] >= threshold for r in single),
                         unnecessary_split_examples=[{k: r[k] for k in ("path", "heading_path", "body_tokens", "ancestor_tokens", "pairs")} for r in unnecessary],
                         initial_probe_failure="Post-call evaluator incorrectly required every scope to be project; 13 allowed module rows triggered its assertion. Packet and scores were already saved. Corrected offline by checking bound source scope. No repeated inference; wall time was not persisted.")
        report["runs"][case] = entry
    report["new_runtime_work"] = {"public_calls": 2, "public_model_pairs": 2298,
                                  "independent_model_control_pairs": 8, "terra_calls": 0}
    (HERE / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (HERE / "artifact-sha256.json").write_text(json.dumps({str(p.relative_to(HERE)): digest(p.read_bytes())
        for p in sorted(HERE.rglob("*")) if p.is_file() and p.name != "artifact-sha256.json"
        and "__pycache__" not in p.parts}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
