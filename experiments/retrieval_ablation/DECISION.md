# Decision after the T00–T04 diagnostic report

This document follows ABLATION_REPORT.md. It is an engineering disposition for
the delivered diagnostic slice, **not** the T12 decision after a completed
retrieval-quality matrix. Reviewed code: `00e83b1334c883cea8f6c2b3512cdd00ee92a1c9`.

| Component | Disposition | Evidence and limit |
|---|---|---|
| Existing source/version/lifecycle/risk/canonical/authority protections | KEEP | Required safety boundary. Real internal policy guards were exercised; no authorization to weaken the product contract follows. |
| Real P handler and current product defaults | KEEP | Unchanged reference implementation; native 23/23 paired subset passed. Full current paired CI was not yet complete at report time. |
| Native FTS instrumentation and frozen-input diagnostic | OPTIONAL | Useful opt-in research plumbing; real assertions and smoke steps passed. Not a new public runtime or proven quality improvement. |
| Corrected representation B and structural assembly D | NOT_EVALUATED | Not implemented or tested as arms in this slice. |
| Legacy soft relevance rules E_G | NOT_EVALUATED | No matched saved-input quality contrast, no remove-one-on-P evidence. Do not delete rules. |
| Legacy ordering/packing E_GR | NOT_EVALUATED | Bypassing ranking is instrumented for the native diagnostic, but no safe final A packet or quality comparison exists. |
| Dense/hybrid/fusion | NOT_EVALUATED | No model provider, inference or new model download was performed. No lexical fallback is labeled hybrid success. |
| Agent skill/answerer quality | NOT_EVALUATED | No actual new model generations and no blinded evaluation. |

## Next minimal implementation boundary

Complete a private shared PacketPort by reusing actual source/reference and
qualification objects, renderer, token estimator, combined-window validator and
authority rules. Add negative integration tests for wrong-scope/version/current
snapshot, modified ranges/quotes, neighboring API ownership and false authority.
Until those pass, keep `BLOCKED_SAFE_PACKET_ADAPTER` and no public A packet.

Then establish an actual worker filesystem/process boundary that excludes
private reviewer labels, with I/O tests; finalize uncapped-trace provenance and
paired regression evidence. Only after those boundaries are verified should the
next separate T05–T07 stage implement B, D_L and the two legacy add-one contrasts.
A new freeze is required whenever code, inputs or parameters change.

No simplification patch, threshold change, product activation, merge or quality
non-inferiority claim is approved by this report. A result of INCONCLUSIVE is not
a finding of equivalence and not permission to remove all heuristics.
