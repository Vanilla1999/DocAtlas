"""Real evaluator CLI refusal with sentinel outputs and execve auditing.

No model/provider mock, no helper calls, no session or inference permitted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--prepared-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    tree = Path(__file__).resolve().parents[3]
    records = []
    for name, error in (("historical-plan", "study plan changed; use a new output"),
                        ("orphan-artifacts", "case artifacts exist without study plan; use a new output")):
        case_root = root / name
        output = case_root / "output"
        artifacts = output / "L0" / "file-current"
        artifacts.mkdir(parents=True)
        (artifacts / "T01-ru.jsonl").write_bytes(b'{"historical":"sentinel output"}\n')
        (artifacts / "opencode.json").write_bytes(b'{"historical":"sentinel config"}\n')
        if name == "historical-plan":
            (output / "file-current-plan.json").write_bytes(
                b'{"question_transport":"cli_positional_historical","sentinel":true}\n')
        before = hashes(output)
        command = [sys.executable, str(tree / "eval/blind_project_context/run_gap_agent_study.py"),
                   "--out", str(output), "--prepared-root", str(args.prepared_root.resolve()),
                   "--executable", str(Path(sys.executable).parent / "doc-atlas"),
                   "--arm", "file-current", "--corpus", "L0", "--case", "T01-ru"]
        trace = case_root / "execve.log"
        result = subprocess.run(["/usr/bin/strace", "-f", "-e", "trace=execve", "-s", "4096",
                                 "-o", str(trace), *command], capture_output=True, text=True, timeout=30)
        (case_root / "stdout.txt").write_text(result.stdout)
        (case_root / "stderr.txt").write_text(result.stderr)
        after = hashes(output)
        executions = [line for line in trace.read_text().splitlines() if "execve(" in line]
        assert result.returncode != 0 and error in result.stderr, result.stderr
        assert before == after, "Existing artifact changed or a new artifact appeared"
        assert len(executions) == 1 and str(sys.executable) in executions[0], executions
        records.append({"case": name, "command": command, "exit": result.returncode,
                        "expected_error": error, "sentinel_bytes_unchanged": True,
                        "before_sha256": before, "after_sha256": after,
                        "execve_count_including_evaluator": len(executions),
                        "session_model_processes": 0})
    receipt = {"status": "PASS", "boundary": "real evaluator CLI; strace execve audit; no mocks",
               "cli_calls": len(records), "session_calls": 0, "model_calls": 0, "cases": records}
    (root / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
