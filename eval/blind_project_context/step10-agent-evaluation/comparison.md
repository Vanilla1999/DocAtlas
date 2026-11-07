# Step 10: fresh baseline versus measured candidate

Measured candidate does not meet the quality or token-efficiency objective: 16/46 versus 42/46 facts; recorded total input+cache is higher even with eight censored failures. L0 alone spends 6.16x matched baseline input+cache and delivers fewer facts. No claim of cost savings is supported.

| Arm/subset | Facts | Full answers | Input | Cache read | Input + cache | Output | Censored |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fresh baseline, all16 | 42/46 | 12/16 | 138621 | 31232 | 169853 | 9315 | 0 |
| Candidate, all16 | 16/46 | 5/16 | 372326 | 28032 | 400358 | 4043 | 8 |
| Fresh baseline, L0 | 21/23 | 6/8 | 49458 | 8064 | 57522 | 4454 | 0 |
| Candidate, L0 | 16/23 | 5/8 | 331824 | 22784 | 354608 | 3455 | 0 |
| Fresh baseline, L2 | 21/23 | 6/8 | 89163 | 23168 | 112331 | 4861 | 0 |
| Candidate, L2 | 0/23 | 0/8 | 40502 | 5248 | 45750 | 588 | 8 |

Full-run recorded input+cache ratio: **at least 2.357×** the fresh baseline's **169853 tokens / 16 sessions**. Both arms report zero reasoning tokens and zero cache-write tokens. Censored usage remains a lower bound, not a zero-cost result.

## Matched L0 result

**16/23 versus 21/23 facts; 354608 versus 57522 input+cache tokens (6.165×).** All eight candidate L0 trajectories completed, so this is the meaningful matched operational comparison. It still has six exact-question contract violations. Candidate L0 time sums to 823.21 seconds; the eight measured durations are 72.34–173.37 seconds.

## L2 censorship

All eight L2 candidate sessions timed out at approximately 900 seconds, emitted no final answers and deliver 0/23 required facts. They remain in the 46-fact denominator. Lower recorded L2 input than the baseline is not evidence of efficiency: no task completed, and unrecorded in-flight work may increase cost. The saved completed-tool stream contains no context result or original get_docs_context arguments for these sessions.

## Contract and source findings

Six L0 requests added surrounding quote characters to the frozen question. T01-en and T05-ru preserved it exactly; L2 preservation is unobservable from saved events. These deviations are reported as protocol failures, not normalized or excused.
Whole-document delivery is explained by conservative semantic membership plus structural closure, not filling a token budget. Successful L0 packets explicitly reported unverified context and incomplete structural dependencies. T02 and T12 emergency stops rejected candidate packets of 50110 and 50297 tokens; those rejected sizes are not delivered model-input usage.
Independent checks compare source text with frozen file spans and citation references with issued source rows. Public content_sha256 is a projection-material fingerprint; no sha256(snippet) equality was assumed.

## Historical/setup accounting stays separate

The denied-access baseline and unprepared initial candidate are in `failed-attempts.{json,md}`. Older step9 measurements are historical and are not this comparison denominator. The fresh valid baseline is `baseline-valid.{json,md}`; final candidate details are `candidate.{json,md}`. Earlier partial snapshots remain preserved.

No policy, threshold, source, question, measured wheel or agent runner was changed during grading. No additional model/product calls were made. The same manual final-answer rule applies to both fresh arms; partial facts count as zero. Supporting citations do not repair omissions in final prose.
