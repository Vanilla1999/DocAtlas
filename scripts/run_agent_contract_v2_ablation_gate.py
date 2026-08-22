#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.contract_v2_ablation import (
    canonical_json,
    derive_from_paths,
    load_json,
    sha256_json,
    verify_ablation,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_OUTPUT = ROOT / "results" / "contract-v2-ablation.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the P1.3 Agent Contract v2 ablation")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    derived = derive_from_paths(
        repo_root=REPO_ROOT,
        public_tasks_path=ROOT / "tasks.json",
        oracle_path=ROOT / "expected_trajectories.json",
        atlas_path=ROOT / "results" / "first-divergence-atlas.json",
    )
    verify_ablation(derived)
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(derived, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        committed = load_json(args.output)
        verify_ablation(committed)
        if canonical_json(committed) != canonical_json(derived):
            raise SystemExit(
                "committed P1.3 report differs from the frozen counterfactual derivation; "
                "run with --write and review the decision change"
            )
    print(
        "P1.3 Agent Contract v2 ablation: PASS; "
        "working_path=rejected; inference=inconclusive(8/8 covered); "
        "continuation_token=rejected; "
        f"sha256={sha256_json(derived)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
