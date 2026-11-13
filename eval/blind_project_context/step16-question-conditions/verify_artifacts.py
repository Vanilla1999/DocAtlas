"""Offline artifact audit only; no product imports, model calls or semantic judge."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    manifest = load("manifest.json")
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, name
    cases = {c["id"]: c for c in load("historical/cases.json")}
    answers = {a["id"]: a for a in load("historical/answers.json")}
    rubric = {c["id"]: c for c in load("rubric-v2.json")["cases"]}
    review = load("baseline-review-v2.json")
    rows = quotes = sources = old_quotes = 0
    assert {r["case_id"] for r in review["reviews"]} == set(cases)
    for r in review["reviews"]:
        assert {i["id"] for i in r["items"]} == {i["id"] for i in rubric[r["case_id"]]["items"]}
        for item in r["items"]:
            rows += 1
            if item["quote"] is not None:
                assert item["quote"] in answers[r["trial"]]["answer"], item["id"]
                quotes += 1
    for case in cases.values():
        for source in case["sources"]:
            if case["id"] == "V-M1":
                path = "eval/blind_project_context/step14-host-language-live/frozen-corpus/" + source["path"]
                raw = subprocess.check_output(["git", "show", f'{manifest["historical_revision"]}:{path}'], cwd=ROOT)
                span = "".join(raw.decode().splitlines(keepends=True)[source["line_start"] - 1:source["line_end"]])
                assert span == source["text"], source["path"]
            else:
                raw = source["text"].encode()
            assert hashlib.sha256(raw).hexdigest() == source["source_sha256"], source["path"]
            sources += 1
    for case in load("historical/gold.json"):
        for fact in case["facts"]:
            assert any(fact["quote"] in s["text"] for s in cases[case["id"]]["sources"])
            old_quotes += 1
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    result = {"status": "PASS_ARTIFACT_INTEGRITY_ONLY", "manifest_hashes": len(manifest["sha256"]),
              "source_spans_and_hashes": sources, "historical_quotes_in_prepared_evidence": old_quotes,
              "review_rows": rows, "exact_answer_quotes": quotes, "git_diff_check": "PASS",
              "semantic_review_independent": False, "provider_delivery_verified": False,
              "model_calls_by_artifact_verifier": 0, "product_tests_run": 0}
    if (HERE / 'live/delivery-checks.json').exists():
        result['live_delivery_checks'] = load('live/delivery-checks.json')
        result['live_review_checks'] = load('live/summary.json')['checks']
        result['generated_answers'] = 8
    (HERE / "checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
