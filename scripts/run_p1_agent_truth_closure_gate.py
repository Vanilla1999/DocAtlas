#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.p1_closure import (
    canonical_json,
    derive_from_paths,
    load_json,
    sha256_json,
    verify_closure,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_OUTPUT = ROOT / "results" / "p1-agent-truth-closure.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the P1 Agent Truth closure scorecard")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    derived = derive_from_paths(repo_root=REPO_ROOT, root=ROOT)
    verify_closure(derived)
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(derived, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        committed = load_json(args.output)
        verify_closure(committed)
        if canonical_json(committed) != canonical_json(derived):
            raise SystemExit(
                "committed P1 closure differs from the current evidence set; "
                "run with --write and review the claim-boundary change"
            )
    print(
        "P1 Agent Truth closure: PASS; execution=CLOSED; "
        "outcome=AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN; "
        f"sha256={sha256_json(derived)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
