# Recorded replay comparison controls

`compare_replays.py` mechanically compares existing native A/B/D_L development
artifacts. It refuses mismatched public-file hashes, Python runtime, fixture root,
repeat count or isolation mode; missing/duplicate executions; failed/audit-dirty
records; and recorded budgets beyond 800. It also checks raw results against
execution summaries. No semantic judgments, unsigned-artifact authenticity,
source integrity re-audit, model answer evaluation or causal certification.

Tests cover altered identity/input/runtime, duplicates, missing executions,
failed calls, unsafe audit records, over-budget raw packets and changed DTOs.
Mechanical identity explicitly does not become semantic/answer quality.
Focused harness: **94 passed** after adding these controls.

Applied to all saved panels: guard refinement has **204 paired executions,
zero changed DTOs**; heading threshold has **68 paired executions, ten changed
DTOs** (five synthetic cases, each repeated twice). Real-question DTOs unchanged.
The actual different-root README rerun is refused as `runtime_path` mismatch.
Output: `/tmp/opencode/ablation-mechanical-comparisons.json`.

Usage:

```bash
python -m experiments.retrieval_ablation.compare_replays LEFT_DIR RIGHT_DIR --arm B
```

This closes the development mechanical-pairing control, not original T09/T10
semantic evaluator or independent holdout requirements. Code inventories are
reported, not forced equal: intervention comparisons intentionally change code.
They remain subject to manual inspection for additional uncontrolled factors.
