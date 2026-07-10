"""Reproduce the scored DocAtlas side from a normalized local capture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from parity_eval import ROOT, build_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score one DocAtlas parity capture deterministically.")
    parser.add_argument("--dataset", default=str(ROOT / "dataset.jsonl"))
    parser.add_argument("--traces", required=True, help="Normalized JSONL DocAtlas capture.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(args.dataset, [args.traces])
    if set(report["providers"]) - {"docatlas"}:
        raise SystemExit("--traces must contain only provider=docatlas records")
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
