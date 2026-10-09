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

## Current acceptance cost policy

The owner removed the fixed 800-token full-response acceptance ceiling on
2026-10-09. Report schema `systemic-retrieval-plan-acceptance-v3` treats full
model-visible token counts and canonical UTF-8 bytes as minimization metrics.
It retains measured distributions and maxima without a budget pass/fail flag.
Evidence fidelity, sufficiency floors, source integrity, complete case inventory,
and the other acceptance checks remain required.

The frozen corpus labels `within_budget` and `over_budget` remain historical
cohort names; the 48-case primary cohort and all 80 cases are unchanged. Selector
and singleton diagnostics retain their explicitly labelled historical 800-token
control for comparison with older experiments. That diagnostic bound is not a
current full-response merge requirement. This policy change does not itself
reduce response size or establish client/model token savings.
