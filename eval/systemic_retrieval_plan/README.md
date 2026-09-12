# Systemic retrieval independent-project sample

This directory is an evaluation-only, post-hoc independent-project sample for
PR #186. The projects are absent from the frozen 80-case
`eval/evidence_quality_v2` development corpus. Source files are copied unchanged
from the pinned upstream Git blobs recorded in `source-manifest.json`; the runner
verifies their SHA-256 digests before indexing.

The sample is **not hidden and not preregistered**. It can support a bounded
cross-project regression/generalization check, but it is not evidence for broad
market-wide or unseen-distribution generalization. Raw traces are written
outside the repository by `scripts/run_systemic_retrieval_plan_gate.py`.
