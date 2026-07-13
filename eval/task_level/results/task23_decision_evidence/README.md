# Task 23 decision evidence

This directory contains sanitized, tracked decision artifacts for Task 23. Raw runner stdout, stderr, trajectories, workspaces, and per-run result files remain local/CI-only under ignored result directories.

The legacy `task23_full_001.json` report predates the tracked sanitized per-run bundle. The regenerated `task23_full_002.json` report has a sibling `task23_full_002_runs.sanitized.jsonl` bundle containing per-cell metrics, normalized sanitized trajectories, and patches; its SHA-256 is bound in `source_artifacts.sanitized_runs_sha256`.

- `task23_full_001.json`: fail-closed report for the first full matrix attempt.
- `task23_full_002.json`: completed 36-cell historical matrix and current fail-closed `INCONCLUSIVE` decision. Its `retry_provenance` records the 20 cells retried only after infrastructure failures.
- `task23_full_002_runs.sanitized.jsonl`: tracked 36-cell rescore bundle bound to the report by SHA-256.
- Each report's `source_artifacts` hashes bind it to the ignored `runs.jsonl`, frozen protocol, and protocol amendment.
- `artifact_integrity` describes storage completeness only.
- `runtime_integrity` describes whether the recorded attempts produced valid runner outputs.

The first attempt is intentionally retained as `INCONCLUSIVE`: 22 of 36 cells encountered provider transport failures. Diagnostic medians cover only valid runner outputs and are not product-decision estimates. The second attempt has complete artifact and runtime integrity (36 of 36 valid cells), but all 36 rows lack complete budget metadata and maximum turns were not runner-enforced. The hardened gate therefore classifies it as `INCONCLUSIVE`; zero resolved hidden tests and increased token use remain descriptive observations only.

## Legacy evidence limitations

`task23_full_001.json` remains a historical artifact. `task23_full_002.json` was regenerated with the hardened analysis code. In particular:

- the first attempt has no tracked per-run rescore bundle;
- `useful_context_ratio` is `null` until real usage attribution exists;
- task-level input/output limits were not captured as complete per-run budget metadata, and maximum turns were not runner-enforced;
- the confidence interval resampled task/repeat pairs rather than clustering by the three independent tasks.

These limitations prevent a valid `CONTINUE` or `PIVOT_REQUIRED` product decision. Task 33 owns a replacement evidence-complete, task-clustered protocol. The frozen Task 23 protocol retains its original `sha256-concat-v1` fixture identifiers for source-hash reproducibility; new fixture builds use collision-resistant `sha256-length-prefixed-v2`.
