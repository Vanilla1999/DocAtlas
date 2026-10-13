"""Offline frozen pilot decision; never changes oracle or imports product/model."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / "FROZEN_PILOT.json").read_text())
    planned = set(manifest["config"]["case_ids"])
    rows = [row for row in json.loads((ROOT / "pilot-assessment/CASE_RESULTS.json").read_text())["cases"]
            if row["case_id"] in planned]
    summary = json.loads((ROOT / "pilot/SUMMARY.json").read_text())
    result = dict(workload={key: value for key, value in summary.items() if key != "records"},
                  cases=[], decision="REJECT_CANDIDATE_FOR_TWO_LOSS_FIX", full40="NOT RUN: pilot gate FAIL",
                  oracle_unchanged=True, additional_product_calls=0, ignored_unrun_assessor_rows=76)
    for case_id in manifest["config"]["case_ids"]:
        case = dict(case_id=case_id, arms={}, target_windows=[])
        for arm in ("native", "learned"):
            row = next(row for row in rows if row["case_id"] == case_id and row["arm"] == arm)
            directory = ROOT / "pilot" / arm / "calls/0" / case_id / arm
            case["arms"][arm] = dict(
                status=row["status"], read_only_pass=row.get("read_only_pass"),
                native=row.get("native"), packed=row.get("packed"),
                metadata=json.loads((directory / "metadata.json").read_text()),
                model=json.loads((directory / "model.json").read_text()))
        case["fairness"] = json.loads((ROOT / "pilot/fairness" / (case_id + ".json")).read_text())
        directory = ROOT / "pilot/learned/calls/0" / case_id / "learned"
        selection = json.loads((directory / "selection.json").read_text())[0]
        model = case["arms"]["learned"]["model"]
        relevant = ([("example", "export POETRY_VIRTUALENVS_PATH=/path/to/virtualenvs/directory")]
                    if case_id == "V40-P03" else [("filename_list", "- `eslint.config.mjs`"),
                                                    ("placement_export_continuation", "It should be placed in the root directory of your project")])
        payload = json.loads((directory / "public-payload.json").read_text())
        for label, needle in relevant:
            matches = [(index, candidate) for index, candidate in enumerate(selection["pool"]) if needle in candidate["text"]]
            for index, candidate in matches:
                case["target_windows"].append(dict(label=label, original_rank=index+1,
                    learned_rank=model["order"].index(index)+1, raw_logit=model["scores"][index],
                    text=candidate["text"], text_sha256=candidate["text_sha256"],
                    binding=candidate["binding"], native_span=candidate["span"],
                    in_final_public_source=any(candidate["text"] in source["snippet"] for source in payload["sources"])))
        result["cases"].append(case)
    changed = [name for name, digest in manifest["inputs_sha256"].items()
               if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
    assert not changed
    result.update(frozen_files_checked=len(manifest["inputs_sha256"]), frozen_inputs_changed=changed,
                  pilot_gate_pass=all(case["arms"]["learned"]["native"]["strict_positive_pass"]
                                      for case in result["cases"]))
    assert len(rows) == 4 and not result["pilot_gate_pass"]
    (ROOT / "PILOT_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for case in result["cases"]:
        print(case["case_id"], [(target["label"], target["learned_rank"], target["in_final_public_source"])
                               for target in case["target_windows"]])
    print("Gate FAIL; full40 not run;", len(manifest["inputs_sha256"]), "frozen inputs unchanged")


if __name__ == "__main__":
    main()
