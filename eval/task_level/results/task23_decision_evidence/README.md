# Task 23 decision evidence

This directory contains sanitized, tracked decision artifacts for Task 23. Raw runner stdout, stderr, trajectories, workspaces, and per-run result files remain local/CI-only under ignored result directories.

- `task23_full_001.json`: fail-closed report for the first full matrix attempt.
- `task23_full_002.json`: completed 36-cell matrix and final `PIVOT_REQUIRED` decision. Its `retry_provenance` records the 20 cells retried only after infrastructure failures.
- Each report's `source_artifacts` hashes bind it to the ignored `runs.jsonl`, frozen protocol, and protocol amendment.
- `artifact_integrity` describes storage completeness only.
- `runtime_integrity` describes whether the recorded attempts produced valid runner outputs.

The first attempt is intentionally retained as `INCONCLUSIVE`: 22 of 36 cells encountered provider transport failures. Diagnostic medians cover only valid runner outputs and are not product-decision estimates. The second attempt has complete artifact and runtime integrity (36 of 36 valid cells); under the frozen decision rule, no quality gain and increased token use produce `PIVOT_REQUIRED`.
