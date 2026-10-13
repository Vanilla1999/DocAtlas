"""Resume only unstarted questions, within the original comparative wall deadline."""
from __future__ import annotations
import json
import os
import subprocess
import time
from pathlib import Path


def main():
    report = Path(__file__).resolve().parent
    root = report.parents[2]
    output = report / "comparison-receipts"
    deadline = (output / "worker-V0.json").stat().st_mtime + 1800
    manifest_path = report / "FROZEN_RUN_V4.json"
    manifest = json.loads(manifest_path.read_text())
    config = manifest["config"]
    safe = Path(json.loads((report / "EXECUTION_START.json").read_text())["safe_private_runtime"])
    started_ids = {r["case_id"] for r in (json.loads(line) for line in (
        output / "VQ/EXECUTION_LEDGER.jsonl").read_text().splitlines())
        if r["operation"] == "get_docs_context" and r["status"] == "started"}
    result = {"status": "running", "blocked": {"VALL": "version guard"}, "arms": {}}
    for arm, folder in [("VQ", "VQ-recovery"), ("VA", "VA"), ("VS", "VS")]:
        remaining = int(deadline - time.time())
        if remaining <= 0:
            result.update(status="wall_deadline", remaining_arm=arm)
            break
        specs = []
        for index, spec in enumerate(config["datasets"]):
            if arm not in spec["arms"]:
                continue
            item = dict(spec, index=index, arms=[arm])
            if arm == "VQ":
                cases = json.loads((Path(spec["path"]) / "questions.json").read_text())["cases"]
                item["case_ids"] = [c["id"] for c in cases if c["id"] not in started_ids]
                item["count"] = len(item["case_ids"])
            specs.append(item)
        worker = output / f"worker-{folder}.json"
        worker.write_text(json.dumps({"python": config["candidate_python"], "datasets": specs,
                                      "wall_seconds": remaining}, indent=2) + "\n")
        command = [config["candidate_python"], "-I", str(root / "eval/heuristic_removal/run.py"),
                   "--manifest", str(manifest_path), "--worker", str(worker),
                   "--output", str(output / folder), "--work", str(safe / "comparison-work" / folder)]
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH" and not k.startswith("DOCATLAS_")}
        env.update(TMPDIR=str(safe), TIKTOKEN_CACHE_DIR=config["tokenizer_cache_dir"])
        with (output / "RECOVERY_LEDGER.jsonl").open("a") as handle:
            handle.write(json.dumps({"operation": "arm_process", "status": "started", "arm": arm,
                                     "folder": folder, "command": command, "remaining_wall": remaining}) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        with (output / f"{folder}.stdout").open("w") as out, (output / f"{folder}.stderr").open("w") as err:
            child = subprocess.run(command, cwd=safe, env=env, stdout=out, stderr=err, timeout=remaining)
        summary = json.loads((output / folder / "SUMMARY.json").read_text())
        result["arms"][folder] = {"status": summary["status"], "contexts": summary["contexts"],
                                 "preparations": summary["preparations"], "exit_code": child.returncode}
        if any(r.get("database_unchanged") is False or r.get("files_unchanged") is False for r in summary["records"]):
            result.update(status="read_only_stop")
            break
    else:
        result["status"] = "recovery_finished"
    (output / "RECOVERY_SUMMARY.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
