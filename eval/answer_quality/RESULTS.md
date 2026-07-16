# Task 43 provider-free result

This directory contains the first real execution of the frozen Task 43
protocol. The execution is bound to protocol SHA-256
`2a9725df3dd31ed09eea84cf16cc84d747b34856d5ce5fac9405b1d3695cb2de`
and deterministic result digest
`5e4b1603d59f1895a929a3545e465c3883364c83a135331317462b0ab02f3680`.

The deterministic automated gate and frozen Pareto gate are **PASS**:

- all 29 frozen contracts pass independently;
- non-legal queries omit legal-authority evidence while explicit legal intent
  can still select it;
- exact identifier requests omit prefix lookalikes such as
  `Auth.loginLegacy` for `Auth.login`;
- docs and patch source fields, including trust and scope metadata, are
  exactly bound to their internal snapshots;
- required-fact coverage, citation validity, and holdout Recall@5 are 100%;
- baseline and candidate p95 retrieval-plus-projection latency are measured in
  one Python process and remain within the frozen 10% bound for both docs and
  patch results;
- actionable questions backed only by general guidance disclose the missing
  configuration detail instead of presenting that guidance as complete.

Task 39 and Task 42 lower-layer gates pass, including the Task 42 reversed
candidate-order determinism check.

The overall provider-free verdict is **INCONCLUSIVE** because human review is
still pending. The production-model experiment also remains **INCONCLUSIVE**.
No human ratings, provider usage, or production-model savings are claimed.
The six human-review inputs now carry their public questions and applicable
version/path constraints so directness and ambiguity can be reviewed without
consulting hidden evaluator state.

Run the provider-free observation with:

```bash
python -m eval.answer_quality_runner --output-dir eval/answer_quality
```

The command intentionally exits non-zero while human review keeps the overall
provider-free verdict from becoming `PASS`.
