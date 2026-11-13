"""Prepare immutable answer-only inputs; no model calls or product imports.

Run from any directory with Python's standard library. Historical files are
read from a pinned git commit, never from a mutable sibling worktree.
"""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REV = "420e21924e486a7ebca8f4aa891cc176e07280f6"
OLD = "eval/blind_project_context/step15-answer-conditions/terra-small"
REPLACE = (
    "Make one final pass through the supplied sources, comparing each question-relevant "
    "statement with your draft. Add any supported point the draft leaves out, and remove "
    "claims the sources do not support. Keep this check internal; return only the final answer."
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    if isinstance(data, str):
        data = data.encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise SystemExit(f"Refusing to overwrite different artifact: {path}")
    path.write_bytes(data)


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()


def main():
    hashes = {}
    for name in ["cases.json", "inputs.json", "answers.json", "gold.json",
                 "manifest.json", "RESULTS_RU.md", "RUN_RECEIPT_RU.md"]:
        blob = subprocess.check_output(["git", "show", f"{REV}:{OLD}/{name}"], cwd=ROOT)
        save(HERE / "historical" / name, blob)
        hashes[f"historical/{name}"] = sha(blob)
    cases = json.loads((HERE / "historical/cases.json").read_text())
    inputs = json.loads((HERE / "historical/inputs.json").read_text())
    baseline = {x["case_id"]: x for x in inputs if x["policy"] == "current"}
    assert len(cases) == len(baseline) == 4
    candidate = (HERE / "candidate.txt").read_text().strip()
    roster = []
    for index, case in enumerate(cases):
        original = baseline[case["id"]]
        prompt = original["prompt"]
        assert sha(prompt.encode()) == original["prompt_sha256"]
        assert prompt.count(REPLACE) == 1
        assert case["question"] in prompt
        # Presence checks verify packaging only, never semantic delivery/retention.
        supplied = json.loads(prompt.split("SUPPLIED SOURCE EVIDENCE\n", 1)[1])
        assert supplied == case["sources"]
        changed = prompt.replace(REPLACE, candidate, 1)
        assert changed.replace(candidate, REPLACE, 1) == prompt
        arms = [("current", prompt), ("aspect-conditions-v1", changed)]
        if index % 2:
            arms.reverse()
        for arm, text in arms:
            trial = f"pair-{index + 1:02d}-{arm}"
            path = f"generator-inputs/{trial}.txt"
            save(HERE / path, text)
            hashes[path] = sha(text.encode())
            roster.append({"id": trial, "case_id": case["id"], "arm": arm,
                           "input": path, "sha256": hashes[path],
                           "historical_baseline_id": original["id"],
                           "evidence_sha256": sha(json_bytes(case["sources"]))})
    for name in ["candidate.txt", "rubric-v2.json", "prepare.py"]:
        hashes[name] = sha((HERE / name).read_bytes())
    receipt = {
        "schema": "question-relative-fixed-evidence-v1",
        "status": "PREPARED_LIVE_RUN_BLOCKED",
        "historical_revision": REV, "historical_path": OLD,
        "requested_model": "openai/gpt-6.1-terra", "effort_override": None,
        "historical_effective_settings": None,
        "provider_requests": 0, "provider_usage": None,
        "actual_provider_input_delivery": "unknown",
        "candidate_results": None,
        "blockers": ["Historical effective effort, full harness/system inputs and provider bodies are unavailable.",
                     "Original subagent launch tool is not advertised in this session; CLI existence does not establish equivalent execution.",
                     "No silent substitution of the historical answering model/settings or local product runtime."],
        "checks": {"cases": 4, "prepared_trials": 8, "source_texts_in_prepared_inputs": True,
                   "baseline_prompt_hashes_match": True, "only_instruction_replaced": True},
        "roster": roster, "sha256": hashes,
    }
    save(HERE / "manifest.json", json_bytes(receipt))
    print(json.dumps(receipt["checks"]))
    print("PREPARED_LIVE_RUN_BLOCKED; provider_requests=0; usage=null")


if __name__ == "__main__":
    main()
