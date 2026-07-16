# Task 43 provider-free result

This directory contains the first real execution of the frozen Task 43
protocol. The execution is bound to protocol SHA-256
`2a9725df3dd31ed09eea84cf16cc84d747b34856d5ce5fac9405b1d3695cb2de`
and deterministic result digest
`b7fead9ca5c8141bb0ae7ab4242df12cb0409263d9fc910f91105543d0d6ece6`.

The provider-free verdict is **FAIL**. This is a truthful baseline, not an
accepted default:

- `t39-adv-legal-distractor` exposes `legal/terms.md` alongside the required
  `docs/configuration.md` evidence.
- `t42-patch-identifier-boundary` exposes `src/legacy_auth.py` and
  `Auth.loginLegacy` alongside the required exact identifier.
- the patch projection validator does not reject a mutation of
  `sources[].path` against its internal snapshot. The runner requires the
  explicit snapshot-binding error and therefore fails closed.

Task 39 and Task 42 lower-layer gates pass, including the Task 42 reversed
candidate-order determinism check. Required-fact coverage and holdout Recall@5
remain 100%, but those metrics cannot compensate for citation or integrity
failures under the frozen Pareto rule.

Human review and the production-model experiment remain **INCONCLUSIVE**. No
human ratings, provider usage, or production-model savings are claimed.

Run the provider-free observation with:

```bash
python -m eval.answer_quality_runner --output-dir eval/answer_quality
```

The command intentionally exits non-zero while the provider-free verdict is
not `PASS`. Product fixes belong in a subsequent branch and must consume the
same frozen protocol and cases without rewriting them.
