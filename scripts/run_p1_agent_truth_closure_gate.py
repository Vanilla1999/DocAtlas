#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from eval.agent_developer_v1.p1_closure import (
    PROTOCOL, SCHEMA_VERSION, default_current_paths, derive_from_paths,
    load_json, sha256_json, verify_closure,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval/agent_developer_v1"
DEFAULT_OUTPUT = ROOT / "results/p1-agent-truth-closure.current.json"


def input_arguments(parser: argparse.ArgumentParser) -> None:
    defaults = default_current_paths(ROOT)
    for name in ("p14", "p15", "p16"):
        parser.add_argument("--" + name, type=Path, default=defaults["p1_" + name[-1]])
    parser.add_argument("--gates", type=Path, help="JSON of actual named workflow step outcomes")


def report_inputs(args: argparse.Namespace) -> tuple[dict, dict | None]:
    paths = {"p1_4": args.p14, "p1_5": args.p15, "p1_6": args.p16}
    try:
        outcomes = load_json(args.gates) if args.gates is not None else None
    except (OSError, ValueError, TypeError):
        outcomes = None
    return paths, outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify current P1 fixture evidence from one checkout")
    input_arguments(parser)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true", help="Compatibility flag; current evidence is always saved")
    args = parser.parse_args(argv)
    paths, outcomes = report_inputs(args)
    protected = {
        ROOT / "results" / name for name in (
            "first-divergence-atlas.json", "contract-v2-ablation.json",
            "paraphrase-proofability.json", "mixed-evidence-provenance.json",
            "evidence-is-data.json", "p1-agent-truth-closure.json",
        )
    } | set(paths.values())
    if args.gates is not None:
        protected.add(args.gates)
    if args.output.resolve() in {path.resolve() for path in protected}:
        parser.error("current closure output must not overwrite historical or input evidence")
    context = dict(repo_root=REPO_ROOT, root=ROOT, current_paths=paths, gate_outcomes=outcomes)
    if outcomes is None:
        print("Missing current workflow proof: supply --gates with actual SHA-bound step outcomes; historical green is not a fallback.")
    try:
        report = derive_from_paths(**context)
    except Exception as exc:
        report = {
            "schema_version": SCHEMA_VERSION, "protocol": PROTOCOL,
            "passed": False, "execution_status": "ERROR",
            "error": {"type": type(exc).__name__,
                      "message_sha256": hashlib.sha256(str(exc).encode("utf-8")).hexdigest()},
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"P1 current closure: {report['execution_status']}; sha256={sha256_json(report)}; report={args.output}")
    for row in report.get("scorecard", [])[3:]:
        print(f"{row['id']}: integrity={row['integrity_valid']}; quality={row['quality_passed']}; "
              f"summary={json.dumps(row['summary'], sort_keys=True)}; error={json.dumps(row['error'], sort_keys=True)}")
    for row in report.get("required_gates", {}).get("outcomes", []):
        print(f"GATE {row['id']}: {row['outcome']}")
    try:
        verify_closure(report, **context)
    except Exception as exc:
        print(f"P1 current closure: FAIL ({type(exc).__name__}: {exc})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
