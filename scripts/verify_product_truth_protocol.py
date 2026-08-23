#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from eval.product_truth_v1.protocol import validate_repository


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    result = validate_repository(REPO_ROOT)
    print(
        "P2 Product Truth protocol: PASS; "
        f"sha256={result['protocol_sha256']}; "
        f"schemas={result['schema_count']}; "
        f"samples={result['sample_count']}; "
        f"canary={result['canary_scored_runs']}; "
        f"full={result['minimum_scored_runs']}-{result['maximum_scored_runs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
