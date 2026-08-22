#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.paraphrase_robustness import (
    canonical_json,
    derive_from_paths,
    load_json,
    sha256_json,
    verify_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_OUTPUT = ROOT / "results" / "paraphrase-proofability.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify P1.4 paraphrase/proofability evidence")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    derived = derive_from_paths(
        repo_root=REPO_ROOT,
        protocol_path=ROOT / "paraphrase_protocol.json",
        selector_path=REPO_ROOT / "docmancer" / "docs" / "application" / "evidence_selection.py",
        planner_path=REPO_ROOT / "docmancer" / "docs" / "domain" / "project_answer_contract.py",
    )
    verify_report(derived)
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(derived, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        committed = load_json(args.output)
        verify_report(committed)
        if canonical_json(committed) != canonical_json(derived):
            raise SystemExit(
                "committed P1.4 report differs from the current frozen corpus/runtime; "
                "run with --write and review the measured change"
            )
    print(
        "P1.4 paraphrase/proofability: PASS; "
        f"cases={derived['summary']['case_count']}; "
        f"negative_false_support={derived['summary']['false_supported_negative_controls']}; "
        f"sha256={sha256_json(derived)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
