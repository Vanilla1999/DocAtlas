# Task 18 — run a valid Context7 parity protocol

## Priority

P1 evidence gate. Complete after tasks 14, 16, and 17.

## Problem

The existing 150-row dataset and scorer are useful scaffolding, not a valid comparison. DocAtlas traces are supplied rather than captured, cold/warm coverage is inconsistent, relevance can pass on an incorrect section, snippet presence can pass with an empty snippet, and exact-version claims can rely on rolling corpora or provider self-report.

## Goal

Produce a reproducible, paired comparison whose protocol blocks unsupported or contaminated claims automatically.

## Dataset requirements

1. Keep at least 150 audited items across at least 10 Python, 10 JavaScript/TypeScript, and 5 Dart/Flutter libraries.
2. Questions must be independently useful, not five suffix variants of one topic.
3. Each item defines requested version, source capability, allowed corpus, expected facts, acceptable sections/paths/symbols, snippet requirement, and unsupported conditions.
4. Exact-version items must point to demonstrably version-bound corpus. Rolling/latest corpus is marked unsupported for exact-match scoring.
5. Store and verify a dataset digest in every trace and report.

## Capture protocol

6. One documented command executes DocAtlas from a clean cache, records the cold result, repeats the identical query warm, and instruments network/lifecycle counts.
7. Define a separate documented Context7 adapter/capture contract using the identical question and version constraint.
8. A full comparison contains exactly one record for every `(provider, case_id, phase)` pair: `150 × 2 providers × 2 phases = 600` records. Missing or duplicate pairs invalidate comparability.
9. Record run id, dataset digest, repository/tool commits or versions, model/policy metadata where a model participates, timestamps, and normalized source provenance.
10. Keep raw traces private when required, but commit a sanitized per-item result and aggregate report.

## Scoring protocol

11. Relevance requires question-specific expected evidence, not only matching host plus one symbol.
12. A snippet is present only when normalized non-empty code exists and passes the same basic validation for both providers.
13. Exactness comes from source-derived provenance, not only `resolved_version` reported by a provider.
14. Calculate per-item output, confidence intervals, wins, losses, ties, unsupported cases, cold/warm latency, network count, lifecycle overhead, and contamination.
15. Add adversarial tests for wrong path/section, empty snippet, self-reported version, duplicate phase, missing phase, dataset mismatch, and rolling corpus.

## PR merge gate

The implementation model may not have Context7 credentials. Merge requires:

- audited dataset/schema and digest generation;
- working DocAtlas cold/warm capture on deterministic local provider fixtures;
- a Context7 adapter contract plus replay fixture, without embedded credentials;
- uniqueness/coverage/scoring validation against a synthetic complete 600-record trace;
- every adversarial invalid trace rejected;
- report generation tested from the replay fixture.

It does not require claiming parity or contacting Context7.

## Credentialed operator evidence gate

A named maintainer/operator runs the two real providers with authorized access and commits the sanitized per-item report plus reproducibility metadata. Raw captures stay private where required. Until this 600-record run passes validation, the repository must show `comparable=false` and no parity/win claim.

## Claim gate

Any incomplete coverage, unverified version, unequal source rule, protocol contamination, or missing provenance sets `comparable=false`. The report must then say why and must not emit a parity/win claim.

## Non-goals

- Do not tune the dataset after viewing provider winners.
- Do not treat retrieval parity as task-level patch success.
- Do not commit secrets or proprietary raw traces.

## Acceptance criteria

- The DocAtlas command performs capture rather than re-scoring a user-created trace.
- Synthetic/replay validation proves that a valid full run requires 600 unique paired records bound to one dataset digest.
- All adversarial traces fail comparability or the affected metric.
- The credentialed operator gate, when run, produces a sanitized report listing every case and explicit unsupported set.
- Claims are generated only after a complete real comparable operator run; lack of credentials/evidence remains `comparable=false` rather than blocking the implementation PR.
- Evaluation tests and `git diff --check` pass.
