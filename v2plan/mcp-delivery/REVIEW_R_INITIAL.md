# Independent initial review — open findings

Reviewed A integration `e69b57b1` and C committed `2abf253d` / `f9513f18`.
B and C's indexed followup were not in scope. Source-derived review; no
hostile filesystem or Windows reproduction executed by R.

| ID | Severity | Finding | Owner | State |
|---|---|---|---|---|
| R1 | High | Path checks do not pin subsequent SQLite DB/journal boundary against parent replacement | A | OPEN |
| R2 | Medium | Input source/catalog/config hardlinks not rejected | A | OPEN |
| R3 | Medium | Aggregate byte/deadline checks happen after excess document read | A | OPEN |
| R4 | Medium | Owned server named `servers` inside V2 mapping is skipped, permitting duplicate registration | C | OPEN |
| R5 | Medium | POSIX descriptor primitives lack deliberate unsupported-platform guard on Windows | A | OPEN |
| R6 | Medium | Host accepts error-marked/malformed/conflicting structured and text evidence channels | B | OPEN |
| R7 | Medium | Host permits forged visible requirement-to-witness syntactic binding | B | OPEN |
| R8 | Medium | Host source line endpoints need not match retained text and are copied into citations | B | OPEN |
| R9 | Medium | Native recovery drops explicit scope/module/version bindings and admits contradictory versions | B | OPEN |

SQLite generation comparison, source ownership and rollback use one
`BEGIN IMMEDIATE` transaction; R found no independent SQL atomicity defect.
Caller confirmation remains intent, not issuer authentication. Cold database
creation/migration is not implemented by the authorized lane. Exact replay after
a changed generation is stale; no-op requests use the explicitly updated
expected generation. These limits must remain visible in acceptance reporting.

No full installed/deployed/release certification was issued. Final closure
requires fixes, targeted tests and independent re-review on the integrated SHA.

## Native consumer followup

R independently ran 39 focused tests plus one targeted recovery case with normal
conftest, and directly reproduced R6–R9 with adversarial probes. No production
edits or historical suite runs. Native retention/copies and absence of invented
read capabilities passed their reviewed checks, but do not close R6–R9.
No new finding in the reviewed coding instructions, projection split, CLI
early-denial/helper extraction or coordinator active assertion migrations.
Those coordinator conclusions were static-only, not full release certification.
