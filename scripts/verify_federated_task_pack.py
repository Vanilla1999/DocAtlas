#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.product_truth_v2.federated_task_pack import (  # noqa: E402
    build_report,
    load_json,
    verify_report,
)


MANIFEST = ROOT / "eval" / "product_truth_v2" / "federated-task-pack.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest = load_json(MANIFEST)
    report = build_report(manifest)
    verify_report(report, manifest=manifest)
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    summary = report["summary"]
    print(
        "Federated Product Truth candidate pack: PASS; "
        f"repositories={summary['repositories']}; "
        f"candidates={summary['candidate_tasks']}; "
        f"valid={summary['valid_tasks']}; "
        f"status={report['execution_status']}; "
        f"sha256={report['manifest_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
