#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.mixed_provenance import (
    canonical_json,
    derive_from_paths,
    load_json,
    sha256_json,
    verify_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_OUTPUT = ROOT / "results" / "mixed-evidence-provenance.json"


def _production_evidence_model_path() -> Path:
    candidates = (
        REPO_ROOT / "docmancer" / "docs" / "application" / "evidence_models.py",
        REPO_ROOT / "docmancer" / "docs" / "domain" / "answer_completeness.py",
    )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise RuntimeError("no reviewed production evidence-model module exists")
    return existing[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify P1.5 mixed-evidence provenance")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    derived = derive_from_paths(
        repo_root=REPO_ROOT,
        protocol_path=ROOT / "mixed_provenance_protocol.json",
        selector_path=REPO_ROOT / "docmancer" / "docs" / "application" / "evidence_selection.py",
        model_path=_production_evidence_model_path(),
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
                "committed P1.5 report differs from the frozen mixed-evidence derivation; "
                "run with --write and review the provenance change"
            )
    print(
        "P1.5 mixed-evidence provenance: PASS; "
        f"cases={derived['summary']['case_count']}; "
        f"matched={derived['summary']['matched_cases']}; "
        f"sha256={sha256_json(derived)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
