#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.first_divergence import (
    build_atlas,
    canonical_json,
    load_json,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS = ROOT / "eval/agent_developer_v1/tasks.json"
DEFAULT_ORACLE = ROOT / "eval/agent_developer_v1/expected_trajectories.json"
DEFAULT_REPORT = ROOT / "eval/agent_developer_v1/results/model-benchmark.json"
DEFAULT_ATLAS = (
    ROOT / "eval/agent_developer_v1/results/first-divergence-atlas.json"
)
DEFAULT_MARKDOWN = (
    ROOT / "docs/analysis/p1.2-agent-developer-first-divergence.md"
)


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _check(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"missing generated evidence file: {path}")
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise SystemExit(f"generated evidence drift: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the P1.2 Agent Developer first-divergence atlas"
    )
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--atlas", type=Path, default=DEFAULT_ATLAS)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    atlas = build_atlas(
        load_json(args.tasks),
        load_json(args.oracle),
        load_json(args.report),
    )
    atlas_text = _json_text(atlas)
    markdown_text = render_markdown(atlas)

    if args.check:
        _check(args.atlas, atlas_text)
        _check(args.markdown, markdown_text)
        print(
            "Agent Developer P1.2 first-divergence atlas: CHECK PASS "
            f"({len(atlas['tasks'])} tasks; sha256={atlas['source']['report_sha256']})"
        )
        return 0

    args.atlas.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.atlas.write_text(atlas_text, encoding="utf-8")
    args.markdown.write_text(markdown_text, encoding="utf-8")
    print(canonical_json(atlas["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
