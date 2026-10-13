"""Coordinator-only sequential execution; ALL halted by installed version guard."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


def main() -> None:
    report = Path(__file__).resolve().parent
    root = report.parents[2]
    manifest_path = report / "FROZEN_RUN_V3.json"
    manifest = json.loads(manifest_path.read_text())
    config = manifest["config"]
    safe = Path(json.loads((report / "EXECUTION_START.json").read_text())["safe_private_runtime"])
    output, work = report / "comparison-receipts", safe / "comparison-work"
    output.mkdir()
    work.mkdir(mode=0o700)
    started = time.perf_counter()
    summary = {"status": "running", "arms": {}, "blocked_arms": {"VALL": "installed explicit-version guard failure"},
               "planned_after_safety_stop": 260, "contexts": 0, "preparations": 0, "model_calls": 0}

    def save(path, value):
        path.write_text(json.dumps(value, indent=2) + "\n")

    def log(**row):
        with (output / "EXECUTION_LEDGER.jsonl").open("a") as handle:
            handle.write(json.dumps(row) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    try:
        for arm in ("V0", "VQ", "VA", "VS"):
            remaining = int(1800 - (time.perf_counter() - started))
            if remaining <= 0:
                raise TimeoutError("global comparative wall ceiling")
            interpreter = config["baseline_python" if arm == "V0" else "candidate_python"]
            specs = [dict(spec, index=index, arms=[arm]) for index, spec in enumerate(config["datasets"])
                     if arm in spec["arms"]]
            worker = output / f"worker-{arm}.json"
            save(worker, {"python": interpreter, "datasets": specs, "wall_seconds": remaining})
            command = [interpreter, "-I", str(root / "eval/heuristic_removal/run.py"),
                       "--manifest", str(manifest_path), "--output", str(output / arm),
                       "--work", str(work / arm), "--worker", str(worker)]
            log(operation="arm_process", status="started", arm=arm, command=command)
            env = {key: value for key, value in os.environ.items()
                   if key != "PYTHONPATH" and not key.startswith("DOCATLAS_")}
            env.update(TMPDIR=str(safe), TIKTOKEN_CACHE_DIR=config["tokenizer_cache_dir"])
            with (output / f"{arm}.stdout").open("w") as out, (output / f"{arm}.stderr").open("w") as err:
                child = subprocess.run(command, cwd=work, env=env, stdout=out, stderr=err, timeout=remaining)
            path = output / arm / "SUMMARY.json"
            lane = json.loads(path.read_text()) if path.exists() else {"status": "setup_failure", "contexts": 0, "preparations": 0}
            summary["arms"][arm] = lane
            log(operation="arm_process", status="returned", arm=arm, exit_code=child.returncode,
                contexts=lane["contexts"], preparations=lane["preparations"])
            if any(row.get("database_unchanged") is False or row.get("files_unchanged") is False
                   for row in lane.get("records", [])):
                raise RuntimeError("read-only violation: stopping all remaining arms")
        summary["status"] = "restricted_completed" if all(
            lane["status"] == "completed" for lane in summary["arms"].values()) else "restricted_incomplete"
    except Exception as exc:
        summary.update(status="error", error=repr(exc))
    finally:
        attempts = [json.loads(line) for path in output.glob("*/EXECUTION_LEDGER.jsonl")
                    for line in path.read_text().splitlines()]
        summary["contexts"] = sum(row["operation"] == "get_docs_context" and row["status"] == "started" for row in attempts)
        summary["preparations"] = sum(row["operation"] == "prepare_docs" and row["status"] == "started" for row in attempts)
        summary["seconds"] = time.perf_counter() - started
        save(output / "SUMMARY.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "arms"}))


if __name__ == "__main__":
    main()
