# Task 43 answer-quality protocol

This directory freezes the Task 43 provider-free quality contract before any
real Task 43 case is executed.

Validate the protocol without running retrieval, selection, or projection:

```bash
python -m eval.answer_quality_gate --validate-protocol --print-manifest
```

The command validates the 29 one-to-one overlays for the frozen Task 39 and
Task 42 cases, all bound file digests, the non-compensating Pareto rules, the
timing method, and the six-case human-review selection. The protocol-phase
module deliberately exposes no real-case runner.

After this protocol is merged, Task 43 implementation must add a separate
runner that consumes these files without rewriting them. Raw timing samples
belong in a separate non-deterministic artifact and never participate in the
deterministic result digest. Production-model execution remains a later local
operator gate and is `INCONCLUSIVE` without verified capabilities, credentials,
and provider usage records.
