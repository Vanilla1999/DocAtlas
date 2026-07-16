# Task 43 provider-free result

This directory contains the first real execution of the frozen Task 43
protocol. The execution is bound to protocol SHA-256
`2a9725df3dd31ed09eea84cf16cc84d747b34856d5ce5fac9405b1d3695cb2de`
and deterministic result digest
`ab40b26b58fb7e98424906144e971f560425e62f547d7aca867d2d8e235a0245`.

The deterministic automated gate and frozen Pareto gate are **PASS**:

- all 29 frozen contracts pass independently;
- non-legal queries omit legal-authority evidence while explicit legal intent
  can still select it;
- exact identifier requests omit prefix lookalikes such as
  `Auth.loginLegacy` for `Auth.login`;
- docs and patch source mutations are rejected against their internal
  snapshots;
- required-fact coverage, citation validity, and holdout Recall@5 are 100%;
- paired p95 retrieval-plus-projection latency remains within the frozen 10%
  bound for both docs and patch results.

Task 39 and Task 42 lower-layer gates pass, including the Task 42 reversed
candidate-order determinism check.

The overall provider-free verdict is **INCONCLUSIVE** because human review is
still pending. The production-model experiment also remains **INCONCLUSIVE**.
No human ratings, provider usage, or production-model savings are claimed.

Run the provider-free observation with:

```bash
python -m eval.answer_quality_runner --output-dir eval/answer_quality
```

The command intentionally exits non-zero while human review keeps the overall
provider-free verdict from becoming `PASS`.
